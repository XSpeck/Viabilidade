"""
Página de Auditoria - Acesso restrito ao Leo
Salve como: pages/auditoria.py
"""

import streamlit as st
from viability_functions import format_time_br
from login_system import require_authentication
from viability_functions import (
    get_pending_viabilities,
    update_viability_ftth,
    update_viability_ftta,
    delete_viability,
    get_statistics
)
import logging

logger = logging.getLogger(__name__)

# ======================
# Configuração da Página
# ======================
st.set_page_config(
    page_title="Auditoria - Validador de Projetos",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Verificar autenticação
if not require_authentication():
    st.stop()

# Verificar se é Leo
if st.session_state.user_login.lower() != "leo":
    st.error("🚫 Acesso Negado! Esta página é restrita ao usuário Leo.")
    st.info("👈 Use o menu lateral para navegar para outras páginas.")
    st.stop()

# ======================
# Header
# ======================
st.title("🔍 Auditoria de Viabilizações")
st.markdown("Análise técnica das solicitações de viabilidade")

# Botão de atualizar
col_header1, col_header2 = st.columns([4, 1])
with col_header2:
    if st.button("🔄 Atualizar", use_container_width=True):
        st.rerun()

def format_time_no_convert(iso_string: str) -> str:
    """Formata a string ISO sem alterar o fuso horário (já vem em horário de Brasília)"""
    if not iso_string:
        return "-"
    try:
        dt = datetime.fromisoformat(str(iso_string))
        # se já tem fuso (-03:00), apenas formata
        return dt.strftime('%d/%m/%Y %H:%M')
    except Exception:
        return str(iso_string)[:16]

# ======================
# Função de Formulário
# ======================
def show_viability_form(row: dict, urgente: bool = False):
    """Exibe formulário de auditoria para uma viabilização"""
    
    # Estilo do card baseado na urgência
    if urgente:
        border_color = "#FF4444"
        bg_color = "#FFF5F5"
        icon = "🔥"
    else:
        border_color = "#667eea"
        bg_color = "#F8F9FA"
        icon = "📋"
    
    with st.container():
        st.markdown(f"""
        <div style='border-left: 5px solid {border_color}; padding: 15px; 
                    background-color: {bg_color}; border-radius: 5px; margin-bottom: 20px;'>
        </div>
        """, unsafe_allow_html=True)
        
        # Cabeçalho
        col_title, col_delete = st.columns([5, 1])
        with col_title:
            st.markdown(f"### {icon} Solicitação #{row['id'][:8]}")
        with col_delete:
            if st.button("🗑️", key=f"delete_{row['id']}", help="Excluir solicitação"):
                if delete_viability(row['id']):
                    st.success("✅ Solicitação excluída!")
                    st.rerun()
        
        # Informações da solicitação
        col1, col2 = st.columns([2, 3])
        
        with col1:
            st.markdown("#### 📍 Informações")
            st.text(f"👤 Usuário: {row['usuario']}")
            st.text(f"📍 Plus Code: {row['plus_code_cliente']}")
            st.text(f"🔍 Tipo: {row['tipo_instalacao']}")
            st.text(f"🏨 Nome: {row['predio_ftta']}")
            st.text(f"📅 Solicitado em: {format_time_no_convert(row['data_auditoria'])}")
            if urgente:
                st.error("🔥 **URGENTE - Cliente Presencial**")
        
        with col2:
            # Formulário baseado no tipo
            if row['tipo_instalacao'] == 'FTTH':
                st.markdown("#### 🏠 Dados FTTH (Casa)")
                
                with st.form(key=f"form_ftth_{row['id']}"):
                    cto = st.text_input("N° Caixa (CTO)", key=f"cto_{row['id']}")
                    
                    col_f1, col_f2 = st.columns(2)
                    with col_f1:
                        portas = st.number_input("Portas Disponíveis", min_value=0, max_value=50, value=0, key=f"portas_{row['id']}")
                    with col_f2:
                        rx = st.text_input("Menor RX (dBm)", placeholder="-18.67", key=f"rx_{row['id']}")
                    
                    col_f3, col_f4 = st.columns(2)
                    with col_f3:
                        distancia = st.text_input("Distância até Cliente", placeholder="64.3m", key=f"dist_{row['id']}")
                    with col_f4:
                        localizacao = st.text_input("Localização da Caixa", key=f"loc_{row['id']}")
                    
                    obs = st.text_area("Observações", key=f"obs_{row['id']}", height=80)
                    
                    # Botões
                    col_btn1, col_btn2, col_btn3 = st.columns(3)
                    
                    with col_btn1:
                        aprovado = st.form_submit_button("✅ Viabilizar", type="primary", use_container_width=True)
                    with col_btn2:  # ← NOVO BOTÃO AQUI
                        utp = st.form_submit_button("📡 Atendemos UTP", use_container_width=True)
                    with col_btn3:
                        rejeitado = st.form_submit_button("❌ Sem Viabilidade", type="secondary", use_container_width=True)
                    
                    if aprovado:
                        if cto and portas > 0 and rx and distancia and localizacao:
                            dados = {
                                'cto_numero': cto,
                                'portas_disponiveis': portas,
                                'menor_rx': rx,
                                'distancia_cliente': distancia,
                                'localizacao_caixa': localizacao,
                                'observacoes': obs
                            }
                            if update_viability_ftth(row['id'], 'aprovado', dados):
                                st.success("✅ Viabilização aprovada!")
                                st.balloons()
                                st.rerun()
                        else:
                            st.error("❌ Preencha todos os campos obrigatórios!")
                    
                    if rejeitado:
                        dados = {'motivo_rejeicao': 'Não temos projeto neste ponto'}
                        if update_viability_ftth(row['id'], 'rejeitado', dados):
                            st.success("❌ Solicitação rejeitada")
                            st.rerun()
                    if utp:
                        dados = {'motivo_rejeicao': 'Atendemos UTP'}
                        if update_viability_ftth(row['id'], 'utp', dados):
                            st.success("📡 Marcado como Atendemos UTP")
                            st.rerun()
            else:  # FTTA
                st.markdown("#### 🏢 Dados FTTA (Edifício)")
                
                with st.form(key=f"form_ftta_{row['id']}"):
                    predio = st.text_input("Prédio FTTA", key=f"predio_{row['id']}")
                    
                    col_f1, col_f2 = st.columns(2)
                    with col_f1:
                        portas = st.number_input("Portas Disponíveis", min_value=0, max_value=50, value=0, key=f"portas_ftta_{row['id']}")
                    with col_f2:
                        media_rx = st.text_input("Média RX (dBm)", placeholder="-20.5", key=f"media_rx_{row['id']}")
                    
                    obs = st.text_area("Observações", key=f"obs_ftta_{row['id']}", height=80)
                    
                    # Botões
                    col_btn1, col_btn2, col_btn3 = st.columns(3)
                    
                    with col_btn1:
                        aprovado = st.form_submit_button("✅ Viabilizar", type="primary", use_container_width=True)
                    with col_btn2:
                        utp = st.form_submit_button("📡 Atendemos UTP", use_container_width=True)                    
                    with col_btn3:
                        rejeitado = st.form_submit_button("❌ Sem Viabilidade", type="secondary", use_container_width=True)
                    
                    if aprovado:
                        if predio and portas > 0 and media_rx:
                            dados = {
                                'predio_ftta': predio,
                                'portas_disponiveis': portas,
                                'media_rx': media_rx,
                                'observacoes': obs
                            }
                            if update_viability_ftta(row['id'], 'aprovado', dados):
                                st.success("✅ Viabilização aprovada!")
                                st.balloons()
                                st.rerun()
                        else:
                            st.error("❌ Preencha todos os campos obrigatórios!")
                    
                    if rejeitado:
                        dados = {'motivo_rejeicao': 'Não temos projeto neste ponto'}
                        if update_viability_ftta(row['id'], 'rejeitado', dados):
                            st.success("❌ Solicitação rejeitada")
                            st.rerun()
                    if utp:
                        dados = {'motivo_rejeicao': 'Atendemos UTP'}
                        if update_viability_ftta(row['id'], 'utp', dados):
                            st.success("📡 Marcado como Atendemos UTP")
                            st.rerun()
                            
        st.markdown("---")

# ======================
# Buscar Pendências
# ======================
pending = get_pending_viabilities()

if not pending:
    st.info("✅ Não há solicitações pendentes de auditoria no momento.")
    st.success("👏 Parabéns! Todas as solicitações foram processadas.")
else:
    st.subheader(f"📋 {len(pending)} Solicitações Pendentes")
    
    # Separar urgentes e normais
    urgentes = [p for p in pending if p.get('urgente', False)]
    normais = [p for p in pending if not p.get('urgente', False)]
    
    # Mostrar urgentes primeiro
    if urgentes:
        st.markdown("### 🔥 URGENTES - Cliente Presencial")
        for row in urgentes:
            show_viability_form(row, urgente=True)
    
    # Mostrar normais
    if normais:
        if urgentes:
            st.markdown("---")
        st.markdown("### 📝 Solicitações Normais")
        for row in normais:
            show_viability_form(row, urgente=False)



# ======================
# Footer
# ======================
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <p>🔍 <strong>Validador de Projetos</strong> | Desenvolvido ByLeo</p>
</div>
""", unsafe_allow_html=True)

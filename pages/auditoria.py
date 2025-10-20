"""
Página de Auditoria - Acesso restrito ao Leo
Salve como: pages/auditoria.py
"""

import streamlit as st
from login_system import require_authentication
from streamlit_autorefresh import st_autorefresh
from viability_functions import (
    format_time_br_supa,
    get_pending_viabilities,
    update_viability_ftth,
    update_viability_ftta,
    delete_viability,
    get_statistics,
    request_building_viability,
    reject_building_viability 
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

# ======================
# Atualização automática
# ======================
from streamlit_autorefresh import st_autorefresh  # opcional se quiser externalizar
st_autorefresh(interval=15000, key="auditoria_refresh")  # 15000 ms = 15 segundos

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
            if row.get('predio_ftta'):
                st.text(f"🏨 Nome: {row['predio_ftta']}")            
            st.text(f"📅 Solicitado em: {format_time_br_supa(row['data_solicitacao'])}")
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
                # Verificar se já foi solicitada viabilização de prédio
                status_predio = row.get('status_predio')
                
                # Se ainda não foi solicitado OU se foi rejeitado, mostrar formulário normal
                if status_predio is None or status_predio == 'rejeitado':
                    st.markdown("#### 🏢 Dados FTTA (Edifício)")
                    
                    with st.form(key=f"form_ftta_{row['id']}"):
                        predio = st.text_input("Prédio FTTA", value=row.get('predio_ftta', ''), key=f"predio_{row['id']}")
                        
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
                    
                    # ===== BOTÃO VIABILIZAR PRÉDIO (apenas se ainda não foi solicitado) =====
                    if status_predio is None:
                        st.markdown("---")
                        st.markdown("#### 🏗️ Viabilização de Estrutura no Prédio")
                        st.info("🔧 Temos projeto na rua, mas não temos estrutura pronta no prédio")
                        
                        col_viab_pred = st.columns([1, 2, 1])[1]
                        with col_viab_pred:
                            if st.button(
                                "🏢 Solicitar Viabilização do Prédio", 
                                type="primary", 
                                use_container_width=True,
                                key=f"viab_predio_{row['id']}"
                            ):
                                if request_building_viability(row['id'], {}):
                                    st.success("✅ Solicitação enviada! Aguardando dados do usuário.")
                                    st.info("👤 O usuário receberá um formulário para preencher.")
                                    st.rerun()
                
                # Se está aguardando dados do usuário
                elif status_predio == 'aguardando_dados':
                    st.markdown("#### 🏗️ Viabilização de Estrutura no Prédio")
                    st.warning("⏳ **Aguardando dados do usuário**")
                    st.caption(f"📅 Solicitado em: {format_time_br_supa(row.get('data_solicitacao_predio', ''))}")
                    st.info("👤 O usuário está preenchendo o formulário com os dados do prédio.")
                
                # Se os dados foram recebidos e está pronto para análise
                elif status_predio == 'pronto_auditoria':
                    st.markdown("#### 🏗️ Viabilização de Estrutura no Prédio")
                    st.success("✅ **Dados recebidos! Pronto para análise**")
                    
                    # Mostrar dados recebidos
                    with st.expander("👁️ Ver Dados do Cliente", expanded=True):
                        col_dados1, col_dados2 = st.columns(2)
                        with col_dados1:
                            st.markdown("**👤 Síndico**")
                            st.text(f"Nome: {row.get('nome_sindico', 'N/A')}")
                            st.text(f"Contato: {row.get('contato_sindico', 'N/A')}")
                        with col_dados2:
                            st.markdown("**🏠 Cliente**")
                            st.text(f"Nome: {row.get('nome_cliente_predio', 'N/A')}")
                            st.text(f"Contato: {row.get('contato_cliente_predio', 'N/A')}")
                        
                        st.text(f"🚪 Apartamento: {row.get('apartamento', 'N/A')}")
                        st.text(f"🏢 Edifício: {row.get('predio_ftta', 'N/A')}")
                        st.text(f"📍 Localização: {row['plus_code_cliente']}")
                        
                        if row.get('obs_agendamento'):
                            st.markdown("**📝 Melhores horários:**")
                            st.info(row['obs_agendamento'])
                    
                    st.markdown("---")
                    st.markdown("### 📅 Agendar Visita Técnica")
                    
                    # Formulário de agendamento
                    col_ag1, col_ag2 = st.columns(2)
                    
                    with col_ag1:
                        data_visita = st.date_input(
                            "📅 Data da Visita",
                            key=f"data_visita_{row['id']}",
                            help="Selecione a data para visita técnica",
                            format="DD/MM/YYYY"
                        )
                    
                    with col_ag2:
                        periodo = st.selectbox(
                            "🕐 Período",
                            options=["Manhã", "Tarde"],
                            key=f"periodo_{row['id']}"
                        )
                        
                    # Segunda linha com Técnico e Tecnologia
                    col_ag3, col_ag4 = st.columns(2)
                    
                    with col_ag3:
                        tecnico = st.text_input(
                            "👷 Técnico Responsável",
                            placeholder="Nome do técnico",
                            key=f"tecnico_{row['id']}"
                        )
                    with col_ag4:
                        tecnologia = st.selectbox(
                            "🔧 Tecnologia",
                            options=["FTTA", "UTP"],
                            key=f"tecnologia_{row['id']}",
                            help="Tipo de tecnologia a ser instalada"
                        )
                    
                    st.markdown("---")
                    
                    # Botões de ação
                    col_action1, col_action2 = st.columns(2)
                    
                    with col_action1:
                        if st.button(
                            "📋 Agendar Visita Técnica",
                            type="primary",
                            use_container_width=True,
                            key=f"agendar_{row['id']}"
                        ):
                            if not tecnico or not data_visita or not tecnologia:
                                st.error("❌ Preencha todos os campos de agendamento!")
                            else:
                                st.info("🚧 Funcionalidade será implementada no Passo 3")
                                # Aqui vai a função do Passo 3
                    
                    with col_action2:
                        if st.button(
                            "❌ Edifício Sem Viabilidade",
                            type="secondary",
                            use_container_width=True,
                            key=f"sem_viab_{row['id']}"
                        ):
                            st.session_state[f'show_reject_form_{row["id"]}'] = True
                    
                    # Formulário de rejeição (aparece ao clicar no botão)
                    if st.session_state.get(f'show_reject_form_{row["id"]}', False):
                        st.markdown("---")
                        st.error("### ❌ Registrar Edifício Sem Viabilidade")
                        
                        with st.form(key=f"form_reject_building_{row['id']}"):
                            st.markdown("**Os seguintes dados serão registrados para consulta futura:**")
                            
                            col_rej1, col_rej2 = st.columns(2)
                            with col_rej1:
                                st.text_input("🏢 Condomínio", value=row.get('predio_ftta', ''), disabled=True)
                            with col_rej2:
                                st.text_input("📍 Localização", value=row['plus_code_cliente'], disabled=True)
                            
                            motivo_rejeicao = st.text_area(
                                "📝 Motivo da Não Viabilidade *",
                                placeholder="Descreva o motivo: estrutura inadequada, recusa do síndico, etc.",
                                height=100
                            )
                            
                            col_btn_rej1, col_btn_rej2 = st.columns(2)
                            
                            with col_btn_rej1:
                                confirmar_rejeicao = st.form_submit_button(
                                    "✅ Confirmar Rejeição",
                                    type="primary",
                                    use_container_width=True
                                )
                            
                            with col_btn_rej2:
                                cancelar = st.form_submit_button(
                                    "🔙 Cancelar",
                                    use_container_width=True
                                )
                            
                            if confirmar_rejeicao:
                                if not motivo_rejeicao or motivo_rejeicao.strip() == "":
                                    st.error("❌ Descreva o motivo da não viabilidade!")
                                else:                                                                        
                                    if reject_building_viability(
                                        row['id'],
                                        row.get('predio_ftta', 'Prédio'),
                                        row['plus_code_cliente'],
                                        motivo_rejeicao.strip()
                                    ):
                                        st.success("✅ Edifício registrado como sem viabilidade!")
                                        st.info("📝 Registro salvo para consulta futura")
                                        del st.session_state[f'show_reject_form_{row["id"]}']
                                        st.rerun()
                                    else:
                                        st.error("❌ Erro ao registrar. Tente novamente.")
                            
                            if cancelar:
                                del st.session_state[f'show_reject_form_{row["id"]}']
                                st.rerun()   
                            
        st.markdown("---")

# ======================
# Buscar Pendências
# ======================
pending = get_pending_viabilities()

# ======================
# Notificação de novas solicitações
# ======================
if "pendentes_anteriores" not in st.session_state:
    st.session_state.pendentes_anteriores = len(pending)

# Se há novas solicitações desde a última atualização
if len(pending) > st.session_state.pendentes_anteriores:
    novas = len(pending) - st.session_state.pendentes_anteriores
    st.toast(f"🔔 {novas} nova(s) solicitação(ões) aguardando auditoria!", icon="📬")
    st.markdown("""
    <audio autoplay>
        <source src="https://actions.google.com/sounds/v1/alarms/beep_short.ogg" type="audio/ogg">
    </audio>
    """, unsafe_allow_html=True)

# Atualiza contador
st.session_state.pendentes_anteriores = len(pending)

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

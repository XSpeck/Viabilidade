"""
Página de Auditoria - Acesso restrito Nv 1
Salve como: pages/auditoria.py
"""

import streamlit as st
from login_system import require_authentication
from viability_functions import (
    format_time_br_supa,
    delete_viability,
    get_auditor_viabilities,
    devolver_viabilidade
)
import logging
# Imports dos manipuladores
from pages.auditoria_functions.ftth_handler import show_ftth_form
from pages.auditoria_functions.ftta_handler import show_ftta_form

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

# Verificar se é Admin (nível 1)
if st.session_state.user_nivel != 1:
    st.error("🚫 Acesso Negado! Esta página é restrita a administradores.")
    st.info("👈 Use o menu lateral para navegar.")
    st.stop()

# ======================
# Header
# ======================
st.title("🔍 Auditoria de Viabilizações")
st.markdown("Análise técnica das solicitações de viabilidade")

# Botão de atualizar
col_header1, col_header2 = st.columns([4, 1])
with col_header2:
    if st.button("🔄 Atualizar", width='stretch'):
        st.rerun()

# ======================
# Função de Formulário
# ======================
def show_viability_form(row: dict, urgente: bool = False):
    """Exibe formulário de auditoria para uma viabilização"""
    
    # Estilo do card baseado na urgência
    if urgente:
        icon = "🔥"
        badge_urgente = " - **URGENTE**"
    else:
        icon = "📋"
        badge_urgente = "" 
    
    # Determinar tipo para exibição
    if row['tipo_instalacao'] == 'FTTH':
        tipo_exibir = 'FTTH (Casa)'
        tipo_icon = "🏠"
    elif row['tipo_instalacao'] == 'Prédio':
        if row.get('tecnologia_predio'):
            tipo_exibir = f"{row['tecnologia_predio']} (Prédio)"
        else:
            tipo_exibir = 'Prédio'
        tipo_icon = "🏢"
    else:
        tipo_exibir = row['tipo_instalacao']
        tipo_icon = "📋"
    
    # Criar título do expander (resumo)
    titulo_expander = f"{icon} {tipo_icon} **{row.get('nome_cliente', 'Cliente')}** | {row['plus_code_cliente']}"
    
    if row.get('predio_ftta'):
        titulo_expander += f" | 🏢 {row['predio_ftta']}"
        detalhes_apt = []
        if row.get('andar_predio'):
            detalhes_apt.append(f"Andar {row['andar_predio']}")
        if row.get('bloco_predio'):
            detalhes_apt.append(f"Bloco {row['bloco_predio']}")
        
        if detalhes_apt:
            titulo_expander += f" ({', '.join(detalhes_apt)})"
    
    titulo_expander += badge_urgente
    
    # Criar subtítulo (informações extras)
    subtitulo = f"👤 Solicitado por: {row['usuario']} | 📅 {format_time_br_supa(row['data_solicitacao'])}"
    
    # EXPANDER (COLAPSADO POR PADRÃO)
    with st.expander(titulo_expander, expanded=False):
        st.caption(subtitulo)
        st.markdown("---")        
                
        # Informações da solicitação
        col1, col2 = st.columns([2, 3])
        
        with col1:
            st.markdown("#### 📋 Informações")
            st.text(f"👤 Usuário: {row['usuario']}")
            if row.get('nome_cliente'):
                st.text(f"🙋 Cliente: {row['nome_cliente']}")
            st.text(f"📍 Plus Code: {row['plus_code_cliente']}")
            
            # Determinar tipo real
            if row['tipo_instalacao'] == 'FTTH':
                tipo_exibir = 'FTTH (Casa)'
            elif row['tipo_instalacao'] == 'Prédio':
                if row.get('tecnologia_predio'):
                    tipo_exibir = f"{row['tecnologia_predio']} (Prédio)"
                else:
                    tipo_exibir = 'Prédio (a definir)'
            else:
                tipo_exibir = row['tipo_instalacao']
            
            st.text(f"🏷️ Tipo: {tipo_exibir}")
            
            if row.get('predio_ftta'):
                st.text(f"🏨 Nome: {row['predio_ftta']}")
                if row.get('andar_predio'):
                    st.text(f"🏗️ Andar: {row['andar_predio']}")
                if row.get('bloco_predio'):
                    st.text(f"🏢 Bloco: {row['bloco_predio']}")
                
            st.text(f"📅 Solicitado em: {format_time_br_supa(row['data_solicitacao'])}")
            
            # ===== BOTÃO EXCLUIR =====
            st.markdown("---")
            if st.button(
                "🗑️ Excluir Solicitação",
                key=f"delete_{row['id']}",
                type="secondary",
                width='stretch',
                help="Excluir esta solicitação permanentemente"
            ):
                if delete_viability(row['id']):
                    st.success("✅ Solicitação excluída!")
                    st.rerun()            
            if urgente:
                st.error("🔥 **URGENTE - Cliente Presencial**")

            # Botão para devolver viabilização
            col_devolver = st.columns([1, 2, 1])[1]
            with col_devolver:
                if st.button(
                    "↩️ Devolver para Fila",
                    key=f"devolver_{row['id']}",
                    type="secondary",
                    width='stretch',
                    help="Devolve esta viabilização para outros auditores pegarem"
                ):
                    if devolver_viabilidade(row['id']):
                        st.success("✅ Viabilização devolvida!")
                        st.rerun()
        
        with col2:
            # Chamar formulário apropriado baseado no tipo
            if row['tipo_instalacao'] == 'FTTH':
                show_ftth_form(row)
            else:  # Prédio
                show_ftta_form(row)
                            
        st.markdown("---")

# ======================
# Buscar Pendências
# ======================
pending = get_auditor_viabilities(st.session_state.user_name)

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
    st.markdown("---")
    # ======================
    # Separar por tipo e urgência
    # ======================
    urgentes = [p for p in pending if p.get('urgente', False)]
    ftth = [p for p in pending if p['tipo_instalacao'] == 'FTTH' and not p.get('urgente', False)]
    
    # Separar prédios por status
    predios_novos = [
        p for p in pending 
        if p['tipo_instalacao'] == 'Prédio' 
        and not p.get('urgente', False)
        and p.get('status_predio') is None
    ]
    
    predios_aguardando_dados = [
        p for p in pending 
        if p['tipo_instalacao'] == 'Prédio' 
        and not p.get('urgente', False)
        and p.get('status_predio') == 'aguardando_dados'
    ]
    
    predios_prontos_agendar = [
        p for p in pending 
        if p['tipo_instalacao'] == 'Prédio' 
        and not p.get('urgente', False)
        and p.get('status_predio') == 'pronto_auditoria'
    ]
    
    predios_agendados = [
        p for p in pending 
        if p['tipo_instalacao'] == 'Prédio' 
        and not p.get('urgente', False)
        and p.get('status_predio') == 'agendado'
    ]
    
    # ======================
    # SISTEMA DE ABAS
    # ======================
    # Criar nomes das abas com contadores
    tab_names = []

    if urgentes:
        tab_names.append(f"🔥 URGENTES ({len(urgentes)})")
    
    if ftth:
        tab_names.append(f"🏠 FTTH ({len(ftth)})")
    
    if predios_novos:
        tab_names.append(f"🏢 PRÉDIOS NOVOS ({len(predios_novos)})")
    
    if predios_aguardando_dados:
        tab_names.append(f"⏳ AGUARDANDO DADOS ({len(predios_aguardando_dados)})")
    
    if predios_prontos_agendar:
        tab_names.append(f"📅 PRONTOS P/ AGENDAR ({len(predios_prontos_agendar)})")
    
    if predios_agendados:
        tab_names.append(f"✅ AGENDADOS ({len(predios_agendados)})")
    
    # Se não houver abas (nenhuma pendência), não mostrar nada
    if not tab_names:
        pass
    else:
        # Criar as abas dinamicamente
        tabs = st.tabs(tab_names)
        
        tab_index = 0
        
        # ABA URGENTES
        if urgentes:
            with tabs[tab_index]:
                st.warning("⚠️ **Clientes Presenciais - Prioridade Máxima**")
                st.caption(f"📊 {len(urgentes)} solicitação(ões) urgente(s)")
                st.markdown("---")
                
                for row in urgentes:
                    show_viability_form(row, urgente=True)
            
            tab_index += 1
        
        # ABA FTTH
        if ftth:
            with tabs[tab_index]:
                st.info("🏠 **Instalações Residenciais (FTTH)**")
                st.caption(f"📊 {len(ftth)} solicitação(ões) de casa")
                st.markdown("---")
                
                for row in ftth:
                    show_viability_form(row, urgente=False)
            
            tab_index += 1
        
        # ABA PRÉDIOS
        if predios_novos:
            with tabs[tab_index]:
                st.info("🏢 **Prédios Aguardando Análise Inicial**")
                st.caption(f"📊 {len(predios_novos)} prédio(s) para auditar")
                st.markdown("---")
                
                for row in predios_novos:
                    show_viability_form(row, urgente=False)
            
            tab_index += 1
        
        # ABA AGUARDANDO DADOS DO USUÁRIO
        if predios_aguardando_dados:
            with tabs[tab_index]:
                st.warning("⏳ **Aguardando Usuário Preencher Dados**")
                st.caption(f"📊 {len(predios_aguardando_dados)} prédio(s) esperando formulário")
                st.info("💡 Estes prédios estão aguardando o usuário preencher os dados do síndico e cliente")
                st.markdown("---")
                
                for row in predios_aguardando_dados:
                    show_viability_form(row, urgente=False)
            
            tab_index += 1
        
        # ABA PRONTOS PARA AGENDAR
        if predios_prontos_agendar:
            with tabs[tab_index]:
                st.success("📅 **Prontos para Agendamento**")
                st.caption(f"📊 {len(predios_prontos_agendar)} prédio(s) com dados completos")
                st.info("🎯 Ação necessária: Agendar visita técnica")
                st.markdown("---")
                
                for row in predios_prontos_agendar:
                    show_viability_form(row, urgente=False)
            
            tab_index += 1
        
        # ABA AGENDADOS (INFORMATIVO)
        if predios_agendados:
            with tabs[tab_index]:
                st.info("✅ **Visitas Técnicas Agendadas**")
                st.caption(f"📊 {len(predios_agendados)} prédio(s) agendado(s)")
                st.success("🗓️ Estes agendamentos estão na página 'Agenda FTTA/UTP'")
                st.markdown("---")
                
                for row in predios_agendados:
                    # Card resumido, só para visualização
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.markdown("**🏢 Prédio**")
                        st.text(row.get('predio_ftta', 'N/A'))
                    
                    with col2:
                        st.markdown("**📅 Data Visita**")
                        data_visita = row.get('data_visita', 'N/A')
                        if data_visita and data_visita != 'N/A':
                            try:
                                from datetime import datetime
                                data_obj = datetime.strptime(data_visita, '%Y-%m-%d')
                                data_visita = data_obj.strftime('%d/%m/%Y')
                            except:
                                pass
                        st.text(data_visita)
                    
                    with col3:
                        st.markdown("**👷 Técnico**")
                        st.text(row.get('tecnico_responsavel', 'N/A'))
                    
                    with col4:
                        st.markdown("**🔧 Tecnologia**")
                        st.text(row.get('tecnologia_predio', 'N/A'))
                    
                    st.markdown("---")


# ======================
# Footer
# ======================
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <p>🔍 <strong>Validador de Projetos</strong> | Desenvolvido ByLeo</p>
</div>
""", unsafe_allow_html=True)

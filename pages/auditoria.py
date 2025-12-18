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
def show_viability_form(row: dict, urgente: bool = False, context: str = ''):
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
                key=f"delete_{row['id']}_{context}",
                type="secondary",
                width='stretch',
                help="Excluir esta solicitação permanentemente"
            ):
                ok = False
                info = None
                try:
                    ok, info = delete_viability(row['id'])
                except Exception as e:
                    logger.exception(f"Erro ao chamar delete_viability UI: {e}")

                if ok:
                    st.success("✅ Solicitação excluída!")
                    st.rerun()
                else:
                    st.error("❌ Não foi possível excluir a solicitação. Verifique permissões/console e tente novamente.")
                    if info:
                        if isinstance(info, dict):
                            st.json(info)
                        else:
                            st.write(info)
            if urgente:
                st.error("🔥 **URGENTE - Cliente Presencial**")

            # Botão para devolver viabilização
            col_devolver = st.columns([1, 2, 1])[1]
            with col_devolver:
                if st.button(
                    "↩️ Devolver para Fila",
                    key=f"devolver_{row['id']}_{context}",
                    type="secondary",
                    width='stretch',
                    help="Devolve esta viabilização para outros auditores pegarem"
                ):
                    ok = False
                    info = None
                    try:
                        ok, info = devolver_viabilidade(row['id'])
                    except Exception as e:
                        logger.exception(f"Erro ao chamar devolver_viabilidade UI: {e}")

                    if ok:
                        st.success("✅ Viabilização devolvida!")
                        st.rerun()
                    else:
                        st.error("❌ Erro ao devolver viabilização. Tente novamente.")
                        if info:
                            if isinstance(info, dict):
                                st.json(info)
                            else:
                                st.write(info)
        
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
    predios = [p for p in pending if p['tipo_instalacao'] == 'Prédio' and not p.get('urgente', False)]
    # Separar prédios em espera (agendamento / aguardando dados) para NÃO misturar com viabilidades ativas
    waiting_statuses = ['agendado', 'pronto_auditoria', 'aguardando_dados']
    predios_espera = [p for p in predios if p.get('status_predio') in waiting_statuses]
    predios_auditar = [p for p in predios if p.get('status_predio') not in waiting_statuses]
    
    # ======================
    # SISTEMA DE ABAS
    # ======================
    # Criar nomes das abas com contadores (não incluir prédios em espera)
    tab_names = []
    if urgentes:
        tab_names.append(f"🔥 URGENTES ({len(urgentes)})")
    if ftth:
        tab_names.append(f"🏠 FTTH ({len(ftth)})")
    if predios_auditar:
        tab_names.append(f"🏢 PRÉDIOS ({len(predios_auditar)})")
    
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
                    show_viability_form(row, urgente=True, context='urgente')
            
            tab_index += 1
        
        # ABA FTTH
        if ftth:
            with tabs[tab_index]:
                st.info("🏠 **Instalações Residenciais (FTTH)**")
                st.caption(f"📊 {len(ftth)} solicitação(ões) de casa")
                st.markdown("---")
                
                for row in ftth:
                    show_viability_form(row, urgente=False, context='ftth')
            
            tab_index += 1
        
        # ABA PRÉDIOS (apenas prédios que precisam de auditoria ativa)
        if predios_auditar:
            with tabs[tab_index]:
                st.info("🏢 **Instalações em Edifícios**")
                st.caption(f"📊 {len(predios_auditar)} solicitação(ões) de prédio")
                st.markdown("---")
                
                for row in predios_auditar:
                    show_viability_form(row, urgente=False, context='predio')

    # ======================
    # Prédios em Espera (Agendamento / Aguardando Dados) - separado para não atrapalhar fila
    # ======================
    # Prédios em Espera (Agendamento / Aguardando Dados) - separado para não atrapalhar fila
    if predios_espera:
        st.markdown("---")
        st.subheader("🏢 Prédios em Espera (Agendamento / Aguardando Dados)")
        st.info("Estes prédios aguardam ação do usuário ou agendamento e foram separados da fila principal.")
        
        for row in predios_espera:
            status_text = row.get('status_predio', 'Em Espera')
            titulo = f"🏢 {row.get('predio_ftta', 'Prédio')} — {row['plus_code_cliente']} — {status_text}"
            
            with st.expander(titulo, expanded=False):
                # Informações principais
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.markdown("#### 📋 Informações Básicas")
                    st.text(f"👤 Solicitante: {row.get('usuario', 'N/A')}")
                    if row.get('nome_cliente'):
                        st.text(f"🙋 Cliente: {row['nome_cliente']}")
                    st.text(f"📍 Plus Code: {row['plus_code_cliente']}")
                    st.text(f"🏨 Prédio: {row.get('predio_ftta', 'N/A')}")
                    if row.get('andar_predio'):
                        st.text(f"🗃️ Andar: {row['andar_predio']}")
                    if row.get('bloco_predio'):
                        st.text(f"🏢 Bloco: {row['bloco_predio']}")
                    st.text(f"📅 Solicitado: {format_time_br_supa(row.get('data_solicitacao'))}")
                    st.text(f"📌 Status: {status_text}")
                
                with col2:
                    st.markdown("#### 📞 Dados de Contato")
                    if row.get('nome_sindico'):
                        st.text(f"👔 Síndico: {row['nome_sindico']}")
                    if row.get('contato_sindico'):
                        st.text(f"📱 Tel. Síndico: {row['contato_sindico']}")
                    if row.get('nome_cliente_predio'):
                        st.text(f"🙋 Cliente: {row['nome_cliente_predio']}")
                    if row.get('contato_cliente_predio'):
                        st.text(f"📱 Tel. Cliente: {row['contato_cliente_predio']}")
                    if row.get('apartamento'):
                        st.text(f"🚪 Apartamento: {row['apartamento']}")
                    
                    # Agendamento
                    if row.get('data_visita'):
                        st.markdown("---")
                        st.markdown("#### 📅 Agendamento")
                        st.text(f"📆 Data: {row['data_visita']}")
                        st.text(f"🕐 Período: {row.get('periodo_visita', 'N/A')}")
                        st.text(f"👷 Técnico: {row.get('tecnico_responsavel', 'N/A')}")
                        st.text(f"🔧 Tecnologia: {row.get('tecnologia_predio', 'N/A')}")
                        if row.get('data_agendamento'):
                            st.text(f"📝 Agendado em: {format_time_br_supa(row['data_agendamento'])}")
                    
                    # Observações
                    if row.get('obs_agendamento'):
                        st.markdown("---")
                        st.text(f"💬 Obs: {row['obs_agendamento']}")
                
                with col3:
                    st.markdown("#### ⚙️ Ações")
                    # Botão Excluir
                    if st.button(
                        "🗑️ Excluir",
                        key=f"delete_espera_{row['id']}",
                        type="secondary",
                        use_container_width=True
                    ):
                        ok, info = delete_viability(row['id'])
                        if ok:
                            st.success("✅ Excluída!")
                            st.rerun()
                        else:
                            st.error("❌ Erro ao excluir")
                            if info:
                                st.json(info)
                    
                    # Botão Devolver
                    if st.button(
                        "↩️ Devolver",
                        key=f"devolver_espera_{row['id']}",
                        type="secondary",
                        use_container_width=True
                    ):
                        ok, info = devolver_viabilidade(row['id'])
                        if ok:
                            st.success("✅ Devolvido!")
                            st.rerun()
                        else:
                            st.error("❌ Erro")
                            if info:
                                st.json(info)


# ======================
# Footer
# ======================
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <p>🔍 <strong>Validador de Projetos</strong> | Desenvolvido ByLeo</p>
</div>
""", unsafe_allow_html=True)

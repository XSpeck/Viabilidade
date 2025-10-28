"""
Página de Viabilidades - Lista de solicitações pendentes para auditores pegarem
Salve como: pages/viabilidades.py
"""

import streamlit as st
from login_system import require_authentication
from streamlit_autorefresh import st_autorefresh
from viability_functions import format_time_br_supa
from supabase_config import supabase
import logging

logger = logging.getLogger(__name__)

# ======================
# Configuração da Página
# ======================
st.set_page_config(
    page_title="Viabilidades - Validador de Projetos",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Auto-refresh a cada 15 segundos
st_autorefresh(interval=15000, key="viabilidades_refresh")

# Verificar autenticação
if not require_authentication():
    st.stop()

# Verificar se é Admin (nível 1)
if st.session_state.user_nivel != 1:
    st.error("🚫 Acesso Negado! Esta página é restrita a auditores.")
    st.info("👈 Use o menu lateral para navegar.")
    st.stop()

# ======================
# Funções
# ======================
def get_pending_viabilities():
    """Busca viabilizações pendentes (ainda não pegou nenhum auditor)"""
    try:
        response = supabase.table('viabilizacoes')\
            .select('*')\
            .eq('status', 'pendente')\
            .is_('auditor_responsavel', None)\
            .order('urgente', desc=True)\
            .order('data_solicitacao', desc=False)\
            .execute()
        
        if response.data:
            # Filtrar prédios agendados
            filtered = [r for r in response.data if r.get('status_predio') != 'agendado']
            return filtered
        return []
    except Exception as e:
        logger.error(f"Erro ao buscar pendentes: {e}")
        return []

def pegar_viabilidade(viability_id: str, auditor: str) -> bool:
    """Marca viabilidade como 'em_auditoria' e atribui ao auditor"""
    try:
        update_data = {
            'status': 'em_auditoria',
            'auditor_responsavel': auditor
        }
        
        response = supabase.table('viabilizacoes')\
            .update(update_data)\
            .eq('id', viability_id)\
            .execute()
        
        if response.data:
            logger.info(f"Viabilização {viability_id} atribuída a {auditor}")
            return True
        return False
    except Exception as e:
        logger.error(f"Erro ao pegar viabilização: {e}")
        return False

def mostrar_card_viabilidade(row: dict, urgente: bool = False):
    """Exibe card resumido de uma viabilização"""
    
    # Determinar tipo e ícone
    if row['tipo_instalacao'] == 'FTTH':
        tipo_icon = "🏠"
        tipo_nome = "Casa (FTTH)"
    elif row['tipo_instalacao'] == 'Prédio':
        tipo_icon = "🏢"
        tipo_nome = "Prédio"
    else:
        tipo_icon = "📋"
        tipo_nome = row['tipo_instalacao']
    
    # Cor da borda
    border_color = "#FF4444" if urgente else "#667eea"
    bg_color = "#FFF5F5" if urgente else "#F8F9FA"
    
    # Container do card
    with st.container():
        st.markdown(f"""
        <div style='border-left: 5px solid {border_color}; padding: 15px; 
                    background-color: {bg_color}; border-radius: 5px; margin-bottom: 15px;'>
        </div>
        """, unsafe_allow_html=True)
        
        # Linha 1: Título
        col_title, col_btn = st.columns([4, 1])
        
        with col_title:
            urgente_badge = " 🔥 **URGENTE**" if urgente else ""
            st.markdown(f"### {tipo_icon} {row.get('nome_cliente', 'Cliente')}{urgente_badge}")
        
        with col_btn:
            if st.button(
                "✅ Pegar",
                key=f"pegar_{row['id']}",
                type="primary",
                use_container_width=True
            ):
                if pegar_viabilidade(row['id'], st.session_state.user_name):
                    st.success(f"✅ Viabilização atribuída a você!")
                    st.info("➡️ Acesse 'Auditoria' no menu para continuar")
                    st.rerun()
                else:
                    st.error("❌ Erro ao pegar viabilização")
        
        # Linha 2: Informações principais
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown("**👤 Solicitante**")
            st.text(row['usuario'])
        
        with col2:
            st.markdown("**📍 Plus Code**")
            st.code(row['plus_code_cliente'], language=None)
        
        with col3:
            st.markdown("**🏷️ Tipo**")
            st.text(tipo_nome)
        
        with col4:
            st.markdown("**📅 Data**")
            st.text(format_time_br_supa(row['data_solicitacao']))
        
        # Linha 3: Informações extras (se houver)
        if row.get('predio_ftta'):
            st.markdown(f"**🏢 Edifício:** {row['predio_ftta']}")
        
        st.markdown("---")

# ======================
# Header
# ======================
st.title("📋 Viabilizações Disponíveis")
st.markdown("Lista de solicitações aguardando auditoria técnica")

# Botão de atualizar
col_header1, col_header2 = st.columns([4, 1])
with col_header2:
    if st.button("🔄 Atualizar", use_container_width=True):
        st.rerun()

st.markdown("---")

# ======================
# Buscar Pendentes
# ======================
pending = get_pending_viabilities()

# Notificação de novas solicitações
if "pendentes_viabilidades" not in st.session_state:
    st.session_state.pendentes_viabilidades = len(pending)

if len(pending) > st.session_state.pendentes_viabilidades:
    novas = len(pending) - st.session_state.pendentes_viabilidades
    st.toast(f"📬 {novas} nova(s) solicitação(ões)!", icon="🆕")

st.session_state.pendentes_viabilidades = len(pending)

# ======================
# Exibir Lista
# ======================
if not pending:
    st.info("✅ Não há viabilizações disponíveis no momento.")
    st.success("🎉 Todas as solicitações foram distribuídas aos auditores!")
else:
    st.subheader(f"📊 {len(pending)} Solicitação(ões) Disponível(is)")
    
    # Separar urgentes e normais
    urgentes = [p for p in pending if p.get('urgente', False)]
    normais = [p for p in pending if not p.get('urgente', False)]
    
    # Mostrar urgentes primeiro
    if urgentes:
        st.error(f"🔥 **{len(urgentes)} URGENTE(S) - Cliente(s) Presencial(is)**")
        st.markdown("---")
        
        for row in urgentes:
            mostrar_card_viabilidade(row, urgente=True)
    
    # Depois mostrar normais
    if normais:
        if urgentes:
            st.markdown("---")
            st.markdown("---")
        st.info(f"📋 **{len(normais)} Solicitação(ões) Normal(is)**")
        st.markdown("---")
        
        for row in normais:
            mostrar_card_viabilidade(row, urgente=False)

# ======================
# Footer
# ======================
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <p>📋 <strong>Validador de Projetos</strong> | Desenvolvido ByLeo</p>
</div>
""", unsafe_allow_html=True)

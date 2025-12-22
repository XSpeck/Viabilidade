"""
Página OS Redes - Acesso Restrito
Salve como: pages/os_redes.py
"""

import streamlit as st
from login_system import require_authentication

# ======================
# Configuração da Página
# ======================
st.set_page_config(
    page_title="OS Redes - Em Desenvolvimento",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Verificar autenticação e carregar menu
if not require_authentication():
    st.stop()

# ======================
# Verificação de Nível de Acesso
# ======================
# Acesso restrito apenas para nível 1 (Admin)
if st.session_state.user_nivel != 1:
    st.error("❌ Acesso negado! Esta página é restrita a usuários de nível 1 (Admin).")
    st.stop()

# ======================
# Conteúdo da Página
# ======================
st.title("📡 OS Redes")
st.markdown("---")

st.info("""
    ## 🚧 Em Desenvolvimento
    
    Esta página está em fase de construção e será liberada em breve.
    
    Aguarde as novidades!
""")

# Exemplo de como manter o layout padrão
st.markdown("---")
st.caption(f"Usuário: {st.session_state.user_name} | Nível: {st.session_state.user_nivel}")

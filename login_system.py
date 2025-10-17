"""
Sistema de Login integrado com Supabase
Salve como: login_system.py
"""

import streamlit as st
import logging
from datetime import datetime
from supabase_config import supabase

logger = logging.getLogger(__name__)

# ======================
# Funções de Autenticação
# ======================

def verify_credentials(login: str, password: str) -> tuple[bool, str, str]:
    """
    Verifica credenciais do usuário no Supabase
    Retorna: (autenticado: bool, nome_usuario: str, login: str)
    """
    try:
        # Buscar usuário pelo login e senha
        response = supabase.table('users').select('*').eq('login', login).eq('senha', password).execute()
        
        if response.data and len(response.data) > 0:
            user = response.data[0]
            logger.info(f"Login bem-sucedido: {login}")
            return True, user['nome'], user['login']
        
        logger.warning(f"Tentativa de login falhou: {login}")
        return False, "", ""
    except Exception as e:
        logger.error(f"Erro ao verificar credenciais: {e}")
        return False, "", ""

def init_login_state():
    """Inicializa estado de sessão do login"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_name' not in st.session_state:
        st.session_state.user_name = ""
    if 'user_login' not in st.session_state:
        st.session_state.user_login = ""
    if 'login_timestamp' not in st.session_state:
        st.session_state.login_timestamp = None

def logout():
    """Faz logout do usuário"""
    st.session_state.authenticated = False
    st.session_state.user_name = ""
    st.session_state.user_login = ""
    st.session_state.login_timestamp = None

# ======================
# Interface de Login
# ======================

def show_login_page():
    """Exibe página de login"""
    st.markdown("""
        <div style='text-align: center; padding: 20px;'>
            <h1>🔐 Validador de Projetos</h1>
            <p style='color: #666;'>Faça login para acessar o sistema</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Centralizar formulário
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        with st.container():
            st.markdown("""
                <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                            padding: 30px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
            """, unsafe_allow_html=True)
            
            with st.form("login_form", clear_on_submit=False):
                st.markdown("<h3 style='color: white; text-align: center;'>Acesso ao Sistema</h3>", 
                           unsafe_allow_html=True)
                
                login = st.text_input(
                    "👤 Login",
                    placeholder="Digite seu login",
                    key="login_input"
                )
                
                password = st.text_input(
                    "🔑 Senha",
                    type="password",
                    placeholder="Digite sua senha",
                    key="password_input"
                )
                
                col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
                with col_btn2:
                    submit = st.form_submit_button(
                        "🚀 Entrar",
                        use_container_width=True,
                        type="primary"
                    )
                
                if submit:
                    if not login or not password:
                        st.error("❌ Preencha todos os campos!")
                    else:
                        with st.spinner("🔄 Verificando credenciais..."):
                            authenticated, user_name, user_login = verify_credentials(login, password)
                            
                            if authenticated:
                                st.session_state.authenticated = True
                                st.session_state.user_name = user_name
                                st.session_state.user_login = user_login
                                st.session_state.login_timestamp = datetime.now()
                                st.success(f"✅ Bem-vindo, {user_name}!")
                                st.rerun()
                            else:
                                st.error("❌ Login ou senha incorretos!")
            
            st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("""
            <div style='text-align: center; padding: 20px; color: #666;'>
                <p>📧 Problemas com acesso? Entre em contato com o administrador</p>
            </div>
        """, unsafe_allow_html=True)

def show_user_info():
    """Exibe informações do usuário logado na sidebar"""
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 👤 Usuário Logado")
        st.info(f"**{st.session_state.user_name}**")
        
        if st.session_state.login_timestamp:
            login_time = st.session_state.login_timestamp.strftime('%H:%M:%S')
            st.caption(f"🕐 Login: {login_time}")
        
        if st.button("🚪 Sair", use_container_width=True, type="secondary"):
            logout()
            st.rerun()

# ======================
# Menu de Navegação
# ======================

def show_navigation_menu():
    """Exibe menu de navegação na sidebar"""
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 📋 Menu de Navegação")
        
        # Página Principal
        if st.button("🏠 Busca", use_container_width=True, key="nav_home"):
            st.switch_page("validator_system.py")
        
        # Página de Resultados (todos)
        if st.button("📊 Meus Resultados", use_container_width=True, key="nav_results"):
            st.switch_page("pages/resultados.py")
        
        # Página de Auditoria (só Leo)
        if st.session_state.user_login.lower() == "leo":
            if st.button("🔍 Auditoria", use_container_width=True, key="nav_audit"):
                st.switch_page("pages/auditoria.py")
        
        # Página de Relatórios (todos)
        if st.button("📁 Relatórios", use_container_width=True, key="nav_reports"):
            st.switch_page("pages/relatorios.py")

# ======================
# Função Principal de Integração
# ======================

def require_authentication():
    """
    Verifica autenticação antes de permitir acesso ao sistema.
    Adicione esta função no início do seu app principal.
    
    Retorna True se autenticado, False caso contrário.
    """
    init_login_state()
    
    if not st.session_state.authenticated:
        show_login_page()
        return False
    
    # Se autenticado, mostra informações do usuário e menu
    show_user_info()
    show_navigation_menu()
    return True

import streamlit as st
import pandas as pd
import gdown
import logging
from datetime import datetime

# ======================
# Configurações de Login
# ======================
LOGIN_FILE_ID = "1rbE1en0BZCiKJU5Cy302bKjwkdVYOvuk"  # ID do arquivo users.csv no Google Drive
LOGIN_CSV_PATH = "users.csv"

logger = logging.getLogger(__name__)

# ======================
# Funções de Autenticação
# ======================

@st.cache_data(ttl=300)  # Cache de 5 minutos
def load_users() -> pd.DataFrame:
    """Carrega usuários do Google Drive"""
    try:
        url = f"https://drive.google.com/uc?id={LOGIN_FILE_ID}"
        gdown.download(url, LOGIN_CSV_PATH, quiet=True, fuzzy=True)
        df = pd.read_csv(LOGIN_CSV_PATH)
        logger.info(f"Carregados {len(df)} usuários")
        return df
    except Exception as e:
        logger.error(f"Erro ao carregar usuários: {e}")
        # Retorna DataFrame vazio com estrutura correta
        return pd.DataFrame(columns=['nome', 'login', 'senha'])

def verify_credentials(login: str, password: str) -> tuple[bool, str]:
    """
    Verifica credenciais do usuário
    Retorna: (autenticado: bool, nome_usuario: str)
    """
    try:
        df_users = load_users()
        
        if df_users.empty:
            return False, ""
        
        # Busca usuário pelo login
        user = df_users[df_users['login'].str.lower() == login.lower()]
        
        if user.empty:
            return False, ""
        
        # Verifica senha (texto simples)
        if user.iloc[0]['senha'] == password:
            return True, user.iloc[0]['nome']
        
        return False, ""
    except Exception as e:
        logger.error(f"Erro ao verificar credenciais: {e}")
        return False, ""

def init_login_state():
    """Inicializa estado de sessão do login"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_name' not in st.session_state:
        st.session_state.user_name = ""
    if 'login_timestamp' not in st.session_state:
        st.session_state.login_timestamp = None

def logout():
    """Faz logout do usuário"""
    st.session_state.authenticated = False
    st.session_state.user_name = ""
    st.session_state.login_timestamp = None
    st.cache_data.clear()

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
                            authenticated, user_name = verify_credentials(login, password)
                            
                            if authenticated:
                                st.session_state.authenticated = True
                                st.session_state.user_name = user_name
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
    
    # Se autenticado, mostra informações do usuário
    show_user_info()
    return True


# ======================
# INSTRUÇÕES DE USO
# ======================
"""
COMO INTEGRAR NO SEU SISTEMA:

1. CRIAR ARQUIVO users.csv NO GOOGLE DRIVE:
   
   Estrutura do CSV (senhas em texto simples):
   nome,login,senha
   Leonardo Silva,leo,123456
   Admin Sistema,admin,admin123
   João Santos,joao,senha123
   Maria Oliveira,maria,maria2024

2. OBTER ID DO ARQUIVO:
   - Faça upload do users.csv no Google Drive
   - Clique com botão direito > Compartilhar > "Qualquer pessoa com o link"
   - Copie o ID do link (parte entre /d/ e /view)
   - Substitua em LOGIN_FILE_ID acima

3. INTEGRAR NO SEU CÓDIGO PRINCIPAL (validator_system.py):
   
   No início do arquivo, após os imports:
   
   from login_system import require_authentication
   
   Logo após st.set_page_config(), adicione:
   
   # Verificar autenticação
   if not require_authentication():
       st.stop()
   
   # Resto do seu código continua aqui...

4. ESTRUTURA FINAL:
   
   validator_system.py (seu arquivo principal)
   login_system.py (este arquivo)
   users.csv (no Google Drive)

5. ADICIONAR NOVOS USUÁRIOS:
   
   - Edite o users.csv no Google Drive
   - Adicione nova linha com: nome,login,senha
   - O cache é atualizado a cada 5 minutos automaticamente
   
   Exemplo:
   Pedro Costa,pedro,pedro2024

6. EXEMPLO DE ARQUIVO users.csv COMPLETO:
   
   nome,login,senha
   Leonardo Silva,leo,123456
   Admin Sistema,admin,admin123
   João Santos,joao,senha123
   Maria Oliveira,maria,maria2024
"""

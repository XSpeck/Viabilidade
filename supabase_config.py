import streamlit as st
from supabase import create_client, Client
import logging

logger = logging.getLogger(__name__)

# ======================
# CONFIGURAÇÕES DO SUPABASE
# ======================
SUPABASE_URL = st.secrets["SUPABASE_URL"] 
SUPABASE_KEY = st.secrets["SUPABASE_KEY"] 

# ======================
# Cliente Supabase
# ======================
@st.cache_resource
def get_supabase_client() -> Client:
    """
    Retorna cliente Supabase (singleton com cache)
    """
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Cliente Supabase inicializado com sucesso")
        return supabase
    except Exception as e:
        logger.error(f"Erro ao inicializar Supabase: {e}")
        st.error(f"❌ Erro ao conectar ao banco de dados: {e}")
        st.stop()

# Instância global
supabase: Client = get_supabase_client()

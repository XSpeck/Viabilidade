import streamlit as st
from supabase import create_client, Client
import logging

logger = logging.getLogger(__name__)

# ======================
# CONFIGURAÇÕES DO SUPABASE
# ======================
SUPABASE_URL = "https://rvyldmtzcneexotozbev.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJ2eWxkbXR6Y25lZXhvdG96YmV2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjA2MTAwODEsImV4cCI6MjA3NjE4NjA4MX0.9WIl6mNUFZwV9kB6sHFjFn2K4Ti6QJCikHSXHjX2rVM"

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

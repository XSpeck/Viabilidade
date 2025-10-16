import streamlit as st
import pandas as pd
import logging
from datetime import datetime
import supabase_config

logger = logging.getLogger(__name__)

# ======================
# Funções de Viabilização (Supabase)
# ======================

def create_viability_request(user_name: str, viability_data: Dict) -> bool:
    """Cria nova solicitação de viabilização"""
    try:
        supabase = supabase_config.supabase
        
        new_request = {
            'usuario': user_name,
            'cto_numero': viability_data.get('cto_numero', ''),
            'distancia_real': viability_data.get('distancia_real', ''),
            'distancia_sobra': viability_data.get('distancia_sobra', ''),
            'localizacao_caixa': viability_data.get('localizacao_caixa', ''),
            'portas_disponiveis': None,
            'menor_rx': None,
            'status': 'pendente',
            'motivo_rejeicao': None,
            'data_solicitacao': datetime.now().isoformat(),
            'data_auditoria': None,
            'data_finalizacao': None,
            'auditado_por': None
        }
        
        supabase.table('viabilizacoes').insert(new_request).execute()
        st.cache_data.clear()
        return True
        
    except Exception as e:
        logger.error(f"Erro ao criar solicitação: {e}")
        return False

@st.cache_data(ttl=30)
def load_viability_data() -> pd.DataFrame:
    """Carrega dados do Supabase"""
    try:
        supabase = supabase_config.supabase
        response = supabase.table('viabilizacoes').select('*').order('data_solicitacao', desc=True).execute()
        
        if response.data:
            return pd.DataFrame(response.data)
        return pd.DataFrame()
            
    except Exception as e:
        logger.error(f"Erro ao carregar viabilizações: {e}")
        return pd.DataFrame()

def update_viability_status(viability_id: str, status: str, **kwargs) -> bool:
    """Atualiza uma viabilização"""
    try:
        supabase = supabase_config.supabase
        
        update_data = {'status': status}
        update_data.update(kwargs)
        
        supabase.table('viabilizacoes').update(update_data).eq('id', viability_id).execute()
        st.cache_data.clear()
        return True
        
    except Exception as e:
        logger.error(f"Erro ao atualizar: {e}")
        return False

# ======================
# ABA 1: AUDITORIA (Leo)
# ======================

def show_audit_tab():
    st.header("Auditoria de Viabilizações")
    
    if st.session_state.user_name.lower() != "leo":
        st.error("Acesso restrito apenas para Leo")
        return
    
    df = load_viability_data()
    
    if df.empty:
        st.info("Sem viabilizações no sistema")
        return
    
    pending = df[df['status'] == 'pendente'].copy()
    
    if pending.empty:
        st.info("Sem solicitações pendentes")
        return
    
    st.metric("Solicitações Pendentes", len(pending))
    st.markdown("---")
    
    for idx, row in pending.iterrows():
        with st.expander(f"Solicitação #{row['id'][:8]} - {row['usuario']}", expanded=True):
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Usuário:** {row['usuario']}")
                st.write(f"**Nº Caixa:** {row['cto_numero']}")
                st.write(f"**Distância Real:** {row['distancia_real']}")
                st.write(f"**Distância c/ Sobra:** {row['distancia_sobra']}")
                st.write(f"**Localização:** {row['localizacao_caixa']}")
            
            with col2:
                portas = st.number_input(
                    "Portas Disponíveis",
                    min_value=0, max_value=50, value=0,
                    key=f"portas_{row['id']}"
                )
                
                menor_rx = st.text_input(
                    "Menor RX (dBm)",
                    placeholder="Ex: -18.67",
                    key=f"rx_{row['id']}"
                )
            
            col_btn1, col_btn2 = st.columns(2)
            
            with col_btn1:
                if st.button("OK - Aprovar", key=f"approve_{row['id']}", type="primary", use_container_width=True):
                    if portas > 0 and menor_rx:
                        if update_viability_status(
                            row['id'],
                            'aprovado',
                            portas_disponiveis=portas,
                            menor_rx=menor_rx,
                            data_auditoria=datetime.now().isoformat(),
                            auditado_por='leo'
                        ):
                            st.success("Aprovado!")
                            st.rerun()
                    else:
                        st.warning("Preencha Portas e RX")
            
            with col_btn2:
                if st.button("Rejeitar", key=f"reject_{row['id']}", type="secondary", use_container_width=True):
                    motivo = st.text_input(
                        "Motivo da rejeição",
                        key=f"motivo_input_{row['id']}"
                    )
                    if motivo:
                        if update_viability_status(
                            row['id'],
                            'sem_viabilidade',
                            motivo_rejeicao=motivo,
                            data_auditoria=datetime.now().isoformat(),
                            auditado_por='leo'
                        ):
                            st.success("Rejeitado!")
                            st.rerun()

# ======================
# ABA 2: RESULTADOS (Usuário)
# ======================

def show_results_tab():
    st.header("Meus Resultados")
    
    df = load_viability_data()
    
    if df.empty:
        st.info("Sem solicitações")
        return
    
    # Dados do usuário que foram aprovados
    user_approved = df[
        (df['usuario'] == st.session_state.user_name) & 
        (df['status'] == 'aprovado')
    ].copy()
    
    # Dados do usuário que foram rejeitados
    user_rejected = df[
        (df['usuario'] == st.session_state.user_name) & 
        (df['status'] == 'sem_viabilidade')
    ].copy()
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Aprovadas", len(user_approved))
    with col2:
        st.metric("Sem Viabilidade", len(user_rejected))
    
    st.markdown("---")
    
    # Viabilidades aprovadas
    if not user_approved.empty:
        st.subheader("Viabilizações Aprovadas")
        
        for idx, row in user_approved.iterrows():
            with st.expander(f"CTO {row['cto_numero']} - {row['data_auditoria'][:10]}"):
                
                dados = f"""Nº Caixa: {row['cto_numero']}
Portas Disponíveis: {row['portas_disponiveis']}
Menor RX: {row['menor_rx']} dBm
Distância até Cliente: {row['distancia_sobra']}
Localização da Caixa: {row['localizacao_caixa']}"""
                
                st.code(dados, language="text")
                
                if st.button("Finalizar", key=f"finish_{row['id']}", type="primary", use_container_width=True):
                    if update_viability_status(row['id'], 'finalizado', data_finalizacao=datetime.now().isoformat()):
                        st.success("Viabilização finalizada!")
                        st.rerun()
    
    # Sem viabilidade
    if not user_rejected.empty:
        st.markdown("---")
        st.subheader("Sem Viabilidade")
        
        for idx, row in user_rejected.iterrows():
            with st.expander(f"CTO {row['cto_numero']} - {row['data_auditoria'][:10]}"):
                st.warning(f"Motivo: {row['motivo_rejeicao']}")

# ======================
# ABA 3: RELATÓRIOS/ARQUIVO
# ======================

def show_reports_tab():
    st.header("Relatórios e Arquivo")
    
    df = load_viability_data()
    
    if df.empty:
        st.info("Sem dados")
        return
    
    # Separar por status
    aprovadas = df[df['status'] == 'finalizado']
    sem_viabilidade = df[df['status'] == 'sem_viabilidade']
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Viabilidades Aprovadas", len(aprovadas))
    with col2:
        st.metric("Sem Viabilidade", len(sem_viabilidade))
    
    st.markdown("---")
    
    tab1, tab2 = st.tabs(["Viabilidades Aprovadas", "Sem Viabilidade"])
    
    with tab1:
        st.subheader("Viabilizações Aprovadas e Finalizadas")
        
        if aprovadas.empty:
            st.info("Sem viabilizações aprovadas")
        else:
            search = st.text_input("Buscar por CTO, Usuário...", key="search_approved")
            
            df_display = aprovadas.copy()
            if search:
                mask = df_display.astype(str).apply(
                    lambda x: x.str.lower().str.contains(search.lower(), na=False)
                ).any(axis=1)
                df_display = df_display[mask]
            
            for idx, row in df_display.iterrows():
                with st.expander(f"CTO {row['cto_numero']} - {row['usuario']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Usuário:** {row['usuario']}")
                        st.write(f"**Nº Caixa:** {row['cto_numero']}")
                        st.write(f"**Localização:** {row['localizacao_caixa']}")
                    with col2:
                        st.write(f"**Portas:** {row['portas_disponiveis']}")
                        st.write(f"**RX:** {row['menor_rx']} dBm")
                        st.write(f"**Distância:** {row['distancia_sobra']}")
    
    with tab2:
        st.subheader("Solicitações Sem Viabilidade")
        
        if sem_viabilidade.empty:
            st.info("Sem rejeições")
        else:
            search = st.text_input("Buscar por CTO, Usuário...", key="search_rejected")
            
            df_display = sem_viabilidade.copy()
            if search:
                mask = df_display.astype(str).apply(
                    lambda x: x.str.lower().str.contains(search.lower(), na=False)
                ).any(axis=1)
                df_display = df_display[mask]
            
            for idx, row in df_display.iterrows():
                with st.expander(f"CTO {row['cto_numero']} - {row['usuario']}"):
                    st.write(f"**Usuário:** {row['usuario']}")
                    st.write(f"**Nº Caixa:** {row['cto_numero']}")
                    st.warning(f"**Motivo:** {row['motivo_rejeicao']}")

# ======================
# FUNÇÃO PRINCIPAL
# ======================

def show_viability_system():
    """Mostra as 3 abas de viabilização"""
    
    st.markdown("---")
    
    if st.session_state.user_name.lower() == "leo":
        tab1, tab2, tab3 = st.tabs(["Auditoria", "Meus Resultados", "Relatórios"])
        
        with tab1:
            show_audit_tab()
        with tab2:
            show_results_tab()
        with tab3:
            show_reports_tab()
    else:
        tab1, tab2 = st.tabs(["Meus Resultados", "Relatórios"])
        
        with tab1:
            show_results_tab()
        with tab2:
            show_reports_tab()

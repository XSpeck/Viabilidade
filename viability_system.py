import streamlit as st
import pandas as pd
import gdown
import logging
from datetime import datetime
from typing import Optional, Dict
import uuid

# ======================
# Configurações de Viabilização
# ======================
VIABILITY_FILE_ID = "18t2nAn-EADPVonV_9EEQCKwa665DA8eJ"  # ID do viabilizacoes.csv
VIABILITY_CSV_PATH = "viabilizacoes.csv"

logger = logging.getLogger(__name__)

# ======================
# Funções de Gerenciamento de Viabilizações
# ======================

def init_viability_csv():
    """Cria estrutura inicial do CSV se não existir"""
    try:
        df = pd.DataFrame(columns=[
            'id', 'usuario', 'plus_code_cliente', 'cto_numero', 'distancia_real', 
            'distancia_sobra', 'localizacao_caixa', 'portas_disponiveis', 'menor_rx',
            'status', 'motivo_rejeicao', 'data_solicitacao', 'data_auditoria', 
            'data_finalizacao', 'auditado_por'
        ])
        df.to_csv(VIABILITY_CSV_PATH, index=False)
        return df
    except Exception as e:
        logger.error(f"Erro ao criar CSV inicial: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=60)  # Cache de 1 minuto para dados dinâmicos
def load_viability_data() -> pd.DataFrame:
    """Carrega dados de viabilização do Google Drive"""
    try:
        url = f"https://drive.google.com/uc?id={VIABILITY_FILE_ID}"
        gdown.download(url, VIABILITY_CSV_PATH, quiet=True, fuzzy=True)
        df = pd.read_csv(VIABILITY_CSV_PATH)
        logger.info(f"Carregadas {len(df)} viabilizações")
        return df
    except Exception as e:
        logger.warning(f"Erro ao carregar viabilizações, criando novo: {e}")
        return init_viability_csv()

def save_viability_data(df: pd.DataFrame):
    """Salva dados localmente (necessário fazer upload manual ao Drive)"""
    try:
        df.to_csv(VIABILITY_CSV_PATH, index=False)
        st.cache_data.clear()
        logger.info("Dados de viabilização salvos")
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar viabilizações: {e}")
        return False

def create_viability_request(user_name: str, viability_data: Dict) -> bool:
    """Cria nova solicitação de viabilização"""
    try:
        df = load_viability_data()
        
        new_request = {
            'id': str(uuid.uuid4())[:8],
            'usuario': user_name,
            'plus_code_cliente': viability_data.get('plus_code', ''),
            'cto_numero': viability_data.get('cto_numero', ''),
            'distancia_real': viability_data.get('distancia_real', ''),
            'distancia_sobra': viability_data.get('distancia_sobra', ''),
            'localizacao_caixa': viability_data.get('localizacao_caixa', ''),
            'portas_disponiveis': '',
            'menor_rx': '',
            'status': 'pendente',
            'motivo_rejeicao': '',
            'data_solicitacao': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'data_auditoria': '',
            'data_finalizacao': '',
            'auditado_por': ''
        }
        
        df = pd.concat([df, pd.DataFrame([new_request])], ignore_index=True)
        save_viability_data(df)
        return True
    except Exception as e:
        logger.error(f"Erro ao criar solicitação: {e}")
        return False

def update_viability_status(viability_id: str, status: str, **kwargs) -> bool:
    """Atualiza status e dados de uma viabilização"""
    try:
        df = load_viability_data()
        idx = df[df['id'] == viability_id].index
        
        if len(idx) == 0:
            return False
        
        df.loc[idx, 'status'] = status
        
        for key, value in kwargs.items():
            if key in df.columns:
                df.loc[idx, key] = value
        
        save_viability_data(df)
        return True
    except Exception as e:
        logger.error(f"Erro ao atualizar viabilização: {e}")
        return False

# ======================
# Interface: Aba de Auditoria (Leo)
# ======================

def show_audit_tab():
    """Aba de auditoria - acesso restrito ao Leo"""
    st.header("🔍 Auditoria de Viabilizações")
    
    # Verificar acesso
    if st.session_state.user_name.lower() != "leo":
        st.error("🚫 Acesso restrito! Apenas o usuário 'Leo' pode acessar esta aba.")
        return
    
    df = load_viability_data()
    pending = df[df['status'] == 'pendente'].copy()
    
    if pending.empty:
        st.info("✅ Não há solicitações pendentes de auditoria.")
        return
    
    st.metric("⏳ Pendentes", len(pending))
    st.markdown("---")
    
    # Listar pendências
    for idx, row in pending.iterrows():
        with st.expander(f"📋 Solicitação #{row['id']} - {row['usuario']} - {row['data_solicitacao']}", expanded=True):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 📍 Informações da Solicitação")
                st.text(f"Usuário: {row['usuario']}")
                st.text(f"Plus Code Cliente: {row['plus_code_cliente']}")
                st.text(f"N° Caixa (CTO): {row['cto_numero']}")
                st.text(f"Distância Real: {row['distancia_real']}")
                st.text(f"Distância c/ Sobra: {row['distancia_sobra']}")
                st.text(f"Localização Caixa: {row['localizacao_caixa']}")
            
            with col2:
                st.markdown("### ✏️ Análise Técnica")
                
                portas = st.number_input(
                    "Portas Disponíveis",
                    min_value=0,
                    max_value=50,
                    value=0,
                    key=f"portas_{row['id']}"
                )
                
                menor_rx = st.text_input(
                    "Menor RX (dBm)",
                    placeholder="Ex: -18.67",
                    key=f"rx_{row['id']}"
                )
                
                motivo = st.text_area(
                    "Motivo da Rejeição (opcional)",
                    placeholder="Preencher apenas se for rejeitar",
                    key=f"motivo_{row['id']}"
                )
            
            col_btn1, col_btn2 = st.columns(2)
            
            with col_btn1:
                if st.button("✅ Aprovar", key=f"approve_{row['id']}", type="primary", use_container_width=True):
                    if portas > 0 and menor_rx:
                        success = update_viability_status(
                            row['id'],
                            'aprovado',
                            portas_disponiveis=portas,
                            menor_rx=menor_rx,
                            data_auditoria=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            auditado_por='leo'
                        )
                        if success:
                            st.success(f"✅ Solicitação #{row['id']} aprovada!")
                            st.rerun()
                        else:
                            st.error("❌ Erro ao aprovar solicitação")
                    else:
                        st.warning("⚠️ Preencha todos os campos técnicos para aprovar")
            
            with col_btn2:
                if st.button("❌ Rejeitar", key=f"reject_{row['id']}", type="secondary", use_container_width=True):
                    if motivo:
                        success = update_viability_status(
                            row['id'],
                            'rejeitado',
                            motivo_rejeicao=motivo,
                            data_auditoria=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            auditado_por='leo'
                        )
                        if success:
                            st.success(f"❌ Solicitação #{row['id']} rejeitada")
                            st.rerun()
                        else:
                            st.error("❌ Erro ao rejeitar solicitação")
                    else:
                        st.warning("⚠️ Informe o motivo da rejeição")
            
            st.markdown("---")

# ======================
# Interface: Aba de Resultados
# ======================

def show_results_tab():
    """Aba de resultados - cada usuário vê apenas seus"""
    st.header("📊 Meus Resultados")
    
    df = load_viability_data()
    user_results = df[
        (df['usuario'] == st.session_state.user_name) & 
        ((df['status'] == 'aprovado') | (df['status'] == 'rejeitado'))
    ].copy()
    
    if user_results.empty:
        st.info("📭 Você não possui resultados no momento.")
        return
    
    # Separar aprovados e rejeitados
    approved = user_results[user_results['status'] == 'aprovado']
    rejected = user_results[user_results['status'] == 'rejeitado']
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("✅ Aprovadas", len(approved))
    with col2:
        st.metric("❌ Rejeitadas", len(rejected))
    
    st.markdown("---")
    
    # Mostrar aprovadas
    if not approved.empty:
        st.subheader("✅ Viabilizações Aprovadas")
        for idx, row in approved.iterrows():
            with st.expander(f"📦 CTO {row['cto_numero']} - {row['data_auditoria']}", expanded=True):
                
                # Dados para copiar
                dados_completos = f"""N°Caixa: {row['cto_numero']}
Portas disponíveis: {row['portas_disponiveis']}
Menor RX: {row['menor_rx']} dBm
Distância até cliente: {row['distancia_sobra']}
Localização da Caixa: {row['localizacao_caixa']}"""
                
                st.code(dados_completos, language="text")
                
                col_btn1, col_btn2 = st.columns(2)
                
                with col_btn1:
                    st.button("📋 Copiar Dados", key=f"copy_{row['id']}", use_container_width=True)
                    st.caption("💡 Use Ctrl+C para copiar o texto acima")
                
                with col_btn2:
                    if st.button("✅ Finalizar", key=f"finish_{row['id']}", type="primary", use_container_width=True):
                        success = update_viability_status(
                            row['id'],
                            'finalizado',
                            data_finalizacao=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        )
                        if success:
                            st.success("✅ Viabilização finalizada!")
                            st.rerun()
    
    # Mostrar rejeitadas
    if not rejected.empty:
        st.markdown("---")
        st.subheader("❌ Solicitações Sem Viabilidade")
        for idx, row in rejected.iterrows():
            with st.expander(f"⚠️ {row['plus_code_cliente']} - {row['data_auditoria']}"):
                st.warning(f"**Motivo:** {row['motivo_rejeicao']}")
                st.text(f"CTO Tentada: {row['cto_numero']}")
                st.text(f"Auditado em: {row['data_auditoria']}")

# ======================
# Interface: Aba de Relatórios
# ======================

def show_reports_tab():
    """Aba de relatórios/arquivo"""
    st.header("📁 Relatórios e Arquivo")
    
    df = load_viability_data()
    
    # Contadores
    finalizadas = df[df['status'] == 'finalizado']
    rejeitadas = df[df['status'] == 'rejeitado']
    pendentes = df[df['status'] == 'pendente']
    aprovadas_aguardando = df[df['status'] == 'aprovado']
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("✅ Aprovadas", len(finalizadas))
    with col2:
        st.metric("❌ Rejeitadas", len(rejeitadas))
    with col3:
        st.metric("⏳ Pendentes", len(pendentes))
    with col4:
        total = len(finalizadas) + len(rejeitadas)
        taxa = (len(finalizadas) / total * 100) if total > 0 else 0
        st.metric("📊 Taxa Aprovação", f"{taxa:.1f}%")
    
    st.markdown("---")
    
    # Abas de arquivo
    tab1, tab2 = st.tabs(["✅ Viabilidades Aprovadas", "❌ Sem Viabilidade"])
    
    with tab1:
        st.subheader("📋 Viabilizações Finalizadas")
        
        if finalizadas.empty:
            st.info("Nenhuma viabilização finalizada ainda.")
        else:
            # Busca
            search_approved = st.text_input("🔍 Buscar", placeholder="Plus Code, CTO, Usuário...", key="search_approved")
            
            df_display = finalizadas.copy()
            if search_approved:
                mask = df_display.astype(str).apply(
                    lambda x: x.str.lower().str.contains(search_approved.lower(), na=False)
                ).any(axis=1)
                df_display = df_display[mask]
            
            # Exibir dados
            for idx, row in df_display.iterrows():
                with st.expander(f"📦 {row['cto_numero']} - {row['usuario']} - {row['data_finalizacao']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.text(f"Usuário: {row['usuario']}")
                        st.text(f"Plus Code: {row['plus_code_cliente']}")
                        st.text(f"N° Caixa: {row['cto_numero']}")
                        st.text(f"Localização: {row['localizacao_caixa']}")
                    with col2:
                        st.text(f"Portas: {row['portas_disponiveis']}")
                        st.text(f"Menor RX: {row['menor_rx']} dBm")
                        st.text(f"Distância: {row['distancia_sobra']}")
                        st.text(f"Finalizado: {row['data_finalizacao']}")
    
    with tab2:
        st.subheader("🚫 Solicitações Rejeitadas")
        
        if rejeitadas.empty:
            st.info("Nenhuma solicitação rejeitada.")
        else:
            # Busca
            search_rejected = st.text_input("🔍 Buscar", placeholder="Plus Code, Usuário...", key="search_rejected")
            
            df_display = rejeitadas.copy()
            if search_rejected:
                mask = df_display.astype(str).apply(
                    lambda x: x.str.lower().str.contains(search_rejected.lower(), na=False)
                ).any(axis=1)
                df_display = df_display[mask]
            
            # Exibir dados
            for idx, row in df_display.iterrows():
                with st.expander(f"❌ {row['plus_code_cliente']} - {row['usuario']} - {row['data_auditoria']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.text(f"Usuário: {row['usuario']}")
                        st.text(f"Plus Code: {row['plus_code_cliente']}")
                        st.text(f"CTO Tentada: {row['cto_numero']}")
                    with col2:
                        st.warning(f"**Motivo:** {row['motivo_rejeicao']}")
                        st.text(f"Rejeitado em: {row['data_auditoria']}")
                        st.text(f"Auditado por: {row['auditado_por']}")

# ======================
# FUNÇÃO PRINCIPAL DE INTEGRAÇÃO
# ======================

def show_viability_system():
    """
    Função principal que adiciona o sistema de abas ao validador.
    Chamar esta função após a página de busca no validator_system.py
    """
    
    st.markdown("---")
    st.markdown("---")
    
    # Criar abas
    if st.session_state.user_name.lower() == "leo":
        tabs = st.tabs(["🔍 Auditoria", "📊 Meus Resultados", "📁 Relatórios"])
        
        with tabs[0]:
            show_audit_tab()
        with tabs[1]:
            show_results_tab()
        with tabs[2]:
            show_reports_tab()
    else:
        tabs = st.tabs(["📊 Meus Resultados", "📁 Relatórios"])
        
        with tabs[0]:
            show_results_tab()
        with tabs[1]:
            show_reports_tab()


# ======================
# INSTRUÇÕES DE INTEGRAÇÃO
# ======================
"""
COMO INTEGRAR NO validator_system.py:

1. CRIAR ARQUIVO viabilizacoes.csv NO GOOGLE DRIVE:
   
   Estrutura inicial (vazio):
   id,usuario,plus_code_cliente,cto_numero,distancia_real,distancia_sobra,localizacao_caixa,portas_disponiveis,menor_rx,status,motivo_rejeicao,data_solicitacao,data_auditoria,data_finalizacao,auditado_por

2. OBTER ID DO ARQUIVO e substituir em VIABILITY_FILE_ID

3. NO validator_system.py, ADICIONAR NO INÍCIO:
   
   from viability_system import show_viability_system, create_viability_request

4. ADICIONAR BOTÃO "VIABILIZAR" NA SEÇÃO DE BUSCA:
   
   (Após exibir as informações da CTO mais próxima, adicionar:)
   
   if st.button("🎯 Viabilizar", type="primary", use_container_width=True):
       viability_data = {
           'plus_code': plus_code_input,
           'cto_numero': closest_cto['name'],
           'distancia_real': format_distance(walking_route_cto['distance']),
           'distancia_sobra': format_distance(walking_route_cto['distance'] + 50),
           'localizacao_caixa': coords_to_pluscode(closest_cto['lat'], closest_cto['lon'])
       }
       
       if create_viability_request(st.session_state.user_name, viability_data):
           st.success("✅ Solicitação de viabilização enviada!")
       else:
           st.error("❌ Erro ao criar solicitação")

5. NO FINAL DO validator_system.py, ANTES DO FOOTER:
   
   # Sistema de Viabilização
   show_viability_system()

PRONTO! O sistema estará integrado mantendo a estrutura original.
"""

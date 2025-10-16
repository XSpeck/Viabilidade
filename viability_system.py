import streamlit as st
import pandas as pd
import logging
from datetime import datetime
from typing import Optional, Dict, List
import uuid
import supabase_config

logger = logging.getLogger(__name__)

# ======================
# Funções de Gerenciamento de Viabilidades (Supabase)
# ======================

def create_viability_request(user_name: str, viability_data: Dict) -> bool:
    """Cria nova solicitação de viabilização no Supabase"""
    try:
        supabase = supabase_config.supabase
        
        new_request = {
            'usuario': user_name,
            'plus_code_cliente': viability_data.get('plus_code', ''),
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
        
        response = supabase.table('viabilizacoes').insert(new_request).execute()
        logger.info(f"Viabilização criada: {response.data[0]['id']}")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao criar solicitação: {e}")
        st.error(f"Erro ao salvar viabilização: {e}")
        return False

@st.cache_data(ttl=60)
def load_viability_data() -> pd.DataFrame:
    """Carrega dados de viabilização do Supabase"""
    try:
        supabase = supabase_config.supabase
        response = supabase.table('viabilizacoes').select('*').order('data_solicitacao', desc=True).execute()
        
        if response.data:
            df = pd.DataFrame(response.data)
            logger.info(f"Carregadas {len(df)} viabilizações")
            return df
        else:
            return pd.DataFrame()
            
    except Exception as e:
        logger.error(f"Erro ao carregar viabilizações: {e}")
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

def update_viability_status(viability_id: str, status: str, **kwargs) -> bool:
    """Atualiza status e dados de uma viabilização"""
    try:
        supabase = supabase_config.supabase
        
        update_data = {'status': status}
        
        # Adicionar timestamps automaticamente
        if status == 'aprovado':
            update_data['data_auditoria'] = datetime.now().isoformat()
        elif status == 'rejeitado':
            update_data['data_auditoria'] = datetime.now().isoformat()
        elif status == 'finalizado':
            update_data['data_finalizacao'] = datetime.now().isoformat()
        
        # Adicionar outros dados
        update_data.update(kwargs)
        
        response = supabase.table('viabilizacoes').update(
            update_data
        ).eq('id', viability_id).execute()
        
        logger.info(f"Viabilização atualizada: {viability_id} -> {status}")
        st.cache_data.clear()
        return True
        
    except Exception as e:
        logger.error(f"Erro ao atualizar viabilização: {e}")
        st.error(f"Erro ao atualizar: {e}")
        return False

# ======================
# Interface: Aba de Auditoria (Leo)
# ======================

def show_audit_tab():
    """Aba de auditoria - acesso restrito ao Leo"""
    st.header("🔍 Auditoria de Viabilizações")
    
    if st.session_state.user_name.lower() != "leo":
        st.error("🚫 Acesso restrito! Apenas o usuário 'Leo' pode acessar esta aba.")
        return
    
    df = load_viability_data()
    
    if df.empty:
        st.info("✅ Não há viabilizações no sistema.")
        return
    
    pending = df[df['status'] == 'pendente'].copy()
    
    if pending.empty:
        st.info("✅ Não há solicitações pendentes de auditoria.")
        return
    
    st.metric("⏳ Pendentes", len(pending))
    st.markdown("---")
    
    for idx, row in pending.iterrows():
        # Formatar data para exibição
        data_sol = row['data_solicitacao'][:10] if isinstance(row['data_solicitacao'], str) else row['data_solicitacao'].strftime('%Y-%m-%d')
        
        with st.expander(
            f"📋 Solicitação #{row['id'][:8]} - {row['usuario']} - {data_sol}", 
            expanded=True
        ):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 📍 Informações da Solicitação")
                st.text(f"Usuário: {row['usuario']}")
                st.text(f"Plus Code Cliente: {row['plus_code_cliente']}")
                st.text(f"Nº Caixa (CTO): {row['cto_numero']}")
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
                            auditado_por='leo'
                        )
                        if success:
                            st.success(f"✅ Solicitação #{row['id'][:8]} aprovada!")
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
                            auditado_por='leo'
                        )
                        if success:
                            st.success(f"❌ Solicitação #{row['id'][:8]} rejeitada")
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
    
    if df.empty:
        st.info("Nenhuma solicitação no momento.")
        return
    
    user_results = df[
        (df['usuario'] == st.session_state.user_name) & 
        ((df['status'] == 'aprovado') | (df['status'] == 'rejeitado'))
    ].copy()
    
    if user_results.empty:
        st.info("🔭 Você não possui resultados no momento.")
        return
    
    approved = user_results[user_results['status'] == 'aprovado']
    rejected = user_results[user_results['status'] == 'rejeitado']
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("✅ Aprovadas", len(approved))
    with col2:
        st.metric("❌ Rejeitadas", len(rejected))
    
    st.markdown("---")
    
    if not approved.empty:
        st.subheader("✅ Viabilizações Aprovadas")
        for idx, row in approved.iterrows():
            data_aud = row['data_auditoria'][:10] if isinstance(row['data_auditoria'], str) else row['data_auditoria'].strftime('%Y-%m-%d') if row['data_auditoria'] else 'N/A'
            
            with st.expander(f"📦 CTO {row['cto_numero']} - {data_aud}", expanded=True):
                
                dados_completos = f"""Nº Caixa: {row['cto_numero']}
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
                            'finalizado'
                        )
                        if success:
                            st.success("✅ Viabilização finalizada!")
                            st.rerun()
    
    if not rejected.empty:
        st.markdown("---")
        st.subheader("❌ Solicitações Sem Viabilidade")
        for idx, row in rejected.iterrows():
            data_aud = row['data_auditoria'][:10] if isinstance(row['data_auditoria'], str) else row['data_auditoria'].strftime('%Y-%m-%d') if row['data_auditoria'] else 'N/A'
            
            with st.expander(f"⚠️ {row['plus_code_cliente']} - {data_aud}"):
                st.warning(f"**Motivo:** {row['motivo_rejeicao']}")
                st.text(f"CTO Tentada: {row['cto_numero']}")
                st.text(f"Auditado em: {data_aud}")

# ======================
# Interface: Aba de Relatórios
# ======================

def show_reports_tab():
    """Aba de relatórios/arquivo"""
    st.header("📈 Relatórios e Arquivo")
    
    df = load_viability_data()
    
    if df.empty:
        st.info("Nenhum dado disponível.")
        return
    
    finalizadas = df[df['status'] == 'finalizado']
    rejeitadas = df[df['status'] == 'rejeitado']
    pendentes = df[df['status'] == 'pendente']
    
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
    
    tab1, tab2 = st.tabs(["✅ Viabilidades Aprovadas", "❌ Sem Viabilidade"])
    
    with tab1:
        st.subheader("📋 Viabilizações Finalizadas")
        
        if finalizadas.empty:
            st.info("Nenhuma viabilização finalizada ainda.")
        else:
            search_approved = st.text_input(
                "🔍 Buscar", 
                placeholder="Plus Code, CTO, Usuário...", 
                key="search_approved"
            )
            
            df_display = finalizadas.copy()
            if search_approved:
                mask = df_display.astype(str).apply(
                    lambda x: x.str.lower().str.contains(search_approved.lower(), na=False)
                ).any(axis=1)
                df_display = df_display[mask]
            
            for idx, row in df_display.iterrows():
                data_fin = row['data_finalizacao'][:10] if isinstance(row['data_finalizacao'], str) else row['data_finalizacao'].strftime('%Y-%m-%d') if row['data_finalizacao'] else 'N/A'
                
                with st.expander(f"📦 {row['cto_numero']} - {row['usuario']} - {data_fin}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.text(f"Usuário: {row['usuario']}")
                        st.text(f"Plus Code: {row['plus_code_cliente']}")
                        st.text(f"Nº Caixa: {row['cto_numero']}")
                        st.text(f"Localização: {row['localizacao_caixa']}")
                    with col2:
                        st.text(f"Portas: {row['portas_disponiveis']}")
                        st.text(f"Menor RX: {row['menor_rx']} dBm")
                        st.text(f"Distância: {row['distancia_sobra']}")
                        st.text(f"Finalizado: {data_fin}")
    
    with tab2:
        st.subheader("🚫 Solicitações Rejeitadas")
        
        if rejeitadas.empty:
            st.info("Nenhuma solicitação rejeitada.")
        else:
            search_rejected = st.text_input(
                "🔍 Buscar", 
                placeholder="Plus Code, Usuário...", 
                key="search_rejected"
            )
            
            df_display = rejeitadas.copy()
            if search_rejected:
                mask = df_display.astype(str).apply(
                    lambda x: x.str.lower().str.contains(search_rejected.lower(), na=False)
                ).any(axis=1)
                df_display = df_display[mask]
            
            for idx, row in df_display.iterrows():
                data_aud = row['data_auditoria'][:10] if isinstance(row['data_auditoria'], str) else row['data_auditoria'].strftime('%Y-%m-%d') if row['data_auditoria'] else 'N/A'
                
                with st.expander(f"❌ {row['plus_code_cliente']} - {row['usuario']} - {data_aud}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.text(f"Usuário: {row['usuario']}")
                        st.text(f"Plus Code: {row['plus_code_cliente']}")
                        st.text(f"CTO Tentada: {row['cto_numero']}")
                    with col2:
                        st.warning(f"**Motivo:** {row['motivo_rejeicao']}")
                        st.text(f"Rejeitado em: {data_aud}")
                        st.text(f"Auditado por: {row['auditado_por']}")

# ======================
# Função Principal
# ======================

def show_viability_system():
    """
    Função principal que adiciona o sistema de abas ao validador.
    """
    
    st.markdown("---")
    st.markdown("---")
    
    if st.session_state.user_name.lower() == "leo":
        tabs = st.tabs(["🔍 Auditoria", "📊 Meus Resultados", "📈 Relatórios"])
        
        with tabs[0]:
            show_audit_tab()
        with tabs[1]:
            show_results_tab()
        with tabs[2]:
            show_reports_tab()
    else:
        tabs = st.tabs(["📊 Meus Resultados", "📈 Relatórios"])
        
        with tabs[0]:
            show_results_tab()
        with tabs[1]:
            show_reports_tab()

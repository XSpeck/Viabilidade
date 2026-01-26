"""
Página de Resultados - Cada usuário vê apenas seus resultados
Salve como: pages/resultados.py
"""

import streamlit as st
from login_system import require_authentication
from streamlit_autorefresh import st_autorefresh
from viability_functions import get_user_results, finalize_viability, finalize_viability_approved, format_datetime_resultados, format_time_br_supa
import logging
import pandas as pd
from datetime import datetime, timedelta
from supabase_config import supabase
import re

logger = logging.getLogger(__name__)

# ======================
# Configuração da Página
# ======================
st.set_page_config(
    page_title="Meus Resultados - Validador de Projetos",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ======================
# Atualização automática
# ======================
st_autorefresh(interval=20000, key="resultados_refresh")  # 20000 ms = 20 segundos

# Verificar autenticação
if not require_authentication():
    st.stop()

# ======================
# Header
# ======================
st.title("📊 Meus Resultados")

st.markdown(f"Viabilizações de **{st.session_state.user_name}**")

# Botão de atualizar
col_header1, col_header2 = st.columns([4, 1])
with col_header2:
    if st.button("🔄 Atualizar", width='stretch'):
        st.rerun()

# ======================
# Buscar Resultados
# ======================
results = get_user_results(st.session_state.user_name)

st.markdown("---")
st.subheader("🔍 Filtros")

col_filtro1, col_filtro2, col_filtro3 = st.columns(3)

with col_filtro1:
    filtro_tipo = st.selectbox(
        "Tipo de Instalação",
        options=["Todos", "FTTH", "Prédio"],
        key="filtro_tipo"
    )

with col_filtro2:
    filtro_status = st.selectbox(
        "Status",
        options=["Todos", "Em Análise", "Aprovado", "Rejeitado", "UTP", "Prédio Pendente"],
        key="filtro_status"
    )

with col_filtro3:
    busca_texto = st.text_input(
        "🔎 Buscar",
        placeholder="Cliente, Plus Code, Prédio...",
        key="busca_geral"
    )

# ========== APLICAR FILTROS ==========
results_filtrados = results.copy()

# Filtro por tipo
if filtro_tipo != "Todos":
    results_filtrados = [r for r in results_filtrados if r['tipo_instalacao'] == filtro_tipo]

# Filtro por status
if filtro_status == "Em Análise":
    results_filtrados = [
        r for r in results_filtrados
        if r['status'] in ['pendente', 'em_auditoria']
    ]
elif filtro_status == "Aprovado":
    results_filtrados = [r for r in results_filtrados if r['status'] == 'aprovado']
elif filtro_status == "Rejeitado":
    results_filtrados = [r for r in results_filtrados if r['status'] == 'rejeitado']
elif filtro_status == "UTP":
    results_filtrados = [r for r in results_filtrados if r['status'] == 'utp']
elif filtro_status == "Prédio Pendente":
    results_filtrados = [r for r in results_filtrados if r.get('status_predio') in ['aguardando_dados', 'pronto_auditoria', 'agendado']]

# Busca por texto (cliente, plus code, prédio)
if busca_texto:
    busca_lower = busca_texto.lower()
    results_filtrados = [
        r for r in results_filtrados 
        if busca_lower in r.get('nome_cliente', '').lower() 
        or busca_lower in r['plus_code_cliente'].lower()
        or busca_lower in r.get('predio_ftta', '').lower()
    ]

# Mostrar contador
st.info(f"📊 Mostrando **{len(results_filtrados)}** de **{len(results)}** solicitações")
# ========== FIM DOS FILTROS ==========

# ======================
# Notificação de novos resultados
# ======================
if "resultados_anteriores" not in st.session_state:
    st.session_state.resultados_anteriores = len(results)

# Se há novos resultados desde a última atualização
if len(results) > st.session_state.resultados_anteriores:
    novos = len(results) - st.session_state.resultados_anteriores
    st.toast(f"🎉 {novos} novo(s) resultado(s) disponível(is)!", icon="✅")
    st.markdown("""
    <audio autoplay>
        <source src="https://actions.google.com/sounds/v1/cartoon/wood_plank_flicks.ogg" type="audio/ogg">
    </audio>
    """, unsafe_allow_html=True)

# Atualiza contador
st.session_state.resultados_anteriores = len(results)

if not results:
    st.info("📭 Você não possui resultados no momento.")
    st.markdown("""
    ### Como funciona?
    1. Faça uma busca na **página principal**
    2. Clique em **"Viabilizar"**
    3. Aguarde a **auditoria técnica**
    4. Seus resultados aparecerão aqui!
    """)
    st.stop()

# Separar aprovados e rejeitados
approved = [r for r in results_filtrados if r['status'] == 'aprovado']
rejected = [r for r in results_filtrados if r['status'] == 'rejeitado']
utp = [r for r in results_filtrados if r['status'] == 'utp']
structured = [r for r in results_filtrados if r.get('status_predio') == 'estruturado']
building_pending = [r for r in results_filtrados if r.get('status_predio') in ['aguardando_dados', 'pronto_auditoria', 'agendado']]

# Pendentes: incluir tanto 'pendente' quanto 'em_auditoria'
pending_analysis = [r for r in results_filtrados 
                   if r['status'] in ['pendente', 'em_auditoria'] 
                   and not r.get('status_predio')]

st.markdown("---")
# ======================
# Separar pendentes por status
# ======================
# Na fila (ninguém pegou ainda)
na_fila = [r for r in pending_analysis 
           if r['status'] == 'pendente' and not r.get('auditor_responsavel')]

# Em auditoria (alguém pegou)
em_auditoria = [r for r in pending_analysis 
                if r['status'] == 'em_auditoria' or r.get('auditor_responsavel')]

# ======================
# Mostrar Em Auditoria (alguém já pegou)
# ======================
if em_auditoria:
    st.subheader("🔍 Em Análise Técnica")
    
    for row in em_auditoria:
        auditor = row.get('auditor_responsavel', 'Auditor')
        
        tipo_icon = "🏠" if row['tipo_instalacao'] == 'FTTH' else "🏢"
        
        if row['tipo_instalacao'] == 'FTTH':
            tipo_nome = "Casa (FTTH)"
        elif row['tipo_instalacao'] == 'Prédio':
            if row.get('tecnologia_predio'):
                tipo_nome = f"Prédio ({row['tecnologia_predio']})"
            else:
                tipo_nome = "Prédio"
        else:
            tipo_nome = row['tipo_instalacao']
        
        urgente_badge = " 🔥 **URGENTE**" if row.get('urgente', False) else ""        
        
        with st.expander(f"🔍 {tipo_icon} {row['plus_code_cliente']} - {tipo_nome}{urgente_badge}"):
            
            col_pend1, col_pend2 = st.columns(2)
            
            with col_pend1:
                st.markdown("### 📋 Informações")
                if row.get('nome_cliente'):
                    st.text(f"🙋 Cliente: {row['nome_cliente']}")
                st.text(f"📍 Plus Code: {row['plus_code_cliente']}")
                st.text(f"🏷️ Tipo: {tipo_nome}")
                if row.get('predio_ftta'):
                    st.text(f"🏢 Edifício: {row['predio_ftta']}")
                st.text(f"📅 Solicitado: {format_time_br_supa(row['data_solicitacao'])}")
                
                if row.get('urgente', False):
                    st.error("🔥 **Solicitação Urgente - Cliente Presencial**")
            
            with col_pend2:
                st.markdown("### ⏱️ Status")
                st.success(f"👤 **{auditor} está verificando sua solicitação**")
                st.info("🔍 Análise técnica em andamento")
                st.caption("💡 Você será notificado assim que a análise for concluída")
    
    st.markdown("---")

# ======================
# Mostrar Na Fila (ninguém pegou ainda)
# ======================
if na_fila:
    st.subheader("📋 Aguardando Análise")
    st.info(f"📬 {len(na_fila)} solicitação(ões) na fila aguardando verificação")
    
    for row in na_fila:
        tipo_icon = "🏠" if row['tipo_instalacao'] == 'FTTH' else "🏢"
        
        if row['tipo_instalacao'] == 'FTTH':
            tipo_nome = "Casa (FTTH)"
        elif row['tipo_instalacao'] == 'Prédio':
            if row.get('tecnologia_predio'):
                tipo_nome = f"Prédio ({row['tecnologia_predio']})"
            else:
                tipo_nome = "Prédio"
        else:
            tipo_nome = row['tipo_instalacao']
        
        urgente_badge = " 🔥 **URGENTE**" if row.get('urgente', False) else ""        
        
        with st.expander(f"📋 {tipo_icon} {row['plus_code_cliente']} - {tipo_nome}{urgente_badge}"):
            
            col_pend1, col_pend2 = st.columns(2)
            
            with col_pend1:
                st.markdown("### 📋 Informações")
                if row.get('nome_cliente'):
                    st.text(f"🙋 Cliente: {row['nome_cliente']}")
                st.text(f"📍 Plus Code: {row['plus_code_cliente']}")
                st.text(f"🏷️ Tipo: {tipo_nome}")
                if row.get('predio_ftta'):
                    st.text(f"🏢 Edifício: {row['predio_ftta']}")
                st.text(f"📅 Solicitado: {format_time_br_supa(row['data_solicitacao'])}")
                
                if row.get('urgente', False):
                    st.error("🔥 **Solicitação Urgente - Cliente Presencial**")
            
            with col_pend2:
                st.markdown("### ⏱️ Status")
                st.warning("📋 **Na fila para análise**")
                st.info("⏳ Aguardando um técnico pegar sua solicitação")
                st.caption("💡 Você será notificado quando iniciar a análise")
    
    st.markdown("---")


# ======================
# Mostrar Aprovadas
# ======================
if approved:
    st.subheader("✅ Viabilizações Aprovadas")
    st.success("🎉 Parabéns! Suas solicitações foram aprovadas!")
    
    for row in approved:
        with st.expander(f"📦 {row['plus_code_cliente']} - Auditado em {format_datetime_resultados(row['data_auditoria'])}", expanded=True):
            
            # Verificar tipo
            if row['tipo_instalacao'] == 'FTTH':
                st.markdown("### 🏠 FTTH (Casa)")
                if row.get('nome_cliente'):
                    st.info(f"🙋 **Cliente:** {row['nome_cliente']}")
                
                # Dados para copiar
                dados_completos = f"""N°Caixa: {row['cto_numero']}
Portas disponíveis: {row['portas_disponiveis']}
Menor RX: {row['menor_rx']} dBm
Distância até cliente: {row['distancia_cliente']}
Localização da Caixa: {row['localizacao_caixa']}"""
                
                if row.get('observacoes'):
                    dados_completos += f"\nObs: {row['observacoes']}"
                
            else:  # FTTA
                st.markdown("### 🏢 FTTA (Edifício)")
                if row.get('nome_cliente'):
                    st.info(f"🙋 **Cliente:** {row['nome_cliente']}")
                
                # Dados para copiar
                dados_completos = f"""
Prédio FTTA: {row['predio_ftta']}
CDOI: {row['cdoi']}
Portas disponíveis: {row['portas_disponiveis']}
Média RX: {row['media_rx']} dBm"""
                
                if row.get('observacoes'):
                    dados_completos += f"\nObs: {row['observacoes']}"
            
            # Exibir dados
            st.code(dados_completos, language="text")
            
            col_btn1, col_btn2, col_btn3 = st.columns([2, 2, 1])
            
            with col_btn1:
                st.caption("📋 **Dica:** selecione o texto acima e use **Ctrl+C** para copiar.")
            
            with col_btn3:
                if st.button("✅ Finalizar", key=f"finish_{row['id']}", type="primary", width='stretch'):
                    if finalize_viability_approved(row['id']):
                        st.success("✅ Viabilização finalizada e arquivada!")
                        
                        st.rerun()
            
            st.caption(f"🕐 Auditado por: {row['auditado_por']} em {format_datetime_resultados(row['data_auditoria'])}")

# ======================
# Mostrar Estruturados
# ======================
if structured:
    st.markdown("---")
    st.subheader("✅ Prédio Estruturado")
    st.success("🎉 Parabéns! A estrutura foi instalada no prédio!")
    
    for row in structured:
        with st.expander(f"🏢 {row.get('predio_ftta', 'Prédio')} - Estruturado", expanded=True):
            
            st.markdown("### 🏗️ Estrutura Instalada")
            
            col_struct1, col_struct2 = st.columns(2)
            
            with col_struct1:
                st.markdown("#### 📋 Informações")
                st.text(f"🏢 Edifício: {row.get('predio_ftta', 'N/A')}")
                if row.get('andar_predio'):
                    st.text(f"🏗️ Andar: {row['andar_predio']}")
                if row.get('bloco_predio'):
                    st.text(f"🏢 Bloco: {row['bloco_predio']}")
                st.text(f"📍 Localização: {row['plus_code_cliente']}")
                st.text(f"🔧 Tecnologia: {row.get('tecnologia_predio', 'N/A')}")
            
            with col_struct2:
                st.markdown("#### 👷 Execução")
                st.text(f"👤 Técnico: {row.get('tecnico_responsavel', 'N/A')}")
                data_visita = row.get('data_visita', 'N/A')
                if data_visita and data_visita != 'N/A':
                    try:
                        data_obj = datetime.strptime(data_visita, '%Y-%m-%d')
                        data_visita = data_obj.strftime('%d/%m/%Y')
                    except:
                        pass
                st.text(f"📅 Data Visita: {data_visita}")
                st.text(f"🕐 Período: {row.get('periodo_visita', 'N/A')}")
            
            st.markdown("---")
            
            # Dados para copiar
            dados_estruturados = f"""Condomínio: {row.get('predio_ftta', 'N/A')}
Tecnologia: {row.get('tecnologia_predio', 'N/A')}
Localização: {row['plus_code_cliente']}
Técnico: {row.get('tecnico_responsavel', 'N/A')}
Data Estruturação: {format_datetime_resultados(row.get('data_finalizacao', ''))}"""
            
            st.code(dados_estruturados, language="text")
            
            col_btn1, col_btn2 = st.columns([3, 1])
            
            with col_btn1:
                st.markdown("💡 **Dica:** Estrutura concluída! Clique em Finalizar para arquivar.")
            
            with col_btn2:
                if st.button("✅ Finalizar", key=f"finish_struct_{row['id']}", type="primary", width='stretch'):
                    if finalize_viability_approved(row['id']):
                        st.success("✅ Estruturação arquivada!")
                        st.balloons()
                        st.rerun()            

# ======================
# Mostrar Rejeitadas
# ======================
if rejected:
    st.markdown("---")
    st.subheader("❌ Solicitações Sem Viabilidade")
    
    for row in rejected:
        tipo_icon = "🏠" if row['tipo_instalacao'] == 'FTTH' else "🏢"
        with st.expander(f"⚠️ {tipo_icon} {row['plus_code_cliente']} - {format_datetime_resultados(row['data_auditoria'])}"):
            # Verificar se é rejeição de prédio
            if row.get('status_predio') == 'rejeitado':
                st.error("### 🏢 Edifício Sem Viabilidade")
                st.markdown(f"**Edifício:** {row.get('predio_ftta', 'N/A')}")
                st.markdown(f"**Localização:** {row['plus_code_cliente']}")
                
                if row.get('motivo_rejeicao'):
                    st.markdown("**Motivo:**")
                    st.warning(row['motivo_rejeicao'].replace('Edifício sem viabilidade: ', ''))
            else:
                # Mensagem padrão
                st.error("### 📝 Não temos projeto neste ponto")
            
                # Motivo
                if row.get('motivo_rejeicao'):
                    st.markdown(f"**Motivo:** {row['motivo_rejeicao']}")
            
            # Informações adicionais
            st.text(f"Tipo: {row['tipo_instalacao']}")
            st.text(f"Plus Code: {row['plus_code_cliente']}")
            st.caption(f"🕐 Analisado por: {row['auditado_por']} em {format_datetime_resultados(row['data_auditoria'])}")

            st.markdown("---")
            if st.button("✅ OK, Entendi", key=f"finish_rejected_{row['id']}", type="secondary", width='stretch'):
                if finalize_viability(row['id']):
                    st.success("✅ Confirmado!")
                    st.rerun()
                    
# ======================
# Mostrar UTP
# ======================
if utp:
    st.markdown("---")
    st.subheader("📡 Atendemos UTP")
    
    for row in utp:
        with st.expander(f"📡 {row['plus_code_cliente']} - {format_datetime_resultados(row['data_auditoria'])}"):
            
            # Mensagem padrão
            st.info("### 📡 Atendemos UTP")
            
            # Informações adicionais            
            st.text(f"Plus Code: {row['plus_code_cliente']}")
            st.caption(f"🕐 Analisado por: {row['auditado_por']} em {format_datetime_resultados(row['data_auditoria'])}")
            
            # Botão finalizar (não arquiva, apenas remove da lista)
            if st.button("✅ Finalizar", key=f"finish_utp_{row['id']}", type="primary", width='stretch'):
                if finalize_viability(row['id']):
                    st.success("✅ Finalizado!")
                    st.rerun()
                    
# ======================
# Mostrar Viabilizações de Prédio Pendentes
# ======================
if building_pending:
    st.markdown("---")
    st.subheader("🏢 Viabilização de Prédio")
    st.warning("⚠️ Temos projeto na rua, mas precisamos viabilizar a estrutura no prédio.")    
    
    for row in building_pending:
        status_atual = row.get('status_predio')
        
        # Título diferente baseado no status
        if status_atual == 'agendado':
            titulo = f"📅 {row.get('predio_ftta', 'Prédio')} - Viabilidade Agendada"
            expandido = False
        elif status_atual == 'pronto_auditoria':
            titulo = f"⏳ {row.get('predio_ftta', 'Prédio')} - Aguardando Agendamento"
            expandido = False  # Não expandir automaticamente
        else:
            titulo = f"🏗️ {row.get('predio_ftta', 'Prédio')} - {row['plus_code_cliente']}"
            expandido = True  # Expandir para preencher
        
        with st.expander(titulo, expanded=expandido):
            # Se está agendado, mostrar informações e botão para consultar agenda
            if status_atual == 'agendado':
                st.success("✅ **Visita Técnica Agendada!**")
                
                col_agend1, col_agend2 = st.columns(2)
                
                with col_agend1:
                    st.markdown("### 📅 Dados do Agendamento")
                    st.text(f"🏢 Edifício: {row.get('predio_ftta', 'N/A')}")
                    st.text(f"📍 Localização: {row['plus_code_cliente']}")
                    data_visita = row.get('data_visita', 'N/A')
                    if data_visita and data_visita != 'N/A':
                        try:
                            data_obj = datetime.strptime(data_visita, '%Y-%m-%d')
                            data_visita = data_obj.strftime('%d/%m/%Y')
                        except:
                            pass
                    st.text(f"📅 Data: {data_visita}")
                    st.text(f"🕐 Período: {row.get('periodo_visita', 'N/A')}")
                
                with col_agend2:
                    st.markdown("### 👷 Informações Técnicas")
                    st.text(f"👤 Técnico: {row.get('tecnico_responsavel', 'N/A')}")
                    st.text(f"🔧 Tecnologia: {row.get('tecnologia_predio', 'N/A')}")
                    st.text(f"📆 Agendado em: {format_time_br_supa(row.get('data_agendamento', ''))}")                
                    
            # Se já foi enviado, mostrar mensagem de aguardando
            elif status_atual == 'pronto_auditoria':
                st.success("✅ **Dados enviados com sucesso!**")
                st.info("⏳ **Aguardando agendamento da visita técnica**")
                
                st.markdown("---")
                st.markdown("### 📋 Dados Enviados")
                
                col_enviado1, col_enviado2 = st.columns(2)
                with col_enviado1:                    
                    st.text(f"🏢 Edifício: {row.get('predio_ftta', 'N/A')}")
                    if row.get('andar_predio'):
                        st.text(f"🏗️ Andar: {row['andar_predio']}")
                    if row.get('bloco_predio'):
                        st.text(f"🏢 Bloco: {row['bloco_predio']}")
                    st.text(f"📍 Plus Code: {row['plus_code_cliente']}")
                    st.text(f"👤 Síndico: {row.get('nome_sindico', 'N/A')}")
                    st.text(f"📞 Contato: {row.get('contato_sindico', 'N/A')}")
                
                with col_enviado2:
                    st.text(f"🏠 Cliente: {row.get('nome_cliente_predio', 'N/A')}")
                    st.text(f"📞 Contato: {row.get('contato_cliente_predio', 'N/A')}")
                    st.text(f"🚪 Apartamento: {row.get('apartamento', 'N/A')}")
                
                if row.get('obs_agendamento'):
                    st.markdown("**📝 Horários sugeridos:**")
                    st.info(row['obs_agendamento'])
                
                st.caption("💡 Você será notificado quando a visita for agendada")
                
            else:
                # Formulário para preencher (código que já existe)
                st.markdown("### 📋 Informações da Solicitação Original")
                col_info1, col_info2 = st.columns(2)
                with col_info1:
                    st.text(f"Nome do Edifício: {row.get('predio_ftta', 'N/A')}")
                    st.text(f"Plus Code: {row['plus_code_cliente']}")
                with col_info2:
                    st.text(f"Tipo: {row['tipo_instalacao']}")
                    st.text(f"Solicitado em: {format_time_br_supa(row['data_solicitacao'])}")
                
                st.markdown("---")
                st.markdown("### 🔧 Preencha os Dados para Viabilização")
                
                with st.form(key=f"form_building_{row['id']}"):
                    
                    col_form1, col_form2 = st.columns(2)
                    
                    with col_form1:
                        st.markdown("#### 👤 Dados do Síndico")
                        nome_sindico = st.text_input(
                            "Nome do Síndico *",
                            placeholder="Nome completo",
                            key=f"sindico_nome_{row['id']}"
                        )
                        contato_sindico = st.text_input(
                            "Contato do Síndico *",
                            placeholder="(48) 99999-9999",
                            key=f"sindico_contato_{row['id']}"
                        )
                    
                    with col_form2:
                        st.markdown("#### 🏠 Dados do Cliente")
                        nome_cliente = st.text_input(
                            "Nome do Cliente *",
                            placeholder="Nome completo",
                            key=f"cliente_nome_{row['id']}"
                        )
                        contato_cliente = st.text_input(
                            "Contato do Cliente *",
                            placeholder="(48) 99999-9999",
                            key=f"cliente_contato_{row['id']}"
                        )
                        apartamento = st.text_input(
                            "Apartamento *",
                            placeholder="Ex: 301, Bloco A",
                            key=f"apartamento_{row['id']}"
                        )
                    
                    st.markdown("#### 📝 Observações")
                    obs_agendamento = st.text_area(
                        "Melhores datas e horários para visita técnica",
                        placeholder="Ex: Segunda ou Quarta, manhã (9h-12h)",
                        height=100,
                        key=f"obs_agend_{row['id']}"
                    )
                    
                    st.markdown("---")
                    col_submit = st.columns([1, 2, 1])[1]
                    with col_submit:
                        submit_building = st.form_submit_button(
                            "📤 Enviar para verificação Técnica",
                            type="primary",
                            width='stretch'
                        )
                    
                    if submit_building:
                        # Validar campos obrigatórios
                        if not all([nome_sindico, contato_sindico, nome_cliente, contato_cliente, apartamento]):
                            st.error("❌ Preencha todos os campos obrigatórios (*)")
                        else:
                            from viability_functions import submit_building_data
                            
                            dados = {
                                'nome_sindico': nome_sindico.strip(),
                                'contato_sindico': contato_sindico.strip(),
                                'nome_cliente_predio': nome_cliente.strip(),
                                'contato_cliente_predio': contato_cliente.strip(),
                                'apartamento': apartamento.strip(),
                                'obs_agendamento': obs_agendamento.strip()
                            }
                            
                            if submit_building_data(row['id'], dados):
                                st.success("✅ Dados enviados com sucesso!")
                                st.balloons()
                                st.rerun()
                            else:
                                st.error("❌ Erro ao enviar dados. Tente novamente.")  
# ======================
# TABELA DE HISTÓRICO COMPLETO
# ======================
st.markdown("---")
st.subheader("📋 Histórico Completo de Viabilizações")

# ========== LINHA 1: FILTROS DE DATA ==========
col_data1, col_data2 = st.columns(2)

with col_data1:
    data_inicio_hist = st.date_input(
        "📅 Data Início",
        value=datetime.now().date() - timedelta(days=30),
        key="data_inicio_historico",
        format="DD/MM/YYYY",
        help="Padrão: Últimos 30 dias"
    )

with col_data2:
    data_fim_hist = st.date_input(
        "📅 Data Fim",
        value=datetime.now().date(),
        key="data_fim_historico",
        format="DD/MM/YYYY",
        help="Padrão: hoje"
    )

# ========== LINHA 2: FILTROS AVANÇADOS ==========
col_filtro1, col_filtro2, col_filtro3 = st.columns(3)

with col_filtro1:
    filtro_tipo_hist = st.selectbox(
        "🏷️ Tipo de Instalação",
        options=["Todos", "FTTH", "Prédio"],
        key="filtro_tipo_hist"
    )

with col_filtro2:
    filtro_status_hist = st.selectbox(
        "📊 Status",
        options=[
            "Todos",
            "Pendente",
            "Em Auditoria", 
            "Aprovado",
            "Rejeitado",
            "Finalizado",
            "UTP"
        ],
        key="filtro_status_hist"
    )

with col_filtro3:
    ordenar_por = st.selectbox(
        "🔄 Ordenar por",
        options=[
            "Data (Mais recente)",
            "Data (Mais antiga)",
            "Status (A-Z)",
            "Tipo (A-Z)"
        ],
        key="ordenar_hist"
    )

# ========== LINHA 3: BUSCA ==========
busca_historico = st.text_input(
    "🔍 Buscar no Histórico",
    placeholder="Cliente, Plus Code, CTO, Prédio, Auditor...",
    key="busca_historico"
)

# Mostrar período selecionado
if data_inicio_hist and data_fim_hist:
    st.caption(f"📊 Exibindo de {data_inicio_hist.strftime('%d/%m/%Y')} até {data_fim_hist.strftime('%d/%m/%Y')}")

st.markdown("---")

# ========== BUSCAR E PROCESSAR DADOS ==========
try:
    response_historico = supabase.table('viabilizacoes')\
        .select('*')\
        .eq('usuario', st.session_state.user_name)\
        .order('data_solicitacao', desc=True)\
        .execute()
    
    historico_completo = response_historico.data if response_historico.data else []
    
    if historico_completo:
        # Converter para DataFrame
        df_historico = pd.DataFrame(historico_completo)
        
        # ========== APLICAR FILTRO DE DATA ==========
        df_historico['data_filtro'] = df_historico.apply(
            lambda row: row.get('data_auditoria') if row.get('data_auditoria') 
            else row.get('data_solicitacao'), 
            axis=1
        )
        
        df_historico['data_filtro'] = pd.to_datetime(df_historico['data_filtro'], errors='coerce')
        
        if data_inicio_hist:
            df_historico = df_historico[
                df_historico['data_filtro'].dt.date >= data_inicio_hist
            ]
        
        if data_fim_hist:
            df_historico = df_historico[
                df_historico['data_filtro'].dt.date <= data_fim_hist
            ]
        
        # ========== APLICAR FILTRO DE TIPO ==========
        if filtro_tipo_hist != "Todos":
            df_historico = df_historico[df_historico['tipo_instalacao'] == filtro_tipo_hist]
        
        # ========== APLICAR FILTRO DE STATUS ==========
        if filtro_status_hist != "Todos":
            status_map = {
                "Pendente": "pendente",
                "Em Auditoria": "em_auditoria",
                "Aprovado": "aprovado",
                "Rejeitado": "rejeitado",
                "Finalizado": "finalizado",
                "UTP": "utp"
            }
            status_filtro = status_map.get(filtro_status_hist)
            if status_filtro:
                df_historico = df_historico[df_historico['status'] == status_filtro]
        
        # ========== APLICAR BUSCA POR TEXTO ==========
        if busca_historico:
            termo_busca = re.escape(busca_historico.lower().replace("+", "").strip())
            mask = df_historico.astype(str).apply(
                lambda x: x.str.lower().str.replace("+", "", regex=False).str.contains(termo_busca, regex=True, na=False)                
            ).any(axis=1)
            df_historico = df_historico[mask]
        
        # ========== APLICAR ORDENAÇÃO ==========
        if ordenar_por == "Data (Mais recente)":
            df_historico = df_historico.sort_values('data_filtro', ascending=False)
        elif ordenar_por == "Data (Mais antiga)":
            df_historico = df_historico.sort_values('data_filtro', ascending=True)
        elif ordenar_por == "Status (A-Z)":
            df_historico = df_historico.sort_values('status', ascending=True)
        elif ordenar_por == "Tipo (A-Z)":
            df_historico = df_historico.sort_values('tipo_instalacao', ascending=True)
        
        # Remover coluna auxiliar
        if 'data_filtro' in df_historico.columns:
            df_historico = df_historico.drop(columns=['data_filtro'])
        
        # ========== PREPARAR TABELA PARA EXIBIÇÃO ==========
        colunas_exibir = [
            'data_solicitacao', 'tipo_instalacao', 'plus_code_cliente',
            'nome_cliente', 'status', 'cto_numero', 'predio_ftta',
            'distancia_cliente', 'menor_rx', 'localizacao_caixa', 'portas_disponiveis',
            'auditado_por'
        ]
        
        colunas_disponiveis = [col for col in colunas_exibir if col in df_historico.columns]
        df_display = df_historico[colunas_disponiveis].copy()
        
        # Renomear colunas
        rename_dict = {
            'data_solicitacao': 'Data Solicitação',
            'tipo_instalacao': 'Tipo',
            'plus_code_cliente': 'Plus Code',
            'nome_cliente': 'Cliente',
            'status': 'Status',
            'cto_numero': 'CTO',
            'predio_ftta': 'Prédio',
            'distancia_cliente': 'Distância',
            'menor_rx': 'Menor RX',
            'localizacao_caixa': 'Localização Caixa',
            'portas_disponiveis': 'Portas',
            'auditado_por': 'Auditor'
        }
        df_display.rename(columns=rename_dict, inplace=True)
        
        # ========== FORMATAR DADOS ==========
        # Formatar data
        if 'Data Solicitação' in df_display.columns:
            df_display['Data Solicitação'] = df_display['Data Solicitação'].apply(
                lambda x: format_datetime_resultados(x) if x else '-'
            )
        
        # Formatar Status (com ícones)
        if 'Status' in df_display.columns:
            status_icons = {
                'pendente': '⏳ Pendente',
                'em_auditoria': '🔍 Em Auditoria',
                'aprovado': '✅ Aprovado',
                'rejeitado': '❌ Rejeitado',
                'finalizado': '📦 Finalizado',
                'utp': '📡 UTP'
            }
            df_display['Status'] = df_display['Status'].map(status_icons).fillna(df_display['Status'])
        
        # Formatar Tipo (com ícones)
        if 'Tipo' in df_display.columns:
            tipo_icons = {
                'FTTH': '🏠 FTTH',
                'Prédio': '🏢 Prédio'
            }
            df_display['Tipo'] = df_display['Tipo'].map(tipo_icons).fillna(df_display['Tipo'])
        
        # Formatar RX
        if 'Menor RX' in df_display.columns:
            df_display['Menor RX'] = df_display['Menor RX'].apply(
                lambda x: f"{x} dBm" if pd.notna(x) and str(x).strip() != '' else '-'
            )
        
        # Garantir que outras colunas sejam strings
        for col in ['Localização Caixa', 'Portas', 'Distância', 'CTO', 'Prédio', 'Auditor']:
            if col in df_display.columns:
                df_display[col] = df_display[col].fillna('-').astype(str)
        
        # ========== MÉTRICAS RÁPIDAS ==========
        col_metric1, col_metric2, col_metric3, col_metric4 = st.columns(4)
        
        with col_metric1:
            st.metric("📊 Total Filtrado", len(df_display))
        
        with col_metric2:
            aprovados = len(df_display[df_display['Status'].str.contains('Aprovado|Finalizado', na=False)])
            st.metric("✅ Aprovados", aprovados)
        
        with col_metric3:
            rejeitados = len(df_display[df_display['Status'].str.contains('Rejeitado', na=False)])
            st.metric("❌ Rejeitados", rejeitados)
        
        with col_metric4:
            pendentes = len(df_display[df_display['Status'].str.contains('Pendente|Auditoria', na=False)])
            st.metric("⏳ Em Andamento", pendentes)
        
        st.markdown("---")
        
        # ========== EXIBIR TABELA ==========
        st.dataframe(
            df_display,
            use_container_width=True,
            height=400
        )
        
        st.caption(f"📊 Mostrando {len(df_display)} de {len(historico_completo)} registros totais")
        
        # ========== BOTÃO DE DOWNLOAD ==========
        csv_export = df_display.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Baixar Histórico (CSV)",
            data=csv_export,
            file_name=f"historico_viabilizacoes_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True
        )
        
    else:
        st.info("📭 Nenhuma viabilização no histórico")
        
except Exception as e:
    st.error(f"❌ Erro ao carregar histórico: {e}")
    logger.error(f"Erro histórico: {e}")

    
# ======================
# Footer
# ======================
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <p>📊 <strong>Validador de Projetos</strong> | Desenvolvido ByLeo</p>
</div>
""", unsafe_allow_html=True)

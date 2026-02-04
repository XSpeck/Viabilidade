"""
Pagina de Resultados - Cada usuario ve apenas seus resultados
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
# Configuracao da Pagina
# ======================
st.set_page_config(
    page_title="Meus Resultados - Validador de Projetos",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ======================
# Atualizacao automatica
# ======================
st_autorefresh(interval=20000, key="resultados_refresh")  # 20000 ms = 20 segundos

# Verificar autenticacao
if not require_authentication():
    st.stop()

# ======================
# Header
# ======================
st.title("📊 Meus Resultados")

st.markdown(f"Viabilizacoes de **{st.session_state.user_name}**")

# Botao de atualizar
col_header1, col_header2 = st.columns([4, 1])
with col_header2:
    if st.button("🔄 Atualizar", key="btn_atualizar_top"):
        st.rerun()

# ======================
# Buscar Resultados
# ======================
results = get_user_results(st.session_state.user_name)

# ======================
# Notificacao de novos resultados
# ======================
if "resultados_anteriores" not in st.session_state:
    st.session_state.resultados_anteriores = len(results)

# Se ha novos resultados desde a ultima atualizacao
if len(results) > st.session_state.resultados_anteriores:
    novos = len(results) - st.session_state.resultados_anteriores
    st.toast(f"🎉 {novos} novo(s) resultado(s) disponivel(is)!", icon="✅")
    st.markdown("""
    <audio autoplay>
        <source src="https://actions.google.com/sounds/v1/cartoon/wood_plank_flicks.ogg" type="audio/ogg">
    </audio>
    """, unsafe_allow_html=True)

# Atualiza contador
st.session_state.resultados_anteriores = len(results)

# ======================
# Separar por categoria
# ======================
approved = [r for r in results if r['status'] == 'aprovado']
rejected = [r for r in results if r['status'] == 'rejeitado']
utp = [r for r in results if r['status'] == 'utp']
structured = [r for r in results if r.get('status_predio') == 'estruturado']
building_pending = [r for r in results if r.get('status_predio') in ['aguardando_dados', 'pronto_auditoria', 'agendado']]

# Pendentes: incluir tanto 'pendente' quanto 'em_auditoria'
pending_analysis = [r for r in results
                   if r['status'] in ['pendente', 'em_auditoria']
                   and not r.get('status_predio')]

# Separar pendentes por status
na_fila = [r for r in pending_analysis
           if r['status'] == 'pendente' and not r.get('auditor_responsavel')]

em_auditoria = [r for r in pending_analysis
                if r['status'] == 'em_auditoria' or r.get('auditor_responsavel')]

# ======================
# Contadores para as abas
# ======================
count_analise = len(em_auditoria) + len(na_fila)
count_aprovadas = len(approved) + len(structured)
count_rejeitadas = len(rejected)
count_utp = len(utp)
count_predio = len(building_pending)

# ======================
# ABAS PRINCIPAIS
# ======================
st.markdown("---")

tab_analise, tab_aprovadas, tab_rejeitadas, tab_utp, tab_predio = st.tabs([
    f"🔍 Em Analise ({count_analise})",
    f"✅ Aprovadas ({count_aprovadas})",
    f"❌ Sem Viabilidade ({count_rejeitadas})",
    f"📡 UTP ({count_utp})",
    f"🏢 Prédio/Cond. ({count_predio})"
])

# ======================
# ABA 1: EM ANALISE TECNICA
# ======================
with tab_analise:
    if not em_auditoria and not na_fila:
        st.info("📭 Voce nao possui solicitacoes em analise no momento.")

    # Mostrar Em Auditoria (alguem ja pegou)
    if em_auditoria:
        st.subheader("🔍 Em Analise Tecnica")

        for row in em_auditoria:
            auditor = row.get('auditor_responsavel', 'Auditor')

            if row['tipo_instalacao'] == 'FTTH':
                tipo_icon = "🏠"
                tipo_nome = "Casa (FTTH)"
            elif row['tipo_instalacao'] in ['Prédio', 'Predio']:
                tipo_icon = "🏢"
                if row.get('tecnologia_predio'):
                    tipo_nome = f"Prédio ({row['tecnologia_predio']})"
                else:
                    tipo_nome = "Prédio"
            elif row['tipo_instalacao'] == 'Condomínio':
                tipo_icon = "🏘️"
                if row.get('tecnologia_predio'):
                    tipo_nome = f"Condomínio ({row['tecnologia_predio']})"
                else:
                    tipo_nome = "Condomínio"
            else:
                tipo_icon = "📋"
                tipo_nome = row['tipo_instalacao']

            urgente_badge = " 🔥 **URGENTE**" if row.get('urgente', False) else ""

            with st.expander(f"🔍 {tipo_icon} {row['plus_code_cliente']} - {tipo_nome}{urgente_badge}"):

                col_pend1, col_pend2 = st.columns(2)

                with col_pend1:
                    st.markdown("### 📋 Informacoes")
                    if row.get('nome_cliente'):
                        st.text(f"🙋 Cliente: {row['nome_cliente']}")
                    st.text(f"📍 Plus Code: {row['plus_code_cliente']}")
                    st.text(f"🏷️ Tipo: {tipo_nome}")
                    if row.get('predio_ftta'):
                        st.text(f"🏢 Edificio: {row['predio_ftta']}")
                    st.text(f"📅 Solicitado: {format_time_br_supa(row['data_solicitacao'])}")

                    if row.get('urgente', False):
                        st.error("🔥 **Solicitacao Urgente - Cliente Presencial**")

                with col_pend2:
                    st.markdown("### ⏱️ Status")
                    st.success(f"👤 **{auditor} esta verificando sua solicitacao**")
                    st.info("🔍 Analise tecnica em andamento")
                    st.caption("💡 Voce sera notificado assim que a analise for concluida")

        st.markdown("---")

    # Mostrar Na Fila (ninguem pegou ainda)
    if na_fila:
        st.subheader("📋 Aguardando Analise")
        st.info(f"📬 {len(na_fila)} solicitacao(oes) na fila aguardando verificacao")

        for row in na_fila:
            if row['tipo_instalacao'] == 'FTTH':
                tipo_icon = "🏠"
                tipo_nome = "Casa (FTTH)"
            elif row['tipo_instalacao'] in ['Prédio', 'Predio']:
                tipo_icon = "🏢"
                if row.get('tecnologia_predio'):
                    tipo_nome = f"Prédio ({row['tecnologia_predio']})"
                else:
                    tipo_nome = "Prédio"
            elif row['tipo_instalacao'] == 'Condomínio':
                tipo_icon = "🏘️"
                if row.get('tecnologia_predio'):
                    tipo_nome = f"Condomínio ({row['tecnologia_predio']})"
                else:
                    tipo_nome = "Condomínio"
            else:
                tipo_icon = "📋"
                tipo_nome = row['tipo_instalacao']

            urgente_badge = " 🔥 **URGENTE**" if row.get('urgente', False) else ""

            with st.expander(f"📋 {tipo_icon} {row['plus_code_cliente']} - {tipo_nome}{urgente_badge}"):

                col_pend1, col_pend2 = st.columns(2)

                with col_pend1:
                    st.markdown("### 📋 Informacoes")
                    if row.get('nome_cliente'):
                        st.text(f"🙋 Cliente: {row['nome_cliente']}")
                    st.text(f"📍 Plus Code: {row['plus_code_cliente']}")
                    st.text(f"🏷️ Tipo: {tipo_nome}")
                    if row.get('predio_ftta'):
                        st.text(f"🏢 Edificio: {row['predio_ftta']}")
                    st.text(f"📅 Solicitado: {format_time_br_supa(row['data_solicitacao'])}")

                    if row.get('urgente', False):
                        st.error("🔥 **Solicitacao Urgente - Cliente Presencial**")

                with col_pend2:
                    st.markdown("### ⏱️ Status")
                    st.warning("📋 **Na fila para analise**")
                    st.info("⏳ Aguardando um tecnico pegar sua solicitacao")
                    st.caption("💡 Voce sera notificado quando iniciar a analise")

        st.markdown("---")

    # ======================
    # TABELA DE HISTORICO COMPLETO (dentro da aba Em Analise)
    # ======================
    st.subheader("📋 Historico Completo de Viabilizacoes")

    # ========== LINHA 1: FILTROS DE DATA ==========
    col_data1, col_data2 = st.columns(2)

    with col_data1:
        data_inicio_hist = st.date_input(
            "📅 Data Inicio",
            value=datetime.now().date() - timedelta(days=30),
            key="data_inicio_historico",
            format="DD/MM/YYYY",
            help="Padrao: Ultimos 30 dias"
        )

    with col_data2:
        data_fim_hist = st.date_input(
            "📅 Data Fim",
            value=datetime.now().date(),
            key="data_fim_historico",
            format="DD/MM/YYYY",
            help="Padrao: hoje"
        )

    # ========== LINHA 2: FILTROS AVANCADOS ==========
    col_filtro1, col_filtro2, col_filtro3 = st.columns(3)

    with col_filtro1:
        filtro_tipo_hist = st.selectbox(
            "🏷️ Tipo de Instalacao",
            options=["Todos", "FTTH", "Prédio", "Condomínio"],
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
        "🔍 Buscar no Historico",
        placeholder="Cliente, Plus Code, CTO, Predio, Auditor...",
        key="busca_historico"
    )

    # Mostrar periodo selecionado
    if data_inicio_hist and data_fim_hist:
        st.caption(f"📊 Exibindo de {data_inicio_hist.strftime('%d/%m/%Y')} ate {data_fim_hist.strftime('%d/%m/%Y')}")

    st.markdown("---")

    # ========== BUSCAR E PROCESSAR DADOS ==========
    try:
        response_historico = supabase.table('viabilizacoes')\
            .select('*')\
            .ilike('usuario', st.session_state.user_name)\
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
                if filtro_tipo_hist == "Prédio":
                    df_historico = df_historico[df_historico['tipo_instalacao'].isin(['Prédio', 'Predio'])]
                else:
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

            # ========== APLICAR ORDENACAO ==========
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

            # ========== PREPARAR TABELA PARA EXIBICAO ==========
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
                'data_solicitacao': 'Data Solicitacao',
                'tipo_instalacao': 'Tipo',
                'plus_code_cliente': 'Plus Code',
                'nome_cliente': 'Cliente',
                'status': 'Status',
                'cto_numero': 'CTO',
                'predio_ftta': 'Predio',
                'distancia_cliente': 'Distancia',
                'menor_rx': 'Menor RX',
                'localizacao_caixa': 'Localizacao Caixa',
                'portas_disponiveis': 'Portas',
                'auditado_por': 'Auditor'
            }
            df_display.rename(columns=rename_dict, inplace=True)

            # ========== FORMATAR DADOS ==========
            # Formatar data
            if 'Data Solicitacao' in df_display.columns:
                df_display['Data Solicitacao'] = df_display['Data Solicitacao'].apply(
                    lambda x: format_datetime_resultados(x) if x else '-'
                )

            # Formatar Status (com icones)
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

            # Formatar Tipo (com icones)
            if 'Tipo' in df_display.columns:
                tipo_icons = {
                    'FTTH': '🏠 FTTH',
                    'Predio': '🏢 Prédio',
                    'Prédio': '🏢 Prédio',
                    'Condomínio': '🏘️ Condomínio'
                }
                df_display['Tipo'] = df_display['Tipo'].map(tipo_icons).fillna(df_display['Tipo'])

            # Formatar RX
            if 'Menor RX' in df_display.columns:
                df_display['Menor RX'] = df_display['Menor RX'].apply(
                    lambda x: f"{x} dBm" if pd.notna(x) and str(x).strip() != '' else '-'
                )

            # Garantir que outras colunas sejam strings
            for col in ['Localizacao Caixa', 'Portas', 'Distancia', 'CTO', 'Predio', 'Auditor']:
                if col in df_display.columns:
                    df_display[col] = df_display[col].fillna('-').astype(str)

            # ========== METRICAS RAPIDAS ==========
            col_metric1, col_metric2, col_metric3, col_metric4 = st.columns(4)

            with col_metric1:
                st.metric("📊 Total Filtrado", len(df_display))

            with col_metric2:
                aprovados_hist = len(df_display[df_display['Status'].str.contains('Aprovado|Finalizado', na=False)])
                st.metric("✅ Aprovados", aprovados_hist)

            with col_metric3:
                rejeitados_hist = len(df_display[df_display['Status'].str.contains('Rejeitado', na=False)])
                st.metric("❌ Rejeitados", rejeitados_hist)

            with col_metric4:
                pendentes_hist = len(df_display[df_display['Status'].str.contains('Pendente|Auditoria', na=False)])
                st.metric("⏳ Em Andamento", pendentes_hist)

            st.markdown("---")

            # ========== EXIBIR TABELA ==========
            st.dataframe(
                df_display,
                use_container_width=True,
                height=400
            )

            st.caption(f"📊 Mostrando {len(df_display)} de {len(historico_completo)} registros totais")

            # ========== BOTAO DE DOWNLOAD ==========
            csv_export = df_display.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Baixar Historico (CSV)",
                data=csv_export,
                file_name=f"historico_viabilizacoes_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                use_container_width=True
            )

        else:
            st.info("📭 Nenhuma viabilizacao no historico")

    except Exception as e:
        st.error(f"❌ Erro ao carregar historico: {e}")
        logger.error(f"Erro historico: {e}")


# ======================
# ABA 2: VIABILIZACOES APROVADAS
# ======================
with tab_aprovadas:
    if not approved and not structured:
        st.info("📭 Voce nao possui viabilizacoes aprovadas no momento.")

    # Mostrar Aprovadas
    if approved:
        st.subheader("✅ Viabilizacoes Aprovadas")
        st.success("🎉 Parabens! Suas solicitacoes foram aprovadas!")

        for row in approved:
            with st.expander(f"📦 {row['plus_code_cliente']} - Auditado em {format_datetime_resultados(row['data_auditoria'])}", expanded=True):

                # Verificar tipo
                if row['tipo_instalacao'] == 'FTTH':
                    st.markdown("### 🏠 FTTH (Casa)")
                    if row.get('nome_cliente'):
                        st.info(f"🙋 **Cliente:** {row['nome_cliente']}")

                    # Dados para copiar
                    dados_completos = f"""N Caixa: {row['cto_numero']}
Portas disponiveis: {row['portas_disponiveis']}
Menor RX: {row['menor_rx']} dBm
Distancia ate cliente: {row['distancia_cliente']}
Localizacao da Caixa: {row['localizacao_caixa']}"""

                    if row.get('observacoes'):
                        dados_completos += f"\nObs: {row['observacoes']}"

                else:  # FTTA
                    st.markdown("### 🏢 FTTA (Edificio)")
                    if row.get('nome_cliente'):
                        st.info(f"🙋 **Cliente:** {row['nome_cliente']}")

                    # Dados para copiar
                    dados_completos = f"""
Predio FTTA: {row['predio_ftta']}
CDOI: {row['cdoi']}
Portas disponiveis: {row['portas_disponiveis']}
Media RX: {row['media_rx']} dBm"""

                    if row.get('observacoes'):
                        dados_completos += f"\nObs: {row['observacoes']}"

                # Exibir dados
                st.code(dados_completos, language="text")

                col_btn1, col_btn2, col_btn3 = st.columns([2, 2, 1])

                with col_btn1:
                    st.caption("📋 **Dica:** selecione o texto acima e use **Ctrl+C** para copiar.")

                with col_btn3:
                    if st.button("✅ Finalizar", key=f"finish_{row['id']}", type="primary"):
                        if finalize_viability_approved(row['id']):
                            st.success("✅ Viabilizacao finalizada e arquivada!")
                            st.rerun()

                st.caption(f"🕐 Auditado por: {row['auditado_por']} em {format_datetime_resultados(row['data_auditoria'])}")

    # Mostrar Estruturados
    if structured:
        if approved:
            st.markdown("---")
        st.subheader("✅ Predio Estruturado")
        st.success("🎉 Parabens! A estrutura foi instalada no predio!")

        for row in structured:
            with st.expander(f"🏢 {row.get('predio_ftta', 'Predio')} - Estruturado", expanded=True):

                st.markdown("### 🏗️ Estrutura Instalada")

                col_struct1, col_struct2 = st.columns(2)

                with col_struct1:
                    st.markdown("#### 📋 Informacoes")
                    st.text(f"🏢 Edificio: {row.get('predio_ftta', 'N/A')}")
                    if row.get('andar_predio'):
                        st.text(f"🏠 Casa/Apto: {row['andar_predio']}")
                    if row.get('bloco_predio'):
                        st.text(f"🏢 Bloco: {row['bloco_predio']}")
                    st.text(f"📍 Localizacao: {row['plus_code_cliente']}")
                    st.text(f"🔧 Tecnologia: {row.get('tecnologia_predio', 'N/A')}")

                with col_struct2:
                    st.markdown("#### 👷 Execucao")
                    st.text(f"👤 Tecnico: {row.get('tecnico_responsavel', 'N/A')}")
                    data_visita = row.get('data_visita', 'N/A')
                    if data_visita and data_visita != 'N/A':
                        try:
                            data_obj = datetime.strptime(data_visita, '%Y-%m-%d')
                            data_visita = data_obj.strftime('%d/%m/%Y')
                        except ValueError:
                            pass
                    st.text(f"📅 Data Visita: {data_visita}")
                    st.text(f"🕐 Periodo: {row.get('periodo_visita', 'N/A')}")

                st.markdown("---")

                # Dados para copiar
                dados_estruturados = f"""Condominio: {row.get('predio_ftta', 'N/A')}
Tecnologia: {row.get('tecnologia_predio', 'N/A')}
Localizacao: {row['plus_code_cliente']}
Tecnico: {row.get('tecnico_responsavel', 'N/A')}
Data Estruturacao: {format_datetime_resultados(row.get('data_finalizacao', ''))}"""

                st.code(dados_estruturados, language="text")

                col_btn1, col_btn2 = st.columns([3, 1])

                with col_btn1:
                    st.markdown("💡 **Dica:** Estrutura concluida! Clique em Finalizar para arquivar.")

                with col_btn2:
                    if st.button("✅ Finalizar", key=f"finish_struct_{row['id']}", type="primary"):
                        if finalize_viability_approved(row['id']):
                            st.success("✅ Estruturacao arquivada!")
                            st.rerun()


# ======================
# ABA 3: SOLICITACOES SEM VIABILIDADE
# ======================
with tab_rejeitadas:
    if not rejected:
        st.info("📭 Voce nao possui solicitacoes rejeitadas.")
    else:
        st.subheader("❌ Solicitacoes Sem Viabilidade")

        for row in rejected:
            tipo_icon = "🏠" if row['tipo_instalacao'] == 'FTTH' else "🏢"
            with st.expander(f"⚠️ {tipo_icon} {row['plus_code_cliente']} - {format_datetime_resultados(row['data_auditoria'])}"):
                # Verificar se e rejeicao de predio
                if row.get('status_predio') == 'rejeitado':
                    st.error("### 🏢 Edificio Sem Viabilidade")
                    st.markdown(f"**Edificio:** {row.get('predio_ftta', 'N/A')}")
                    st.markdown(f"**Localizacao:** {row['plus_code_cliente']}")

                    if row.get('motivo_rejeicao'):
                        st.markdown("**Motivo:**")
                        st.warning(row['motivo_rejeicao'].replace('Edificio sem viabilidade: ', ''))
                else:
                    # FTTH sem viabilidade
                    st.error("### 🏠 Sem Viabilidade Neste Ponto")

                    if row.get('nome_cliente'):
                        st.markdown(f"**Cliente:** {row['nome_cliente']}")
                    st.markdown(f"**Localizacao:** {row['plus_code_cliente']}")

                    # Justificativa do auditor
                    if row.get('motivo_rejeicao'):
                        st.markdown("**Justificativa:**")
                        st.warning(row['motivo_rejeicao'])
                    else:
                        st.info("Nao temos projeto neste ponto.")

                # Informacoes adicionais
                st.text(f"Tipo: {row['tipo_instalacao']}")
                st.text(f"Plus Code: {row['plus_code_cliente']}")
                st.caption(f"🕐 Analisado por: {row['auditado_por']} em {format_datetime_resultados(row['data_auditoria'])}")

                st.markdown("---")
                if st.button("✅ OK, Entendi", key=f"finish_rejected_{row['id']}", type="secondary"):
                    if finalize_viability(row['id']):
                        st.success("✅ Confirmado!")
                        st.rerun()


# ======================
# ABA 4: ATENDEMOS UTP
# ======================
with tab_utp:
    if not utp:
        st.info("📭 Voce nao possui solicitacoes marcadas como UTP.")
    else:
        st.subheader("📡 Atendemos UTP")
        st.info("Estas solicitacoes estao em areas onde atendemos via UTP (cabo de rede).")

        for row in utp:
            with st.expander(f"📡 {row['plus_code_cliente']} - {format_datetime_resultados(row['data_auditoria'])}"):

                # Mensagem padrao
                st.info("### 📡 Atendemos UTP")

                # Informacoes adicionais
                st.text(f"Plus Code: {row['plus_code_cliente']}")
                st.caption(f"🕐 Analisado por: {row['auditado_por']} em {format_datetime_resultados(row['data_auditoria'])}")

                # Botao finalizar (nao arquiva, apenas remove da lista)
                if st.button("✅ Finalizar", key=f"finish_utp_{row['id']}", type="primary"):
                    if finalize_viability(row['id']):
                        st.success("✅ Finalizado!")
                        st.rerun()


# ======================
# ABA 5: VIABILIZACAO DE PREDIO
# ======================
with tab_predio:
    if not building_pending:
        st.info("📭 Voce nao possui viabilizacoes de prédio/condomínio pendentes.")
    else:
        st.subheader("🏢 Viabilizacao de Prédio/Condomínio")
        st.warning("⚠️ Temos projeto na rua, mas precisamos viabilizar a estrutura no prédio/condomínio.")

        for row in building_pending:
            status_atual = row.get('status_predio')

            # Titulo diferente baseado no status
            if status_atual == 'agendado':
                titulo = f"📅 {row.get('predio_ftta', 'Predio')} - Viabilidade Agendada"
                expandido = False
            elif status_atual == 'pronto_auditoria':
                titulo = f"⏳ {row.get('predio_ftta', 'Predio')} - Aguardando Agendamento"
                expandido = False  # Nao expandir automaticamente
            else:
                titulo = f"🏗️ {row.get('predio_ftta', 'Predio')} - {row['plus_code_cliente']}"
                expandido = True  # Expandir para preencher

            with st.expander(titulo, expanded=expandido):
                # Se esta agendado, mostrar informacoes e botao para consultar agenda
                if status_atual == 'agendado':
                    st.success("✅ **Visita Tecnica Agendada!**")

                    col_agend1, col_agend2 = st.columns(2)

                    with col_agend1:
                        st.markdown("### 📅 Dados do Agendamento")
                        st.text(f"🏢 Edificio: {row.get('predio_ftta', 'N/A')}")
                        st.text(f"📍 Localizacao: {row['plus_code_cliente']}")
                        data_visita = row.get('data_visita', 'N/A')
                        if data_visita and data_visita != 'N/A':
                            try:
                                data_obj = datetime.strptime(data_visita, '%Y-%m-%d')
                                data_visita = data_obj.strftime('%d/%m/%Y')
                            except ValueError:
                                pass
                        st.text(f"📅 Data: {data_visita}")
                        st.text(f"🕐 Periodo: {row.get('periodo_visita', 'N/A')}")

                    with col_agend2:
                        st.markdown("### 👷 Informacoes Tecnicas")
                        st.text(f"👤 Tecnico: {row.get('tecnico_responsavel', 'N/A')}")
                        st.text(f"🔧 Tecnologia: {row.get('tecnologia_predio', 'N/A')}")
                        st.text(f"📆 Agendado em: {format_time_br_supa(row.get('data_agendamento', ''))}")

                # Se ja foi enviado, mostrar mensagem de aguardando
                elif status_atual == 'pronto_auditoria':
                    st.success("✅ **Dados enviados com sucesso!**")
                    st.info("⏳ **Aguardando agendamento da visita tecnica**")

                    st.markdown("---")
                    st.markdown("### 📋 Dados Enviados")

                    col_enviado1, col_enviado2 = st.columns(2)
                    with col_enviado1:
                        st.text(f"🏢 Edificio: {row.get('predio_ftta', 'N/A')}")
                        if row.get('andar_predio'):
                            st.text(f"🏠 Casa/Apto: {row['andar_predio']}")
                        if row.get('bloco_predio'):
                            st.text(f"🏢 Bloco: {row['bloco_predio']}")
                        st.text(f"📍 Plus Code: {row['plus_code_cliente']}")
                        st.text(f"👤 Sindico: {row.get('nome_sindico', 'N/A')}")
                        st.text(f"📞 Contato: {row.get('contato_sindico', 'N/A')}")

                    with col_enviado2:
                        st.text(f"🏠 Cliente: {row.get('nome_cliente_predio', 'N/A')}")
                        st.text(f"📞 Contato: {row.get('contato_cliente_predio', 'N/A')}")
                        st.text(f"🚪 Apartamento: {row.get('apartamento', 'N/A')}")

                    if row.get('obs_agendamento'):
                        st.markdown("**📝 Horarios sugeridos:**")
                        st.info(row['obs_agendamento'])

                    st.caption("💡 Voce sera notificado quando a visita for agendada")

                else:
                    # Formulario para preencher (codigo que ja existe)
                    st.markdown("### 📋 Informacoes da Solicitacao Original")
                    col_info1, col_info2 = st.columns(2)
                    with col_info1:
                        st.text(f"Nome do Edificio: {row.get('predio_ftta', 'N/A')}")
                        st.text(f"Plus Code: {row['plus_code_cliente']}")
                    with col_info2:
                        st.text(f"Tipo: {row['tipo_instalacao']}")
                        st.text(f"Solicitado em: {format_time_br_supa(row['data_solicitacao'])}")

                    st.markdown("---")
                    st.markdown("### 🔧 Preencha os Dados para Viabilizacao")

                    with st.form(key=f"form_building_{row['id']}"):

                        col_form1, col_form2 = st.columns(2)

                        with col_form1:
                            st.markdown("#### 👤 Dados do Sindico")
                            nome_sindico = st.text_input(
                                "Nome do Sindico *",
                                placeholder="Nome completo",
                                key=f"sindico_nome_{row['id']}"
                            )
                            contato_sindico = st.text_input(
                                "Contato do Sindico *",
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

                        st.markdown("#### 📝 Observacoes")
                        obs_agendamento = st.text_area(
                            "Melhores datas e horarios para visita tecnica",
                            placeholder="Ex: Segunda ou Quarta, manha (9h-12h)",
                            height=100,
                            key=f"obs_agend_{row['id']}"
                        )

                        st.markdown("---")
                        col_submit = st.columns([1, 2, 1])[1]
                        with col_submit:
                            submit_building = st.form_submit_button(
                                "📤 Enviar para verificacao Tecnica",
                                type="primary"
                            )

                        if submit_building:
                            # Validar campos obrigatorios
                            if not all([nome_sindico, contato_sindico, nome_cliente, contato_cliente, apartamento]):
                                st.error("❌ Preencha todos os campos obrigatorios (*)")
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
                                    st.rerun()
                                else:
                                    st.error("❌ Erro ao enviar dados. Tente novamente.")


# ======================
# Footer
# ======================
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <p>📊 <strong>Validador de Projetos</strong> | Desenvolvido ByLeo</p>
</div>
""", unsafe_allow_html=True)

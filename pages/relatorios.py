"""
Página de Relatórios - Análises e visualizações completas
Salve como: pages/relatorios.py
"""

import streamlit as st
from login_system import require_authentication
from viability_functions import (
    get_ftth_approved,
    get_ftth_rejected,
    get_all_approved,
    get_structured_buildings,
    get_buildings_without_viability,
    get_report_statistics,
    format_datetime_resultados,
    format_time_br_supa
)
from supabase_config import supabase
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
from openlocationcode import openlocationcode as olc
from datetime import datetime, timedelta
import logging
import re
logger = logging.getLogger(__name__)

# ======================
# Configuração da Página
# ======================
st.set_page_config(
    page_title="Relatórios - Validador de Projetos",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Verificar autenticação
if not require_authentication():
    st.stop()

# ======================
# Funções Auxiliares
# ======================
def pluscode_to_coords(pluscode: str):
    """Converte Plus Code para coordenadas"""
    try:
        reference_lat = -28.6775
        reference_lon = -49.3696
        pluscode = pluscode.strip().upper()
        if not olc.isFull(pluscode):
            pluscode = olc.recoverNearest(pluscode, reference_lat, reference_lon)
        decoded = olc.decode(pluscode)
        lat = (decoded.latitudeLo + decoded.latitudeHi) / 2
        lon = (decoded.longitudeLo + decoded.longitudeHi) / 2
        return lat, lon
    except Exception as e:
        logger.error(f"Erro ao converter Plus Code: {e}")
        return None, None

# ======================
# Header
# ======================
st.title("📊 Relatórios e Análises")
st.markdown("Análise completa de viabilizações e expansão da rede")

# Botão de atualizar
col_header1, col_header2 = st.columns([4, 1])
with col_header2:
    if st.button("🔄 Atualizar", width='stretch'):
        st.rerun()

st.markdown("---")

# ======================
# FILTRO DE DATA
# ======================
st.subheader("📅 Filtrar por Período")

col_filtro1, col_filtro2, col_filtro3 = st.columns([2, 2, 1])

with col_filtro1:
    data_inicio = st.date_input(
        "Data Início",
        value=None,
        key="data_inicio_relatorio",
        format="DD/MM/YYYY",
        help="Deixe vazio para mostrar desde o início"
    )

with col_filtro2:
    data_fim = st.date_input(
        "Data Fim",
        value=None,
        key="data_fim_relatorio",
        format="DD/MM/YYYY",
        help="Deixe vazio para mostrar até hoje"
    )

with col_filtro3:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔍 Aplicar Filtro", type="primary", width='stretch'):
        st.rerun()

# Converter datas para ISO format (se fornecidas)
data_inicio_iso = data_inicio.isoformat() if data_inicio else None
data_fim_iso = data_fim.isoformat() if data_fim else None

# Mostrar período ativo
if data_inicio or data_fim:
    periodo_texto = f"📊 Exibindo dados de "
    if data_inicio:
        periodo_texto += f"{data_inicio.strftime('%d/%m/%Y')}"
    else:
        periodo_texto += "início"
    periodo_texto += " até "
    if data_fim:
        periodo_texto += f"{data_fim.strftime('%d/%m/%Y')}"
    else:
        periodo_texto += "hoje"
    st.info(periodo_texto)
else:
    st.success("✅ Exibindo todos os dados (sem filtro de período)")

st.markdown("---")

# ======================
# 1. KPIs Principais
# ======================
st.subheader("🎯 Indicadores Principais")

stats = get_report_statistics(data_inicio_iso, data_fim_iso)

col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)

with col_kpi1:
    st.metric(
        label="✅ FTTH Aprovadas",
        value=stats['ftth_aprovadas'],
        help="Inclui aprovadas e finalizadas"
    )

with col_kpi2:
    st.metric(
        label="🏢 Prédios Estruturados",
        value=stats['predios_estruturados']
    )

with col_kpi3:
    taxa_aprovacao = stats.get('taxa_aprovacao_ftth', 0)
    st.metric(
        label="📈 Taxa de Aprovação",
        value=f"{taxa_aprovacao:.1f}%"
    )

with col_kpi4:
    st.metric(
        label="📍 Pontos Sem Viabilidade",
        value=stats['pontos_sem_viabilidade'],
        delta_color="inverse"
    )

st.markdown("---")

# ======================
# 2. Gráficos FTTH
# ======================
st.subheader("📊 Análise FTTH (Residencial)")

col_graph1, col_graph2 = st.columns(2)

# Gráfico de Pizza
with col_graph1:
    st.markdown("#### 🥧 Aprovadas vs Rejeitadas")
    
    labels = ['Aprovadas', 'Rejeitadas']
    values = [
        stats['ftth_aprovadas'],
        stats['ftth_rejeitadas']
    ]
    colors = ['#4CAF50', '#F44336']
    
    fig_pizza = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=.3,
        marker_colors=colors,
        textinfo='label+percent+value',
        textposition='auto'
    )])
    
    fig_pizza.update_layout(
        height=400,
        showlegend=True,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    
    st.plotly_chart(fig_pizza, width='stretch')

# Gráfico de Barras Comparativo
with col_graph2:
    st.markdown("#### 📊 Comparativo de Resultados")
    
    fig_barras = go.Figure(data=[
        go.Bar(
            name='Quantidade',
            x=labels,
            y=values,
            marker_color=colors,
            text=values,
            textposition='auto'
        )
    ])
    
    fig_barras.update_layout(
        height=400,
        yaxis_title="Quantidade",
        showlegend=False,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    
    st.plotly_chart(fig_barras, width='stretch')

st.markdown("---")

# ======================
# 3. MAPA - Pontos Sem Viabilidade FTTH
# ======================
st.subheader("🗺️ Mapa de Pontos Sem Viabilidade FTTH")
st.info("📍 Analise as áreas com rejeições para identificar oportunidades de expansão da rede")

ftth_rejeitadas = get_ftth_rejected(data_inicio_iso, data_fim_iso)

if ftth_rejeitadas:
    # Criar mapa centrado
    mapa = folium.Map(
        location=[-28.6775, -49.3696],
        zoom_start=12,
        tiles="OpenStreetMap"
    )
        
    # Criar cluster de marcadores
    marker_cluster = MarkerCluster(
        name="Pontos Sem Viabilidade",
        overlay=True,
        control=True,
        icon_create_function=None
    ).add_to(mapa)
    
    # Adicionar marcadores
    for idx, row in enumerate(ftth_rejeitadas):
        lat, lon = pluscode_to_coords(row['plus_code_cliente'])

        if lat is not None and lon is not None:
            popup_html = f"""
            <div style='width: 250px'>
                <h4>❌ Sem Viabilidade</h4>
                <p><b>📍 Plus Code:</b> {row['plus_code_cliente']}</p>
                <p><b>👤 Cliente:</b> {row.get('nome_cliente', 'N/A')}</p>
                <p><b>👥 Solicitante:</b> {row['usuario']}</p>
                <p><b>📅 Data:</b> {format_time_br_supa(row['data_auditoria'])}</p>
                <p><b>📝 Motivo:</b> {row.get('motivo_rejeicao', 'Não temos projeto neste ponto')}</p>
                <p><b>🔍 Auditor:</b> {row.get('auditado_por', 'N/A')}</p>
            </div>
            """
            
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=f"❌ {row['plus_code_cliente']} - {row.get('nome_cliente', 'Cliente')}",
                icon=folium.Icon(color='red', icon='times-circle', prefix='fa')
            ).add_to(marker_cluster)
    
    # Renderizar mapa
    st_folium(
        mapa,
        width=None,
        height=500,
        returned_objects=[],
        key="mapa_rejeitadas"
    )
    
    st.caption(f"📊 Total de {len(ftth_rejeitadas)} pontos sem viabilidade mapeados")
else:
    st.success("✅ Não há pontos FTTH sem viabilidade no período selecionado!")

st.markdown("---")

# ======================
# 3.1 MAPA - Viabilidades Aprovadas
# ======================
st.subheader("🗺️ Mapa de Viabilidades Aprovadas")
st.info("📍 Visualize onde há mais demanda e onde estamos atendendo com sucesso")

ftth_aprovadas_mapa = get_all_approved(data_inicio_iso, data_fim_iso)

if ftth_aprovadas_mapa:
    # Criar mapa centrado
    mapa_aprovadas = folium.Map(
        location=[-28.6775, -49.3696],
        zoom_start=12,
        tiles="OpenStreetMap"
    )

    # Criar cluster de marcadores
    marker_cluster_aprovadas = MarkerCluster(
        name="Viabilidades Aprovadas",
        overlay=True,
        control=True,
        icon_create_function=None
    ).add_to(mapa_aprovadas)

    # Contadores por tipo
    count_ftth = 0
    count_predio = 0
    count_condominio = 0

    # Adicionar marcadores
    for idx, row in enumerate(ftth_aprovadas_mapa):
        lat, lon = pluscode_to_coords(row['plus_code_cliente'])

        if lat is not None and lon is not None:
            tipo = row.get('tipo_instalacao', 'FTTH')

            # Definir cor e ícone baseado no tipo
            if tipo == 'FTTH':
                cor = 'green'
                icone = 'home'
                tipo_label = '🏠 FTTH'
                count_ftth += 1
            elif tipo == 'Condomínio':
                cor = 'orange'
                icone = 'building'
                tipo_label = '🏘️ Condomínio'
                count_condominio += 1
            else:
                cor = 'blue'
                icone = 'building'
                tipo_label = '🏢 Prédio'
                count_predio += 1

            # Construir popup com informações relevantes
            popup_html = f"""
            <div style='width: 280px'>
                <h4>✅ {tipo_label}</h4>
                <p><b>📍 Plus Code:</b> {row['plus_code_cliente']}</p>
                <p><b>👤 Cliente:</b> {row.get('nome_cliente', 'N/A')}</p>
                <p><b>👥 Solicitante:</b> {row['usuario']}</p>
                <p><b>📅 Data:</b> {format_time_br_supa(row.get('data_auditoria', ''))}</p>
            """

            # Adicionar campos específicos por tipo
            if tipo == 'FTTH' or tipo == 'Condomínio':
                popup_html += f"""
                <hr style='margin: 5px 0'>
                <p><b>📦 CTO:</b> {row.get('cto_numero', 'N/A')}</p>
                <p><b>📏 Distância:</b> {row.get('distancia_cliente', 'N/A')}</p>
                <p><b>🔌 Portas:</b> {row.get('portas_disponiveis', 'N/A')}</p>
                <p><b>📶 Menor RX:</b> {row.get('menor_rx', 'N/A')} dBm</p>
                """
            else:  # Prédio
                popup_html += f"""
                <hr style='margin: 5px 0'>
                <p><b>🏢 Prédio:</b> {row.get('predio_ftta', 'N/A')}</p>
                <p><b>📡 CDOI:</b> {row.get('cdoi', 'N/A')}</p>
                <p><b>🔌 Portas:</b> {row.get('portas_disponiveis', 'N/A')}</p>
                <p><b>📶 Média RX:</b> {row.get('media_rx', 'N/A')} dBm</p>
                """

            popup_html += f"""
                <hr style='margin: 5px 0'>
                <p><b>🔍 Auditor:</b> {row.get('auditado_por', 'N/A')}</p>
            </div>
            """

            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_html, max_width=320),
                tooltip=f"✅ {row['plus_code_cliente']} - {row.get('nome_cliente', 'Cliente')}",
                icon=folium.Icon(color=cor, icon=icone, prefix='fa')
            ).add_to(marker_cluster_aprovadas)

    # Renderizar mapa
    st_folium(
        mapa_aprovadas,
        width=None,
        height=500,
        returned_objects=[],
        key="mapa_aprovadas"
    )

    # Métricas abaixo do mapa
    col_map1, col_map2, col_map3, col_map4 = st.columns(4)
    with col_map1:
        st.metric("📊 Total Aprovadas", len(ftth_aprovadas_mapa))
    with col_map2:
        st.metric("🏠 FTTH (Casa)", count_ftth)
    with col_map3:
        st.metric("🏘️ Condomínios", count_condominio)
    with col_map4:
        st.metric("🏢 Prédios", count_predio)

    st.caption("💡 **Legenda:** 🟢 FTTH (Casa) | 🟠 Condomínio | 🔵 Prédio")
else:
    st.info("📭 Não há viabilidades aprovadas no período selecionado")

st.markdown("---")

# ======================
# 4. TABELAS FTTH
# ======================
st.subheader("📋 Dados Detalhados FTTH")

tab_ftth1, tab_ftth2 = st.tabs([
    f"✅ Aprovadas ({stats['ftth_aprovadas']})",
    f"❌ Rejeitadas ({stats['ftth_rejeitadas']})"
])

# TAB 1: Aprovadas
with tab_ftth1:
    ftth_aprovadas = get_ftth_approved(data_inicio_iso, data_fim_iso)
    
    if ftth_aprovadas:
        # Busca
        search_aprovadas = st.text_input(
            "🔍 Buscar",
            placeholder="Cliente, Plus Code, CTO, Auditor...",
            key="search_aprovadas"
        )
        
        df_aprovadas = pd.DataFrame(ftth_aprovadas)
        
        # Filtrar
        if search_aprovadas:
            termo_busca = re.escape(search_aprovadas.lower().replace("+", "").strip())
            mask = df_aprovadas.astype(str).apply(
                lambda x: x.str.lower().str.replace("+", "", regex=False).str.contains(termo_busca, regex=True, na=False)
                                
            ).any(axis=1)
            df_aprovadas = df_aprovadas[mask]
        
        # Selecionar colunas (inclui 'usuario')
        colunas = [
            'data_auditoria', 'plus_code_cliente', 'nome_cliente', 'cto_numero',
            'portas_disponiveis', 'menor_rx', 'distancia_cliente', 'usuario', 'auditado_por', 'status'
        ]
        
        df_display = df_aprovadas[[col for col in colunas if col in df_aprovadas.columns]].copy()
        
        # Renomear
        rename_dict = {
            'data_auditoria': 'Data',
            'plus_code_cliente': 'Plus Code',
            'nome_cliente': 'Cliente',
            'cto_numero': 'CTO',
            'portas_disponiveis': 'Portas',
            'menor_rx': 'RX (dBm)',
            'distancia_cliente': 'Distância',
            'usuario': 'Usuário',
            'auditado_por': 'Auditor',
            'status': 'Status'
        }
        df_display.rename(columns=rename_dict, inplace=True)
        
        # Formatar data
        if 'Data' in df_display.columns:
            df_display['Data'] = df_display['Data'].apply(
                lambda x: format_datetime_resultados(x) if pd.notna(x) and x != '' else '-'
            )
        
        # Formatar status
        if 'Status' in df_display.columns:
            df_display['Status'] = df_display['Status'].apply(
                lambda x: '✅ Aprovada' if x == 'aprovado' else '📦 Finalizada'
            )
        
        st.dataframe(df_display, width='stretch', height=400)
        st.caption(f"📊 Mostrando {len(df_display)} de {len(ftth_aprovadas)} registros")
        
        # Exportar
        csv = df_display.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Baixar CSV",
            data=csv,
            file_name="ftth_aprovadas.csv",
            mime="text/csv"
        )
    else:
        st.info("📭 Nenhuma FTTH aprovada no período selecionado.")

# TAB 2: Rejeitadas
with tab_ftth2:
    if ftth_rejeitadas:
        # Busca
        search_rejeitadas = st.text_input(
            "🔍 Buscar",
            placeholder="Cliente, Plus Code, Motivo...",
            key="search_rejeitadas"
        )
        
        df_rejeitadas = pd.DataFrame(ftth_rejeitadas)
        
        # Filtrar
        if search_rejeitadas:
            termo_busca = re.escape(search_rejeitadas.lower().replace("+", "").strip())
            mask = df_rejeitadas.astype(str).apply(
                lambda x: x.str.lower().str.replace("+", "", regex=False).str.contains(termo_busca, regex=True, na=False)
            ).any(axis=1)
            df_rejeitadas = df_rejeitadas[mask]
        
        # Selecionar colunas (inclui 'usuario')
        colunas = [
            'data_auditoria', 'plus_code_cliente', 'nome_cliente',
            'motivo_rejeicao', 'usuario', 'auditado_por'
        ]

        df_display = df_rejeitadas[[col for col in colunas if col in df_rejeitadas.columns]].copy()

        # Renomear com dicionário para manter ordem e nomes claros
        rename_dict = {
            'data_auditoria': 'Data',
            'plus_code_cliente': 'Plus Code',
            'nome_cliente': 'Cliente',
            'motivo_rejeicao': 'Motivo',
            'usuario': 'Usuário',
            'auditado_por': 'Auditor'
        }
        df_display.rename(columns=rename_dict, inplace=True)

        # Formatar data
        if 'Data' in df_display.columns:
            df_display['Data'] = df_display['Data'].apply(
                lambda x: format_datetime_resultados(x) if pd.notna(x) and x != '' else '-'
            )
        
        st.dataframe(df_display, width='stretch', height=400)
        st.caption(f"📊 Mostrando {len(df_display)} de {len(ftth_rejeitadas)} registros")
        
        # Exportar
        csv = df_display.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Baixar CSV",
            data=csv,
            file_name="ftth_rejeitadas.csv",
            mime="text/csv"
        )
    else:
        st.info("📭 Nenhuma FTTH rejeitada no período selecionado.")

st.markdown("---")

# ======================
# 5. SEÇÃO PRÉDIOS/CONDOMÍNIOS
# ======================
st.subheader("🏢 Prédios/Condomínios (FTTA/UTP/FTTH)")

# KPIs Prédios
predios_estruturados = get_structured_buildings()
predios_sem_viab = get_buildings_without_viability()

# Separar por tecnologia
ftta_count = len([p for p in predios_estruturados if p.get('tecnologia') == 'FTTA'])
utp_count = len([p for p in predios_estruturados if p.get('tecnologia') == 'UTP'])
ftth_count = len([p for p in predios_estruturados if p.get('tecnologia') == 'FTTH'])

col_pred1, col_pred2, col_pred3, col_pred4, col_pred5 = st.columns(5)

with col_pred1:
    st.metric("🏗️ Total Estruturados", len(predios_estruturados))

with col_pred2:
    st.metric("⚡ FTTA", ftta_count)

with col_pred3:
    st.metric("📡 UTP", utp_count)

with col_pred4:
    st.metric("🟠 FTTH (Cond.)", ftth_count)

with col_pred5:
    st.metric("❌ Sem Viabilidade", len(predios_sem_viab))

st.markdown("---")

# 🆕 BUSCAR VIABILIDADES DE PRÉDIOS/CONDOMÍNIOS (aprovadas/em análise)
try:
    response_viab_predios = supabase.table('viabilizacoes')\
        .select('*')\
        .in_('tipo_instalacao', ['Prédio', 'Predio', 'Condomínio'])\
        .in_('status', ['aprovado', 'pendente', 'em_auditoria'])\
        .order('data_auditoria', desc=True)\
        .execute()

    viabilidades_predios = response_viab_predios.data if response_viab_predios.data else []
except Exception as e:
    logger.error(f"Erro ao buscar viabilidades de prédios/condomínios: {e}")
    viabilidades_predios = []

# Tabelas Prédios
tab_pred1, tab_pred2, tab_pred3 = st.tabs([
    f"📋 Viabilizações ({len(viabilidades_predios)})",
    f"✅ Estruturados ({len(predios_estruturados)})",
    f"❌ Sem Viabilidade ({len(predios_sem_viab)})"
])

with tab_pred1:
    if viabilidades_predios:
        # Busca
        search_viab_pred = st.text_input(
            "🔍 Buscar",
            placeholder="Prédio, Plus Code, Usuário...",
            key="search_viab_predios"
        )
        
        df_viab_pred = pd.DataFrame(viabilidades_predios)
        
        # Filtrar
        if search_viab_pred:
            termo_busca = re.escape(search_viab_pred.lower().replace("+", "").strip())
            mask = df_viab_pred.astype(str).apply(
                lambda x: x.str.lower().str.replace("+", "", regex=False).str.contains(termo_busca, regex=True, na=False)
            ).any(axis=1)
            df_viab_pred = df_viab_pred[mask]
        
        # Selecionar colunas
        colunas = ['data_auditoria', 'predio_ftta', 'tipo_instalacao', 'andar_predio', 'bloco_predio', 'status',
                   'plus_code_cliente',  'nome_cliente', 'cdoi',
                   'portas_disponiveis', 'media_rx', 'usuario', 'auditado_por']
        #'data_solicitacao'
        
        colunas_existentes = [col for col in colunas if col in df_viab_pred.columns]
        
        df_display = df_viab_pred[colunas_existentes].copy()
        
        # Renomear
        rename_dict = {
           # 'data_solicitacao': 'Data Solicitação',
            'predio_ftta': 'Prédio/Cond.',
            'andar_predio': 'Casa/Apto',
            'bloco_predio': 'Bloco',
            'tipo_instalacao': 'Tipo',
            'status': 'Status',
            'plus_code_cliente': 'Plus Code',
            'usuario': 'Solicitante',
            'nome_cliente': 'Cliente',
            'cdoi': 'CDOI',
            'portas_disponiveis': 'Portas',
            'media_rx': 'Média RX',
            'auditado_por': 'Auditor',
            'data_auditoria': 'Data Auditoria'
        }
        df_display.rename(columns=rename_dict, inplace=True)
        
        # Formatar datas
       # if 'Data Solicitação' in df_display.columns:
        #    df_display['Data Solicitação'] = df_display['Data Solicitação'].apply(
         #       lambda x: format_datetime_resultados(x) if x else '-'
         #   )
        
        if 'Data Auditoria' in df_display.columns:
            df_display['Data Auditoria'] = df_display['Data Auditoria'].apply(
                lambda x: format_datetime_resultados(x) if pd.notna(x) and x != '' else '-'
            )
        
        # Formatar status
        if 'Status' in df_display.columns:
            status_map = {
                'pendente': '⏳ Pendente',
                'em_auditoria': '🔍 Em Auditoria',
                'aprovado': '✅ Aprovado'
            }
            df_display['Status'] = df_display['Status'].map(status_map).fillna(df_display['Status'])

        # Formatar tipo
        if 'Tipo' in df_display.columns:
            tipo_map = {
                'Prédio': '🏢 Prédio',
                'Predio': '🏢 Prédio',
                'Condomínio': '🏘️ Condomínio'
            }
            df_display['Tipo'] = df_display['Tipo'].map(tipo_map).fillna(df_display['Tipo'])

        # Exibir tabela
        st.dataframe(df_display, width='stretch', height=400)
        st.caption(f"📊 Mostrando {len(df_display)} de {len(viabilidades_predios)} registros")
        
        # Exportar
        csv = df_display.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Baixar CSV",
            data=csv,
            file_name="viabilizacoes_predios.csv",
            mime="text/csv"
        )
        
        # 🆕 ESTATÍSTICAS RÁPIDAS
        st.markdown("---")
        st.subheader("📊 Estatísticas Rápidas")
        
        col_stats1, col_stats2, col_stats3, col_stats4 = st.columns(4)
        
        with col_stats1:
            pendentes = len([v for v in viabilidades_predios if v['status'] == 'pendente'])
            st.metric("⏳ Pendentes", pendentes)
        
        with col_stats2:
            em_audit = len([v for v in viabilidades_predios if v['status'] == 'em_auditoria'])
            st.metric("🔍 Em Auditoria", em_audit)
        
        with col_stats3:
            aprovados = len([v for v in viabilidades_predios if v['status'] == 'aprovado'])
            st.metric("✅ Aprovados", aprovados)
        
        with col_stats4:
            # Prédios únicos
            predios_unicos = df_viab_pred['predio_ftta'].nunique() if 'predio_ftta' in df_viab_pred.columns else 0
            st.metric("🏨Prédios Únicos", predios_unicos)
        
    else:
        st.info("📭 Nenhuma viabilização de prédio no período selecionado.")

# TAB 1: Estruturados
with tab_pred2:
    if predios_estruturados:
        df_estruturados = pd.DataFrame(predios_estruturados)
        
        # Selecionar colunas
        colunas = ['data_estruturacao', 'condominio', 'tecnologia', 
                   'localizacao', 'estruturado_por']
        
        df_display = df_estruturados[[col for col in colunas if col in df_estruturados.columns]].copy()

        # Renomear usando dicionário (mais seguro)
        rename_dict = {
            'data_estruturacao': 'Data',
            'condominio': 'Condomínio',
            'tecnologia': 'Tecnologia',
            'localizacao': 'Localização',
            'estruturado_por': 'Técnico'
        }
        df_display.rename(columns=rename_dict, inplace=True)
        
        # Formatar data
        if 'Data' in df_display.columns:
            df_display['Data'] = df_display['Data'].apply(
                lambda x: format_datetime_resultados(x) if pd.notna(x) and x != '' else '-'
            )
        
        st.dataframe(df_display, width='stretch', height=400)
        
        # Exportar
        csv = df_display.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Baixar CSV",
            data=csv,
            file_name="predios_estruturados.csv",
            mime="text/csv"
        )
    else:
        st.info("📭 Nenhum prédio estruturado ainda.")

# TAB 2: Sem Viabilidade
with tab_pred3:
    if predios_sem_viab:
        df_sem_viab = pd.DataFrame(predios_sem_viab)
        
        # Selecionar colunas
        colunas = ['data_registro', 'condominio', 'localizacao', 
                   'observacao', 'registrado_por']
        
        df_display = df_sem_viab[[col for col in colunas if col in df_sem_viab.columns]].copy()

        # Renomear usando dicionário (mais seguro)
        rename_dict = {
            'data_registro': 'Data',
            'condominio': 'Condomínio',
            'localizacao': 'Localização',
            'observacao': 'Motivo',
            'registrado_por': 'Registrado Por'
        }
        df_display.rename(columns=rename_dict, inplace=True)
        
        # Formatar data
        if 'Data' in df_display.columns:
            df_display['Data'] = df_display['Data'].apply(
                lambda x: format_datetime_resultados(x) if pd.notna(x) and x != '' else '-'
            )
        
        st.dataframe(df_display, width='stretch', height=400)
        
        # Exportar
        csv = df_display.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Baixar CSV",
            data=csv,
            file_name="predios_sem_viabilidade.csv",
            mime="text/csv"
        )
    else:
        st.success("✅ Não há prédios sem viabilidade!")

# ======================
# Footer
# ======================
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <p>📊 <strong>Validador de Projetos</strong> | Desenvolvido ByLeo</p>
</div>
""", unsafe_allow_html=True)

"""
Página de Relatórios - Análises e visualizações completas
Salve como: pages/relatorios.py
"""

import streamlit as st
from login_system import require_authentication
from viability_functions import (
    get_ftth_approved,
    get_ftth_rejected,
    get_structured_buildings,
    get_buildings_without_viability,
    get_report_statistics,
    format_datetime_resultados,
    format_time_br_supa
)
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
    if st.button("🔄 Atualizar", use_container_width=True):
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
    if st.button("🔍 Aplicar Filtro", type="primary", use_container_width=True):
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
    st.metric(
        label="📈 Taxa de Aprovação",
        value=f"{stats['taxa_aprovacao_ftth']:.1f}%"
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
    
    st.plotly_chart(fig_pizza, use_container_width=True)

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
    
    st.plotly_chart(fig_barras, use_container_width=True)

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
    
    # Criar cluster de marcadores COM COR VERMELHA
    marker_cluster = MarkerCluster(
        name="Pontos Sem Viabilidade",
        overlay=True,
        control=True,
        icon_create_function="""\
            function(cluster) {
                var childCount = cluster.getChildCount();
                var c = ' marker-cluster-';
                if (childCount < 10) {
                    c += 'small';
                } else if (childCount < 100) {
                    c += 'medium';
                } else {
                    c += 'large';
                }
                return new L.DivIcon({ 
                    html: '<div><span>' + childCount + '</span></div>', 
                    className: 'marker-cluster-red' + c, 
                    iconSize: new L.Point(40, 40) 
                });
            }
        """
    ).add_to(mapa)
    
    # Adicionar CSS customizado para clusters vermelhos
    mapa.get_root().html.add_child(folium.Element("""\
    <style>
        .marker-cluster-red {
            background-color: rgba(255, 0, 0, 0.6);
        }
        .marker-cluster-red div {
            background-color: rgba(220, 0, 0, 0.6);
            width: 30px;
            height: 30px;
            margin-left: 5px;
            margin-top: 5px;
            text-align: center;
            border-radius: 15px;
            font: 12px "Helvetica Neue", Arial, Helvetica, sans-serif;
            font-weight: bold;
            line-height: 30px;
        }
        .marker-cluster-red span {
            color: #fff;
        }
        .marker-cluster-redsmall {
            background-color: rgba(255, 100, 100, 0.6);
        }
        .marker-cluster-redsmall div {
            background-color: rgba(255, 0, 0, 0.7);
        }
        .marker-cluster-redmedium {
            background-color: rgba(240, 50, 50, 0.6);
        }
        .marker-cluster-redmedium div {
            background-color: rgba(200, 0, 0, 0.7);
        }
        .marker-cluster-redlarge {
            background-color: rgba(220, 0, 0, 0.6);
        }
        .marker-cluster-redlarge div {
            background-color: rgba(180, 0, 0, 0.7);
        }
    </style>
    """))
    
    # Adicionar marcadores
    for idx, row in enumerate(ftth_rejeitadas):
        lat, lon = pluscode_to_coords(row['plus_code_cliente'])
        
        if lat and lon:
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
        
        # Selecionar colunas
        colunas = ['data_auditoria', 'plus_code_cliente', 'nome_cliente', 'cto_numero', 
                   'portas_disponiveis', 'menor_rx', 'distancia_cliente', 'auditado_por', 'status']
        
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
            'auditado_por': 'Auditor',
            'status': 'Status'
        }
        df_display.rename(columns=rename_dict, inplace=True)
        
        # Formatar data
        if 'Data' in df_display.columns:
            df_display['Data'] = df_display['Data'].apply(
                lambda x: format_datetime_resultados(x) if x else '-'
            )
        
        # Formatar status
        if 'Status' in df_display.columns:
            df_display['Status'] = df_display['Status'].apply(
                lambda x: '✅ Aprovada' if x == 'aprovado' else '📦 Finalizada'
            )
        
        st.dataframe(df_display, use_container_width=True, height=400)
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
        st.info("Nenhuma FTTH aprovada no período selecionado.")

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
        
        # Selecionar colunas
        colunas = ['data_auditoria', 'plus_code_cliente', 'nome_cliente', 
                   'motivo_rejeicao', 'auditado_por']
        
        df_display = df_rejeitadas[[col for col in colunas if col in df_rejeitadas.columns]].copy()
        
        # Renomear
        df_display.columns = ['Data', 'Plus Code', 'Cliente', 'Motivo', 'Auditor'][:len(df_display.columns)]
        
        # Formatar data
        if 'Data' in df_display.columns:
            df_display['Data'] = df_display['Data'].apply(
                lambda x: format_datetime_resultados(x) if x else '-'
            )
        
        st.dataframe(df_display, use_container_width=True, height=400)
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
        st.success("✅ Não há FTTH rejeitadas no período selecionado!")

st.markdown("---")

# ======================
# 5. SEÇÃO PRÉDIOS
# ======================
st.subheader("🏢 Prédios (FTTA/UTP)")

# KPIs Prédios
predios_estruturados = get_structured_buildings()
predios_sem_viab = get_buildings_without_viability()

# Separar por tecnologia
ftta_count = len([p for p in predios_estruturados if p.get('tecnologia') == 'FTTA'])
utp_count = len([p for p in predios_estruturados if p.get('tecnologia') == 'UTP'])

col_pred1, col_pred2, col_pred3, col_pred4 = st.columns(4)

with col_pred1:
    st.metric("🏗️ Total Estruturados", len(predios_estruturados))

with col_pred2:
    st.metric("⚡ FTTA Estruturados", ftta_count)

with col_pred3:
    st.metric("📡 UTP Estruturados", utp_count)

with col_pred4:
    st.metric("❌ Sem Viabilidade", len(predios_sem_viab))

st.markdown("---")

# Tabelas Prédios
tab_pred1, tab_pred2 = st.tabs([
    f"✅ Estruturados ({len(predios_estruturados)})",
    f"❌ Sem Viabilidade ({len(predios_sem_viab)})"
])

# TAB 1: Estruturados
with tab_pred1:
    if predios_estruturados:
        df_estruturados = pd.DataFrame(predios_estruturados)
        
        # Selecionar colunas
        colunas = ['data_estruturacao', 'condominio', 'tecnologia', 
                   'localizacao', 'estruturado_por']
        
        df_display = df_estruturados[[col for col in colunas if col in df_estruturados.columns]].copy()
        
        # Renomear
        df_display.columns = ['Data', 'Condomínio', 'Tecnologia', 'Localização', 'Técnico'][:len(df_display.columns)]
        
        # Formatar data
        if 'Data' in df_display.columns:
            df_display['Data'] = df_display['Data'].apply(
                lambda x: format_datetime_resultados(x) if x else '-'
            )
        
        st.dataframe(df_display, use_container_width=True, height=400)
        
        # Exportar
        csv = df_display.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Baixar CSV",
            data=csv,
            file_name="predios_estruturados.csv",
            mime="text/csv"
        )
    else:
        st.info("Nenhum prédio estruturado ainda.")

# TAB 2: Sem Viabilidade
with tab_pred2:
    if predios_sem_viab:
        df_sem_viab = pd.DataFrame(predios_sem_viab)
        
        # Selecionar colunas
        colunas = ['data_registro', 'condominio', 'localizacao', 
                   'observacao', 'registrado_por']
        
        df_display = df_sem_viab[[col for col in colunas if col in df_sem_viab.columns]].copy()
        
        # Renomear
        df_display.columns = ['Data', 'Condomínio', 'Localização', 'Motivo', 'Registrado Por'][:len(df_display.columns)]
        
        # Formatar data
        if 'Data' in df_display.columns:
            df_display['Data'] = df_display['Data'].apply(
                lambda x: format_datetime_resultados(x) if x else '-'
            )
        
        st.dataframe(df_display, use_container_width=True, height=400)
        
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

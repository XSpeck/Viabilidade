"""
Página de Auditoria - Acesso restrito ao Leo
Salve como: pages/auditoria.py
"""

import streamlit as st
from login_system import require_authentication
from streamlit_autorefresh import st_autorefresh
from viability_functions import (
    format_time_br_supa,
    get_pending_viabilities,
    update_viability_ftth,
    update_viability_ftta,
    delete_viability,
    get_statistics,
    request_building_viability,
    reject_building_viability 
)
import logging
# Imports adicionais para busca de CTOs
import xml.etree.ElementTree as ET
from shapely.geometry import LineString, Point
from openlocationcode import openlocationcode as olc
from geopy.distance import geodesic
import gdown
import requests
import folium
from streamlit_folium import st_folium
from typing import List, Tuple

logger = logging.getLogger(__name__)

# ======================
# Configuração da Página
# ======================
st.set_page_config(
    page_title="Auditoria - Validador de Projetos",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ======================
# Atualização automática
# ======================

st_autorefresh(interval=15000, key="auditoria_refresh")  # 15000 ms = 15 segundos

# Verificar autenticação
if not require_authentication():
    st.stop()

# Verificar se é Admin (nível 1)
if st.session_state.user_nivel != 1:
    st.error("🚫 Acesso Negado! Esta página é restrita a administradores.")
    st.info("👈 Use o menu lateral para navegar.")
    st.stop()

# ======================
# Header
# ======================
st.title("🔍 Auditoria de Viabilizações")
st.markdown("Análise técnica das solicitações de viabilidade")

# Configurações para busca
LOCATIONIQ_KEY = "pk.66f355328aaad40fe69b57c293f66815"
reference_lat = -28.6775
reference_lon = -49.3696
file_id_ctos = "1EcKNk2yqHDEMMXJZ17fT0flPV19HDhKJ"
ctos_kml_path = "ctos.kml"

KML_CONFIGS = {
    "COOPER-COCAL": {
        "file_id": "1XD-GgwgFgB2RcKkBAxf5RSBWu2yfIf2w",
        "color": "#FF1493",
        "path": "cooper_cocal.kml"
    },
    "COOPERA": {
        "file_id": "1E5tKI5brZMo1rcrJANXggYegV1IrCdnv",
        "color": "#00FF00",
        "path": "coopera.kml"
    },
    "COPERALIANCA": {
        "file_id": "1cDZwFpCDygrmZvP2_oSZoXT3oKXKT8Bh",
        "color": "#0000FF",
        "path": "coperalianca.kml"
    },
    "CERMOFUL": {
        "file_id": "1r4gnRFaNUmAZ6f9oTdR1x9RcfksWTXDx",
        "color": "#FF8C00",
        "path": "cermoful.kml"
    },
    "CERTREL": {
        "file_id": "1ZGczns-MIV897jQ8HRhH6LFgMRMdydm4",
        "color": "#8A2BE2",
        "path": "certrel.kml"
    },
    "FORÇALUZ": {
        "file_id": "1CHAWKnha0C1f44uLJYXUOj0UcrtnlPKK",
        "color": "#FFD700",
        "path": "forcaluz.kml"
    },
    "CELESC": {
        "file_id": "1M5P4_THpr1qxcxhPVOyQCdGTE5_7faRB",
        "color": "#FF0000",
        "path": "celesc.kml"
    }
}

# ============================================
# FUNÇÕES DE BUSCA (copiar do validator_system.py)
# ============================================

def validate_coordinates(lat: float, lon: float) -> bool:
    return -90 <= lat <= 90 and -180 <= lon <= 180

def format_distance(distance_m: float) -> str:
    if distance_m < 1000:
        return f"{distance_m:.1f}m"
    else:
        return f"{distance_m/1000:.2f}km"

def coords_to_pluscode(lat, lon):
    return olc.encode(lat, lon)

@st.cache_data(ttl=3600)
def download_ctos_file(file_id: str, output: str) -> str:
    try:
        url = f"https://drive.google.com/uc?id={file_id}"
        gdown.download(url, output, quiet=True, fuzzy=True)
        return output
    except Exception as e:
        logger.error(f"Erro ao baixar CTOs: {e}")
        raise

@st.cache_data(ttl=3600)
def load_ctos_from_kml(path: str) -> List[dict]:
    try:
        namespaces = {'kml': 'http://www.opengis.net/kml/2.2'}
        tree = ET.parse(path)
        root = tree.getroot()
        ctos = []
        for placemark in root.findall(".//kml:Placemark", namespaces):
            name_elem = placemark.find("kml:name", namespaces)
            coords_elem = placemark.find(".//kml:coordinates", namespaces)
            if coords_elem is not None and coords_elem.text:
                parts = coords_elem.text.strip().split(",")
                if len(parts) >= 2:
                    lon, lat = float(parts[0]), float(parts[1])
                    if validate_coordinates(lat, lon):
                        ctos.append({
                            "name": name_elem.text.strip() if name_elem is not None else "CTO",
                            "lat": lat,
                            "lon": lon
                        })
        return ctos
    except Exception as e:
        logger.error(f"Erro ao carregar CTOs: {e}")
        return []

def pluscode_to_coords(pluscode: str) -> Tuple[float, float]:
    try:
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

def find_nearest_ctos(lat: float, lon: float, ctos: List[dict], max_radius: float = 400.0) -> List[dict]:
    if not ctos:
        return []
    dists = []
    for cto in ctos:
        if cto["name"].upper().startswith("CDOI"):
            continue
        dist = geodesic((lat, lon), (cto["lat"], cto["lon"])).meters
        if dist <= max_radius:
            dists.append({**cto, "distance": dist})
    dists.sort(key=lambda x: x["distance"])
    return dists

@st.cache_data(ttl=3600)
def get_walking_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float):
    try:
        url = f"http://router.project-osrm.org/route/v1/foot/{start_lon},{start_lat};{end_lon},{end_lat}"
        params = {"overview": "full", "geometries": "geojson", "steps": "false"}
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == "Ok" and data.get("routes"):
                route = data["routes"][0]
                return {
                    "distance": route["distance"],
                    "duration": route["duration"],
                    "geometry": route["geometry"]
                }
        return None
    except Exception as e:
        logger.error(f"Erro ao calcular rota: {e}")
        return None

@st.cache_data(ttl=3600)
def load_lines_from_kml(path: str) -> List[List[Tuple[float, float]]]:
    """Carrega linhas de projeto de um arquivo KML"""
    try:
        namespaces = {'kml': 'http://www.opengis.net/kml/2.2'}
        tree = ET.parse(path)
        root = tree.getroot()
        lines = []
        for ls in root.findall(".//kml:LineString", namespaces):
            coords_elem = ls.find("kml:coordinates", namespaces)
            if coords_elem is not None and coords_elem.text:
                try:
                    raw = coords_elem.text.strip().split()
                    coords = []
                    for c in raw:
                        parts = c.split(',')
                        if len(parts) >= 2:
                            lon, lat = float(parts[0]), float(parts[1])
                            if validate_coordinates(lat, lon):
                                coords.append((lat, lon))
                    if len(coords) > 1:
                        lines.append(coords)
                except (ValueError, IndexError) as e:
                    logger.warning(f"Linha KML inválida ignorada: {e}")
                    continue
        logger.info(f"Carregadas {len(lines)} linhas do KML {path}")
        return lines
    except Exception as e:
        logger.error(f"Erro ao carregar linhas KML: {e}")
        return []

@st.cache_data(ttl=3600)
def download_file(file_id: str, output: str) -> str:
    """Download de arquivo do Google Drive"""
    try:
        url = f"https://drive.google.com/uc?id={file_id}"
        gdown.download(url, output, quiet=True, fuzzy=True)
        logger.info(f"Arquivo {output} baixado com sucesso")
        return output
    except Exception as e:
        logger.error(f"Erro ao baixar {output}: {e}")
        raise Exception(f"Falha no download do arquivo {output}: {str(e)}")

# Botão de atualizar
col_header1, col_header2 = st.columns([4, 1])
with col_header2:
    if st.button("🔄 Atualizar", use_container_width=True):
        st.rerun()

# ======================
# Função de Formulário
# ======================
def show_viability_form(row: dict, urgente: bool = False):
    """Exibe formulário de auditoria para uma viabilização"""
    
     # Estilo do card baseado na urgência
    if urgente:
        icon = "🔥"
        badge_urgente = " - **URGENTE**"
    else:
        icon = "📋"
        badge_urgente = "" 
    
    # Determinar tipo para exibição
    if row['tipo_instalacao'] == 'FTTH':
        tipo_exibir = 'FTTH (Casa)'
        tipo_icon = "🏠"
    elif row['tipo_instalacao'] == 'Prédio':
        if row.get('tecnologia_predio'):
            tipo_exibir = f"{row['tecnologia_predio']} (Prédio)"
        else:
            tipo_exibir = 'Prédio'
        tipo_icon = "🏢"
    else:
        tipo_exibir = row['tipo_instalacao']
        tipo_icon = "📋"
    
    # Criar título do expander (resumo)
    titulo_expander = f"{icon} {tipo_icon} **{row.get('nome_cliente', 'Cliente')}** | {row['plus_code_cliente']}"
    
    if row.get('predio_ftta'):
        titulo_expander += f" | 🏢 {row['predio_ftta']}"
    
    titulo_expander += badge_urgente
    
    # Criar subtítulo (informações extras)
    subtitulo = f"👤 Solicitado por: {row['usuario']} | 📅 {format_time_br_supa(row['data_solicitacao'])}"
    
    # EXPANDER (COLAPSADO POR PADRÃO)
    with st.expander(titulo_expander, expanded=False):
        st.caption(subtitulo)
        st.markdown("---")        
                
        # Informações da solicitação
        col1, col2 = st.columns([2, 3])
        
        with col1:
            st.markdown("#### 📋 Informações")
            st.text(f"👤 Usuário: {row['usuario']}")
            if row.get('nome_cliente'):
                st.text(f"🙋 Cliente: {row['nome_cliente']}")
            st.text(f"📍 Plus Code: {row['plus_code_cliente']}")
            
            # Determinar tipo real
            if row['tipo_instalacao'] == 'FTTH':
                tipo_exibir = 'FTTH (Casa)'
            elif row['tipo_instalacao'] == 'Prédio':
                # Se já foi definido pelo Leo
                if row.get('tecnologia_predio'):
                    tipo_exibir = f"{row['tecnologia_predio']} (Prédio)"
                else:
                    tipo_exibir = 'Prédio (a definir)'
            else:
                tipo_exibir = row['tipo_instalacao']
            
            st.text(f"🏷️ Tipo: {tipo_exibir}")
            
            if row.get('predio_ftta'):
                st.text(f"🏨 Nome: {row['predio_ftta']}")            
            st.text(f"📅 Solicitado em: {format_time_br_supa(row['data_solicitacao'])}")
            
            # ===== BOTÃO EXCLUIR =====
            st.markdown("---")
            if st.button(
                "🗑️ Excluir Solicitação",
                key=f"delete_{row['id']}",
                type="secondary",
                use_container_width=True,
                help="Excluir esta solicitação permanentemente"
            ):
                if delete_viability(row['id']):
                    st.success("✅ Solicitação excluída!")
                    st.rerun()            
            if urgente:
                st.error("🔥 **URGENTE - Cliente Presencial**")
        
        with col2:
            # Formulário baseado no tipo
            if row['tipo_instalacao'] == 'FTTH':
                st.markdown("#### 🏠 Dados FTTH (Casa)")
                
                # Verificar se CTO já foi escolhida
                cto_escolhida = row.get('cto_numero')
                
                if cto_escolhida:
                    st.success(f"✅ CTO Escolhida: **{cto_escolhida}**")
                    st.caption(f"📏 Distância: {row.get('distancia_cliente', 'N/A')} | 📍 Localização: {row.get('localizacao_caixa', 'N/A')}")
                    st.warning("⚠️ Os campos abaixo são EDITÁVEIS caso precise corrigir")
                
                # ========================================
                # BOTÃO BUSCAR CTOs (se ainda não escolheu)
                # ========================================
                if not cto_escolhida or st.session_state.get(f'mostrar_busca_{row["id"]}', False):
                    col_busca = st.columns([1, 2, 1])[1]
                    with col_busca:
                        if st.button(
                            "🔍 Buscar CTOs Próximas",
                            type="secondary",
                            use_container_width=True,
                            key=f"btn_buscar_{row['id']}"
                        ):
                            st.session_state[f'mostrar_busca_{row["id"]}'] = True
                            st.rerun()
                
                # ========================================
                # MOSTRAR BUSCA DE CTOs
                # ========================================
                if st.session_state.get(f'mostrar_busca_{row["id"]}', False):
                    cache_key = f'busca_cache_{row["id"]}'
    
                    if cache_key not in st.session_state:
                                        
                        try:
                            # Converter Plus Code para coordenadas
                            lat, lon = pluscode_to_coords(row['plus_code_cliente'])
                            
                            if lat and lon:
                                # 🆕 CARREGAR CTOs E LINHAS
                                with st.spinner("Carregando dados..."):
                                    # Baixar e carregar CTOs
                                    download_ctos_file(file_id_ctos, ctos_kml_path)
                                    ctos = load_ctos_from_kml(ctos_kml_path)
                                    
                                    # 🆕 Baixar e carregar linhas de projeto
                                    all_lines = {}
                                    for company, config in KML_CONFIGS.items():
                                        try:
                                            download_file(config["file_id"], config["path"])
                                            lines = load_lines_from_kml(config["path"])
                                            all_lines[company] = {
                                                "lines": lines,
                                                "color": config["color"]
                                            }
                                            logger.info(f"Carregadas {len(lines)} linhas para {company}")
                                        except Exception as e:
                                            logger.error(f"Erro ao carregar {company}: {e}")
                                            all_lines[company] = {"lines": [], "color": config["color"]}
                            
                            # Buscar CTOs próximas
                            candidate_ctos = find_nearest_ctos(lat, lon, ctos, max_radius=3500.0)
                            
                            if candidate_ctos:
                                cto_routes = []
                                
                                with st.spinner("📍 Calculando rotas..."):
                                    for cto in candidate_ctos[:10]:
                                        route = get_walking_route(lat, lon, cto["lat"], cto["lon"])
                                        
                                        if route:
                                            linha_reta = geodesic((lat, lon), (cto["lat"], cto["lon"])).meters
                                            if route["distance"] > linha_reta * 5:
                                                route["distance"] = linha_reta
                                            
                                            cto_routes.append({
                                                "cto": cto,
                                                "route": route,
                                                "distance": route["distance"]
                                            })
                                        else:
                                            cto_routes.append({
                                                "cto": cto,
                                                "route": None,
                                                "distance": cto["distance"]
                                            })
                                    
                                    cto_routes.sort(key=lambda x: x["distance"])
                                    cto_routes = cto_routes[:5]

                                # 💾 SALVAR NO CACHE
                                st.session_state[cache_key] = {
                                    'lat': lat,
                                    'lon': lon,
                                    'cto_routes': cto_routes,
                                    'all_lines': all_lines
                                }
                            else:
                                st.warning("⚠️ Nenhuma CTO encontrada próxima (raio de 3.5km)")
                        else:
                            st.error("❌ Erro ao converter Plus Code para coordenadas")
                    
                    except Exception as e:
                        st.error(f"❌ Erro na busca: {e}")
                        logger.error(f"Erro ao buscar CTOs: {e}")
                
                # 📦 USAR DADOS DO CACHE
                if cache_key in st.session_state:
                    cached = st.session_state[cache_key]
                    lat = cached['lat']
                    lon = cached['lon']
                    cto_routes = cached['cto_routes']
                    all_lines = cached['all_lines']
                            
                    st.success(f"✅ {len(cto_routes)} CTOs encontradas")

                # ========================================
                # MAPA INTERATIVO
                # ========================================
                
                st.markdown("### 🗺️ Visualização no Mapa")                               
                
                # Criar mapa centrado no cliente
                mapa = folium.Map(
                    location=[lat, lon],
                    zoom_start=16,
                    tiles="OpenStreetMap"
                )
                for company, data in all_lines.items():
                    for line_coords in data["lines"]:
                        folium.PolyLine(
                            locations=line_coords,
                            color=data["color"],
                            weight=3,
                            opacity=0.6,
                            tooltip=f"Projeto {company}"
                        ).add_to(mapa)
                
                # Marcador do CLIENTE
                folium.Marker(
                    location=[lat, lon],
                    popup=f"<b>🏠 Cliente</b><br>{row.get('nome_cliente', 'Cliente')}<br>{row['plus_code_cliente']}",
                    tooltip="📍 Localização do Cliente",
                    icon=folium.Icon(color='red', icon='home', prefix='fa')
                ).add_to(mapa)
                
                # Adicionar CTOs encontradas
                for idx, item in enumerate(cto_routes):
                    cto = item["cto"]
                    route = item["route"]
                    
                    # Cor baseada na posição (verde = mais próxima)
                    cores = ['green', 'blue', 'orange', 'purple', 'darkred']
                    cor = cores[idx] if idx < len(cores) else 'gray'
                    
                    # Ícone com número
                    icons_numero = ['1', '2', '3', '4', '5']
                    icon_numero = icons_numero[idx] if idx < len(icons_numero) else str(idx+1)
                    
                    # Popup com informações
                    if route:
                        dist_info = f"🚶 Rota: {format_distance(route['distance'])}<br>🏃 +50m: {format_distance(route['distance'] + 50)}"
                    else:
                        dist_info = f"📏 Linha reta: {format_distance(cto['distance'])}"
                    
                    popup_html = f"""
                    <div style='width: 200px'>
                        <h4>{icon_numero}. {cto['name']}</h4>
                        <p>{dist_info}</p>
                        <p>📍 {coords_to_pluscode(cto['lat'], cto['lon'])}</p>
                    </div>
                    """
                    
                    # Marcador da CTO
                    folium.Marker(
                        location=[cto["lat"], cto["lon"]],
                        popup=folium.Popup(popup_html, max_width=250),
                        tooltip=f"{icon_numero}. {cto['name']} - {format_distance(item['distance'])}",
                        icon=folium.Icon(color=cor, icon='info-sign', prefix='glyphicon')
                    ).add_to(mapa)
                    
                    # Desenhar ROTA se existir
                    if route and route.get('geometry'):
                        # Extrair coordenadas da rota
                        coordenadas_rota = []
                        for coord in route['geometry']['coordinates']:
                            coordenadas_rota.append([coord[1], coord[0]])  # [lat, lon]
                        
                        # Linha da rota
                        folium.PolyLine(
                            locations=coordenadas_rota,
                            color=cor,
                            weight=4,
                            opacity=0.7,
                            tooltip=f"Rota até {cto['name']}"
                        ).add_to(mapa)
                    else:
                        # Linha reta se não houver rota
                        folium.PolyLine(
                            locations=[[lat, lon], [cto["lat"], cto["lon"]]],
                            color=cor,
                            weight=2,
                            opacity=0.4,
                            dash_array='10',
                            tooltip=f"Linha reta até {cto['name']}"
                        ).add_to(mapa)
                
                # Ajustar zoom para mostrar todos os pontos
                bounds = [[lat, lon]]
                for item in cto_routes:
                    bounds.append([item["cto"]["lat"], item["cto"]["lon"]])
                
                mapa.fit_bounds(bounds, padding=[50, 50])
                
                # Renderizar mapa
                st_folium(mapa, width=700, height=500)
                
                st.markdown("---")
                # ========================================
                # FIM DO MAPA
                # ========================================
                                
                                # Exibir CTOs
                                for idx, item in enumerate(cto_routes):
                                    cto = item["cto"]
                                    route = item["route"]
                                    pluscode_cto = coords_to_pluscode(cto["lat"], cto["lon"])
                                    
                                    icons = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
                                    icon = icons[idx] if idx < len(icons) else "📍"
                                    
                                    col_cto1, col_cto2 = st.columns([4, 1])
                                    
                                    with col_cto1:
                                        if route:
                                            dist_real = route["distance"]
                                            dist_com_sobra = dist_real + 50
                                            
                                            st.markdown(f"""
                                            **{icon} CTO: {cto["name"]}**  
                                            📍 Localização: `{pluscode_cto}`  
                                            🚶 Distância real: {format_distance(route["distance"])}  
                                            🏃‍♂️ Com sobra (+50m): {format_distance(dist_com_sobra)}
                                            """)
                                        else:
                                            dist_com_sobra = cto["distance"] + 50
                                            st.markdown(f"""
                                            **{icon} CTO: {cto["name"]}**  
                                            📍 Localização: `{pluscode_cto}`  
                                            📏 Distância em linha reta: {format_distance(cto["distance"])}
                                            🏃‍♂️ Com sobra (+50m): {format_distance(dist_com_sobra)}
                                            """)
                                    
                                    with col_cto2:
                                        if st.button(
                                            "✅ Escolher",
                                            key=f"escolher_cto_{row['id']}_{idx}",
                                            type="primary",
                                            use_container_width=True
                                        ):
                                            # Calcular distância com sobra
                                            if route:
                                                dist_final = route["distance"] + 50
                                            else:
                                                dist_final = cto["distance"] + 50
                                            
                                            # Salvar CTO escolhida
                                            from viability_functions import save_selected_cto
                                            
                                            cto_data = {
                                                'cto_numero': cto["name"],
                                                'distancia_cliente': format_distance(dist_final),
                                                'localizacao_caixa': pluscode_cto
                                            }
                                            
                                            if save_selected_cto(row['id'], cto_data):
                                                st.success(f"✅ CTO {cto['name']} escolhida!")
                                                del st.session_state[f'mostrar_busca_{row["id"]}']
                                                st.rerun()
                                    
                                    st.markdown("---")
                            else:
                                st.warning("⚠️ Nenhuma CTO encontrada próxima (raio de 3.5km)")
                        else:
                            st.error("❌ Erro ao converter Plus Code para coordenadas")
                    
                    except Exception as e:
                        st.error(f"❌ Erro na busca: {e}")
                        logger.error(f"Erro ao buscar CTOs: {e}")
                    
                    # Botão para fechar busca
                    col_fechar = st.columns([1, 2, 1])[1]
                    with col_fechar:
                        if st.button("❌ Fechar Busca", use_container_width=True, key=f"fechar_busca_{row['id']}"):
                            del st.session_state[f'mostrar_busca_{row["id"]}']
                            if f'busca_cache_{row["id"]}' in st.session_state:
                                del st.session_state[f'busca_cache_{row["id"]}']
                            st.rerun()                    
                
                # ========================================
                # FORMULÁRIO DE AUDITORIA
                # ========================================
                st.markdown("---")
                
                with st.form(key=f"form_ftth_{row['id']}"):
                    cto = st.text_input(
                        "N° Caixa (CTO) *", 
                        value=row.get('cto_numero', ''),
                        disabled=False,
                        key=f"cto_{row['id']}",
                        help="⚠️ Você pode editar este campo se necessário"
                    )
                    
                    col_f1, col_f2 = st.columns(2)
                    with col_f1:
                        distancia = st.text_input(
                            "Distância até Cliente *",
                            value=row.get('distancia_cliente', ''),
                            disabled=False,
                            key=f"dist_{row['id']}",
                            help="⚠️ Editável - ex: 150m, 1.2km"
                        )
                    with col_f2:
                        localizacao = st.text_input(
                            "Localização da Caixa *",
                            value=row.get('localizacao_caixa', ''),
                            disabled=False,
                            key=f"loc_{row['id']}",
                            help="⚠️ Editável - Plus Code da caixa"
                        )
                    
                    st.markdown("---")
                    st.markdown("**Preencha os dados técnicos:**")
                    
                    col_f3, col_f4 = st.columns(2)
                    with col_f3:
                        portas = st.number_input("Portas Disponíveis *", min_value=0, max_value=50, value=0, key=f"portas_{row['id']}")
                    with col_f4:
                        rx = st.text_input("Menor RX (dBm) *", placeholder="-18.67", key=f"rx_{row['id']}")
                    
                    obs = st.text_area("Observações", key=f"obs_{row['id']}", height=80)
                    
                    # Botões
                    col_btn1, col_btn2 = st.columns(2)
                    
                    with col_btn1:
                        aprovado = st.form_submit_button("✅ Viabilizar", type="primary", use_container_width=True)
                   # with col_btn2:
                       # utp = st.form_submit_button("📡 Atendemos UTP", use_container_width=True)
                    with col_btn2:
                        rejeitado = st.form_submit_button("❌ Sem Viabilidade", type="secondary", use_container_width=True)
                    
                    if aprovado:
                        if not cto or not cto.strip():
                            st.error("❌ Preencha o N° da Caixa (CTO)!")
                        elif not distancia or not distancia.strip():
                            st.error("❌ Preencha a Distância!")
                        elif not localizacao or not localizacao.strip():
                            st.error("❌ Preencha a Localização da Caixa!")
                        elif portas <= 0:
                            st.error("❌ Preencha as Portas Disponíveis!")
                        elif not rx or not rx.strip():
                            st.error("❌ Preencha o Menor RX!")
                        else:
                            dados = {
                                'cto_numero': cto.strip(),
                                'portas_disponiveis': portas,
                                'menor_rx': rx.strip(),
                                'distancia_cliente': distancia.strip(),
                                'localizacao_caixa': localizacao.strip(),
                                'observacoes': obs
                            }
                            if update_viability_ftth(row['id'], 'aprovado', dados):
                                st.success("✅ Viabilização aprovada!")
                                st.rerun()
                    
                    if rejeitado:
                        dados = {'motivo_rejeicao': 'Não temos projeto neste ponto'}
                        if update_viability_ftth(row['id'], 'rejeitado', dados):
                            st.success("❌ Solicitação rejeitada")
                            st.rerun()
                    
                    #if utp:
                      #  dados = {'motivo_rejeicao': 'Atendemos UTP'}
                      #  if update_viability_ftth(row['id'], 'utp', dados):
                       #     st.success("📡 Marcado como Atendemos UTP")
                        #    st.rerun()
            
            else:  # Prédio (FTTA ou UTP a definir)
                # Verificar se já foi solicitada viabilização de prédio
                status_predio = row.get('status_predio')
                
                # Se ainda não foi solicitado OU se foi rejeitado, mostrar formulário normal
                if status_predio is None or status_predio == 'rejeitado':
                    st.markdown("#### 🏢 Dados do Prédio")
                    
                    with st.form(key=f"form_ftta_{row['id']}"):
                        predio = st.text_input("Prédio FTTA", value=row.get('predio_ftta', ''), key=f"predio_{row['id']}")
                        
                        col_f1, col_f2 = st.columns(2)
                        with col_f1:
                            portas = st.number_input("Portas Disponíveis", min_value=0, max_value=50, value=0, key=f"portas_ftta_{row['id']}")
                        with col_f2:
                            media_rx = st.text_input("Média RX (dBm)", placeholder="-20.5", key=f"media_rx_{row['id']}")
                        
                        obs = st.text_area("Observações", key=f"obs_ftta_{row['id']}", height=80)
                        
                        # Botões
                        col_btn1, col_btn2, col_btn3 = st.columns(3)
                        
                        with col_btn1:
                            aprovado = st.form_submit_button("✅ Viabilizar", type="primary", use_container_width=True)
                        with col_btn2:
                            utp = st.form_submit_button("📡 Atendemos UTP", use_container_width=True)                    
                        with col_btn3:
                            rejeitado = st.form_submit_button("❌ Sem Viabilidade", type="secondary", use_container_width=True)
                        
                        if aprovado:
                            if predio and portas > 0 and media_rx:
                                dados = {
                                    'predio_ftta': predio,
                                    'portas_disponiveis': portas,
                                    'media_rx': media_rx,
                                    'observacoes': obs
                                }
                                if update_viability_ftta(row['id'], 'aprovado', dados):
                                    st.success("✅ Viabilização aprovada!")
                                    st.balloons()
                                    st.rerun()
                            else:
                                st.error("❌ Preencha todos os campos obrigatórios!")
                        
                        if rejeitado:
                            # Mostrar formulário para coletar motivo
                            st.session_state[f'show_reject_predio_form_{row["id"]}'] = True
                        
                    if st.session_state.get(f'show_reject_predio_form_{row["id"]}', False):
                        st.markdown("---")
                        st.error("### ❌ Registrar Prédio Sem Viabilidade")
                        
                        with st.form(key=f"form_reject_predio_inicial_{row['id']}"):
                            st.markdown("**Os seguintes dados serão registrados para consulta futura:**")
                            
                            col_rej1, col_rej2 = st.columns(2)
                            with col_rej1:
                                st.text_input("🏢 Condomínio", value=row.get('predio_ftta', ''), disabled=True)
                            with col_rej2:
                                st.text_input("📍 Localização", value=row['plus_code_cliente'], disabled=True)
                            
                            motivo_rejeicao_predio = st.text_area(
                                "📝 Motivo da Não Viabilidade *",
                                placeholder="Descreva o motivo: não temos projeto nesta rua, distância muito grande, etc.",
                                height=100
                            )
                            
                            col_btn_rej1, col_btn_rej2 = st.columns(2)
                            
                            with col_btn_rej1:
                                confirmar_rej_predio = st.form_submit_button(
                                    "✅ Confirmar Rejeição",
                                    type="primary",
                                    use_container_width=True
                                )
                            
                            with col_btn_rej2:
                                cancelar_rej_predio = st.form_submit_button(
                                    "🔙 Cancelar",
                                    use_container_width=True
                                )
                            
                            if confirmar_rej_predio:
                                if not motivo_rejeicao_predio or motivo_rejeicao_predio.strip() == "":
                                    st.error("❌ Descreva o motivo da não viabilidade!")
                                else:
                                    if reject_building_viability(
                                        row['id'],
                                        row.get('predio_ftta', 'Prédio'),
                                        row['plus_code_cliente'],
                                        motivo_rejeicao_predio.strip()
                                    ):
                                        st.success("✅ Prédio registrado como sem viabilidade!")
                                        st.info("📋 Registro salvo para consulta futura")
                                        del st.session_state[f'show_reject_predio_form_{row["id"]}']
                                        st.rerun()
                                    else:
                                        st.error("❌ Erro ao registrar. Tente novamente.")
                            
                            if cancelar_rej_predio:
                                del st.session_state[f'show_reject_predio_form_{row["id"]}']
                                st.rerun()
                                
                        if utp:
                            dados = {'motivo_rejeicao': 'Atendemos UTP'}
                            if update_viability_ftta(row['id'], 'utp', dados):
                                st.success("📡 Marcado como Atendemos UTP")
                                st.rerun()
                    
                    # ===== BOTÃO VIABILIZAR PRÉDIO (apenas se ainda não foi solicitado) =====
                    if status_predio is None:
                        st.markdown("---")
                        st.markdown("#### 🏗️ Viabilização de Estrutura no Prédio")
                        st.info("🔧 Temos projeto na rua, mas não temos estrutura pronta no prédio")
                        
                        col_viab_pred = st.columns([1, 2, 1])[1]
                        with col_viab_pred:
                            if st.button(
                                "🏢 Solicitar Viabilização do Prédio", 
                                type="primary", 
                                use_container_width=True,
                                key=f"viab_predio_{row['id']}"
                            ):
                                if request_building_viability(row['id'], {}):
                                    st.success("✅ Solicitação enviada! Aguardando dados do usuário.")
                                    st.info("👤 O usuário receberá um formulário para preencher.")
                                    st.rerun()
                
                # Se está aguardando dados do usuário
                elif status_predio == 'aguardando_dados':
                    st.markdown("#### 🏗️ Viabilização de Estrutura no Prédio")
                    st.warning("⏳ **Aguardando dados do usuário**")
                    st.caption(f"📅 Solicitado em: {format_time_br_supa(row.get('data_solicitacao_predio', ''))}")
                    st.info("👤 O usuário está preenchendo o formulário com os dados do prédio.")
                
                # Se os dados foram recebidos e está pronto para análise
                elif status_predio == 'pronto_auditoria':
                    st.markdown("#### 🏗️ Viabilização de Estrutura no Prédio")
                    st.success("✅ **Dados recebidos! Pronto para análise**")
                    
                    # Mostrar dados recebidos
                    with st.expander("👁️ Ver Dados do Cliente", expanded=True):
                        col_dados1, col_dados2 = st.columns(2)
                        with col_dados1:
                            st.markdown("**👤 Síndico**")
                            st.text(f"Nome: {row.get('nome_sindico', 'N/A')}")
                            st.text(f"Contato: {row.get('contato_sindico', 'N/A')}")
                        with col_dados2:
                            st.markdown("**🏠 Cliente**")
                            st.text(f"Nome: {row.get('nome_cliente_predio', 'N/A')}")
                            st.text(f"Contato: {row.get('contato_cliente_predio', 'N/A')}")
                        
                        st.text(f"🚪 Apartamento: {row.get('apartamento', 'N/A')}")
                        st.text(f"🏢 Edifício: {row.get('predio_ftta', 'N/A')}")
                        st.text(f"📍 Localização: {row['plus_code_cliente']}")
                        
                        if row.get('obs_agendamento'):
                            st.markdown("**📝 Melhores horários:**")
                            st.info(row['obs_agendamento'])
                    
                    st.markdown("---")
                    st.markdown("### 📅 Agendar Visita Técnica")
                    
                    # Formulário de agendamento
                    col_ag1, col_ag2 = st.columns(2)
                    
                    with col_ag1:
                        data_visita = st.date_input(
                            "📅 Data da Visita",
                            key=f"data_visita_{row['id']}",
                            help="Selecione a data para visita técnica",
                            format="DD/MM/YYYY"
                        )
                    
                    with col_ag2:
                        periodo = st.selectbox(
                            "🕐 Período",
                            options=["Manhã", "Tarde"],
                            key=f"periodo_{row['id']}"
                        )
                        
                    # Segunda linha com Técnico e Tecnologia
                    col_ag3, col_ag4 = st.columns(2)
                    
                    with col_ag3:
                        tecnico = st.text_input(
                            "👷 Técnico Responsável",
                            placeholder="Nome do técnico",
                            key=f"tecnico_{row['id']}"
                        )
                    with col_ag4:
                        tecnologia = st.selectbox(
                            "🔧 Tecnologia",
                            options=["FTTA", "UTP"],
                            key=f"tecnologia_{row['id']}",
                            help="Tipo de tecnologia a ser instalada"
                        )
                    
                    st.markdown("---")
                    
                    # Botões de ação
                    col_action1, col_action2 = st.columns(2)
                    
                    with col_action1:
                        if st.button(
                            "📋 Agendar Visita Técnica",
                            type="primary",
                            use_container_width=True,
                            key=f"agendar_{row['id']}"
                        ):
                            if not tecnico or not data_visita or not tecnologia:
                                st.error("❌ Preencha todos os campos de agendamento!")
                            else:
                                from viability_functions import schedule_building_visit
            
                                if schedule_building_visit(
                                    row['id'],
                                    data_visita,
                                    periodo,
                                    tecnico,
                                    tecnologia
                                ):
                                    st.success("✅ Visita agendada com sucesso!")
                                    st.info("📅 Agendamento registrado na Agenda FTTA/UTP")
                                    st.rerun()
                                else:
                                    st.error("❌ Erro ao agendar. Tente novamente.")
                    
                    with col_action2:
                        if st.button(
                            "❌ Edifício Sem Viabilidade",
                            type="secondary",
                            use_container_width=True,
                            key=f"sem_viab_{row['id']}"
                        ):
                            st.session_state[f'show_reject_form_{row["id"]}'] = True
                    
                    # Formulário de rejeição (aparece ao clicar no botão)
                    if st.session_state.get(f'show_reject_form_{row["id"]}', False):
                        st.markdown("---")
                        st.error("### ❌ Registrar Edifício Sem Viabilidade")
                        
                        with st.form(key=f"form_reject_building_{row['id']}"):
                            st.markdown("**Os seguintes dados serão registrados para consulta futura:**")
                            
                            col_rej1, col_rej2 = st.columns(2)
                            with col_rej1:
                                st.text_input("🏢 Condomínio", value=row.get('predio_ftta', ''), disabled=True)
                            with col_rej2:
                                st.text_input("📍 Localização", value=row['plus_code_cliente'], disabled=True)
                            
                            motivo_rejeicao = st.text_area(
                                "📝 Motivo da Não Viabilidade *",
                                placeholder="Descreva o motivo: estrutura inadequada, recusa do síndico, etc.",
                                height=100
                            )
                            
                            col_btn_rej1, col_btn_rej2 = st.columns(2)
                            
                            with col_btn_rej1:
                                confirmar_rejeicao = st.form_submit_button(
                                    "✅ Confirmar Rejeição",
                                    type="primary",
                                    use_container_width=True
                                )
                            
                            with col_btn_rej2:
                                cancelar = st.form_submit_button(
                                    "🔙 Cancelar",
                                    use_container_width=True
                                )
                            
                            if confirmar_rejeicao:
                                if not motivo_rejeicao or motivo_rejeicao.strip() == "":
                                    st.error("❌ Descreva o motivo da não viabilidade!")
                                else:                                                                        
                                    if reject_building_viability(
                                        row['id'],
                                        row.get('predio_ftta', 'Prédio'),
                                        row['plus_code_cliente'],
                                        motivo_rejeicao.strip()
                                    ):
                                        st.success("✅ Edifício registrado como sem viabilidade!")
                                        st.info("📝 Registro salvo para consulta futura")
                                        del st.session_state[f'show_reject_form_{row["id"]}']
                                        st.rerun()
                                    else:
                                        st.error("❌ Erro ao registrar. Tente novamente.")
                            
                            if cancelar:
                                del st.session_state[f'show_reject_form_{row["id"]}']
                                st.rerun()   
                            
        st.markdown("---")

# ======================
# Buscar Pendências
# ======================
pending = get_pending_viabilities()

# ======================
# Notificação de novas solicitações
# ======================
if "pendentes_anteriores" not in st.session_state:
    st.session_state.pendentes_anteriores = len(pending)

# Se há novas solicitações desde a última atualização
if len(pending) > st.session_state.pendentes_anteriores:
    novas = len(pending) - st.session_state.pendentes_anteriores
    st.toast(f"🔔 {novas} nova(s) solicitação(ões) aguardando auditoria!", icon="📬")
    st.markdown("""
    <audio autoplay>
        <source src="https://actions.google.com/sounds/v1/alarms/beep_short.ogg" type="audio/ogg">
    </audio>
    """, unsafe_allow_html=True)    

# Atualiza contador
st.session_state.pendentes_anteriores = len(pending)

if not pending:
    st.info("✅ Não há solicitações pendentes de auditoria no momento.")
    st.success("👏 Parabéns! Todas as solicitações foram processadas.")
else:
    st.subheader(f"📋 {len(pending)} Solicitações Pendentes")
    st.markdown("---")
    # ======================
    # Separar por tipo e urgência
    # ======================
    urgentes = [p for p in pending if p.get('urgente', False)]
    ftth = [p for p in pending if p['tipo_instalacao'] == 'FTTH' and not p.get('urgente', False)]
    predios = [p for p in pending if p['tipo_instalacao'] == 'Prédio' and not p.get('urgente', False)]
    
    # ======================
    # SISTEMA DE ABAS
    # ======================
    # Criar nomes das abas com contadores
    tab_names = []
    if urgentes:
        tab_names.append(f"🔥 URGENTES ({len(urgentes)})")
    if ftth:
        tab_names.append(f"🏠 FTTH ({len(ftth)})")
    if predios:
        tab_names.append(f"🏢 PRÉDIOS ({len(predios)})")
    
    # Se não houver abas (nenhuma pendência), não mostrar nada
    if not tab_names:
        # Já foi mostrado o st.info antes, não precisa fazer nada
        pass
    else:
        # Criar as abas dinamicamente
        tabs = st.tabs(tab_names)
        
        tab_index = 0
        
        # ABA URGENTES
        if urgentes:
            with tabs[tab_index]:
                st.warning("⚠️ **Clientes Presenciais - Prioridade Máxima**")
                st.caption(f"📊 {len(urgentes)} solicitação(ões) urgente(s)")
                st.markdown("---")
                
                for row in urgentes:
                    show_viability_form(row, urgente=True)
            
            tab_index += 1
        
        # ABA FTTH
        if ftth:
            with tabs[tab_index]:
                st.info("🏠 **Instalações Residenciais (FTTH)**")
                st.caption(f"📊 {len(ftth)} solicitação(ões) de casa")
                st.markdown("---")
                
                for row in ftth:
                    show_viability_form(row, urgente=False)
            
            tab_index += 1
        
        # ABA PRÉDIOS
        if predios:
            with tabs[tab_index]:
                st.info("🏢 **Instalações em Edifícios**")
                st.caption(f"📊 {len(predios)} solicitação(ões) de prédio")
                st.markdown("---")
                
                for row in predios:
                    show_viability_form(row, urgente=False)


# ======================
# Footer
# ======================
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <p>🔍 <strong>Validador de Projetos</strong> | Desenvolvido ByLeo</p>
</div>
""", unsafe_allow_html=True)

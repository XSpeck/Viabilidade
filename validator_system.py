import streamlit as st
import xml.etree.ElementTree as ET
from shapely.geometry import LineString, Point
from openlocationcode import openlocationcode as olc
from geopy.distance import geodesic
import folium
from streamlit_folium import st_folium
import gdown
import pandas as pd
import requests
import logging
from datetime import datetime
import time
from typing import Optional, Tuple, List
import re

# ======================
# Configurações
# ======================
LOCATIONIQ_KEY = "pk.66f355328aaad40fe69b57c293f66815"
file_id_kml = "1tuxvnc-2FHVVjtLHJ34LFpU3Uq5jiVul"
kml_path = "REDE_CLONIX.kml"
reference_lat = -28.6775
reference_lon = -49.3696
file_id_ctos = "1EcKNk2yqHDEMMXJZ17fT0flPV19HDhKJ"
ctos_kml_path = "ctos.kml"

DISTANCE_CONFIGS = {
    "excellent": {"max": 25, "color": "success", "icon": "✅", "message": "Excelente viabilidade"},
    "good": {"max": 100, "color": "success", "icon": "✅", "message": "Boa viabilidade"},
    "moderate": {"max": 300, "color": "warning", "icon": "⚠️", "message": "Viabilidade moderada"},
    "poor": {"max": 500, "color": "warning", "icon": "⚠️", "message": "Viabilidade baixa"},
    "none": {"max": float('inf'), "color": "error", "icon": "❌", "message": "Sem viabilidade"}
}

csv_ids = {
    "utp": "1UTp5gbAqppEhpIIp8qUvF83KARvwKego",
    "sem_viabilidade": "1Xo34rgfWQayl_4mJiPnTYlxWy356SpCK"
}
csv_files = {
    "utp": "utp.csv",
    "sem_viabilidade": "sem_viabilidade.csv"
}

# ======================
# Configuração de Logging
# ======================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ======================
# Estado da Sessão
# ======================
def init_session_state():
    defaults = {
        "refresh_clicked": False,
        "last_update": None,
        "search_history": [],
        "favorite_locations": [],
        "cache_timestamp": None
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# ======================
# Funções Utilitárias
# ======================
def validate_plus_code(plus_code: str) -> bool:
    pattern = r'^[23456789CFGHJMPQRVWX]{4,8}\+[23456789CFGHJMPQRVWX]{2,3}$'
    return bool(re.match(pattern, plus_code.upper().strip()))

def validate_coordinates(lat: float, lon: float) -> bool:
    return -90 <= lat <= 90 and -180 <= lon <= 180

def format_distance(distance_m: float) -> str:
    if distance_m < 1000:
        return f"{distance_m:.1f}m"
    else:
        return f"{distance_m/1000:.2f}km"

def get_distance_category(distance_m: float) -> dict:
    for category, config in DISTANCE_CONFIGS.items():
        if distance_m <= config["max"]:
            return {"category": category, **config}
    return {"category": "none", **DISTANCE_CONFIGS["none"]}

# ======================
# Cache e Download
# ======================
def on_refresh():
    st.cache_data.clear()
    st.session_state.refresh_clicked = True
    st.session_state.last_update = datetime.now()
    logger.info("Cache limpo e arquivos marcados para atualização")

@st.cache_data(ttl=3600)
def download_file(file_id: str, output: str) -> str:
    try:
        url = f"https://drive.google.com/uc?id={file_id}"
        gdown.download(url, output, quiet=True, fuzzy=True)
        logger.info(f"Arquivo {output} baixado com sucesso")
        return output
    except Exception as e:
        logger.error(f"Erro ao baixar {output}: {e}")
        raise Exception(f"Falha no download do arquivo {output}: {str(e)}")

def load_lines_from_kml(path: str) -> List[List[Tuple[float, float]]]:
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
        logger.info(f"Carregadas {len(lines)} linhas do KML")
        return lines
    except Exception as e:
        logger.error(f"Erro ao carregar KML: {e}")
        raise Exception(f"Falha ao carregar arquivo KML: {str(e)}")

@st.cache_data(ttl=3600)
def load_ctos_from_kml(path: str) -> List[dict]:
    try:
        namespaces = {'kml': 'http://www.opengis.net/kml/2.2'}
        tree = ET.parse(path)
        root = tree.getroot()
        ctos = []
        for placemark in root.findall(".//kml:Placemark", namespaces):
            name_elem = placemark.find("kml:name", namespaces)
            desc_elem = placemark.find(".//kml:value", namespaces)
            coords_elem = placemark.find(".//kml:coordinates", namespaces)
            if coords_elem is not None and coords_elem.text:
                parts = coords_elem.text.strip().split(",")
                if len(parts) >= 2:
                    lon, lat = float(parts[0]), float(parts[1])
                    if validate_coordinates(lat, lon):
                        ctos.append({
                            "name": name_elem.text.strip() if name_elem is not None else "CTO",
                            "desc": desc_elem.text.strip() if desc_elem is not None else "",
                            "lat": lat,
                            "lon": lon
                        })
        logger.info(f"Carregados {len(ctos)} CTOs do arquivo KML")
        return ctos
    except Exception as e:
        logger.error(f"Erro ao carregar CTOs: {e}")
        return []

@st.cache_data(ttl=3600)
def load_all_files():
    try:
        download_file(file_id_kml, kml_path)
        download_file(file_id_ctos, ctos_kml_path)
        download_file(csv_ids["utp"], csv_files["utp"])
        download_file(csv_ids["sem_viabilidade"], csv_files["sem_viabilidade"])
        lines = load_lines_from_kml(kml_path)
        lines = [line for line in lines if line and len(line) > 1]
        df_utp = pd.read_csv(csv_files["utp"])
        df_sem = pd.read_csv(csv_files["sem_viabilidade"])
        ctos = load_ctos_from_kml(ctos_kml_path)
        logger.info(f"Arquivos carregados: {len(lines)} linhas, {len(ctos)} CTOs, {len(df_utp)} UTP, {len(df_sem)} sem viabilidade")
        st.session_state.cache_timestamp = datetime.now()
        return lines, ctos, df_utp, df_sem
    except Exception as e:
        logger.error(f"Erro ao carregar arquivos: {e}")
        raise

# ======================
# Funções de Geolocalização
# ======================
def pluscode_to_coords(pluscode: str) -> Tuple[float, float]:
    try:
        pluscode = pluscode.strip().upper()
        if not validate_plus_code(pluscode):
            raise ValueError("Formato de Plus Code inválido")
        if not olc.isFull(pluscode):
            pluscode = olc.recoverNearest(pluscode, reference_lat, reference_lon)
        decoded = olc.decode(pluscode)
        lat = (decoded.latitudeLo + decoded.latitudeHi) / 2
        lon = (decoded.longitudeLo + decoded.longitudeHi) / 2
        if not validate_coordinates(lat, lon):
            raise ValueError("Coordenadas resultantes inválidas")
        return lat, lon
    except Exception as e:
        logger.error(f"Erro ao converter Plus Code {pluscode}: {e}")
        raise Exception(f"Erro ao processar Plus Code: {str(e)}")

def check_proximity(point: Tuple[float, float], lines: List[List[Tuple[float, float]]]) -> Tuple[Optional[float], Optional[int]]:
    if not lines:
        return None, None
    try:
        pt = Point(point[1], point[0])
        closest_distance = float('inf')
        closest_line = None
        for i, line in enumerate(lines):
            if not line or len(line) < 2:
                continue
            try:
                line_coords = [(lon, lat) for lat, lon in line]
                ln = LineString(line_coords)
                if ln.is_empty or not ln.is_valid:
                    continue
                closest_point = ln.interpolate(ln.project(pt))
                if closest_point is None or closest_point.is_empty:
                    continue
                distance = geodesic((point[0], point[1]), (closest_point.y, closest_point.x)).meters
                if distance < closest_distance:
                    closest_distance = distance
                    closest_line = i + 1
            except Exception as line_error:
                logger.warning(f"Erro ao processar linha {i}: {line_error}")
                continue
        if closest_distance == float('inf'):
            return None, None
        return closest_distance, closest_line
    except Exception as e:
        logger.error(f"Erro ao verificar proximidade: {e}")
        return None, None

@st.cache_data(ttl=1800)
def reverse_geocode(lat: float, lon: float) -> str:
    url = f"https://us1.locationiq.com/v1/reverse?key={LOCATIONIQ_KEY}&lat={lat}&lon={lon}&format=json"
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                display_name = data.get("display_name", "Endereço não encontrado")
                return display_name
            elif response.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            else:
                return f"Erro na consulta: HTTP {response.status_code}"
        except requests.RequestException as e:
            if attempt == max_retries - 1:
                return f"Erro na consulta: {str(e)}"
            time.sleep(1)
    return "Erro na consulta após múltiplas tentativas"

def find_nearest_ctos(lat: float, lon: float, ctos: List[dict], max_radius: float = 800.0) -> List[dict]:
    """Retorna as CTOs dentro do raio máximo da coordenada"""
    if not ctos:
        return []
    dists = []
    for cto in ctos:
        dist = geodesic((lat, lon), (cto["lat"], cto["lon"])).meters
        if dist <= max_radius:
            dists.append({**cto, "distance": dist})
    dists.sort(key=lambda x: x["distance"])
    return dists

# ======================
# Interface Streamlit
# ======================
st.set_page_config(
    page_title="Validador de Projetos",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.title("🔍 Validador de Projetos")
st.markdown("---")

with st.sidebar:
    st.header("⚙️ Controles")
    if st.button("🔄 Atualizar Arquivos", help="Limpa o cache e recarrega todos os arquivos"):
        on_refresh()
    if st.session_state.cache_timestamp:
        st.info(f"📅 Última atualização: {st.session_state.cache_timestamp.strftime('%H:%M:%S')}")
    st.markdown("---")
    st.header("📋 Critérios de Viabilidade")
    for category, config in DISTANCE_CONFIGS.items():
        if config["max"] == float('inf'):
            distance_text = "> 500m"
        else:
            distance_text = f"≤ {config['max']}m"
        st.markdown(f"{config['icon']} **{config['message']}**: {distance_text}")

if st.session_state.refresh_clicked:
    st.success("✅ Arquivos atualizados com sucesso!")
    st.session_state.refresh_clicked = False

try:
    with st.spinner("Carregando arquivos..."):
        lines, ctos, df_utp, df_sem = load_all_files()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("🗺️ Linhas de Rede", len(lines))
    with col2:
        st.metric("📡 UTPs/FTTAs Atendidas", len(df_utp))
    with col3:
        st.metric("🏢 Prédios sem Viabilidade", len(df_sem))
except Exception as e:
    st.error(f"❌ Erro ao carregar arquivos: {e}")
    st.stop()

st.markdown("---")
st.subheader("📍 Validação de Localização")

plus_code_input = st.text_input(
    "Digite o Plus Code",
    placeholder="Ex: 8JV4+8XR ou 589G8JV4+8XR",
    help="Plus Code é um sistema de endereçamento baseado em coordenadas do Google"
).strip().upper()

if plus_code_input:
    if not validate_plus_code(plus_code_input):
        st.error("❌ Formato de Plus Code inválido. Use o formato correto (ex: 8JV4+8XR)")
    else:
        try:
            lat, lon = pluscode_to_coords(plus_code_input)
            col1, col2 = st.columns([2, 1])

            with col1:
                st.markdown("### 📍 Informações da Localização")
                coords_str = f"{lat:.6f}, {lon:.6f}"
                st.caption("Coordenadas (copiar)")
                st.code(coords_str, language="text")

                maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
                st.markdown(
                    f'''
                    <a href="{maps_url}" target="_blank" 
                       style="display:inline-block;padding:0.75em 1.5em;background: linear-gradient(45deg, #4285F4, #34A853);
                              color:white;text-decoration:none;border-radius:8px;margin:10px 0;
                              box-shadow: 0 2px 4px rgba(0,0,0,0.2);font-weight:bold;">
                        🗺️ Abrir no Google Maps
                    </a>
                    ''',
                    unsafe_allow_html=True
                )

                nearest_ctos = find_nearest_ctos(lat, lon, ctos, max_radius=800.0)
                st.markdown("### 🛠 CTOs mais próximas")
                if nearest_ctos:
                    for cto in nearest_ctos[:3]:
                        st.success(
                            f'**{cto["name"]}**\n'
                            f'- Coordenadas: `{cto["lat"]:.6f}, {cto["lon"]:.6f}`\n'
                            f'- Distância em Linha reta: {format_distance(cto["distance"])}'
                        )
                else:
                    st.warning("Nenhuma CTO encontrada próxima.")

                with st.spinner("Buscando endereço..."):
                    endereco = reverse_geocode(lat, lon)
                    endereco_simples = ", ".join(endereco.split(",")[:3])
                st.info(f"🏠 **Endereço aproximado:** {endereco_simples}")

            with col2:
                st.markdown("### 🎯 Análise de Viabilidade")
                with st.spinner("Calculando distância..."):
                    dist_m, line_num = check_proximity((lat, lon), lines)
                if dist_m is not None:
                    category_info = get_distance_category(dist_m)
                    distance_formatted = format_distance(dist_m)
                    if category_info["color"] == "success":
                        st.success(f"{category_info['icon']} **{category_info['message']}**")
                    elif category_info["color"] == "warning":
                        st.warning(f"{category_info['icon']} **{category_info['message']}**")
                    else:
                        st.error(f"{category_info['icon']} **{category_info['message']}**")
                    st.metric("📏 Distância", distance_formatted)
                else:
                    st.error("❌ Não foi possível calcular a distância")

            st.markdown("### 🗺️ Visualização no Mapa")
            if dist_m is not None and dist_m <= 100:
                zoom_level = 18
            elif dist_m is not None and dist_m <= 500:
                zoom_level = 16
            else:
                zoom_level = 15

            m = folium.Map(
                location=[lat, lon],
                zoom_start=zoom_level,
                tiles='OpenStreetMap'
            )

            for i, line in enumerate(lines):
                folium.PolyLine(
                    locations=line,
                    color="blue",
                    weight=3,
                    opacity=0.7,
                    popup=f"Linha #{i+1}"
                ).add_to(m)

            marker_color = "green" if dist_m and dist_m <= 100 else "orange" if dist_m and dist_m <= 500 else "red"
            folium.Marker(
                location=[lat, lon],
                popup=f"📍 {plus_code_input}<br>📏 {format_distance(dist_m) if dist_m else 'N/A'}",
                tooltip=f"Plus Code: {plus_code_input}",
                icon=folium.Icon(color=marker_color, icon="info-sign")
            ).add_to(m)

            if nearest_ctos:
                for cto in nearest_ctos:
                    folium.Marker(
                        location=[cto["lat"], cto["lon"]],
                        popup=f'CTO: {cto["name"]}<br>Distância: {format_distance(cto["distance"])}',
                        tooltip=f'CTO: {cto["name"]}',
                        icon=folium.Icon(color="blue", icon="cloud")
                    ).add_to(m)

            if dist_m is not None:
                folium.Circle(
                    location=[lat, lon],
                    radius=max(25, min(dist_m, 500)),
                    color="red",
                    weight=2,
                    fillColor="red",
                    fillOpacity=0.1,
                    popup=f"Raio: {max(25, min(dist_m, 500)):.0f}m"
                ).add_to(m)

            st_folium(m, width=700, height=400)

            search_entry = {
                "plus_code": plus_code_input,
                "coordinates": coords_str,
                "distance": dist_m,
                "timestamp": datetime.now()
            }
            if search_entry not in st.session_state.search_history:
                st.session_state.search_history.insert(0, search_entry)
                st.session_state.search_history = st.session_state.search_history[:10]
        except Exception as e:
            st.error(f"❌ Erro ao processar localização: {e}")
            logger.error(f"Erro no processamento: {e}")

st.markdown("---")
col1, col2 = st.columns(2)

with col1:
    st.subheader("📡 UTPs/FTTAs Atendidas")
    search_utp = st.text_input("🔍 Buscar UTP/FTTA", key="search_utp", placeholder="Digite para filtrar...")
    if search_utp:
        try:
            mask = df_utp.astype(str).apply(lambda x: x.str.lower().str.contains(search_utp.lower(), na=False)).any(axis=1)
            filtered_df = df_utp[mask]
            st.dataframe(filtered_df, use_container_width=True, height=300)
            st.caption(f"Mostrando {len(filtered_df)} de {len(df_utp)} registros")
        except Exception as e:
            st.warning(f"Erro ao filtrar UTP: {e}")
            st.dataframe(df_utp, use_container_width=True, height=300)
    else:
        st.dataframe(df_utp, use_container_width=True, height=300)

with col2:
    st.subheader("🏢 Prédios sem Viabilidade")
    search_sem = st.text_input("🔍 Buscar Prédios", key="search_sem_viab", placeholder="Digite para filtrar...")
    if search_sem:
        try:
            mask = df_sem.astype(str).apply(lambda x: x.str.lower().str.contains(search_sem.lower(), na=False)).any(axis=1)
            filtered_df = df_sem[mask]
            st.dataframe(filtered_df, use_container_width=True, height=300)
            st.caption(f"Mostrando {len(filtered_df)} de {len(df_sem)} registros")
        except Exception as e:
            st.warning(f"Erro ao filtrar prédios: {e}")
            st.dataframe(df_sem, use_container_width=True, height=300)
    else:
        st.dataframe(df_sem, use_container_width=True, height=300)

if st.session_state.search_history:
    st.markdown("---")
    st.subheader("📚 Histórico de Pesquisas")
    for i, entry in enumerate(st.session_state.search_history[:5]):
        with st.expander(f"🕒 {entry['plus_code']} - {entry['timestamp'].strftime('%H:%M:%S')}"):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.text(f"Plus Code: {entry['plus_code']}")
            with col2:
                st.text(f"Coordenadas: {entry['coordinates']}")
            with col3:
                distance_text = format_distance(entry['distance']) if entry['distance'] else "N/A"
                st.text(f"Distância em linha: {distance_text}")

st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666; padding: 20px;'>
        <p>🔍 <strong>Validador de Projetos</strong> | Desenvolvido ByLeo</p>
        <p>📊 Dados atualizados | 🗺️ Integração com Google Maps e LocationIQ</p>
    </div>
    """,
    unsafe_allow_html=True
)

import streamlit as st
import xml.etree.ElementTree as ET
from shapely.geometry import LineString, Point
from openlocationcode import openlocationcode as olc
from geopy.distance import geodesic
import folium
from streamlit_folium import st_folium
from login_system import require_authentication
import gdown
import pandas as pd
import requests
import logging
from datetime import datetime
import time
from typing import Optional, Tuple, List, Dict
import re
from login_system import require_authentication
from viability_system import show_viability_system, create_viability_request
import supabase_config

# ======================
# Configurações
# ======================
LOCATIONIQ_KEY = "pk.66f355328aaad40fe69b57c293f66815"
reference_lat = -28.6775
reference_lon = -49.3696
file_id_ctos = "1EcKNk2yqHDEMMXJZ17fT0flPV19HDhKJ"
ctos_kml_path = "ctos.kml"

# Configuração dos arquivos KML com suas respectivas cores e IDs
KML_CONFIGS = {
    "COOPER-COCAL": {
        "file_id": "1XD-GgwgFgB2RcKkBAxf5RSBWu2yfIf2w",
        "color": "#FF1493",  # Vermelho
        "path": "cooper_cocal.kml"
    },
    "COOPERA": {
        "file_id": "1E5tKI5brZMo1rcrJANXggYegV1IrCdnv",
        "color": "#00FF00",  # Verde
        "path": "coopera.kml"
    },
    "COPERALIANCA": {
        "file_id": "1cDZwFpCDygrmZvP2_oSZoXT3oKXKT8Bh",
        "color": "#0000FF",  # Azul
        "path": "coperalianca.kml"
    },
    "CERMOFUL": {
        "file_id": "1r4gnRFaNUmAZ6f9oTdR1x9RcfksWTXDx",
        "color": "#FF8C00",  # Laranja escuro
        "path": "cermoful.kml"
    },
    "CERTREL": {
        "file_id": "1ZGczns-MIV897jQ8HRhH6LFgMRMdydm4",
        "color": "#8A2BE2",  # Azul violeta
        "path": "certrel.kml"
    },
    "FORÇALUZ": {
        "file_id": "1CHAWKnha0C1f44uLJYXUOj0UcrtnlPKK",
        "color": "#FFD700",  # Dourado
        "path": "forcaluz.kml"
    },
    "CELESC": {
        "file_id": "1M5P4_THpr1qxcxhPVOyQCdGTE5_7faRB",
        "color": "#FF0000",  # Rosa profundo
        "path": "celesc.kml"
    }
}

# Configurações de distância padrão
DISTANCE_CONFIGS = {
    "excellent": {"max": 25, "color": "success", "icon": "✅", "message": "Excelente viabilidade"},
    "good": {"max": 100, "color": "success", "icon": "✅", "message": "Boa viabilidade"},
    "moderate": {"max": 300, "color": "warning", "icon": "⚠️", "message": "Viabilidade moderada"},
    "poor": {"max": 500, "color": "warning", "icon": "⚠️", "message": "Viabilidade baixa"},
    "none": {"max": float('inf'), "color": "error", "icon": "❌", "message": "Sem viabilidade"}
}

# Configurações específicas para CELESC (limites menores)
CELESC_DISTANCE_CONFIGS = {
    "excellent": {"max": 5, "color": "success", "icon": "✅", "message": "Excelente viabilidade (CELESC)"},
    "good": {"max": 10, "color": "success", "icon": "✅", "message": "Boa viabilidade (CELESC)"},
    "moderate": {"max": 25, "color": "warning", "icon": "⚠️", "message": "Viabilidade moderada (CELESC)"},
    "poor": {"max": 50, "color": "warning", "icon": "⚠️", "message": "Viabilidade baixa (CELESC)"},
    "none": {"max": float('inf'), "color": "error", "icon": "❌", "message": "Sem viabilidade (CELESC)"}
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

def coords_to_pluscode(lat, lon):
    return olc.encode(lat, lon)

def validate_coordinates(lat: float, lon: float) -> bool:
    return -90 <= lat <= 90 and -180 <= lon <= 180

def format_distance(distance_m: float) -> str:
    if distance_m < 1000:
        return f"{distance_m:.1f}m"
    else:
        return f"{distance_m/1000:.2f}km"

def get_distance_category(distance_m: float, is_celesc: bool = False) -> dict:
    configs = CELESC_DISTANCE_CONFIGS if is_celesc else DISTANCE_CONFIGS
    for category, config in configs.items():
        if distance_m <= config["max"]:
            return {"category": category, **config}
    return {"category": "none", **configs["none"]}

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
        logger.info(f"Carregadas {len(lines)} linhas do KML {path}")
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
        # Baixar arquivos CSV
        download_file(csv_ids["utp"], csv_files["utp"])
        download_file(csv_ids["sem_viabilidade"], csv_files["sem_viabilidade"])
        
        # Baixar arquivo de CTOs
        download_file(file_id_ctos, ctos_kml_path)
        
        # Baixar e carregar todos os arquivos KML
        all_lines = {}
        total_lines = 0
        
        for company, config in KML_CONFIGS.items():
            try:
                download_file(config["file_id"], config["path"])
                lines = load_lines_from_kml(config["path"])
                lines = [line for line in lines if line and len(line) > 1]
                all_lines[company] = {
                    "lines": lines,
                    "color": config["color"],
                    "count": len(lines)
                }
                total_lines += len(lines)
                logger.info(f"Carregadas {len(lines)} linhas para {company}")
            except Exception as e:
                logger.error(f"Erro ao carregar {company}: {e}")
                all_lines[company] = {"lines": [], "color": config["color"], "count": 0}
        
        # Carregar outros dados
        df_utp = pd.read_csv(csv_files["utp"])
        df_sem = pd.read_csv(csv_files["sem_viabilidade"])
        ctos = load_ctos_from_kml(ctos_kml_path)
        
        logger.info(f"Total: {total_lines} linhas de {len(KML_CONFIGS)} empresas, {len(ctos)} CTOs, {len(df_utp)} UTP, {len(df_sem)} sem viabilidade")
        st.session_state.cache_timestamp = datetime.now()
        return all_lines, ctos, df_utp, df_sem
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

def check_proximity_all_companies(point: Tuple[float, float], all_lines: Dict) -> Dict:
    """Verifica proximidade para todas as empresas e retorna a mais próxima"""
    if not all_lines:
        return {"distance": None, "company": None, "line": None, "is_celesc": False}
    
    try:
        pt = Point(point[1], point[0])
        closest_distance = float('inf')
        closest_company = None
        closest_line = None
        
        for company, data in all_lines.items():
            lines = data["lines"]
            if not lines:
                continue
                
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
                        closest_company = company
                        closest_line = i + 1
                except Exception as line_error:
                    logger.warning(f"Erro ao processar linha {i} da empresa {company}: {line_error}")
                    continue
        
        if closest_distance == float('inf'):
            return {"distance": None, "company": None, "line": None, "is_celesc": False}
        
        return {
            "distance": closest_distance,
            "company": closest_company,
            "line": closest_line,
            "is_celesc": closest_company == "CELESC"
        }
    except Exception as e:
        logger.error(f"Erro ao verificar proximidade: {e}")
        return {"distance": None, "company": None, "line": None, "is_celesc": False}

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

def find_nearest_ctos(lat: float, lon: float, ctos: List[dict], max_radius: float = 400.0) -> List[dict]:
    """Retorna as CTOs dentro do raio máximo da coordenada, excluindo CTOs CDOI"""
    if not ctos:
        return []
    dists = []
    for cto in ctos:
        # Ignorar CTOs que começam com CDOI
        if cto["name"].upper().startswith("CDOI"):
            continue
        dist = geodesic((lat, lon), (cto["lat"], cto["lon"])).meters
        if dist <= max_radius:
            dists.append({**cto, "distance": dist})
    dists.sort(key=lambda x: x["distance"])
    return dists

@st.cache_data(ttl=3600)
def get_walking_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float) -> Optional[Dict]:
    """
    Calcula a rota real a pé usando OSRM (Open Source Routing Machine)
    API pública e 100% gratuita - sem necessidade de API key
    Retorna distância e duração estimada
    """
    try:
        # OSRM API público - perfil "foot" para pedestres
        url = f"http://router.project-osrm.org/route/v1/foot/{start_lon},{start_lat};{end_lon},{end_lat}"
        params = {
            "overview": "full",
            "geometries": "geojson",
            "steps": "false"
        }
        
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == "Ok" and data.get("routes") and len(data["routes"]) > 0:
                route = data["routes"][0]
                return {
                    "distance": route["distance"],  # em metros
                    "duration": route["duration"],  # em segundos
                    "geometry": route["geometry"]   # GeoJSON da rota
                }
            else:
                logger.warning(f"OSRM: Nenhuma rota encontrada - {data.get('code', 'unknown')}")
                return None
        else:
            logger.warning(f"OSRM API retornou status {response.status_code}")
            return None
            
    except requests.Timeout:
        logger.error("OSRM: Timeout na requisição (servidor público pode estar lento)")
        return None
    except requests.RequestException as e:
        logger.error(f"Erro ao consultar OSRM API: {e}")
        return None
    except Exception as e:
        logger.error(f"Erro inesperado na rota: {e}")
        return None

def format_duration(seconds: float) -> str:
    """Formata duração em segundos para formato legível"""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes}min"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        return f"{hours}h {minutes}min"

# ======================
# Interface Streamlit
# ======================
st.set_page_config(
    page_title="Validador de Projetos",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

if not require_authentication():
       st.stop()    
    
st.title("🔍 Validador de Projetos")

with st.sidebar:
    st.header("⚙️ Controles")
    if st.button("🔄 Atualizar Arquivos", help="Limpa o cache e recarrega todos os arquivos"):
        on_refresh()
    if st.session_state.cache_timestamp:
        st.info(f"📅 Última atualização: {st.session_state.cache_timestamp.strftime('%H:%M:%S')}")
    st.markdown("---")
    st.header("📋 Critérios de Viabilidade Padrão")
    for category, config in DISTANCE_CONFIGS.items():
        if config["max"] == float('inf'):
            distance_text = "> 500m"
        else:
            distance_text = f"≤ {config['max']}m"
        st.markdown(f"{config['icon']} **{config['message']}**: {distance_text}")
    
    st.markdown("---")
    st.header("⚡ Critérios CELESC (Especiais)")
    for category, config in CELESC_DISTANCE_CONFIGS.items():
        if config["max"] == float('inf'):
            distance_text = "> 50m"
        else:
            distance_text = f"≤ {config['max']}m"
        st.markdown(f"{config['icon']} **{config['message']}**: {distance_text}")

if st.session_state.refresh_clicked:
    st.success("✅ Arquivos atualizados com sucesso!")
    st.session_state.refresh_clicked = False

try:
    with st.spinner("Carregando arquivos de todas as empresas..."):
        all_lines, ctos, df_utp, df_sem = load_all_files()
        
except Exception as e:
    st.error(f"❌ Erro ao carregar arquivos: {e}")
    st.stop()

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

            # Verificar proximidade com todas as empresas
            proximity_result = check_proximity_all_companies((lat, lon), all_lines)
            
            # Buscar CTOs em um raio maior inicialmente
            candidate_ctos = find_nearest_ctos(lat, lon, ctos, max_radius=3500.0)
            
            # Calcular rotas reais para as CTOs candidatas
            cto_routes = []
            if candidate_ctos:
                with st.spinner("🗺️ Calculando rotas reais para CTOs..."):
                    for cto in candidate_ctos[:10]:  # Calcular para até 10 CTOs
                        route = get_walking_route(lat, lon, cto["lat"], cto["lon"])                      
            
                        if route:  # Só adicionar se conseguiu calcular a rota
                            linha_reta = geodesic((lat, lon), (cto["lat"], cto["lon"])).meters
                            if route["distance"] > linha_reta * 5:  # Se OSRM > 5x a linha reta
                                route["distance"] = linha_reta
                                
                            cto_routes.append({
                                "cto": cto,
                                "route": route,
                                "distance": route["distance"]  # Distância real
                            })
                        else:
                            # Se não conseguiu calcular rota, usar distância em linha reta como fallback
                            cto_routes.append({
                                "cto": cto,
                                "route": None,
                                "distance": cto["distance"]  # Distância em linha reta
                            })
                    
                    # Ordenar pela distância REAL (da rota)
                    cto_routes.sort(key=lambda x: x["distance"])
                    
                    # Pegar apenas as 3 mais próximas pela rota real
                    cto_routes_all = cto_routes  # Todas (até 10)
                    cto_routes = cto_routes[:3]   # Apenas 3 para o card
                    
            
            # Definir a CTO mais próxima e sua rota
            closest_cto = None
            walking_route_cto = None
            nearest_ctos = []
            
            if cto_routes:
                closest_cto = cto_routes[0]["cto"]
                walking_route_cto = cto_routes[0]["route"]
                nearest_ctos = [item["cto"] for item in cto_routes]

            with col1:
                st.markdown("### 📍 Informações da Localização")
                coords_str = f"{lat:.6f}, {lon:.6f}"
                st.caption("Coordenadas (copiar)")
                st.code(coords_str, language="text")
                maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
                with st.spinner("Buscando endereço..."):
                    endereco = reverse_geocode(lat, lon)
                    endereco_simples = ", ".join(endereco.split(",")[:3])
                st.info(f"🏠 **Endereço aproximado:** {endereco_simples}")
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
                with col1:
                    st.markdown("### 🎯 Análise de Viabilidade")
                    if proximity_result["distance"] is not None:
                        dist_m = proximity_result["distance"]
                        company = proximity_result["company"]
                        is_celesc = proximity_result["is_celesc"]
                        
                        # Mostrar informações da empresa mais próxima
                        if company:
                            company_color = all_lines[company]["color"]
                            st.markdown(f'💡 Postes da <span style="color:{company_color}; font-weight:bold;">{company}</span>', unsafe_allow_html=True)
                        
                        category_info = get_distance_category(dist_m, is_celesc)
                        
                        if category_info["color"] == "success":
                            st.success(f"{category_info['icon']} **{category_info['message']}**")
                        elif category_info["color"] == "warning":
                            st.warning(f"{category_info['icon']} **{category_info['message']}**")
                        else:
                            st.error(f"{category_info['icon']} **{category_info['message']}**")
                        
                        # Mostrar rota até CTO mais próxima
                        if walking_route_cto and closest_cto:
                          
                            route_distance = walking_route_cto["distance"]  # distância real em metros
                            route_distance_sobra_val = route_distance + 50  # soma 50 metros
                            route_distance_sobra = format_distance(route_distance_sobra_val)
                            route_distance_fmt = format_distance(route_distance)
                            route_duration = format_duration(walking_route_cto["duration"])
                            
                            
                            st.markdown(f"### 🎯 CTO Mais Próxima: **{closest_cto['name']}**")
                            
                            col_route1, col_route2 = st.columns(2)
                            with col_route1:
                                st.metric("🚶 Distância real (a pé)", route_distance_fmt)
                            with col_route2:
                                st.metric("🏃‍♂️ Distância com sobra (+50m)", route_distance_sobra)

                            # ===== ADICIONAR AQUI O BOTÃO VIABILIZAR =====
                            
                            # ===== FIM DO BOTÃO =====                            
                                                        
                            st.info("🗺️ Rota calculada usando OSRM (Open Source) - considera ruas e calçadas")
                        elif nearest_ctos:
                            st.caption("⏳ Não foi possível calcular rota (servidor OSRM pode estar lento)")
                        
                        if is_celesc:
                            st.info("⚡ Aplicados critérios especiais da CELESC (limites menores)")
                    else:
                        st.error("❌ Não foi possível calcular a distância")
                # MAPA com todas as empresas
                st.markdown("### 🗺️ Visualização no Mapa")
                dist_m = proximity_result["distance"]
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

                # Adicionar linhas de todas as empresas com cores diferentes
                for company, data in all_lines.items():
                    lines = data["lines"]
                    color = data["color"]
                    for i, line in enumerate(lines):
                        folium.PolyLine(
                            locations=line,
                            color=color,
                            weight=3,
                            opacity=0.8,
                            popup=f"{company} - Linha #{i+1}",
                            tooltip=f"{company}"
                        ).add_to(m)

                # Marker para o ponto pesquisado
                marker_color = "green" if dist_m and dist_m <= 100 else "orange" if dist_m and dist_m <= 500 else "red"
                popup_text = f"📍 {plus_code_input}<br>📏 {format_distance(dist_m) if dist_m else 'N/A'}"
                if proximity_result["company"]:
                    popup_text += f"<br>🏢 {proximity_result['company']}"
                
                folium.Marker(
                    location=[lat, lon],
                    popup=popup_text,
                    tooltip=f"Plus Code: {plus_code_input}",
                    icon=folium.Icon(color=marker_color, icon="info-sign")
                ).add_to(m)

                # Adicionar CTOs
              #  if nearest_ctos:
               #     for cto in nearest_ctos:
                if cto_routes_all:
                    for item in cto_routes_all:
                        cto = item["cto"]
                        folium.Marker(
                            location=[cto["lat"], cto["lon"]],
                            popup=f'CTO: {cto["name"]}<br>Distância: {format_distance(cto["distance"])}',
                            tooltip=f'CTO: {cto["name"]}',
                            icon=folium.Icon(color="blue", icon="cloud")
                        ).add_to(m)

                # Desenhar rota real a pé até a CTO mais próxima
                if walking_route_cto and walking_route_cto.get("geometry") and closest_cto:
                    try:
                        coords = walking_route_cto["geometry"]["coordinates"]
                        route_points = [[coord[1], coord[0]] for coord in coords]
                        
                        folium.PolyLine(
                            locations=route_points,
                            color="#000000",
                            weight=5,
                            opacity=0.9,
                            popup=f"🚶 Rota até {closest_cto['name']}: {format_distance(walking_route_cto['distance'])} - {format_duration(walking_route_cto['duration'])}",
                            tooltip=f"Rota até CTO: {closest_cto['name']}",
                            dash_array="10, 5"
                        ).add_to(m)
                        
                        # Destacar a CTO mais próxima com cor diferente
                        folium.Marker(
                            location=[closest_cto["lat"], closest_cto["lon"]],
                            popup=f"🎯 CTO MAIS PRÓXIMA<br>{closest_cto['name']}<br>Distância: {format_distance(walking_route_cto['distance'])}<br>Tempo: {format_duration(walking_route_cto['duration'])}",
                            tooltip=f"🎯 CTO Mais Próxima: {closest_cto['name']}",
                            icon=folium.Icon(color="red", icon="star")
                        ).add_to(m)
                    except Exception as e:
                        logger.error(f"Erro ao desenhar rota no mapa: {e}")

                # Círculo de proximidade
                if dist_m is not None:
                    max_radius = 250 if proximity_result["is_celesc"] else 500
                    circle_radius = max(25, min(dist_m, max_radius))
                    folium.Circle(
                        location=[lat, lon],
                        radius=circle_radius,
                        color="red",
                        weight=2,
                        fillColor="red",
                        fillOpacity=0.1,
                        popup=f"Raio: {circle_radius:.0f}m"
                    ).add_to(m)

                st.markdown("<div style='display: flex; justify-content: center;'>", unsafe_allow_html=True)
                st_folium(m, width=None, height=600, key=f"map_{plus_code_input}", returned_objects=[])
                st.markdown("</div>", unsafe_allow_html=True)

                # Lista de CTOs próximas com distância real
                st.markdown("### 🛠 CTOs mais próximas (com distância real)")
                if cto_routes:
                    for idx, item in enumerate(cto_routes):
                        cto = item["cto"]
                        route = item["route"]
                        pluscode_cto = coords_to_pluscode(cto["lat"], cto["lon"])
                        
                        # Definir ícone e cor baseado na posição
                        if idx == 0:
                            icon = "🥇"
                            style = "background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px; border-radius: 10px; margin-bottom: 10px;"
                        elif idx == 1:
                            icon = "🥈"
                            style = "background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; padding: 15px; border-radius: 10px; margin-bottom: 10px;"
                        else:
                            icon = "🥉"
                            style = "background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; padding: 15px; border-radius: 10px; margin-bottom: 10px;"
                        
                        if route:

                            dist_real = route["distance"]  # em metros
                            dist_com_sobra = dist_real + 50  # soma 50 metros
                            dist_sobra_fmt = format_distance(dist_com_sobra)
                            
                            st.markdown(f"""
                            <div style="{style}">
                                <h4>{icon} CTO: {cto["name"]}</h4>
                                <p>📍 Coordenadas: <code>{cto["lat"]:.6f}, {cto["lon"]:.6f}</code></p>
                                <p>🔢 Plus Code: <code>{pluscode_cto}</code></p>
                                <p>🚶 <strong>Distância real (a pé): {format_distance(route["distance"])}</strong></p>
                                <p>🏃‍♂️ <strong>Distância com sobra (+50 m): {dist_sobra_fmt}</strong></p>
                                
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.markdown(f"""
                            <div style="{style}">
                                <h4>{icon} CTO: {cto["name"]}</h4>
                                <p>📍 Coordenadas: <code>{cto["lat"]:.6f}, {cto["lon"]:.6f}</code></p>
                                <p>🔢 Plus Code: <code>{pluscode_cto}</code></p>
                                <p>📏 Distância em linha reta: {format_distance(cto["distance"])}</p>
                                <p>⚠️ <em>Não foi possível calcular rota real</em></p>
                            </div>
                            """, unsafe_allow_html=True)
                else:
                    st.warning("Nenhuma CTO encontrada próxima.")

            

            search_entry = {
                "plus_code": plus_code_input,
                "coordinates": coords_str,
                "distance": proximity_result["distance"],
                "company": proximity_result["company"],
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
    search_utp = st.text_input("🔎 Buscar UTP/FTTA", key="search_utp", placeholder="Digite para filtrar...")
    if search_utp:
        try:
            mask = df_utp.astype(str).apply(lambda x: x.str.lower().str.contains(search_utp.lower(), na=False)).any(axis=1)
            filtered_df = df_utp[mask]
            st.dataframe(filtered_df, width='stretch', height=300)
            st.caption(f"Mostrando {len(filtered_df)} de {len(df_utp)} registros")
        except Exception as e:
            st.warning(f"Erro ao filtrar UTP: {e}")
            st.dataframe(df_utp, width='stretch', height=300)
    else:
        st.dataframe(df_utp, width='stretch', height=300)

with col2:
    st.subheader("🏢 Prédios sem Viabilidade")
    search_sem = st.text_input("🔎 Buscar Prédios", key="search_sem_viab", placeholder="Digite para filtrar...")
    if search_sem:
        try:
            mask = df_sem.astype(str).apply(lambda x: x.str.lower().str.contains(search_sem.lower(), na=False)).any(axis=1)
            filtered_df = df_sem[mask]
            st.dataframe(filtered_df, width='stretch', height=300)
            st.caption(f"Mostrando {len(filtered_df)} de {len(df_sem)} registros")
        except Exception as e:
            st.warning(f"Erro ao filtrar prédios: {e}")
            st.dataframe(df_sem, width='stretch', height=300)
    else:
        st.dataframe(df_sem, width='stretch', height=300)

# Legenda de cores das empresas
st.markdown("---")
st.subheader("🎨 Legenda de Cores das Empresas")
cols = st.columns(len(KML_CONFIGS))
for i, (company, config) in enumerate(KML_CONFIGS.items()):
    with cols[i % len(cols)]:
        color_box = f'<div style="background-color:{config["color"]}; width:100%; height:30px; border-radius:5px; display:flex; align-items:center; justify-content:center; color:white; font-weight:bold; text-shadow:1px 1px 2px rgba(0,0,0,0.7);">{company}</div>'
        st.markdown(color_box, unsafe_allow_html=True)

if st.session_state.search_history:
    st.markdown("---")
    st.subheader("📚 Histórico de Pesquisas")
    for i, entry in enumerate(st.session_state.search_history[:5]):
        company_info = f" - {entry['company']}" if entry.get('company') else ""
        with st.expander(f"🕐 {entry['plus_code']}{company_info} - {entry['timestamp'].strftime('%H:%M:%S')}"):
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.text(f"Plus Code: {entry['plus_code']}")
            with col2:
                st.text(f"Coordenadas: {entry['coordinates']}")
            with col3:
                distance_text = format_distance(entry['distance']) if entry['distance'] else "N/A"
                st.text(f"Distância: {distance_text}")
            with col4:
                company_text = entry.get('company', 'N/A')
                st.text(f"Empresa: {company_text}")
# ===== ADICIONAR AQUI O SISTEMA DE VIABILIZAÇÃO =====

# ===== FIM DO SISTEMA =====

st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666; padding: 20px;'>
        <p>🔍 <strong>Validador de Projetos</strong> | Desenvolvido ByLeo</p>        
    </div>
    """,
    unsafe_allow_html=True
)

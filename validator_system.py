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
from typing import Optional, Tuple, List, Dict
import re
import supabase_config

# Importar depois para evitar problemas de dependência circular
from viability_functions import (
    get_current_time, 
    TIMEZONE_BR, 
    format_time_br,
    get_ftth_pending_search,
    save_selected_cto,
    update_viability_ftth
)
from login_system import require_authentication

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

# ======================
# Cache e Download
# ======================
def on_refresh():
    st.cache_data.clear()
    st.session_state.refresh_clicked = True
    st.session_state.last_update = get_current_time()
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
        download_file(csv_ids["utp"], csv_files["utp"])
        download_file(csv_ids["sem_viabilidade"], csv_files["sem_viabilidade"])
        download_file(file_id_ctos, ctos_kml_path)
        
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
        
        df_utp = pd.read_csv(csv_files["utp"])
        df_sem = pd.read_csv(csv_files["sem_viabilidade"])
        ctos = load_ctos_from_kml(ctos_kml_path)
        
        logger.info(f"Total: {total_lines} linhas, {len(ctos)} CTOs, {len(df_utp)} UTP, {len(df_sem)} sem viabilidade")
        st.session_state.cache_timestamp = get_current_time()
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
def get_walking_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float) -> Optional[Dict]:
    try:
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
                    "distance": route["distance"],
                    "duration": route["duration"],
                    "geometry": route["geometry"]
                }
            else:
                logger.warning(f"OSRM: Nenhuma rota encontrada")
                return None
        else:
            logger.warning(f"OSRM API retornou status {response.status_code}")
            return None
            
    except requests.Timeout:
        logger.error("OSRM: Timeout na requisição")
        return None
    except requests.RequestException as e:
        logger.error(f"Erro ao consultar OSRM API: {e}")
        return None
    except Exception as e:
        logger.error(f"Erro inesperado na rota: {e}")
        return None

def format_duration(seconds: float) -> str:
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
    page_title="Busca Detalhada - Validador de Projetos",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

if not require_authentication():
    st.stop()

# Verificar se é Admin (nível 1)
if st.session_state.user_nivel != 1:
    st.error("🚫 Acesso Negado! Esta página é restrita a administradores.")
    st.info("👈 Use o menu lateral para navegar.")
    st.stop()

st.title("🔍 Busca Detalhada - Escolha de CTO")

with st.sidebar:
    st.header("⚙️ Controles")
    if st.button("🔄 Atualizar Arquivos", help="Limpa o cache e recarrega todos os arquivos"):
        on_refresh()
    if st.session_state.cache_timestamp:
        st.info(f"📅 Última atualização: {datetime.now(TIMEZONE_BR).strftime('%d/%m/%Y %H:%M')}")

if st.session_state.refresh_clicked:
    st.success("✅ Arquivos atualizados com sucesso!")
    st.session_state.refresh_clicked = False

try:
    with st.spinner("Carregando arquivos..."):
        all_lines, ctos, df_utp, df_sem = load_all_files()
except Exception as e:
    st.error(f"❌ Erro ao carregar arquivos: {e}")
    st.stop()

# ======================
# Buscar Solicitações FTTH Pendentes
# ======================
#from viability_functions import get_ftth_pending_search, save_selected_cto

ftth_pending = get_ftth_pending_search()

if not ftth_pending:
    st.info("✅ Não há solicitações FTTH aguardando busca detalhada.")
    st.markdown("---")
else:
    st.subheader(f"📋 {len(ftth_pending)} Solicitação(ões) FTTH Aguardando Busca")
    st.markdown("---")
    
    for request in ftth_pending:
        plus_code_input = request['plus_code_cliente']
        urgente = request.get('urgente', False)
        
        # Card visual
        border_color = "#FF4444" if urgente else "#667eea"
        bg_color = "#FFF5F5" if urgente else "#F8F9FA"
        
        st.markdown(f"""
        <div style='border-left: 5px solid {border_color}; padding: 15px; 
                    background-color: {bg_color}; border-radius: 5px; margin-bottom: 20px;'>
        </div>
        """, unsafe_allow_html=True)
        
        col_header1, col_header2 = st.columns([5, 1])
        with col_header1:
            titulo = f"### {'🔥' if urgente else '📋'} Solicitação #{request['id'][:8]} - {request['usuario']}"
            if urgente:
                titulo += " - **URGENTE**"
            st.markdown(titulo)
        
        with col_header2:
            st.caption(format_time_br(request['data_solicitacao']))
        
        try:
            lat, lon = pluscode_to_coords(plus_code_input)
            
            # Informações da Localização
            with st.expander("📍 Informações da Localização", expanded=True):
                col_info1, col_info2 = st.columns(2)
                
                with col_info1:
                    st.text(f"Plus Code: {plus_code_input}")
                    st.text(f"Coordenadas: {lat:.6f}, {lon:.6f}")
                    st.text(f"Usuário: {request['usuario']}")
                
                with col_info2:
                    with st.spinner("Buscando endereço..."):
                        endereco = reverse_geocode(lat, lon)
                        endereco_simples = ", ".join(endereco.split(",")[:3])
                    st.text(f"Endereço:")
                    st.caption(endereco_simples)
                    
                    maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
                    st.markdown(f"[🗺️ Abrir no Google Maps]({maps_url})")
            
            # Buscar CTOs próximas
            candidate_ctos = find_nearest_ctos(lat, lon, ctos, max_radius=3500.0)
            
            cto_routes = []
            if candidate_ctos:
                with st.spinner("🗺️ Calculando rotas para CTOs..."):
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
                    cto_routes = cto_routes[:5]  # Apenas 5 mais próximas
            
            # CTOs mais próximas
            if cto_routes:
                st.markdown("### 🛠 CTOs Mais Próximas - Escolha uma")
                
                for idx, item in enumerate(cto_routes):
                    cto = item["cto"]
                    route = item["route"]
                    pluscode_cto = coords_to_pluscode(cto["lat"], cto["lon"])
                    
                    # Ícone baseado na posição
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
                            st.markdown(f"""
                            **{icon} CTO: {cto["name"]}**  
                            📍 Localização: `{pluscode_cto}`  
                            📏 Distância em linha reta: {format_distance(cto["distance"])}
                            """)
                    
                    with col_cto2:
                        if st.button(
                            "✅ Escolher",
                            key=f"escolher_cto_{request['id']}_{idx}",
                            type="primary",
                            use_container_width=True
                        ):
                            # ========================================
                            # MUDANÇA: Calcular distância COM SOBRA
                            # ========================================
                            
                            if route:
                                # Se tem rota calculada
                                dist_real = route["distance"]
                                dist_com_sobra = dist_real + 50  # Adiciona 50m de sobra
                                distancia_final = format_distance(dist_com_sobra)  # ← USA A DISTÂNCIA COM SOBRA
                            else:
                                # Se não tem rota (linha reta)
                                dist_linha_reta = cto["distance"]
                                dist_com_sobra = dist_linha_reta + 50
                                distancia_final = format_distance(dist_com_sobra)
                            
                            # Salvar CTO escolhida
                            cto_data = {
                                'cto_numero': cto["name"],
                                'distancia_cliente': distancia_final,  # ← DISTÂNCIA COM SOBRA
                                'localizacao_caixa': pluscode_cto
                            }
                            
                            if save_selected_cto(request['id'], cto_data):
                                st.success(f"✅ CTO {cto['name']} escolhida!")
                                st.info("📋 Solicitação enviada para Auditoria")
                                st.balloons()
                                st.rerun()
                    
                    st.markdown("---")
                
                # ===== BOTÃO SEM VIABILIDADE (NOVO) =====
                st.markdown("---")
                st.error("### ❌ Não encontrou CTO viável?")
                
                col_sem_viab = st.columns([1, 2, 1])[1]
                with col_sem_viab:
                    if st.button(
                        "❌ Sem Viabilidade",
                        type="secondary",
                        use_container_width=True,
                        key=f"sem_viab_{request['id']}"
                    ):
                        st.session_state[f'show_reject_form_{request["id"]}'] = True
                
                # Formulário de rejeição (NOVO)
                if st.session_state.get(f'show_reject_form_{request["id"]}', False):
                    with st.form(key=f"form_reject_{request['id']}"):
                        st.markdown("### 📝 Confirmar Sem Viabilidade")
                        
                        motivo = st.text_area(
                            "Motivo da não viabilidade",
                            value="Não temos projeto neste ponto",
                            height=100
                        )
                        
                        col_confirm1, col_confirm2 = st.columns(2)
                        
                        with col_confirm1:
                            confirmar = st.form_submit_button("✅ Confirmar Rejeição", type="primary", use_container_width=True)
                        
                        with col_confirm2:
                            cancelar = st.form_submit_button("🔙 Cancelar", use_container_width=True)
                        
                        if confirmar:
                            dados = {'motivo_rejeicao': motivo.strip() if motivo.strip() else 'Não temos projeto neste ponto'}
                            
                            if update_viability_ftth(request['id'], 'rejeitado', dados):
                                st.success("✅ Solicitação rejeitada!")
                                st.info("📋 Usuário será notificado")
                                del st.session_state[f'show_reject_form_{request["id"]}']
                                st.rerun()
                        
                        if cancelar:
                            del st.session_state[f'show_reject_form_{request["id"]}']
                            st.rerun()
                    
            else:
                st.warning("⚠️ Nenhuma CTO encontrada próxima.")
        
        except Exception as e:
            st.error(f"❌ Erro ao processar: {e}")
            logger.error(f"Erro no processamento: {e}")
        
        st.markdown("---")
        st.markdown("---")

# ======================
# Footer
# ======================
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <p>🔍 <strong>Validador de Projetos</strong> | Desenvolvido ByLeo</p>
</div>
""", unsafe_allow_html=True)

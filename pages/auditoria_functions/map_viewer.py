"""
Módulo de Visualização de Mapas
Salve como: map_viewer.py

Funções para exibir mapas interativos com CTOs e projetos
"""

import streamlit as st
import folium
from streamlit_folium import st_folium
import logging
from typing import List, Tuple
from openlocationcode import openlocationcode as olc
import xml.etree.ElementTree as ET
import gdown

logger = logging.getLogger(__name__)

# ======================
# Configurações
# ======================
LOCATIONIQ_KEY = "pk.66f355328aaad40fe69b57c293f66815"
reference_lat = -28.6775
reference_lon = -49.3696

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

# ======================
# Funções Auxiliares
# ======================

def validate_coordinates(lat: float, lon: float) -> bool:
    """Valida se as coordenadas estão dentro dos limites válidos"""
    return -90 <= lat <= 90 and -180 <= lon <= 180

def coords_to_pluscode(lat: float, lon: float) -> str:
    """Converte coordenadas para Plus Code"""
    return olc.encode(lat, lon)

def pluscode_to_coords(pluscode: str) -> Tuple[float, float]:
    """Converte Plus Code para coordenadas"""
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
def load_ctos_from_kml(path: str) -> List[dict]:
    """Carrega CTOs de um arquivo KML"""
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

# ======================
# Função Principal
# ======================

def show_project_map(pluscode: str, client_name: str = "Cliente", unique_key: str = None, show_ctos: bool = False):
    """
    Exibe mapa interativo com projetos e localização do cliente
    
    Args:
        pluscode: Plus Code do cliente
        client_name: Nome do cliente (para exibição)
        unique_key: Chave única para o mapa (obrigatório)
        show_ctos: Se True, mostra CTOs no mapa (padrão: False)
    
    Returns:
        bool: True se exibiu com sucesso, False se houve erro
    """
    
    if not unique_key:
        st.error("❌ Erro: unique_key é obrigatório para o mapa")
        return False
    
    try:
        # Converter Plus Code para coordenadas
        lat, lon = pluscode_to_coords(pluscode)
        
        if not lat or not lon:
            st.error("❌ Erro ao converter Plus Code para coordenadas")
            return False
        
        with st.spinner("🗺️ Carregando mapa..."):
            # Carregar linhas de projeto
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
            
            # Carregar CTOs se solicitado
            ctos = []
            if show_ctos:
                try:
                    file_id_ctos = "1EcKNk2yqHDEMMXJZ17fT0flPV19HDhKJ"
                    ctos_path = "ctos.kml"
                    download_file(file_id_ctos, ctos_path)
                    ctos = load_ctos_from_kml(ctos_path)
                    # Filtrar CDOIs
                    ctos = [c for c in ctos if not c["name"].upper().startswith("CDOI")]
                except Exception as e:
                    logger.error(f"Erro ao carregar CTOs: {e}")
        
        st.markdown("### 🗺️ Visualização no Mapa")
        
        # Criar mapa centrado no cliente
        mapa = folium.Map(
            location=[lat, lon],
            zoom_start=16,
            tiles="OpenStreetMap"
        )
        
        # Adicionar linhas de projeto
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
            popup=f"<b>📍 {client_name}</b><br>{pluscode}",
            tooltip=f"📍 {client_name}",
            icon=folium.Icon(color='red', icon='home', prefix='fa')
        ).add_to(mapa)
        
        # Adicionar CTOs se solicitado
        if show_ctos and ctos:
            from geopy.distance import geodesic
            
            # Filtrar CTOs próximas (raio de 500m)
            ctos_proximas = []
            for cto in ctos:
                dist = geodesic((lat, lon), (cto["lat"], cto["lon"])).meters
                if dist <= 500:
                    ctos_proximas.append({**cto, "distance": dist})
            
            # Ordenar por distância e pegar as 10 mais próximas
            ctos_proximas.sort(key=lambda x: x["distance"])
            ctos_proximas = ctos_proximas[:10]
            
            # Adicionar marcadores
            cores = ['green', 'blue', 'orange', 'purple', 'darkred', 'lightblue', 'pink', 'gray', 'lightgreen', 'cadetblue']
            for idx, cto in enumerate(ctos_proximas):
                cor = cores[idx] if idx < len(cores) else 'gray'
                
                popup_html = f"""
                <div style='width: 200px'>
                    <h4>{cto['name']}</h4>
                    <p>📏 {cto['distance']:.0f}m</p>
                    <p>📍 {coords_to_pluscode(cto['lat'], cto['lon'])}</p>
                </div>
                """
                
                folium.Marker(
                    location=[cto["lat"], cto["lon"]],
                    popup=folium.Popup(popup_html, max_width=250),
                    tooltip=f"{cto['name']} - {cto['distance']:.0f}m",
                    icon=folium.Icon(color=cor, icon='info-sign', prefix='glyphicon')
                ).add_to(mapa)
        
        # Renderizar mapa
        st_folium(
            mapa,
            width=700,
            height=500,
            key=f"mapa_{unique_key}",
            returned_objects=[],
            feature_group_to_add=None
        )
        
        st.caption("🗺️ Mapa interativo com projetos de rede")
        
        return True
        
    except Exception as e:
        st.error(f"❌ Erro ao carregar mapa: {e}")
        logger.error(f"Erro no mapa: {e}")
        return False

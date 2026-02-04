"""
Manipulador de Viabilizações para Condomínios
Usa padrão FTTH (busca de CTOs) mas com opção de viabilização de estrutura
Salve como: pages/auditoria_functions/condominio_handler.py
"""

import streamlit as st
import logging
from typing import List, Tuple
from openlocationcode import openlocationcode as olc
from geopy.distance import geodesic
import gdown
import requests
import xml.etree.ElementTree as ET
from pages.auditoria_functions.map_viewer import show_project_map

logger = logging.getLogger(__name__)

# Configurações
reference_lat = -28.6775
reference_lon = -49.3696
file_id_ctos = "1EcKNk2yqHDEMMXJZ17fT0flPV19HDhKJ"
ctos_kml_path = "ctos.kml"

# ======================
# Funções Auxiliares
# ======================

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

# ======================
# Função Principal
# ======================

def show_condominio_form(row: dict):
    """
    Exibe formulário de auditoria para Condomínios
    Usa padrão FTTH (busca CTOs) mas com opção de viabilização de estrutura

    Args:
        row: Dicionário com dados da viabilização
    """
    from viability_functions import (
        update_viability_ftth,
        request_building_viability,
        reject_building_viability,
        schedule_building_visit,
        format_time_br_supa
    )

    # Verificar status do condomínio
    status_predio = row.get('status_predio')

    # ========================================
    # FORMULÁRIO INICIAL (sem viabilização ou rejeitado)
    # ========================================
    if status_predio is None or status_predio == 'rejeitado':
        st.markdown("#### 🏘️ Dados do Condomínio")

        # Verificar se CTO já foi escolhida
        cto_escolhida = row.get('cto_numero')

        if cto_escolhida:
            col_cto_info, col_cto_btn = st.columns([3, 1])
            with col_cto_info:
                st.success(f"✅ CTO Escolhida: **{cto_escolhida}**")
                st.caption(f"📏 Distância: {row.get('distancia_cliente', 'N/A')} | 📍 Localização: {row.get('localizacao_caixa', 'N/A')}")
                st.warning("⚠️ Os campos abaixo são EDITÁVEIS caso precise corrigir")

            with col_cto_btn:
                if st.button(
                    "🔄 Buscar Novamente",
                    type="secondary",
                    use_container_width=True,
                    key=f"btn_rebuscar_cond_{row['id']}",
                    help="Clicou errado ou não tem porta? Busque outra CTO"
                ):
                    st.session_state[f'mostrar_busca_cond_{row["id"]}'] = True
                    st.rerun()

        # ========================================
        # BOTÃO BUSCAR CTOs
        # ========================================
        if not cto_escolhida or st.session_state.get(f'mostrar_busca_cond_{row["id"]}', False):
            col_busca = st.columns([1, 2, 1])[1]
            with col_busca:
                if st.button(
                    "🔍 Buscar CTOs Próximas",
                    type="secondary",
                    width='stretch',
                    key=f"btn_buscar_cond_{row['id']}"
                ):
                    st.session_state[f'mostrar_busca_cond_{row["id"]}'] = True
                    st.rerun()

        # ========================================
        # MOSTRAR BUSCA DE CTOs
        # ========================================
        if st.session_state.get(f'mostrar_busca_cond_{row["id"]}', False):
            try:
                # Converter Plus Code para coordenadas
                lat, lon = pluscode_to_coords(row['plus_code_cliente'])

                if lat and lon:
                    # Carregar CTOs
                    with st.spinner("Carregando dados..."):
                        download_ctos_file(file_id_ctos, ctos_kml_path)
                        ctos = load_ctos_from_kml(ctos_kml_path)

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

                        st.success(f"✅ {len(cto_routes)} CTOs encontradas")

                        # MAPA
                        show_project_map(
                            pluscode=row['plus_code_cliente'],
                            client_name=row.get('predio_ftta', 'Condomínio'),
                            unique_key=f"cond_busca_{row['id']}",
                            show_ctos=True
                        )

                        st.markdown("---")

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
                                    key=f"escolher_cto_cond_{row['id']}_{idx}",
                                    type="primary",
                                    width='stretch'
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
                                        del st.session_state[f'mostrar_busca_cond_{row["id"]}']
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
                if st.button("❌ Fechar Busca", width='stretch', key=f"fechar_busca_cond_{row['id']}"):
                    del st.session_state[f'mostrar_busca_cond_{row["id"]}']
                    st.rerun()

        # ========================================
        # FORMULÁRIO DE AUDITORIA
        # ========================================
        if not st.session_state.get(f'mostrar_busca_cond_{row["id"]}', False):
            st.markdown("---")

        with st.form(key=f"form_cond_{row['id']}"):
            cto = st.text_input(
                "N° Caixa (CTO) *",
                value=row.get('cto_numero', ''),
                disabled=False,
                key=f"cto_cond_{row['id']}",
                help="⚠️ Você pode editar este campo se necessário"
            )

            col_f1, col_f2 = st.columns(2)
            with col_f1:
                distancia = st.text_input(
                    "Distância até Condomínio *",
                    value=row.get('distancia_cliente', ''),
                    disabled=False,
                    key=f"dist_cond_{row['id']}",
                    help="⚠️ Editável - ex: 150m, 1.2km"
                )
            with col_f2:
                localizacao = st.text_input(
                    "Localização da Caixa *",
                    value=row.get('localizacao_caixa', ''),
                    disabled=False,
                    key=f"loc_cond_{row['id']}",
                    help="⚠️ Editável - Plus Code da caixa"
                )

            st.markdown("---")
            st.markdown("**Preencha os dados técnicos:**")

            col_f3, col_f4 = st.columns(2)
            with col_f3:
                portas = st.number_input("Portas Disponíveis *", min_value=0, max_value=50, value=0, key=f"portas_cond_{row['id']}")
            with col_f4:
                rx = st.text_input("Menor RX (dBm) *", placeholder="-18.67", key=f"rx_cond_{row['id']}")

            obs = st.text_area("Observações", key=f"obs_cond_{row['id']}", height=80)

            # Botões
            col_btn1, col_btn2 = st.columns(2)

            with col_btn1:
                aprovado = st.form_submit_button("✅ Viabilizar", type="primary", width='stretch')
            with col_btn2:
                rejeitado = st.form_submit_button("❌ Sem Viabilidade", type="secondary", width='stretch')

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
                st.session_state[f'show_reject_cond_form_{row["id"]}'] = True

        # ========================================
        # FORMULÁRIO DE REJEIÇÃO
        # ========================================
        if st.session_state.get(f'show_reject_cond_form_{row["id"]}', False):
            st.markdown("---")
            st.error("### ❌ Registrar Sem Viabilidade")

            with st.form(key=f"form_reject_cond_{row['id']}"):
                st.markdown("**Informe o motivo para o usuário:**")

                col_info1, col_info2 = st.columns(2)
                with col_info1:
                    st.text_input("📍 Plus Code", value=row['plus_code_cliente'], disabled=True)
                with col_info2:
                    if row.get('nome_cliente'):
                        st.text_input("👤 Cliente", value=row['nome_cliente'], disabled=True)

                motivo_rejeicao_cond = st.text_area(
                    "📝 Justificativa para o usuário *",
                    placeholder="Ex: Não temos projeto nesta rua, distância muito grande da rede, área não coberta, etc.",
                    height=100,
                    key=f"motivo_rej_cond_{row['id']}"
                )

                col_btn_rej1, col_btn_rej2 = st.columns(2)

                with col_btn_rej1:
                    confirmar_rej_cond = st.form_submit_button(
                        "✅ Confirmar Rejeição",
                        type="primary",
                        width='stretch'
                    )

                with col_btn_rej2:
                    cancelar_rej_cond = st.form_submit_button(
                        "🔙 Cancelar",
                        width='stretch'
                    )

                if confirmar_rej_cond:
                    if not motivo_rejeicao_cond or motivo_rejeicao_cond.strip() == "":
                        st.error("❌ Informe o motivo da não viabilidade!")
                    else:
                        dados = {'motivo_rejeicao': motivo_rejeicao_cond.strip()}
                        if update_viability_ftth(row['id'], 'rejeitado', dados):
                            st.success("❌ Solicitação rejeitada!")
                            del st.session_state[f'show_reject_cond_form_{row["id"]}']
                            st.rerun()

                if cancelar_rej_cond:
                    del st.session_state[f'show_reject_cond_form_{row["id"]}']
                    st.rerun()

        # ========================================
        # BOTÃO VIABILIZAR ESTRUTURA NO CONDOMÍNIO
        # ========================================
        if status_predio is None:
            st.markdown("---")
            st.markdown("#### 🏗️ Viabilização de Estrutura no Condomínio")
            st.info("🔧 Temos projeto na rua, mas não temos estrutura pronta no condomínio")

            col_viab_cond = st.columns([1, 2, 1])[1]
            with col_viab_cond:
                if st.button(
                    "🏘️ Solicitar Viabilização do Condomínio",
                    type="primary",
                    width='stretch',
                    key=f"viab_cond_{row['id']}"
                ):
                    if request_building_viability(row['id'], {}):
                        st.success("✅ Solicitação enviada! Aguardando dados do usuário.")
                        st.info("👤 O usuário receberá um formulário para preencher.")
                        st.rerun()

    # ========================================
    # AGUARDANDO DADOS
    # ========================================
    elif status_predio == 'aguardando_dados':
        st.markdown("#### 🏗️ Viabilização de Estrutura no Condomínio")
        st.warning("⏳ **Aguardando dados do usuário**")
        st.caption(f"📅 Solicitado em: {format_time_br_supa(row.get('data_solicitacao_predio', ''))}")
        st.info("👤 O usuário está preenchendo o formulário com os dados do condomínio.")

    # ========================================
    # PRONTO PARA AUDITORIA
    # ========================================
    elif status_predio == 'pronto_auditoria':
        st.markdown("#### 🏗️ Viabilização de Estrutura no Condomínio")
        st.success("✅ **Dados recebidos! Pronto para análise**")

        # Mostrar dados recebidos
        with st.expander("👁️ Ver Dados do Cliente", expanded=True):
            col_dados1, col_dados2 = st.columns(2)
            with col_dados1:
                st.markdown("**👤 Responsável/Síndico**")
                st.text(f"Nome: {row.get('nome_sindico', 'N/A')}")
                st.text(f"Contato: {row.get('contato_sindico', 'N/A')}")
            with col_dados2:
                st.markdown("**🏠 Cliente**")
                st.text(f"Nome: {row.get('nome_cliente_predio', 'N/A')}")
                st.text(f"Contato: {row.get('contato_cliente_predio', 'N/A')}")

            st.text(f"🚪 Casa/Apto: {row.get('apartamento', 'N/A')}")
            st.text(f"🏘️ Condomínio: {row.get('predio_ftta', 'N/A')}")
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
                key=f"data_visita_cond_{row['id']}",
                help="Selecione a data para visita técnica",
                format="DD/MM/YYYY"
            )

        with col_ag2:
            periodo = st.selectbox(
                "🕐 Período",
                options=["Manhã", "Tarde"],
                key=f"periodo_cond_{row['id']}"
            )

        # Segunda linha com Técnico e Tecnologia
        col_ag3, col_ag4 = st.columns(2)

        with col_ag3:
            tecnico = st.text_input(
                "👷 Técnico Responsável",
                placeholder="Nome do técnico",
                key=f"tecnico_cond_{row['id']}"
            )
        with col_ag4:
            tecnologia = st.selectbox(
                "🔧 Tecnologia",
                options=["FTTH"],
                key=f"tecnologia_cond_{row['id']}",
                help="Tipo de tecnologia a ser instalada"
            )

        # Checkbox Giga
        giga_agendamento = st.checkbox("⚡ Condomínio Giga?", key=f"giga_agendamento_cond_{row['id']}")

        st.markdown("---")

        # Botões de ação
        col_action1, col_action2 = st.columns(2)

        with col_action1:
            if st.button(
                "📋 Agendar Visita Técnica",
                type="primary",
                width='stretch',
                key=f"agendar_cond_{row['id']}"
            ):
                if not tecnico or not data_visita or not tecnologia:
                    st.error("❌ Preencha todos os campos de agendamento!")
                else:
                    if schedule_building_visit(
                        row['id'],
                        data_visita,
                        periodo,
                        tecnico,
                        tecnologia,
                        giga_agendamento
                    ):
                        st.success("✅ Visita agendada com sucesso!")
                        st.info("📅 Agendamento registrado na Agenda FTTA/UTP")
                        st.rerun()
                    else:
                        st.error("❌ Erro ao agendar. Tente novamente.")

        with col_action2:
            if st.button(
                "❌ Condomínio Sem Viabilidade",
                type="secondary",
                width='stretch',
                key=f"sem_viab_cond_{row['id']}"
            ):
                st.session_state[f'show_reject_form_cond_{row["id"]}'] = True

        # Formulário de rejeição (aparece ao clicar no botão)
        if st.session_state.get(f'show_reject_form_cond_{row["id"]}', False):
            st.markdown("---")
            st.error("### ❌ Registrar Condomínio Sem Viabilidade")

            with st.form(key=f"form_reject_cond_building_{row['id']}"):
                st.markdown("**Os seguintes dados serão registrados para consulta futura:**")

                col_rej1, col_rej2 = st.columns(2)
                with col_rej1:
                    st.text_input("🏘️ Condomínio", value=row.get('predio_ftta', ''), disabled=True)
                with col_rej2:
                    st.text_input("📍 Localização", value=row['plus_code_cliente'], disabled=True)

                motivo_rejeicao = st.text_area(
                    "📝 Motivo da Não Viabilidade *",
                    placeholder="Descreva o motivo: estrutura inadequada, recusa do responsável, etc.",
                    height=100
                )

                col_btn_rej1, col_btn_rej2 = st.columns(2)

                with col_btn_rej1:
                    confirmar_rejeicao = st.form_submit_button(
                        "✅ Confirmar Rejeição",
                        type="primary",
                        width='stretch'
                    )

                with col_btn_rej2:
                    cancelar = st.form_submit_button(
                        "🔙 Cancelar",
                        width='stretch'
                    )

                if confirmar_rejeicao:
                    if not motivo_rejeicao or motivo_rejeicao.strip() == "":
                        st.error("❌ Descreva o motivo da não viabilidade!")
                    else:
                        if reject_building_viability(
                            row['id'],
                            row.get('predio_ftta', 'Condomínio'),
                            row['plus_code_cliente'],
                            motivo_rejeicao.strip()
                        ):
                            st.success("✅ Condomínio registrado como sem viabilidade!")
                            st.info("📝 Registro salvo para consulta futura")
                            del st.session_state[f'show_reject_form_cond_{row["id"]}']
                            st.rerun()
                        else:
                            st.error("❌ Erro ao registrar. Tente novamente.")

                if cancelar:
                    del st.session_state[f'show_reject_form_cond_{row["id"]}']
                    st.rerun()

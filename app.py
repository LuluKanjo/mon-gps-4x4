import streamlit as st
import folium
from streamlit_folium import folium_static
from streamlit_js_eval import streamlit_js_eval
import requests
import pandas as pd
import urllib.parse
from geopy.distance import geodesic

st.set_page_config(page_title="4x4 Expedition Master", layout="wide", initial_sidebar_state="collapsed")

# --- INITIALISATION ---
if 'trace' not in st.session_state: st.session_state['trace'] = []
if 'total_dist' not in st.session_state: st.session_state['total_dist'] = 0.0
if 'manual_mode' not in st.session_state: st.session_state['manual_mode'] = False

# --- BARRE LATÉRALE ---
with st.sidebar:
    st.header("🛠️ Configuration")
    dist_km = st.slider("Rayon de scan (km)", 2, 10, 5)
    num_sos = st.text_input("Numéro SOS (+33...)", "")
    st.divider()
    recording = st.toggle("🛰️ Enregistrer ma trace rouge", value=True)
    if st.button("🗑️ Effacer la trace"):
        st.session_state['trace'] = []
        st.session_state['total_dist'] = 0.0
        st.rerun()

# --- RÉCUPÉRATION GPS ---
loc = streamlit_js_eval(js_expressions='navigator.geolocation.getCurrentPosition(pos => {return {lat: pos.coords.latitude, lon: pos.coords.longitude, alt: pos.coords.altitude, speed: pos.coords.speed}})', key='gps_v5')

# --- FONCTION DE RÉCUPÉRATION OPTIMISÉE ---
@st.cache_data(ttl=300)
def fetch_pistes_pro(lat, lon, dist_m):
    url = "https://overpass-api.de/api/interpreter"
    # Requête chirurgicale : on ne prend que l'essentiel pour ne pas saturer
    query = f"""[out:json][timeout:30];
    (way["highway"="track"]["motor_vehicle"!~"no|private"](around:{dist_m},{lat},{lon}););
    out body; >; out skel qt;"""
    headers = {'User-Agent': 'GPS-4x4-Expedition-Pro-V5'}
    try:
        r = requests.get(url, params={'data': query}, headers=headers, timeout=20)
        if r.status_code == 200: return r.json(), "OK"
        return None, f"Erreur {r.status_code}"
    except: return None, "Serveur indisponible"

st.title("🚜 4x4 Adventure Dash")

# Gestion Position
if not loc and not st.session_state['manual_mode']:
    st.info("🛰️ Recherche GPS...")
    if st.button("📍 Utiliser position Cournonterral (Test)"):
        st.session_state['manual_mode'] = True
        st.rerun()

if loc or st.session_state['manual_mode']:
    lat, lon = (loc['lat'], loc['lon']) if loc else (43.5578, 3.7188)
    alt = loc.get('alt', 50) if loc else 50
    vitesse = (loc.get('speed', 0) or 0) * 3.6 if loc else 0

    # Trace rouge
    if recording and loc:
        if not st.session_state['trace'] or st.session_state['trace'][-1] != (lat, lon):
            if st.session_state['trace']:
                st.session_state['total_dist'] += geodesic(st.session_state['trace'][-1], (lat, lon)).km
            st.session_state['trace'].append((lat, lon))

    # Metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("Altitude", f"{int(alt)} m")
    c2.metric("Vitesse", f"{int(vitesse)} km/h")
    c3.metric("Parcouru", f"{st.session_state['total_dist']:.2f} km")

    # Bouton SOS
    if num_sos:
        msg = urllib.parse.quote(f"SOS 4x4 ! Je suis ici : http://maps.google.com/maps?q={lat},{lon}")
        st.markdown(f'<a href="sms:{num_sos}?body={msg}"><button style="width:100%; background-color:#ff4b4b; color:white; border:none; padding:15px; border-radius:10px; font-weight:bold; cursor:pointer; margin-bottom:20px;">🚨 ENVOYER POSITION SOS PAR SMS</button></a>', unsafe_allow_html=True)

    # Carte
    if st.button(f"🗺️ SCANNER LES PISTES ({dist_km} KM)"):
        with st.spinner("Analyse du terrain..."):
            m = folium.Map(location=[lat, lon], zoom_start=14)
            folium.TileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google', name='Satellite').add_to(m)
            
            data, status = fetch_pistes_pro(lat, lon, dist_km * 1000)
            
            if data:
                nodes = {n['id']: (n['lat'], n['lon']) for n in data['elements'] if n['type'] == 'node'}
                for el in data['elements']:
                    if el['type'] == 'way':
                        coords = [nodes[nid] for nid in el['nodes'] if nid in nodes]
                        folium.PolyLine(coords, color="#CCFF00", weight=5, opacity=0.9).add_to(m)
                st.success(f"Pistes trouvées dans un rayon de {dist_km} km !")
            else:
                st.error(f"Le serveur sature à {dist_km}km. Essayez de réduire le rayon à 3km.")

            if st.session_state['trace']:
                folium.PolyLine(st.session_state['trace'], color="red", weight=4).add_to(m)

            folium.Marker([lat, lon], icon=folium.Icon(color='red', icon='car', prefix='fa')).add_to(m)
            folium_static(m, width=1000, height=600)

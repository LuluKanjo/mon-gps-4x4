import streamlit as st
import folium
from streamlit_folium import folium_static
from streamlit_js_eval import streamlit_js_eval
import requests
import pandas as pd
import urllib.parse
from geopy.distance import geodesic

st.set_page_config(page_title="4x4 Expedition Master", layout="wide", initial_sidebar_state="collapsed")

# --- INITIALISATION & CACHE ---
if 'trace' not in st.session_state: st.session_state['trace'] = []
if 'total_dist' not in st.session_state: st.session_state['total_dist'] = 0.0
if 'manual_mode' not in st.session_state: st.session_state['manual_mode'] = False

# Cette fonction garde les données en mémoire pendant 10 minutes pour ne pas saturer les serveurs
@st.cache_data(ttl=600)
def fetch_pistes(lat, lon, dist):
    servers = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://lz4.overpass-api.de/api/interpreter"
    ]
    # Requête optimisée (plus légère)
    query = f"""[out:json][timeout:30];
    (
      way["highway"~"track|unclassified"]["motor_vehicle"!~"no|private"]["access"!~"no|private"](around:{dist},{lat},{lon});
      node["amenity"~"fuel|drinking_water"](around:{dist},{lat},{lon});
      node["tourism"~"camp_site|picnic_site"](around:{dist},{lat},{lon});
    );
    out body; >; out skel qt;"""
    
    headers = {'User-Agent': 'GPS-4x4-Cournonterral-App/1.0'}
    
    for url in servers:
        try:
            r = requests.get(url, params={'data': query}, headers=headers, timeout=15)
            if r.status_code == 200:
                return r.json()
        except:
            continue
    return None

# --- RÉCUPÉRATION GPS ---
loc = streamlit_js_eval(js_expressions='navigator.geolocation.getCurrentPosition(pos => {return {lat: pos.coords.latitude, lon: pos.coords.longitude, alt: pos.coords.altitude, speed: pos.coords.speed}})', key='gps_final')

st.title("🚜 4x4 Adventure Dash")

# --- GESTION POSITION ---
if not loc and not st.session_state['manual_mode']:
    st.info("🛰️ Recherche du signal... Cliquez ci-dessous si vous êtes à l'intérieur.")
    if st.button("📍 Forcer la position (Cournonterral)"):
        st.session_state['manual_mode'] = True
        st.rerun()

if loc or st.session_state['manual_mode']:
    lat, lon = (loc['lat'], loc['lon']) if loc else (43.5578, 3.7188)
    alt = loc.get('alt', 0) if loc else 50
    vitesse = (loc.get('speed', 0) or 0) * 3.6 if loc else 0

    # Dashboard Metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Altitude", f"{int(alt) if alt else '--'} m")
    c2.metric("Vitesse", f"{int(vitesse)} km/h")
    c3.metric("Distance", f"{st.session_state['total_dist']:.2f} km")
    try:
        w = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true").json()
        c4.metric("Météo", f"{w['current_weather']['temperature']} °C")
    except: c4.metric("Météo", "--")

    # Bouton SOS dynamique
    if st.sidebar.text_input("Numéro SOS", ""):
        num = st.sidebar.text_input("Numéro SOS", "")
        g_maps = f"https://www.google.com/maps?q={lat},{lon}"
        sms = f"sms:{num}?body=SOS 4x4 ! Position : {g_maps}"
        st.markdown(f'<a href="{sms}"><button style="width:100%; background-color:#ff4b4b; color:white; border:none; padding:12px; border-radius:10px; font-weight:bold; cursor:pointer;">🚨 SOS SMS</button></a>', unsafe_allow_html=True)

    # --- LA CARTE ---
    if st.button("🗺️ CHARGER LES PISTES AUTORISÉES"):
        with st.spinner("Récupération des chemins légaux..."):
            m = folium.Map(location=[lat, lon], zoom_start=15)
            folium.TileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google', name='Satellite').add_to(m)
            
            # Utilisation de la fonction avec cache
            data = fetch_pistes(lat, lon, 3000)
            
            if data:
                nodes = {n['id']: (n['lat'], n['lon']) for n in data['elements'] if n['type'] == 'node'}
                for el in data['elements']:
                    if el['type'] == 'way':
                        coords = [nodes[nid] for nid in el['nodes'] if nid in nodes]
                        folium.PolyLine(coords, color="#CCFF00", weight=5, opacity=0.9).add_to(m)
                    if el['type'] == 'node' and 'tags' in el:
                        t = el['tags']
                        if 'fuel' in str(t): folium.Marker([el['lat'], el['lon']], icon=folium.Icon(color='orange', icon='gas-pump', prefix='fa')).add_to(m)
                        elif 'water' in str(t): folium.Marker([el['lat'], el['lon']], icon=folium.Icon(color='blue', icon='tint', prefix='fa')).add_to(m)
            else:
                st.error("Les serveurs sont très occupés. Réessayez dans 30 secondes ou changez de zone.")

            folium.Marker([lat, lon], icon=folium.Icon(color='red', icon='car', prefix='fa')).add_to(m)
            folium_static(m, width=1000, height=600)

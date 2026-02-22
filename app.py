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
    st.title("⚙️ Paramètres")
    num_urgence = st.text_input("📞 Numéro SOS (+336...)", "")
    scan_dist = st.slider("🔍 Scan des pistes (m)", 1000, 10000, 5000)
    st.divider()
    recording = st.toggle("🛰️ Enregistrer ma trace", value=False)
    if st.button("🗑️ Reset l'étape"):
        st.session_state['trace'] = []
        st.session_state['total_dist'] = 0.0
        st.session_state['manual_mode'] = False
        st.rerun()

# --- RÉCUPÉRATION GPS ---
# On tente la localisation auto
loc = streamlit_js_eval(js_expressions='navigator.geolocation.getCurrentPosition(pos => {return {lat: pos.coords.latitude, lon: pos.coords.longitude, alt: pos.coords.altitude, speed: pos.coords.speed}})', key='gps_auto')

# --- GESTION DU MODE MANUEL SI LE GPS BLOQUE ---
st.title("🚜 4x4 Adventure Dash")

if not loc and not st.session_state['manual_mode']:
    st.warning("📡 Recherche du signal GPS... (Si cela reste bloqué, utilisez le bouton ci-dessous)")
    if st.button("📍 Forcer la position sur Cournonterral (Test)"):
        st.session_state['manual_mode'] = True
        st.rerun()

# Définition des coordonnées finales (Auto ou Manuel)
if st.session_state['manual_mode'] and not loc:
    lat, lon, alt, vitesse = 43.5578, 3.7188, 50, 0
else:
    if loc:
        lat, lon = loc['lat'], loc['lon']
        alt = loc.get('alt', 0)
        vitesse = (loc.get('speed', 0) or 0) * 3.6
    else:
        lat = None

# --- AFFICHAGE SI POSITION DISPONIBLE ---
if lat:
    # Enregistrement de la trace
    if recording:
        if not st.session_state['trace'] or st.session_state['trace'][-1] != (lat, lon):
            if st.session_state['trace']:
                st.session_state['total_dist'] += geodesic(st.session_state['trace'][-1], (lat, lon)).km
            st.session_state['trace'].append((lat, lon))

    # Metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Altitude", f"{int(alt) if alt else '--'} m")
    c2.metric("Vitesse", f"{int(vitesse)} km/h")
    c3.metric("Distance Trace", f"{st.session_state['total_dist']:.2f} km")
    try:
        w = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true").json()
        c4.metric("Météo", f"{w['current_weather']['temperature']} °C")
    except: c4.metric("Météo", "--")

    # SOS
    if num_urgence:
        encoded_msg = urllib.parse.quote(f"SOS 4x4 ! Position : http://maps.google.com/maps?q={lat},{lon}")
        st.markdown(f'<a href="sms:{num_urgence}?body={encoded_msg}"><button style="width:100%; background-color:#ff4b4b; color:white; border:none; padding:15px; border-radius:10px; font-weight:bold; cursor:pointer; margin-bottom:20px;">🚨 ENVOYER POSITION SOS PAR SMS</button></a>', unsafe_allow_html=True)

    if st.button("🗺️ ACTUALISER LA CARTE"):
        with st.spinner("Analyse du terrain..."):
            m = folium.Map(location=[lat, lon], zoom_start=15)
            folium.TileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google', name='Satellite').add_to(m)
            
            # Scan Pistes
            q = f"""[out:json];(way["highway"~"track|unclassified"]["motor_vehicle"!~"no|private"]["access"!~"no|private"](around:{scan_dist},{lat},{lon});node["amenity"~"fuel|drinking_water"](around:{scan_dist},{lat},{lon});node["tourism"~"camp_site|picnic_site"](around:{scan_dist},{lat},{lon}););out body;>;out skel qt;"""
            try:
                data = requests.get("http://overpass-api.de/api/interpreter", params={'data': q}).json()
                nodes = {n['id']: (n['lat'], n['lon']) for n in data['elements'] if n['type'] == 'node'}
                for el in data['elements']:
                    if el['type'] == 'way':
                        coords = [nodes[nid] for nid in el['nodes'] if nid in nodes]
                        folium.PolyLine(coords, color="#CCFF00", weight=5, opacity=0.9).add_to(m)
            except: st.error("Liaison base de données difficile...")

            if len(st.session_state['trace']) > 1:
                folium.PolyLine(st.session_state['trace'], color="red", weight=4).add_to(m)

            folium.Marker([lat, lon], icon=folium.Icon(color='red', icon='car', prefix='fa')).add_to(m)
            folium_static(m, width=1000, height=600)

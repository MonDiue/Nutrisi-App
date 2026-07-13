import streamlit as st
from google import genai

# IMPOR HALAMAN DAN HELPER DARI BERKAS PYTHON TERPISAH
from auth_page import render_halaman_login
from profil_page import render_halaman_profil
from dashboard_page import render_halaman_utama

# Setup konfigurasi dasar halaman web browser
st.set_page_config(
    page_title="AI Nutrition Tracker Pro",
    page_icon="🥗",
    layout="centered"
)

# Inisialisasi Klien SDK Gemini AI Pro global
if "client" not in st.session_state:
    try:
        st.session_state.client = genai.Client()
    except Exception:
        st.session_state.client = None

# Inisialisasi Seluruh Kebutuhan State Aplikasi Semasa Sesi Berjalan
if "logged_in" not in st.session_state: 
    st.session_state.logged_in = False
if "profile_setup_done" not in st.session_state: 
    st.session_state.profile_setup_done = False
if "user_profile" not in st.session_state: 
    st.session_state.user_profile = {}
if "nutrisi_target" not in st.session_state: 
    st.session_state.nutrisi_target = {}
if "jurnal_hari_ini" not in st.session_state: 
    st.session_state.jurnal_hari_ini = {"kalori": 0.0, "protein": 0.0, "karbohidrat": 0.0, "lemak": 0.0, "air": 0.0, "serat": 0.0}
if "riwayat_makanan" not in st.session_state: 
    st.session_state.riwayat_makanan = []
if "show_upload_options" not in st.session_state: 
    st.session_state.show_upload_options = False
if "pending_analysis" not in st.session_state: 
    st.session_state.pending_analysis = None

# CENTRAL ROUTING CONTROLLER (Pengarah Alur Navigasi State)
if not st.session_state.logged_in:
    render_halaman_login()
elif st.session_state.logged_in and not st.session_state.profile_setup_done:
    render_halaman_profil()
else:
    render_halaman_utama()

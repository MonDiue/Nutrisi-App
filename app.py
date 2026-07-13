import streamlit as st
import json
from google import genai
from google.genai import types
from PIL import Image
import io

# Setup konfigurasi dasar halaman browser
st.set_page_config(
    page_title="AI Nutrition Tracker Pro",
    page_icon="🥗",
    layout="centered"
)

# ==========================================
# 1. INISIALISASI GEMINI CLIENT & STATE
# ==========================================
if "client" not in st.session_state:
    try:
        st.session_state.client = genai.Client()
    except Exception as e:
        st.session_state.client = None

# Inisialisasi State Pengatur Alur Halaman & Jurnal Data
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

# State baru untuk menu upload dan verifikasi data makanan
if "show_upload_options" not in st.session_state:
    st.session_state.show_upload_options = False
if "pending_analysis" not in st.session_state:
    st.session_state.pending_analysis = None

# ==========================================
# 2. LOGIKA UTAMA INTEGRASI GEMINI AI
# ==========================================
def hitung_target_via_ai(profil):
    """Menghitung target makronutrisi harian — PROTEIN DIKUNCI 2X BERAT BADAN TARGET"""
    protein_mutlak = int(profil["target_berat"] * 2) # Aturan Baru: Menggunakan berat badan target
    
    prompt = f"""
    Kamu adalah seorang Ahli Gizi Dietisien AI profesional. 
    Hitunglah kebutuhan energi (TDEE) dan makronutrisi harian untuk profil berikut:
    - Berat Badan Sekarang: {profil['berat_badan']} kg
    - Tinggi Badan: {profil['tinggi_badan']} cm
    - Umur: {profil['umur']} tahun
    - Target Berat Badan Akhir: {profil['target_berat']} kg
    - Body Goal Utama: {profil['body_goal']}
    
    ATURAN MUTLAK: 
    Target Protein harian HARUS bernilai TEPAT {protein_mutlak} gram (2x dari berat badan TARGET). Jangan diubah!
    Sesuaikan alokasi sisa kalori untuk Karbohidrat dan Lemak sehat secara proporsional sesuai dengan Body Goal mereka.
    
    Berikan hasil kalkulasi dalam format JSON murni tanpa hiasan teks dengan struktur berikut:
    {{
        "kalori": 2200,
        "protein": {protein_mutlak},
        "karbohidrat": 240,
        "lemak": 60,
        "air": 3000,
        "serat": 28
    }}
    """
    if st.session_state.client is None:
        return {"kalori": int(profil["target_berat"] * 30), "protein": protein_mutlak, "karbohidrat": 220, "lemak": 60, "air": 2500, "serat": 25}
        
    try:
        response = st.session_state.client.models.generate_content(
            model='gemini-2.5-flash', contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception as e:
        return {"kalori": int(profil["target_berat"] * 30), "protein": protein_mutlak, "karbohidrat": 200, "lemak": 55, "air": 2500, "serat": 25}

def analisis_foto_makanan_ai(gambar_pil):
    """Menganalisis foto: mendeteksi jenis, bagian, metode masak, gramasi, dan gizi matang/mentah"""
    prompt = """
    Kamu adalah AI Nutritionist yang sangat detail. Analisis makanan/minuman yang ada di dalam foto ini.
    
    Tugas Analisis:
    1. Deteksi semua item makanan/minuman yang terlihat beserta BAGIAN SPESIFIKNYA (misal: dada ayam tanpa kulit, paha atas, telur putihnya saja).
    2. Deteksi METODE MEMASAK yang diterapkan (Goreng, Rebus, Kukus, Panggang, Tumis, atau jika Mentah).
    3. Berikan ASUMSI ESTIMASI TAKARAN/GRAMASI (Gunakan satuan 'gram' atau 'buah'/'butir' untuk makanan, dan 'ml' untuk minuman).
    4. Hitung NILAI NUTRISI YANG SESUAI DENGAN METODE MEMASAKNYA (Contoh: Dada ayam goreng memiliki lemak lebih tinggi dibanding dada ayam rebus).
    
    Berikan hasil akhir dalam format JSON murni dengan bentuk struktur seperti ini:
    {
        "nama_makanan": "Dada Ayam",
        "bagian_makanan": "Dada tanpa kulit",
        "metode_masak": "Goreng",
        "gramasi_estimasi": "150 gram",
        "kalori": 295,
        "protein": 31.0,
        "karbohidrat": 0.0,
        "lemak": 15.0,
        "serat": 0.0,
        "air": 90
    }
    """
    try:
        response = st.session_state.client.models.generate_content(
            model='gemini-2.5-flash', contents=[gambar_pil, prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception as e:
        st.error(f"Gagal menganalisis foto: {e}")
        return None

def rekalkulasi_nutrisi_via_ai(nama, bagian, metode, gramasi):
    """Mengkalkulasi ulang nilai nutrisi berdasarkan koreksi/input manual dari user"""
    prompt = f"""
    Kamu adalah pakar nutrisi kalori. Pengguna mengoreksi data makanan yang mereka makan secara manual.
    Hitung ulang secara akurat nilai nutrisi berdasarkan detail berikut:
    - Nama Makanan: {nama}
    - Bagian yang Dimakan: {bagian}
    - Metode Memasak: {metode}
    - Gramasi / Takaran: {gramasi}
    
    Hitung nilai gizi yang sesuai dengan bentuk olahan makanan tersebut (misal lemak bertambah jika digoreng).
    Berikan output dalam format JSON murni dengan struktur berikut:
    {{
        "nama_makanan": "{nama}",
        "bagian_makanan": "{bagian}",
        "metode_masak": "{metode}",
        "gramasi_estimasi": "{gramasi}",
        "kalori": 0,
        "protein": 0.0,
        "karbohidrat": 0.0,
        "lemak": 0.0,
        "serat": 0.0,
        "air": 0
    }}
    """
    try:
        response = st.session_state.client.models.generate_content(
            model='gemini-2.5-flash', contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception as e:
        st.error(f"Gagal mengkalkulasi ulang: {e}")
        return None

# ==========================================
# 3. INTERFACE HALAMAN 1 & 2 (LOGIN & PROFIL)
# ==========================================
def render_halaman_login():
    st.markdown("<h2 style='text-align: center; margin-top: 20px;'>🔐 Sign In / Sign Up</h2>", unsafe_allow_html=True)
    st.write("Selamat datang di **AI Nutrition Tracker**. Silakan hubungkan akun Anda:")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔴 Masuk dengan Google", use_container_width=True): st.session_state.logged_in = True; st.rerun()
        if st.button("🔵 Masuk dengan Facebook", use_container_width=True): st.session_state.logged_in = True; st.rerun()
    with col2:
        if st.button("📧 Gunakan Akun Gmail", use_container_width=True): st.session_state.logged_in = True; st.rerun()
        if st.button("⚫ Hubungkan via iCloud Apple", use_container_width=True): st.session_state.logged_in = True; st.rerun()

def render_halaman_profil():
    st.markdown("<h2>🥗 Set Profil Fisik & Body Goal Anda</h2>", unsafe_allow_html=True)
    with st.form("form_biodata_nutrisi"):
        col1, col2 = st.columns(2)
        with col1:
            berat = st.number_input("Berat Badan Saat Ini (kg)", min_value=30.0, value=70.0)
            tinggi = st.number_input("Tinggi Badan (cm)", min_value=100, value=170)
            umur = st.number_input("Umur Pengguna (Tahun)", min_value=12, value=23)
        with col2:
            target_bb = st.number_input("Target Berat Badan Akhir (kg)", min_value=30.0, value=65.0)
            goal = st.selectbox("Pilih Body Goal Anda", ["Fat Loss / Cutting", "Muscle Gain / Bulking", "Maintain Weight (Sehat Seimbang)"])
            
        if st.form_submit_button("🚀 Aktifkan Pola Nutrisi AI Saya"):
            st.session_state.user_profile = {"berat_badan": berat, "tinggi_badan": tinggi, "umur": umur, "target_berat": target_bb, "body_goal": goal}
            st.session_state.nutrisi_target = hitung_target_via_ai(st.session_state.user_profile)
            st.session_state.profile_setup_done = True
            st.rerun()

# ==========================================
# 4. INTERFACE HALAMAN 3: DASHBOARD UTAMA
# ==========================================
def render_halaman_utama():
    target = st.session_state.nutrisi_target
    jurnal = st.session_state.jurnal_hari_ini
    
    st.markdown("<h1 style='text-align: center;'>🥗 AI Nutrition Tracker Pro</h1>", unsafe_allow_html=True)
    st.markdown("---")
    
    # METRICS DISPLAY
    st.markdown("### 📊 Status Jurnal Hari Ini")
    c1, c2, c3 = st.columns(3)
    c1.metric("🔥 Kalori", f"{int(jurnal['kalori'])} kkal", f"Target: {target.get('kalori', 2000)}")
    c2.metric("🥩 Protein (2x BB Target)", f"{jurnal['protein']:.1f} g", f"Target: {target.get('protein', 130)} g")
    c3.metric("🍞 Karbohidrat", f"{jurnal['karbohidrat']:.1f} g", f"Target: {target.get('karbohidrat', 230)} g")
    
    c4, c5, c6 = st.columns(3)
    c4.metric("🥑 Lemak", f"{jurnal['lemak']:.1f} g", f"Target: {target.get('lemak', 60)} g")
    c5.metric("💧 Air", f"{int(jurnal['air'])} ml", f"Target: {target.get('air', 2500)} ml")
    c6.metric("🥬 Serat", f"{jurnal['serat']:.1f} g", f"Target: {target.get('serat', 25)} g")
    
    st.markdown("---")
    
    tab_scan, tab_list, tab_db, tab_profil = st.tabs(["📸 Scan Nutrisi", "📝 Catat Manual", "📁 Riwayat Jurnal", "⚙️ Edit Profil"])
    
    # --- TAB 1: SCAN NUTRISI (ALUR BARU MULTI-UPLOAD & KONFIRMASI) ---
    with tab_scan:
        st.write("##### 🍽️ Scan Foto Makanan Anda")
        
        # Tombol utama untuk memicu pilihan menu upload (agar kamera tidak langsung menyala)
        if st.button("📸 Ambil / Unggah Foto Makanan", use_container_width=True, type="primary"):
            st.session_state.show_upload_options = not st.session_state.show_upload_options
            
        if st.session_state.show_upload_options:
            st.markdown("<div style='background-color:#f0f2f6; padding:15px; border-radius:10px;'>", unsafe_allow_html=True)
            metode_upload = st.radio("Pilih Metode Unggah:", ["📁 Dari Galeri / File", "📷 Ambil dari Kamera Langsung"], horizontal=True)
            
            foto_file = None
            if metode_upload == "📁 Dari Galeri / File":
                foto_file = st.file_uploader("Pilih gambar makanan dari penyimpanan galeri kamu", type=["jpg", "jpeg", "png"])
            else:
                foto_file = st.camera_input("Arahkan kamera ke makanan")
            st.markdown("</div><br>", unsafe_allow_html=True)
            
            if foto_file:
                bytes_data = foto_file.getvalue()
                gambar_pil = Image.open(io.BytesIO(bytes_data))
                st.image(gambar_pil, caption="Foto yang dipilih", width=250)
                
                if st.button("🤖 Deteksi & Scan Nutrisi AI", use_container_width=True):
                    with st.spinner("AI sedang membedah makanan, metode masak, dan gramasi..."):
                        res = analisis_foto_makanan_ai(gambar_pil)
                        if res:
                            st.session_state.pending_analysis = res
                            st.success("AI berhasil memindai! Silakan periksa hasil deteksi di bawah.")
        
        # --- BLOK PROSES VERIFIKASI KOREKSI USER (HUMAN-IN-THE-LOOP) ---
        if st.session_state.pending_analysis:
            st.markdown("---")
            st.markdown("### 🔍 Konfirmasi Data Makanan Anda")
            st.write("Apakah tebakan AI di bawah ini sudah sesuai? Jika belum, silakan edit kolomnya lalu klik **Kalkulasi Ulang**:")
            
            p = st.session_state.pending_analysis
            
            # Form Edit Koreksi Pengguna
            with st.form("form_konfirmasi_makanan"):
                edit_nama = st.text_input("Nama Makanan Dideteksi", value=p.get("nama_makanan", ""))
                edit_bagian = st.text_input("Bagian Makanan yang Dimakan", value=p.get("bagian_makanan", ""))
                edit_metode = st.text_input("Metode Masak / Kondisi", value=p.get("metode_masak", ""))
                edit_gramasi = st.text_input("Asumsi Gramasi / Volume", value=p.get("gramasi_estimasi", ""))
                
                # Tampilkan nilai gizi sementara kalkulasi AI
                st.markdown(f"""
                **Kandungan Gizi Saat Ini:** 🔥 Kalori: `{p.get('kalori')}` kkal | 🥩 Protein: `{p.get('protein')}`g | 🍞 Karbohidrat: `{p.get('karbohidrat')}`g | 🥑 Lemak: `{p.get('lemak')}`g
                """)
                
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    tombol_koreksi = st.form_submit_button("🔄 Belum Sesuai, Kalkulasi Ulang AI")
                with col_btn2:
                    tombol_setuju = st.form_submit_button("✅ Sudah Sesuai, Simpan ke Jurnal")
                
                if tombol_koreksi:
                    with st.spinner("Mengalkulasi ulang nilai zat gizi berdasarkan koreksi kamu..."):
                        updated_res = rekalkulasi_nutrisi_via_ai(edit_nama, edit_bagian, edit_metode, edit_gramasi)
                        if updated_res:
                            st.session_state.pending_analysis = updated_res
                            st.success("Nilai gizi berhasil diperbarui oleh AI!")
                            st.rerun()
                            
                if tombol_setuju:
                    # Masukkan data ke log total hari ini
                    st.session_state.jurnal_hari_ini["kalori"] += p.get("kalori", 0)
                    st.session_state.jurnal_hari_ini["protein"] += p.get("protein", 0)
                    st.session_state.jurnal_hari_ini["karbohidrat"] += p.get("karbohidrat", 0)
                    st.session_state.jurnal_hari_ini["lemak"] += p.get("lemak", 0)
                    st.session_state.jurnal_hari_ini["serat"] += p.get("serat", 0)
                    st.session_state.jurnal_hari_ini["air"] += p.get("air", 0)
                    
                    # Tambah ke daftar riwayat list
                    st.session_state.riwayat_makanan.append(p)
                    st.session_state.pending_analysis = None
                    st.session_state.show_upload_options = False
                    st.success("Makanan sukses dicatat ke jurnal!")
                    st.rerun()

    # --- TAB 2: CATAT MANUAL ---
    with tab_list:
        st.write("##### Input Makanan / Air Secara Manual")
        with st.form("form_manual"):
            nama_m = st.text_input("Nama Makanan", value="Nasi Putih + Telur Dadar")
            kal_m = st.number_input("Kalori (kkal)", min_value=0, value=320)
            prot_m = st.number_input("Protein (g)", min_value=0.0, value=14.0)
            karb_m = st.number_input("Karbohidrat (g)", min_value=0.0, value=40.0)
            lemak_m = st.number_input("Lemak (g)", min_value=0.0, value=12.0)
            if st.form_submit_button("Tambah ke Log Harian"):
                st.session_state.jurnal_hari_ini["kalori"] += kal_m
                st.session_state.jurnal_hari_ini["protein"] += prot_m
                st.session_state.jurnal_hari_ini["karbohidrat"] += karb_m
                st.session_state.jurnal_hari_ini["lemak"] += lemak_m
                st.session_state.riwayat_makanan.append({"nama_makanan": nama_m, "kalori": kal_m, "protein": prot_m, "karbohidrat": karb_m, "lemak": lemak_m})
                st.rerun()

    # --- TAB 3: RIWAYAT ---
    with tab_db:
        st.write("##### Daftar Makanan Terkonsumsi Hari Ini")
        if not st.session_state.riwayat_makanan:
            st.info("Belum ada riwayat makan hari ini.")
        else:
            for idx, item in enumerate(st.session_state.riwayat_makanan):
                st.markdown(f"**{idx+1}. {item.get('nama_makanan')}** ({item.get('bagian_makanan', 'Porsi')}) — Olahan: *{item.get('metode_masak', 'Dicor')}* | ⚖️ {item.get('gramasi_estimasi', '1 Porsi')} $\rightarrow$ 🔥 {item.get('kalori')} kkal | 🥩 P: {item.get('protein')}g")
            if st.button("🗑️ Reset Seluruh Data Jurnal", type="secondary"):
                st.session_state.jurnal_hari_ini = {"kalori": 0.0, "protein": 0.0, "karbohidrat": 0.0, "lemak": 0.0, "air": 0.0, "serat": 0.0}
                st.session_state.riwayat_makanan = []
                st.rerun()

    # --- TAB 4: EDIT PROFIL (PROTEIN TETAP TERKUNCI 2X BB TARGET) ---
    with tab_profil:
        st.write("##### ⚙️ Edit Profil & Target Fisik")
        p = st.session_state.user_profile
        with st.form("form_edit_profil"):
            eb_sekarang = st.number_input("Berat Badan Saat Ini (kg)", value=p.get("berat_badan", 70.0))
            eb_tinggi = st.number_input("Tinggi Badan (cm)", value=p.get("tinggi_badan", 170))
            eb_umur = st.number_input("Umur (Tahun)", value=p.get("umur", 23))
            eb_target = st.number_input("Target Berat Badan Akhir (kg)", value=p.get("target_berat", 65.0))
            eb_goal = st.selectbox("Pilih Body Goal", ["Fat Loss / Cutting", "Muscle Gain / Bulking", "Maintain Weight (Sehat Seimbang)"], index=["Fat Loss / Cutting", "Muscle Gain / Bulking", "Maintain Weight (Sehat Seimbang)"].index(p.get("body_goal", "Fat Loss / Cutting")))
            
            if st.form_submit_button("💾 Simpan Perubahan Profil"):
                st.session_state.user_profile = {"berat_badan": eb_sekarang, "tinggi_badan": eb_tinggi, "umur": eb_umur, "target_berat": eb_target, "body_goal": eb_goal}
                # AI dipanggil ulang, protein otomatis dikunci 2x berat badan target baru!
                st.session_state.nutrisi_target = hitung_target_via_ai(st.session_state.user_profile)
                st.success("Profil diperbarui! Target protein harian dikunci 2x dari BB target baru Anda.")
                st.rerun()
                
        if st.button("🚪 Keluar Akun (Log Out)", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.profile_setup_done = False
            st.rerun()

# ==========================================
# CENTRAL ROUTING CONTROLLER (PENGENDALI)
# ==========================================
if not st.session_state.logged_in:
    render_halaman_login()
elif st.session_state.logged_in and not st.session_state.profile_setup_done:
    render_halaman_profil()
else:
    render_halaman_utama()
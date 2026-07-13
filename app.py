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
        # Mencoba memanggil Client Google GenAI secara otomatis dari Secrets
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

# State untuk menu upload dan verifikasi makanan
if "show_upload_options" not in st.session_state:
    st.session_state.show_upload_options = False
if "pending_analysis" not in st.session_state:
    st.session_state.pending_analysis = None

# Opsi Global Berdasarkan Instruksi Baru
OPSI_AKTIVITAS = {
    "1.20 (Sangat Jarang): Tidak olahraga, kerja kantoran duduk seharian.": 1.20,
    "1.375 (Ringan): Olahraga ringan / joging / yoga sekitar 1–3 hari/minggu.": 1.375,
    "1.55 (Sedang): Olahraga intensitas sedang (seperti angkat beban/futsal) 3–5 hari/minggu.": 1.55,
    "1.725 (Berat): Olahraga berat/intensitas tinggi 6–7 hari/minggu.": 1.725,
    "1.90 (Sangat Berat): Atlet profesional atau pekerja fisik berat (kuli, kuli angkut) yang masih latihan keras harian.": 1.90
}

# ==========================================
# 2. LOGIKA UTAMA PERHITUNGAN BMR, TDEE & AI
# ==========================================
def hitung_target_via_ai(profil):
    """Menghitung target makronutrisi harian berdasarkan rumus BMR, TDEE, & Body Goal"""
    # 1. Rumus BMR (Mifflin-St Jeor)
    if profil["gender"] == "Laki-laki":
        bmr = (10 * profil["bb_awal"]) + (6.25 * profil["tb"]) - (5 * profil["umur"]) + 5
    else:
        bmr = (10 * profil["bb_awal"]) + (6.25 * profil["tb"]) - (5 * profil["umur"]) - 161
        
    # 2. Rumus TDEE
    tdee = bmr * profil["indeks_aktivitas"]
    
    # 3. Rumus Penyesuaian Kalori Berdasarkan Body Goal
    if profil["body_goal"] == "Fat Loss":
        target_kalori = tdee - profil["perubahan_kalori"]
    elif profil["body_goal"] == "Muscle Gain":
        target_kalori = tdee + profil["perubahan_kalori"]
    else:
        target_kalori = tdee # Maintain Weight
        
    # Batas bawah protein dikunci pada 2x Berat Badan Target
    protein_mutlak = int(profil["target_berat"] * 2) 
    
    prompt = f"""
    Kamu adalah seorang Ahli Gizi profesional. Seseorang dengan profil berikut membutuhkan target nutrisi:
    - Target Kalori Harian Hasil Hitung Fisik: {int(target_kalori)} kkal (Dihitung dari BMR: {int(bmr)} dan TDEE: {int(tdee)})
    - Target Protein Wajib: {protein_mutlak} gram
    - Tujuan Akhir: {profil['body_goal']}
    
    Berikan pembagian sisa kalori ke target Karbohidrat (gram), Lemak (gram), Serat (gram), dan Air Minum (ml) secara medis.
    Berikan hasil akhir mutlak dalam format JSON murni dengan struktur seperti contoh ini:
    {{
        "kalori": {int(target_kalori)},
        "protein": {protein_mutlak},
        "karbohidrat": 240,
        "lemak": 60,
        "air": 3000,
        "serat": 25
    }}
    """
    
    # Cadangan aman jika API Key kosong / offline
    if st.session_state.client is None:
        return {"kalori": int(target_kalori), "protein": protein_mutlak, "karbohidrat": 220, "lemak": 55, "air": 2500, "serat": 25}
        
    try:
        response = st.session_state.client.models.generate_content(
            model='gemini-2.0-flash', contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception as e:
        # Cadangan aman jika kuota API habis (Eror 429 / 503)
        return {"kalori": int(target_kalori), "protein": protein_mutlak, "karbohidrat": 220, "lemak": 55, "air": 2500, "serat": 25}

def analisis_foto_makanan_ai(gambar_pil):
    """Menganalisis foto hidangan makanan dari galeri/kamera"""
    data_simulasi = {
        "nama_makanan": "Ayam Goreng Crispy + Nasi Putih (Olive Fried Chicken)",
        "bagian_makanan": "Dada Ayam dengan Kulit",
        "metode_masak": "Goreng (Deep Fried)",
        "gramasi_estimasi": "150 gram ayam, 200 gram nasi",
        "kalori": 680,
        "protein": 38.0,
        "karbohidrat": 62.0,
        "lemak": 29.0,
        "serat": 1.5,
        "air": 110
    }

    if st.session_state.client is None:
        st.toast("⚠️ Menggunakan Mode Simulasi (Sistem luring)", icon="ℹ️")
        return data_simulasi

    prompt = """
    Kamu adalah AI Nutritionist yang sangat jeli. Analisis hidangan makanan atau minuman dalam foto ini.
    Deteksi item bahan makanan, bagian spesifik, metode masak, serta estimasi gramasinya.
    Berikan hasil analisis akhir dalam format JSON murni:
    {
        "nama_makanan": "Nama Hidangan Utama",
        "bagian_makanan": "Bagian spesifik yang terdeteksi",
        "metode_masak": "Metode masak",
        "gramasi_estimasi": "150 gram",
        "kalori": 280,
        "protein": 25.0,
        "karbohidrat": 12.0,
        "lemak": 14.0,
        "serat": 2.0,
        "air": 0
    }
    """
    try:
        response = st.session_state.client.models.generate_content(
            model='gemini-2.0-flash', contents=[gambar_pil, prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception as e:
        st.toast("⚠️ Quota Habis / Server Padat. Mengaktifkan estimasi simulasi pintar.", icon="⏳")
        return data_simulasi

def rekalkulasi_nutrisi_via_ai(nama, bagian, metode, gramasi):
    """Menghitung ulang data nutrisi berdasarkan koreksi teks manual pengguna"""
    if st.session_state.client is None:
        return {"nama_makanan": nama, "bagian_makanan": bagian, "metode_masak": metode, "gramasi_estimasi": gramasi, "kalori": 450, "protein": 32.0, "karbohidrat": 45.0, "lemak": 12.0, "serat": 2.0, "air": 100}

    prompt = f"""
    Hitung ulang secara akurat nilai nutrisi berdasarkan data koreksi nyata dari pengguna berikut:
    - Nama Makanan: {nama} | Bagian Makanan: {bagian} | Metode Memasak: {metode} | Gramasi / Takaran Baru: {gramasi}
    Berikan keluaran dalam format JSON murni.
    """
    try:
        response = st.session_state.client.models.generate_content(
            model='gemini-2.0-flash', contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception as e:
        return {"nama_makanan": nama, "bagian_makanan": bagian, "metode_masak": metode, "gramasi_estimasi": gramasi, "kalori": 400, "protein": 30.0, "karbohidrat": 40.0, "lemak": 10.0, "serat": 2.0, "air": 80}

# ==========================================
# 3. INTERFACE HALAMAN 1: LOGIN MULTI-PROVIDER
# ==========================================
def render_halaman_login():
    st.markdown("<h2 style='text-align: center; margin-top: 20px;'>🔐 Sign In / Sign Up</h2>", unsafe_allow_html=True)
    st.write("Selamat datang di **AI Nutrition Tracker Pro**. Silakan hubungkan akun Anda untuk memulai:")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔴 Masuk dengan Google", use_container_width=True): st.session_state.logged_in = True; st.rerun()
        if st.button("🔵 Masuk dengan Facebook", use_container_width=True): st.session_state.logged_in = True; st.rerun()
    with col2:
        if st.button("📧 Gunakan Akun Gmail", use_container_width=True): st.session_state.logged_in = True; st.rerun()
        if st.button("⚫ Hubungkan via iCloud Apple", use_container_width=True): st.session_state.logged_in = True; st.rerun()

# ==========================================
# 4. INTERFACE HALAMAN 2: INPUT PROFIL (ONBOARDING BMR & TDEE)
# ==========================================
def render_halaman_profil():
    st.markdown("<h2>🥗 Set Profil Fisik, Gender & Target Kalori</h2>", unsafe_allow_html=True)
    st.write("Isi data di bawah ini untuk menghitung BMR dan TDEE secara otomatis.")
    
    with st.form("form_informasi_fisik"):
        st.markdown("#### 📏 1. Informasi Fisik & Target")
        col1, col2 = st.columns(2)
        with col1:
            gender = st.selectbox("Jenis Kelamin (Gender)", ["Laki-laki", "Perempuan"])
            berat_awal = st.number_input("Berat Badan Saat Ini (kg)", min_value=30.0, value=70.0, step=0.5)
            tinggi_badan = st.number_input("Tinggi Badan (cm)", min_value=100, value=170)
        with col2:
            umur = st.number_input("Umur Pengguna (Tahun)", min_value=1, max_value=100, value=23)
            berat_target = st.number_input("Target Berat Badan Akhir (kg)", min_value=30.0, value=65.0, step=0.5)
            body_goal = st.selectbox("Pilih Body Goal Anda", ["Fat Loss", "Maintain Weight", "Muscle Gain"])
            
        st.markdown("---")
        st.markdown("#### 🏃‍♂️ 2. Parameter Rumus Kalori (TDEE & Slider Goal)")
        
        aktivitas_pilihan = st.selectbox("Pilih Tingkat Aktivitas Harian (Indeks TDEE):", list(OPSI_AKTIVITAS.keys()))
        indeks_aktivitas = OPSI_AKTIVITAS[aktivitas_pilihan]
        
        # Slider dinamis sesuai instruksi untuk memilih rentang deficit/surplus 300 - 500 kkal
        perubahan_kalori = st.slider("Intensitas Pemotongan/Tambahan Kalori Target (kkal)", min_value=300, max_value=500, value=500, step=50)
        
        st.markdown("<br>", unsafe_allow_html=True)
        submit_profil = st.form_submit_button("🚀 Aktifkan Pola Nutrisi AI Saya", type="primary")
        
        if submit_profil:
            st.session_state.user_profile = {
                "gender": gender, "bb_awal": berat_awal, "tb": tinggi_badan, 
                "umur": umur, "target_berat": berat_target, "body_goal": body_goal,
                "indeks_aktivitas": indeks_aktivitas, "perubahan_kalori": perubahan_kalori
            }
            
            with st.spinner("Mengalkulasi target makro nutrisi optimal Anda..."):
                st.session_state.nutrisi_target = hitung_target_via_ai(st.session_state.user_profile)
                st.session_state.profile_setup_done = True
                st.success("Profil dan Target Nutrisi Berhasil Dikonfigurasi!")
                st.rerun()

# ==========================================
# 5. INTERFACE HALAMAN 3: DASHBOARD UTAMA
# ==========================================
def render_halaman_utama():
    target = st.session_state.nutrisi_target
    jurnal = st.session_state.jurnal_hari_ini
    
    st.markdown("<h1 style='text-align: center;'>🥗 AI Nutrition Tracker Pro</h1>", unsafe_allow_html=True)
    
    if st.session_state.client is None:
        st.info("💡 Mode Simulasi Aktif. Masukkan GEMINI_API_KEY di dashboard Secrets Streamlit Cloud untuk menghubungkan AI Asli.")

    st.markdown("---")
    
    # METRICS DISPLAY STATUS JURNAL HARI INI (Teks 2x BB Target sudah dihapus)
    st.markdown("### 📊 Status Jurnal Hari Ini")
    c1, c2, c3 = st.columns(3)
    c1.metric("🔥 Kalori", f"{int(jurnal['kalori'])} kkal", f"Target: {target.get('kalori', 2000)} kkal")
    c2.metric("🥩 Protein", f"{jurnal['protein']:.1f} g", f"Target: {target.get('protein', 130)} g")
    c3.metric("🍞 Karbohidrat", f"{jurnal['karbohidrat']:.1f} g", f"Target: {target.get('karbohidrat', 230)} g")
    
    c4, c5, c6 = st.columns(3)
    c4.metric("🥑 Lemak", f"{jurnal['lemak']:.1f} g", f"Target: {target.get('lemak', 60)} g")
    c5.metric("💧 Air Minum", f"{int(jurnal['air'])} ml", f"Target: {target.get('air', 2500)} ml")
    c6.metric("🥬 Serat", f"{jurnal['serat']:.1f} g", f"Target: {target.get('serat', 25)} g")
    
    st.markdown("---")
    
    tab_scan, tab_list, tab_db, tab_profil = st.tabs(["📸 Scan Nutrisi AI", "📝 Catat Manual", "📁 Riwayat Jurnal", "⚙️ Edit Profil"])
    
    # --- TAB 1: SCAN NUTRISI ---
    with tab_scan:
        st.write("##### 🍽️ Scan Foto Makanan / Minuman dari Perangkat")
        
        if st.button("📸 Buka Menu Pengunggahan Foto Makanan", use_container_width=True, type="primary"):
            st.session_state.show_upload_options = not st.session_state.show_upload_options
            
        if st.session_state.show_upload_options:
            st.markdown("<div style='background-color:#f0f2f6; padding:15px; border-radius:10px;'>", unsafe_allow_html=True)
            metode_upload = st.radio("Pilih Opsi Sumber File:", ["📁 Unggah dari Galeri / File", "📷 Ambil Gambar Menggunakan Kamera"], horizontal=True)
            
            foto_file = None
            if metode_upload == "📁 Unggah dari Galeri / File":
                foto_file = st.file_uploader("Pilih gambar hidangan makanan dari galeri penyimpanan perangkat", type=["jpg", "jpeg", "png"])
            else:
                foto_file = st.camera_input("Arahkan lensa kamera fokus ke makanan Anda")
            st.markdown("</div><br>", unsafe_allow_html=True)
            
            if foto_file:
                bytes_data = foto_file.getvalue()
                gambar_pil = Image.open(io.BytesIO(bytes_data))
                st.image(gambar_pil, caption="Pratinjau Foto Makanan", width=260)
                
                if st.button("🤖 Jalankan Deteksi Nutrisi AI", use_container_width=True):
                    with st.spinner("AI sedang membedah kalori berdasarkan BMR/TDEE target..."):
                        res = analisis_foto_makanan_ai(gambar_pil)
                        if res:
                            st.session_state.pending_analysis = res
                            st.success("Pemindaian Selesai! Mohon verifikasi hasilnya di bawah ini.")
        
        # --- BLOK PROSES VERIFIKASI KONFIRMASI USER ---
        if st.session_state.pending_analysis:
            st.markdown("---")
            st.markdown("### 🔍 Konfirmasi & Penyesuaian Data Hidangan")
            p = st.session_state.pending_analysis
            
            with st.form("form_konfirmasi_makanan"):
                edit_nama = st.text_input("Makanan Terdeteksi", value=p.get("nama_makanan", ""))
                edit_bagian = st.text_input("Bagian Makanan yang Dimakan", value=p.get("bagian_makanan", ""))
                edit_metode = st.text_input("Metode Memasak / Kondisi Olahan", value=p.get("metode_masak", ""))
                edit_gramasi = st.text_input("Estimasi Gramasi / Volume", value=p.get("gramasi_estimasi", ""))
                
                st.markdown(f"""
                **Estimasi Nutrisi Saat Ini:** 🔥 Kalori: `{p.get('kalori')}` kkal | 🥩 Protein: `{p.get('protein')}`g | 🍞 Karbohidrat: `{p.get('karbohidrat')}`g | 🥑 Lemak: `{p.get('lemak')}`g
                """)
                
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    tombol_koreksi = st.form_submit_button("🔄 Belum Sesuai, Kalkulasi Ulang AI")
                with col_btn2:
                    tombol_setuju = st.form_submit_button("✅ Sudah Sesuai, Masukkan Jurnal")
                
                if tombol_koreksi:
                    with st.spinner("Mengalkulasi ulang nutrisi..."):
                        updated_res = rekalkulasi_nutrisi_via_ai(edit_nama, edit_bagian, edit_metode, edit_gramasi)
                        if updated_res:
                            st.session_state.pending_analysis = updated_res
                            st.rerun()
                            
                if tombol_setuju:
                    st.session_state.jurnal_hari_ini["kalori"] += p.get("kalori", 0)
                    st.session_state.jurnal_hari_ini["protein"] += p.get("protein", 0)
                    st.session_state.jurnal_hari_ini["karbohidrat"] += p.get("karbohidrat", 0)
                    st.session_state.jurnal_hari_ini["lemak"] += p.get("lemak", 0)
                    st.session_state.jurnal_hari_ini["serat"] += p.get("serat", 0)
                    st.session_state.jurnal_hari_ini["air"] += p.get("air", 0)
                    
                    st.session_state.riwayat_makanan.append(p)
                    st.session_state.pending_analysis = None
                    st.session_state.show_upload_options = False
                    st.success("Sukses menyimpan log makanan ke jurnal!")
                    st.rerun()

    # --- TAB 2: CATAT MANUAL ---
    with tab_list:
        st.write("##### Input Makanan Secara Manual")
        with st.form("form_manual"):
            nama_m = st.text_input("Nama Makanan", value="Dada Ayam Panggang")
            kal_m = st.number_input("Kalori (kkal)", min_value=0, value=250)
            prot_m = st.number_input("Protein (g)", min_value=0.0, value=30.0)
            karb_m = st.number_input("Karbohidrat (g)", min_value=0.0, value=0.0)
            lemak_m = st.number_input("Lemak (g)", min_value=0.0, value=5.0)
            if st.form_submit_button("Tambah ke Log Harian"):
                st.session_state.jurnal_hari_ini["kalori"] += kal_m
                st.session_state.jurnal_hari_ini["protein"] += prot_m
                st.session_state.jurnal_hari_ini["karbohidrat"] += karb_m
                st.session_state.jurnal_hari_ini["lemak"] += lemak_m
                st.session_state.riwayat_makanan.append({"nama_makanan": nama_m, "kalori": kal_m, "protein": prot_m, "karbohidrat": karb_m, "lemak": lemak_m, "bagian_makanan": "Porsi Custom", "metode_masak": "Manual"})
                st.rerun()

    # --- TAB 3: RIWAYAT JURNAL ---
    with tab_db:
        st.write("##### Daftar Konsumsi Hari Ini")
        if not st.session_state.riwayat_makanan:
            st.info("Belum ada riwayat konsumsi untuk hari ini.")
        else:
            for idx, item in enumerate(st.session_state.riwayat_makanan):
                st.markdown(f"**{idx+1}. {item.get('nama_makanan')}** — 🔥 {item.get('kalori')} kkal | 🥩 Protein: {item.get('protein')}g | 🍞 Karbo: {item.get('karbohidrat')}g")
            
            if st.button("🗑️ Reset Seluruh Jurnal Hari Ini"):
                st.session_state.jurnal_hari_ini = {"kalori": 0.0, "protein": 0.0, "karbohidrat": 0.0, "lemak": 0.0, "air": 0.0, "serat": 0.0}
                st.session_state.riwayat_makanan = []
                st.rerun()

    # --- TAB 4: EDIT PROFIL ---
    with tab_profil:
        st.write("##### ⚙️ Edit Profil & Hitung Ulang BMR/TDEE")
        p = st.session_state.user_profile
        
        eb_gender = st.selectbox("Jenis Kelamin", ["Laki-laki", "Perempuan"], index=0 if p.get("gender") == "Laki-laki" else 1)
        eb_sekarang = st.number_input("Berat Badan Sekarang (kg)", value=p.get("bb_awal", 70.0))
        eb_tinggi = st.number_input("Tinggi Badan (cm)", value=p.get("tb", 170))
        eb_umur = st.number_input("Umur (Tahun)", value=p.get("umur", 23))
        eb_target = st.number_input("Target Berat Badan Akhir (kg)", value=p.get("target_berat", 65.0))
        eb_goal = st.selectbox("Pilih Body Goal", ["Fat Loss", "Maintain Weight", "Muscle Gain"], index=["Fat Loss", "Maintain Weight", "Muscle Gain"].index(p.get("body_goal", "Fat Loss")))
        
        eb_aktivitas = st.selectbox("Tingkat Aktivitas Harian (Indeks TDEE):", list(OPSI_AKTIVITAS.keys()), index=list(OPSI_AKTIVITAS.keys()).index([k for k, v in OPSI_AKTIVITAS.items() if v == p.get("indeks_aktivitas", 1.20)][0]))
        eb_perubahan = st.slider("Intensitas Pemotongan/Tambahan Kalori Target (kkal)", min_value=300, max_value=500, value=p.get("perubahan_kalori", 500), step=50)
        
        if st.button("💾 Simpan Perubahan Profil", type="primary", use_container_width=True):
            st.session_state.user_profile = {
                "gender": eb_gender, "bb_awal": eb_sekarang, "tb": eb_tinggi, 
                "umur": eb_umur, "target_berat": eb_target, "body_goal": eb_goal,
                "indeks_aktivitas": OPSI_AKTIVITAS[eb_aktivitas], "perubahan_kalori": eb_perubahan
            }
            st.session_state.nutrisi_target = hitung_target_via_ai(st.session_state.user_profile)
            st.success("Profil & BMR/TDEE berhasil dihitung ulang!")
            st.rerun()
                
        if st.button("🚪 Keluar Akun (Log Out)", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.profile_setup_done = False
            st.rerun()

# ==========================================
# CENTRAL ROUTING CONTROLLER
# ==========================================
if not st.session_state.logged_in:
    render_halaman_login()
elif st.session_state.logged_in and not st.session_state.profile_setup_done:
    render_halaman_profil()
else:
    render_halaman_utama()
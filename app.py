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

# State untuk menu upload dan verifikasi makanan
if "show_upload_options" not in st.session_state:
    st.session_state.show_upload_options = False
if "pending_analysis" not in st.session_state:
    st.session_state.pending_analysis = None

# ==========================================
# 2. LOGIKA UTAMA PERHITUNGAN BMR & TARGET VIA AI
# ==========================================
def hitung_target_via_ai(profil):
    """Menghitung target makronutrisi harian berdasarkan rumus BMR lokal dan pemilihan indeks TDEE otomatis oleh AI"""
    # 1. Rumus BMR Medis (Mifflin-St Jeor) secara lokal
    if profil["gender"] == "Laki-laki":
        bmr_lokal = (10 * profil["bb_awal"]) + (6.25 * profil["tb"]) - (5 * profil["umur"]) + 5
    else:
        bmr_lokal = (10 * profil["bb_awal"]) + (6.25 * profil["tb"]) - (5 * profil["umur"]) - 161
        
    # Kunci batas bawah protein aman (2x target berat badan)
    protein_mutlak = int(profil["target_berat"] * 2) 
    
    # Menyusun teks daftar checklist olahraga & kegiatan untuk dibaca AI
    teks_aktivitas = ""
    for act, freq in profil.get("aktivitas", {}).items():
        teks_aktivitas += f"- {act}: {freq} kali per minggu\n"
    if not teks_aktivitas:
        teks_aktivitas = "- Tidak ada aktivitas olahraga rutin (Sedentary/Kerja duduk)\n"
        
    prompt = f"""
    Kamu adalah seorang Ahli Gizi profesional. Tugasmu adalah menentukan faktor aktivitas (indeks TDEE) secara cerdas dan membagi makronutrisi.
    
    Data Fisik & Kegiatan User:
    - Jenis Kelamin: {profil['gender']}
    - BMR Hasil Hitung: {int(bmr_lokal)} kkal
    - Body Goal: {profil['body_goal']}
    - Intensitas Modifikasi Kalori: {profil['perubahan_kalori']} kkal
    - Daftar Kegiatan Fisik Nyata User:
    {teks_aktivitas}
    
    ATURAN MATEMATIKA STRUKTUR KALORI:
    1. Berdasarkan kegiatan fisik di atas, pilihlah satu Angka Indeks Aktivitas yang paling logis dan sesuai panduan klinis:
       * 1.20 -> Tidak olahraga, kerja kantoran duduk seharian.
       * 1.375 -> Olahraga ringan / joging / yoga sekitar 1–3 hari/minggu.
       * 1.55 -> Olahraga intensitas sedang (seperti angkat beban/futsal) 3–5 hari/minggu.
       * 1.725 -> Olahraga berat/intensitas tinggi 6–7 hari/minggu.
       * 1.90 -> Atlet profesional atau pekerja fisik berat (kuli, kuli angkut) + latihan keras harian.
    2. Hitung TDEE = BMR ({int(bmr_lokal)}) x [Angka Indeks Aktivitas Pilihanmu].
    3. Hitung Target Kalori Akhir berdasarkan Body Goal:
       * Jika "Fat Loss" -> Target = TDEE - {profil['perubahan_kalori']}
       * Jika "Muscle Gain" -> Target = TDEE + {profil['perubahan_kalori']}
       * Jika "Maintain Weight (Recomposition)" -> Target = TDEE (Tanpa ditambah/dikurang)
    4. Target Protein Wajib = {protein_mutlak} gram.
    
    Berikan hasil kalkulasi akhir dalam bentuk JSON murni tanpa hiasan Markdown markdown lain, dengan struktur persis seperti ini:
    {{
        "indeks_aktivitas_terpilih": 1.55,
        "tdee_kalkulasi": 2400,
        "kalori": 1900,
        "protein": {protein_mutlak},
        "karbohidrat": 210,
        "lemak": 55,
        "air": 3000,
        "serat": 25
    }}
    """
    
    # Cadangan aman jika offline/simulasi
    default_kalori = int(bmr_lokal * 1.375)
    if profil["body_goal"] == "Fat Loss": default_kalori -= profil["perubahan_kalori"]
    elif profil["body_goal"] == "Muscle Gain": default_kalori += profil["perubahan_kalori"]

    if st.session_state.client is None:
        return {"indeks_aktivitas_terpilih": 1.375, "tdee_kalkulasi": int(bmr_lokal * 1.375), "kalori": default_kalori, "protein": protein_mutlak, "karbohidrat": 200, "lemak": 50, "air": 2500, "serat": 25}
        
    try:
        response = st.session_state.client.models.generate_content(
            model='gemini-2.0-flash', contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception as e:
        return {"indeks_aktivitas_terpilih": 1.375, "tdee_kalkulasi": int(bmr_lokal * 1.375), "kalori": default_kalori, "protein": protein_mutlak, "karbohidrat": 200, "lemak": 50, "air": 2500, "serat": 25}

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
        return data_simulasi
    prompt = "Kamu adalah AI Nutritionist. Analisis hidangan ini dan berikan output format JSON murni nutrisi lengkap."
    try:
        response = st.session_state.client.models.generate_content(
            model='gemini-2.0-flash', contents=[gambar_pil, prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception as e:
        return data_simulasi

def rekalkulasi_nutrisi_via_ai(nama, bagian, metode, gramasi):
    """Menghitung ulang data nutrisi berdasarkan koreksi teks manual pengguna"""
    if st.session_state.client is None:
        return {"nama_makanan": nama, "bagian_makanan": bagian, "metode_masak": metode, "gramasi_estimasi": gramasi, "kalori": 450, "protein": 32.0, "karbohidrat": 45.0, "lemak": 12.0, "serat": 2.0, "air": 100}
    prompt = f"Hitung ulang nutrisi secara akurat dalam JSON murni untuk: {nama} {bagian} {metode} {gramasi}."
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
# 4. INTERFACE HALAMAN 2: INPUT PROFIL & CHECKLIST AKTIVITAS
# ==========================================
def render_halaman_profil():
    st.markdown("<h2>🥗 Set Profil Fisik & Checklist Kegiatan Harian</h2>", unsafe_allow_html=True)
    st.write("Isi data fisik dan centang olahraga Anda. AI akan otomatis menentukan nilai pengali TDEE medis Anda.")
    
    with st.form("form_informasi_fisik"):
        st.markdown("#### 📏 1. Informasi Fisik Dasar")
        col1, col2 = st.columns(2)
        with col1:
            gender = st.selectbox("Jenis Kelamin", ["Laki-laki", "Perempuan"])
            berat_awal = st.number_input("Berat Badan Sekarang (kg)", min_value=30.0, value=70.0, step=0.5)
            tinggi_badan = st.number_input("Tinggi Badan (cm)", min_value=100, value=170)
        with col2:
            umur = st.number_input("Umur Anda (Tahun)", min_value=1, max_value=100, value=24)
            berat_target = st.number_input("Target Berat Badan Akhir (kg)", min_value=30.0, value=65.0, step=0.5)
            body_goal = st.selectbox("Pilih Body Goal", ["Fat Loss", "Maintain Weight (Recomposition)", "Muscle Gain"])
            
        st.markdown("---")
        st.markdown("#### 🏃‍♂️ 2. Checklist Aktivitas Fisik & Frekuensi (AI Auto-TDEE Selector)")
        st.write("Centang semua jenis latihan/kegiatan fisik yang biasa Anda lakukan dalam seminggu:")
        
        # Mengembalikan fitur checklist interaktif
        act_kantor = st.checkbox("Kerja kantoran / Duduk seharian di meja komputer")
        act_ringan = st.checkbox("Olahraga Ringan (Joging santai / Jalan kaki rutin / Yoga ringan)")
        act_beban = st.checkbox("Latihan Angkat Beban (Weight Training / Gym Intensitas Sedang)")
        act_kardio = st.checkbox("Olahraga Kardio Intens (Futsal / Basket / Renang / Bersepeda Cepat)")
        act_berat = st.checkbox("Pekerja Fisik Berat (Kuli bangunan, Kuli angkut barang, Atlet Profesional)")
        
        st.write("Tentukan frekuensi latihan gabungan di atas dalam seminggu:")
        frekuensi_latihan = st.number_input("Berapa hari Anda aktif berlatih dalam 1 minggu?", min_value=0, max_value=7, value=3)
        
        # Slider dinamis deficit/surplus
        perubahan_kalori = st.slider("Intensitas Surplus/Defisit Kalori Harian (Tidak berefek pada Maintain Weight)", min_value=300, max_value=500, value=500, step=50)
        
        submit_profil = st.form_submit_button("🚀 Hitung Pola Nutrisi & Target AI", type="primary")
        
        if submit_profil:
            # Mengompilasi aktivitas yang dichecklist ke dictionary
            daftar_aktifitas_dipilih = {}
            if act_kantor: daftar_aktifitas_dipilih["Kerja Kantoran Duduk"] = "Setiap hari kerja"
            if act_ringan: daftar_aktifitas_dipilih["Olahraga Ringan/Yoga"] = f"{frekuensi_latihan} hari/minggu"
            if act_beban: daftar_aktifitas_dipilih["Angkat Beban / Gym"] = f"{frekuensi_latihan} hari/minggu"
            if act_kardio: daftar_aktifitas_dipilih["Kardio Intens (Futsal/Renang)"] = f"{frekuensi_latihan} hari/minggu"
            if act_berat: daftar_aktifitas_dipilih["Pekerja Fisik Berat/Atlet"] = "Setiap hari harian"
            
            st.session_state.user_profile = {
                "gender": gender, "bb_awal": berat_awal, "tb": tinggi_badan, 
                "umur": umur, "target_berat": berat_target, "body_goal": body_goal,
                "aktivitas": daftar_aktifitas_dipilih, "perubahan_kalori": perubahan_kalori
            }
            
            with st.spinner("Gemini AI sedang menganalisis tingkat TDEE & menyusun makronutrisi..."):
                st.session_state.nutrisi_target = hitung_target_via_ai(st.session_state.user_profile)
                st.session_state.profile_setup_done = True
                st.success("Profil Fisik & Analisis TDEE Sukses Dikonfigurasi!")
                st.rerun()

# ==========================================
# 5. INTERFACE HALAMAN 3: DASHBOARD UTAMA
# ==========================================
def render_halaman_utama():
    target = st.session_state.nutrisi_target
    jurnal = st.session_state.jurnal_hari_ini
    profil = st.session_state.user_profile
    
    st.markdown("<h1 style='text-align: center;'>🥗 AI Nutrition Tracker Pro</h1>", unsafe_allow_html=True)
    
    # Notifikasi Informasi deteksi faktor indeks aktivitas dari AI
    with st.expander("ℹ️ Detail Hasil Analisis Metabolisme Tubuh (AI-Generated)"):
        st.write(f"**Tipe Target:** {profil.get('body_goal')}")
        st.write(f"**Indeks TDEE Dipilih AI:** {target.get('indeks_aktivitas_terpilih', '1.375')}")
        st.write(f"**Estimasi Energi TDEE Anda:** {target.get('tdee_kalkulasi', 2200)} kkal/hari")
    
    st.markdown("---")
    
    # METRICS DISPLAY (Tulisan 2x BB Target sudah dihapus total)
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
                    with st.spinner("AI menganalisis komponen nutrisi makro hidangan..."):
                        res = analisis_foto_makanan_ai(gambar_pil)
                        if res:
                            st.session_state.pending_analysis = res
                            st.success("Pemindaian Selesai! Mohon verifikasi hasilnya di bawah ini.")
        
        if st.session_state.pending_analysis:
            st.markdown("---")
            st.markdown("### 🔍 Konfirmasi & Penyesuaian Data Hidangan")
            p = st.session_state.pending_analysis
            
            with st.form("form_konfirmasi_makanan"):
                edit_nama = st.text_input("Makanan Terdeteksi", value=p.get("nama_makanan", ""))
                edit_bagian = st.text_input("Bagian Makanan yang Dimakan", value=p.get("bagian_makanan", ""))
                edit_metode = st.text_input("Metode Memasak / Kondisi Olahan", value=p.get("metode_masak", ""))
                edit_gramasi = st.text_input("Estimasi Gramasi / Volume", value=p.get("gramasi_estimasi", ""))
                
                st.markdown(f"**Estimasi Nutrisi Saat Ini:** 🔥 Kalori: `{p.get('kalori')}` kkal | 🥩 Protein: `{p.get('protein')}`g | 🍞 Karbohidrat: `{p.get('karbohidrat')}`g | 🥑 Lemak: `{p.get('lemak')}`g")
                
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1: tombol_koreksi = st.form_submit_button("🔄 Belum Sesuai, Kalkulasi Ulang AI")
                with col_btn2: tombol_setuju = st.form_submit_button("✅ Sudah Sesuai, Masukkan Jurnal")
                
                if tombol_koreksi:
                    with st.spinner("Mengalkulasi ulang nutrisi..."):
                        updated_res = rekalkulasi_nutrisi_via_ai(edit_nama, edit_bagian, edit_metode, edit_gramasi)
                        if updated_res:
                            st.session_state.pending_analysis = updated_res
                            st.rerun()
                            
                if tombol_setuju:
                    for key in ["kalori", "protein", "karbohidrat", "lemak", "serat", "air"]:
                        st.session_state.jurnal_hari_ini[key] += p.get(key, 0)
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

    # --- TAB 4: RESET PROFIL ---
    with tab_profil:
        st.write("##### ⚙️ Reset Akun & Profil")
        st.write("Jika ingin menghitung ulang data fisik atau mengubah checklist kegiatan awal dari awal, silakan gunakan tombol log out di bawah ini:")
        if st.button("🚪 Keluar Akun & Reset Profil", use_container_width=True, type="primary"):
            st.session_state.logged_in = False
            st.session_state.profile_setup_done = False
            st.session_state.user_profile = {}
            st.session_state.nutrisi_target = {}
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

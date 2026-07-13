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

if "show_upload_options" not in st.session_state:
    st.session_state.show_upload_options = False
if "pending_analysis" not in st.session_state:
    st.session_state.pending_analysis = None

# Katalog Daftar Aktivitas untuk Checklist Dinamis
KATALOG_AKTIVITAS = {
    "🌱 Olahraga Ringan": [
        "Joging santai", "Jalan kaki rutin", "Yoga ringan", "Pilates"
    ],
    "🏃‍♂️ Olahraga Intensitas Sedang & Permainan": [
        "Angkat beban / Gym", "Futsal", "Sepak bola", "Basket", 
        "Badminton", "Renang", "Bersepeda"
    ],
    "🏗️ Pekerjaan & Aktivitas Fisik Berat": [
        "Kuli bangunan", "Kuli angkat barang", "Atlet profesional (Latihan harian intens)", "Latihan fisik keras harian lainnya"
    ]
}

# ==========================================
# 2. HELPER RENDER CHECKLIST AKTIVITAS DINAMIS
# ==========================================
def render_checklist_aktivitas(prefix_key, profil_existing={}):
    """Menampilkan checklist di mana tiap aktivitas punya input frekuensi individual"""
    st.write("Centang aktivitas yang biasa Anda lakukan dan tentukan frekuensinya per minggu:")
    st.caption("💡 *Jika tidak ada aktivitas yang dicentang, TDEE otomatis dihitung sebagai 1.20 (Kerja kantoran duduk seharian).*")
    
    aktivitas_terpilih = {}
    existing_acts = profil_existing.get("aktivitas", {})
    
    for kategori, daftar_act in KATALOG_AKTIVITAS.items():
        st.markdown(f"**{kategori}**")
        for act in daftar_act:
            is_checked_default = act in existing_acts
            checked = st.checkbox(act, value=is_checked_default, key=f"chk_{act}_{prefix_key}")
            
            if checked:
                default_freq = existing_acts.get(act, 2)
                freq = st.number_input(
                    f"└─ Berapa kali/minggu melakukan {act}?", 
                    min_value=1, max_value=14, value=int(default_freq), step=1,
                    key=f"freq_{act}_{prefix_key}"
                )
                aktivitas_terpilih[act] = freq
    return aktivitas_terpilih

# ==========================================
# 3. LOGIKA UTAMA PERHITUNGAN BMR & TARGET VIA AI
# ==========================================
def hitung_target_via_ai(profil):
    """Menghitung target nutrisi, menentukan indeks TDEE berdasarkan aktivitas individual via AI"""
    # 1. Rumus BMR Medis (Mifflin-St Jeor)
    if profil["gender"] == "Laki-laki":
        bmr_lokal = (10 * profil["bb_awal"]) + (6.25 * profil["tb"]) - (5 * profil["umur"]) + 5
    else:
        bmr_lokal = (10 * profil["bb_awal"]) + (6.25 * profil["tb"]) - (5 * profil["umur"]) - 161
        
    protein_mutlak = int(profil["target_berat"] * 2) 
    
    # Evaluasi Aktivitas
    daftar_act = profil.get("aktivitas", {})
    if not daftar_act:
        teks_aktivitas = "- TIDAK ADA AKTIVITAS DIPILIH. Wajib gunakan indeks TDEE 1.20 (Sedentary/Duduk seharian).\n"
        fallback_index = 1.20
    else:
        teks_aktivitas = ""
        total_freq = 0
        for act, freq in daftar_act.items():
            teks_aktivitas += f"- {act}: {freq} kali per minggu\n"
            total_freq += freq
            
        # Estimasi fallback lokal jika AI offline
        if total_freq <= 2: fallback_index = 1.375
        elif total_freq <= 5: fallback_index = 1.55
        elif total_freq <= 7: fallback_index = 1.725
        else: fallback_index = 1.90
        
    prompt = f"""
    Kamu adalah Ahli Gizi Klinis. Tugasmu adalah menentukan Faktor Aktivitas (Indeks TDEE) secara presisi dan menyusun makronutrisi.
    
    Data Fisik & Kegiatan User:
    - Jenis Kelamin: {profil['gender']} | Umur: {profil['umur']} tahun
    - BMR Hasil Hitung Medis: {int(bmr_lokal)} kkal
    - Body Goal: {profil['body_goal']}
    - Intensitas Defisit/Surplus Kalori: {profil['perubahan_kalori']} kkal
    - Daftar Aktivitas Fisik & Frekuensi Nyata User:
    {teks_aktivitas}
    
    ATURAN PENENTUAN INDEKS TDEE:
    1. Evaluasi seluruh daftar aktivitas di atas. Pilih SATU angka indeks TDEE medis yang paling pas:
       * 1.20 -> Tidak olahraga, kerja kantoran duduk seharian (Wajib pilih ini jika daftar aktivitas kosong/tidak ada).
       * 1.375 -> Olahraga ringan / joging / yoga sekitar 1–3 hari/minggu.
       * 1.55 -> Olahraga intensitas sedang (seperti angkat beban, futsal, basket, badminton) total 3–5 hari/minggu.
       * 1.725 -> Olahraga berat/intensitas tinggi 6–7 hari/minggu.
       * 1.90 -> Atlet profesional atau pekerja fisik berat (kuli bangunan, kuli angkut) + latihan keras harian.
    2. Hitung TDEE = BMR ({int(bmr_lokal)}) x [Indeks TDEE Pilihanmu].
    3. Hitung Target Kalori Akhir berdasarkan Body Goal:
       * Jika "Fat Loss" -> Target = TDEE - {profil['perubahan_kalori']}
       * Jika "Muscle Gain" -> Target = TDEE + {profil['perubahan_kalori']}
       * Jika "Maintain Weight (Recomposition)" -> Target = TDEE (Tanpa dikurang/ditambah)
    4. Target Protein Wajib Kunci di: {protein_mutlak} gram.
    
    Berikan hasil akhir HANYA dalam format JSON murni tanpa teks/markdown tambahan, struktur persis:
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
    
    # Kalkulasi cadangan luring/darurat
    default_tdee = int(bmr_lokal * fallback_index)
    default_kalori = default_tdee
    if profil["body_goal"] == "Fat Loss": default_kalori -= profil["perubahan_kalori"]
    elif profil["body_goal"] == "Muscle Gain": default_kalori += profil["perubahan_kalori"]

    if st.session_state.client is None:
        return {"indeks_aktivitas_terpilih": fallback_index, "tdee_kalkulasi": default_tdee, "kalori": default_kalori, "protein": protein_mutlak, "karbohidrat": 200, "lemak": 50, "air": 2500, "serat": 25}
        
    try:
        response = st.session_state.client.models.generate_content(
            model='gemini-2.0-flash', contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception as e:
        return {"indeks_aktivitas_terpilih": fallback_index, "tdee_kalkulasi": default_tdee, "kalori": default_kalori, "protein": protein_mutlak, "karbohidrat": 200, "lemak": 50, "air": 2500, "serat": 25}

def analisis_foto_makanan_ai(gambar_pil):
    data_simulasi = {
        "nama_makanan": "Ayam Goreng Crispy + Nasi Putih (Olive Fried Chicken)",
        "bagian_makanan": "Dada Ayam dengan Kulit",
        "metode_masak": "Goreng (Deep Fried)",
        "gramasi_estimasi": "150 gram ayam, 200 gram nasi",
        "kalori": 680, "protein": 38.0, "karbohidrat": 62.0, "lemak": 29.0, "serat": 1.5, "air": 110
    }
    if st.session_state.client is None: return data_simulasi
    prompt = "Kamu adalah AI Nutritionist. Analisis hidangan ini dan berikan output format JSON murni nutrisi lengkap."
    try:
        response = st.session_state.client.models.generate_content(
            model='gemini-2.0-flash', contents=[gambar_pil, prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception as e: return data_simulasi

def rekalkulasi_nutrisi_via_ai(nama, bagian, metode, gramasi):
    if st.session_state.client is None:
        return {"nama_makanan": nama, "bagian_makanan": bagian, "metode_masak": metode, "gramasi_estimasi": gramasi, "kalori": 450, "protein": 32.0, "karbohidrat": 45.0, "lemak": 12.0, "serat": 2.0, "air": 100}
    prompt = f"Hitung ulang nutrisi akurat dalam format JSON murni untuk: {nama} {bagian} {metode} {gramasi}."
    try:
        response = st.session_state.client.models.generate_content(
            model='gemini-2.0-flash', contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception as e:
        return {"nama_makanan": nama, "bagian_makanan": bagian, "metode_masak": metode, "gramasi_estimasi": gramasi, "kalori": 400, "protein": 30.0, "karbohidrat": 40.0, "lemak": 10.0, "serat": 2.0, "air": 80}

# ==========================================
# 4. INTERFACE HALAMAN 1: LOGIN
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
# 5. INTERFACE HALAMAN 2: INPUT PROFIL AWAL
# ==========================================
def render_halaman_profil():
    st.markdown("<h2>🥗 Set Profil Fisik & Checklist Kegiatan</h2>", unsafe_allow_html=True)
    st.write("Isi data fisik dasar dan centang aktivitas yang biasa Anda lakukan beserta frekuensinya.")
    
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
        st.markdown("#### 🏃‍♂️ 2. Checklist Aktivitas Fisik & Frekuensi Mandiri")
        aktivitas_dipilih = render_checklist_aktivitas(prefix_key="onboarding")
        
        st.markdown("---")
        perubahan_kalori = st.slider("Intensitas Surplus/Defisit Kalori Harian (Tidak berefek pada Maintain Weight)", min_value=300, max_value=500, value=500, step=50)
        
        submit_profil = st.form_submit_button("🚀 Hitung Pola Nutrisi & Target AI", type="primary")
        if submit_profil:
            st.session_state.user_profile = {
                "gender": gender, "bb_awal": berat_awal, "tb": tinggi_badan, 
                "umur": umur, "target_berat": berat_target, "body_goal": body_goal,
                "aktivitas": aktivitas_dipilih, "perubahan_kalori": perubahan_kalori
            }
            with st.spinner("Gemini AI menganalisis frekuensi latihan & menentukan TDEE optimal..."):
                st.session_state.nutrisi_target = hitung_target_via_ai(st.session_state.user_profile)
                st.session_state.profile_setup_done = True
                st.success("Profil Fisik & Analisis TDEE Sukses Dikonfigurasi!")
                st.rerun()

# ==========================================
# 6. INTERFACE HALAMAN 3: DASHBOARD UTAMA
# ==========================================
def render_halaman_utama():
    target = st.session_state.nutrisi_target
    jurnal = st.session_state.jurnal_hari_ini
    profil = st.session_state.user_profile
    
    st.markdown("<h1 style='text-align: center;'>🥗 AI Nutrition Tracker Pro</h1>", unsafe_allow_html=True)
    
    with st.expander("ℹ️ Detail Hasil Analisis Metabolisme Tubuh (AI-Generated)"):
        st.write(f"**Tipe Target:** `{profil.get('body_goal')}`")
        st.write(f"**Indeks TDEE Dipilih AI:** `{target.get('indeks_aktivitas_terpilih', '1.20')}`")
        st.write(f"**Estimasi Energi TDEE Anda:** `{target.get('tdee_kalkulasi', 2000)}` kkal/hari")
        if not profil.get("aktivitas"):
            st.caption("⚠️ *Tidak ada aktivitas dicentang. TDEE dihitung dengan indeks Sedentary (1.20).*")
        else:
            act_list = ", ".join([f"{k} ({v}x/mgg)" for k,v in profil.get("aktivitas", {}).items()])
            st.caption(f"🏃 *Aktivitas terdeteksi:* {act_list}")
    
    st.markdown("---")
    
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

    # --- TAB 4: EDIT PROFIL LENGKAP ---
    with tab_profil:
        st.write("##### ⚙️ Edit Profil & Kalkulasi Ulang AI")
        p = st.session_state.user_profile
        
        with st.form("form_edit_profil"):
            col1, col2 = st.columns(2)
            with col1:
                eb_gender = st.selectbox("Jenis Kelamin", ["Laki-laki", "Perempuan"], index=0 if p.get("gender") == "Laki-laki" else 1)
                eb_sekarang = st.number_input("Berat Badan Sekarang (kg)", value=p.get("bb_awal", 70.0))
                eb_tinggi = st.number_input("Tinggi Badan (cm)", value=p.get("tb", 170))
            with col2:
                eb_umur = st.number_input("Umur (Tahun)", value=p.get("umur", 24))
                eb_target = st.number_input("Target Berat Badan Akhir (kg)", value=p.get("target_berat", 65.0))
                eb_goal = st.selectbox("Pilih Body Goal", ["Fat Loss", "Maintain Weight (Recomposition)", "Muscle Gain"], index=["Fat Loss", "Maintain Weight (Recomposition)", "Muscle Gain"].index(p.get("body_goal", "Fat Loss")))
            
            st.markdown("---")
            st.markdown("#### 🏃‍♂️ Perbarui Checklist Aktivitas & Frekuensi")
            eb_aktivitas = render_checklist_aktivitas(prefix_key="editprofil", profil_existing=p)
            
            st.markdown("---")
            eb_perubahan = st.slider("Intensitas Surplus/Defisit Kalori Harian", min_value=300, max_value=500, value=p.get("perubahan_kalori", 500), step=50)
            
            if st.form_submit_button("💾 Simpan Perubahan & Kalkulasi Ulang AI", type="primary"):
                st.session_state.user_profile = {
                    "gender": eb_gender, "bb_awal": eb_sekarang, "tb": eb_tinggi, 
                    "umur": eb_umur, "target_berat": eb_target, "body_goal": eb_goal,
                    "aktivitas": eb_aktivitas, "perubahan_kalori": eb_perubahan
                }
                with st.spinner("Gemini AI sedang menghitung ulang TDEE dan target nutrisi baru..."):
                    st.session_state.nutrisi_target = hitung_target_via_ai(st.session_state.user_profile)
                    st.success("Profil & BMR/TDEE berhasil diperbarui!")
                    st.rerun()
                    
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚪 Keluar Akun & Reset Total (Log Out)", use_container_width=True):
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

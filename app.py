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
        # Mengambil otomatis dari Secrets GEMINI_API_KEY di Streamlit Cloud
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

# State untuk menu upload, verifikasi makanan, dan aktivitas fisik
if "show_upload_options" not in st.session_state:
    st.session_state.show_upload_options = False
if "pending_analysis" not in st.session_state:
    st.session_state.pending_analysis = None

# Opsi Global untuk Body Goal & Aktivitas Fisik
OPSI_BODY_GOAL = [
    "Lean (Kering, Atletis & Rendah Lemak)", 
    "Jacked (Berotot Padat & Definisi Tinggi)", 
    "Bulky (Fokus Pembentukan Massa Otot Besar)", 
    "Maintain Weight (Menjaga Proporsi Tubuh & Sehat Seimbang)"
]

OPSI_AKTIVITAS = [
    "Angkat Beban / Gym (Resistance Training)",
    "Kardiointensif (Lari, Berenang, Bersepeda)",
    "Olahraga Tim / Kontak (Futsal, Basket, Badminton)",
    "Calisthenics / Olahraga Beban Tubuh",
    "Pekerjaan Fisik Berat / Jalan Kaki Harian Tinggi"
]

# ==========================================
# 2. LOGIKA UTAMA INTEGRASI GEMINI AI
# ==========================================
def hitung_target_via_ai(profil):
    """Menghitung target makronutrisi harian berdasarkan profil fisik, aktivitas, & aturan protein harian 2x BB Target"""
    protein_mutlak = int(profil["target_berat"] * 2) # Aturan Mutlak: Menggunakan berat badan target
    
    # Format teks daftar aktivitas untuk dibaca AI
    teks_aktivitas = ""
    for act, freq in profil.get("aktivitas", {}).items():
        teks_aktivitas += f"- {act}: {freq} kali per minggu\n"
    if not teks_aktivitas:
        teks_aktivitas = "- Tidak ada aktivitas olahraga rutin (Sedentary)\n"
        
    prompt = f"""
    Kamu adalah seorang Ahli Gizi, Dietisien, dan Pakar Kebugaran AI profesional. 
    Hitunglah total kebutuhan energi harian (TDEE) dan seluruh rincian makronutrisi makro/mikro secara cerdas untuk profil berikut:
    
    PROFIL FISIK:
    - Berat Badan Sekarang: {profil['berat_badan']} kg
    - Tinggi Badan: {profil['tinggi_badan']} cm
    - Umur: {profil['umur']} tahun
    - Target Berat Badan Akhir: {profil['target_berat']} kg
    - Body Goal Utama: {profil['body_goal']}
    
    DAFTAR RITUAL AKTIVITAS FISIK USER:
    {teks_aktivitas}
    
    ATURAN MUTLAK KELUARAN: 
    1. Target Protein harian HARUS bernilai TEPAT {protein_mutlak} gram (Kunci rumus: 2x dari berat badan TARGET). Jangan diubah!
    2. Sesuaikan alokasi sisa kebutuhan kalori untuk Karbohidrat dan Lemak sehat secara presisi berdasarkan intensitas aktivitas fisik dan jenis Body Goal yang mereka pilih (Lean/Jacked/Bulky/Maintain).
    
    Berikan hasil kalkulasi akhir dalam format JSON murni tanpa hiasan markdown teks apapun dengan struktur kunci persis seperti ini:
    {{
        "kalori": 2400,
        "protein": {protein_mutlak},
        "karbohidrat": 260,
        "lemak": 65,
        "air": 3200,
        "serat": 30
    }}
    """
    if st.session_state.client is None:
        return {"kalori": int(profil["target_berat"] * 32), "protein": protein_mutlak, "karbohidrat": 240, "lemak": 60, "air": 3000, "serat": 25}
        
    try:
        response = st.session_state.client.models.generate_content(
            model='gemini-2.5-flash', contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception as e:
        return {"kalori": int(profil["target_berat"] * 30), "protein": protein_mutlak, "karbohidrat": 220, "lemak": 55, "air": 2500, "serat": 25}

def analisis_foto_makanan_ai(gambar_pil):
    """Menganalisis foto dari galeri maupun kamera secara mendalam"""
    prompt = """
    Kamu adalah AI Nutritionist yang sangat jeli. Analisis hidangan makanan atau minuman yang ada di dalam foto ini.
    
    Tugas Analisis Deteksi:
    1. Deteksi semua item bahan makanan yang terlihat beserta BAGIAN SPESIFIKNYA (misal: dada ayam tanpa kulit, paha atas dengan kulit, daging sapi sirloin, putih telur saja, dsb).
    2. Deteksi METODE MEMASAK atau pengolahan yang diterapkan (Goreng deep fry, Rebus, Kukus, Panggang, Tumis, atau jika bahan makanan tersebut Mentah).
    3. Berikan ASUMSI ESTIMASI TAKARAN/GRAMASI yang objektif (Gunakan takaran unit 'gram' atau 'buah'/'butir' untuk objek padat, dan 'ml' untuk elemen cairan/minuman).
    4. Hitung NILAI NUTRISI YANG TELAH DIOLAH SESUAI METODE MASAKNYA (Penting: Jika makanan mentah catat nutrisi mentahnya, jika digoreng pastikan kandungan kalori dan lemak bertambah sesuai metode pengolahannya).
    
    Berikan hasil analisis akhir dalam format JSON murni dengan bentuk struktur wajib seperti ini:
    {
        "nama_makanan": "Nama Hidangan Utama",
        "bagian_makanan": "Bagian spesifik yang terdeteksi",
        "metode_masak": "Metode masak (Goreng/Rebus/Kukus/Mentah/Panggang)",
        "gramasi_estimasi": "150 gram atau 250 ml",
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
            model='gemini-2.5-flash', contents=[gambar_pil, prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception as e:
        st.error(f"Gagal menganalisis gambar: {e}")
        return None

def rekalkulasi_nutrisi_via_ai(nama, bagian, metode, gramasi):
    """Menghitung ulang data nutrisi berdasarkan koreksi manual pengguna"""
    prompt = f"""
    Kamu adalah pakar nutrisi diet. Pengguna menyatakan tebakan sebelumnya belum sesuai dan memberikan koreksi detail.
    Hitung ulang secara akurat nilai nutrisi berdasarkan data koreksi nyata dari pengguna berikut:
    - Nama Makanan: {nama}
    - Bagian Makanan: {bagian}
    - Metode Memasak yang Dipakai: {metode}
    - Gramasi / Takaran Baru: {gramasi}
    
    Pastikan kalkulasi nilai gizi disesuaikan dengan bentuk olahan/metode masaknya (misal: direbus kalori lebih rendah daripada digoreng).
    Berikan keluaran dalam format JSON murni dengan struktur berikut:
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
        st.error(f"Gagal melakukan hitung ulang: {e}")
        return None

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
# 4. INTERFACE HALAMAN 2: INPUT PROFIL & AKTIVITAS (ONBOARDING)
# ==========================================
def render_halaman_profil():
    st.markdown("<h2>🥗 Set Profil Fisik, Body Goal & Aktivitas Anda</h2>", unsafe_allow_html=True)
    st.write("Isi metrik tubuh dan aktivitas harian Anda agar AI dapat meracik target nutrisi yang presisi.")
    
    st.markdown("#### 📏 1. Informasi Fisik & Target")
    col1, col2 = st.columns(2)
    with col1:
        berat = st.number_input("Berat Badan Saat Ini (kg)", min_value=30.0, value=70.0, step=0.5)
        tinggi = st.number_input("Tinggi Badan (cm)", min_value=100, value=170)
        umur = st.number_input("Umur Pengguna (Tahun)", min_value=12, value=23)
    with col2:
        target_bb = st.number_input("Target Berat Badan Akhir (kg)", min_value=30.0, value=65.0, step=0.5)
        goal = st.selectbox("Pilih Body Goal Anda", OPSI_BODY_GOAL)
        
    st.markdown("---")
    st.markdown("#### 🏃‍♂️ 2. Checklist Aktivitas Fisik Harian")
    st.write("Pilih jenis aktivitas fisik/olahraga yang biasa Anda lakukan:")
    
    aktivitas_terpilih = st.multiselect("Pilih seluruh aktivitas yang sesuai:", OPSI_AKTIVITAS)
    
    # Menampung input frekuensi dinamis untuk setiap aktivitas yang dichecklist
    dict_aktivitas_user = {}
    if aktivitas_terpilih:
        st.write("*Tentukan seberapa sering Anda melakukan aktivitas tersebut dalam seminggu:*")
        for akt in aktivitas_terpilih:
            freq = st.slider(f"Frekuensi untuk: {akt} (Kali / Minggu)", min_value=1, max_value=7, value=3, key=f"onboard_{akt}")
            dict_aktivitas_user[akt] = freq
            
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚀 Aktifkan Pola Nutrisi AI Saya", use_container_width=True, type="primary"):
        st.session_state.user_profile = {
            "berat_badan": berat, "tinggi_badan": tinggi, "umur": umur, 
            "target_berat": target_bb, "body_goal": goal, "aktivitas": dict_aktivitas_user
        }
        
        with st.spinner("AI sedang menganalisis profil dan menghitung rencana nutrisi ideal Anda..."):
            st.session_state.nutrisi_target = hitung_target_via_ai(st.session_state.user_profile)
            st.session_state.profile_setup_done = True
            st.success("Rencana Nutrisi AI Berhasil Dibuat!")
            st.rerun()

# ==========================================
# 5. INTERFACE HALAMAN 3: DASHBOARD UTAMA
# ==========================================
def render_halaman_utama():
    target = st.session_state.nutrisi_target
    jurnal = st.session_state.jurnal_hari_ini
    
    st.markdown("<h1 style='text-align: center;'>🥗 AI Nutrition Tracker Pro</h1>", unsafe_allow_html=True)
    st.markdown("---")
    
    # METRICS DISPLAY STATUS JURNAL HARI INI
    st.markdown("### 📊 Status Jurnal Hari Ini")
    c1, c2, c3 = st.columns(3)
    c1.metric("🔥 Kalori", f"{int(jurnal['kalori'])} kkal", f"Target: {target.get('kalori', 2000)} kkal")
    c2.metric("🥩 Protein (2x BB Target)", f"{jurnal['protein']:.1f} g", f"Target: {target.get('protein', 130)} g")
    c3.metric("🍞 Karbohidrat", f"{jurnal['karbohidrat']:.1f} g", f"Target: {target.get('karbohidrat', 230)} g")
    
    c4, c5, c6 = st.columns(3)
    c4.metric("🥑 Lemak", f"{jurnal['lemak']:.1f} g", f"Target: {target.get('lemak', 60)} g")
    c5.metric("💧 Air Minum", f"{int(jurnal['air'])} ml", f"Target: {target.get('air', 2500)} ml")
    c6.metric("🥬 Serat", f"{jurnal['serat']:.1f} g", f"Target: {target.get('serat', 25)} g")
    
    st.markdown("---")
    
    tab_scan, tab_list, tab_db, tab_profil = st.tabs(["📸 Scan Nutrisi AI", "📝 Catat Manual", "📁 Riwayat Jurnal", "⚙️ Edit Profil"])
    
    # --- TAB 1: SCAN NUTRISI (ALUR MULTI-UPLOAD & KONFIRMASI MANUAl) ---
    with tab_scan:
        st.write("##### 🍽️ Scan Foto Makanan / Minuman")
        
        # Tombol utama untuk memicu pilihan menu upload (agar kamera/uploader tidak langsung terbuka otomatis)
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
                    with st.spinner("AI sedang membedah komponen makanan, metode masak, serta gramasi porsi..."):
                        res = analisis_foto_makanan_ai(gambar_pil)
                        if res:
                            st.session_state.pending_analysis = res
                            st.success("Pemindaian AI Selesai! Mohon verifikasi hasilnya di bawah ini.")
        
        # --- BLOK PROSES VERIFIKASI KONFIRMASI USER ---
        if st.session_state.pending_analysis:
            st.markdown("---")
            st.markdown("### 🔍 Konfirmasi & Penyesuaian Data Hidangan")
            st.info("Pastikan Nama Makanan, Bagian Makanan, Metode Masak, dan Gramasi di bawah ini sudah sesuai dengan yang Anda konsumsi:")
            
            p = st.session_state.pending_analysis
            
            # Form Edit Koreksi Pengguna secara Real-Time
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
                    with st.spinner("Mengalkulasi ulang nutrisi berdasarkan koreksi data Anda..."):
                        updated_res = rekalkulasi_nutrisi_via_ai(edit_nama, edit_bagian, edit_metode, edit_gramasi)
                        if updated_res:
                            st.session_state.pending_analysis = updated_res
                            st.success("Nutrisi berhasil disesuaikan ulang oleh AI!")
                            st.rerun()
                            
                if tombol_setuju:
                    # Akumulasikan ke log total hari ini
                    st.session_state.jurnal_hari_ini["kalori"] += p.get("kalori", 0)
                    st.session_state.jurnal_hari_ini["protein"] += p.get("protein", 0)
                    st.session_state.jurnal_hari_ini["karbohidrat"] += p.get("karbohidrat", 0)
                    st.session_state.jurnal_hari_ini["lemak"] += p.get("lemak", 0)
                    st.session_state.jurnal_hari_ini["serat"] += p.get("serat", 0)
                    st.session_state.jurnal_hari_ini["air"] += p.get("air", 0)
                    
                    st.session_state.riwayat_makanan.append(p)
                    st.session_state.pending_analysis = None
                    st.session_state.show_upload_options = False
                    st.success("Sukses menyimpan log makanan!")
                    st.rerun()

    # --- TAB 2: CATAT MANUAL ---
    with tab_list:
        st.write("##### Input Makanan / Air Secara Manual")
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
                
        if st.button("💧 Tambah Air Minum (+250 ml)", use_container_width=True):
            st.session_state.jurnal_hari_ini["air"] += 250
            st.rerun()

    # --- TAB 3: RIWAYAT JURNAL ---
    with tab_db:
        st.write("##### Daftar Konsumsi Hari Ini")
        if not st.session_state.riwayat_makanan:
            st.info("Belum ada riwayat konsumsi untuk hari ini.")
        else:
            for idx, item in enumerate(st.session_state.riwayat_makanan):
                st.markdown(f"**{idx+1}. {item.get('nama_makanan')}** (*{item.get('bagian_makanan', 'Porsi')}*) — Metode: *{item.get('metode_masak')}* | ⚖️ {item.get('gramasi_estimasi')} $\rightarrow$ 🔥 {item.get('kalori')} kkal | 🥩 P: {item.get('protein')}g")
            
            if st.button("🗑️ Reset Seluruh Jurnal Hari Ini", type="secondary"):
                st.session_state.jurnal_hari_ini = {"kalori": 0.0, "protein": 0.0, "karbohidrat": 0.0, "lemak": 0.0, "air": 0.0, "serat": 0.0}
                st.session_state.riwayat_makanan = []
                st.rerun()

    # --- TAB 4: EDIT PROFIL & UPDATE TARGET AKTIVITAS ---
    with tab_profil:
        st.write("##### ⚙️ Edit Profil, Target Fisik & Ritual Aktivitas")
        p = st.session_state.user_profile
        
        eb_sekarang = st.number_input("Berat Badan Saat Ini (kg)", value=p.get("berat_badan", 70.0), key="edit_bb")
        eb_tinggi = st.number_input("Tinggi Badan (cm)", value=p.get("tinggi_badan", 170), key="edit_tb")
        eb_umur = st.number_input("Umur (Tahun)", value=p.get("umur", 23), key="edit_umur")
        eb_target = st.number_input("Target Berat Badan Akhir (kg)", value=p.get("target_berat", 65.0), key="edit_target")
        
        # Mengatur index default untuk body goal agar sesuai data lama
        default_goal_idx = OPSI_BODY_GOAL.index(p.get("body_goal", OPSI_BODY_GOAL[0])) if p.get("body_goal") in OPSI_BODY_GOAL else 0
        eb_goal = st.selectbox("Pilih Body Goal", OPSI_BODY_GOAL, index=default_goal_idx, key="edit_goal")
        
        st.write("Daftar Aktivitas Olahraga:")
        # Mengambil daftar aktivitas lama yang sudah dicentang sebagai default terpilih
        aktivitas_lama = list(p.get("aktivitas", {}).keys())
        eb_aktivitas = st.multiselect("Pilih jenis aktivitas fisik:", OPSI_AKTIVITAS, default=aktivitas_lama, key="edit_multiact")
        
        dict_edit_aktivitas = {}
        if eb_aktivitas:
            for akt in eb_aktivitas:
                val_lama = p.get("aktivitas", {}).get(akt, 3)
                freq = st.slider(f"Frekuensi untuk: {akt} (Kali / Minggu)", min_value=1, max_value=7, value=val_lama, key=f"edit_freq_{akt}")
                dict_edit_aktivitas[akt] = freq
                
        if st.button("💾 Simpan Perubahan Profil & Hitung Ulang AI", type="primary", use_container_width=True):
            st.session_state.user_profile = {
                "berat_badan": eb_sekarang, "tinggi_badan": eb_tinggi, "umur": eb_umur, 
                "target_berat": eb_target, "body_goal": eb_goal, "aktivitas": dict_edit_aktivitas
            }
            # AI dipanggil ulang, menghitung TDEE baru berdasarkan aktivitas baru, protein dikunci 2x BB target baru!
            st.session_state.nutrisi_target = hitung_target_via_ai(st.session_state.user_profile)
            st.success("Profil berhasil diperbarui! Nilai gizi disesuaikan ulang dengan protein tetap terkunci pada 2x BB Target.")
            st.rerun()
                
        if st.button("🚪 Keluar Akun (Log Out)", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.profile_setup_done = False
            st.rerun()

# ==========================================
# CENTRAL ROUTING CONTROLLER (PENGENDALI HALAMAN)
# ==========================================
if not st.session_state.logged_in:
    render_halaman_login()
elif st.session_state.logged_in and not st.session_state.profile_setup_done:
    render_halaman_profil()
else:
    render_halaman_utama()
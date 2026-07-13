import streamlit as st
import json
from PIL import Image
from google import genai
from google.genai import types

# =======================================================
# 1. SETUP TAMPILAN & KONEKSI AI
# =======================================================
st.set_page_config(page_title="AI Nutrition Tracker", page_icon="🥗", layout="centered")

# Inisialisasi Client Gemini
if "client" not in st.session_state:
    # Pastikan variabel lingkungan GEMINI_API_KEY sudah aktif di komputermu
    st.session_state.client = genai.Client()

# =======================================================
# 2. MEMORI APLIKASI (SESSION STATE)
# =======================================================
if "database_makanan" not in st.session_state:
    st.session_state.database_makanan = {
        "nasi putih": {"kalori": 130, "protein": 2.7, "lemak": 0.3, "karbohidrat": 28.2, "serat": 0.4, "gula": 0.1, "air": 68, "ukuran": 100, "satuan": "gram"},
        "telur rebus": {"kalori": 77, "protein": 6.3, "lemak": 5.3, "karbohidrat": 0.6, "serat": 0, "gula": 0.6, "air": 37, "ukuran": 1, "satuan": "butir"},
        "pisang": {"kalori": 105, "protein": 1.3, "lemak": 0.3, "karbohidrat": 27, "serat": 3.1, "gula": 14.4, "air": 88, "ukuran": 1, "satuan": "buah"}
    }

if "jurnal_harian" not in st.session_state:
    st.session_state.jurnal_harian = {"kalori": 0.0, "protein": 0.0, "lemak": 0.0, "karbohidrat": 0.0, "serat": 0.0, "gula": 0.0, "air": 0.0}

if "target_harian" not in st.session_state:
    st.session_state.target_harian = {"kalori": 2000, "protein": 60, "lemak": 65, "karbohidrat": 250, "air": 2500}

if "data_diri" not in st.session_state:
    st.session_state.data_diri = {
        'bb_sekarang': 70, 'tinggi': 170, 'umur': 25, 'bb_tujuan': 65,
        'body_goal': "Lean", 'daftar_aktivitas': []
    }

# =======================================================
# 3. FUNGSI LOGIKA AI
# =======================================================
def scan_foto_makanan_via_ai(gambar_pil):
    prompt = """
    Analisis foto makanan ini hingga level mikronutrisi. Estimasi kuantitas untuk 1 porsi standar.
    Kembalikan JSON murni:
    {
        "makanan": "nama", "kalori": angka, "protein": angka, "lemak": angka, "karbohidrat": angka,
        "serat": angka, "gula": angka, "air": angka_ml, "ukuran": angka, "satuan": "satuan (gram/buah/butir dll)", 
        "detail": "alasan singkat"
    }
    """
    try:
        response = st.session_state.client.models.generate_content(
            model='gemini-2.5-flash', contents=[gambar_pil, prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        return json.loads(response.text)
    except: return None

def hitung_konsumsi_kustom_via_ai(nama_makanan, data_dasar, jumlah_konsumsi, satuan_konsumsi):
    prompt = f"""
    Di database, '{nama_makanan}' memiliki profil per {data_dasar['ukuran']} {data_dasar['satuan']}:
    Kalori: {data_dasar['kalori']} | Protein: {data_dasar['protein']}g | Lemak: {data_dasar['lemak']}g | Karbo: {data_dasar['karbohidrat']}g | Serat: {data_dasar['serat']}g | Gula: {data_dasar['gula']}g | Air: {data_dasar['air']}ml
    
    User makan sebanyak: {jumlah_konsumsi} {satuan_konsumsi}.
    Konversikan nilai nutrisi ini secara proporsional. Jika beda satuan, gunakan database konkretmu untuk rasionya.
    Kembalikan HANYA JSON murni (angka float 1 desimal):
    {{
        "kalori": angka, "protein": angka, "lemak": angka, "karbohidrat": angka,
        "serat": angka, "gula": angka, "air": angka, "penjelasan_internal": "rasio konversinya"
    }}
    """
    try:
        response = st.session_state.client.models.generate_content(
            model='gemini-2.5-flash', contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        return json.loads(response.text)
    except: return None

def hitung_target_nutrisi_via_ai(data_user):
    aktivitas_aktif = [f"{item['nama']} ({item['frekuensi']}x seminggu)" for item in data_user['daftar_aktivitas'] if item['frekuensi'] > 0]
    teks_aktivitas = ", ".join(aktivitas_aktif) if aktivitas_aktif else "Sedentary"
    prompt = f"""
    Hitung TDEE dan target makro holistik berdasarkan: BB: {data_user['bb_sekarang']}kg | Tinggi: {data_user['tinggi']}cm | Umur: {data_user['umur']}thn | Target: {data_user['bb_tujuan']}kg ({data_user['body_goal']}) | Aktivitas: {teks_aktivitas}.
    Kembalikan JSON murni: {{ "target_kalori": angka, "target_protein": angka, "target_lemak": angka, "target_karbohidrat": angka, "target_air": angka, "alasan_singkat": "alasan" }}
    """
    try:
        response = st.session_state.client.models.generate_content(
            model='gemini-2.5-flash', contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        return json.loads(response.text)
    except: return None

# =======================================================
# 4. ANTARMUKA VISUAL (UI SMARTPHONE)
# =======================================================
st.title("🥗 AI Nutrition Tracker")

# DASHBOARD TARGET NUTRISI
st.subheader("📊 Status Jurnal Hari Ini")
c1, c2, c3 = st.columns(3)
c1.metric("🔥 Kalori", f"{st.session_state.jurnal_harian['kalori']:.0f} kkal", f"Target: {st.session_state.target_harian['kalori']}")
c2.metric("🥩 Protein", f"{st.session_state.jurnal_harian['protein']:.1f} g", f"Target: {st.session_state.target_harian['protein']}g")
c3.metric("🍞 Karbo", f"{st.session_state.jurnal_harian['karbohidrat']:.1f} g", f"Target: {st.session_state.target_harian['karbohidrat']}g")

c4, c5, c6 = st.columns(3)
c4.metric("🥑 Lemak", f"{st.session_state.jurnal_harian['lemak']:.1f} g", f"Target: {st.session_state.target_harian['lemak']}g")
c5.metric("💧 Air", f"{st.session_state.jurnal_harian['air']:.0f} ml", f"Target: {st.session_state.target_harian['air']}ml")
c6.metric("🥦 Serat", f"{st.session_state.jurnal_harian['serat']:.1f} g")

st.divider()

# MENU TAB INTERAKTIF
tab1, tab2, tab3, tab4 = st.tabs(["📸 Scan Kamera", "📖 Catat List", "🗂️ Database", "⚙️ Edit Profil"])

# --- TAB 1: SCAN KAMERA ---
with tab1:
    st.write("**Ambil foto makanan langsung dari kamera HP:**")
    foto = st.camera_input("Jepret Makanan")
    
    if foto:
        if st.button("🤖 Analisis Nutrisi AI", use_container_width=True):
            with st.spinner("AI sedang membedah 7 zat gizi makananmu..."):
                img_pil = Image.open(foto)
                hasil_scan = scan_foto_makanan_via_ai(img_pil)
                if hasil_scan:
                    st.session_state.temp_scan = hasil_scan
                else: st.error("Gagal memproses foto.")
                
    if "temp_scan" in st.session_state:
        d = st.session_state.temp_scan
        st.success(f"Terdeteksi: **{d['makanan'].title()}** ({d['ukuran']} {d['satuan']})")
        st.json({"Kalori": d['kalori'], "Protein": d['protein'], "Lemak": d['lemak'], "Karbo": d['karbohidrat'], "Serat": d['serat'], "Gula": d['gula'], "Air": d['air']})
        
        porsi = st.number_input("Berapa porsi yang dimakan?", min_value=0.1, value=1.0, step=0.5)
        if st.button("✅ Masukkan ke Jurnal", type="primary", use_container_width=True):
            for k in ['kalori', 'protein', 'lemak', 'karbohidrat', 'serat', 'gula', 'air']:
                st.session_state.jurnal_harian[k] += d.get(k, 0) * porsi
            st.session_state.database_makanan[d['makanan']] = {k: v for k, v in d.items() if k not in ['makanan', 'detail']}
            del st.session_state.temp_scan
            st.rerun()

# --- TAB 2: CATAT DARI LIST ---
with tab2:
    pilih_mkn = st.selectbox("Pilih menu terdaftar:", list(st.session_state.database_makanan.keys()))
    if pilih_mkn:
        mkn = st.session_state.database_makanan[pilih_mkn]
        st.info(f"Standar database: **{mkn['ukuran']} {mkn['satuan']}** = {mkn['kalori']} kkal | {mkn['protein']}g Protein")
        
        metode = st.radio("Metode input:", ["Per Porsi Standar", "Gramasi Kustom (Menimbang Sendiri)"])
        if metode == "Per Porsi Standar":
            p = st.number_input("Jumlah Porsi:", min_value=0.1, value=1.0, step=0.5, key="input_porsi")
            if st.button("➕ Catat Porsi", type="primary", use_container_width=True):
                for k in ['kalori', 'protein', 'lemak', 'karbohidrat', 'serat', 'gula', 'air']:
                    st.session_state.jurnal_harian[k] += mkn[k] * p
                st.rerun()
        else:
            g = st.number_input("Berat yang dikonsumsi (Gram):", min_value=1.0, value=150.0, step=10.0, key="input_gram")
            if st.button("🤖 AI Kalkulasi Silang & Catat", type="primary", use_container_width=True):
                with st.spinner("AI menghitung proporsi nutrisi..."):
                    hasil = hitung_konsumsi_kustom_via_ai(pilih_mkn, mkn, g, "gram")
                    if hasil:
                        for k in ['kalori', 'protein', 'lemak', 'karbohidrat', 'serat', 'gula', 'air']:
                            st.session_state.jurnal_harian[k] += hasil[k]
                        st.toast(f"Info AI: {hasil.get('penjelasan_internal', 'Berhasil')}")
                        st.rerun()

# --- TAB 3: LIHAT DATABASE ---
with tab3:
    st.write("Daftar makanan tersimpan di aplikasi:")
    st.dataframe(st.session_state.database_makanan, use_container_width=True)

# --- TAB 4: EDIT PROFIL & AUTO-REGENERATE ---
with tab4:
    st.write("**Edit data fisik & target tubuhmu:**")
    with st.form("form_profil"):
        bb = st.number_input("Berat Badan Sekarang (kg):", value=int(st.session_state.data_diri['bb_sekarang']))
        tb = st.number_input("Tinggi Badan (cm):", value=int(st.session_state.data_diri['tinggi']))
        u = st.number_input("Umur (tahun):", value=int(st.session_state.data_diri['umur']))
        target_bb = st.number_input("Target Berat Badan (kg):", value=int(st.session_state.data_diri['bb_tujuan']))
        goal = st.selectbox("Body Goal:", ["Lean", "Bulky", "Shredded", "Jacked"], index=["Lean", "Bulky", "Shredded", "Jacked"].index(st.session_state.data_diri['body_goal']))
        
        simpan = st.form_submit_button("🔄 Simpan & Re-Generate Nutrisi AI", type="primary", use_container_width=True)
        if simpan:
            st.session_state.data_diri.update({'bb_sekarang': bb, 'tinggi': tb, 'umur': u, 'bb_tujuan': target_bb, 'body_goal': goal})
            with st.spinner("AI meracik ulang kebutuhan kalori & air minum barumu..."):
                baru = hitung_target_nutrisi_via_ai(st.session_state.data_diri)
                if baru:
                    for k in ['kalori', 'protein', 'lemak', 'karbohidrat', 'air']:
                        if f"target_{k}" in baru: st.session_state.target_harian[k] = baru[f"target_{k}"]
                    st.success(f"Target diperbarui! Alasan AI: {baru.get('alasan_singkat', '-')}")
                    st.rerun()
import streamlit as st
import json
from google.genai import types

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
        "Kuli bangunan", "Kuli angkut barang", "Atlet profesional (Latihan harian intens)", "Latihan fisik keras harian lainnya"
    ]
}

def hitung_target_via_ai(profil):
    """Menghitung target nutrisi, menentukan indeks TDEE berdasarkan aktivitas harian via AI"""
    # 1. Rumus BMR Medis (Mifflin-St Jeor)
    if profil["gender"] == "Laki-laki":
        bmr_lokal = (10 * profil["bb_awal"]) + (6.25 * profil["tb"]) - (5 * profil["umur"]) + 5
    else:
        bmr_lokal = (10 * profil["bb_awal"]) + (6.25 * profil["tb"]) - (5 * profil["umur"]) - 161
        
    protein_mutlak = int(profil["target_berat"] * 2) 
    
    # Evaluasi Aktivitas Fisik
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
    
    # Kalkulasi cadangan luring/darurat jika server down
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
    """Menganalisis foto makanan menggunakan visi komputer Gemini"""
    data_simulasi = {
        "nama_makanan": "Ayam Goreng Crispy + Nasi Putih",
        "bagian_makanan": "Dada Ayam dengan Kulit",
        "metode_masak": "Goreng (Deep Fried)",
        "gramasi_estimasi": "150 gram ayam, 200 gram nasi",
        "kalori": 680, "protein": 38.0, "karbohidrat": 62.0, "lemak": 29.0, "serat": 1.5, "air": 110
    }
    if st.session_state.client is None: return data_simulasi
    prompt = "Kamu adalah AI Nutritionist. Analisis hidangan ini dan berikan output format JSON murni nutrisi lengkap harian."
    try:
        response = st.session_state.client.models.generate_content(
            model='gemini-2.0-flash', contents=[gambar_pil, prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception as e: return data_simulasi

def rekalkulasi_nutrisi_via_ai(nama, bagian, metode, gramasi):
    """Menghitung ulang data nutrisi berdasarkan masukan teks penyesuaian dari pengguna"""
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
import streamlit as st
from ai_helpers import hitung_target_via_ai, KATALOG_AKTIVITAS

def render_checklist_aktivitas(prefix_key, profil_existing={}):
    """Sub-komponen pembentuk checklist interaktif dengan frekuensi individual mandiri"""
    st.write("Centang aktivitas yang biasa Anda lakukan dan tentukan frekuensinya per minggu:")
    st.caption("💡 *Jika tidak ada aktivitas yang dicentang, TDEE otomatis dihitung dengan indeks Sedentary dasar (1.20).*")
    
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

def render_halaman_profil():
    """Halaman pengisian informasi fisik dasar pertama kali setelah berhasil login"""
    st.markdown("<h2>🥗 Set Profil Fisik & Checklist Kegiatan</h2>", unsafe_allow_html=True)
    st.write("Isi data fisik dasar dan centang aktivitas harian Anda. AI akan menganalisis kebutuhan kalori Anda.")
    
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
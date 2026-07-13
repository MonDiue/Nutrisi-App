import streamlit as st
import io
from PIL import Image
from ai_helpers import analisis_foto_makanan_ai, rekalkulasi_nutrisi_via_ai, hitung_target_via_ai
from profil_page import render_checklist_aktivitas

def render_halaman_utama():
    """Halaman Dasbor Utama Aplikasi Kebugaran"""
    target = st.session_state.nutrisi_target
    jurnal = st.session_state.jurnal_hari_ini
    profil = st.session_state.user_profile
    
    st.markdown("<h1 style='text-align: center;'>🥗 AI Nutrition Tracker Pro</h1>", unsafe_allow_html=True)
    
    # Komponen expander informasi detail TDEE metabolisme tubuh dari AI
    with st.expander("ℹ️ Detail Hasil Analisis Metabolisme Tubuh (AI-Generated)"):
        st.write(f"**Tipe Target:** `{profil.get('body_goal')}`")
        st.write(f"**Indeks TDEE Dipilih AI:** `{target.get('indeks_aktivitas_terpilih', '1.20')}`")
        st.write(f"**Estimasi Energi TDEE Anda:** `{target.get('tdee_kalkulasi', 2000)}` kkal/hari")
        if not profil.get("aktivitas"):
            st.caption("⚠️ *Tidak ada aktivitas dicentang. TDEE dihitung otomatis dengan indeks Sedentary dasar (1.20).*")
        else:
            act_list = ", ".join([f"{k} ({v}x/mgg)" for k,v in profil.get("aktivitas", {}).items()])
            st.caption(f"🏃 *Aktivitas terdeteksi:* {act_list}")
    
    st.markdown("---")
    
    # METRICS DISPLAY STATUS JURNAL GIZI HARIAN
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
    
    # --- TAB 1: PEMINDAI GAMBAR AI ---
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

    # --- TAB 2: INPUT LOG MANUAL ---
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

    # --- TAB 3: LIST DAFTAR REKAMAN JURNAL MAKANAN ---
    with tab_db:
        st.write("##### Daftar Konsumsi Hari Ini")
        if not st.session_state.riwayat_makanan:
            st.info("Belum ada riwayat konsumsi makanan atau minuman untuk hari ini.")
        else:
            for idx, item in enumerate(st.session_state.riwayat_makanan):
                st.markdown(f"**{idx+1}. {item.get('nama_makanan')}** — 🔥 {item.get('kalori')} kkal | 🥩 Protein: {item.get('protein')}g | 🍞 Karbo: {item.get('karbohidrat')}g")
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🗑️ Reset Seluruh Jurnal Hari Ini", use_container_width=True):
                st.session_state.jurnal_hari_ini = {"kalori": 0.0, "protein": 0.0, "karbohidrat": 0.0, "lemak": 0.0, "air": 0.0, "serat": 0.0}
                st.session_state.riwayat_makanan = []
                st.success("Jurnal hari ini berhasil dikosongkan!")
                st.rerun()

    # --- TAB 4: EDIT PROFIL & RE-CALCULATE ---
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
                    
        st.markdown("<br><br>", unsafe_allow_html=True)
        if st.button("🚪 Keluar Akun & Reset Total (Log Out)", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.profile_setup_done = False
            st.session_state.user_profile = {}
            st.session_state.nutrisi_target = {}
            st.success("Berhasil keluar!")
            st.rerun()
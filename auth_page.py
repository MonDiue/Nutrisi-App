import streamlit as st

def render_halaman_login():
    """Menampilkan antar muka login pengguna"""
    st.markdown("<h2 style='text-align: center; margin-top: 20px;'>🔐 Sign In / Sign Up</h2>", unsafe_allow_html=True)
    st.write("Selamat datang di **AI Nutrition Tracker Pro**. Silakan hubungkan akun Anda untuk memulai:")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔴 Masuk dengan Google", use_container_width=True): 
            st.session_state.logged_in = True
            st.rerun()
        if st.button("🔵 Masuk dengan Facebook", use_container_width=True): 
            st.session_state.logged_in = True
            st.rerun()
    with col2:
        if st.button("📧 Gunakan Akun Gmail", use_container_width=True): 
            st.session_state.logged_in = True
            st.rerun()
        if st.button("⚫ Hubungkan via iCloud Apple", use_container_width=True): 
            st.session_state.logged_in = True
            st.rerun()
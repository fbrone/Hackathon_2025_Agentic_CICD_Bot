import streamlit as st
from assistant import run_assistant

if 'authenticated_user' in st.session_state:
    run_assistant(st.session_state.authenticated_user['username'])
else:
    st.warning("Please log in to access the assistant.")
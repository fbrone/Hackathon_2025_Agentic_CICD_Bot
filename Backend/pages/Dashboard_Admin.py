import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from auth.updated_database import get_user, users_collection
from bcrypt import checkpw
from dotenv import load_dotenv
import os

load_dotenv("./config/auth.env")

# Set page config
st.set_page_config(
    page_title="Admin Dashboard",
    page_icon="👥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Session State for Login Persistence
if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False
    st.session_state.admin_username = ""
    st.session_state.user_team = "A"
    st.rerun()

# Admin Login
if not st.session_state.admin_logged_in:
    st.image("https://www.jenkins.io/images/logos/jenkins/jenkins.png", width=90)
    st.markdown("<h1 style='text-align: center;'>🔑 Admin Login</h1>", unsafe_allow_html=True)
    
    with st.form("login_form"):
        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        
        if st.form_submit_button("Login"):
            user = get_user(username)
            if user and checkpw(password.encode('utf-8'), user["password"].encode('utf-8')):
                if user.get("team") == "B":
                    st.session_state.admin_logged_in = True
                    st.session_state.admin_username = username
                    st.session_state.user_team = "B"
                    st.rerun()
                else:
                    st.error("❌ You don't have admin privileges.")
            else:
                st.error("❌ Invalid credentials.")

# Admin Dashboard
if st.session_state.admin_logged_in:
    st.sidebar.image("https://www.jenkins.io/images/logos/jenkins/jenkins.png", width=100)
    st.sidebar.markdown(f"### Welcome, **{st.session_state.admin_username}** (Team {st.session_state.user_team}) 👋")
    
    page = st.sidebar.radio(
        "Select Page", 
        ["View All Users", "Pending Requests", "Modify User Role/Team"],
        label_visibility="collapsed"
    )
    
    if st.sidebar.button("Logout"):
        st.session_state.admin_logged_in = False
        st.session_state.admin_username = ""
        st.session_state.user_team = ""
        st.rerun()

    users = list(users_collection.find({}, {"_id": 0, "username": 1, "team": 1, "email": 1, "requested_team": 1, "role": 1}))

    if page == "View All Users":
        st.markdown("<h2 style='text-align: center;'>👥 All Registered Users</h2>", unsafe_allow_html=True)
        
        if users:
            df = pd.DataFrame(users)
            st.dataframe(df, use_container_width=True)
            st.subheader("🧮 User Team Distribution")
            team_counts = df['team'].value_counts()
            fig, ax = plt.subplots(figsize=(2, 2), dpi=150)
            ax.pie (team_counts, 
                labels=team_counts.index, 
                autopct='%1.1f%%', 
                textprops={'fontsize': 5}, 
                startangle=100 
            )
            st.pyplot(fig)
        else:
            st.info("📌 No registered users found.")
        
    elif page == "Pending Requests":
        st.markdown("<h2 style='text-align: center;'>🔹 Team Change Requests</h2>", unsafe_allow_html=True)
        
        requests = [user for user in users if user.get("requested_team")]
        
        if requests:
            st.dataframe(pd.DataFrame(requests), use_container_width=True)
            
            with st.form("approve_request"):
                username = st.selectbox("Select user", [r["username"] for r in requests])
                if st.form_submit_button("Approve Request"):
                    user = get_user(username)
                    if user:
                        users_collection.update_one(
                            {"username": username},
                            {"$set": {
                                "team": user["requested_team"],
                                "role": "admin" if user["requested_team"] == "B" else "non-admin",
                                "requested_team": None
                            }}
                        )
                        st.success(f"Approved {username}'s move to Team {user['requested_team']}")
                        st.rerun()
        else:
            st.info("📌 No pending team change requests.")

    elif page == "Modify User Role/Team":
        st.markdown("<h2 style='text-align: center;'>⚙️ Modify Any User's Role or Team</h2>", unsafe_allow_html=True)
        
        all_usernames = [u["username"] for u in users]
        
        with st.form("modify_user_form"):
            selected_user = st.selectbox("Select a user", all_usernames)
            new_team = st.radio("Select new team", ["A", "B"])
            new_role = st.radio("Select new role", ["admin", "non-admin"])
            
            if st.form_submit_button("Apply Changes"):
                users_collection.update_one(
                    {"username": selected_user},
                    {"$set": {
                        "team": new_team,
                        "role": new_role,
                        "requested_team": None  # Clear any old requests
                    }}
                )
                st.success(f"✅ Updated {selected_user}: Team {new_team}, Role {new_role}")
                st.rerun()
import streamlit as st
from authlib.integrations.requests_client import OAuth2Session
import os
import uuid
from dotenv import load_dotenv
from auth.updated_database import store_user, get_user, users_collection
import webbrowser
from datetime import datetime
import bcrypt

# Load secrets
load_dotenv("./config/auth.env")

CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8502"  

AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
TOKEN_URL = "https://github.com/login/oauth/access_token"
USER_URL = "https://api.github.com/user"
EMAILS_URL = "https://api.github.com/user/emails"

# Streamlit config
st.set_page_config(page_title="Login", layout="centered")

# UI
st.title("🔐 Jenkins AI Agent Login")
st.markdown("Please login using your GitHub account.")

# Session init
if "auth_state" not in st.session_state:
    st.session_state["auth_state"] = None
if "token" not in st.session_state:
    st.session_state["token"] = None

# --- LOGIN BUTTON ---
if st.button("🔗 Login with GitHub"):
    auth_session = OAuth2Session(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=["read:org", "user:email"]
    )
    auth_url, state = auth_session.create_authorization_url(
        AUTHORIZE_URL,
        state=str(uuid.uuid4())
    )
    st.session_state["auth_state"] = state

    # ✅ Redirect in same tab
    st.markdown(f"""
        <meta http-equiv="refresh" content="0; url={auth_url}" />
    """, unsafe_allow_html=True)



    
# def check_github_token_access(token, org_to_check=None):
#     session = OAuth2Session(token=token)

#     # --- 1. Get user info and token scopes
#     user_resp = session.get("https://api.github.com/user")
#     if user_resp.status_code != 200:
#         st.error("❌ Failed to fetch user info.")
#         return

#     user_data = user_resp.json()
#     scopes = user_resp.headers.get("X-OAuth-Scopes", "None")

#     st.subheader("🔐 GitHub Token Access Check")
#     st.write("👤 **User:**", user_data.get("login"))
#     st.write("🛡️ **Granted Scopes:**", scopes)

#     # --- 2. Get org memberships
#     org_resp = session.get("https://api.github.com/user/memberships/orgs")
#     if org_resp.status_code == 200:
#         orgs = [org["organization"]["login"] for org in org_resp.json()]
#         st.write("🏢 **Organizations:**", orgs)
#     else:
#         st.error(f"⚠️ Failed to fetch org memberships: {org_resp.status_code}")
#         return

#     # --- 3. (Optional) Get team info for a specific org
#     if org_to_check and org_to_check in orgs:
#         team_resp = session.get(f"https://api.github.com/orgs/{org_to_check}/teams")
#         if team_resp.status_code == 200:
#             teams = [team["name"] for team in team_resp.json()]
#             st.write(f"👥 **Teams in {org_to_check}:**", teams)
#         elif team_resp.status_code == 403:
#             st.warning("🔒 Access to teams is forbidden. Ensure the app is approved for org-level access.")
#         elif team_resp.status_code == 404:
#             st.error(f"❌ Org '{org_to_check}' not found or not accessible.")
#         else:
#             st.error(f"⚠️ Unexpected error: {team_resp.status_code}")

# if st.button("🛠 Check My GitHub Access"):
#     check_github_token_access(st.session_state["token"], org_to_check="ibm")  # or "ibm"


# --- HANDLE REDIRECT WITH CODE ---
query_params = st.query_params
code = query_params.get("code")

if code and not st.session_state.get("token"):
    try:
        oauth = OAuth2Session(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            redirect_uri=REDIRECT_URI,
        )
        token = oauth.fetch_token(
            TOKEN_URL,
            code=code,
            client_secret=CLIENT_SECRET
        )
        st.session_state["token"] = token
        st.rerun()

    except Exception as e:
        st.error(f"❌ Token exchange failed: {e}")
        st.stop()

# --- FETCH USER INFO IF LOGGED IN ---
if st.session_state.get("token"):
    try:
        token = st.session_state["token"]
        session = OAuth2Session(token=token)

        user_resp = session.get(USER_URL)
        user_info = user_resp.json()
        username = user_info.get("login", "")
        company = user_info.get("company", "")

        email_resp = session.get(EMAILS_URL)
        emails = email_resp.json()
        email = next((e["email"] for e in emails if e.get("primary")), None)

        if not email or not (email.endswith("@ibm.com")):
            st.error("⛔ Only users with @ibm.com emails are allowed.")
            st.stop()

        role = "non-admin"
        default_team = "A"

        existing_user = get_user(username)
        
        if existing_user and existing_user.get("password"):
            st.session_state["authenticated_user"] = {
                "email": email,
                "username": username,
                "role": role
            }
            st.switch_page("pages/Chatbot_UI.py")
        else:
            st.subheader("🔒 Set Your Password")
            st.write("Please set a password for dashboard access")

            password = st.text_input("Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")

            # ⬇️ Instantly show dropdown after checkbox click
            request_team_change = st.checkbox("Request team change (optional)")
            if request_team_change:
                new_team = st.selectbox(
                    "Select desired team",
                    options=["A", "B", "C", "D"],
                    help="Team B: Admin access\nTeam C: Special access\nTeam D: Limited access"
                )
            else:
                new_team = default_team

            # Submit button below inputs
            if st.button("Set Password"):
                if password != confirm_password:
                    st.error("Passwords don't match!")
                elif len(password) < 8:
                    st.error("Password must be at least 8 characters")
                else:
                    hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

                    user_data = {
                        "username": username,
                        "password": hashed_pw.decode('utf-8'),
                        "role": role,
                        "email": email,
                        "team": default_team,
                        # "requested_team": new_team if request_team_change else None,
                        "requested_team": new_team if request_team_change else None,
                        "company": company,
                        "last_login": datetime.utcnow()
                    }

                    users_collection.update_one(
                        {"username": username},
                        {"$set": user_data},
                        upsert=True
                    )

                    st.session_state["authenticated_user"] = {
                        "email": email,
                        "username": username,
                        "role": role
                    }

                    if request_team_change:
                        st.success(f"Password set successfully! Team change request to Team {new_team} submitted.")
                    else:
                        st.success("Password set successfully!")

                    st.switch_page("pages/Chatbot_UI.py")

    except Exception as e:
        st.error(f"⚠️ Failed to get user info: {e}")

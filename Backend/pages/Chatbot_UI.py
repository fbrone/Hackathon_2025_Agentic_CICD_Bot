import streamlit as st
# from OAuth_Login import github_login
from auth.updated_database import get_user, add_user, store_jobs, get_stored_jobs, get_user_projects
from auth.auth import authenticate, hash_password
import requests
import urllib.parse
from langchain.tools import Tool
from langchain.memory import ConversationBufferMemory
from langchain.agents import initialize_agent, AgentType
from langchain_community.llms import Ollama
from dotenv import load_dotenv
import os
import re
import bcrypt
# Load environment variables
load_dotenv("./config/auth.env")

# from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient

from auth.updated_database import get_user, update_user_role, get_all_users, add_user

# app = Flask(__name__)
# app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback_secret_key")

# MongoDB connection
client = MongoClient("mongodb://localhost:27017/")
db = client['jenkins_ai']
users_collection = db['users']


# Jenkins Configuration
JENKINS_BASE_URL = os.getenv("JENKINS_BASE_URL")
JENKINS_USER = os.getenv("JENKINS_USER")
JENKINS_API_TOKEN = os.getenv("JENKINS_API_TOKEN")


# Session State Management
if "authenticated_user" not in st.session_state:
    st.session_state.authenticated_user = None

if "show_trigger_input" not in st.session_state:
    st.session_state.show_trigger_input = False

if "job_params" not in st.session_state:
    st.session_state.job_params = {}

if "job_triggered" not in st.session_state:
    st.session_state.job_triggered = False


# def handle_login():
#     username = st.session_state.username
#     password = st.session_state.password

#     auth_result = authenticate(username, password)

#     if auth_result["status"] == "failed":
#         st.session_state.authenticated_user = None
#         st.error(f":x: {auth_result['message']}")
#     else:
#         st.session_state.authenticated_user = {"username": username, "role": auth_result["role"]}
#         st.success(f":white_check_mark: Welcome, {username} ({auth_result['role']})!")
#         st.rerun()

# def handle_logout():
#     st.session_state.authenticated_user = None
#     st.success(":white_check_mark: You have been logged out.")
#     st.rerun()


# Jenkins Operations
def fetch_and_store_jobs():
    jobs = f"{JENKINS_BASE_URL}/api/json"
    requests.packages.urllib3.disable_warnings()
    headers = {"Authorization": f"Bearer {JENKINS_API_TOKEN}"}
    response = requests.get(jobs, headers=headers, verify=False)
    store_jobs(jobs)
    return ":white_check_mark: Jobs successfully stored in MongoDB."

def list_all_jobs(job_type="all"):
    if not st.session_state.authenticated_user:
        return ":warning: Please log in first."

    jobs_data = get_stored_jobs(job_type)

    if not jobs_data:
        return f":x: No {job_type} jobs found in the database."

    jobs = [job["name"] for job in jobs_data]
    # category_text = ":clipboard: All Jenkins jobs" if job_type == "all" else f":crown: {job_type.capitalize()} jobs"
    # return f"{category_text}:\n" + "\n".join(f"- {job}" for job in jobs)
    category_text = ""
    if job_type == "admin":
        category_text = ":crown: Admin triggerable Jenkins jobs:"
    elif job_type == "non-admin":
        category_text = ":busts_in_silhouette: Non-admin-triggerable Jenkins jobs:"
    else:
        category_text = ":clipboard: All Jenkins jobs:"

    return f"{category_text}\n" + "\n".join(f"- {job}" for job in jobs)


# Fetch Jenkins Job Parameters
def fetch_job_parameters(job_name):
    url = f"{JENKINS_BASE_URL}/job/{urllib.parse.quote(job_name)}/api/json"
    requests.packages.urllib3.disable_warnings()
    headers = {"Authorization": f"Bearer {JENKINS_API_TOKEN}"}
    response = requests.get(url, headers=headers, verify=False)
    # response = requests.get(url, auth=(JENKINS_USER, JENKINS_API_TOKEN))
    print("*"*50,url)
    print(response)
    if response.status_code != 200:
        return []

    job_data = response.json()
    property_data = job_data.get("property", [])

    for prop in property_data:
        if "parameterDefinitions" in prop:
            return [
                {
                    "name": param.get("name", ""),
                    "defaultValue": param.get("defaultParameterValue", {}).get("value", ""),
                    "choices": param.get("choices", [])
                }
                for param in prop["parameterDefinitions"]
            ]

    return []


def trigger_job(job_name, params):
    formatted_params = urllib.parse.urlencode(params)
    url = f"{JENKINS_BASE_URL}/job/{urllib.parse.quote(job_name)}/buildWithParameters?{formatted_params}"
    requests.packages.urllib3.disable_warnings()
    headers = {"Authorization": f"Bearer {JENKINS_API_TOKEN}"}
    response = requests.get(url, headers=headers, verify=False)
    # response = requests.post(url, auth=(JENKINS_USER, JENKINS_API_TOKEN))

    if response.status_code == 201:
        return f":white_check_mark: Job '{job_name}' triggered successfully!"
    return f":x: Failed to trigger job. Status: {response.status_code}, Response: {response.text}"



# def get_last_build_summary(job_name: str):
#     data = jenkins_api.get_last_build_summary(job_name)
    
#     print("DEBUG: API Response:", data)  # :white_check_mark: Check the exact response from Jenkins

#     if not isinstance(data, dict):
#         return ":x: Error: Invalid API response."

#     build_number = data.get("number", "Unknown")
#     build_status = data.get("result")  # :white_check_mark: Do NOT set a default value yet
#     requests.packages.urllib3.disable_warnings()
#     build_url = data.get("url") or f"{JENKINS_BASE_URL}/job/{urllib.parse.quote(job_name)}/{build_number}/"
#     headers = {"Authorization": f"Bearer {JENKINS_API_TOKEN}"}
#     response = requests.get(build_url, headers=headers, verify=False)
#     print(f"DEBUG: build_status={build_status}, build_number={build_number}, build_url={build_url}")

#     # :white_check_mark: Fix: Correctly set build_status
#     if build_status is None:  # If Jenkins has no result yet, it means the build is running.
#         build_status = "RUNNING"

#     # :white_check_mark: Fix: Normalize the status for correct color coding
#     build_status = build_status.upper() if isinstance(build_status, str) else "UNKNOWN"
#     status_color = "green" if build_status == "SUCCESS" else "red"

#     build_summary = (
#         f"<p>Build <span style='color: blue;'>#{build_number}</span> "
#         f"Status: <span style='color: {status_color};'>{build_status}</span> - "
#         f"<a href='{build_url}' target='_blank'>{build_url}</a></p>"
#     )

#     st.markdown(build_summary, unsafe_allow_html=True)
#     return build_summary

import urllib.parse
import requests
import streamlit as st


def get_last_build_summary(job_name: str):
    headers = {"Authorization": f"Bearer {JENKINS_API_TOKEN}"}
    requests.packages.urllib3.disable_warnings()

    # Step 1: Get job info
    job_url = f"{JENKINS_BASE_URL}/job/{urllib.parse.quote(job_name)}/api/json"
    response = requests.get(job_url, headers=headers, verify=False)
    if response.status_code != 200:
        return f":x: Failed to fetch job info for '{job_name}'"
    job_info = response.json()

    last_build = job_info.get("lastBuild")
    last_completed = job_info.get("lastCompletedBuild")

    if not last_build and not last_completed:
        return f":warning: No builds found for job '{job_name}'"

    # Step 2: Determine if a build is running
    build = last_build or last_completed
    build_number = build["number"]
    build_url = build["url"]
    build_api_url = f"{build_url}api/json"

    build_resp = requests.get(build_api_url, headers=headers, verify=False)
    if build_resp.status_code != 200:
        return f":x: Failed to fetch build info for build #{build_number}"
    build_data = build_resp.json()

    if build_data.get("building", False):
        build_status = "RUNNING"
    else:
        build_status = build_data.get("result") or "UNKNOWN"

    # Step 3: Color coding
    status_color = {
        "SUCCESS": "green",
        "FAILURE": "red",
        "ABORTED": "gray",
        "RUNNING": "orange",
        "UNKNOWN": "black"
    }.get(build_status, "black")

    # Step 4: Format output
    build_summary = (
        f"<p>Build <span style='color: blue;'>#{build_number}</span> "
        f"Status: <span style='color: {status_color};'>{build_status}</span> - "
        f"<a href='{build_url}' target='_blank'>Details</a></p>"
    )

    return build_summary



# def get_specific_build_summary(query: str):
#     """Extracts job name and build number from the query and fetches the build summary."""
    
#     # Try to match the correct format
#     match = re.search(r"build summary of (\S+) with build number (\d+)", query, re.IGNORECASE)
    
#     if not match:
#         # Check if input is comma-separated (alternative format)
#         parts = [part.strip() for part in query.split(",")]
#         if len(parts) == 2:
#             job_name, build_number = parts
#         else:
#             return ":x: Invalid input format. Please provide job name and build number, e.g., 'get the build summary of my-job with build number 42'."
#     else:
#         job_name, build_number = match.groups()

#     data = jenkins_api.get_specific_build_summary(job_name, build_number)

#     if not isinstance(data, dict):
#         return ":x: Error fetching build data."

#     build_status = data.get("result", "Unknown")
#     requests.packages.urllib3.disable_warnings()
#     build_url = data.get("url") or f"{JENKINS_BASE_URL}/job/{urllib.parse.quote(job_name)}/{build_number}/"
#     headers = {"Authorization": f"Bearer {JENKINS_API_TOKEN}"}
#     response = requests.get(build_url, headers=headers, verify=False)

#     return f":small_blue_diamond: Build #{build_number} of job '{job_name}' Status: {build_status} :link: More details: {build_url}"

def get_specific_build_summary(query: str):
    import re
    import urllib.parse

    # Extract job name and build number
    match = re.search(r"build summary of (\S+) with build number (\d+)", query, re.IGNORECASE)
    if not match:
        parts = [part.strip() for part in query.split(",")]
        if len(parts) != 2:
            return ":x: Invalid input format. Use: 'get the build summary of <job> with build number <num>'."
        job_name, build_number = parts
    else:
        job_name, build_number = match.groups()

    # Make sure build_number is a string for URL construction
    build_number = str(build_number)

    build_api_url = f"{JENKINS_BASE_URL}/job/{urllib.parse.quote(job_name)}/{build_number}/api/json"
    build_url = f"{JENKINS_BASE_URL}/job/{urllib.parse.quote(job_name)}/{build_number}/"

    headers = {"Authorization": f"Bearer {JENKINS_API_TOKEN}"}
    requests.packages.urllib3.disable_warnings()

    response = requests.get(build_api_url, headers=headers, verify=False)
    if response.status_code != 200:
        return f":x: Failed to fetch build #{build_number} of job '{job_name}'"

    build_data = response.json()
    is_building = build_data.get("building", False)
    result = build_data.get("result")

    if is_building:
        build_status = "RUNNING"
    elif result is not None:
        build_status = result.upper()
    else:
        build_status = "UNKNOWN"

    # Return clean response
    return (
        f"<p>Build <span style='color: blue;'>#{build_number}</span> "
        f"Status: <span style='color: {'orange' if build_status == 'RUNNING' else 'green' if build_status == 'SUCCESS' else 'red'};'>"
        f"{build_status}</span> - <a href='{build_url}' target='_blank'>Details</a></p>"
    )


# Tools
tools = [
    Tool(name="List All Jobs", func=lambda _: list_all_jobs("all"), description="Lists all Jenkins jobs.", return_direct=True),
    Tool(name="List All Admin Jobs", func=lambda _: list_all_jobs("admin"), description="Lists only admin-triggerable Jenkins jobs.", return_direct=True),
    Tool(name="List All Non-Admin Jobs", func=lambda _: list_all_jobs("non-admin"), description="Lists only non-admin-triggerable Jenkins jobs.", return_direct=True),
    Tool(name="Trigger Job", func=trigger_job, description="Triggers a Jenkins job."),
    Tool(name="Get Last Build Summary", func=get_last_build_summary, description="Fetches the last build summary."),
    Tool(name="Get Specific Build Summary", func=get_specific_build_summary, description="Fetches a specific build summary."),
]

# AI Agent
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
llm = Ollama(model="llama3")
agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.CONVERSATIONAL_REACT_DESCRIPTION,
    memory=memory,
    verbose=True,
    handle_parsing_errors=True,
)
# **Process Query Function**
def process_query(query: str):
    if not st.session_state.authenticated_user:
        return ":warning: Please log in first."
    response = agent.run(query)
    st.session_state.messages.append({"role": "user", "content": query})
    st.session_state.messages.append({"role": "assistant", "content": response})
    return response





# def is_user_in_team_for_repo(access_token, org, repo, username):
#     headers = {"Authorization": f"Bearer {access_token}"}
    
#     # Get all teams with access to the repo
#     teams_url = f"https://api.github.com/repos/{org}/{repo}/teams"
#     teams_response = requests.get(teams_url, headers=headers)

#     if teams_response.status_code != 200:
#         print("Failed to fetch teams for repo")
#         return False

#     teams = teams_response.json()

#     for team in teams:
#         team_slug = team["slug"]
#         check_membership_url = f"https://api.github.com/orgs/{org}/teams/{team_slug}/memberships/{username}"
#         membership_response = requests.get(check_membership_url, headers=headers)
        
#         if membership_response.status_code == 200:
#             state = membership_response.json().get("state")
#             if state == "active":
#                 return True

#     return False


# Streamlit UI

if "authenticated_user" not in st.session_state and "registered_user" in st.query_params:
    registered_user = st.query_params["registered_user"]
    if registered_user:
        st.session_state.authenticated_user = {"username": registered_user, "role": "admin"}  # Default role
        st.rerun()  # Refresh the page after setting session state

st.set_page_config(page_title="CICD AI Bot", page_icon=":robot_face:", layout="wide")
st.title(":robot_face: Welcome to Jenkins CICD AI Bot")

if "authenticated_user" in st.session_state:
    st.markdown(f"👤 **Logged in as:** `{st.session_state.authenticated_user['username']}`")


    if st.button("🔓 Logout"):
        # Clear authentication-related session state
        for key in ["token", "auth_state", "authenticated_user"]:
            if key in st.session_state:
                del st.session_state[key]
        st.success("You have been logged out.")
        st.switch_page("OAuth_Login.py")
        # st.rerun()

    # Chat Interface
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Display "Trigger Jobs" button
    if st.button("Trigger Jobs"):
        st.session_state.show_trigger_input = True


    # Ensure job selection respects role permissions
    if st.session_state.show_trigger_input and "job_name" not in st.session_state:
        # Fetch all jobs for admins, only non-admin jobs for non-admin users
        job_options = [job["name"] for job in get_stored_jobs("all_jobs" if st.session_state.authenticated_user["role"] == "admin" else "non-admin")]
        
        if not job_options:
            st.error(":x: No jobs available for selection.")
        else:
            job_name_input = st.selectbox("Select Job Name:", job_options, key="job_name_input")

        if st.button("Submit Job Name"):
            job_name = st.session_state.job_name_input
            params = fetch_job_parameters(job_name)

            if params:
                st.session_state.job_params = {param['name']: param for param in params}
                st.session_state['job_name'] = job_name
                st.success(f":white_check_mark: Job '{job_name}' found! Please enter the required parameters.")
                st.rerun()  # Ensure UI updates properly
                
            else:
                st.error(f":x: No parameters found for job '{job_name}' or job does not exist.")

    # Show the parameter input form
    if "job_name" in st.session_state and st.session_state.job_params and not st.session_state.job_triggered:
        st.subheader(f"Enter Parameters for '{st.session_state.job_name}'")

        with st.form("parameter_form"):
            submitted_params = {}
    
            for param, param_details in st.session_state.job_params.items():
                if isinstance(param_details, dict) and param_details.get("choices"):
                    index = next((i for i, choice in enumerate(param_details["choices"]) if choice == param_details.get("defaultValue")), 0)
                    submitted_params[param] = st.selectbox(f"{param}:", options=param_details["choices"], index=index)
                else:
                    submitted_params[param] = st.text_input(f"{param}:", value=param_details.get("defaultValue", ""))

            submitted = st.form_submit_button("Submit Parameters")
            canceled = st.form_submit_button("Cancel")

        if submitted:
            result = trigger_job(st.session_state.job_name, submitted_params)
            if "successfully" in result:
                st.session_state.job_triggered = True
                st.success(f":white_check_mark: Job '{st.session_state.job_name}' has been successfully triggered!")
            else:
                st.error(result)

        if canceled:
            # Clear session state
            st.session_state.pop("job_name", None)
            st.session_state.pop("job_params", None)
            st.session_state.show_trigger_input = False
            st.success(":white_check_mark: Form canceled successfully.")
            st.rerun()

    # Process User Input for other operations
    if prompt := st.chat_input("Ask me anything about Jenkins (e.g., 'List jobs', 'Get build summary')..."):
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner(":thinking_face: Thinking..."):
                response = agent.run(prompt)
                st.markdown(response)
            
            st.session_state.messages.append({"role": "assistant", "content": response})

if __name__ == '__main__':
    pass

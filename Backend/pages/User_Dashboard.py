import streamlit as st
import pandas as pd
import requests
import os
from requests.auth import HTTPBasicAuth
import matplotlib.pyplot as plt
from auth.updated_database import get_user, users_collection
from bcrypt import checkpw
import math
import time
import psutil
import plotly.express as px
from datetime import datetime, timedelta
# from streamlit_autorefresh import st_autorefresh
import re
from dotenv import load_dotenv
# Add this to your existing imports:
from collections import defaultdict
load_dotenv("./config/auth.env")
import requests
import urllib3

# Disable warnings for unverified HTTPS requests
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# Jenkins Configuration
JENKINS_BASE_URL = os.getenv("JENKINS_BASE_URL")
JENKINS_USER = os.getenv("JENKINS_USER")
JENKINS_API_TOKEN = os.getenv("JENKINS_API_TOKEN")
API_KEY=os.getenv("JENKINS_API_TOKEN")

auth = (JENKINS_USER, JENKINS_API_TOKEN)

# Set page config
st.set_page_config(
    page_title="Jenkins Dashboard",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .stButton>button {
        background-color: #4CAF50;
        color: white;
        border-radius: 5px;
        padding: 0.25rem 0.5rem;
        border: none;
        font-size: 0.9rem;
    }
    .stButton>button:hover {
        background-color: #45a049;
        color: white;
    }
    .stTextInput>div>div>input, .stSelectbox>div>div>select {
        padding: 0.5rem;
    }
    .css-1aumxhk {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 20px;
    }
    .metric-card {
        background-color: white;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        margin-bottom: 20px;
    }
    .success {
        color: #4CAF50;
    }
    .error {
        color: #FF5733;
    }
    .warning {
        color: #FFC107;
    }
</style>
""", unsafe_allow_html=True)



def get_api_response(url, **kwargs):
    headers = kwargs.pop("headers", {})
    
    # Debug print: CURL equivalent
    curl_headers = ' '.join([f"-H '{key}: {value}'" for key, value in headers.items()])
    curl_command = f"curl -I -k --location -X GET '{url}' {curl_headers}"
    print("Generated cURL command:\n", curl_command)

    # Actual API call
    response = requests.get(url, headers=headers, verify=False, **kwargs)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed with status code: {response.status_code}")
        return {}


def get_job_build_stats(job_name):
    """Fetch build statistics for a specific Jenkins job."""
    url = f"{JENKINS_BASE_URL}/job/{job_name}/api/json?tree=builds[number,result]"
    headers = {"Authorization": f"Bearer {API_KEY}"}
    response = requests.get(url, headers=headers, verify=False)
    # response = requests.get(url, auth=auth)
    if response.status_code == 200:
        builds = response.json().get("builds", [])
        build_data = {
            "total_builds": len(builds),
            "success": len([build for build in builds if build.get("result") == "SUCCESS"]),
            "failure": len([build for build in builds if build.get("result") == "FAILURE"]),
            "aborted": len([build for build in builds if build.get("result") == "ABORTED"]),
            "running": len([build for build in builds if build.get("result") == None]),
        }
        return build_data
    else:
        st.error(f"❌ Failed to fetch build stats for job {job_name}. Status code: {response.status_code}")
        return None

def fetch_build_info(jenkins_url, job_name, build_number, user, token):
    """Fetch information about a specific build."""
    url = f"{jenkins_url}/job/{job_name}/{build_number}/api/json"
    headers = {"Authorization": f"Bearer {API_KEY}"}
    response = requests.get(url, headers=headers, verify=False)
    # response = requests.get(url, auth=(user, token))
    return response.json() if response.status_code == 200 else None

def fetch_test_report(jenkins_url, job_name, build_number, user, token):
    """Fetch test report for a specific build."""
    url = f"{jenkins_url}/job/{job_name}/{build_number}/testReport/api/json"
    headers = {"Authorization": f"Bearer {API_KEY}"}
    response = requests.get(url, headers=headers, verify=False)
    # response = requests.get(url, auth=(user, token))
    return response.json() if response.status_code == 200 else None

def format_duration(duration_ms):
    """Format duration from milliseconds to human-readable format."""
    seconds = duration_ms // 1000
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{hours}h {minutes}m {seconds}s" if hours > 0 else f"{minutes}m {seconds}s"

def format_timestamp(timestamp_ms):
    """Format timestamp from milliseconds to readable date/time."""
    dt = datetime.fromtimestamp(timestamp_ms / 1000)
    return dt.strftime("%Y-%m-%d %H:%M:%S")

# Main Dashboard
st.sidebar.image("https://www.jenkins.io/images/logos/jenkins/jenkins.png", width=100)
st.sidebar.markdown("### Jenkins Dashboard 🛠️")

# Buttons for Navigation
page = st.sidebar.radio(
    "Select Page", 
    ["Jenkins Job Statistics", "Node Status", "Test Suit Details"],
    label_visibility="collapsed"
)

if page == "Jenkins Job Statistics":
    st.markdown("<h1 style='text-align: center;'>📊 Jenkins Metrics Dashboard</h1>", unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["Job Statistics", "Test Case Metrics"])
    
    with tab1:
        st.subheader("🔎 Job Build Statistics")
        
        with st.expander("Search for a Job", expanded=True):
            job_name = st.text_input("Enter Jenkins Job Name", placeholder="e.g., my-pipeline-job")
            
            if job_name:
                stats = get_job_build_stats(job_name)
                if stats:
                    col1, col2, col3, col4, col5 = st.columns(5)
                    with col1:
                        st.metric("Total Builds", stats['total_builds'])
                    with col2:
                        st.metric("Success", stats['success'], delta_color="off", 
                                 help="Number of successful builds")
                    with col3:
                        st.metric("Failure", stats['failure'], delta_color="off")
                    with col4:
                        st.metric("Aborted", stats['aborted'], delta_color="off")
                    with col5:
                        st.metric("Running", stats['running'], delta_color="off")

                    st.subheader("🧮 Build Result Distribution")
                    total_builds = stats["total_builds"]
                    if total_builds > 0:
                        labels = ['Success', 'Failure', 'Aborted', 'Running']
                        sizes = [stats["success"], stats["failure"], stats["aborted"], stats["running"]]
                        colors = ['#4CAF50', '#FF5733', '#646d64', '#FFC107']

                        fig, ax = plt.subplots()
                        wedges, texts, autotexts = ax.pie(
                            sizes,
                            colors=colors,
                            autopct='%1.1f%%',
                            startangle=90,
                            textprops={'fontsize': 6}
                        )
                        ax.legend(wedges, labels, title="Results", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))
                        ax.axis('equal')
                        st.pyplot(fig)

                    else:
                        st.info("📌 No builds available for this job.")
    
    with tab2:
        st.subheader("✅ Test Case Metrics")
        
        with st.form("test_case_form"):
            col1, col2 = st.columns(2)
            with col1:
                job_name = st.text_input("Job Name", placeholder="Enter Jenkins Job Name")
            with col2:
                build_number = st.text_input("Build Number", placeholder="Enter Build Number")
            
            if st.form_submit_button("Fetch Metrics", use_container_width=True):
                if job_name and build_number:
                    build_info = fetch_build_info(JENKINS_BASE_URL, job_name, build_number, JENKINS_USER, JENKINS_API_TOKEN)
                    if build_info:
                        test_data = fetch_test_report(JENKINS_BASE_URL, job_name, build_number, JENKINS_USER, JENKINS_API_TOKEN)

                        # Extract build metadata
                        build_status = build_info.get("result", "UNKNOWN")
                        build_url = build_info.get("url")
                        start_time = format_timestamp(build_info["timestamp"])
                        duration = format_duration(build_info["duration"])

                        # Default values if test report not found
                        total = passed = failed = skipped = 0
                        failed_tests = []

                        if test_data:
                            total = test_data.get("totalCount", 0)
                            passed = test_data.get("passCount", 0)
                            failed = test_data.get("failCount", 0)
                            skipped = test_data.get("skipCount", 0)

                            failed_tests = [case["name"] for suite in test_data.get("suites", []) 
                                            for case in suite.get("cases", []) if case["status"] == "FAILED"]

                        # Display in a nice layout
                        st.markdown("### 📊 Build Information")
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Job Name", job_name)
                        with col2:
                            st.metric("Build Number", build_number)
                        with col3:
                            if build_status == "SUCCESS":
                                st.metric("Status", "SUCCESS", help="Build succeeded")
                            else:
                                st.metric("Status", build_status, delta="Failed", delta_color="inverse")

                        st.markdown("### ⏱ Execution Details")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Start Time", start_time)
                        with col2:
                            st.metric("Duration", duration)

                        st.markdown("### 🧪 Test Results")
                        if test_data:
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("Total Tests", total)
                            with col2:
                                st.metric("Passed", passed, f"{passed/total*100:.1f}%" if total > 0 else "N/A")
                            with col3:
                                st.metric("Failed", failed, f"{failed/total*100:.1f}%" if total > 0 else "N/A")
                            with col4:
                                st.metric("Skipped", skipped, f"{skipped/total*100:.1f}%" if total > 0 else "N/A")

                            if failed_tests:
                                with st.expander("View Failed Tests"):
                                    for test in failed_tests:
                                        st.error(f"❌ {test}")
                        else:
                            st.warning("No test data available for this build.")
                    else:
                        st.error("Failed to fetch build info.")
                else:
                    st.warning("Please enter both job name and build number.")

elif page == "Node Status":
    st.markdown("<h1 style='text-align: center;'>🖥️ Jenkins Node Status</h1>", unsafe_allow_html=True)
    
    def get_runnable_jobs():
        """Fetch all Jenkins jobs with color 'red' or 'blue'."""
        url = f"{JENKINS_BASE_URL}/api/json?tree=jobs[name,color]"
        headers = {"Authorization": f"Bearer {API_KEY}"}
        response = requests.get(url, headers=headers, verify=False)
        # response = requests.get(url, auth=(JENKINS_USER, JENKINS_API_TOKEN))
        if response.status_code == 200:
            jobs = response.json().get("jobs", [])
            runnable_jobs = [
                job["name"] for job in jobs if job.get("color") in ["red", "blue", "notbuilt"]
            ]
            return runnable_jobs
        else:
            st.error(f"❌ Failed to fetch jobs. Status code: {response.status_code}")
            return []

    def get_node_resource_usage():
        url = f"{JENKINS_BASE_URL}/computer/api/json?depth=2"
        headers = {"Authorization": f"Bearer {API_KEY}"}
        response = requests.get(url, headers=headers, verify=False)
        # response = requests.get(url, auth=(JENKINS_USER, JENKINS_API_TOKEN))
        if response.status_code == 200:
            return response.json().get("computer", [])
        else:
            st.error(f"❌ Failed to fetch node resource usage. Status code: {response.status_code}")
            return []

    def get_running_jobs():
        """Fetch all currently running Jenkins jobs and their URLs."""
        url = f"{JENKINS_BASE_URL}/computer/api/json?depth=2"
        headers = {"Authorization": f"Bearer {API_KEY}"}
        response = requests.get(url, headers=headers, verify=False)
        # response = requests.get(url, auth=(JENKINS_USER, JENKINS_API_TOKEN))

        running_jobs = []

        if response.status_code == 200:
            computers = response.json().get("computer", [])
            for computer in computers:
                executors = computer.get("executors", [])
                for executor in executors:
                    current_executable = executor.get("currentExecutable")
                    if current_executable:
                        job_name = current_executable.get("fullDisplayName")
                        job_url = current_executable.get("url")
                        if job_name and job_url:
                            running_jobs.append((job_name, job_url))
        else:
            st.error(f"❌ Failed to fetch running jobs. Status code: {response.status_code}")

        return running_jobs

    def extract_build_number(job_string):
        match = re.search(r"#(\d+)", job_string)
        if match:
            return int(match.group(1))
        else:
            raise ValueError("Build number not found in string")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("✅ Runnable Jenkins Jobs")
        runnable_jobs = get_runnable_jobs()
        st.metric("Total Runnable Jobs", len(runnable_jobs))
        
        with st.expander("View Runnable Jobs"):
            if runnable_jobs:
                for job in runnable_jobs:
                    st.markdown(f"- 🔧 **{job}**")
            else:
                st.info("No runnable jobs found")
    
    with col2:
        st.subheader("🏃‍♂️ Currently Running Jobs")
        running_jobs = get_running_jobs()
        st.metric("Active Jobs", len(running_jobs))
        
        with st.expander("Manage Running Jobs"):
            if running_jobs:
                for job_name, job_url in running_jobs:
                    st.markdown(f"- 🚀 **{job_name}**")

                    try:
                        build_number = extract_build_number(job_name)
                        stop_url = f"{job_url}stop"

                        if st.button(f"🛑 Stop '{job_name}'", key=job_name):
                            stop_response = requests.post(stop_url, auth=(JENKINS_USER, JENKINS_API_TOKEN))
                            if stop_response.status_code == 200:
                                st.success(f"✅ Successfully stopped job: {job_name}")
                            else:
                                st.error(f"❌ Failed to stop job: {job_name}. Status: {stop_response.status_code}")
                    except Exception as e:
                        st.error(f"⚠️ Unable to parse or stop job '{job_name}'. Error: {e}")
            else:
                st.success("✅ No jobs are currently running.")

    st.markdown("---")
    st.subheader("🖥️ Node Resource Status")
    
    def format_gib(bytes_val):
        if isinstance(bytes_val, (int, float)):
            return f"{bytes_val / (1024**3):.2f} GiB"
        return "N/A"

    def fetch_node_data():
        API_URL = f"{JENKINS_BASE_URL}/computer/api/json?depth=1"
        headers = {"Authorization": f"Bearer {API_KEY}"}
        response = requests.get(API_URL, headers=headers, verify=False)
        try:
            # response = requests.get(API_URL, auth=(JENKINS_USER, JENKINS_API_TOKEN))
            # response = requests.get(API_URL, headers=headers, verify=False)
            if response.status_code != 200:
                st.error(f"Jenkins returned status code {response.status_code}")
                return pd.DataFrame()
            
            data = response.json()
            nodes = data.get("computer", [])

            rows = []
            for node in nodes:
                monitor_data = node.get("monitorData", {})
                swap_monitor = monitor_data.get("hudson.node_monitors.SwapSpaceMonitor", {})
                temp_monitor = monitor_data.get("hudson.node_monitors.TemporarySpaceMonitor", {})
                disk_monitor = monitor_data.get("hudson.node_monitors.DiskSpaceMonitor", {})
                
                free_swap = swap_monitor.get("availableSwapSpace", None)
                free_temp = temp_monitor.get("size", None)
                free_disk = disk_monitor.get("size", None)
                response_time = node.get("responseTime", None)
                response_time_str = f"{response_time} ms" if response_time is not None else "Unavailable"

                rows.append({
                    "🖥️ Node": node.get("displayName", "N/A"),
                    "Online": "✅ Yes" if not node.get("offline") else "❌ No",
                    "Executors": node.get('numExecutors', 0),
                    "Free Disk Space": format_gib(free_disk),
                    "Free Swap Space": format_gib(free_swap),
                    "Free Temp Space": format_gib(free_temp),
                    "Response Time": response_time_str
                })

            return pd.DataFrame(rows)
        except Exception as e:
            st.error(f"Error fetching data from Jenkins: {e}")
            return pd.DataFrame()

    if st.button("🔄 Refresh Node Data", use_container_width=True):
        st.rerun()
        
    data = fetch_node_data()
    if not data.empty:
        st.dataframe(data, use_container_width=True)
        
        # Convert GiB-formatted strings back to floats
        def parse_gib(gib_str):
            try:
                return float(gib_str.split()[0])
            except:
                return 0

        # Resource charts
        st.subheader("📊 Resource Utilization")
        
        data["Parsed Free Disk"] = data["Free Disk Space"].apply(parse_gib)
        data["Parsed Free Swap"] = data["Free Swap Space"].apply(parse_gib)
        data["Parsed Free Temp"] = data["Free Temp Space"].apply(parse_gib)

        # Disk Space Bar Chart
        disk_bar = px.bar(
            data,
            x="Parsed Free Disk",
            y="🖥️ Node",
            orientation="h",
            title="💽 Free Disk Space per Node (GiB)",
            labels={"Parsed Free Disk": "GiB"},
            color="🖥️ Node"
        )

        # Swap Space Bar Chart
        swap_bar = px.bar(
            data,
            x="Parsed Free Swap",
            y="🖥️ Node",
            orientation="h",
            title="🔃 Free Swap Space per Node (GiB)",
            labels={"Parsed Free Swap": "GiB"},
            color="🖥️ Node"
        )

        # Temp Space Bar Chart
        temp_bar = px.bar(
            data,
            x="Parsed Free Temp",
            y="🖥️ Node",
            orientation="h",
            title="🧊 Free Temp Space per Node (GiB)",
            labels={"Parsed Free Temp": "GiB"},
            color="🖥️ Node"
        )

        # Display charts
        st.plotly_chart(disk_bar, use_container_width=True)
        st.plotly_chart(swap_bar, use_container_width=True)
        st.plotly_chart(temp_bar, use_container_width=True)
        
        # Pie chart of total resources
        st.subheader("🔍 Total Free Resources")
        total_free_disk = data["Parsed Free Disk"].sum()
        total_free_swap = data["Parsed Free Swap"].sum()
        total_free_temp = data["Parsed Free Temp"].sum()

        pie_labels = ["Free Disk Space", "Free Swap Space", "Free Temp Space"]
        pie_values = [total_free_disk, total_free_swap, total_free_temp]

        fig = px.pie(
            names=pie_labels,
            values=pie_values,
            title="Resource Distribution Across All Nodes",
            hole=0.4
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No node data available.")

elif page == "Test Suit Details":
    HEADERS = {"Authorization": f"Bearer {API_KEY}"}
    def get_all_jobs():
        url = f"{JENKINS_BASE_URL}/api/json"
        res = requests.get(url, headers=HEADERS, verify=False)
        if res.status_code == 200:
            jobs = res.json().get("jobs", [])
            return [job["name"] for job in jobs]
        return []

    def get_job_views(job_name):
        url = f"{JENKINS_BASE_URL}/api/json"
        res = requests.get(url, headers=HEADERS, verify=False)
        if res.status_code == 200:
            views = res.json().get("views", [])
            job_views = []
            for view in views:
                view_url = view["url"] + "api/json"
                view_data = requests.get(view_url, headers=HEADERS, verify=False).json()
                for job in view_data.get("jobs", []):
                    if job["name"] == job_name:
                        job_views.append(view["name"])
            return job_views
        return []

    def get_builds_for_job(job_name):
        url = f"{JENKINS_BASE_URL}/job/{job_name}/api/json"
        res = requests.get(url, headers=HEADERS, verify=False)
        if res.status_code == 200:
            builds = res.json().get("builds", [])
            return [str(build["number"]) for build in builds]
        return []

    def get_test_suite_details(job_name, build_number):
        url = f"{JENKINS_BASE_URL}/job/{job_name}/{build_number}/wfapi/describe"
        res = requests.get(url, headers=HEADERS, verify=False)
        if res.status_code == 200:
            return res.json()
        return {}
    
    def get_all_views_with_job_counts():
        """New function to get all views with their job counts"""
        url = f"{JENKINS_BASE_URL}/api/json"
        res = requests.get(url, headers=HEADERS, verify=False)
        if res.status_code == 200:
            views = res.json().get("views", [])
            view_counts = []
            for view in views:
                if view["name"].lower() == "all":
                    continue
                view_url = view["url"] + "api/json"
                view_data = requests.get(view_url, headers=HEADERS, verify=False).json()
                job_count = len(view_data.get("jobs", []))
                view_counts.append({
                    "view_name": view["name"],
                    "job_count": job_count
                })
            return view_counts
        return []

    # ----------------- Streamlit UI -----------------
    st.markdown("<h1 style='text-align: center;'>🖥️ Test Suit Details</h1>", unsafe_allow_html=True)
    tabu1, tabu2 = st.tabs(["Views", "Test Suits"])
    
    with tabu1:
        
        # First Row - View Distribution (existing chart)
        view_counts = get_all_views_with_job_counts()
        
        if not view_counts:
            st.warning("No view data available")
        else:
            df_views = pd.DataFrame(view_counts)
            
            if len(df_views) > 0:
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("📊 View Analytics Dashboard")
                    fig1 = px.pie(
                        df_views,
                        values='job_count',
                        names='view_name',
                        title='Jobs per View (Excluding "All")',
                        hole=0.3,
                        color_discrete_sequence=px.colors.qualitative.Pastel
                    )
                    st.plotly_chart(fig1, use_container_width=True)
                
                # Second Row - Status Distribution for Selected View
                with col2:
                    st.markdown("### Job Distribution Across Views")
                    selected_view = st.selectbox(
                        "Select a view to analyze job statuses:",
                        df_views['view_name'],
                        key="status_view_select"
                    )
                    
                    if selected_view:
                        with st.spinner(f"Loading job statuses for {selected_view}..."):
                            # Get job statuses for the selected view
                            status_counts = {'SUCCESS': 0, 'FAILURE': 0, 'ABORTED': 0, 'RUNNING': 0}
                            
                            # Find the view's jobs
                            view_url = f"{JENKINS_BASE_URL}/api/json"
                            res = requests.get(view_url, headers=HEADERS, verify=False)
                            if res.status_code == 200:
                                for view in res.json().get("views", []):
                                    if view["name"] == selected_view:
                                        view_jobs_url = view["url"] + "api/json"
                                        view_jobs = requests.get(view_jobs_url, headers=HEADERS, verify=False).json()
                                        for job in view_jobs.get("jobs", []):
                                            job_url = f"{JENKINS_BASE_URL}/job/{job['name']}/lastBuild/api/json?tree=result"
                                            job_res = requests.get(job_url, headers=HEADERS, verify=False)
                                            if job_res.status_code == 200:
                                                status = job_res.json().get("result", "UNKNOWN")
                                                if status in status_counts:
                                                    status_counts[status] += 1
                                                    
                            # Create the status pie chart
                            df_status = pd.DataFrame({
                                'Status': list(status_counts.keys()),
                                'Count': list(status_counts.values())
                            })
                            
                            fig2 = px.pie(
                                df_status,
                                values='Count',
                                names='Status',
                                title=f'Job Statuses in {selected_view}',
                                color='Status',
                                color_discrete_map={
                                    'SUCCESS': '#2ecc71',
                                    'FAILURE': '#e74c3c',
                                    'ABORTED': '#f39c12',
                                    'RUNNING': '#3498db'
                                }
                            )
                            st.plotly_chart(fig2, use_container_width=True)
                            
                            # Display summary metrics
                            st.markdown("**Status Summary:**")
                            cols = st.columns(4)
                            cols[0].metric("Success", status_counts['SUCCESS'])
                            cols[1].metric("Failed", status_counts['FAILURE'])
                            cols[2].metric("Aborted", status_counts['ABORTED'])
                            cols[3].metric("Running", status_counts['RUNNING'])
            else:
                st.info("No views available (other than 'All' view)")

    with tabu2:
        st.subheader("📋 Test Suite Explorer")
        
        # Create expandable sections for better organization
        with st.expander("🔍 Select View/Folder", expanded=True):
            # Get all views (excluding 'All')
            views_data = get_all_views_with_job_counts()
            view_names = [view["view_name"] for view in views_data] if views_data else []
            
            if not view_names:
                st.warning("No views available")
            else:
                selected_view = st.selectbox(
                    "Select a View/Folder:",
                    view_names,
                    key="view_select",
                    help="Select a Jenkins view/folder to explore"
                )
        
        if 'selected_view' in locals() and selected_view:
            with st.expander("🔧 Select Job", expanded=True):
                # Get jobs for selected view
                view_jobs = []
                url = f"{JENKINS_BASE_URL}/api/json"
                res = requests.get(url, headers=HEADERS, verify=False)
                if res.status_code == 200:
                    for view in res.json().get("views", []):
                        if view["name"] == selected_view:
                            view_url = view["url"] + "api/json"
                            view_data = requests.get(view_url, headers=HEADERS, verify=False).json()
                            view_jobs = [job["name"] for job in view_data.get("jobs", [])]
                            break
                
                if not view_jobs:
                    st.warning(f"No jobs found in view: {selected_view}")
                else:
                    selected_job = st.selectbox(
                        "Select a Job:",
                        sorted(view_jobs),
                        key="job_select",
                        help="Select a Jenkins job to inspect"
                    )
        
        if 'selected_job' in locals() and selected_job:
            with st.expander("🏗 Select Build", expanded=True):
                # Get builds for selected job
                builds = get_builds_for_job(selected_job)
                
                if not builds:
                    st.warning(f"No builds found for job: {selected_job}")
                else:
                    # Enhance build display with status information
                    build_info = []
                    for build_num in builds[:50]:  # Limit to 50 most recent builds
                        build_url = f"{JENKINS_BASE_URL}/job/{selected_job}/{build_num}/api/json"
                        res = requests.get(build_url, headers=HEADERS, verify=False)
                        if res.status_code == 200:
                            build_data = res.json()
                            status = build_data.get("result", "RUNNING")
                            timestamp = datetime.fromtimestamp(build_data["timestamp"]/1000).strftime('%Y-%m-%d %H:%M')
                            build_info.append({
                                "number": build_num,
                                "status": status,
                                "timestamp": timestamp
                            })
                    
                    if not build_info:
                        st.warning("Could not fetch build details")
                    else:
                        # Create formatted display options
                        build_options = [
                            f"#{b['number']} ({b['status']}) - {b['timestamp']}"
                            for b in sorted(build_info, key=lambda x: x['number'], reverse=True)
                        ]
                        
                        selected_build_display = st.selectbox(
                            "Select a Build:",
                            build_options,
                            key="build_select",
                            help="Select a build number to analyze"
                        )
                        selected_build = selected_build_display.split("#")[1].split(" ")[0]
        
        # Display pipeline details when build is selected
        if 'selected_build' in locals() and selected_build:
            st.subheader("📋 Pipeline Stages")
            with st.spinner("Loading pipeline details..."):
                pipeline_data = get_test_suite_details(selected_job, selected_build)
                
                if not pipeline_data:
                    st.error("Failed to fetch pipeline data")
                else:
                    stages = pipeline_data.get("stages", [])
                    if stages:
                        # Enhanced dataframe display
                        df = pd.DataFrame([{
                            "Stage": stage.get("name", "Unnamed"),
                            "Status": stage.get("status", "UNKNOWN"),
                            "Duration (s)": round(stage.get("durationMillis", 0) / 1000, 2),
                            "Start Offset (s)": round(
                                (stage.get("startTimeMillis", 0) - 
                                pipeline_data.get("startTimeMillis", 0)) / 1000, 2)
                        } for stage in stages])
                        
                        # Color coding for status
                        status_colors = {
                            "SUCCESS": "green",
                            "FAILED": "red",
                            "UNKNOWN": "gray"
                        }
                        
                        st.dataframe(
                            df.style.applymap(
                                lambda x: f"color: {status_colors.get(x, 'black')}", 
                                subset=["Status"]
                            ),
                            use_container_width=True,
                            height=min(40 * len(stages), 400))  # Dynamic height
                    else:
                        st.warning("No stages found in this pipeline")

    # st.markdown("<h1 style='text-align: center;'>🖥️ Deeper Info</h1>", unsafe_allow_html=True)
    # job_name = st.text_input("Enter Jenkins Job Name")
    # build_number = st.text_input("Enter Build Number")
    

    # def get_pipeline_json(job_name, build_number):
    #     url = f"{JENKINS_BASE_URL}/job/{job_name}/{build_number}/wfapi/describe"
    #     headers = {"Authorization": f"Bearer {API_KEY}"}
    #     response = requests.get(url, headers=headers, verify=False)
    #     st.write("🔗 Fetched pipeline API:", url)

    #     if response.status_code == 200:
    #         data = response.json()
    #         stages = data.get("stages", [])
    #         if not stages:
    #             st.warning("No pipeline stages found.")
    #             return

    #         df = pd.DataFrame([{
    #             "Stage Name": stage.get("name", "Unnamed"),
    #             "Status": stage.get("status", "UNKNOWN"),
    #             "Start Time": stage.get("startTimeMillis", 0),
    #             "Duration (s)": round(stage.get("durationMillis", 0) / 1000, 2)
    #         } for stage in stages])

    #         # Convert start time from millis to readable time (relative to build start)
    #         build_start = data.get("startTimeMillis", 0)
    #         df["Start Time (s after build start)"] = ((df["Start Time"] - build_start) / 1000).round(2)
    #         df.drop(columns=["Start Time"], inplace=True)

    #         # Reorder columns for readability
    #         df = df[["Stage Name", "Status", "Start Time (s after build start)", "Duration (s)"]]

    #         st.dataframe(df, use_container_width=True)
    #     else:
    #         st.error(f"Failed to fetch pipeline structure: {response.status_code}")

    # if job_name and build_number:
    #     # st.subheader("📊 Test Report")
    #     # test_data = get_test_case_details(job_name, build_number)
    #     # if test_data:
    #     #     display_test_case_summary_chart(test_data)
    #     #     display_test_cases(test_data)

    #     # st.subheader("📄 Raw Flow Graph HTML")
    #     # get_flow_graph_html(job_name, build_number)

    #     st.subheader("📋 Structured Pipeline Info (wfapi/describe)")
    #     get_pipeline_json(job_name, build_number)

    # else:
    #     st.info("Please enter both a job name and a build number to view deeper test case info.")
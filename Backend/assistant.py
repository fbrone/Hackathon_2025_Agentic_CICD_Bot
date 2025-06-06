
import streamlit as st
from datetime import datetime
import re
import random
import requests
import os
from dotenv import load_dotenv
from auth.updated_database import (
    get_notification, update_notification,
    add_inquired_job, add_triggered_job,
    update_job_status_for_all_users,
    notification_collection,
    get_completed_inquired_notifications,
    mark_notifications_as_read, add_notification, get_unread_notifications, mark_notification_as_read, initialize_database
)
from pages.Chatbot_UI import get_last_build_summary, trigger_job, get_specific_build_summary
from datetime import time
import logging

# Load Jenkins credentials
load_dotenv("./config/auth.env")
JENKINS_URL = os.getenv("JENKINS_BASE_URL")
JENKINS_USER = os.getenv("JENKINS_USER")
JENKINS_API_TOKEN = os.getenv("JENKINS_API_TOKEN")
JENKINS_AUTH = (JENKINS_USER, JENKINS_API_TOKEN)


# Utility functions
def get_last_build_number(job_name):
    url = f"{JENKINS_URL}/job/{job_name}/api/json"
    headers = {"Authorization": f"Bearer {JENKINS_API_TOKEN}"}
    requests.packages.urllib3.disable_warnings()
    res = requests.get(url, headers=headers, verify=False)
    if res.ok:
        return res.json().get("lastBuild", {}).get("number")
    return None

def check_build_status(job_name, build_number):
    url = f"{JENKINS_URL}/job/{job_name}/{build_number}/api/json"
    headers = {"Authorization": f"Bearer {JENKINS_API_TOKEN}"}
    requests.packages.urllib3.disable_warnings()
    res = requests.get(url, headers=headers, verify=False)
    if res.ok:
        data = res.json()
        if data.get("building"):
            return "RUNNING"
        return data.get("result")
    return None

def poll_job_statuses():
    """Background task to check job statuses and update notifications"""
    users = notification_collection.find({})
    for user in users:
        username = user["username"]
        # Check both inquired and triggered jobs
        for job_type in ["inquired_jobs", "triggered_jobs"]:
            for job in user.get(job_type, []):
                if job.get("status") == "running":
                    current_status = check_build_status(job["job_name"], job["build_number"])
                    if current_status in ["SUCCESS", "FAILURE", "ABORTED"]:
                        update_job_status_for_all_users(
                            job["job_name"], 
                            job["build_number"], 
                            current_status.lower(),
                            f"Build #{job['build_number']} of {job['job_name']} completed: {current_status}"
                        )
                        add_notification(
                            username,
                            job["job_name"],
                            job["build_number"],
                            current_status.lower(),
                            "inquired" if job_type == "inquired_jobs" else "triggered"
                        )

class JenkinsAssistant:
    def __init__(self, username):
        self.username = username
        self.user_data = get_notification(username) or {}
        self.notification_status = self.user_data.get("notification_status", "on")
        self.check_completed_jobs()

    def check_completed_jobs(self):
        """Check both inquired AND triggered jobs"""
        user_data = get_notification(self.username)
        if not user_data:
            return

        for job_type in ["inquired_jobs", "triggered_jobs"]:  # Check both types
            for job in user_data.get(job_type, []):
                if job.get("status") == "running":
                    current_status = check_build_status(job["job_name"], job["build_number"])
                    if current_status in ["SUCCESS", "FAILURE", "ABORTED"]:
                        update_job_status_for_all_users(
                            job["job_name"], job["build_number"], 
                            current_status.lower(),
                            f"Build #{job['build_number']} of {job['job_name']} completed: {current_status}"
                        )
                        add_notification(
                            self.username,
                            job["job_name"],
                            job["build_number"],
                            current_status.lower(),
                            job_type.split('_')[0]  # "inquired" or "triggered"
                        )

    def show_notifications(self):
        """Display unread notifications"""
        notifications = get_unread_notifications(self.username)
        if not notifications:
            return False

        with st.expander("🔔 Notifications", expanded=True):
            for i, notif in enumerate(notifications):
                status_emoji = "✅" if notif["status"] == "success" else "❌"
                col1, col2 = st.columns([0.8, 0.2])
                
                with col1:
                    st.markdown(f"""
                    {status_emoji} **{notif['job_name']}** (Build #{notif['build_number']})  
                    Status: {notif['status'].upper()}  
                    <small>{notif['timestamp'].strftime('%Y-%m-%d %H:%M')}</small>
                    """, unsafe_allow_html=True)
                
                with col2:
                    # Add unique index to the key
                    if st.button(
                        "Mark as read", 
                        key=f"read_{notif['job_name']}_{notif['build_number']}_{i}"  # Added index
                    ):
                        mark_notification_as_read(
                            self.username,
                            notif["job_name"],
                            notif["build_number"]
                        )
                        st.rerun()
            
            st.markdown("---")
            if st.button("Mark all as read", key="mark_all_read"):
                for notif in notifications:
                    mark_notification_as_read(
                        self.username,
                        notif["job_name"],
                        notif["build_number"]
                    )
                st.rerun()
        
        return True

    def toggle_notifications(self):
        toggled = st.toggle(
            "🔕 Snooze Notifications" if self.notification_status == "on" else "🔔 Enable Notifications",
            value=(self.notification_status == "off")
        )
        status = "off" if toggled else "on"
        if status != self.notification_status:
            update_notification(self.username, {"notification_status": status})
            st.toast("Notifications " + ("snoozed" if status == "off" else "enabled"))
            self.notification_status = status

    def check_if_tracked_build_finished(self):
        """Notify user if a previously inquired or triggered running build has finished."""
        note = get_notification(self.username)

        if not note or note.get("notification_status", "on") == "off":
            return

        activity = note.get("activity", "")
        if ":running" not in activity:
            return

        job_name = note.get("job_name")
        build_id = note.get("build_id")
        if not job_name or not build_id:
            return

        status = check_build_status(job_name, build_id)
        if status in ["SUCCESS", "FAILURE", "ABORTED"]:
            update_notification(
                self.username,
                {
                    "activity": activity.replace("running", "done"),
                    "subject": f"Build #{build_id} of {job_name} completed with status {status}",
                    "job_name": job_name,
                    "build_id": build_id
                }
            )
            if status == "SUCCESS":
                st.success(f"🎉 Your build #{build_id} of **{job_name}** completed successfully!")
            else:
                st.error(f"❌ Your build #{build_id} of **{job_name}** completed with status: {status}!")
    
    def handle_query(self, user_input):
        self.check_if_tracked_build_finished()

        if any(word in user_input.lower() for word in ["hi", "hello", "hey"]):
            return random.choice(["Hello!", "Hi there!", "Hey! How can I help?"])

        # Specific build summary inquiry
        specific_match = re.search(
            r"summary of ([a-zA-Z0-9_\-]+) (with|for|whose)? build number (\d+)", user_input.lower()
        )
        if specific_match:
            job = specific_match.group(1)
            build_number = specific_match.group(3)
            status = check_build_status(job, build_number)
            summary = get_specific_build_summary(user_input)

            if status == "RUNNING":
                subject = f"Build #{build_number} of {job} is running. You'll be notified when done."
                update_notification(self.username, {
                    "activity": f"inquiry:{job}:{build_number}:running",
                    "subject": subject,
                    "job_name": job,
                    "build_id": build_number
                })
                add_inquired_job(self.username, job, build_number, subject)
            else:
                update_notification(self.username, {
                    "activity": f"inquiry:{job}:{build_number}:done",
                    "subject": f"Build #{build_number} of {job} completed: {status}",
                    "job_name": job,
                    "build_id": build_number
                })
            return summary

        # General build summary
        match = re.search(r"summary of ([a-zA-Z0-9_\-]+)", user_input.lower())
        if match:
            job = match.group(1)
            build_id = get_last_build_number(job)
            if not build_id:
                return f"No builds found for **{job}**"

            status = check_build_status(job, build_id)
            summary = get_last_build_summary(job)

            if status == "RUNNING":
                subject = f"Build #{build_id} of {job} is running. You'll be notified when done."
                update_notification(self.username, {
                    "activity": f"inquiry:{job}:{build_id}:running",
                    "subject": subject,
                    "job_name": job,
                    "build_id": build_id
                })
                add_inquired_job(self.username, job, build_id, subject)
                return f"Build #{build_id} of **{job}** is still running. You’ll be notified when it finishes."
            else:
                update_notification(self.username, {
                    "activity": f"inquiry:{job}:{build_id}:done",
                    "subject": f"Build #{build_id} of {job} completed: {status}",
                    "job_name": job,
                    "build_id": build_id
                })
                return f"Build #{build_id} of **{job}** is completed with satus: {status}\n\n{summary}"

        return "Ask me about Jenkins build summary, like: `build summary of qe-trigger-squid-sanity-openstack`"

    def run(self):
        st.title("🤖 Jenkins Assistant")
        self.toggle_notifications()
        self.show_notifications()
        st.markdown("---")

        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                if msg["role"] == "assistant":
                    st.markdown(msg["content"], unsafe_allow_html=True)
                else:
                    st.markdown(msg["content"])


        if prompt := st.chat_input("Ask me something about Jenkins..."):
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                response = self.handle_query(prompt)
                if response is None:
                    response = "Hmm, I didn't get that. Try again?"
                st.markdown(response, unsafe_allow_html=True)
                st.session_state.chat_history.append({"role": "assistant", "content": response})

        if st.button("🗑️ Clear Chat"):
            st.session_state.chat_history = []
            st.rerun()





# def notification_ui(username):
#     st.markdown(
#         """
#         <style>
#         .notification-bell {
#             position: absolute;
#             top: 1rem;
#             right: 1rem;
#             font-size: 24px;
#             cursor: pointer;
#         }
#         .notification-dropdown {
#             position: absolute;
#             top: 3rem;
#             right: 1rem;
#             width: 300px;
#             background-color: white;
#             box-shadow: 0 4px 8px rgba(0,0,0,0.1);
#             border-radius: 0.5rem;
#             padding: 1rem;
#             z-index: 1000;
#         }
#         </style>
#         """,
#         unsafe_allow_html=True
#     )

#     if "show_notifications" not in st.session_state:
#         st.session_state.show_notifications = False

#     notif_count = len(get_completed_inquired_notifications(username))
#     bell_label = "🔔" + (f" ({notif_count})" if notif_count else "")

#     if st.button(bell_label, key="notification_bell", help="Click to view notifications"):
#         st.session_state.show_notifications = not st.session_state.show_notifications

#     if st.session_state.show_notifications:
#         notifications = get_completed_inquired_notifications(username)
#         with st.container():
#             st.markdown('<div class="notification-dropdown">', unsafe_allow_html=True)
#             if notifications:
#                 for notif in notifications:
#                     st.markdown(f"""
#                     <div>
#                         ✅ Job <b>{notif['job_name']}</b> (Build #{notif['build_id']}) completed.
#                         <br><small>{notif['timestamp']}</small>
#                         <hr>
#                     </div>
#                     """, unsafe_allow_html=True)
#                 if st.button("Mark all as read", key="mark_read"):
#                     mark_notifications_as_read(username)
#                     st.success("Notifications marked as read.")
#                     st.session_state.show_notifications = False
#             else:
#                 st.write("No new notifications.")
#             st.markdown('</div>', unsafe_allow_html=True)

def get_build_status(job_name, build_id):
    url = f"{JENKINS_URL}/job/{job_name}/{build_id}/api/json"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return "COMPLETED" if data.get("result") else "RUNNING"
    return None

def update_notifications():
    users = notification_collection.find({})
    for user in users:
        updated = False
        for notif in user.get("notifications", []):
            if notif["status"] == "RUNNING":
                current_status = get_build_status(notif["job_name"], notif["build_id"])
                if current_status == "COMPLETED":
                    notif["status"] = "COMPLETED"
                    notif["timestamp"] = datetime.utcnow().isoformat()
                    updated = True
        if updated:
            notification_collection.update_one(
                {"username": user["username"]},
                {"$set": {"notifications": user["notifications"]}}
            )



    
def run_assistant(username):
    # notification_ui(username)
    assistant = JenkinsAssistant(username)
    assistant.run()


if __name__ == "__main__":

    initialize_database() 
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('jenkins_assistant.log'),
            logging.StreamHandler()
        ]
    )

    def log_error(error):
        """Helper function to log errors"""
        logging.error(f"Job polling error: {str(error)}", exc_info=True)

    def run_poller():
        """Main polling loop with error handling"""
        while True:
            try:
                logging.info("Starting job status poll...")
                update_notifications()
                poll_job_statuses()
                logging.info("Polling completed. Sleeping for 60 seconds...")
                time.sleep(60)
            except KeyboardInterrupt:
                logging.info("Received shutdown signal, exiting...")
                break
            except Exception as e:
                log_error(e)
                time.sleep(60)  # Wait before retrying after error

    run_poller()

# Run periodically (e.g. with cron or background thread)
# if __name__ == "__main__":
#     update_notifications()
#     while True:
#         poll_job_statuses()
#         time.sleep(60)

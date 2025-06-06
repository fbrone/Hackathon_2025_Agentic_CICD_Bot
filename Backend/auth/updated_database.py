
from pymongo import MongoClient
from pymongo.errors import PyMongoError
import os
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv("../config/auth.env")

# MongoDB Configuration
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "jenkins_ai"

# Database Connection
client = MongoClient(MONGO_URI)
db = client[DB_NAME]

# Collections
users_collection = db["users"]
admin_jobs_collection = db["admin_jobs"]
non_admin_jobs_collection = db["non_admin_jobs"]
all_jobs_collection = db["all_jobs"]
role_requests_collection = db["role_requests"]

notification_collection = db["notification_collection"]



# ==============================
#        USER OPERATIONS
# ==============================


def store_user(email, role, username, company, team):
    print("📝 Storing user in MongoDB...")
    print(f"email={email}, role={role}, username={username}, company={company}, team={team}")
    try:
        result = users_collection.update_one(
            {"email": email},
            {
                "$set": {
                    "role": role,
                    "username": username,
                    "company": company,
                    "team": team,
                    "last_login": datetime.utcnow()
                }
            },
            upsert=True
        )
        print(f"✅ Matched: {result.matched_count}, Modified: {result.modified_count}, Upserted: {result.upserted_id}")
    except Exception as e:
        print(f"❌ MongoDB error: {e}")




# def get_user(email):
#     return users_collection.find_one({"email": email})


def get_user(username):
    """Retrieve user details from MongoDB."""
    return users_collection.find_one({"username": username}, {"_id": 0})

def get_user_projects(username):
        user = users_collection.find_one({"username": username})
        return user.get("projects", []) if user else []



def add_user(username, hashed_password, role, email, jenkins_api_key, requested_admin=False):
    # def add_user(username, hashed_password, role, email, jenkins_api_key, requested_admin=False):
    if users_collection.find_one({"username": username}):
        return "❌ Username already exists!"

    user_data = {
        "username": username,
        "password": hashed_password,
        "role": role,
        "email": email,
        "jenkins_api_key": jenkins_api_key,
        "requested_admin": requested_admin,
    }

    try:
        result = users_collection.insert_one(user_data)
        if result.inserted_id:
            print(f"✅ User {username} registered successfully! Inserted ID: {result.inserted_id}")  # Debugging
        return "✅ User registered successfully!"
    except Exception as e:
        print("❌ MongoDB Insert Error:", str(e))  # Debugging
        return f"❌ Database Error: {str(e)}"


def get_all_users():
    """Retrieve all registered users (Admin-only feature)."""
    try:
        return list(users_collection.find({}, {"_id": 0, "password": 0}))
    except PyMongoError as e:
        return f"❌ Database Error: {str(e)}"

def request_admin_role(username):
    """Allow non-admin users to request admin role."""
    if not get_user(username):
        return "❌ User does not exist."
    
    if role_requests_collection.find_one({"username": username}):
        return "❗ Admin role request already submitted."
    
    try:
        role_requests_collection.insert_one({"username": username})
        return "✅ Admin role request submitted successfully."
    except PyMongoError as e:
        return f"❌ Database Error: {str(e)}"

def get_admin_requests():
    """Fetch all pending admin role requests."""
    try:
        return list(role_requests_collection.find({}, {"_id": 0}))
    except PyMongoError as e:
        return f"❌ Database Error: {str(e)}"

def update_user_role(username, new_role):
    """Update a user's role (Admin-only feature)."""
    if not get_user(username):
        return "❌ User does not exist."
    
    try:
        users_collection.update_one({"username": username}, {"$set": {"role": new_role}})
        role_requests_collection.delete_one({"username": username})  # Clear role request if approved
        return f"✅ {username} is now an {new_role}."
    except PyMongoError as e:
        return f"❌ Database Error: {str(e)}"

# ==============================
#        JOB OPERATIONS
# ==============================


def store_jobs(jobs):
    """Store jobs in MongoDB and categorize them correctly."""
    admin_jobs, non_admin_jobs = [], []

    try:
        # Clear collections before inserting new jobs
        all_jobs_collection.delete_many({})
        all_jobs_collection.insert_many(jobs)  # Store all jobs for reference
        

        for job in jobs:
            # Store all jobs in admin_jobs
            admin_jobs.append(job)

        for job in jobs:
            # Categorize jobs based on the presence of "trigger" in the name
            if "trigger" not in job["name"].lower():
                non_admin_jobs.append(job)  # Store only non-trigger jobs in non-admin

        # Store all jobs in admin_jobs_collection
        if admin_jobs:
            admin_jobs_collection.delete_many({})
            admin_jobs_collection.insert_many(jobs)

        # Store only non-trigger jobs in non_admin_jobs_collection
        if non_admin_jobs:
            non_admin_jobs_collection.delete_many({})
            non_admin_jobs_collection.insert_many(non_admin_jobs)

        return "✅ Jobs stored successfully."

    except PyMongoError as e:
        return f"❌ Database Error: {str(e)}"


def get_stored_jobs(job_type="all"):
    """Fetch jobs based on category."""
    try:
        if job_type == "admin":
            # return list(admin_jobs_collection.find({}, {"_id": 0}))
            return list(all_jobs_collection.find({}, {"_id": 0}))
        elif job_type == "non-admin":
            return list(non_admin_jobs_collection.find({}, {"_id": 0}))
        else:
            return list(all_jobs_collection.find({}, {"_id": 0}))
    except PyMongoError as e:
        return f"❌ Database Error: {str(e)}"





# ==============================
#        NOTIFICATION
# ==============================

from datetime import datetime

# Assuming notification_collection is your MongoDB collection object
def initialize_database():
    notification_collection.create_index([("username", 1)])
    notification_collection.create_index([("notifications.read", 1)])
    notification_collection.create_index([("notifications.job_name", 1)])
    notification_collection.create_index([("notifications.build_number", 1)])


def get_completed_inquired_notifications(username):
    user_doc = notification_collection.find_one({"username": username})
    if not user_doc:
        return []

    return [
        n for n in user_doc.get("notifications", [])
        if n["type"] == "inquired" and n["status"] == "COMPLETED"
    ]

def mark_notifications_as_read(username):
    notification_collection.update_one(
        {"username": username},
        {"$set": {
            "notifications.$[elem].notified": True
        }},
        array_filters=[{"elem.status": "COMPLETED", "elem.type": "inquired"}]
    )


# Add to database.py (new functions)
def add_notification(username, job_name, build_number, status, notification_type="inquired"):
    notification = {
        "job_name": job_name,
        "build_number": build_number,
        "status": status,
        "type": notification_type,
        "timestamp": datetime.utcnow(),
        "read": False
    }
    
    notification_collection.update_one(
        {"username": username},
        {"$push": {"notifications": notification}},
        upsert=True
    )

def get_unread_notifications(username):
    user_doc = notification_collection.find_one({"username": username})
    if not user_doc:
        return []
    
    return [
        n for n in user_doc.get("notifications", [])
        if not n.get("read", False)
    ]

def mark_notification_as_read(username, job_name, build_number):
    notification_collection.update_one(
        {"username": username, "notifications.job_name": job_name, "notifications.build_number": build_number},
        {"$set": {"notifications.$.read": True}}
    )



def add_triggered_job(username, job_name, build_number, subject=None):
    if subject is None:
        subject = f"You triggered build #{build_number} of {job_name}. It is running now."
    now = datetime.utcnow()

    existing = notification_collection.find_one({
        "username": username,
        "triggered_jobs.job_name": job_name,
        "triggered_jobs.build_number": build_number
    })

    if existing:
        notification_collection.update_one(
            {
                "username": username,
                "triggered_jobs.job_name": job_name,
                "triggered_jobs.build_number": build_number
            },
            {
                "$set": {
                    "triggered_jobs.$.status": "running",
                    "triggered_jobs.$.subject": subject,
                    "triggered_jobs.$.timestamp": now
                }
            }
        )
    else:
        notification_collection.update_one(
            {"username": username},
            {
                "$push": {
                    "triggered_jobs": {
                        "job_name": job_name,
                        "build_number": build_number,
                        "status": "running",
                        "subject": subject,
                        "timestamp": now
                    }
                }
            },
            upsert=True
        )


def add_inquired_job(username, job_name, build_number, subject=None):
    if subject is None:
        subject = f"Build #{build_number} of {job_name} is running. You'll be notified when done."
    now = datetime.utcnow()

    existing = notification_collection.find_one({
        "username": username,
        "inquired_jobs.job_name": job_name,
        "inquired_jobs.build_number": build_number
    })

    if existing:
        notification_collection.update_one(
            {
                "username": username,
                "inquired_jobs.job_name": job_name,
                "inquired_jobs.build_number": build_number
            },
            {
                "$set": {
                    "inquired_jobs.$.status": "running",
                    "inquired_jobs.$.subject": subject,
                    "inquired_jobs.$.timestamp": now
                }
            }
        )
    else:
        notification_collection.update_one(
            {"username": username},
            {
                "$push": {
                    "inquired_jobs": {
                        "job_name": job_name,
                        "build_number": build_number,
                        "status": "running",
                        "subject": subject,
                        "timestamp": now
                    }
                }
            },
            upsert=True
        )


def update_job_status_for_all_users(job_name, build_number, status, subject=None):
    now = datetime.utcnow()
    if subject is None:
        subject = f"Build #{build_number} of {job_name} {status}."

    # Update triggered_jobs
    notification_collection.update_many(
        {
            "triggered_jobs.job_name": job_name,
            "triggered_jobs.build_number": build_number
        },
        {
            "$set": {
                "triggered_jobs.$.status": status,
                "triggered_jobs.$.subject": subject,
                "triggered_jobs.$.timestamp": now
            }
        }
    )

    # Update inquired_jobs
    notification_collection.update_many(
        {
            "inquired_jobs.job_name": job_name,
            "inquired_jobs.build_number": build_number
        },
        {
            "$set": {
                "inquired_jobs.$.status": status,
                "inquired_jobs.$.subject": subject,
                "inquired_jobs.$.timestamp": now
            }
        }
    )

    # Fetch all distinct usernames that triggered or inquired this job
    triggered_users = notification_collection.distinct(
        "username",
        {
            "triggered_jobs.job_name": job_name,
            "triggered_jobs.build_number": build_number
        }
    )
    inquired_users = notification_collection.distinct(
        "username",
        {
            "inquired_jobs.job_name": job_name,
            "inquired_jobs.build_number": build_number
        }
    )

    all_users = set(triggered_users) | set(inquired_users)

    for username in all_users:
        notify_user(username, {"job_name": job_name, "build_number": build_number, "status": status, "subject": subject})


def notify_user(username, job_info):
    print(f"Notify {username}: {job_info['subject']}")


def remove_finished_jobs(username):
    notification_collection.update_one(
        {"username": username},
        {"$pull": {"triggered_jobs": {"status": {"$ne": "running"}}}}
    )
    notification_collection.update_one(
        {"username": username},
        {"$pull": {"inquired_jobs": {"status": {"$ne": "running"}}}}
    )

def update_notification(username, status=None, activity=None, subject=None):
    update_fields = {}
    if status is not None:
        update_fields["notification_status"] = status
    if activity is not None:
        update_fields["activity"] = activity
    if subject is not None:
        update_fields["subject"] = subject

    if update_fields:
        notification_collection.update_one(
            {"username": username},
            {"$set": update_fields},
            upsert=True
        )




def get_notification(username):
    return notification_collection.find_one({"username": username}, {"_id": 0, "triggered_jobs": 1, "inquired_jobs": 1})



# def update_notification(username, status=None, activity=None, subject=None):
#     update_fields = {}
#     if status:
#         update_fields["notification_status"] = status
#     if activity:
#         update_fields["activity"] = activity
#     if subject:
#         update_fields["subject"] = subject

#     if update_fields:
#         notification_collection.update_one(
#             {"username": username},
#             {"$set": update_fields},
#             upsert=True
#         )


# ==============================
#         UTILITIES
# ==============================

def clear_collections():
    """Clear all database collections (For testing purposes only)."""
    users_collection.delete_many({})
    admin_jobs_collection.delete_many({})
    non_admin_jobs_collection.delete_many({})
    all_jobs_collection.delete_many({})
    role_requests_collection.delete_many({})
    return "✅ All collections cleared successfully."

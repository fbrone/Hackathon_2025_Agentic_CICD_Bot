


# # import bcrypt
# # import sys
# # sys.path.append("..")

# # from Backend.auth.database import get_user

# # def authenticate(username, password):
# #     """Authenticate user and return role-based access."""
# #     user = get_user(username)
# #     print(user)  # Debugging purpose

# #     if not user:
# #         return {"status": "failed", "message": "User not found"}

# #     hashed_password = user["password"].encode("utf-8")  # Ensure it's in bytes
# #     input_password = password.encode("utf-8")  # Convert input password to bytes

# #     # Proper password verification using bcrypt
# #     if bcrypt.checkpw(input_password, hashed_password):
# #         return {"status": "success", "role": user["role"]}

# #     return {"status": "failed", "message": "Invalid credentials"}





# import bcrypt
# import sys
# sys.path.append("..")

# from Backend.auth.database import get_user

# def authenticate(username, password):
#     """Authenticate user and return role-based access."""
#     user = get_user(username)
#     if not user:
#         return {"status": "failed", "message": "User not found"}

#     hashed_password = user["password"].encode("utf-8")
#     input_password = password.encode("utf-8")

#     if bcrypt.checkpw(input_password, hashed_password):
#         return {"status": "success", "role": user["role"]}

#     return {"status": "failed", "message": "Invalid credentials"}

# def hash_password(password):
#     """Hash a password for secure storage."""
#     return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


import bcrypt
import sys
import logging
sys.path.append("..")

from Backend.auth.updated_database import get_user

# Logger setup for better error tracking
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def authenticate(username, password):
    """Authenticate user and return role-based access."""
    user = get_user(username)
    if not user:
        logging.warning(f"Authentication failed: User '{username}' not found.")
        return {"status": "failed", "message": "❌ User not found."}

    hashed_password = user["password"].encode("utf-8")
    input_password = password.encode("utf-8")

    if bcrypt.checkpw(input_password, hashed_password):
        logging.info(f"Authentication successful for user '{username}'.")
        return {"status": "success", "role": user["role"]}

    logging.warning(f"Authentication failed: Incorrect password for user '{username}'.")
    return {"status": "failed", "message": "❌ Invalid credentials."}

def hash_password(password):
    """Hash a password for secure storage."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(input_password, hashed_password):
    """Verify hashed password with user input."""
    return bcrypt.checkpw(input_password.encode('utf-8'), hashed_password.encode('utf-8'))

import os
from datetime import datetime
from pymongo import MongoClient

MONGO_URI = os.environ["MONGO_URI"]
DB_NAME = os.environ.get("DB_NAME", "telegram_bot")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

FILES = db.files
USERS = db.users

# =========================
# USER FUNCTIONS
# =========================

def add_user(user_id: int, username: str | None, name: str):
    USERS.update_one(
        {"_id": user_id},
        {
            "$setOnInsert": {
                "username": username,
                "name": name,
                "banned": False,
                "joined_at": datetime.utcnow()
            }
        },
        upsert=True
    )


def is_banned(user_id: int) -> bool:
    user = USERS.find_one({"_id": user_id}, {"banned": 1})
    return bool(user and user.get("banned"))


def ban_user(user_id: int):
    USERS.update_one({"_id": user_id}, {"$set": {"banned": True}})


def unban_user(user_id: int):
    USERS.update_one({"_id": user_id}, {"$set": {"banned": False}})


def get_all_active_users():
    return USERS.find({"banned": False}, {"_id": 1})


# =========================
# FILE FUNCTIONS
# =========================

def save_file(code: str, log_message_id: int):
    FILES.update_one(
        {"_id": code},
        {
            "$set": {
                "log_msg_id": log_message_id,
                "created_at": datetime.utcnow()
            }
        },
        upsert=True
    )


def get_file(code: str):
    return FILES.find_one({"_id": code})


def delete_file(code: str):
    FILES.delete_one({"_id": code})

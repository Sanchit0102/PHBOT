import motor.motor_asyncio
import datetime
import os

MONGO_URI = os.environ["MONGO_URI"]
DB_NAME = os.environ.get("DB_NAME", "ph_telegram_bot")
LOG_CHANNEL_ID = int(os.environ["LOG_CHANNEL_ID"])
LOG_TEXT = """<i><u>👁️‍🗨️USER DETAILS</u>

○ ID : <code>{id}</code>
○ DC : <code>{dc_id}</code>
○ First Name : <code>{first_name}</code>
○ UserName : @{username}</i>"""

class Database:

    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]

        self.users = self.db.users
        self.files = self.db.files

    # =====================================================
    # USER METHODS
    # =====================================================

    def new_user(self, user):
        return {
            "_id": user.id,
            "username": user.username,
            "name": user.first_name,
            "banned": False,
            "joined_at": datetime.datetime.utcnow()
        }

    async def add_user(self, user):
        await self.users.update_one(
            {"_id": user.id},
            {"$setOnInsert": self.new_user(user)},
            upsert=True
        )
        
    async def is_user_exist(self, user_id: int) -> bool:
        user = await self.users.find_one({"_id": int(user_id)})
        return True if user else False

    async def is_banned(self, user_id: int) -> bool:
        user = await self.users.find_one(
            {"_id": int(user_id)},
            {"banned": 1}
        )
        return bool(user and user.get("banned"))

    async def ban_user(self, user_id: int):
        await self.users.update_one(
            {"_id": int(user_id)},
            {"$set": {"banned": True}},
            upsert=True
        )

    async def unban_user(self, user_id: int):
        await self.users.update_one(
            {"_id": int(user_id)},
            {"$set": {"banned": False}}
        )

    async def total_users_count(self) -> int:
        return await self.users.count_documents({})

    async def get_all_users(self):
        return self.users.find({"banned": False}, {"_id": 1})

    async def delete_user(self, user_id: int):
        await self.users.delete_one({"_id": int(user_id)})

    # =====================================================
    # FILE METHODS
    # =====================================================

    async def save_file(self, code: str, log_message_id: int):
        await self.files.update_one(
            {"_id": code},
            {
                "$set": {
                    "log_msg_id": log_message_id,
                    "created_at": datetime.datetime.utcnow()
                }
            },
            upsert=True
        )

    async def get_file(self, code: str):
        return await self.files.find_one({"_id": code})

    async def delete_file(self, code: str):
        await self.files.delete_one({"_id": code})


# =====================================================
# DATABASE INSTANCE
# =====================================================

db = Database(MONGO_URI, DB_NAME)


# =====================================================
# AUTO USER LOGGER (OPTIONAL)
# =====================================================

async def adds_user(bot, msg):
    user_id = msg.from_user.id

    if await db.is_user_exist(user_id):
        return
        
    await db.add_user(msg.from_user)

    if LOG_CHANNEL_ID:
        await bot.send_message(
            LOG_CHANNEL_ID,
            text=LOG_TEXT.format(
                id=msg.from_user.id,
                dc_id=msg.from_user.dc_id,
                first_name=msg.from_user.first_name,
                username=msg.from_user.username,
            )
        )

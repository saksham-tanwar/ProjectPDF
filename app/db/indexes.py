from pymongo import ASCENDING, DESCENDING, TEXT
from pymongo.asynchronous.database import AsyncDatabase


async def ensure_indexes(db: AsyncDatabase) -> None:
    await db.users.create_index([("provider", ASCENDING), ("provider_id", ASCENDING)], unique=True)
    await db.sessions.create_index("expires_at", expireAfterSeconds=0)
    await db.sessions.create_index("user_id")
    await db.files.create_index([("owner_id", ASCENDING), ("created_at", DESCENDING)])
    await db.files.create_index([("status", ASCENDING), ("updated_at", ASCENDING)])
    await db.chunks.create_index([("file_id", ASCENDING), ("text", TEXT)], name="file_text", default_language="english")
    await db.chunks.create_index([("file_id", ASCENDING), ("page", ASCENDING), ("index", ASCENDING)])
    await db.chunks.create_index([("owner_id", ASCENDING)])

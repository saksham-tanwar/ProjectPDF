from pymongo import AsyncMongoClient

from app.config import settings

mongo_client: AsyncMongoClient = AsyncMongoClient(
    settings.mongo_url,
    serverSelectionTimeoutMS=5_000,
    connectTimeoutMS=5_000,
)

from pymongo import AsyncMongoClient, MongoClient

from app.config import Settings

CLIENT_OPTIONS = {"serverSelectionTimeoutMS": 5_000, "connectTimeoutMS": 5_000, "appname": "paperchat"}


def create_async_client(settings: Settings) -> AsyncMongoClient:
    return AsyncMongoClient(settings.mongo_url, tz_aware=True, **CLIENT_OPTIONS)


def create_sync_client(settings: Settings) -> MongoClient:
    return MongoClient(settings.mongo_url, tz_aware=True, **CLIENT_OPTIONS)

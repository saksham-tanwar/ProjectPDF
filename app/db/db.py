from app.config import settings
from .client import mongo_client

database = mongo_client[settings.mongo_database]

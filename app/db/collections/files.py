from ..db import database
from pymongo.asynchronous.collection import AsyncCollection

files_collection: AsyncCollection = database["files"]
chunks_collection: AsyncCollection = database["chunks"]

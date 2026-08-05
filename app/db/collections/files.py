from pydantic import Field
from typing import TypedDict, Optional
from ..db import database
from pymongo.asynchronous.collection import AsyncCollection


class FileSchema(TypedDict):
    name: str = Field(..., description="The name of the file")
    status: str = Field(..., description="The status of the file")
    result: Optional[str] = Field(None, description="The result from AI")


COLLECTION_NAME = "files"
files_collection: AsyncCollection = database[COLLECTION_NAME]

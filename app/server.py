from fastapi import FastAPI, UploadFile, Path
from app.utils.file import save_to_disk
from .db.collections.files import files_collection, FileSchema
from .queue.q import q
from .queue.workers import process_file
from bson import ObjectId

app = FastAPI()


@app.get("/")
def hello():
    return {"status": "healthy"}


@app.get("/{id}")
async def get_file_by_id(id: str = Path(..., description="The ID of file")):
    db_file = await files_collection.find_one({"_id": ObjectId(id)})

    return {
        "_id": str(db_file["_id"]),
        "name": db_file["name"],
        "status": db_file["status"]

    }


@app.post("/upload")
async def upload_file(
    file: UploadFile
):
    db_file = await files_collection.insert_one(
        document=FileSchema
        (name=file.filename,
         status="saving"
         )
    )

    file_path = f"/mnt/uploads/{str(db_file.inserted_id)}{file.filename}"

    await save_to_disk(file=await file.read(), path=file_path)

    await files_collection.update_one({"_id": db_file.inserted_id}, {
        "$set": {
            "status": "queued",
            "file_path": file_path,
        }
    })

    job = q.enqueue(process_file, str(db_file.inserted_id))
    print("File pushed")

    return {"file_id": str(db_file.inserted_id)}

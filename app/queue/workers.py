import os
from ..db.collections.files import files_collection
from bson import ObjectId
from pdf2image import convert_from_path
import base64
from openai import OpenAI

client = OpenAI()

# Function to encode the image


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


async def process_file(id: str):
    file_doc = await files_collection.find_one({"_id": ObjectId(id)})
    file_path = file_doc["file_path"]

    await files_collection.update_one({"_id": ObjectId(id)}, {
        "$set": {
            "status": "processing"
        }
    })

    await files_collection.update_one({"_id": ObjectId(id)}, {
        "$set": {
            "status": "converting to images"
        }
    })

    pages = convert_from_path(file_path)
    images = []

    image_dir = f"/mnt/uploads/images/{id}"
    os.makedirs(image_dir, exist_ok=True)

    for i, page in enumerate(pages):
        image_save_path = f"{image_dir}/image-{i}.jpg"
        page.save(image_save_path, 'JPEG')
        images.append(image_save_path)

    await files_collection.update_one({"_id": ObjectId(id)}, {
        "$set": {
            "status": "Converted to image successfully"
        }
    })

    images_base64 = [encode_image(img) for img in images]

    result = client.responses.create(
        model="gpt-4.1",
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "roast this mail"},
                    {
                        # flake8: noqa
                        "type": "input_image",
                        "image_url": f"data:image/jpeg;base64,{images_base64[0]}",
                    },
                ],
            }
        ],
    )

    await files_collection.update_one({"_id": ObjectId(id)}, {
        "$set": {
            "status": "proccesed",
            "result": result.output_text
        }})

    print(result.output_text)

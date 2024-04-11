import pymongo
from scrapy.utils.project import get_project_settings
from datetime import datetime, timedelta

from io import BytesIO
import requests
from PIL import Image

settings = get_project_settings()

mongo_uri=settings.get('MONGODB_URI')
mongo_db=settings.get('MONGODB_DATABASE')
collection_name=settings.get('MONGODB_COLLECTION')
client = pymongo.MongoClient(mongo_uri)
db = client[mongo_db]

def does_event_exist(_id):
    entry = db[collection_name].find_one({'_id': _id})
    if entry:
        time_diff = datetime.now() - entry.get('last_check')
        if time_diff > timedelta(days=3):
            return "EVENT_UPDATE"
        else:
            return "EVENT_EXISTS"
    else:
        return "EVENT_DOES_NOT_EXIST"

def download_image(url, _id):
    try:
        r = requests.get(url)
        r.raise_for_status()
        b = BytesIO(r.content).read()

        with BytesIO(r.content) as b:
            img = Image.open(b)
            
            target_aspect_ratio = 206/140
            original_width, original_height = img.size
            original_aspect_ratio = original_width / original_height
            if original_aspect_ratio <= target_aspect_ratio:
                target_height = int(original_width / target_aspect_ratio)
                height_diff = (original_height - target_height) // 2

                left = 0
                top = height_diff
                right = original_width
                bottom = original_height - height_diff
                coordinates = (left, top, right, bottom)
            else:
                target_width = int(original_height / (1/target_aspect_ratio))
                width_diff = (original_width - target_width ) // 2

                left = width_diff
                top = 0
                right = original_width - width_diff
                bottom = original_height
                coordinates = (left, top, right, bottom)
            new = img.crop(coordinates)
            new.save(str('./img/' + _id + '.webp'), format="WEBP")
    except requests.RequestException as e:
        print(f"Error making request to {url}: {e}")
    except Exception as e:
        print(f"Something went wrong with {url}, but status was 200: {e}")

    

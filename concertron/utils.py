import pymongo
from scrapy.utils.project import get_project_settings
from datetime import datetime, timedelta

from io import BytesIO
import requests

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

def download_image(url):
    try:
        r = requests.get(url)
        r.raise_for_status()
        b = BytesIO(r.content).read()
        return b
    except requests.RequestException as e:
        print(f"Error making request to {url}: {e}")
        return None
    except Exception as e:
        print(f"Something went wrong with {url}, but status was 200: {e}")

    

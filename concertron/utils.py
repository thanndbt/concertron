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

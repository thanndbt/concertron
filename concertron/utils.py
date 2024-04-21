import pymongo
from scrapy.utils.project import get_project_settings
from datetime import datetime, timedelta, timezone

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

def construct_datetime(lang, datefield, timefield=None): # This function exists for venues with no other date format than text like "Mo 01 jan 2024" and a separate time field.
    months = {
            'nl': {'jan': 1, 'feb': 2, 'mrt': 3, 'apr': 4, 'mei': 5, 'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9, 'okt': 10, 'nov': 11, 'dec': 12},
            'en': {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12},
            }
    date = datefield.strip().lower().split(' ')
    if timefield:
        time = timefield.split(':')
        return datetime(int(date[-1]), months.get(lang).get(date[-2]), int(date[-3]), int(time[0]), int(time[1])).astimezone(timezone.utc).replace(tzinfo=None)
    else:
        return datetime(int(date[-1]), months.get(lang).get(date[-2]), int(date[-3])).astimezone(timezone.utc).replace(tzinfo=None)


import pymongo
from datetime import datetime
import utils

client = pymongo.MongoClient('mongodb://concertron-mongodb:27017')
db = client['concertron_test']

async def create_user(_id, artists=[], tags=[], events=[], notify_all=False):
    db.discord_users.insert_one({
        "_id": _id,
        "created": datetime.now(),
        "artists": utils.str_to_list(artists), # Str to list only used as failsafe for mistakes made in later development
        "tags": utils.str_to_list(tags),
        "events": utils.str_to_list(events),
        "notify_all": notify_all
        })

async def find_user(_id):
    return db.discord_users.find_one({'_id': _id})

async def update_user(_id, events=[], artists=[], tags=[]):
    db.discord_users.update_one(
            {"_id": _id},
            {"$addToSet": {"events": events, "artists": {"$each": artists}, "tags": {"$each": tags}}}
            )

async def create_sendlist(discord, artists=None, tags=None, events=None): # Generates a list of discord user objects for a message to be sent to
    variables = {'artists': artists, 'tags': tags, 'events': events}
    matches = db.discord_users.find({'$or': [{var: {'$in': val}} for var, val in variables.items() if val and isinstance(val, list)]})
    return [discord.get_user(_id) for _id in matches.distinct('_id')]

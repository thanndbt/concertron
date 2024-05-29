import pymongo
from datetime import datetime
import utils

client = pymongo.MongoClient('mongodb://concertron-mongodb:27017')
db = client['concertron_test']

def db_init(): # Makes sure a last_check field is set upon starting up to prevent a clean setup blasting all events everywhere (that would be a lot)
    if not db.system.find_one({'_id': 'discord'}):
        db.system.insert_one({'_id': 'discord', 'last_check': datetime.now()})

def find_events(filter_q=None, sort_q=None): # Queries a default plus whatever the code calling it needs
    # Query defaults
    filter = {
            '$or': [
                {'event_type': 'Concert'},
                {'event_type': 'Festival'},
                {'event_type': 'Club'}
                ],
            'date': {'$gt': datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)},
            }
    sort = {'date': 1}

    if filter_q:
        filter.update(filter_q)
    if sort_q:
        sort.update(sort_q)

    return db.events.find(filter=filter, sort=sort)

def fetch_updates():
    filter = {'last_modified': {'$gt': db.system.find_one({'_id': 'discord'}).get('last_check')}} # Only get documents updated after the last check
    return find_events(filter_q=filter)

def write_success():
    db.system.update_one({'_id': 'discord'}, {'$set': {'last_check': datetime.now()}}) # Just as a flag

async def search_artist(message): # Search for artist in lineup fields in documents. TO-DO: no text appended should send a warning message. Rn it just sends ALL acts and needs to be killed inb4 rate limit
    content = message.content.split('$artist')[1].strip()
    if content:
        results = find_events({'lineup': {'$regex': content, '$options': 'i'}})
        if len(list(results.clone())) > 0:
            for match in results:
                sent = await message.channel.send(**utils.show_embed(match))
                await sent.add_reaction("❤️")
        else:
            await message.channel.send(f"No events found containing *{content}*")
    else:
        await message.channel.send(f"{message.author.mention} Please specify an artist like so: *$artist Red Hot Chili Peppers*")


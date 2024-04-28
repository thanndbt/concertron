import discord
from discord.ext import tasks, commands
import pymongo
from datetime import datetime
import utils
import logging

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
logger = logging.FileHandler(filename='./logs/discord.log', encoding='utf-8', mode='w')
emojis = ["🩷", "🧡", "💛", "💚", "💙", "🩵", "💜", "🤎", "🩶", "🤍", "💘", "💝", "💖", "💗", "💓", "💞", "💕", "💟"]

def db_events_find(filter_q=None, sort_q=None):
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

def show_embed(item): # Item is a MongoDB document/dict
    file = discord.File(f"./img/{item['_id']}.webp", "image.webp")
    embed = discord.Embed(
            title = item['title'],
            description = item['subtitle'],
            url = item['url'],
            timestamp = item['date']
            )
    embed.add_field(name='Location', value=item['location'])
    if item['support']:
        embed.add_field(name='Support', value='\n'.join(item['support']))
    embed.add_field(name='Status', value=' '.join(item['status'].split('_')).capitalize())
    embed.set_image(url="attachment://image.webp")
    return {'file': file, 'embed': embed}

async def search_artist(message):
    results = db_events_find({'lineup': {'$regex': message.content.split('$artist')[1].strip(), '$options': 'i'}})
    for match in results:
        sent = await message.channel.send(**show_embed(match))
        await sent.add_reaction("❤️")

def str_to_list(string):
    if isinstance(string, str):
        return string.split(", ")
    elif isinstance(string, list):
        return string
    else:
        raise Exception("Type is neither str nor list!")

async def create_user(_id, artists=[], tags=[], events=[], notify_all=False):
    db.discord_users.insert_one({
        "_id": _id,
        "created": datetime.now(),
        "artists": str_to_list(artists),
        "tags": str_to_list(tags),
        "events": str_to_list(events),
        "notify_all": notify_all
        })

async def find_user(_id):
    return db.discord_users.find_one({'_id': _id})

async def create_sendlist(artists=None, tags=None, events=None):
    variables = {'artists': artists, 'tags': tags, 'events': events}
    matches = db.discord_users.find({'$or': [{var: {'$in': val}} for var, val in variables.items() if val and isinstance(val, list)]})
    return [client.get_user(_id) for _id in matches.distinct('_id')]

client = discord.Client(intents=intents)
db = pymongo.MongoClient('localhost:27017').concertron_test
agenda = db_events_find()

if not db.system.find_one({'_id': 'discord'}):
    db.system.insert_one({'_id': 'discord', 'last_check': datetime.now()})

@tasks.loop(minutes=5)
async def send_updates():
    filter = {'last_modified': {'$gt': db.system.find_one({'_id': 'discord'}).get('last_check')}}
    updated = db_events_find(filter)
    for item in updated:
        embed = show_embed(item).get('embed')
        if item['updates'] == 'new':
            embed.set_author(name="New event")
            for user in await create_sendlist(artists=item['lineup'], tags=item['tags']):
                private = await user.send(file=discord.File(f"./img/{item['_id']}.webp", "image.webp"), embed=embed.copy())
                await private.add_reaction("❤️")
        elif isinstance(item['updates'], list) and len(item['updates']) > 0:
            head_text = "Update: " + ', '.join(item['updates'])
            embed.set_author(name=head_text)
            for user in await create_sendlist(artists=item['lineup'], events=[item['_id']]):
                private = await user.send(file=discord.File(f"./img/{item['_id']}.webp", "image.webp"), embed=embed.copy())
                await private.add_reaction("❤️")
        message = await home_channel.send(file=discord.File(f"./img/{item['_id']}.webp", "image.webp"), embed=embed.copy())
        await message.add_reaction("❤️")
        # for i, artist in enumerate(item['lineup'], 0):
            # await message.add_reaction(emojis[i])
    db.system.update_one({'_id': 'discord'}, {'$set': {'last_check': datetime.now()}})

@client.event
async def on_ready():
    global home_channel
    home_channel = client.get_channel(utils.home)
    message = "Hello everyone! I'm here."
    await home_channel.send(message)
    send_updates.start()

@client.event
async def on_reaction_add(reaction, user):
    if user == client.user:
        return

    if reaction.message.author == client.user:
        if str(reaction.emoji) == "❤️":
            event_url = reaction.message.embeds[0].url
            event = db.events.find_one({'url': event_url})
            event_id = event['_id']
            user_profile = await find_user(user.id)
            if user_profile:
                db.discord_users.update_one(
                        {"_id": user.id},
                        {"$addToSet": {"events": event_id, "artists": {"$each": event['lineup']}, "tags": {"$each": event['tags']}}}
                        )
            else:
                await create_user(user.id, events=[event_id], artists=event['lineup'], tags=event['tags'])
            await user.send(f"{event['title']} has been added to your watchlist")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('$hello'):
        await message.channel.send(embed=discord.Embed(title="Hello", description="This is a test"))

    if message.content.startswith('$next'):
        item = agenda.next()
        await message.channel.send(**show_embed(item))

    if message.content.startswith('$artist'):
        await search_artist(message)

    if message.content.startswith('$update'):
        await send_updates()

    if message.content.startswith('$watchlist'):
        user_profile = db.discord_users.find_one({'_id': message.author.id})
        if user_profile:
            embed = discord.Embed(
                    title = "Watchlist",
                    description = """
                    NOTE: tags are as they are found in the venues. Concertron parses these separately for good recommendations and watching. Some 'artists' may be event titles due to the dev still learning and being a dumb fuck.

                    When you follow an event, all acts on the line-up and its genre tags are added to your profile, as well as the event itself being on your watchlist.
                    """
                    )
            embed.add_field(name="Artists", value='\n'.join(user_profile['artists']))
            embed.add_field(name="Tags (i.e. genres)", value='\n'.join(user_profile['tags']))
            embed.add_field(name="Events", value='\n'.join(user_profile['events']))
            await message.author.send(embed=embed)
        else:
            await message.author.send("You do not have a watchlist yet. Heart an event to follow it and add the artists.")

if __name__ == '__main__':
    client.run(utils.key, log_handler=logger, log_level=logging.DEBUG)


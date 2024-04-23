import discord
import pymongo
from datetime import datetime
import keys

intents = discord.Intents.default()
intents.message_content = True

def db_events_find(filter_q=None, sort_q=None):
    # Query defaults
    filter = {
            '$or': [
                {'event_type': 'Concert'},
                {'event_type': 'Festival'},
                {'event_type': 'Club'}
                ]}
    sort = {'date': 1}

    if filter_q:
        filter.update(filter_q)
    if sort_q:
        sort.update(sort_q)

    return db.events.find(filter=filter, sort=sort)

def show_embed(item):
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
    embed.set_author(name=item['venue_id'].split('_')[-1].capitalize())
    embed.set_image(url="attachment://image.webp")
    return file, embed

async def search_artist(message):
    results = db_events_find({'lineup': {'$regex': message.content.split('$artist')[1].strip(), '$options': 'i'}})
    for match in results:
        embed = show_embed(match)
        await message.channel.send(file=embed[0], embed=embed[1])

async def send_updates(message):
    filter = {'last_modified': {'$gt': db.system.find_one({'_id': 'discord'}).get('last_check')}}
    updated = db_events_find(filter)
    for item in updated:
        file, embed = show_embed(item)
        await message.channel.send(file=file, embed=embed)
    db.system.update_one({'_id': 'discord'}, {'$set': {'last_check': datetime.now()}})

client = discord.Client(intents=intents)
db = pymongo.MongoClient('localhost:27017').concertron_test
agenda = db_events_find()

if not db.system.find_one({'_id': 'discord'}):
    db.system.insert_one({'_id': 'discord', 'last_check': datetime.now()})

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('$hello'):
        await message.channel.send(embed=discord.Embed(title="Hello", description="This is a test"))

    if message.content.startswith('$next'):
        item = agenda.next()
        embed = show_embed(item)
        await message.channel.send(file=embed[0], embed=embed[1])

    if message.content.startswith('$artist'):
        await search_artist(message)

    if message.content.startswith('$update'):
        await send_updates(message)


if __name__ == '__main__':
    client.run(keys.api)


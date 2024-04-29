import discord
from discord.ext import tasks, commands
import logging

# local modules
import utils
import keys
import events
import users

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
logger = logging.FileHandler(filename='./logs/discord.log', encoding='utf-8', mode='w')

# These are for adding artists on lineups, still has to be worked out, maybe move over to utils
emojis = ["🩷", "🧡", "💛", "💚", "💙", "🩵", "💜", "🤎", "🩶", "🤍", "💘", "💝", "💖", "💗", "💓", "💞", "💕", "💟"]

client = discord.Client(intents=intents)
agenda = events.find_events() # Only for '$next', remove soon (not a very useful feature, but good for debugging in current stage)

@tasks.loop(minutes=5) # Fetch and process updates in db every 5 minutes
async def send_updates():
    for item in events.fetch_updates():
        embed = utils.show_embed(item).get('embed') # Since the file needs to get loaded anyway for every send, dont take it.

        if item['updates'] == 'new': # If event was newly added to the db
            embed.set_author(name="New event")
            for user in await users.create_sendlist(client, artists=item['lineup'], tags=item['tags']):
                private = await user.send(file=discord.File(f"./img/{item['_id']}.webp", "image.webp"), embed=embed.copy())
                await private.add_reaction("❤️") # Heart for event (and - for now - artist following

        elif isinstance(item['updates'], list) and len(item['updates']) > 0: # If event has been updated, don't broadcast if there are no changes despite last_modified
            head_text = "Update: " + ', '.join(item['updates'])
            embed.set_author(name=head_text)

            for user in await users.create_sendlist(client, artists=item['lineup'], events=[item['_id']]):
                private = await user.send(file=discord.File(f"./img/{item['_id']}.webp", "image.webp"), embed=embed.copy())
                await private.add_reaction("❤️")

        message = await home_channel.send(file=discord.File(f"./img/{item['_id']}.webp", "image.webp"), embed=embed.copy())
        await message.add_reaction("❤️")
        # for i, artist in enumerate(item['lineup'], 0):
            # await message.add_reaction(emojis[i])
        events.write_success()

@client.event
async def on_ready():
    global home_channel
    home_channel = client.get_channel(keys.home)
    message = "Hello everyone! I'm here."
    await home_channel.send(message)
    send_updates.start()

@client.event
async def on_reaction_add(reaction, user):
    if user == client.user:
        return

    if reaction.message.author == client.user: # Check if message reacted to is from bot
        if str(reaction.emoji) == "❤️": # If :heart:/:red_heart:, add event, artists and tags to user profile
            event_url = reaction.message.embeds[0].url
            event = events.find_events(filter_q={'url': event_url}).next()
            user_profile = await users.find_user(user.id)

            if user_profile: #If profile exists, add it
                await users.update_user(user.id, event['_id'], event['lineup'], event['tags'])
            else: # If not, create profile and add information to it
                await create_user(user.id, [event['_id']], event['lineup'], event['tags'])

            await user.send(f"{event['title']} has been added to your watchlist")

@client.event
# This should probably get a differnet implementation. TODO: learn about commands in discord.py
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('$hello'):
        await message.channel.send(embed=discord.Embed(title="Hello", description="This is a test"))

    if message.content.startswith('$next'): # Leave for debugging
        item = agenda.next()
        await message.channel.send(**utils.show_embed(item))

    if message.content.startswith('$artist'): # Search for artist in lineup fields in documents. TO-DO: no text appended should send a warning message. Rn it just sends ALL acts and needs to be killed inb4 rate limit
        await events.search_artist(message)

    if message.content.startswith('$update'): # Manually run the update cycle. TO-DO: Limit this to certain users/channels/roles
        await send_updates()

    if message.content.startswith('$watchlist'): # DM a user's profile to that user.
        user_profile = await users.find_user(message.author.id)
        if user_profile:
            embed = discord.Embed(
                    title = "Watchlist",
                    description = """
                    NOTE: tags are as they are found in the venues. Concertron parses these separately for good recommendations and watching. Some 'artists' may be event titles.

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
    events.db_init() # Makes sure a last_check field is set upon starting up to prevent a clean setup blasting all events everywhere (that would be a lot)
    client.run(keys.key, log_handler=logger, log_level=logging.DEBUG)

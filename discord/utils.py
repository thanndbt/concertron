from discord import File, Embed

def str_to_list(string):
    if isinstance(string, str):
        return string.split(", ")
    elif isinstance(string, list):
        return string
    else:
        raise Exception("Type is neither str nor list!")

def show_embed(item): # Generate an embed for a show. Item is a MongoDB document/dict
    file = File(f"./img/{item['_id']}.webp", "image.webp") # Made for convenience's sake, but not required. Use utils.show_embed(item)['embed'] and add discord.File separately
    embed = Embed(
            title = item['title'],
            description = item['subtitle'],
            url = item['url'],
            timestamp = item['date']
            )
    embed.add_field(name='Location', value=item['location'])
    if item['support']: # Maybe replace with item['lineup'] for consistency?
        embed.add_field(name='Support', value='\n'.join(item['support']))
    embed.add_field(name='Status', value=' '.join(item['status'].split('_')).capitalize())
    embed.set_image(url="attachment://image.webp")
    return {'file': file, 'embed': embed}

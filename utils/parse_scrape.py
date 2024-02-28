import aiohttp
from logs.manager import LogManager

async def fetch_page(session, url): # Basic function to fetch websites
    logger = LogManager(__name__)
    try:
        async with session.get(url) as response:
            if response.status == 200: # Make sure only succesful requests get through
                return await response.text()
            else:
                raise aiohttp.ClientResponseError(status=response.status) # Raise error if code other than 200 is returned
    except Exception as e:
        logger.error(f'Fetching page failed: {e}')

def determine_separator(data): # This determines what separator to use. Built around the varying way Melkweg lists lineups and support acts.
    separator_slash_count = data.count(' / ')
    separator_dash_count = data.count(' - ')

    if separator_slash_count > separator_dash_count:
        return ' / '
    elif separator_dash_count > separator_slash_count:
        return ' - '
    else:
        return ' / ' # Function defaults to ' / ' as this is more prevalent for Melkweg

def fetch_script_tag(soup, pos): # for catching the script tag that contains the json for 013
    try:
        return soup.find_all('script')[pos]
    except IndexError:
        logger.error('The script tag does not exist')
    except:
        logger.exception('Something went wrong while finding the 013 script tag')



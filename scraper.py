import asyncio
import aiohttp
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
from urllib.parse import urljoin

def determine_separator(data): # This determines what separator to use. Built around the varying way Melkweg lists lineups and support acts.
    separator_slash_count = data.count(' / ')
    separator_dash_count = data.count(' - ')

    if separator_slash_count > separator_dash_count:
        return ' / '
    elif separator_dash_count > separator_slash_count:
        return ' - '
    else:
        return ' / ' # Function defaults to ' / ' as this is more prevalent for Melkweg

async def fetch_page(session, url): # Basic function to fetch websites
    async with session.get(url) as response:
        if response.status == 200: # Make sure only succesful requests get through
            return await response.text()
        else:
            raise aiohttp.ClientResponseError(status=response.status) # Raise error if code other than 200 is returned

async def parse_event_melkweg(show, session, url):
    try:
        tag_sep = '·' # Separator for genre tags
        event_type = show.find(class_='styles_event-compact__type-item__RPgGU') # Find event type
        if event_type and (event_type.span.get_text(strip=True).lower() in ['concert', 'club', 'festival']): # Filter event types (excluding expositions and cinema)
            event_response = await fetch_page(session, url) 
            event_soup = BeautifulSoup(event_response, 'html.parser')
            if show.find(class_='styles_event-compact__subtitle__yGojc'): # Find subtitle on agenda page, return empty if none
                subtitle = show.find(class_='styles_event-compact__subtitle__yGojc').get_text(strip=True)
            else:
                subtitle = ''

            event_subs = event_soup.find_all(class_='styles_event-header__subtitle__LBG7q') # Find all subtitles on event page
            if (len(event_subs) == 1 and event_subs[0].get_text(strip=True) != subtitle) or (len(event_subs) == 2): # Only trigger if the only line is not existing subtitle or if there are multiple lines (in which case it will take the latter of the two)
                support_line = event_subs[-1].get_text(strip=True)
                if len(support_line.split(': ')) == 2:
                    acts = support_line.split(': ')[-1]
                    support = acts.split(determine_separator(acts))
                else: support = ''
            else: support = ''

            # Combine all data in dictionary
            data = {
                    'id': url.split('/')[-2],
                    'artist': show.h3.get_text(strip=True),
                    'subtitle': subtitle,
                    'support': support,
                    'date': datetime.fromisoformat(event_soup.time.get('datetime').replace('Z', '+00:00')),
                    'location': str(event_soup.find(class_='styles_event-header__location__jvvG4').get_text(strip=False) + ', Melkweg, Amsterdam, NL'),
                    'tags': show.find(class_='styles_tags-list__DAdH2').get_text(strip=True).split(tag_sep) if show.find(class_='styles_tags-list__DAdH2') else '',
                    'url': url,
                    }

            return data
        else:
            print('Event is not the correct type: ' + url)
            return None
    except Exception as e:
        print(f"Error parsing event page {url}: {e}")
        return None

async def scrape_melkweg():
    base_url = 'https://melkweg.nl/en/agenda/'

    async with aiohttp.ClientSession() as session:
        try:
            # Load agenda page
            agenda_html = await fetch_page(session, base_url)
            soup = BeautifulSoup(agenda_html, 'html.parser')
            agenda = soup.find_all(class_="styles_event-list-day__list-item__o6KTp") # Makes a list of all event entries in the agenda

            tasks = [] # Prepare for async goodness
            for show in agenda:
                relative_url = show.a.get('href') # Whatever comes behind the domain name
                full_url = urljoin(base_url, relative_url) # Duh
                tasks.append(parse_event_melkweg(show, session, full_url)) # Adds tasks for rapid scraping async goodness

            parsed_results = await asyncio.gather(*tasks)
            return [result for result in parsed_results if result is not None] # Filter out the empties to sanitise data
        except aiohttp.ClientError as ce:
            print(f"HTTP request error: {ce}")
            return []
        except Exception as e:
            print(f"An error occurred: {e}")
            return []

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    df = pd.DataFrame(loop.run_until_complete(scrape_melkweg()))
    print(df)
    df.to_csv('test.csv')

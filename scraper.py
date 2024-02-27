import asyncio
import aiohttp
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from urllib.parse import urljoin
import json
import logging
import html
import sqlite3
import traceback

import constants

logging.basicConfig(filename='test.log', encoding='utf-8', level=logging.DEBUG)

def determine_separator(data): # This determines what separator to use. Built around the varying way Melkweg lists lineups and support acts.
    separator_slash_count = data.count(' / ')
    separator_dash_count = data.count(' - ')

    if separator_slash_count > separator_dash_count:
        return ' / '
    elif separator_dash_count > separator_slash_count:
        return ' - '
    else:
        return ' / ' # Function defaults to ' / ' as this is more prevalent for Melkweg

async def retrieve_event(event_id, db_conn):
    try:
        cursor = db_conn.cursor()
        cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
        row = cursor.fetchone()
        if row:
            columns = [description[0] for description in cursor.description]
            return dict(zip(columns, row))
        else:
            return None
    except Exception as e:
        logging.warning(f"Error retrieving event from db: {e}")
        print(f"Error retrieving event from db: {e}")

async def check_last_modification(event_id, db_conn):
    try:
        event = await retrieve_event(event_id, db_conn)
        if event:
            time_diff = datetime.now() - datetime.fromisoformat(event.get('last_check'))
            if time_diff > timedelta(days=3):
                return "EVENT_UPDATE"
            else:
                return "EVENT_EXISTS"
        else:
            return "EVENT_DOES_NOT_EXIST"

    except Exception as e:
        logging.warning(f"Error checking last mod time: {e}")
        print(f"Error checking last mod time: {e}")
        traceback.print_exc(limit=1)

async def insert_event_data(data, db_conn):
    try:
        cursor = db_conn.cursor()
        cursor.execute("Insert INTO events (id, artist, subtitle, support, date, location, tags, ticket_status, url, venue_id, last_check, last_modified) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (data['id'], data['artist'], data['subtitle'], data['support'], data['date'], data['location'], data['tags'], data['ticket_status'], data['url'], data['venue_id'], data['last_check'], data['last_modified']))
        db_conn.commit()
    except Exception as e:
        logging.warning(f"Error inserting event into database: {e}")
        print(f"Error inserting event into database: {e}")

async def update_event_data(event_id, data, db_conn):
    try:
        stored_event = await retrieve_event(event_id, db_conn)
        print(type(stored_event))
        print(type(data))
        if stored_event:
            cursor = db_conn.cursor()
            changes = {key: value for key, value in data.items() if stored_event[key] != value}

            if changes:
                # Construct the UPDATE query
                changes['last_check'] = datetime.now()
                changes['last_modified'] = datetime.now()
                set_clause = ', '.join(f"{key} = ?" for key in changes.keys())
                query = f"UPDATE events SET {set_clause} WHERE id = ?"
                values = tuple(changes.values()) + (event_id,)

                # Execute the UPDATE query
                cursor.execute(query, values)
                db_conn.commit()
            else:
                cursor.execute("UPDATE events SET last_check=? WHERE id=?", (datetime.now(), event_id))
    except Exception as e:
        logging.warning(f'Failed to update event entry in db: {e}')
        print(f'Failed to update event entry in db: {e}')

def fetch_script_tag(soup, pos): # for catching the script tag that contains the json for 013
    try:
        return soup.find_all('script')[pos]
    except IndexError:
        print('The script tag does not exist')
    except:
        print('Something went wrong while finding the 013 script tag')

async def fetch_page(session, url): # Basic function to fetch websites
    async with session.get(url) as response:
        if response.status == 200: # Make sure only succesful requests get through
            return await response.text()
        else:
            raise aiohttp.ClientResponseError(status=response.status) # Raise error if code other than 200 is returned

async def parse_event_013(show, session, url, db_conn):
    try:
        relative_url = show.get('url')
        full_url = urljoin(url, relative_url)

        async def data_fetcher(show, session, url):
            event_response = await fetch_page(session, url)
            event_soup = BeautifulSoup(event_response, 'html.parser')
            script_tag = fetch_script_tag(event_soup, -1)
            event_data = json.loads(script_tag.string)
            return event_data

        def check_ticket_status(show):
            try:
                flags = show.get('flags')
                if flags.get('soldOut'):
                    return 'SOLD_OUT'
                elif flags.get('fewTicketsAvailable'):
                    return 'FEW_TICKETS'
                elif flags.get('saleStarted'):
                    return 'SALE_LIVE'
                elif not flags.get('saleStarted'):
                    return 'SALE_NOT_LIVE'
                elif flags.get('cancelled'):
                    return 'CANCELLED'
                else:
                    return 'UNKNOWN'
            except Exception as e:
                logging.warning(f'Ticket status could not be checked for {full_url}: {e}')
                print(f'Ticket status could not be checked for {full_url}: {e}')
                return 'UNKNOWN'

        event_id = '-'.join(show.get('url').split('/')[2:])
        event_status = await check_last_modification(event_id, db_conn)
        if event_status == 'EVENT_UPDATE':
            event_data = await data_fetcher(show, session, full_url)

            tags = []
            for tag in show.get('genres'): # 013's genre tags are nested
                tags.append(tag.get('title'))

            data = {
                    # 013 has loads of flags
                    'artist': html.unescape(str(show.get('title'))),
                    'subtitle': html.unescape(str(show.get('subTitle') if show.get('subTitle') else show.get('mobileEventDescription'))),
                    'support': json.dumps(show.get('supportActs')),
                    'date': datetime.fromisoformat(show.get('dates').get('startsAt')),
                    'location': str(event_data.get('location').get('name') + ', Tilburg, NL'), # 013's in house events contain a full location name in the JSON, so mentioning the venue is pointless
                    'tags': json.dumps(tags),
                    'ticket_status': check_ticket_status(show),
                    }
            await update_event_data(event_id, data, db_conn)

        elif event_status == 'EVENT_EXISTS':
            logging.info('Event exists but does not require updating')

        elif event_status == 'EVENT_DOES_NOT_EXIST':
            try:
                event_data = await data_fetcher(show, session, full_url)
                tags = []
                for tag in show.get('genres'): # 013's genre tags are nested
                    tags.append(tag.get('title'))

                data = {
                        # 013 has loads of flags
                        'id': event_id,
                        'artist': html.unescape(str(show.get('title'))),
                        'subtitle': html.unescape(str(show.get('subTitle') if show.get('subTitle') else show.get('mobileEventDescription'))),
                        'support': json.dumps(show.get('supportActs')),
                        'date': datetime.fromisoformat(show.get('dates').get('startsAt')),
                        'location': str(event_data.get('location').get('name') + ', Tilburg, NL'), # 013's in house events contain a full location name in the JSON, so mentioning the venue is pointless
                        'tags': json.dumps(tags),
                        'ticket_status': check_ticket_status(show),
                        'url': full_url,
                        'venue_id': '013_nl',
                        'last_check': datetime.now(),
                        'last_modified': datetime.now()
                        }

                await insert_event_data(data, db_conn)
            except Exception as e:
                print(f'013 - EVENT_DOES_NOT_EXIST: {e}')
                traceback.print_exc(limit=1)

    except Exception as e:
        print(f"Error parsing event page {url}: {e}")

async def parse_event_melkweg(show, session, url, db_conn):
    try:
        def check_ticket_status(show):
            try:
                event_label = show.find(class_='styles_label__p9pQy')
                if event_label and event_label.get_text(strip=True).lower() == 'sold out':
                    return 'SOLD_OUT'
                # elif flags.get('fewTicketsAvailable'): # Does not seem to exist for Melkweg
                    # return 'FEW_TICKETS'
                # elif flags.get('saleStarted'): # Does not seem to exist. Currently, if it is online, it is for sale. Keep an eye on this.
                    # return 'SALE_LIVE'
                # elif not flags.get('saleStarted'):
                    # return 'SALE_NOT_LIVE'
                elif event_label and event_label.get_text(strip=True).lower() == 'cancelled':
                    return 'CANCELLED'
                else:
                    return 'SALE_LIVE' # This is true, for now.
            except Exception as e:
                logging.warning(f'Ticket status could not be checked for {url}: {e}')
                print(f'Ticket status could not be checked for {url}: {e}')
                return 'UNKNOWN'

        async def data_fetcher(session, url):
            response = await fetch_page(session, url) 
            soup = BeautifulSoup(response, 'html.parser')
            return soup

        def fetch_subtitle(show):
            if show.find(class_='styles_event-compact__subtitle__yGojc'): # Find subtitle on agenda page, return empty if none
                subtitle = show.find(class_='styles_event-compact__subtitle__yGojc').get_text(strip=True)
            else:
                subtitle = ''
            return subtitle

        def fetch_support(event_soup):
            event_subs = event_soup.find_all(class_='styles_event-header__subtitle__LBG7q') # Find all subtitles on event page
            if (len(event_subs) == 1 and event_subs[0].get_text(strip=True) != subtitle) or (len(event_subs) == 2): # Only trigger if the only line is not existing subtitle or if there are multiple lines (in which case it will take the latter of the two)
                support_line = event_subs[-1].get_text(strip=True)
                if len(support_line.split(': ')) == 2:
                    acts = support_line.split(': ')[-1]
                    support = acts.split(determine_separator(acts))
                else: support = []
            else: support = []
            return support
        
        tag_sep = '·' # Separator for genre tags
        event_type = show.find(class_='styles_event-compact__type-item__RPgGU') # Find event type
        if event_type and (event_type.span.get_text(strip=True).lower() in ['concert', 'club', 'festival']): # Filter event types (excluding expositions and cinema)
            event_id = url.split('/')[-2]
            event_status = await check_last_modification(event_id, db_conn)

            if event_status == 'EVENT_UPDATE':
                event_soup = await data_fetcher(session, url)
                subtitle = fetch_subtitle(show)
                support = fetch_support(event_soup)

                # Combine all data in dictionary
                data = {
                        'artist': str(show.h3.get_text(strip=True)),
                        'subtitle': str(subtitle),
                        'support': json.dumps(support),
                        'date': datetime.fromisoformat(event_soup.time.get('datetime').replace('Z', '+00:00')),
                        'location': str(event_soup.find(class_='styles_event-header__location__jvvG4').get_text(strip=False) + ', Melkweg, Amsterdam, NL'),
                        'tags': json.dumps(show.find(class_='styles_tags-list__DAdH2').get_text(strip=True).split(tag_sep) if show.find(class_='styles_tags-list__DAdH2') else []),
                        'ticket_status': check_ticket_status(show),
                        }

                await update_event_data(event_id, data, db_conn)

            elif event_status == 'EVENT_EXISTS':
                logging.info('Event exists but does not require updating')

            elif event_status == 'EVENT_DOES_NOT_EXIST':
                event_soup = await data_fetcher(session, url)
                subtitle = fetch_subtitle(show)
                support = fetch_support(event_soup)

                # Combine all data in dictionary
                data = {
                        'id': event_id,
                        'artist': str(show.h3.get_text(strip=True)),
                        'subtitle': str(subtitle),
                        'support': json.dumps(support),
                        'date': datetime.fromisoformat(event_soup.time.get('datetime').replace('Z', '+00:00')),
                        'location': str(event_soup.find(class_='styles_event-header__location__jvvG4').get_text(strip=False) + ', Melkweg, Amsterdam, NL'),
                        'tags': json.dumps(show.find(class_='styles_tags-list__DAdH2').get_text(strip=True).split(tag_sep) if show.find(class_='styles_tags-list__DAdH2') else []),
                        'ticket_status': check_ticket_status(show),
                        'url': url,
                        'venue_id': 'melkweg_nl',
                        'last_check': datetime.now(),
                        'last_modified': datetime.now(),
                        }

                await insert_event_data(data, db_conn)

        else:
            print('Event is not the correct type: ' + url)
            return None
    except Exception as e:
        print(f"Error parsing event page {url}: {e}")
        return None

async def scrape_013(db_conn):
    base_url = 'https://www.013.nl/programma'
    async with aiohttp.ClientSession() as session:
        try:
            agenda_html = await fetch_page(session, base_url)
            soup = BeautifulSoup(agenda_html, 'html.parser')

            # 013 uses json to store all information on events and generates its pages that way. It is actually very effective.
            # This fetches and pre-processes the json
            script_tag = fetch_script_tag(soup, -3)
            script_content = script_tag.string
            start_index = script_content.find('{"')
            end_index = script_content.find('}]},')+3
            json_content = script_content[start_index:end_index]

            agenda = json.loads(json_content)['events'] # From here everything is accessible as a list of dictionary. Every event is a dict.

            tasks = []
            for show in agenda:
                tasks.append(parse_event_013(show, session, base_url, db_conn))

            await asyncio.gather(*tasks)

        except aiohttp.ClientError as ce:
            print(f"HTTP request error: {ce}")
            return []
        except Exception as e:
            print(f"An error occurred: {e}")
            return []       

async def scrape_melkweg(db_conn):
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
                tasks.append(parse_event_melkweg(show, session, full_url, db_conn)) # Adds tasks for rapid scraping async goodness

            parsed_results = await asyncio.gather(*tasks)
            return [result for result in parsed_results if result is not None] # Filter out the empties to sanitise data
        except aiohttp.ClientError as ce:
            print(f"HTTP request error: {ce}")
            return []
        except Exception as e:
            print(f"An error occurred: {e}")
            return []

if __name__ == '__main__':
    logging.info('Running test mode')

    db_name = 'concertron_test_1.db'
    conn = sqlite3.connect(db_name)

    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS events (
        id TEXT PRIMARY KEY,
        artist TEXT NOT NULL,
        subtitle TEXT NOT NULL,
        support TEXT NOT NULL,
        date TIMESTAMP,
        location TEXT NOT NULL,
        tags TEXT NOT NULL,
        ticket_status TEXT NOT NULL,
        url TEXT NOT NULL,
        venue_id TEXT NOT NULL,
        last_check TIMESTAMP,
        last_modified TIMESTAMP
        )''')
    conn.commit()

    asyncio.run(scrape_melkweg(conn))
    asyncio.run(scrape_013(conn))

    conn.close()

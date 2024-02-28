import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json
import html
from datetime import datetime, timedelta

from logs.manager import LogManager
# from ..db.manager import DatabaseManager
from utils.parse_scrape import fetch_page, fetch_script_tag, determine_separator

class EventParser:
    def __init__(self, venue_id, db):
        self.venue_id = venue_id
        self.db = db
        self.logger = LogManager(__name__)

    async def parse(self, show, session, url):
        if self.venue_id == 'nl_013':
            await self._parse_nl_013(show, session, url)
        elif self.venue_id == 'nl_melkweg':
            await self._parse_nl_melkweg(show, session, url)
        else:
            raise Exception(f'{self.venue_id} does not exist!')

    async def _parse_nl_013(self, show, session, url):
    ### 013 EVENT DICT KEYS ###
    # ROOT: ['id', 'title', 'subTitle', 'mobileEventDescription', 'supportActs', 'slug', 'type', 'url', 'dates', 'flags', 'colors', 'genres', 'images']
    # FLAGS['soldOut', 'onlyOne', 'cancelled', 'moved', 'newDate', 'onLocation', 'fewTicketsAvailable', 'saleStarted', 'saleEnded', 'started']
    ###########################
        try:
            relative_url = show.get('url')
            full_url = urljoin(url, relative_url)

            async def data_fetcher(show, session, url): # Reuse json fetching logic from the 013 website
                try:
                    event_response = await fetch_page(session, url)
                    event_soup = BeautifulSoup(event_response, 'html.parser')
                    script_tag = fetch_script_tag(event_soup, -1)
                    event_data = json.loads(script_tag.string)
                    return event_data
                except Exception as e:
                    self.logger.exception(f'Error fetching 013 json: {e}')

            def check_ticket_status(show): # Sets ticket sale status based on flags in json
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
                    self.logger.exception(f'Ticket status could not be checked for {full_url}: {e}')
                    return 'UNKNOWN'

            event_id = str(self.venue_id + '-' + '-'.join(relative_url.split('/')[2:]))
            event_status = await self.db.should_recheck_event(event_id)

            if event_status == 'EVENT_UPDATE':
                self.logger.debug(f'Updating event {event_id}')
                try:
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
                    self.logger.debug('Up-to-date scrape ' + event_id + ': ' + str(data))
                    await self.db.update_event_data(event_id, data)
                except Exception as e:
                    self.logger.exception(f'Failed to update entry {event_id}: {e}')

            elif event_status == 'EVENT_EXISTS':
                self.logger.debug(f'Event {event_id} exists but does not require updating')

            elif event_status == 'EVENT_DOES_NOT_EXIST':
                self.logger.debug(f'Event {event_id} does not exist and is getting built')
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
                            'venue_id': self.venue_id,
                            'last_check': datetime.now(),
                            'last_modified': datetime.now()
                            }
                    self.logger.debug(str(data))

                    await self.db.insert_event_data(data)
                except Exception as e:
                    self.logger.exception(f'Failed to build new entry {event_id}: {e}')

        except Exception as e:
            self.logger.exception(f"Error parsing event page {url}: {e}")

    async def _parse_nl_melkweg(self, show, session, url):
        try:
            relative_url = show.a.get('href') # Whatever comes behind the domain name
            full_url = urljoin(url, relative_url) # Duh
            def check_ticket_status(show): # Checks ticket status primarily based on a label seen on the agenda page
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
                    self.logger.exception(f'Ticket status could not be checked for {url}: {e}')
                    return 'UNKNOWN'

            async def data_fetcher(session, url): # Fetches event page, returns as a soup
                response = await fetch_page(session, url) 
                soup = BeautifulSoup(response, 'html.parser')
                return soup

            def fetch_subtitle(show): # Find subtitle on agenda page, return empty if none
                if show.find(class_='styles_event-compact__subtitle__yGojc'): 
                    subtitle = show.find(class_='styles_event-compact__subtitle__yGojc').get_text(strip=True)
                else:
                    subtitle = ''
                return subtitle

            def fetch_support(event_soup): # Find support acts on event page
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
            if event_type and (event_type.span.get_text(strip=True).lower() in ['concert', 'club', 'festival']): # Filter event types (exclude expositions and cinema)
                event_id = str(self.venue_id + '-' + relative_url.split('/')[-2])
                event_status = await self.db.should_recheck_event(event_id)

                if event_status == 'EVENT_UPDATE':
                    try:
                        event_soup = await data_fetcher(session, full_url)
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

                        self.logger.debug('Up-to-date scrape ' + event_id + ': ' + str(data))
                        await self.db.update_event_data(event_id, data)
                    except Exception as e:
                        self.logger.exception(f'Failed to update entry {event_id}: {e}')

                elif event_status == 'EVENT_EXISTS':
                    self.logger.debug(f'Event {event_id} exists but does not require updating')

                elif event_status == 'EVENT_DOES_NOT_EXIST':
                    self.logger.debug(f'Event {event_id} does not exist and is getting built')
                    try:
                        event_soup = await data_fetcher(session, full_url)
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
                                'url': full_url,
                                'venue_id': self.venue_id,
                                'last_check': datetime.now(),
                                'last_modified': datetime.now(),
                                }

                        self.logger.debug(str(data))
                        await self.db.insert_event_data(data)
                    except Exception as e:
                        self.logger.exception(f'Failed to build new entry {event_id}: {e}')

            else:
                self.logger.debug('Event is not the correct type: ' + full_url)
                return None
        except Exception as e:
            self.logger.exception(f"Error parsing event page {event_id}: {e}")
            return None



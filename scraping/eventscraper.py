import asyncio
import aiohttp
import json
from bs4 import BeautifulSoup

from utils.parse_scrape import fetch_page, fetch_script_tag
from scraping.eventparser import EventParser
from logs.manager import LogManager

class EventScraper:
    def __init__(self, venue_id, db):
        self.venue_id = venue_id
        self.db = db
        self.logger = LogManager(__name__)

    async def scrape(self):
        if self.venue_id == 'nl_013':
            await self._scrape_nl_013()
        elif self.venue_id == 'nl_melkweg':
            await self._scrape_nl_melkweg()
        else:
            raise Exception(f'{self.venue_id} does not exist!')

    async def _scrape_nl_013(self):
        base_url = 'https://www.013.nl/programma'
        async with aiohttp.ClientSession() as session:
            try:
                agenda_html = await fetch_page(session, base_url)
                soup = BeautifulSoup(agenda_html, 'html.parser')

                # 013 uses json to store all information on events and generates its pages that way. It is actually very effective.
                # This fetches and pre-processes the json
                script_tag = fetch_script_tag(soup, -3) # Second parameter is a position, see function. In this case, the expected json is in the 3rd to last script tag. This makes sense when you look at the code. There are few other unique identifiers that I know to work with, so positional it is.
                script_content = script_tag.string
                start_index = script_content.find('{"')
                end_index = script_content.find('}]},')+3
                json_content = script_content[start_index:end_index]

                agenda = json.loads(json_content)['events'] # From here everything is accessible as a list of dictionary. Every event is a dict.

                tasks = []
                parser = EventParser(self.venue_id, self.db)
                for show in agenda:
                    tasks.append(parser.parse(show, session, base_url)) # Adds tasks for rapid scraping async goodness

                await asyncio.gather(*tasks)

            except aiohttp.ClientError as ce:
                self.logger.error(f"HTTP request error: {ce}")
                return []
            except Exception as e:
                self.logger.error(f"An error occurred in {self.venue_id}: {e}")
                return []       

    async def _scrape_nl_melkweg(self):
        base_url = 'https://melkweg.nl/en/agenda/'

        async with aiohttp.ClientSession() as session:
            try:
                # Load agenda page
                agenda_html = await fetch_page(session, base_url)
                soup = BeautifulSoup(agenda_html, 'html.parser')
                agenda = soup.find_all(class_="styles_event-list-day__list-item__o6KTp") # Makes a list of all event entries in the agenda

                tasks = [] # Prepare for async goodness
                parser = EventParser(self.venue_id, self.db)
                for show in agenda:
                    tasks.append(parser.parse(show, session, base_url)) # Adds tasks for rapid scraping async goodness

                parsed_results = await asyncio.gather(*tasks)
                return [result for result in parsed_results if result is not None] # Filter out the empties to sanitise data
            except aiohttp.ClientError as ce:
                self.logger.error(f"HTTP request error: {ce}")
                return []
            except Exception as e:
                self.logger.error(f"An error occurred in {self.venue_id}: {e}")
                return []

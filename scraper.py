# 'global' packages
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from urllib.parse import urljoin

# local modules
from logs.manager import LogManager
from db.manager import DatabaseManager
from scraping.eventscraper import EventScraper


######## VENUE EVENT PARSERS ########

async def main():
    db_name = 'concertron_test_1.db'
    db = DatabaseManager(db_name)

    db.execute_query('''CREATE TABLE IF NOT EXISTS events (
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

    # asyncio.run(scrape_melkweg(db))
    # asyncio.run(scrape_013(db))

    scrape_013 = EventScraper('nl_013', db)
    scrape_melkweg = EventScraper('nl_melkweg', db)
    await asyncio.gather(
            scrape_013.scrape(),
            scrape_melkweg.scrape(),
    )

    # asyncio.run(scrape_013.scrape())
    # asyncio.run(scrape_melkweg())

    db.disconnect()
    logger.info('Goodbye!')

if __name__ == '__main__':
    logger = LogManager(__name__)
    logger.info('Running test mode')

    asyncio.run(main())

import asyncio
import aiohttp
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
from urllib.parse import urljoin

def determine_separator(data):
    separator_slash_count = data.count(' / ')
    separator_dash_count = data.count(' - ')

    if separator_slash_count > separator_dash_count:
        return ' / '
    elif separator_dash_count > separator_slash_count:
        return ' - '
    else:
        return ' / ' 

async def fetch_page(session, url):
    async with session.get(url) as response:
        if response.status == 200:
            return await response.text()
        else:
            raise aiohttp.ClientResponseError(status=response.status)

async def parse_event_melkweg(show, session, url):
    try:
        tag_sep = '·'
        event_type = show.find_all(class_='styles_event-compact__type-item__RPgGU')
        if event_type and (event_type[0].span.get_text(strip=True).lower() in ['concert', 'club', 'festival']):
            event_response = await fetch_page(session, url)
            event_soup = BeautifulSoup(event_response, 'html.parser')
            if show.find(class_='styles_event-compact__subtitle__yGojc'):
                subtitle = show.find(class_='styles_event-compact__subtitle__yGojc').get_text(strip=True)
            else:
                subtitle = ''

            event_subs = event_soup.find_all(class_='styles_event-header__subtitle__LBG7q')
            if (len(event_subs) == 1 and event_subs[0].get_text(strip=True) != subtitle) or (len(event_subs) == 2):
                support_line = event_subs[-1].get_text(strip=True)
                if len(support_line.split(': ')) == 2:
                    acts = support_line.split(': ')[-1]
                    support = acts.split(determine_separator(acts))
                else: support = ''
            else: support = ''

            data = {
                    'id': url.split('/')[-2],
                    'artist': show.h3.get_text(strip=True),
                    'subtitle': subtitle,
                    'support': support,
                    'date': datetime.fromisoformat(event_soup.time.get('datetime').replace('Z', '+00:00')),
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
    parsed_results = []

    async with aiohttp.ClientSession() as session:
        try:
            agenda_html = await fetch_page(session, base_url)

            soup = BeautifulSoup(agenda_html, 'html.parser')
            agenda = soup.find_all(class_="styles_event-list-day__list-item__o6KTp")

            tasks = []
            for show in agenda:
                # print(show.a.get('href'))
                relative_url = show.a.get('href')
                full_url = urljoin(base_url, relative_url)
                tasks.append(parse_event_melkweg(show, session, full_url))

            parsed_results.extend(await asyncio.gather(*tasks))
            return [result for result in parsed_results if result is not None]
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

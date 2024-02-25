import requests
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
        # If both separators appear an equal number of times,
        # or if neither separator is found, you might choose
        # one as the default or handle it differently based on your requirements.
        return ' / '  # You can change this to ' - ' or handle it differently

def scrape_melkweg():
    tag_sep = '·'
    data = []
    response = requests.get('https://melkweg.nl/en/agenda/')

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        agenda = soup.find_all(class_="styles_event-list-day__list-item__o6KTp")

        for show in agenda:
            # print(show.a.get('href'))
            relative_url = show.a.get('href')
            full_url = urljoin(response.url, relative_url)
            event_type = show.find_all(class_='styles_event-compact__type-item__RPgGU')
            if event_type and (event_type[0].span.get_text(strip=True).lower() in ['concert', 'club', 'festival']):
                event_response = requests.get(full_url)
                event_soup = BeautifulSoup(event_response.text, 'html.parser')

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

                x = {
                        'id': relative_url.split('/')[-2],
                        'artist': show.h3.get_text(strip=True),
                        'subtitle': subtitle,
                        'support': support,
                        'date': datetime.fromisoformat(event_soup.time.get('datetime').replace('Z', '+00:00')),
                        'tags': show.find(class_='styles_tags-list__DAdH2').get_text(strip=True).split(tag_sep) if show.find(class_='styles_tags-list__DAdH2') else '',
                        'url': full_url,
                        }

                data.append(x)

    else:
        raise requests.HTTPError("Server responded with " + str(response.status_code))

    return data

if __name__ == '__main__':
    df = pd.DataFrame(scrape_melkweg())
    print(df)
    df.to_csv('test.csv')

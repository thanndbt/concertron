import scrapy
from concertron.items import ConcertronNewItem, ConcertronUpdatedItem, ImageItem
from datetime import datetime, timezone
from concertron.utils import does_event_exist
import json

class spider(scrapy.Spider):
    name = "nl_effenaar"
    allowed_domains = ["effenaar.nl"]
    start_urls = ["https://www.effenaar.nl/_next/data/pknsU4Zs6EV--qHIa_Tla/nl/agenda.json"]

    def check_status(self, state):
        if state:
            if state == 'cancelled':
                return 'CANCELLED'
            elif state == 'moved':
                return 'MOVED'
            elif state == 'last_tickets':
                return 'FEW_TICKETS'
            elif state == 'sold_out':
                return 'SOLD_OUT'
            elif state == 'new':
                return 'SALE_LIVE'
            else:
                return 'UNKNOWN'
        else:
            return 'SALE_LIVE'

    def split_subtitle(self, data):
        subtitle_list = []
        support = []
        if data:
            split = data.split('|')
            for segment in split:
                if segment.strip().startswith('+'):
                    support.extend(map(str.strip, segment.split('+')[1:]))
                elif segment.strip().lower().startswith('feat. '):
                    step = segment.strip()[6:].split(', ')
                    if ' and ' in step[-1]:
                        support.extend(step[:-1] + step[-1].split(' and '))
                    else:
                        support.extend(step)
                else:
                    subtitle_list.append(segment)

        subtitle = '|'.join(subtitle_list)
        if 'many more' in support:
            support.remove('many more')
        return subtitle, support

    def parse(self, response):
        script = json.loads(response.body)
        matches = []
        for query in script['pageProps']['dehydrated']['queries']:
            if query['queryKey'] == 'events-collection-nl':
                matches.append(query)
        if len(matches) == 1:
            agenda = matches[0]['state']['data']['pageData']['algolia']['serverState']['initialResults']['production_events']['results'][0]['hits']
        for show in agenda: 
            subtitle, support = self.split_subtitle(show.get('subtitle'))
            main_data = { 
                    '_id': str(self.name + show.get('slug').split('/')[-1] + '-' + show.get('objectID').split('/')[-1].split(':')[0]),
                    'title': show.get('title').strip(),
                    'subtitle': subtitle,
                    'support': support,
                    'date': datetime.fromtimestamp(show.get('date')).astimezone(timezone.utc).replace(tzinfo=None),
                    'location': str(show.get('locations')[0].get('title') + ', ' + ('Effenaar, ' if "zaal" in show.get('locations')[0].get('title').lower() else '') + 'Eindhoven, NL'),
                    'tags': [genre['title'] for genre in show.get('genres')],
                    'status': self.check_status(show.get('state')),
                    }
            event_status = does_event_exist(main_data.get('_id'))
            if event_status == 'EVENT_DOES_NOT_EXIST':
                additional_data = {
                        'event_type': 'Comedy' if 'Popcultuur / Comedy / Film' in main_data.get('tags') else 'Concert',
                        'lineup': support + main_data.get('title').split(' | ')[0].split(' + '),
                        'url': 'https://effenaar.nl' + show.get('slug'),
                        'venue_id': self.name,
                        'last_check': datetime.now(),
                        'last_modified': datetime.now(),
                        }
                main_data.update(additional_data)
                event_item = ConcertronNewItem(**main_data)
                yield event_item

                image_data = {
                        'image_urls': [show.get('header_image').get('image').get('sizes').get('2510w')],
                        '_id': main_data['_id']
                }
                image_item = ImageItem(**image_data)
                yield image_item

            elif event_status == "EVENT_EXISTS" or event_status == "EVENT_UPDATE":
                event_item = ConcertronUpdatedItem(**main_data)
                yield event_item

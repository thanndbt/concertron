import scrapy
from concertron.items import ConcertronNewItem, ConcertronUpdatedItem, ConcertronTagsItem, ImageItem
from datetime import datetime, timezone
import json
from html import unescape

from concertron.utils import does_event_exist 

class spiderEvents(scrapy.Spider):
    name = "nl_013_events"
    allowed_domains = ["013.nl"]
    start_urls = ["https://013.nl/programma"]
    venue_id = 'nl_013'

    def check_status(self, response, url): 
        # Checks status based on the ribbons on the calendar page
        if url.split('/')[-1] == 'programma':
            label = response.xpath('.//div[@class="ribbon_basic ribbon_small"]//text()').get()
            if label:
                if label == 'Uitverkocht':
                    return 'SOLD_OUT'
                elif label == 'Laatste kaarten':
                    return 'FEW_TICKETS'
                elif label == 'Afgelast': # Could be different
                    return 'CANCELLED'
            else:
                return None
        # Checks status based on things on the event page
        else:
            button = response.xpath("//*[contains(@class, 'button-zoom')]")
            price_table =  response.xpath("//ul[@class='relative specs_table']/li/b[text()='Entree']//following-sibling::div")
            # Most events have a button, even as a dummy for sold out shows
            if button:
                button_text = ''.join(button[0].xpath(".//text()").getall()).strip()
                if button_text == 'Tickets':
                    return 'SALE_LIVE'
                elif button_text == 'On sale alert':
                    return 'SALE_NOT_LIVE'
                elif button_text == 'Uitverkocht':
                    return 'SOLD_OUT'
                elif button_text == 'Laatste kaarten' or button_text == 'Laatste tickets':
                    return 'FEW_TICKETS'
                elif button_text == 'Afgelast': # Could be different, no way to tell right now
                    return 'CANCELLED'
            # Free events and some sale_not_live cases do not have a button. This is based on the data in thetablew on the side
            elif price_table:
                price = price_table.xpath('.//b/text()').get()
                if price == 'Gratis':
                    return 'FREE'
                else:
                    return 'SALE_NOT_LIVE'
            else:
                return 'UNKNOWN' #Thusfar, nothing returns this

    def parse(self, response):
        for entry in response.xpath('//article'):
            show_url = entry.xpath('.//a/@href').get()
            show = entry.xpath('.//a')[0]

            main_data = {
                    '_id': str(self.venue_id + '-' + '-'.join(show_url.split('/')[4:])),
                    'title': unescape(show.xpath('.//div//h2/text()').get()),
                    'subtitle': unescape(show.xpath('.//div//h3/text()').get() if show.xpath('.//div//h3') else (show.xpath('.//div//p/text()').get() if show.xpath(".//div//p") else '')),
                    'date': datetime.fromisoformat(show.xpath('.//time/@datetime').get()).astimezone(timezone.utc).replace(tzinfo=None),
                    'status': self.check_status(show, response.url),
            }

            event_status = does_event_exist(main_data.get('_id'))
            if event_status == 'EVENT_DOES_NOT_EXIST':
                yield scrapy.Request(url=show_url, callback=self.parse_new, meta={'main_data': main_data})
            elif event_status == "EVENT_EXISTS":
                event_item = ConcertronUpdatedItem(**main_data)
                yield event_item
            elif event_status == "EVENT_UPDATE":
                yield scrapy.Request(url=show_url, callback=self.parse_updated, meta={'main_data': main_data})

    def parse_new(self, response):
        main_data = response.meta['main_data']
        location_line = response.xpath("//ul[@class='relative specs_table']/li[last()]/*/text()").getall()
        venue_name = '013'
        town = 'Tilburg, NL'
        connector = ', '
        base_location = connector.join([venue_name, town])
        support = response.xpath('//article//ul[@class="mt-1 flex flex-wrap gap-2 heading-din text-xs md:text-lead"]/li/text()').getall() if response.xpath('//article//ul[@class="mt-1 flex flex-wrap gap-2 heading-din text-xs md:text-lead"]') else []
        additional_data = {
                'event_type': 'Festival' if 'festival' in ' '.join(response.xpath("//h1/text()").getall()).lower() else 'Concert',
                'support': support,
                'lineup': support + main_data.get('title').split(' + '),
                'location': connector.join([location_line[1], base_location]) if location_line[0] == 'Zaal' else (connector.join([location_line[1], town]) if location_line[0] == 'Locatie' else venue),
                'url': response.url,
                'tags': [],
                'status': self.check_status(response, response.url),
                'venue_id': self.venue_id,
                'last_check': datetime.now(),
                'last_modified': datetime.now(),
        }

        main_data.update(additional_data)
        event_item = ConcertronNewItem(**main_data)
        yield event_item

        image_data = {
                'image_urls': [response.xpath("//img/@src").get()],
                '_id': main_data['_id']
        }
        image_item = ImageItem(**image_data)
        yield image_item

    def parse_updated(self, response):
        main_data = response.meta['main_data']
        location_line = response.xpath("//ul[@class='relative specs_table']/li[last()]/*/text()").getall()
        venue_name = '013'
        town = 'Tilburg, NL'
        connector = ', '
        base_location = connector.join([venue_name, town])
        support = response.xpath('//article//ul[@class="mt-1 flex flex-wrap gap-2 heading-din text-xs md:text-lead"]/li/text()').getall() if response.xpath('//article//ul[@class="mt-1 flex flex-wrap gap-2 heading-din text-xs md:text-lead"]') else []
        additional_data = {
                'support': support,
                'lineup': support + main_data.get('title').split(' + '),
                'location': connector.join([location_line[1], base_location]) if location_line[0] == 'Zaal' else (connector.join([location_line[1], town]) if location_line[0] == 'Locatie' else venue),
                'status': self.check_status(response, response.url),
                'last_check': datetime.now(),
        }
        main_data.update(additional_data)

        event_item = ConcertronUpdatedItem(**main_data)
        yield event_item


class spiderTags(scrapy.Spider):
    name = "nl_013_tags"
    allowed_domains = ["013.nl"]
    start_urls = ["https://013.nl/programma"]
    venue_id = 'nl_013'

    def check_tags(self, response):
        #Takes a list of events from the response to the request
        output = json.loads(response.text)
        matches = output.get('events')

        for match in matches:
            if match in response.meta.get('events').keys():
                tag_data = {
                        '_id': response.meta.get('events').get(match),
                        'tag': response.meta.get('tag'),
                        'last_modified': datetime.now()
                        }
                tag_item = ConcertronTagsItem(**tag_data)
                yield tag_item

    def parse(self, response):
        # Builds event db, then gets filters and passes these on to check_tags one by one
        events = {}
        for entry in response.xpath('//article'):
            show_url = entry.xpath('.//a/@href').get()
            event_id = str(self.venue_id + '-' + '-'.join(show_url.split('/')[4:]))
            internal_id = int(entry.xpath('./@x-show').get().split('(')[1].replace(')', ''))
            events.update({internal_id: event_id})

        filters = json.loads(response.xpath('//main//script/text()').get().splitlines()[-1].split(' = ')[-1].replace(';', ''))
        for tag in filters.items():
            yield scrapy.Request(url=str(f'https://www.013.nl/actions/visited/search?q=&genre={tag[0]}'), callback=self.check_tags, meta={'tag': tag[1], 'events': events})

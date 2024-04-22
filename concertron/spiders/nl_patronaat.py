import scrapy
from concertron.items import ConcertronNewItem, ConcertronUpdatedItem, ImageItem
from datetime import datetime, timezone
from concertron.utils import does_event_exist, construct_datetime

class spider(scrapy.Spider):
    name = "nl_patronaat"
    allowed_domains = ["patronaat.nl"]
    start_urls = ["https://www.patronaat.nl/programma/"]

    def check_status(self, response, status_hint):
        status_tag = response.xpath(".//div[contains(@class, 'event-program__status-tag')]/p/text()").get()
        if status_hint:
            if status_hint == 'CANCELLED':
                return 'CANCELLED'
            else:
                return 'UNKNOWN'
        elif status_tag:
            if status_tag == 'UITVERKOCHT':
                return 'SOLD_OUT'
            elif status_tag == 'LAATSTE KAARTEN':
                return 'FEW_TICKETS'
            elif status_tag == 'just announced':
                return 'SALE_LIVE'
            else:
                return 'UNKNOWN'
        elif response.xpath(".//a[@class='event__tags-item free event__tags-item--free']").get():
            return 'FREE'
        else:
            return 'SALE_LIVE'

    def split_title(self, data):
        status = None
        support = []
        title = ''
        if data.split(':')[0].lower == 'gecancelled':
            status = 'CANCELLED'
        if ':' in data and not status:
            split = data.split(': ')
            title = split[0]
            support = split[1].split(' + ')
        else:
            split = data.split(' + ')
            title = split[0]
            support = split[1:]
        if 'support' in support:
            support.remove('support')
        return title, support, status

    def parse(self, response):
        if response.body:
            agenda = response.xpath("//div[@class='event-program']")
            for show in agenda: 
                title, support, status_hint = self.split_title(show.xpath(".//h3/a/text()").get().strip())
                show_url = show.xpath(".//a/@href").get()
                main_data = { 
                        '_id': str(self.name + '-' + show_url.split('/')[-2]),
                        'title': title.strip(),
                        'subtitle': show.xpath(".//div[@class='event-program__subtitle']/text()").get().strip(),
                        'support': list(map(str.strip, support)), # Should be list, if no support, then just []
                        'tags': list(map(str.strip, show.xpath(".//a[@class='event__tags-item event__tags-item--genre']/text()").getall())),
                        'status': self.check_status(show, status_hint),
                        }
                event_status = does_event_exist(main_data.get('_id'))
                if event_status == 'EVENT_DOES_NOT_EXIST':
                    yield scrapy.Request(url=show_url, callback=self.parse_new, meta={'main_data': main_data})
                elif event_status == "EVENT_EXISTS":
                    event_item = ConcertronUpdatedItem(**main_data)
                    yield event_item
                elif event_status == "EVENT_UPDATE":
                    yield scrapy.Request(url=show_url, callback=self.parse_updated, meta={'main_data': main_data})
            if response.meta.get('counter'):
                counter = response.meta.get('counter') + 1
            else:
                counter = 1
            yield scrapy.FormRequest(url="https://patronaat.nl/cms/wp-admin/admin-ajax.php", method="POST", formdata={"action": "more_posts", "offset": str(counter), "taxonomy": "", "term": "", "type": "pt_event"}, callback=self.parse, meta={'counter': counter})

    def parse_new(self, response):
        main_data = response.meta['main_data']
        location = response.xpath(".//div[@class='event__info-bar--remote-location']/text()").get().strip()
        # print(response.xpath("//div[@class='event__info-bar--star-date']/text()").get().strip(), response.xpath("//div[@class='event__info-bar--doors-open']/text()").get().strip().split()[-1])
        additional_data = {
                'event_type': 'Club' if 'nachtleven' in main_data.get('tags') else ('Festival' if 'fest' in main_data.get('title') else 'Concert'),
                'lineup': main_data.get('support') + [main_data.get('title').split('•')[0].strip()],
                'location': str(location + (', Patronaat' if 'Stage' in location or 'CLUB3' in location else '') + ', Haarlem, NL'),
                'date': construct_datetime('nl', response.xpath("//div[@class='event__info-bar--star-date']/text()").get().strip(), response.xpath("//div[@class='event__info-bar--doors-open']/text()").get().strip().split()[-1]),
                'venue_id': self.name, # Should not have to change
                'url': response.url,
                'last_check': datetime.now(),
                'last_modified': datetime.now(),
                }
        main_data.update(additional_data)
        
        festival_lineup = response.xpath("//div[contains(@class, 'event__support--festival')]//div[@class='event__support-act--info']/h2/text()").getall()
        if festival_lineup:
            main_data['support'] += list(map(str.strip, festival_lineup))
            main_data['lineup'] += list(map(str.strip, festival_lineup))
            main_data['event_type'] = 'Festival'

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
        location = response.xpath(".//div[@class='event__info-bar--remote-location']/text()").get().strip()
        additional_data = {
                'lineup': main_data.get('support') + [main_data.get('title').split('•')[0].strip()],
                'location': str(location + (', Patronaat' if 'Stage' in location or 'CLUB3' in location else '') + ', Haarlem, NL'),
                'date': construct_datetime('nl', response.xpath("//div[@class='event__info-bar--star-date']/text()").get().strip(), response.xpath("//div[@class='event__info-bar--doors-open']/text()").get().strip().split()[-1]),
                'last_check': datetime.now(),
        }

        main_data.update(additional_data)

        festival_lineup = response.xpath("//div[contains(@class, 'event__support--festival')]//div[@class='event__support-act--info']/h2/text()").getall()
        if festival_lineup:
            main_data['support'] += list(map(str.strip, festival_lineup))
            main_data['lineup'] += list(map(str.strip, festival_lineup))

        event_item = ConcertronUpdatedItem(**main_data)
        yield event_item

import scrapy
from concertron.items import ConcertronNewItem, ConcertronUpdatedItem
from datetime import datetime, timezone
from concertron.utils import does_event_exist

class spider(scrapy.Spider):
    name = "nl_melkweg"
    allowed_domains = ["www.melkweg.nl"]
    start_urls = ["https://www.melkweg.nl/en/agenda/"]

    def determine_separator(self, data): # This determines what separator to use. Built around the varying way Melkweg lists lineups and support acts.
        separator_slash_count = data.count(' / ')
        separator_dash_count = data.count(' - ')

        if separator_slash_count > separator_dash_count:
            return ' / '
        elif separator_dash_count > separator_slash_count:
            return ' - '
        else:
            return ' / ' # Function defaults to ' / ' as this is more prevalent for Melkweg

    def fetch_support(self, response):
        event_subs = response.css('p.styles_event-header__subtitle__LBG7q ::text').getall() # Find all subtitles on event page
        if (len(event_subs) == 1 and event_subs[0] != response.meta['main_data']['subtitle']) or (len(event_subs) == 2): # Only trigger if the only line is not existing subtitle or if there are multiple lines (in which case it will take the latter of the two)
            support_line = event_subs[-1]
            if len(support_line.split(': ')) == 2:
                acts = support_line.split(': ')[-1]
                support = acts.split(self.determine_separator(acts))
            else: support = []
        else: support = []
        return support

    def check_status(self, page, _type): # Checks ticket status primarily based on a label seen on the agenda page
        if _type == 'event':
            button = page.css('span.styles_button__text__KlsHu ::text').get()
            if button == 'Tickets':
                return 'SALE_LIVE'
            elif button == 'Sold out':
                return 'SOLD_OUT'
            elif button == 'Moved':
                return 'MOVED'
            elif button == 'Cancelled':
                return 'CANCELLED'
            elif button == 'Free':
                return 'FREE'
            elif page.css('li.styles_ticket-prices__presale-text__2ljIp'):
                return 'SALE_NOT_LIVE'
            else:
                return 'UNKNOWN'

        elif _type == 'agenda':
            event_label = page.css('span.styles_label__p9pQy ::text').get()
            if event_label == 'Sold out':
                return 'SOLD_OUT'
            elif event_label == 'Cancelled':
                return 'CANCELLED'
            elif event_label == 'Moved':
                return 'MOVED'
            else:
                return None

        else:
            raise Exception('Page type is invalid!')

    def parse(self, response):
        for show in response.css("li.styles_event-list-day__list-item__o6KTp"):
            show_url = show.css('a ::attr(href)').get()
            subtitle = show.css('p.styles_event-compact__subtitle__yGojc ::text')
            main_data = {
                    '_id': str(self.name + '-' + show_url.split('/')[-2]),
                    'title': show.css('h3 ::text').get(),
                    'subtitle': subtitle.get() if subtitle else '',
                    'tags': list(filter(lambda x: x != ' · ', show.css('p.styles_tags-list__DAdH2 ::text').extract())),
                    'status': self.check_status(show, 'agenda'),
                    }
            event_status = does_event_exist(main_data.get('_id'))
            if event_status == 'EVENT_DOES_NOT_EXIST':
                yield scrapy.Request(url=str('https://www.melkweg.nl' + show_url), callback=self.parse_new, meta={'main_data': main_data})
            elif event_status == "EVENT_EXISTS":
                event_item = ConcertronUpdatedItem(**main_data)
                yield event_item
            elif event_status == "EVENT_UPDATE":
                yield scrapy.Request(url=str('https://www.melkweg.nl' + show_url), callback=self.parse_updated, meta={'main_data': main_data})

    def parse_new(self, response):
        additional_data = {
                'event_type': response.css('ul.styles_event-header__profiles-list__igpuv ::text').get(),
                'support': self.fetch_support(response),
                'date': datetime.fromisoformat(response.css('time ::attr(datetime)').get().replace('Z', '+00:00')).astimezone(timezone.utc).replace(tzinfo=None),
                'location': str(response.css('span.styles_event-header__location__jvvG4 ::text').get().strip() + ', Melkweg, Amsterdam, NL'),
                'status': self.check_status(response, 'event'),
                'url': response.url,
                'venue_id': self.name,
                'last_check': datetime.now(),
                'last_modified': datetime.now(),
        }

        main_data = response.meta['main_data']
        main_data.update(additional_data)
        event_item = ConcertronNewItem(**main_data)
        yield event_item

    def parse_updated(self, response):
        additional_data = {
                'support': self.fetch_support(response),
                'date': datetime.fromisoformat(response.css('time ::attr(datetime)').get().replace('Z', '+00:00')).astimezone(timezone.utc).replace(tzinfo=None),
                'location': str(response.css('span.styles_event-header__location__jvvG4 ::text').get().strip() + ', Melkweg, Amsterdam, NL'),
                'status': self.check_status(response, 'event'),
        }

        main_data = response.meta['main_data']
        main_data.update(additional_data)
        event_item = ConcertronUpdatedItem(**main_data)
        yield event_item

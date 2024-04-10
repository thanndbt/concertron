import scrapy
from concertron.items import ConcertronNewItem, ConcertronUpdatedItem, ConcertronTagsItem
from datetime import datetime, timezone
from concertron.utils import does_event_exist, download_image


class spiderEvents(scrapy.Spider):
    name = "nl_tivolivredenburg_events"
    allowed_domains = ["www.tivolivredenburg.nl"]
    start_urls = ["https://www.tivolivredenburg.nl/agenda"]
    venue_id = 'nl_tivolivredenburg'

    def check_event_type(self, response):
        # The only indication of event types at Tivo are certain collections.
        # Some collections are genre indicators but it is not consistent.
        # Only ones that are indicative of anything are about lectures, podcasts, etc.
        collection_link = response.css('a.event-collection-cta__link ::attr(href)').get()
        if collection_link == 'https://tivolivredenburg.nl/kennis':
            return 'Knowledge'
        if collection_link == 'https://www.tivolivredenburg.nl/studio/podcast/':
            return 'Podcast'
        # elif collection_link == 'https://tivolivredenburg.nl/collection':
                # return 'Collection'
        else:
            return 'Concert'

    def check_status(self, response):
        icon = response.xpath('.//span[@class="agenda-list-item__icon"]').get() # Lil shopping cart icon that links to ticket sale
        label = response.xpath('.//p[@class="agenda-list-item__label"]/text()').get()
        subtitle = str(response.xpath(".//p[@class='agenda-list-item__text']/text()").get()).strip()
        if icon:
            return 'SALE_LIVE'
        elif label:
            if label.lower() == 'uitverkocht':
                return 'SOLD_OUT'
            elif label.lower() == 'verplaatst':
                return 'MOVED'
            elif label.lower() == 'afgelast':
                return 'CANCELLED'
        elif not icon and not label:
            if 'gratis' in subtitle.lower():
                return 'FREE'
            else:
                return 'SALE_NOT_LIVE'
        else:
            return 'UNKNOWN'

    def fetch_support(self, response):
        empty_types = ['geen', 'nog geen bekend', 'nog niet bekend', 'geen support', 'geen support act']
        support_field = response.xpath("//dt[text()='Support act']/following-sibling::dd[1]/text()").get()
        if support_field:
            if str(support_field).lower() in empty_types:
                return []
            elif ' + ' in support_field:
                return support_field.split(' + ')
            elif ', ' and ' & ' in support_field:
                return support_field.replace(' & ', ', ').split(', ')
            elif support_field:
                return [support_field]
            elif response.xpath("//dt[text()='Uitvoerenden']"):
                return response.xpath("//dt[text()='Uitvoerenden']/following-sibling::dd[1]/p/strong/text()").getall()
            else:
                return []
        else:
            return []

    def fetch_datetime(self, response):
        months = {'jan': 1, 'feb': 2, 'mrt': 3, 'apr': 4, 'mei': 5, 'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9, 'okt': 10, 'nov': 11, 'dec': 12}
        all_times = response.xpath('//div[@class="lane  lane--event"]//time/text()').getall()
        date = all_times[-1].strip().split(' ')
        if len(all_times) == 1:
            return datetime(int(date[-1]), months.get(date[-2]), int(date[-3])).astimezone(timezone.utc).replace(tzinfo=None)
        else:
            time = all_times[0].split(':')
            return datetime(int(date[-1]), months.get(date[-2]), int(date[-3]), int(time[0]), int(time[1])).astimezone(timezone.utc).replace(tzinfo=None)

    def fetch_location(self, response):
        # We like readable stuff. Location line would not have been readable :(
        venue = 'TivoliVredenburg'
        town = 'Utrecht, NL'
        base_location = venue + ', ' + town
        location_line = response.xpath("//dt[text()='Locatie']/following-sibling::dd[1]/*/text()").get()
        internal = ['Grote Zaal', 'Ronda', 'Pandora', 'Hertz', 'Cloud Nine', 'Club Nine', 'Park 6', 'Rabo Open Stage']
        if location_line in internal:
            return str(location_line + ', ' + base_location)
        if location_line:
            return str(location_line + ', ' + town)
        else:
            return base_location

    def parse(self, response):
        for show in response.css('li.agenda-list-item'):
            show_url = show.css('a.link ::attr(href)').get()
            main_data = {
                    '_id': str(self.venue_id + '-' + show_url.split('/')[-2]),
                    'title': str(' '.join(show.css('h2.agenda-list-item__title ::text').getall()).strip()),
                    'subtitle': str(' '.join(show.css('p.agenda-list-item__text ::text').getall()).strip()),
                    'status': self.check_status(show),
                    }
            event_status = does_event_exist(main_data.get('_id'))
            if event_status == 'EVENT_DOES_NOT_EXIST':
                yield scrapy.Request(url=show_url, callback=self.parse_new, meta={'main_data': main_data})
            elif event_status == "EVENT_EXISTS":
                event_item = ConcertronUpdatedItem(**main_data)
                yield event_item
            elif event_status == "EVENT_UPDATE":
                yield scrapy.Request(url=show_url, callback=self.parse_updated, meta={'main_data': main_data})
        if len(response.css('li.agenda-list-item')) == 50 and 'page' not in response.url:
            yield scrapy.Request(url=str(self.start_urls[0] + '/page/2'), callback=self.parse)
        else:
            max_page = int(response.xpath('//title/text()').get().split(' - ')[1].split()[-1])
            url_split = response.url.split('/')
            number_index = url_split.index('page') + 1
            old_page = int(url_split[number_index])
            url_split[number_index] = str(int(old_page + 1))
            page_url = '/'.join(url_split)
            if old_page < max_page:
                yield scrapy.Request(url=page_url, callback=self.parse)

    def parse_new(self, response):
        main_data = response.meta['main_data']
        additional_data = {
                'event_type': self.check_event_type(response), # Str
                'support': self.fetch_support(response), # Should be list, if no support, then just []
                'date': self.fetch_datetime(response),
                'location': self.fetch_location(response), 
                'tags': [],
                'url': response.url, # Str, full url. could be as simple as response.url
                'venue_id': self.venue_id, # Should not have to change
                'last_check': datetime.now(),
                'last_modified': datetime.now(),
                }
        main_data.update(additional_data)
        event_item = ConcertronNewItem(**main_data)
        download_image(response.xpath("//source/@srcset").get().split(' ')[0], main_data['_id'])
        yield event_item

    def parse_updated(self, response):
        additional_data = {
                'support': self.fetch_support(response), # Should be list, if no support, then just []
                'date': self.fetch_datetime(response),
                'location': self.fetch_location(response), 
                'venue_id': self.venue_id, # Should not have to change
                'last_check': datetime.now(),
                }

        main_data = response.meta['main_data']
        main_data.update(additional_data)
        event_item = ConcertronUpdatedItem(**main_data)
        yield event_item

class spiderTags(scrapy.Spider):
    name = "nl_tivolivredenburg_tags"
    allowed_domains = ["www.tivolivredenburg.nl"]
    start_urls = ["https://www.tivolivredenburg.nl/agenda"]
    venue_id = 'nl_tivolivredenburg'

    def check_tags(self, response):
        for show in response.css('li.agenda-list-item'):
            show_url = show.css('a.link ::attr(href)').get()
            tag_data = {
                    '_id': str(self.venue_id + '-' + show_url.split('/')[-2]),
                    'tag': response.meta.get('tag'),
                    'last_modified': datetime.now(),
                    }
            tag_item = ConcertronTagsItem(**tag_data)
            yield tag_item
        if len(response.css('li.agenda-list-item')) == 50 and 'page' not in response.url:
            url_split = response.url.split('/')
            insert_index = url_split.index('agenda') + 1
            url_split.insert(insert_index, '2')
            url_split.insert(insert_index, 'page')
            page_url = '/'.join(url_split)
            yield scrapy.Request(url=page_url, callback=self.check_tags, meta={'tag': response.meta.get('tag')})
        elif 'page' not in response.url:
            pass
        else:
            max_page = int(response.xpath('//title/text()').get().split(' - ')[1].split()[-1])
            url_split = response.url.split('/')
            number_index = url_split.index('page') + 1
            old_page = int(url_split[number_index])
            url_split[number_index] = str(int(old_page + 1))
            page_url = '/'.join(url_split)
            if old_page < max_page:
                yield scrapy.Request(url=page_url, callback=self.check_tags, meta={'tag': response.meta.get('tag')})

    def parse(self, response):
        filters = response.xpath('//a[@data-taxonomy="event_category"]/@data-term_id').getall()
        for tag in filters:
            yield scrapy.Request(url=str(self.start_urls[0] + f'/?event_category={tag}'), callback=self.check_tags, meta={'tag': tag})

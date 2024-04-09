# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class ConcertronNewItem(scrapy.Item):
    _id = scrapy.Field()
    event_type = scrapy.Field()
    title = scrapy.Field()
    subtitle = scrapy.Field()
    support = scrapy.Field()
    date = scrapy.Field()
    location = scrapy.Field()
    tags = scrapy.Field()
    status = scrapy.Field()
    url = scrapy.Field()
    venue_id = scrapy.Field()
    image_bin = scrapy.Field()
    image_url = scrapy.Field()
    last_check = scrapy.Field()
    last_modified = scrapy.Field()

class ConcertronUpdatedItem(scrapy.Item):
    _id = scrapy.Field()
    title = scrapy.Field()
    subtitle = scrapy.Field()
    support = scrapy.Field()
    date = scrapy.Field()
    location = scrapy.Field()
    tags = scrapy.Field()
    status = scrapy.Field()
    last_check = scrapy.Field()

class ConcertronTagsItem(scrapy.Item):
    _id = scrapy.Field()
    tag = scrapy.Field()
    last_modified = scrapy.Field()

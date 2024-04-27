# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
import pymongo
from datetime import datetime
import os
from PIL import Image
from concertron.items import ConcertronNewItem, ConcertronUpdatedItem, ConcertronTagsItem, ImageItem
from scrapy.pipelines.images import ImagesPipeline
import scrapy

class ConcertronPipeline:
    def __init__(self, mongo_uri, mongo_db, collection_name):
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db
        self.collection_name = collection_name

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            mongo_uri=crawler.settings.get('MONGODB_URI'),
            mongo_db=crawler.settings.get('MONGODB_DATABASE'),
            collection_name=crawler.settings.get('MONGODB_COLLECTION'),
        )

    def open_spider(self, spider):
        self.client = pymongo.MongoClient(self.mongo_uri)
        self.db = self.client[self.mongo_db]

    def close_spider(self, spider):
        self.client.close()

    def process_item(self, item, spider):
        if isinstance(item, ConcertronNewItem):
            return self.process_new(item, spider)
        elif isinstance(item, ConcertronUpdatedItem):
            return self.process_update(item, spider)
        elif isinstance(item, ConcertronTagsItem):
            return self.process_tags(item, spider)
        else:
            return item

    def process_new(self, item, spider):
        entry = item
        entry['updates'] ='new'
        self.db[self.collection_name].insert_one(dict(entry))
        return item

    def process_update(self, item, spider):
        entry = self.db[self.collection_name].find_one({'_id': item.get('_id')})

        # Compare relevant fields and check for changes
        relevant_fields = ['title', 'subtitle', 'support', 'date', 'location', 'tags', 'status']  # Define relevant fields for comparison
        # fields_changed = any(entry.get(field) != item.get(field) for field in relevant_fields)
        fields_changed = {field: item.get(field) for field in relevant_fields if item.get(field) and entry.get(field) != item.get(field)}

        # Process the updated item if relevant fields have changed
        if fields_changed:
            fields_changed['updates'] = list(fields_changed.keys())
            # Process the updated item as needed
            # Example: Update the existing item in the database
            if item.get('last_check'):
                fields_changed['last_check'] = item.get('last_check')
            fields_changed['last_modified'] = datetime.now()
            self.db[self.collection_name].update_one({'_id': item['_id']}, {'$set': fields_changed})
            return item
        elif item.get('last_check') and not fields_changed:
            self.db[self.collection_name].update_one({'_id': item.get('_id')}, {'$set': {'last_check': item.get('last_check'), 'updates': []}})
            return None
        else:
            # Skip processing if relevant fields have not changed and no deep check was done
            return None

    def process_tags(self, item, spider):
        edge_cases_art = ['Poëzie / Spoken Word']
        edge_cases_club = ['by-night', 'by-night-global', 'by-night-blobal', 'Club', 'club', '00:13']
        edge_cases_comedy = ['comedy', 'Comedy']
        # edge_cases_concert = ['Concert']
        edge_cases_festival = ['Festivals']
        edge_cases_knowledge = ['Literature / Science / Politics / Art', 'Workshop', 'Panel', 'Talks', 'DJ & Producer Workshops']

        entry = self.db[self.collection_name].find_one({'_id': item.get('_id')})
        tags = entry.get('tags')
        if item.get('tag') not in tags:
            tags.append(item.get('tag'))
            if item.get('tag') in edge_cases_art:
                self.db[self.collection_name].update_one({'_id': item.get('_id')}, {'$set': {'event_type': 'Art', 'tags': tags, 'last_modified': item.get('last_modified')}})
            elif item.get('tag') in edge_cases_club:
                self.db[self.collection_name].update_one({'_id': item.get('_id')}, {'$set': {'event_type': 'Club', 'tags': tags, 'last_modified': item.get('last_modified')}})
            elif item.get('tag') in edge_cases_comedy:
                self.db[self.collection_name].update_one({'_id': item.get('_id')}, {'$set': {'event_type': 'Comedy', 'tags': tags, 'last_modified': item.get('last_modified')}})
            # elif item.get('tag') in edge_cases_concert:
                # self.db[self.collection_name].update_one({'_id': item.get('_id')}, {'$set': {'event_type': 'Concert', 'tags': tags, 'last_modified': item.get('last_modified')}})
            elif item.get('tag') in edge_cases_festival:
                self.db[self.collection_name].update_one({'_id': item.get('_id')}, {'$set': {'event_type': 'Festival', 'tags': tags, 'last_modified': item.get('last_modified')}})
            elif item.get('tag') in edge_cases_knowledge:
                self.db[self.collection_name].update_one({'_id': item.get('_id')}, {'$set': {'event_type': 'Knowledge', 'tags': tags, 'last_modified': item.get('last_modified')}})
            else:
                self.db[self.collection_name].update_one({'_id': item.get('_id')}, {'$set': {'tags': tags, 'last_modified': item.get('last_modified')}})
            # self.db[self.collection_name].update_one({'_id': item.get('_id')}, {'$set': {'tags': tags, 'last_modified': item.get('last_modified')}})
            return item
        else:
            return None

class CustomImagePipeline(ImagesPipeline):
    def get_media_requests(self, item, info):
        if isinstance(item, ImageItem):
            for image_url in item["image_urls"]:
                yield scrapy.Request(image_url)
        else:
            return item

    def item_completed(self, results, item, info):
        dir_base = './img/'
        dir_dl = 'dl/'
        if isinstance(item, ImageItem):
            image_paths = [x["path"] for ok, x in results if ok]
            adapter = ItemAdapter(item)
            adapter["image_paths"] = image_paths
            for image_path in adapter["image_paths"]:
                with Image.open(dir_base + dir_dl + image_path) as img:
                    target_aspect_ratio = 1.47
                    original_width, original_height = img.size
                    original_aspect_ratio = original_width / original_height
                    if original_aspect_ratio <= target_aspect_ratio:
                        target_height = int(original_width / target_aspect_ratio)
                        height_diff = (original_height - target_height) // 2

                        left = 0
                        top = height_diff
                        right = original_width
                        bottom = original_height - height_diff
                        coordinates = (left, top, right, bottom)
                    else:
                        target_width = int(original_height / (1/target_aspect_ratio))
                        width_diff = (original_width - target_width ) // 2

                        left = width_diff
                        top = 0
                        right = original_width - width_diff
                        bottom = original_height
                        coordinates = (left, top, right, bottom)
                    new = img.crop(coordinates)
                    new.save(str(dir_base + adapter['_id'] + '.webp'), format="WEBP")
                    # os.remove(str(dir_base + dir_dl + image_path))
                    return item
        else:
            return item

import scrapy
from twisted.internet import reactor, defer
# from twisted.internet import defer
from scrapy.crawler import CrawlerRunner
from scrapy.utils.log import configure_logging
from scrapy.utils.project import get_project_settings
# from scrapy.utils.reactor import install_reactor
import importlib
import pkgutil
import pymongo
from datetime import datetime
import os
import shutil

settings = get_project_settings()
configure_logging(settings)
runner = CrawlerRunner(settings)

client = pymongo.MongoClient(settings['MONGODB_URI'])
db = client[settings['MONGODB_DATABASE']]

@defer.inlineCallbacks
def crawl():
    spiders_package = importlib.import_module("concertron.spiders")
    for importer, modname, ispkg in pkgutil.iter_modules(spiders_package.__path__):
        module = importlib.import_module(f"concertron.spiders.{modname}")
        for name in dir(module):
            obj = getattr(module, name)
            if isinstance(obj, type) and issubclass(obj, scrapy.Spider) and obj != scrapy.Spider:
                yield runner.crawl(obj)

    reactor.stop()
    db.system.update_one({'_id': 'scraper'}, {'$set': {'last_run': datetime.now()}}, upsert=True)

def clean_up():
    query = {'date': {'$lt': datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)}}

    if os.path.exists("./img/dl/full"):
        shutil.rmtree("./img/dl/full")

    for _id in db.events.find(query).distinct('_id'):
        if os.path.exists(f"./img/{_id}.webp"):
            os.remove(f"./img/{_id}.webp")
    
    db.events.delete_many(query)


if __name__ == '__main__':
    crawl()
    reactor.run()
    clean_up()

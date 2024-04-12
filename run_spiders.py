import scrapy
from twisted.internet import reactor, defer
# from twisted.internet import defer
from scrapy.crawler import CrawlerRunner
from scrapy.utils.log import configure_logging
from scrapy.utils.project import get_project_settings
from scrapy.utils.reactor import install_reactor
import importlib
import pkgutil

# install_reactor('twisted.internet.asyncioreactor.AsyncioSelectorReactor')
# asyncioreactor.install()

# from concertron.spiders import nl_melkweg, nl_013, nl_paradiso, nl_tivolivredenburg
from concertron.spiders import *

settings = get_project_settings()
configure_logging(settings)
runner = CrawlerRunner(settings)

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

crawl()
reactor.run()

import scrapy
from twisted.internet import reactor, defer
# from twisted.internet import defer
from scrapy.crawler import CrawlerRunner
from scrapy.utils.log import configure_logging
from scrapy.utils.project import get_project_settings
from scrapy.utils.reactor import install_reactor

# install_reactor('twisted.internet.asyncioreactor.AsyncioSelectorReactor')
# asyncioreactor.install()

from concertron.spiders import nl_melkweg, nl_013, nl_paradiso, nl_tivolivredenburg

settings = get_project_settings()
configure_logging(settings)
runner = CrawlerRunner(settings)

@defer.inlineCallbacks
def crawl():
    yield runner.crawl(nl_melkweg.spider)
    yield runner.crawl(nl_013_events.spider)
    yield runner.crawl(nl_013_tags.spider)
    yield runner.crawl(nl_paradiso.spider)
    yield runner.crawl(nl_tivolivredenburg.spiderEvents)
    yield runner.crawl(nl_tivolivredenburg.spiderTags)
    reactor.stop()
# d = runner.join()
# d.addBoth(lambda _: reactor.stop())

crawl()
reactor.run()

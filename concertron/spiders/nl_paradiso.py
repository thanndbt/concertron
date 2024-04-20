import scrapy
from concertron.items import ConcertronNewItem, ConcertronUpdatedItem, ConcertronTagsItem, ImageItem
import json
from datetime import datetime, timezone
from concertron.utils import does_event_exist


class spiderEvents(scrapy.Spider):
    name = "nl_paradiso_events"
    allowed_domains = ["knwxh8dmh1.execute-api.eu-central-1.amazonaws.com"]
    start_urls = ["https://knwxh8dmh1.execute-api.eu-central-1.amazonaws.com/graphql"]
    venue_id = 'nl_paradiso'

    def check_status(self, show):
        eventStatus = show.get('eventStatus')
        soldOut = show.get('soldOut')

        if eventStatus == 'canceled':
            return 'CANCELLED'
        elif eventStatus == 'postponed':
            return 'MOVED'
        elif soldOut == 'yes' or soldOut == 'yesWithWaitingList':
            return 'SOLD_OUT'
        elif soldOut == 'no':
            return 'SALE_LIVE'
        else:
            return 'UNKNOWN'

    def parse(self, response):
        data = json.loads(response.body)
        agenda = data.get('data').get('program').get('events')

        for show in agenda:
            main_data = {
                    '_id': str(self.venue_id + '-' + str(show.get('id'))),
                    'title': str(show.get('title')),
                    'subtitle': str(show.get('subtitle')) if show.get('subtitle') else '',
                    'support': str(show.get('supportAct')).split(' + ') if show.get('supportAct') else [],
                    'date': datetime.fromisoformat(show.get('startDateTime')).astimezone(timezone.utc).replace(tzinfo=None),
                    'location': str(str(show.get('location')[0].get('title')) + ', Amsterdam, NL') if show.get('location') else str('Paradiso, Amsterdam, NL'),
                    'tags': [], # Tags are not embedded in data, but maybe it is. It is not in the standard response
                    # 'status': show.get('soldOut'), # Just for reference
                    'status': self.check_status(show), # Just for reference
                    }
            main_data['lineup'] = main_data['support'] + [main_data['title']]

            event_status = does_event_exist(main_data.get('_id'))
            if event_status == 'EVENT_DOES_NOT_EXIST':
                additional_data = {
                        'event_type': 'Concert',
                        'url': str('https://paradiso.nl/en/' + show.get('uri')),
                        'venue_id': self.venue_id,
                        'last_check': datetime.now(),
                        'last_modified': datetime.now(),
                        }
                main_data.update(additional_data)
                event_item = ConcertronNewItem(**main_data)
                yield event_item

                image_data = {
                        'image_urls': [show.get('image')[1].get('desktopXL2xWebp')],
                        '_id': main_data['_id']
                }
                image_item = ImageItem(**image_data)
                yield image_item
            elif event_status == "EVENT_EXISTS" or event_status == "EVENT_UPDATE":
                event_item = ConcertronUpdatedItem(**main_data)
                yield event_item

    def start_requests(self):
        json_data = {
                'operationName': "programItemsQuery",
                'query': '''
                query programItemsQuery(
                    $site: String
                        $size: Int = 100
                        $gteStartDateTime: String
                        $lteStartDateTime: String
                        $searchAfter: [String]
                        $location: [Int]
                        $subBrand: [Int]
                        $contentCategory: [Int]
                        $highlight: Boolean = false
                        ) {
                        program(
                          site: $site
                          size: $size
                          gteStartDateTime: $gteStartDateTime
                          lteStartDateTime: $lteStartDateTime
                          searchAfter: $searchAfter
                          location: $location
                          subBrand: $subBrand
                          contentCategory: $contentCategory
                          highlight: $highlight
                        ) {
                          __typename
                          events {
                            __typename
                            id
                            uri
                            title
                            startDateTime
                            date
                            subtitle
                            sort
                            eventStatus
                            highlight
                            supportAct
                            announceSupport
                            soldOut
                            location {
                              id
                              title
                            }
                            image {
                              mobile
                              mobile2x
                              mobileWebp
                              mobile2xWebp
                              tablet
                              tablet2x
                              tabletWebp
                              tablet2xWebp
                              desktop
                              desktop2x
                              desktopWebp
                              desktop2xWebp
                              desktopL
                              desktopL2x
                              desktopLWebp
                              desktopL2xWebp
                              desktopXL
                              desktopXL2x
                              desktopXLWebp
                              desktopXL2xWebp
                              type
                            }
                          }
                        }
                        }''',
                "variables": {
                        "contentCategory": None,
                        "gteStartDateTime": datetime.now().strftime('%Y-%m-%d'),
                        "location": None,
                        "lteStartDateTime": None,
                        "searchAfter": None,
                        "site": "paradisoEnglish",
                        "size": 1000,
                        "subBrand": None
                        }
                }
        body = json.dumps(json_data)

        headers = {
                'Content-Type': 'application/json',
                }

        yield scrapy.Request(
                url='https://knwxh8dmh1.execute-api.eu-central-1.amazonaws.com/graphql',
                method='POST',
                headers=headers,
                body=body,
                callback=self.parse
                )


class spiderTags(scrapy.Spider):
    name = "nl_paradiso_tags"
    allowed_domains = ["paradiso.nl", "knwxh8dmh1.execute-api.eu-central-1.amazonaws.com"]
    start_urls = ["https://www.paradiso.nl/en"]
    venue_id = 'nl_paradiso'

    def check_tags(self, response):
        data = json.loads(response.body)
        agenda = data.get('data').get('program').get('events')

        for show in agenda:
            tag_data = {
                    '_id': str(self.venue_id + '-' + str(show.get('id'))),
                    'tag': response.meta.get('tag'),
                    'last_modified': datetime.now()
                    }
            tag_item = ConcertronTagsItem(**tag_data)
            yield tag_item

    def parse(self, response):
        script = response.xpath("//script[contains(text(), 'contentCategory_Category')]/text()").get().replace('\\"', '"')
        pattern_start = '"contentCategory":[{'
        pattern_end = '}]}}]'
        filters = json.loads(script[script.find(pattern_start)+len(pattern_start)-2:script.find(pattern_end)+2])

        for tag in filters:
            json_data = {
                    'operationName': "programItemsQuery",
                    'query': '''
                    query programItemsQuery(
                        $site: String
                            $size: Int = 100
                            $gteStartDateTime: String
                            $lteStartDateTime: String
                            $searchAfter: [String]
                            $location: [Int]
                            $subBrand: [Int]
                            $contentCategory: [Int]
                            $highlight: Boolean = false
                            ) {
                            program(
                              site: $site
                              size: $size
                              gteStartDateTime: $gteStartDateTime
                              lteStartDateTime: $lteStartDateTime
                              searchAfter: $searchAfter
                              location: $location
                              subBrand: $subBrand
                              contentCategory: $contentCategory
                              highlight: $highlight
                            ) {
                              __typename
                              events {
                                __typename
                                id
                                uri
                                title
                                startDateTime
                                date
                                subtitle
                                sort
                                eventStatus
                                highlight
                                supportAct
                                announceSupport
                                soldOut
                                location {
                                  id
                                  title
                                }
                                image {
                                  mobile
                                  mobile2x
                                  mobileWebp
                                  mobile2xWebp
                                  tablet
                                  tablet2x
                                  tabletWebp
                                  tablet2xWebp
                                  desktop
                                  desktop2x
                                  desktopWebp
                                  desktop2xWebp
                                  desktopL
                                  desktopL2x
                                  desktopLWebp
                                  desktopL2xWebp
                                  desktopXL
                                  desktopXL2x
                                  desktopXLWebp
                                  desktopXL2xWebp
                                  type
                                }
                              }
                            }
                            }''',
                    "variables": {
                            "contentCategory": [int(tag.get('id'))],
                            "gteStartDateTime": datetime.now().strftime('%Y-%m-%d'),
                            "location": None,
                            "lteStartDateTime": None,
                            "searchAfter": None,
                            "site": "paradisoEnglish",
                            "size": 1000,
                            "subBrand": None
                            }
                    }
            body = json.dumps(json_data)

            headers = {
                    'Content-Type': 'application/json',
                    }

            yield scrapy.Request(
                    url='https://knwxh8dmh1.execute-api.eu-central-1.amazonaws.com/graphql',
                    method='POST',
                    headers=headers,
                    body=body,
                    callback=self.check_tags,
                    meta={'tag': tag.get('title')}
                    )


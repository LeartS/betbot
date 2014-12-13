import requests
from io import BytesIO, StringIO
from lxml import etree

DEBUG = True

class SitesManager(object):

    def __init__(self, sites=[]):
        self.sites = sites

    def add_site(self, site):
        self.sites.push_back(site)

    def check_for_sure_bets(self, sport=None, location=None):
        for site in self.sites:
            print(site.get_league_quotes(sport, location))

class Site(object):
    url = ''
    url_params = {}

    def parse_html_for_quotes(self, parsed_html):
        if DEBUG: print('Parsing HTML for generic site')
        pass

    def get_html_tree(self, url):
        r = requests.get(url)
        html_string = BytesIO(r.text.encode('UTF-8'))
        parser = etree.HTMLParser(remove_blank_text=True, remove_comments=True,
                                  recover=True)
        html = etree.parse(html_string, parser)
        return html

    def get_league_quotes(self, sport, location):
        if DEBUG:
            print('Checking quotes for {}-{} on {}'.format(
                sport, location, self.__class__.__name__))
        try:
            sport_id = self.url_params[sport]['id']
            location_id = self.url_params[sport]['locations'][location]
        except KeyError:
            # This site does not have this league, so no quotes
            return []
        html = self.get_html_tree(
            self.url.format(sport=sport_id, location=location_id)
        )
        return self.parse_html_for_quotes(html)


class BWin(Site):
    url = 'https://m.bwin.it/#/?sport={sport}&location={location}'
    url_params = {
        'soccer': {
            'id': 4,
            'locations': {
                'poland': 22,
            },
        }
    }


class Sisal(Site):
    url = 'http://mobile.sisal.it/events_wap.t?league={sport}_{location}'
    url_params = {
        'soccer': {
            'id': 1,
            'locations': {
                'poland': 183,
            },
        }
    }

    def parse_html_for_quotes(self, html_tree):
        if DEBUG: print('Parsing HTML for Sisal')
        match_nodes = html_tree.getroot().xpath(
            '//table[@class="event-header"]//span[@class="fs15px b"]')
        quote_nodes = html_tree.getroot().xpath(
            '//span[@class="odds-convert"]')
        matches_quotes = {}
        for match, quotes in zip(
                match_nodes,
                (quote_nodes[i:i+3] for i in range(0, len(quote_nodes), 3))):
            matches_quotes[match.text] = tuple(
                float(quote.text.replace(',', '.')) for quote in quotes)
        return matches_quotes


if __name__ == '__main__':
    sites_manager = SitesManager([Sisal()])
    sites_manager.check_for_sure_bets('soccer', 'poland')

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

    def parse_response(self, reponse):
        if DEBUG: print('Parsing reponse for generic site')
        pass

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
        response = requests.get(self.url.format(sport=sport_id,
                                                location=location_id))
        return self.parse_response(response)


class BWin(Site):
    url = ('https://it-it.mobileapi.bwinlabs.com/api/iphone/v2/events/search?'
           'sportid={sport}&regionid={location}&fields=details.('
           'short_name%2Cstarts_at%2Cleague%2Cparticipants)%2Cscore_board'
           '%2Ctype%2Ceventids%2Cgames%5B0%5D.(id%2Cname%2C'
           'results.(name%2Codds))&sort=live%20desc%2Cstartsat%20asc%2Csportid'
           '%20asc%2Ceventname%20asc&content=list&page_number=1&page_size=40'
           '&partnerid=mobit2013')
    # url = 'https://m.bwin.it/#/?sport={sport}&location={location}'
    url_params = {
        'soccer': {
            'id': 4,
            'locations': {
                'poland': 22,
                'cipro': 58,
            },
        }
    }

    def parse_response(self, response):
        if DEBUG: print('Parsing quotes as JSON for BWin')
        data = response.json()
        matches_quotes = {}
        for event in data['response']['items']['events']:
            game = [g for g in event['non_live']['games'] if g['name'] == '1X2']
            try:
                game = game[0]
            except IndexError:
                continue
            matches_quotes[event['details']['short_name']] = tuple(
                result['odds'] for result in game['results'])
        return matches_quotes


class Sisal(Site):
    url = 'http://mobile.sisal.it/events_wap.t?league={sport}_{location}'
    url_params = {
        'soccer': {
            'id': 1,
            'locations': {
                'poland': 183,
                'cipro': 290,
            },
        }
    }

    def parse_response(self, response):
        if DEBUG: print('Parsing response as HTML tree for Sisal')
        data = BytesIO(response.text.encode('utf-8'))
        parser = etree.HTMLParser(remove_blank_text=True, remove_comments=True,
                                  recover=True)
        html = etree.parse(data, parser)
        match_nodes = html.getroot().xpath(
            '//table[@class="event-header"]//span[@class="fs15px b"]')
        quote_nodes = html.getroot().xpath(
            '//span[@class="odds-convert"]')
        matches_quotes = {}
        for match, quotes in zip(
                match_nodes,
                (quote_nodes[i:i+3] for i in range(0, len(quote_nodes), 3))):
            matches_quotes[match.text] = tuple(
                float(quote.text.replace(',', '.')) for quote in quotes)
        return matches_quotes


if __name__ == '__main__':
    sites_manager = SitesManager([Sisal(), BWin()])
    sites_manager.check_for_sure_bets('soccer', 'cipro')

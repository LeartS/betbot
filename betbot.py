import requests
import logging
import argparse
from io import BytesIO, StringIO
from lxml import etree


logger = logging.getLogger('betbot')
logging.basicConfig(level=logging.ERROR)


class Event(object):
    """
    An event is a day of a league of a sport.
    An event can have multiple matches.
    """

    def __init__(self, sport, league):
        self.sport = sport
        self.league = league
        self.quotes = {}

    def make_id(self, teams):
        return ' VS '.join(t.lower() for t in teams)

    def get_or_create_match(self, teams, quotes):
        """
        Associate this match with one of the saved one from this event,
        by looking at similarities of teams, quotes, and possibly other factors
        in the future (like start time).
        If this is a new match (i.e. we can't find a similar one), create it.
        """

        def quote_distance(quote_a, quote_b):
            return sum(abs(1/q_a - 1/q_b) for q_a, q_b in zip(quote_a, quote_b))

        for match, site_quotes in self.quotes.items():
            for site, s_quotes in site_quotes.items():
                if quote_distance(s_quotes, quotes) < 0.05:
                    return match
        match_id = self.make_id(teams)
        self.quotes[match_id] = {}
        return match_id

    def add_site_quotes(self, site_name, quotes):
        for match_teams, match_quotes in quotes.items():
            match_id = self.get_or_create_match(match_teams, match_quotes)
            self.quotes[match_id][site_name] = match_quotes


class SitesManager(object):

    def __init__(self, sites=[]):
        self.leagues = {}
        self.sites = []
        for site in sites:
            self.add_site(site)
        logger.info('SitesManager initialized')
        logger.info('Sites registered: {}'.format(
            ', '.join([s.__class__.__name__ for s in self.sites])))
        logger.info('Leagues registered: {}'.format(self.leagues))

    def add_site(self, site):
        # update the global leagues set to include this site leagues
        for sport in site.url_params:
            if not sport in self.leagues:
                self.leagues[sport] = set()
            self.leagues[sport].update(
                set(site.url_params[sport]['leagues'].keys()))
        # add the site
        self.sites.append(site)

    def check_for_sure_bets(self, sports=None):
        if sports is None:
            sports = self.leagues.keys()
        for sport in sports:
            for league in self.leagues[sport]:
                event = Event(sport, league)
                for site in self.sites:
                    site_league_quotes = site.get_league_quotes(sport, league)
                    if site_league_quotes:
                        event.add_site_quotes(site.__class__.__name__,
                                              site_league_quotes)
                print(event.quotes)


class Site(object):
    url = ''
    url_params = {}

    def parse_response(self, reponse):
        logger.debug('Parsing reponse for generic site')
        pass

    def get_league_quotes(self, sport, league):
        logger.info('Checking quotes for {}-{} on {}'.format(
            sport, league, self.__class__.__name__))
        try:
            sport_id = self.url_params[sport]['id']
            league_id = self.url_params[sport]['leagues'][league]
        except KeyError:
            # This site does not have this league, so no quotes
            return []
        headers = {
            'User-Agent': ('Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:34.0)'
                           'Gecko/20100101 Firefox/34.0')
        }
        response = requests.get(self.url.format(sport=sport_id,
                                                league=league_id),
                                headers=headers)
        logger.debug(self.url.format(sport=sport_id, league=league_id))
        return self.parse_response(response)


class BWin(Site):
    url = ('https://it-it.mobileapi.bwinlabs.com/api/iphone/v2/events/search?'
           'sportid={sport}&leagueid={league}&fields=details.('
           'short_name%2Cstarts_at%2Cleague%2Cparticipants)%2Cscore_board'
           '%2Ctype%2Ceventids%2Cgames%5B0%5D.(id%2Cname%2C'
           'results.(name%2Codds))&sort=live%20desc%2Cstartsat%20asc%2Csportid'
           '%20asc%2Ceventname%20asc&content=list&page_number=1&page_size=40'
           '&partnerid=mobit2013')
    url_params = {
        'soccer': {
            'id': 4,
            'leagues': {
                'poland-ekstraklasa': 21543,
                'cipro-1-division': 39123,
                'israel-premier-league': 24835,
            },
        }
    }

    def parse_response(self, response):
        logger.debug('Parsing quotes as JSON for BWin')
        data = response.json()
        matches_quotes = {}
        for event in data['response']['items']['events']:
            game = [g for g in event['non_live']['games'] if g['name'] == '1X2']
            try:
                game = game[0]
            except IndexError:
                continue
            teams = tuple(event['details']['short_name'].split(' - '))
            matches_quotes[teams] = tuple(
                result['odds'] for result in game['results'])
        return matches_quotes


class Sisal(Site):
    url = 'http://mobile.sisal.it/events_wap.t?league={sport}_{league}'
    url_params = {
        'soccer': {
            'id': 1,
            'leagues': {
                'poland-ekstraklasa': 183,
                'cipro-1-division': 290,
                'israel-premier-league': 215,
            },
        }
    }

    def parse_response(self, response):
        logger.debug('Parsing response as HTML tree for Sisal')
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
            matches_quotes[tuple(match.text.split(' - '))] = tuple(
                float(quote.text.replace(',', '.')) for quote in quotes)
        return matches_quotes


class Bet365(Site):
    url = ('https://mobile.bet365.it/sport/coupon/?ptid={sport}&key='
           '1-1-13-{league}-2-17-0-0-1-0-0-4100-0-0-1-0-0-0-0-0-0')
    url_params = {
        'soccer': {
            'id': 4100,
            'leagues': {
                'poland-ekstraklasa': '26304997',
                'cipro-1-division': '26404811',
                'israel-premier-league': '26405613',
            },
        },
    }

    def parse_response(self, response):
        logger.debug('Parsing response as HTML tree for Bet365')
        data = BytesIO(response.text.encode('utf-8'))
        parser = etree.HTMLParser(remove_blank_text=True, remove_comments=True,
                                  recover=True)
        html = etree.parse(data, parser)
        match_nodes = html.getroot().xpath(
            '//th[@class="DarkMidGrey"][@colspan="2"]')
        quote_nodes = html.getroot().xpath(
            '//td[contains(@class, "nFTRr2")]')
        matches_quotes = {}
        for match, quotes in zip(
                match_nodes,
                (quote_nodes[i:i+3] for i in range(0, len(quote_nodes), 3))):
            matches_quotes[tuple(match.text.split(' v '))] = tuple(
                float(quote.text) for quote in quotes)
        return matches_quotes

if __name__ == '__main__':
    # App config
    log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    parser = argparse.ArgumentParser(description='Find sure bets.')
    parser.add_argument('-l', '--log-level', default='WARNING',
                        choices=log_levels, dest='log_level',
                        type=lambda x: x.upper())
    args = parser.parse_args()
    logger.setLevel(getattr(logging, args.log_level))

    sites_manager = SitesManager([Sisal(), BWin(), Bet365()])
    sites_manager.check_for_sure_bets()

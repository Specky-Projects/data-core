from app.modules.sports_odds.parsers.generic_odds_parser import GenericOddsParser


class NbaOddsParser(GenericOddsParser):
    default_sport = "basketball"
    default_league = "NBA"
    default_country = "US"

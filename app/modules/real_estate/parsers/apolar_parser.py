from app.modules.real_estate.parsers.generic_parser import GenericRealEstateParser


class ApolarParser(GenericRealEstateParser):
    listing_path_markers = GenericRealEstateParser.listing_path_markers + (
        "apolar",
        "comprar",
        "locar",
    )


from app.modules.real_estate.models import RealEstateListing


def price_per_m2(listing: RealEstateListing, price: float | None) -> float | None:
    if price is None or not listing.area_m2:
        return None
    return float(price) / listing.area_m2


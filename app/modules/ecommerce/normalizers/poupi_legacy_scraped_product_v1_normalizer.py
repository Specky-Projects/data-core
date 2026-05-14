from app.modules.ecommerce.normalizers.product_normalizer import EcommerceProductNormalizer


class PoupiLegacyScrapedProductV1Normalizer(EcommerceProductNormalizer):
    normalizer_name = "poupi_legacy_scraped_product_v1_normalizer"
    normalizer_version = "1.0.0"
    supported_raw_schema_name = "scrapedProduct"
    supported_raw_schema_version = "1.0.0"

from app.modules.crypto.normalizers.snapshot_normalizer import CryptoSnapshotNormalizer


class TradingCandleNormalizer(CryptoSnapshotNormalizer):
    module = "trading"
    normalizer_name = "trading_candle_normalizer"
    normalizer_version = "1.0.0"

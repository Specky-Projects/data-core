from app.normalization.services import BaseNormalizer

NormalizerType = type[BaseNormalizer]


class NormalizerRegistry:
    def __init__(self) -> None:
        self._normalizers: dict[str, list[NormalizerType]] = {}

    def register(self, module: str, normalizer_type: NormalizerType) -> None:
        registered = self._normalizers.setdefault(module, [])
        if normalizer_type not in registered:
            registered.append(normalizer_type)

    def get(self, module: str) -> NormalizerType | None:
        normalizers = self._normalizers.get(module) or []
        return normalizers[0] if normalizers else None

    def get_for_raw(
        self,
        module: str,
        *,
        source_name: str | None = None,
        raw_schema_name: str | None = None,
        raw_schema_version: str | None = None,
    ) -> NormalizerType | None:
        for normalizer_type in self._normalizers.get(module, []):
            if normalizer_type.supports_raw(
                source_name=source_name,
                raw_schema_name=raw_schema_name,
                raw_schema_version=raw_schema_version,
            ):
                return normalizer_type
        return self.get(module)

    def modules(self) -> list[str]:
        return sorted(self._normalizers.keys())

    def all(self) -> dict[str, list[NormalizerType]]:
        return {module: list(normalizers) for module, normalizers in self._normalizers.items()}


normalizer_registry = NormalizerRegistry()

from app.analytics.services import BaseAnalyticsProcessor

AnalyticsProcessorType = type[BaseAnalyticsProcessor]


class AnalyticsRegistry:
    def __init__(self) -> None:
        self._processors: dict[str, AnalyticsProcessorType] = {}

    def register(self, module: str, processor_type: AnalyticsProcessorType) -> None:
        self._processors[module] = processor_type

    def get(self, module: str) -> AnalyticsProcessorType | None:
        return self._processors.get(module)

    def modules(self) -> list[str]:
        return sorted(self._processors.keys())

    def all(self) -> dict[str, AnalyticsProcessorType]:
        return dict(self._processors)


analytics_registry = AnalyticsRegistry()

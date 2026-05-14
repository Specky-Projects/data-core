from dataclasses import dataclass


@dataclass(frozen=True)
class LineMovementSummary:
    opening_odd: float | None
    latest_odd: float | None
    movement: float | None


def calculate_line_movement(opening_odd: float | None, latest_odd: float | None) -> LineMovementSummary:
    movement = latest_odd - opening_odd if opening_odd is not None and latest_odd is not None else None
    return LineMovementSummary(opening_odd=opening_odd, latest_odd=latest_odd, movement=movement)

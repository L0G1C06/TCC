"""Intermediate metrics computed from raw _ColumnStats accumulators."""

from dataclasses import dataclass



@dataclass
class TruncationDiagnostics:
    last_digit_freq: dict[str, float]
    digit_spike: bool
    round_value_ratio: float
    threshold_bunching: dict[str, int]


@dataclass
class ColumnMetrics:
    """
    Valores derivados dos contadores brutos de _ColumnStats.
    Pode ser reconstruído tanto de um _ColumnStats quanto
    de um _eligibility.json (para o ModuleAggregator).
    """
    col: str
    total_count: int
    null_count: int
    zero_count: int
    valid_count: int
    null_pct: float
    zero_pct: float
    min_val: float | None
    max_val: float | None
    orders_of_magnitude: float
    is_sequential_id: bool
    has_artificial_truncation: bool
    truncation: TruncationDiagnostics
    first_digit_counts: dict[str, int]
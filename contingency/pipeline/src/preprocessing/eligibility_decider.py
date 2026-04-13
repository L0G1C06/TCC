"""Eligibility decision logic — reusable by _ColumnStats and ModuleAggregator."""

from dataclasses import dataclass, field

from src.core.column_metrics import ColumnMetrics

MIN_VALID_COUNT = 1_000
MIN_ORDERS_OF_MAGNITUDE = 2


@dataclass
class EligibilityResult:
    eligible: bool
    reasons: list[str] = field(default_factory=list)


class BenfordEligibilityDecider:
    """
    Decide se uma coluna (ou agregado de colunas) é elegível
    para análise de Benford. Stateless — pode ser instanciado uma vez e
    reaproveitado para N colunas ou N módulos.
    """

    def decide(self, metrics: ColumnMetrics) -> EligibilityResult:
        reasons: list[str] = []

        if metrics.is_sequential_id:
            reasons.append("Sequential ID detected")

        if metrics.valid_count < MIN_VALID_COUNT:
            reasons.append(
                f"Insufficient sample: {metrics.valid_count:,} valid values "
                f"(need >= {MIN_VALID_COUNT:,})"
            )

        if metrics.orders_of_magnitude < MIN_ORDERS_OF_MAGNITUDE:
            reasons.append(
                f"Insufficient spread: {metrics.orders_of_magnitude} "
                f"order(s) of magnitude (need >= {MIN_ORDERS_OF_MAGNITUDE})"
            )

        if metrics.has_artificial_truncation:
            reasons.append("Artificial truncation detected")

        if metrics.null_pct > 50:
            reasons.append(f"Excessive nulls: {metrics.null_pct:.1f}%")

        if metrics.zero_pct > 30:
            reasons.append(f"Excessive zeros: {metrics.zero_pct:.1f}%")

        return EligibilityResult(eligible=len(reasons) == 0, reasons=reasons)
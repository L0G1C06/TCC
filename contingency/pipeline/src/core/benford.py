"""Benford's Law eligibility analysis — streaming, O(1) memory per column."""

from typing import Any

import numpy as np
import pandas as pd

from src.core.column_metrics import ColumnMetrics, TruncationDiagnostics
from src.preprocessing.eligibility_decider import BenfordEligibilityDecider

from src.preprocessing.numeric_cleaner import clean_numeric_column
from src.preprocessing.id_detector import is_sequential_id

_DECIDER = BenfordEligibilityDecider()


class _ColumnStats:
    """Accumulates only what's needed for eligibility — never stores raw values."""

    def __init__(self, thresholds: list[float] | None = None):
        self.total: int = 0
        self.null_count: int = 0
        self.zero_count: int = 0
        self.valid_count: int = 0
        self.min_val: float = float("inf")
        self.max_val: float = float("-inf")
        self.last_digit_counts: np.ndarray = np.zeros(10, dtype=np.int64)
        # Índices 1–9 usados; índice 0 reservado / ignorado intencionalmente.
        self.first_digit_counts: np.ndarray = np.zeros(10, dtype=np.int64)
        # Par de dois dígitos: chaves "10"–"99", 90 entradas.
        self.two_digit_counts: dict[str, int] = {str(i): 0 for i in range(10, 100)}
        self.round_count: int = 0
        self.id_sample: pd.Series | None = None
        self.thresholds: list[float] = thresholds or []
        self.threshold_counts: dict[str, int] = {str(t): 0 for t in self.thresholds}

    # ── Acumulação (streaming) ────────────────────────────────────────────────

    def update(self, chunk: pd.Series) -> None:
        cleaned = clean_numeric_column(chunk)
        self.total += len(cleaned)
        self.null_count += int(cleaned.isna().sum())

        valid = cleaned[cleaned.notna() & (cleaned != 0)]
        self.zero_count += int((cleaned == 0).sum())

        if valid.empty:
            return

        self.valid_count += len(valid)
        valid_abs = valid.abs()

        self.min_val = min(self.min_val, float(valid_abs.min()))
        self.max_val = max(self.max_val, float(valid_abs.max()))

        # ── Primeiro dígito ───────────────────────────────────────────────────
        log_data = np.log10(valid_abs)
        first_digits = np.floor(10 ** (log_data - np.floor(log_data))).astype(np.int64)
        for d, count in first_digits.value_counts().items():
            if 1 <= d <= 9:
                self.first_digit_counts[d] += count

        # ── Dois primeiros dígitos (Benford 2d) ───────────────────────────────
        # Escala cada valor para o intervalo [10, 100) e trunca para obter
        # o par d1d2. np.clip cobre instabilidade de ponto flutuante nos
        # extremos de potência de 10 (ex: log10(1000.0) → 2.9999…).
        exp    = np.floor(log_data.to_numpy()).astype(int)
        scaled = valid_abs.to_numpy() / np.power(10.0, (exp - 1).astype(float))
        pairs  = np.clip(np.floor(scaled).astype(int), 10, 99)
        unique_pairs, pair_counts = np.unique(pairs, return_counts=True)
        for d, cnt in zip(unique_pairs, pair_counts):
            self.two_digit_counts[str(int(d))] += int(cnt)

        # ── Último dígito ─────────────────────────────────────────────────────
        int_part = valid_abs.astype(np.int64)
        for d, count in (int_part % 10).value_counts().items():
            if 0 <= d <= 9:
                self.last_digit_counts[d] += count

        self.round_count += int((int_part % 100 == 0).sum())

        if self.id_sample is None or len(self.id_sample) < 1_000:
            sample_chunk = chunk.dropna().iloc[:200]
            self.id_sample = (
                sample_chunk if self.id_sample is None
                else pd.concat([self.id_sample, sample_chunk]).iloc[:1_000]
            )

        for t in self.thresholds:
            tol = t * 0.01
            self.threshold_counts[str(t)] += int(
                ((valid >= t - tol) & (valid <= t + tol)).sum()
            )

    # ── Derivação de métricas (puro cálculo, sem decisão) ────────────────────

    def to_metrics(self, col: str, skip_truncation_check: bool = False) -> ColumnMetrics:
        """
        Converte os contadores brutos em ColumnMetrics.
        Não decide elegibilidade — só computa valores derivados.
        """
        null_pct = self.null_count / self.total * 100 if self.total > 0 else 0.0
        zero_pct = self.zero_count / self.total * 100 if self.total > 0 else 0.0

        has_range = (
            self.min_val < float("inf")
            and self.max_val > float("-inf")
            and self.min_val > 0
        )
        orders = (
            round(np.log10(self.max_val) - np.log10(self.min_val), 2)
            if has_range else 0.0
        )

        total_last = self.last_digit_counts.sum()
        last_freq = (
            self.last_digit_counts / total_last if total_last > 0
            else np.zeros(10)
        )
        digit_spike = bool(last_freq[0] > 0.25 or last_freq[5] > 0.20)
        round_ratio = self.round_count / self.valid_count if self.valid_count > 0 else 0.0
        has_truncation = (
            False if skip_truncation_check
            else (digit_spike and round_ratio > 0.30)
        )

        seq_id = is_sequential_id(self.id_sample) if self.id_sample is not None else False

        return ColumnMetrics(
            col=col,
            total_count=self.total,
            null_count=self.null_count,
            zero_count=self.zero_count,
            valid_count=self.valid_count,
            null_pct=round(null_pct, 2),
            zero_pct=round(zero_pct, 2),
            min_val=self.min_val if has_range else None,
            max_val=self.max_val if has_range else None,
            orders_of_magnitude=orders,
            is_sequential_id=seq_id,
            has_artificial_truncation=has_truncation,
            truncation=TruncationDiagnostics(
                last_digit_freq={str(i): round(float(last_freq[i]), 4) for i in range(10)},
                digit_spike=digit_spike,
                round_value_ratio=round(round_ratio, 4),
                threshold_bunching=self.threshold_counts,
            ),
            first_digit_counts={str(i): int(self.first_digit_counts[i]) for i in range(1, 10)},
        )

    # ── Relatório final (só formatação) ──────────────────────────────────────

    def to_report(self, col: str, skip_truncation_check: bool = False) -> dict[str, Any]:
        """
        Retorna o dict JSON-serializável para _eligibility.json.
        Delega cálculo ao to_metrics() e decisão ao BenfordEligibilityDecider.
        """
        metrics = self.to_metrics(col, skip_truncation_check)
        result = _DECIDER.decide(metrics)

        return {
            "found": True,
            "total_count": metrics.total_count,
            "null_count": metrics.null_count,
            "zero_count": metrics.zero_count,
            "null_percentage": metrics.null_pct,
            "zero_percentage": metrics.zero_pct,
            "valid_count": metrics.valid_count,
            "min_value": metrics.min_val,
            "max_value": metrics.max_val,
            "orders_of_magnitude": metrics.orders_of_magnitude,
            "is_sequential_id": metrics.is_sequential_id,
            "has_artificial_truncation": metrics.has_artificial_truncation,
            "truncation_diagnostics": {
                "last_digit_counts": {
                    str(i): int(self.last_digit_counts[i]) for i in range(10)
                },
                "round_count": self.round_count,
                "last_digit_freq": metrics.truncation.last_digit_freq,
                "digit_spike": metrics.truncation.digit_spike,
                "round_value_ratio": metrics.truncation.round_value_ratio,
                "threshold_bunching": metrics.truncation.threshold_bunching,
            },
            "eligible": result.eligible,
            "reasons": result.reasons,
            "first_digit_counts": metrics.first_digit_counts,
            "two_digit_counts": self.two_digit_counts,
        }
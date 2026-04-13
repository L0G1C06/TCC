"""Module-level Benford eligibility aggregation from partition _eligibility.json files."""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import boto3
import numpy as np

from src.core.column_metrics import ColumnMetrics, TruncationDiagnostics
from src.preprocessing.eligibility_decider import BenfordEligibilityDecider
from src.core.module_config import ModuleConfig

logger = logging.getLogger(__name__)

_DECIDER = BenfordEligibilityDecider()
_PARTITION_METADATA_FILE = "_eligibility.json"
_MODULE_REPORT_FILE = "_MODULE_ELIGIBILITY.json"


# ── Acumulador por coluna ─────────────────────────────────────────────────────

@dataclass
class _ColAccumulator:
    """
    Acumula contadores brutos de N partições para uma única coluna.
    Espelha _ColumnStats, mas opera sobre dicts (lidos do JSON)
    em vez de pd.Series (lidos do Parquet).
    """
    total_count: int = 0
    null_count: int = 0
    zero_count: int = 0
    valid_count: int = 0
    round_count: int = 0
    min_val: float = float("inf")
    max_val: float = float("-inf")
    first_digit_counts: dict[str, int] = field(
        default_factory=lambda: {str(i): 0 for i in range(1, 10)}
    )
    two_digit_counts: dict[str, int] = field(
        default_factory=lambda: {str(i): 0 for i in range(10, 100)}
    )
    last_digit_counts: dict[str, int] = field(
        default_factory=lambda: {str(i): 0 for i in range(10)}
    )
    threshold_bunching: dict[str, int] = field(default_factory=dict)
    _seq_id_votes: int = 0
    _partition_count: int = 0

    def ingest(self, col_report: dict[str, Any]) -> None:
        """
        Incorpora o relatório de uma partição ao acumulador.
        Silenciosamente ignora chaves ausentes (partições antigas
        sem last_digit_counts brutos se tornam neutras na agregação).
        """
        self.total_count += col_report.get("total_count", 0)
        self.null_count += col_report.get("null_count", 0)
        self.zero_count += col_report.get("zero_count", 0)
        self.valid_count += col_report.get("valid_count", 0)
        self._partition_count += 1

        if col_report.get("is_sequential_id", False):
            self._seq_id_votes += 1

        min_v = col_report.get("min_value")
        max_v = col_report.get("max_value")
        if min_v is not None and min_v > 0:
            self.min_val = min(self.min_val, float(min_v))
        if max_v is not None:
            self.max_val = max(self.max_val, float(max_v))

        for d, count in col_report.get("first_digit_counts", {}).items():
            self.first_digit_counts[d] = self.first_digit_counts.get(d, 0) + int(count)
        for d, count in col_report.get("two_digit_counts", {}).items():
            self.two_digit_counts[d] = self.two_digit_counts.get(d, 0) + int(count)

        trunc = col_report.get("truncation_diagnostics", {})
        for d, count in trunc.get("last_digit_counts", {}).items():
            self.last_digit_counts[d] = self.last_digit_counts.get(d, 0) + int(count)
        self.round_count += int(trunc.get("round_count", 0))
        for t, count in trunc.get("threshold_bunching", {}).items():
            self.threshold_bunching[t] = self.threshold_bunching.get(t, 0) + int(count)

    def to_metrics(self, col: str, skip_truncation_check: bool = False) -> ColumnMetrics:
        """
        Reconstrói ColumnMetrics a partir dos contadores somados.
        Mesma lógica de _ColumnStats.to_metrics() — sem acesso ao S3.
        """
        null_pct = self.null_count / self.total_count * 100 if self.total_count > 0 else 0.0
        zero_pct = self.zero_count / self.total_count * 100 if self.total_count > 0 else 0.0

        has_range = (
                self.min_val < float("inf")
                and self.max_val > float("-inf")
                and self.min_val > 0
        )
        orders = (
            round(np.log10(self.max_val) - np.log10(self.min_val), 2)
            if has_range else 0.0
        )

        last_arr = np.array(
            [self.last_digit_counts.get(str(i), 0) for i in range(10)],
            dtype=np.float64,
        )
        total_last = last_arr.sum()
        last_freq = last_arr / total_last if total_last > 0 else np.zeros(10)
        digit_spike = bool(last_freq[0] > 0.25 or last_freq[5] > 0.20)
        round_ratio = self.round_count / self.valid_count if self.valid_count > 0 else 0.0
        has_truncation = (
            False if skip_truncation_check
            else (digit_spike and round_ratio > 0.30)
        )

        is_id = (
            self._seq_id_votes > self._partition_count / 2
            if self._partition_count > 0 else False
        )

        return ColumnMetrics(
            col=col,
            total_count=self.total_count,
            null_count=self.null_count,
            zero_count=self.zero_count,
            valid_count=self.valid_count,
            null_pct=round(null_pct, 2),
            zero_pct=round(zero_pct, 2),
            min_val=self.min_val if has_range else None,
            max_val=self.max_val if has_range else None,
            orders_of_magnitude=orders,
            is_sequential_id=is_id,
            has_artificial_truncation=has_truncation,
            truncation=TruncationDiagnostics(
                last_digit_freq={str(i): round(float(last_freq[i]), 4) for i in range(10)},
                digit_spike=digit_spike,
                round_value_ratio=round(round_ratio, 4),
                threshold_bunching=self.threshold_bunching,
            ),
            first_digit_counts={
                str(i): self.first_digit_counts.get(str(i), 0) for i in range(1, 10)
            },
        )


# ── Agregador principal ───────────────────────────────────────────────────────

class ModuleAggregator:
    """
    Coleta todos os _eligibility.json de um módulo S3, soma os contadores
    e decide se o módulo inteiro é elegível para análise de Benford.

    Não re-lê Parquet. Custo: apenas leituras de JSONs pequenos (~2 KB cada).
    """

    def __init__(self, bucket: str | None = None):
        import os
        self._bucket = bucket or os.environ["RUMOLOG_S3_BUCKET"]
        self._s3 = boto3.client("s3")

    def aggregate(
            self,
            module_s3_path: str,
            config: ModuleConfig,
    ) -> dict[str, Any]:
        """
        Agrega todos os _eligibility.json do módulo e salva
        _MODULE_ELIGIBILITY.json na raiz do caminho informado.
        """
        prefix = module_s3_path.rstrip("/") + "/"
        logger.info("ModuleAggregator: scanning s3://%s/%s", self._bucket, prefix)

        eligibility_keys = self._list_eligibility_keys(prefix)
        if not eligibility_keys:
            raise ValueError(f"No {_PARTITION_METADATA_FILE} found under {prefix}")

        logger.info("Found %d partition metadata files", len(eligibility_keys))

        accumulators: dict[str, _ColAccumulator] = {
            col: _ColAccumulator() for col in config.numeric_columns
        }
        skipped = 0

        for key in eligibility_keys:
            try:
                partition_report = self._read_json(key)
            except Exception as exc:
                logger.warning("Skipping %s — read error: %s", key, exc)
                skipped += 1
                continue

            col_reports: dict[str, Any] = partition_report.get("columns", {})
            for col in config.numeric_columns:
                col_report = col_reports.get(col)
                if col_report and col_report.get("found", False):
                    accumulators[col].ingest(col_report)

        # ── Decisão por coluna ────────────────────────────────────────────────
        column_reports: dict[str, Any] = {}
        for col, acc in accumulators.items():
            if acc._partition_count == 0:
                column_reports[col] = {
                    "found": False,
                    "eligible": False,
                    "reasons": ["Column not found in any partition"],
                }
                continue

            metrics = acc.to_metrics(col, config.skip_truncation_check)
            result = _DECIDER.decide(metrics)
            # ↓ acc passado explicitamente para preservar os contadores brutos
            column_reports[col] = _format_column_report(metrics, result, acc)

        module_report = _build_module_report(
            module_s3_path=module_s3_path,
            column_reports=column_reports,
            numeric_columns=config.numeric_columns,
            partitions_found=len(eligibility_keys),
            partitions_skipped=skipped,
        )

        output_key = prefix + _MODULE_REPORT_FILE
        self._write_json(output_key, module_report)
        logger.info(
            "Module report saved → s3://%s/%s | decision: %s",
            self._bucket, output_key, module_report["decision"],
        )

        return module_report

    # ── S3 helpers ────────────────────────────────────────────────────────────

    def _list_eligibility_keys(self, prefix: str) -> list[str]:
        keys: list[str] = []
        paginator = self._s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.endswith(_PARTITION_METADATA_FILE) and _MODULE_REPORT_FILE not in key:
                    keys.append(key)
        return keys

    def _read_json(self, key: str) -> dict[str, Any]:
        response = self._s3.get_object(Bucket=self._bucket, Key=key)
        return json.loads(response["Body"].read().decode("utf-8"))

    def _write_json(self, key: str, data: dict[str, Any]) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self._s3.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=body,
            ContentType="application/json",
        )


# ── Formatação de relatório ───────────────────────────────────────────────────

def _format_column_report(
        metrics: ColumnMetrics,
        result,
        acc: _ColAccumulator,
) -> dict[str, Any]:
    """
    Serializa ColumnMetrics + EligibilityResult para o JSON de módulo.

    Os contadores brutos de last_digit_counts são escritos diretamente
    do acumulador — não das frequências derivadas — para que o M2
    possa recalcular χ² com o n real sem perda de informação.
    """
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
            # contadores brutos — obrigatórios para χ² no M2
            "last_digit_counts": {
                str(i): acc.last_digit_counts.get(str(i), 0) for i in range(10)
            },
            "round_count": acc.round_count,
            # derivados — usados pelo dashboard e pelo decider
            "last_digit_freq": metrics.truncation.last_digit_freq,
            "digit_spike": metrics.truncation.digit_spike,
            "round_value_ratio": metrics.truncation.round_value_ratio,
            "threshold_bunching": metrics.truncation.threshold_bunching,
        },
        "eligible": result.eligible,
        "reasons": result.reasons,
        "first_digit_counts": metrics.first_digit_counts,
        "two_digit_counts": {
            str(i): acc.two_digit_counts.get(str(i), 0) for i in range(10, 100)
        },
    }


def _build_module_report(
        module_s3_path: str,
        column_reports: dict[str, Any],
        numeric_columns: list[str],
        partitions_found: int,
        partitions_skipped: int,
) -> dict[str, Any]:
    """Monta o dict final _MODULE_ELIGIBILITY.json."""
    eligible_cols = [c for c, r in column_reports.items() if r.get("eligible")]
    ineligible_cols = [c for c, r in column_reports.items()
                       if not r.get("eligible") and r.get("found", False)]
    missing_cols = [c for c, r in column_reports.items() if not r.get("found", False)]

    all_reasons = [
        f"[{col}] {reason}"
        for col, report in column_reports.items()
        for reason in report.get("reasons", [])
    ]

    n_eligible = len(eligible_cols)
    if n_eligible == len(numeric_columns):
        decision = "eligible"
    elif n_eligible > 0:
        decision = "eligible_with_reservation"
    else:
        decision = "ineligible"

    total_rows = max(
        (r.get("total_count", 0) for r in column_reports.values() if r.get("found")),
        default=0,
    )

    return {
        "module_path": module_s3_path,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "partitions_analyzed": partitions_found - partitions_skipped,
        "partitions_skipped": partitions_skipped,
        "eligible": n_eligible > 0,
        "decision": decision,
        "reasons": all_reasons,
        "columns": column_reports,
        "summary": {
            "total_rows": total_rows,
            "total_columns": len(numeric_columns),
            "eligible_columns": n_eligible,
            "ineligible_columns": len(ineligible_cols),
            "missing_columns": len(missing_cols),
            "eligible_list": eligible_cols,
            "ineligible_list": ineligible_cols,
            "missing_list": missing_cols,
        },
    }

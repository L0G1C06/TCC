"""Partition discovery and processing utilities."""

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd

from src.core.module_config import ModuleConfig
from src.io.data_loader import (
    PartitionReadError,
    iter_partition_chunks,
    partition_prefix,
)
from src.io.metadata_writer import write_eligibility_metadata
from src.io.reader.s3_reader import list_partition_prefixes
from src.preprocessing.granularity_resolver import resolve_granularity

logger = logging.getLogger(__name__)


def find_partitions(
    module_path: str | Path,
    *,
    list_fn: Callable | None = None,          # ← novo, opcional
) -> list[str]:
    """
    Retorna lista de prefixos de partição.
    `list_fn(module_path) → list[str]` substitui a lógica S3 quando fornecido.
    """
    if list_fn is not None:
        return list_fn(module_path)
    prefix = partition_prefix(module_path)
    return list(list_partition_prefixes(prefix).keys())


def process_partition(
    partition_path: str,
    config: ModuleConfig,
    chunk_size: int = 100_000,
    delete_corrupted: bool = True,
    use_recovery: bool = True,
    show_progress: bool = True,
    *,
    chunk_iter_fn: Callable = iter_partition_chunks,    # ← novo, opcional
    write_meta_fn: Callable = write_eligibility_metadata,  # ← novo, opcional
) -> dict[str, Any]:
    tag = partition_path.rstrip("/").split("/")[-1]
    print(f"[{tag}] Processing: {partition_path}")

    from src.core.benford import _ColumnStats
    stats: dict[str, _ColumnStats] = {col: _ColumnStats() for col in config.numeric_columns}
    total_rows = 0

    try:
        for chunk in chunk_iter_fn(           # ← era iter_partition_chunks hardcoded
            partition_path, config.numeric_columns, chunk_size,
            delete_corrupted=delete_corrupted,
            use_recovery=use_recovery,
            show_progress=show_progress,
        ):
            total_rows += len(chunk)
            for col in config.numeric_columns:
                if col in chunk.columns:
                    stats[col].update(chunk[col])

    except PartitionReadError as e:
        return {
            "eligible": False,
            "decision": "error",
            "error": str(e),
            "error_type": "all_files_corrupted",
        }

    if total_rows == 0:
        raise ValueError(f"No data loaded from {partition_path}")

    column_reports: dict[str, Any] = {}
    for col in config.numeric_columns:
        column_reports[col] = stats[col].to_report(col, config.skip_truncation_check)

    eligible_cols   = [c for c, r in column_reports.items() if r["eligible"]]
    ineligible_cols = [c for c, r in column_reports.items() if not r["eligible"] and r.get("found", True)]
    missing_cols    = [c for c, r in column_reports.items() if not r.get("found", True)]

    all_reasons = [
        f"[{col}] {reason}"
        for col, report in column_reports.items()
        for reason in report.get("reasons", [])
    ]

    n_eligible = len(eligible_cols)
    if n_eligible == len(config.numeric_columns):
        decision = "eligible"
    elif n_eligible > 0:
        decision = "eligible_with_reservation"
    else:
        decision = "ineligible"

    eligibility = {
        "eligible": n_eligible > 0,
        "decision": decision,
        "reasons": all_reasons,
        "columns": column_reports,
        "summary": {
            "total_rows": total_rows,
            "total_columns": len(config.numeric_columns),
            "eligible_columns": n_eligible,
            "ineligible_columns": len(ineligible_cols),
            "missing_columns": len(missing_cols),
            "eligible_list": eligible_cols,
            "ineligible_list": ineligible_cols,
            "missing_list": missing_cols,
        },
        "granularity": resolve_granularity(
            total_rows=total_rows,
            partition_path=partition_path,
            min_threshold=1000,
        ),
    }

    del stats

    metadata_path = write_meta_fn(partition_path, eligibility)  # ← era hardcoded
    print(f"[{tag}] Decision: {eligibility['decision']} | {metadata_path}")
    return eligibility
"""
Executa M1 + M2 inteiramente em memória sobre um pd.Series.
Não lê nem escreve disco/S3 — usado exclusivamente pelo M5.
"""
from __future__ import annotations

import pandas as pd

from src.core.benford import _ColumnStats
from src.preprocessing.eligibility_decider import BenfordEligibilityDecider
from ..engine.m2_engine import M2Engine
from ..engine.scorer import M4Scorer
from ...io.reader.s3_reader import parse_column_inputs

_DECIDER = BenfordEligibilityDecider()
_ENGINE  = M2Engine()


def score_series(series: pd.Series, column_name: str = "target") -> float | None:
    """
    Roda M1 + M2 sobre um pd.Series e devolve o score M4.

    Retorna None se a série for inelegível (valid_count < 1000, etc.).

    Parâmetros
    ----------
    series      : valores float64 (já limpos pelo numeric_cleaner)
    column_name : nome fictício usado nos logs

    Retorna
    -------
    float em [0, 1] ou None se inelegível
    """
    # ── M1 em memória ────────────────────────────────────────────────
    stats = _ColumnStats(column_name)

    # Processa em chunks de 100k para manter O(1) de memória
    CHUNK = 100_000
    for start in range(0, len(series), CHUNK):
        chunk = series.iloc[start : start + CHUNK]
        stats.update(chunk)

    report = stats.to_report()  # dict no mesmo formato do _eligibility.json
    col_report = report["columns"].get(column_name, {})

    if not col_report.get("eligible", False):
        return None

    # ── M2 em memória ────────────────────────────────────────────────
    try:
        inputs = parse_column_inputs({column_name: col_report})
    except Exception:
        return None

    if not inputs:
        return None

    analyses = _ENGINE.analyze(inputs)

    if column_name not in analyses:
        return None

    scorer = M4Scorer()
    scores = scorer.score({column_name: analyses[column_name]})

    col_score = scores.get(column_name)
    return col_score.score if col_score is not None else None
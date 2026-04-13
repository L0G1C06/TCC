"""Sequential ID detection utilities."""

import numpy as np
import pandas as pd


def is_sequential_id(series: pd.Series, sample_size: int = 1_000) -> bool:
    """
    Detect if a series is a sequential identifier.
    Only applies to columns whose content looks like IDs (integer strings
    with consistent length). Numeric value columns are excluded early.
    """
    valid = series.dropna().astype(str).str.strip()
    if len(valid) == 0:
        return False

    sample = valid.sample(min(sample_size, len(valid)), random_state=42)

    # Colunas de valor monetário têm vírgula ou ponto decimal — não são IDs
    has_decimal = sample.str.contains(r'[,\.]', regex=True).mean()
    if has_decimal > 0.1:
        return False

    # IDs são só dígitos
    if not sample.str.match(r'^\d+$').all():
        return False

    # Comprimento muito consistente é sinal de ID (ex: CPF, matrícula)
    lengths = sample.str.len()
    if lengths.std() > 2:
        return False

    # Checa sequencialidade — exclui diffs == 0 para não confundir com valores repetidos
    try:
        numeric = pd.to_numeric(sample, errors='coerce').dropna().sort_values()
        if len(numeric) > 10:
            diffs = numeric.diff().dropna()
            nonzero_diffs = diffs[diffs != 0]   # ignora repetições
            if len(nonzero_diffs) == 0:
                return False  # todos iguais = valor constante, não ID
            mode_val = nonzero_diffs.mode().iloc[0]
            ratio = (nonzero_diffs == mode_val).sum() / len(nonzero_diffs)
            return bool(ratio > 0.8)
    except Exception:
        pass

    return False

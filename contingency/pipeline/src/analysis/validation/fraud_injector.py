"""
Injeta adulteração controlada em uma pd.Series de valores monetários.
Estratégia: concentração de dígito inicial — força pct% dos valores
a começarem com target_digit, preservando a ordem de magnitude original.
"""

import numpy as np
import pandas as pd


def inject_digit_concentration(
    series: pd.Series,
    pct: float,
    target_digit: int = 7,
    seed: int = 42,
) -> pd.Series:
    """
    Parâmetros
    ----------
    series       : valores originais (float64, sem nulos)
    pct          : fração adulterada, ex: 0.15 = 15%
    target_digit : dígito inicial forçado (1–9)
    seed         : reprodutibilidade

    Retorna
    -------
    pd.Series com pct% dos valores substituídos por valores cujo
    primeiro dígito é target_digit, na mesma ordem de magnitude.
    """
    if not (0.0 < pct <= 1.0):
        raise ValueError(f"pct deve estar em (0, 1], recebeu {pct}")
    if target_digit not in range(1, 10):
        raise ValueError(f"target_digit deve ser 1–9, recebeu {target_digit}")

    rng = np.random.default_rng(seed)
    result = series.copy()

    n_inject = int(len(series) * pct)
    indices = rng.choice(len(series), size=n_inject, replace=False)

    original_values = series.iloc[indices].values

    # Para cada valor original, preserva a ordem de magnitude
    # e força o primeiro dígito para target_digit
    injected = _force_first_digit(original_values, target_digit, rng)
    result.iloc[indices] = injected

    return result


def _force_first_digit(
    values: np.ndarray,
    digit: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """
    Substitui o primeiro dígito significativo por `digit`,
    preservando a ordem de magnitude (número de casas decimais/inteiras).

    Ex: valor=3.847, digit=7 → 7.xxx na mesma OOM
    """
    result = np.empty_like(values, dtype=np.float64)

    for i, v in enumerate(values):
        if v <= 0:
            result[i] = v
            continue

        # Ordem de magnitude do valor original
        magnitude = np.floor(np.log10(v))
        # Gera um valor aleatório com o dígito forçado na posição correta
        # Ex: digit=7, magnitude=3 → valor entre 7000 e 8000
        lower = digit * (10 ** magnitude)
        upper = (digit + 1) * (10 ** magnitude)
        result[i] = rng.uniform(lower, upper)

    return result
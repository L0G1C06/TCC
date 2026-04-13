"""
Fixtures sintéticas com comportamento estatístico conhecido.
Todas as distribuições são determinísticas via seed fixo.
"""
import numpy as np
import pytest

_RNG = np.random.default_rng(42)

# Contagens totais — grande o suficiente para χ² e Z-Score serem estáveis
N = 100_000


def _make_1d_counts(probs: np.ndarray, n: int = N, seed: int = 42) -> dict[str, int]:
    """Gera first_digit_counts a partir de um vetor de probabilidades (9 dígitos)."""
    rng = np.random.default_rng(seed)
    counts = rng.multinomial(n, probs)
    return {str(d): int(c) for d, c in zip(range(1, 10), counts)}


def _make_2d_counts(probs: np.ndarray, n: int = N, seed: int = 42) -> dict[str, int]:
    """Gera two_digit_counts a partir de vetor de 90 probabilidades (pares 10–99)."""
    rng = np.random.default_rng(seed)
    counts = rng.multinomial(n, probs)
    return {str(pair): int(c) for pair, c in zip(range(10, 100), counts)}


def _make_last_counts(probs: np.ndarray, n: int = N, seed: int = 42) -> dict[str, int]:
    """Gera last_digit_counts a partir de vetor de 10 probabilidades (0–9)."""
    rng = np.random.default_rng(seed)
    counts = rng.multinomial(n, probs)
    return {str(d): int(c) for d, c in zip(range(10), counts)}


# ── Distribuições de 1º dígito ────────────────────────────────────────────────

@pytest.fixture
def benford_perfect_1d() -> dict[str, int]:
    """Distribuição Benford exata: P(d) = log10(1 + 1/d)."""
    probs = np.array([np.log10(1 + 1 / d) for d in range(1, 10)])
    probs /= probs.sum()
    return _make_1d_counts(probs)


@pytest.fixture
def benford_uniform_1d() -> dict[str, int]:
    """Distribuição uniforme — fraude total de 1º dígito."""
    probs = np.ones(9) / 9
    return _make_1d_counts(probs)


@pytest.fixture
def fraud_digit7_1d() -> dict[str, int]:
    """30% dos valores concentrados no dígito 7."""
    probs = np.array([np.log10(1 + 1 / d) for d in range(1, 10)])
    probs /= probs.sum()
    probs[6] += 0.30          # dígito 7 → índice 6
    probs /= probs.sum()      # renormaliza
    return _make_1d_counts(probs)


# ── Distribuições de 2 dígitos ────────────────────────────────────────────────

@pytest.fixture
def benford_perfect_2d() -> dict[str, int]:
    """Distribuição Benford 2D exata: P(n) = log10(1 + 1/n), n ∈ 10–99."""
    probs = np.array([np.log10(1 + 1 / n) for n in range(10, 100)])
    probs /= probs.sum()
    return _make_2d_counts(probs)


@pytest.fixture
def bunching_49_2d() -> dict[str, int]:
    """30% concentrado no par 49 — invisível para Lane 1."""
    probs = np.array([np.log10(1 + 1 / n) for n in range(10, 100)])
    probs /= probs.sum()
    probs[39] += 0.30         # par 49 → índice 39
    probs /= probs.sum()
    return _make_2d_counts(probs)


# ── Distribuições de último dígito ───────────────────────────────────────────

@pytest.fixture
def last_digit_uniform() -> dict[str, int]:
    """Distribuição uniforme real — H₀ verdadeira para LastDigitChi2."""
    probs = np.ones(10) / 10
    return _make_last_counts(probs)


@pytest.fixture
def last_digit_spike_0() -> dict[str, int]:
    """Spike em 0: freq(0) = 0.35 — arredondamento artificial."""
    probs = np.ones(10) / 10
    probs[0] = 0.35
    probs[1:] = (1 - 0.35) / 9
    return _make_last_counts(probs)


@pytest.fixture
def last_digit_spike_5() -> dict[str, int]:
    """Spike em 5: freq(5) = 0.30."""
    probs = np.ones(10) / 10
    probs[5] = 0.30
    probs_rest = (1 - 0.30) / 9
    for i in range(10):
        if i != 5:
            probs[i] = probs_rest
    return _make_last_counts(probs)
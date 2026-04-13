"""
Gera curva ROC para o sistema RING Analysis via injeção sintética.

Protocolo:
  Para cada nível de adulteração p em [pct_min, pct_max]:
    - n_trials partições adulteradas → scores → rótulo positivo
  Baseline limpo (p=0):
    - n_trials partições limpas     → scores → rótulo negativo
  Varia threshold → TPR/FPR → curva ROC → AUC
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, roc_curve

from ..validation.fraud_injector import inject_digit_concentration
from ..validation.pipeline_runner import score_series

logger = logging.getLogger(__name__)


@dataclass
class ROCResult:
    fpr: np.ndarray
    tpr: np.ndarray
    thresholds: np.ndarray
    auc: float
    scores_fraud: list[float]   # scores das amostras adulteradas
    scores_clean: list[float]   # scores das amostras limpas
    pct_levels: list[float]     # nível de adulteração por score_fraud

    def summary(self) -> str:
        lines = [
            f"AUC:          {self.auc:.4f}",
            f"Amostras:     {len(self.scores_fraud)} fraude + {len(self.scores_clean)} limpo",
            f"Score médio (fraude): {np.mean(self.scores_fraud):.4f}",
            f"Score médio (limpo):  {np.mean(self.scores_clean):.4f}",
        ]
        # Menor % em que TPR > 80%
        detected = [
            (p, s) for p, s in zip(self.pct_levels, self.scores_fraud)
            if s is not None
        ]
        if detected:
            threshold_05 = np.percentile(self.scores_clean, 95)  # FPR ≈ 5%
            detectable = [p for p, s in detected if s > threshold_05]
            if detectable:
                lines.append(f"Detectável a partir de: {min(detectable)*100:.0f}% adulteração (FPR≈5%)")
        return "\n".join(lines)


class ROCEvaluator:
    """
    Parâmetros
    ----------
    pct_min    : menor nível de adulteração (default 0.01 = 1%)
    pct_max    : maior nível de adulteração (default 0.30 = 30%)
    pct_step   : passo (default 0.01 = 1%)
    n_trials   : partições por nível (default 30)
    target_digit : dígito forçado na injeção (default 7)
    seed       : semente base (incrementada por trial)
    """

    def __init__(
        self,
        pct_min: float = 0.01,
        pct_max: float = 0.30,
        pct_step: float = 0.01,
        n_trials: int = 30,
        target_digit: int = 7,
        seed: int = 42,
    ):
        self.pct_levels = np.arange(pct_min, pct_max + pct_step / 2, pct_step)
        self.n_trials = n_trials
        self.target_digit = target_digit
        self.seed = seed

    def evaluate(
        self,
        series: pd.Series,
        column_name: str = "target",
    ) -> ROCResult:
        """
        Roda o protocolo completo sobre uma pd.Series limpa (float64).

        Cada trial usa uma amostra aleatória diferente da série original,
        garantindo variabilidade mesmo com dados repetidos.
        """
        rng = np.random.default_rng(self.seed)

        scores_fraud: list[float] = []
        scores_clean: list[float] = []
        pct_per_score: list[float] = []

        n = len(series)

        # ── Baseline limpo ────────────────────────────────────────────
        logger.info("Avaliando baseline limpo (%d trials)...", self.n_trials)
        for trial in range(self.n_trials):
            sample = self._sample(series, rng)
            score = score_series(sample, column_name)
            if score is not None:
                scores_clean.append(score)

        if not scores_clean:
            raise RuntimeError("Nenhuma amostra limpa passou pela elegibilidade.")

        # ── Amostras adulteradas ──────────────────────────────────────
        total = len(self.pct_levels) * self.n_trials
        done = 0

        for pct in self.pct_levels:
            for trial in range(self.n_trials):
                sample = self._sample(series, rng)
                injected = inject_digit_concentration(
                    sample,
                    pct=float(pct),
                    target_digit=self.target_digit,
                    seed=int(rng.integers(0, 2**31)),
                )
                score = score_series(injected, column_name)
                if score is not None:
                    scores_fraud.append(score)
                    pct_per_score.append(float(pct))

                done += 1
                if done % 50 == 0:
                    logger.info("  %d/%d trials concluídos", done, total)

        if not scores_fraud:
            raise RuntimeError("Nenhuma amostra adulterada passou pela elegibilidade.")

        # ── Monta ROC ─────────────────────────────────────────────────
        y_true = [1] * len(scores_fraud) + [0] * len(scores_clean)
        y_score = scores_fraud + scores_clean

        fpr, tpr, thresholds = roc_curve(y_true, y_score)
        auc = roc_auc_score(y_true, y_score)

        logger.info("AUC: %.4f", auc)

        return ROCResult(
            fpr=fpr,
            tpr=tpr,
            thresholds=thresholds,
            auc=auc,
            scores_fraud=scores_fraud,
            scores_clean=scores_clean,
            pct_levels=pct_per_score,
        )

    def _sample(self, series: pd.Series, rng: np.random.Generator) -> pd.Series:
        """Amostra aleatória de 50k registros (ou tudo se menor)."""
        n = min(len(series), 50_000)
        idx = rng.choice(len(series), size=n, replace=False)
        return series.iloc[idx].reset_index(drop=True)
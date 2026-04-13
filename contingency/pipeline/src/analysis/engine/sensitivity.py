"""
analysis/engine/sensitivity.py

Análise de Sensibilidade LHS — Etapa B e C do M4.

Verifica se o ranking das bases mais suspeitas é robusto a variações
nos pesos do score composto. Resultado central do TCC:
    "As 3 bases mais suspeitas mantêm suas posições em >80% dos cenários"
    → prova que o resultado não é artefato da escolha de pesos.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.stats.qmc import LatinHypercube

logger = logging.getLogger(__name__)

# ── Componentes na ordem canônica ─────────────────────────────────────────────
_COMPONENTS = ["JS_1d", "MAD_1d", "JS_2d", "Z_max", "last_digit"]
_N_COMPONENTS = len(_COMPONENTS)

# ── Resultados ────────────────────────────────────────────────────────────────

@dataclass
class SensitivityResult:
    """
    Resultado completo da análise LHS.

    Campos
    ------
    stability_matrix    : DataFrame (n_samples × n_scopes) — posição no ranking
                          para cada combinação de pesos.
                          index   = inteiro 0..n_samples-1
                          columns = scope_id (ex: "modulo=compras")

    stability_scores    : dict scope_id → fração de cenários em que o scope
                          manteve a mesma posição canônica (±0 posições).

    top_k_stability     : dict scope_id → fração de cenários em que o scope
                          permaneceu no top-k (default k=3).

    canonical_ranking   : lista de scope_id ordenada pelo score canônico
                          (pesos originais do M2_SPEC).

    robust_top3         : lista de scope_id que ficaram no top-3 em >80%
                          dos cenários — resultado para o TCC.

    weight_samples      : array (n_samples × 5) — as combinações de pesos
                          geradas pelo LHS. Útil para reprodutibilidade.

    n_samples           : número de amostras LHS geradas.
    """
    stability_matrix : pd.DataFrame
    stability_scores : dict[str, float]
    top_k_stability  : dict[str, float]
    canonical_ranking: list[str]
    robust_top3      : list[str]
    weight_samples   : np.ndarray
    n_samples        : int
    k                : int = 3

    def summary(self) -> str:
        """Resumo em texto para print no terminal e no TCC."""
        lines = [
            f"LHS Sensitivity — {self.n_samples} amostras, k={self.k}",
            f"{'─' * 60}",
            f"{'Scope':<40} {'Rank canônico':>14} {'Top-k estab.':>13}",
            f"{'─' * 40} {'─' * 14} {'─' * 13}",
        ]
        for rank, scope in enumerate(self.canonical_ranking, 1):
            topk  = self.top_k_stability.get(scope, 0.0)
            mark  = " ✓" if scope in self.robust_top3 else ""
            lines.append(
                f"  {scope:<38} #{rank:<13} {topk:>11.1%}{mark}"
            )
        lines += [
            f"{'─' * 60}",
            f"Top-3 robustos (>80% dos cenários): {len(self.robust_top3)}",
        ]
        for s in self.robust_top3:
            lines.append(f"  • {s}")
        return "\n".join(lines)


# ── Analisador ────────────────────────────────────────────────────────────────

class LHSSensitivityAnalyzer:
    """
    Gera 500+ combinações de pesos via Latin Hypercube Sampling e
    calcula a estabilidade do ranking do Score Composto M4.

    Recebe os valores brutos já normalizados globalmente (saída do
    GlobalScorer._global_normalize via raw_values) para que a
    sensibilidade avalie apenas a variação dos pesos — não da normalização.

    Uso
    ---
        from analysis.engine.scorer import GlobalScorer
        from analysis.engine.sensitivity import LHSSensitivityAnalyzer

        global_scorer = GlobalScorer()
        for scope_id, analyses in all_analyses.items():
            global_scorer.register(scope_id, analyses)

        all_scores    = global_scorer.score_all()
        analyzer      = LHSSensitivityAnalyzer()
        result        = analyzer.analyze(global_scorer.raw_values)
        print(result.summary())
    """

    def __init__(self, n_samples: int = 500, k: int = 3, seed: int = 42):
        """
        n_samples : número de combinações de pesos LHS (mínimo 500 para TCC)
        k         : posições no top-k para calcular estabilidade (default 3)
        seed      : semente para reprodutibilidade — registrar no TCC
        """
        self.n_samples = n_samples
        self.k         = k
        self.seed      = seed

    def analyze(
        self,
        raw_values: dict[str, dict[str, dict[str, float]]],
        canonical_weights: dict[str, float] | None = None,
    ) -> SensitivityResult:
        """
        Executa a análise LHS completa.

        Parâmetros
        ----------
        raw_values        : GlobalScorer.raw_values
                            {scope_id: {col: {component: value}}}
                            Nota: scope_id com múltiplas colunas são
                            reduzidos ao max score entre as colunas —
                            o score do escopo é o pior caso.

        canonical_weights : pesos canônicos para o ranking de referência.
                            None = usa os pesos do M2_SPEC.
        """
        from ..base import BenfordFlag  # import local evita circular

        cw = canonical_weights or {
            "JS_1d": 0.30, "MAD_1d": 0.25, "JS_2d": 0.20,
            "Z_max": 0.15, "last_digit": 0.10,
        }

        # ── Redução scope → vetor de componentes normalizados ─────────────
        # Escopo com múltiplas colunas: pega a coluna com pior perfil
        # (max de cada componente individualmente — conservador).
        scope_vectors = _build_scope_vectors(raw_values)
        scopes        = list(scope_vectors.keys())

        if len(scopes) < 2:
            raise ValueError(
                f"LHS requer ao menos 2 escopos registrados. "
                f"Encontrados: {len(scopes)}"
            )

        # Matriz (n_scopes × n_components) — valores brutos globalizados
        matrix = np.array(
            [[scope_vectors[s].get(c, 0.0) for c in _COMPONENTS] for s in scopes],
            dtype=np.float64,
        )

        # ── Normalização global da matriz de escopos ──────────────────────
        mins = matrix.min(axis=0)
        maxs = matrix.max(axis=0)
        rngs = maxs - mins
        with np.errstate(invalid="ignore", divide="ignore"):
            norm_matrix = np.where(rngs > 1e-12, (matrix - mins) / rngs, 0.0)

        # ── Ranking canônico ──────────────────────────────────────────────
        cw_arr          = np.array([cw[c] for c in _COMPONENTS])
        canonical_scores = norm_matrix @ cw_arr
        canonical_order  = np.argsort(canonical_scores)[::-1]
        canonical_ranking = [scopes[i] for i in canonical_order]

        # ── Geração LHS de pesos ──────────────────────────────────────────
        weight_samples = _sample_weights_lhs(
            n=self.n_samples,
            d=_N_COMPONENTS,
            seed=self.seed,
        )

        # ── Matriz de rankings (n_samples × n_scopes) ────────────────────
        # rank_matrix[i, j] = posição do scope j no cenário i (1-indexed)
        scores_matrix = norm_matrix @ weight_samples.T  # (n_scopes × n_samples)
        rank_matrix   = np.argsort(
            np.argsort(-scores_matrix, axis=0), axis=0
        ) + 1  # (n_scopes × n_samples), 1-indexed

        stability_df = pd.DataFrame(
            rank_matrix.T,           # (n_samples × n_scopes)
            columns=scopes,
        )

        # ── Métricas de estabilidade ──────────────────────────────────────
        canonical_ranks = {
            scopes[canonical_order[r]]: r + 1
            for r in range(len(scopes))
        }

        stability_scores: dict[str, float] = {}
        top_k_stability:  dict[str, float] = {}

        for scope in scopes:
            canonical_rank = canonical_ranks[scope]
            col_ranks      = stability_df[scope].values

            # Fração dos cenários com rank idêntico ao canônico
            stability_scores[scope] = float((col_ranks == canonical_rank).mean())

            # Fração dos cenários onde o scope ficou no top-k
            top_k_stability[scope] = float((col_ranks <= self.k).mean())

        # ── Top-3 robustos ────────────────────────────────────────────────
        robust_top3 = [
            s for s in canonical_ranking[:self.k]
            if top_k_stability[s] >= 0.80
        ]

        _log_sensitivity(canonical_ranking, top_k_stability, robust_top3, self.k)

        return SensitivityResult(
            stability_matrix=stability_df,
            stability_scores=stability_scores,
            top_k_stability=top_k_stability,
            canonical_ranking=canonical_ranking,
            robust_top3=robust_top3,
            weight_samples=weight_samples,
            n_samples=self.n_samples,
            k=self.k,
        )


# ── Funções auxiliares ────────────────────────────────────────────────────────

def _build_scope_vectors(
    raw_values: dict[str, dict[str, dict[str, float]]],
) -> dict[str, dict[str, float]]:
    """
    Reduz {scope: {col: {component: value}}} para {scope: {component: value}}.
    Escopos com múltiplas colunas usam o max por componente (caso mais suspeito).
    """
    result: dict[str, dict[str, float]] = {}
    for scope_id, col_raws in raw_values.items():
        if not col_raws:
            continue
        merged: dict[str, float] = {}
        for col_raw in col_raws.values():
            for comp, val in col_raw.items():
                merged[comp] = max(merged.get(comp, 0.0), val)
        result[scope_id] = merged
    return result


def _sample_weights_lhs(n: int, d: int, seed: int) -> np.ndarray:
    """
    Gera n combinações de pesos em R^d com Σwᵢ = 1 via LHS.

    Estratégia: LHS em [0,1]^d → normaliza cada linha pela soma.
    Garante cobertura uniforme do simplex sem viés para os cantos.

    Retorna array (n × d).
    """
    sampler = LatinHypercube(d=d, seed=seed)
    raw     = sampler.random(n=n)           # (n × d) em [0, 1]

    # Proteção: evitar linhas com soma zero (impossível com LHS, mas defensivo)
    row_sums = raw.sum(axis=1, keepdims=True)
    row_sums = np.where(row_sums < 1e-12, 1.0, row_sums)

    return raw / row_sums                   # (n × d), cada linha soma 1.0


def _log_sensitivity(
    canonical_ranking: list[str],
    top_k_stability: dict[str, float],
    robust_top3: list[str],
    k: int,
) -> None:
    logger.info("LHS Sensitivity concluída")
    for rank, scope in enumerate(canonical_ranking[:k], 1):
        stab = top_k_stability.get(scope, 0.0)
        robust = "✓ robusto" if scope in robust_top3 else "✗ instável"
        logger.info("  #%d %s — top-%d em %.1f%% dos cenários — %s",
                    rank, scope, k, stab * 100, robust)
    if len(robust_top3) < k:
        logger.warning(
            "Apenas %d/%d bases no top-%d são robustas (>80%%). "
            "Revisar pesos canônicos ou ampliar base de dados.",
            len(robust_top3), k, k,
        )
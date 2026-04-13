"""
Sistema de Detecção de Fraude — Análise de Benford Multi-Dígito
Implementação completa seguindo o modelo matemático do TCC.

Modo de operação em chunks
--------------------------
Para datasets grandes (>5M registros) use a API em duas passagens:

    # 1ª passagem — acumula estatísticas globais sem manter dados na RAM
    acum = BenfordAccumulator()
    for chunk in ler_chunks(...):
        acum.alimentar(chunk["valor"].values)
    benford_global = acum.finalizar()

    # 2ª passagem — processa cada chunk independentemente e salva
    for chunk in ler_chunks(...):
        resultado = processar_chunk(chunk, benford_global)
        resultado.to_csv(saida, mode="a", header=False)
        del resultado  # libera antes do próximo

Para datasets pequenos (<2M) use diretamente detectar_fraude().
"""

from __future__ import annotations

import logging
import math
import time
import warnings
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator, Optional

import numpy as np
import pandas as pd
from scipy.stats import chi2, kstest, shapiro
from tqdm import tqdm

warnings.filterwarnings("ignore")

# ── Logging ───────────────────────────────────────────────────────────────────

log = logging.getLogger(__name__)


@contextmanager
def _cronometrar(label: str):
    log.info("  ▶  %s ...", label)
    t0 = time.perf_counter()
    yield
    log.info("  ✔  %s — %.2fs", label, time.perf_counter() - t0)


# ─────────────────────────────────────────────
# CONFIGURAÇÃO
# ─────────────────────────────────────────────

WEIGHTS = dict(w1=0.20, w2=0.20, w3=0.20, w4=0.25, w5=0.15)

MAD_THRESHOLDS = dict(d1=0.015, d2=0.012, d12=0.0012, last=0.008)

MARGEM_SUSPEITA = 0.02
ALPHA           = 0.05
CHUNK_SIZE      = 500_000   # registros por chunk (ajuste conforme RAM disponível)
CLUSTER_BATCH_SIZE = 50


# ─────────────────────────────────────────────
# ESTRUTURAS DE DADOS
# ─────────────────────────────────────────────

@dataclass
class BenfordResult:
    mad: float
    chi2_stat: float
    chi2_pvalue: float
    freq_obs: dict
    freq_exp: dict
    digitos_suspeitos: list
    desvio: bool


@dataclass
class ClusterResult:
    chave: tuple
    n: int
    taxa_outliers: float
    mad_d1: float
    alto_risco: bool
    benford_d1: Optional[BenfordResult] = None


@dataclass
class TransactionResult:
    """Mantido por compatibilidade com código legado."""
    index: int
    valor: float
    outlier_iqr: bool
    outlier_z: bool
    outlier_mad: bool
    flag_benford: int
    cluster_alto_risco: bool
    score_raw: float = 0.0
    score_norm: float = 0.0
    classificacao: str = "NORMAL"


# ─────────────────────────────────────────────
# EXTRAÇÃO DE DÍGITOS — VETORIZADA
# ─────────────────────────────────────────────

def _extrair_digitos_vetorizado(X: np.ndarray) -> dict[str, np.ndarray]:
    """
    Extrai d1, d2, d12, last para o array de uma vez.
    Valores sem dígito suficiente recebem sentinela -1.
    """
    inteiros = np.abs(X).astype(np.int64)

    with np.errstate(divide="ignore", invalid="ignore"):
        n_digits = np.where(inteiros > 0, np.floor(np.log10(inteiros)).astype(int) + 1, 1)

    pot  = (10 ** (n_digits - 1)).astype(np.int64)
    pot2 = (10 ** np.maximum(n_digits - 2, 0)).astype(np.int64)

    d1   = (inteiros // pot) % 10
    d2   = np.where(n_digits >= 2, (inteiros // (pot // 10)) % 10, -1)
    d12  = np.where(n_digits >= 2, (inteiros // pot2) % 100, -1)
    last = inteiros % 10

    return dict(d1=d1, d2=d2, d12=d12, last=last)


# ─────────────────────────────────────────────
# FREQUÊNCIAS ESPERADAS (calculadas uma única vez)
# ─────────────────────────────────────────────

_FREQ_EXP = {
    "d1":   {d: math.log10(1 + 1 / d) for d in range(1, 10)},
    "d2":   {d: sum(math.log10(1 + 1 / (10 * k + d)) for k in range(1, 10))
             for d in range(0, 10)},
    "d12":  {n: math.log10(1 + 1 / n) for n in range(10, 100)},
    "last": {d: 0.1 for d in range(0, 10)},
}

def freq_esperada_d1()   -> dict: return _FREQ_EXP["d1"]
def freq_esperada_d2()   -> dict: return _FREQ_EXP["d2"]
def freq_esperada_d12()  -> dict: return _FREQ_EXP["d12"]
def freq_esperada_last() -> dict: return _FREQ_EXP["last"]


# ─────────────────────────────────────────────
# ACUMULADOR BENFORD — 1ª PASSAGEM (sem guardar dados)
# ─────────────────────────────────────────────

@dataclass
class BenfordAccumulator:
    """
    Acumula contagens de dígitos chunk a chunk sem manter os valores na RAM.

    Uso:
        acum = BenfordAccumulator()
        for chunk_vals in ...:
            acum.alimentar(chunk_vals)
        benford_global = acum.finalizar()
    """
    _counts: dict[str, Counter] = field(default_factory=lambda: {
        k: Counter() for k in ("d1", "d2", "d12", "last")
    })
    _total: dict[str, int] = field(default_factory=lambda: {
        k: 0 for k in ("d1", "d2", "d12", "last")
    })

    def alimentar(self, X: np.ndarray) -> None:
        """Adiciona um chunk de valores às contagens acumuladas."""
        X = X[np.isfinite(X) & (X > 0)]
        if len(X) == 0:
            return
        d = _extrair_digitos_vetorizado(X)
        for nivel in ("d1", "d2", "d12", "last"):
            arr = d[nivel]
            validos = arr[arr >= 0]
            self._counts[nivel].update(validos.tolist())
            self._total[nivel] += len(validos)

    def finalizar(self) -> dict[str, BenfordResult]:
        """Calcula BenfordResult para cada nível a partir das contagens acumuladas."""
        resultados = {}
        for nivel, freq_exp in _FREQ_EXP.items():
            total = self._total[nivel]
            if total == 0:
                resultados[nivel] = BenfordResult(0, 0, 1, {}, freq_exp, [], False)
                continue

            digitos  = sorted(freq_exp.keys())
            freq_obs = {d: self._counts[nivel].get(d, 0) / total for d in digitos}

            mad = float(np.mean([abs(freq_obs[d] - freq_exp[d]) for d in digitos]))

            chi2_stat = sum(
                ((freq_obs[d] - freq_exp[d]) ** 2) / freq_exp[d]
                for d in digitos if freq_exp[d] > 0
            ) * total

            p_value           = 1 - chi2.cdf(chi2_stat, len(digitos) - 1)
            digitos_suspeitos = [d for d in digitos if freq_obs[d] > freq_exp[d] + MARGEM_SUSPEITA]
            desvio            = mad > MAD_THRESHOLDS.get(nivel, 0.015) or p_value < ALPHA

            resultados[nivel] = BenfordResult(
                mad=mad, chi2_stat=chi2_stat, chi2_pvalue=p_value,
                freq_obs=freq_obs, freq_exp=freq_exp,
                digitos_suspeitos=digitos_suspeitos, desvio=desvio,
            )
            log.info("    [%s] MAD=%.5f  χ²=%.2f  p=%.4f  suspeitos=%s  desvio=%s",
                     nivel.upper(), mad, chi2_stat, p_value, digitos_suspeitos, desvio)

        return resultados


# ─────────────────────────────────────────────
# NÚCLEO BENFORD (compatibilidade)
# ─────────────────────────────────────────────

def _analisar_distribuicao(valores: np.ndarray, freq_exp: dict, label: str) -> BenfordResult:
    arr   = np.asarray(valores)
    arr   = arr[arr >= 0]
    total = len(arr)

    if total == 0:
        return BenfordResult(0, 0, 1, {}, freq_exp, [], False)

    digitos  = sorted(freq_exp.keys())
    counts   = Counter(arr.tolist())
    freq_obs = {d: counts.get(d, 0) / total for d in digitos}
    mad      = float(np.mean([abs(freq_obs[d] - freq_exp[d]) for d in digitos]))

    chi2_stat = sum(
        ((freq_obs[d] - freq_exp[d]) ** 2) / freq_exp[d]
        for d in digitos if freq_exp[d] > 0
    ) * total

    p_value           = 1 - chi2.cdf(chi2_stat, len(digitos) - 1)
    digitos_suspeitos = [d for d in digitos if freq_obs[d] > freq_exp[d] + MARGEM_SUSPEITA]
    desvio            = mad > MAD_THRESHOLDS.get(label, 0.015) or p_value < ALPHA

    return BenfordResult(mad=mad, chi2_stat=chi2_stat, chi2_pvalue=p_value,
                         freq_obs=freq_obs, freq_exp=freq_exp,
                         digitos_suspeitos=digitos_suspeitos, desvio=desvio)


def analisar_benford_completo(
    valores: list | np.ndarray,
    digitos_vetorizados: Optional[dict[str, np.ndarray]] = None,
) -> dict[str, BenfordResult]:
    if digitos_vetorizados is None:
        digitos_vetorizados = _extrair_digitos_vetorizado(np.asarray(valores, dtype=np.float64))
    d = digitos_vetorizados
    return {
        "d1":   _analisar_distribuicao(d["d1"],   _FREQ_EXP["d1"],   "d1"),
        "d2":   _analisar_distribuicao(d["d2"],   _FREQ_EXP["d2"],   "d2"),
        "d12":  _analisar_distribuicao(d["d12"],  _FREQ_EXP["d12"],  "d12"),
        "last": _analisar_distribuicao(d["last"], _FREQ_EXP["last"], "last"),
    }


def benford_desvio_global(resultados: dict[str, BenfordResult]) -> bool:
    return any(r.desvio for r in resultados.values())


# ─────────────────────────────────────────────
# FLAGS BENFORD — VETORIZADA
# ─────────────────────────────────────────────

def calcular_flags_benford_vetorizado(
    digitos: dict[str, np.ndarray],
    benford_global: dict[str, BenfordResult],
) -> np.ndarray:
    flags = np.zeros(len(digitos["d1"]), dtype=np.int32)
    for nivel, arr in digitos.items():
        suspeitos = np.array(benford_global[nivel].digitos_suspeitos, dtype=np.int64)
        if suspeitos.size == 0:
            continue
        flags += (np.isin(arr, suspeitos) & (arr >= 0)).astype(np.int32)
    return flags


def flag_benford_transacao(valor: float, resultados: dict[str, BenfordResult]) -> int:
    """Compatibilidade com testes unitários."""
    s = str(int(abs(valor)))
    mapa = {"d1": int(s[0]), "d2": int(s[1]) if len(s) >= 2 else -1,
            "d12": int(s[:2]) if len(s) >= 2 else -1, "last": int(s[-1])}
    return sum(1 for nv, d in mapa.items()
               if d >= 0 and d in resultados[nv].digitos_suspeitos)


# ─────────────────────────────────────────────
# OUTLIERS E NORMALIDADE
# ─────────────────────────────────────────────

def detectar_outliers(X: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    Q1, Q3      = np.percentile(X, 25), np.percentile(X, 75)
    outlier_iqr = (X < Q1 - 1.5 * (Q3 - Q1)) | (X > Q3 + 1.5 * (Q3 - Q1))

    media, desvio = X.mean(), X.std()
    outlier_z     = np.abs((X - media) / (desvio or 1)) > 3

    mediana       = np.median(X)
    mad           = np.median(np.abs(X - mediana)) or 1e-9
    outlier_mad   = np.abs(0.6745 * (X - mediana) / mad) > 3.5

    log.info("    Outliers — IQR: %d (%.1f%%)  Z: %d (%.1f%%)  MAD: %d (%.1f%%)",
             outlier_iqr.sum(), outlier_iqr.mean() * 100,
             outlier_z.sum(),   outlier_z.mean()   * 100,
             outlier_mad.sum(), outlier_mad.mean()  * 100)
    return outlier_iqr, outlier_z, outlier_mad


def testar_normalidade(X: np.ndarray) -> dict:
    sample       = X if len(X) <= 5000 else np.random.choice(X, 5000, replace=False)
    _, p_shapiro = shapiro(sample)
    _, p_ks      = kstest((X - X.mean()) / (X.std() or 1), "norm")
    normal       = p_shapiro > ALPHA and p_ks > ALPHA
    log.info("    Normalidade — Shapiro p=%.4f  KS p=%.4f  normal=%s", p_shapiro, p_ks, normal)
    return dict(p_shapiro=p_shapiro, p_ks=p_ks, normal=normal)


# ─────────────────────────────────────────────
# CLUSTERS — EM BATCH
# ─────────────────────────────────────────────

def _processar_cluster(
    chave: tuple,
    idx: np.ndarray,
    vals: np.ndarray,
    digitos_globais: dict[str, np.ndarray],
    outlier_mask: np.ndarray,
    limiar_mad: float,
    limiar_taxa_outliers: float,
) -> ClusterResult:
    digitos_cluster = {k: v[idx] for k, v in digitos_globais.items()}
    benford         = analisar_benford_completo(vals, digitos_vetorizados=digitos_cluster)
    taxa_outliers   = float(outlier_mask[idx].mean())
    mad_d1          = benford["d1"].mad
    return ClusterResult(
        chave=chave, n=len(vals),
        taxa_outliers=taxa_outliers, mad_d1=mad_d1,
        alto_risco=(mad_d1 > limiar_mad) and (taxa_outliers > limiar_taxa_outliers),
        benford_d1=benford["d1"],
    )


def analisar_clusters(
    df: pd.DataFrame,
    colunas_cluster: list[str],
    coluna_valor: str,
    outlier_mask: np.ndarray,
    digitos_globais: dict[str, np.ndarray],
    limiar_mad: float = 0.015,
    limiar_taxa_outliers: float = 0.20,
    batch_size: int = CLUSTER_BATCH_SIZE,
) -> dict[tuple, ClusterResult]:
    grupos      = [(chave if isinstance(chave, tuple) else (chave,), grp.index.to_numpy())
                   for chave, grp in df.groupby(colunas_cluster)]
    vals_global = df[coluna_valor].to_numpy()
    resultados: dict[tuple, ClusterResult] = {}
    n_alto_risco = 0

    log.info("    %d clusters — batches de %d", len(grupos), batch_size)

    with tqdm(total=len(grupos), desc="Clusters", unit="cluster") as pbar:
        for start in range(0, len(grupos), batch_size):
            batch = grupos[start : start + batch_size]
            for chave, idx in batch:
                r = _processar_cluster(chave, idx, vals_global[idx],
                                       digitos_globais, outlier_mask,
                                       limiar_mad, limiar_taxa_outliers)
                resultados[chave] = r
                if r.alto_risco:
                    n_alto_risco += 1
                pbar.update(1)
            del batch

    log.info("    Clusters: %d total, %d alto risco", len(resultados), n_alto_risco)
    return resultados


def mapear_cluster_risco(
    df: pd.DataFrame,
    colunas_cluster: list[str],
    cluster_results: dict[tuple, ClusterResult],
) -> np.ndarray:
    mapa      = {chave: res.alto_risco for chave, res in cluster_results.items()}
    chave_col = df[colunas_cluster].apply(
        lambda row: tuple(row) if len(colunas_cluster) > 1 else (row.iloc[0],), axis=1
    )
    return chave_col.map(mapa).fillna(False).to_numpy(dtype=bool)


# ─────────────────────────────────────────────
# SCORE E CLASSIFICAÇÃO
# ─────────────────────────────────────────────

def calcular_scores(
    outlier_iqr: np.ndarray, outlier_z: np.ndarray, outlier_mad_arr: np.ndarray,
    flags_benford: np.ndarray, cluster_risco: np.ndarray, weights: dict = WEIGHTS,
) -> tuple[np.ndarray, np.ndarray]:
    raw = (weights["w1"] * outlier_iqr.astype(float)
         + weights["w2"] * outlier_z.astype(float)
         + weights["w3"] * outlier_mad_arr.astype(float)
         + weights["w4"] * (flags_benford / 4.0)
         + weights["w5"] * cluster_risco.astype(float))
    mn, mx     = raw.min(), raw.max()
    norm_score = (raw - mn) / (mx - mn + 1e-12)
    return raw, norm_score


def classificar(score: float) -> str:
    if score >= 0.7: return "ALTA SUSPEITA"
    if score >= 0.4: return "SUSPEITA"
    return "NORMAL"


def _classificar_array(norm_score: np.ndarray) -> np.ndarray:
    result = np.full(len(norm_score), "NORMAL", dtype=object)
    result[norm_score >= 0.4] = "SUSPEITA"
    result[norm_score >= 0.7] = "ALTA SUSPEITA"
    return result


# ─────────────────────────────────────────────
# PROCESSAMENTO DE CHUNK — 2ª PASSAGEM
# ─────────────────────────────────────────────

def processar_chunk(
    chunk: pd.DataFrame,
    benford_global: dict[str, BenfordResult],
    colunas_cluster: list[str],
    coluna_valor: str = "valor",
    norm_min: float = 0.0,
    norm_max: float = 1.0,
) -> pd.DataFrame:
    """
    Processa um chunk na 2ª passagem usando o benford_global já calculado.

    norm_min / norm_max: mín/máx do score raw global (calculados na 1ª passagem)
    para que a normalização seja consistente entre chunks.
    """
    chunk = chunk[chunk[coluna_valor].notna() & (chunk[coluna_valor] > 0)].reset_index(drop=True)
    if chunk.empty:
        return chunk

    X       = chunk[coluna_valor].values
    digitos = _extrair_digitos_vetorizado(X)

    outlier_iqr, outlier_z, outlier_mad = detectar_outliers(X)
    flags_benford = calcular_flags_benford_vetorizado(digitos, benford_global)

    # Clusters dentro do chunk
    cluster_risco = np.zeros(len(chunk), dtype=bool)
    if colunas_cluster and all(c in chunk.columns for c in colunas_cluster):
        outlier_any     = outlier_iqr | outlier_z | outlier_mad
        cluster_results = analisar_clusters(
            chunk, colunas_cluster, coluna_valor, outlier_any, digitos
        )
        cluster_risco = mapear_cluster_risco(chunk, colunas_cluster, cluster_results)

    raw = (WEIGHTS["w1"] * outlier_iqr.astype(float)
         + WEIGHTS["w2"] * outlier_z.astype(float)
         + WEIGHTS["w3"] * outlier_mad.astype(float)
         + WEIGHTS["w4"] * (flags_benford / 4.0)
         + WEIGHTS["w5"] * cluster_risco.astype(float))

    norm_score = (raw - norm_min) / (norm_max - norm_min + 1e-12)

    chunk["outlier_iqr"]        = outlier_iqr
    chunk["outlier_z"]          = outlier_z
    chunk["outlier_mad"]        = outlier_mad
    chunk["flag_benford"]       = flags_benford
    chunk["cluster_alto_risco"] = cluster_risco
    chunk["score_raw"]          = raw
    chunk["score_norm"]         = norm_score
    chunk["classificacao"]      = _classificar_array(norm_score)

    # Libera arrays temporários antes de retornar
    del X, digitos, outlier_iqr, outlier_z, outlier_mad
    del flags_benford, cluster_risco, raw, norm_score

    return chunk


# ─────────────────────────────────────────────
# PIPELINE CHUNKED — API PRINCIPAL PARA DATASETS GRANDES
# ─────────────────────────────────────────────

def detectar_fraude_chunked(
    chunks_fn,                          # callable() → Iterator[pd.DataFrame]
    output_csv: str,
    colunas_cluster: list[str],
    coluna_valor: str = "valor",
    chunk_size: int = CHUNK_SIZE,
) -> dict:
    """
    Pipeline completo em duas passagens para datasets que não cabem na RAM.

    Passagem 1 — varre os chunks acumulando apenas contagens de dígitos
                 (O(1) memória extra por chunk).
    Passagem 2 — processa cada chunk com o Benford global, escreve CSV
                 incrementalmente e libera a RAM antes do próximo.

    Parâmetros
    ----------
    chunks_fn       : callable sem argumentos que retorna Iterator[pd.DataFrame]
    output_csv      : caminho do CSV de saída (será sobrescrito)
    colunas_cluster : colunas para agrupamento
    coluna_valor    : nome da coluna monetária
    chunk_size      : hint de tamanho do chunk (usado pelo chamador)

    Retorna
    -------
    metricas : dict com benford_global, normalidade (amostral), benford_desvio
    """
    t_total = time.perf_counter()

    # ── 1ª passagem — acumula Benford e estatísticas globais ──────────
    log.info("Passagem 1/2 — acumulando estatísticas globais...")
    acum        = BenfordAccumulator()
    sample_vals = []   # amostra para normalidade (máx 5000 valores)
    n_total     = 0
    raw_min     = np.inf
    raw_max     = -np.inf

    for chunk in tqdm(chunks_fn(), desc="Passagem 1", unit="chunk"):
        vals = chunk[coluna_valor].dropna()
        vals = vals[vals > 0].values
        if len(vals) == 0:
            continue
        acum.alimentar(vals)
        n_total += len(vals)

        # Amostra para normalidade
        if len(sample_vals) < 5000:
            sample_vals.extend(vals[:max(0, 5000 - len(sample_vals))].tolist())

        # Pré-calcula range do score raw para normalização global consistente
        oir, oz, om = detectar_outliers(vals)
        raw_chunk = (WEIGHTS["w1"] * oir.astype(float)
                   + WEIGHTS["w2"] * oz.astype(float)
                   + WEIGHTS["w3"] * om.astype(float))
        raw_min = min(raw_min, raw_chunk.min())
        raw_max = max(raw_max, raw_chunk.max())
        del vals, oir, oz, om, raw_chunk

    with _cronometrar("Finalizando Benford global"):
        benford_global = acum.finalizar()
    del acum

    norm_result = testar_normalidade(np.array(sample_vals))
    del sample_vals

    log.info("  Total acumulado: %d registros  raw_score ∈ [%.4f, %.4f]",
             n_total, raw_min, raw_max)

    # ── 2ª passagem — processa e salva chunk a chunk ──────────────────
    log.info("Passagem 2/2 — processando e gravando resultados...")
    primeiro = True
    n_gravados = 0
    contadores: Counter = Counter()

    for chunk in tqdm(chunks_fn(), desc="Passagem 2", unit="chunk"):
        resultado = processar_chunk(
            chunk, benford_global, colunas_cluster, coluna_valor,
            norm_min=raw_min, norm_max=raw_max,
        )
        if resultado.empty:
            del chunk, resultado
            continue

        contadores.update(resultado["classificacao"].tolist())
        resultado.to_csv(output_csv, mode="w" if primeiro else "a",
                         header=primeiro, index=False)
        n_gravados += len(resultado)
        primeiro    = False
        del chunk, resultado   # libera RAM antes do próximo chunk

    metricas = dict(
        normalidade    = norm_result,
        benford_global = benford_global,
        benford_desvio = benford_desvio_global(benford_global),
        n_total        = n_total,
        classificacao  = dict(contadores),
    )

    elapsed = time.perf_counter() - t_total
    log.info("Pipeline chunked completo — %d registros em %.1fs", n_gravados, elapsed)
    for cls, n in contadores.items():
        log.info("  %-14s %8d (%.1f%%)", cls, n, n / max(n_gravados, 1) * 100)

    return metricas


# ─────────────────────────────────────────────
# PIPELINE LEGADO — para datasets pequenos
# ─────────────────────────────────────────────

def preprocessar(df: pd.DataFrame, coluna_valor: str = "valor") -> pd.DataFrame:
    antes = len(df)
    df    = df.dropna(subset=[coluna_valor])
    df    = df[df[coluna_valor] > 0].reset_index(drop=True)
    log.info("    Pré-processamento: %d → %d registros (%d removidos)",
             antes, len(df), antes - len(df))
    return df


def detectar_fraude(
    df: pd.DataFrame,
    coluna_valor: str = "valor",
    colunas_cluster: Optional[list[str]] = None,
) -> tuple[pd.DataFrame, dict]:
    """
    Pipeline completo em memória — use apenas para datasets < 2M registros.
    Para datasets maiores use detectar_fraude_chunked().
    """
    t_total = time.perf_counter()
    bar = tqdm(total=7, desc="Pipeline", unit="etapa", ncols=80, leave=True)

    def step(label: str) -> None:
        bar.set_postfix_str(label)
        bar.update(1)

    step("pré-processamento")
    with _cronometrar("Pré-processamento"):
        df = preprocessar(df, coluna_valor)
        X  = df[coluna_valor].values

    step("extração de dígitos")
    with _cronometrar("Extração de dígitos"):
        digitos_globais = _extrair_digitos_vetorizado(X)

    step("outliers")
    with _cronometrar("Outliers"):
        outlier_iqr, outlier_z, outlier_mad_arr = detectar_outliers(X)

    step("normalidade")
    with _cronometrar("Normalidade"):
        norm_result = testar_normalidade(X)

    step("benford global + flags")
    with _cronometrar("Benford global"):
        benford_global = analisar_benford_completo(X, digitos_vetorizados=digitos_globais)

    with _cronometrar("Flags Benford"):
        flags_benford = calcular_flags_benford_vetorizado(digitos_globais, benford_global)
        log.info("    Flag > 0: %d (%.1f%%)",
                 (flags_benford > 0).sum(), (flags_benford > 0).mean() * 100)
        del X

    step("clusters")
    with _cronometrar("Clusters"):
        cluster_risco = np.zeros(len(df), dtype=bool)
        cluster_results = {}
        if colunas_cluster and all(c in df.columns for c in colunas_cluster):
            outlier_any     = outlier_iqr | outlier_z | outlier_mad_arr
            cluster_results = analisar_clusters(
                df, colunas_cluster, coluna_valor, outlier_any, digitos_globais
            )
            cluster_risco = mapear_cluster_risco(df, colunas_cluster, cluster_results)
            log.info("    Alto risco: %d (%.1f%%)",
                     cluster_risco.sum(), cluster_risco.mean() * 100)

    step("score + classificação")
    with _cronometrar("Score final"):
        raw, norm_score = calcular_scores(
            outlier_iqr, outlier_z, outlier_mad_arr, flags_benford, cluster_risco
        )
        classificacao = _classificar_array(norm_score)

    bar.close()

    df["outlier_iqr"]        = outlier_iqr
    df["outlier_z"]          = outlier_z
    df["outlier_mad"]        = outlier_mad_arr
    df["flag_benford"]       = flags_benford
    df["cluster_alto_risco"] = cluster_risco
    df["score_raw"]          = raw
    df["score_norm"]         = norm_score
    df["classificacao"]      = classificacao
    df_result = df

    metricas = dict(
        normalidade    = norm_result,
        benford_global = {k: v for k, v in benford_global.items()},
        benford_desvio = benford_desvio_global(benford_global),
        clusters       = cluster_results,
    )

    del outlier_iqr, outlier_z, outlier_mad_arr, flags_benford
    del cluster_risco, raw, norm_score, digitos_globais

    log.info("Pipeline completo em %.2fs", time.perf_counter() - t_total)
    return df_result, metricas


# ─────────────────────────────────────────────
# RELATÓRIO
# ─────────────────────────────────────────────

def imprimir_relatorio(df_result: pd.DataFrame, metricas: dict) -> None:
    sep = "=" * 65
    print(f"\n{sep}\n  RELATÓRIO DE DETECÇÃO DE FRAUDE\n{sep}")

    n = metricas["normalidade"]
    print(f"\n📊 NORMALIDADE")
    print(f"   Shapiro p={n['p_shapiro']:.4f} | KS p={n['p_ks']:.4f} | "
          f"Normal={'✅' if n['normal'] else '❌'}")

    print(f"\n🔢 BENFORD MULTI-DÍGITO (Global)")
    for nivel, res in metricas["benford_global"].items():
        status = "🚨" if res.desvio else "✅"
        print(f"   [{nivel.upper():4s}] MAD={res.mad:.5f}  χ²={res.chi2_stat:.2f}  "
              f"p={res.chi2_pvalue:.4f}  Suspeitos={res.digitos_suspeitos}  {status}")
    print(f"\n   Desvio global: {'🚨 SIM' if metricas['benford_desvio'] else '✅ NÃO'}")

    if df_result is not None:
        print(f"\n⚠️  OUTLIERS")
        for col, label in [("outlier_iqr","IQR"),("outlier_z","Z  "),("outlier_mad","MAD")]:
            if col in df_result.columns:
                n_out = df_result[col].sum()
                print(f"   {label}: {n_out:6,} ({df_result[col].mean()*100:.1f}%)")

        clusters = metricas.get("clusters", {})
        if clusters:
            n_risco = sum(1 for c in clusters.values() if c.alto_risco)
            print(f"\n🗂️  CLUSTERS — {len(clusters)} total, {n_risco} alto risco")
            for chave, c in sorted(clusters.items(), key=lambda x: x[1].mad_d1, reverse=True)[:15]:
                status = "🚨 ALTO RISCO" if c.alto_risco else "✅ Normal"
                print(f"   {str(chave)[:55]:55s} | n={c.n:5d} | "
                      f"outliers={c.taxa_outliers*100:5.1f}% | MAD_d1={c.mad_d1:.5f} | {status}")

        print(f"\n🎯 CLASSIFICAÇÃO FINAL")
        for cls in ["ALTA SUSPEITA", "SUSPEITA", "NORMAL"]:
            n_cls = (df_result["classificacao"] == cls).sum()
            print(f"   {cls:14s}: {n_cls:7,} ({n_cls/len(df_result)*100:.1f}%)")

        top = (df_result[df_result["classificacao"] == "ALTA SUSPEITA"]
               .sort_values("score_norm", ascending=False).head(15))
        if not top.empty:
            print(f"\n🔴 TOP SUSPEITOS")
            cols = [c for c in ["fonte","favorecido","cpf_cnpj","orgao","ano",
                                 "valor","score_norm","flag_benford",
                                 "outlier_iqr","outlier_z","outlier_mad"]
                    if c in top.columns]
            display = top[cols].copy()
            if "valor" in display.columns:
                display["valor"] = display["valor"].apply(
                    lambda v: f"R$ {v/1e6:.2f} M" if v >= 1e6
                    else (f"R$ {v/1e3:.1f} k" if v >= 1e3 else f"R$ {v:.2f}"))
            print(display.to_string(index=False))

    # Relatório resumido para modo chunked (sem df_result)
    if "classificacao" in metricas:
        print(f"\n🎯 CLASSIFICAÇÃO FINAL (chunked)")
        total = sum(metricas["classificacao"].values())
        for cls, n in metricas["classificacao"].items():
            print(f"   {cls:14s}: {n:7,} ({n/max(total,1)*100:.1f}%)")

    print(f"\n{sep}\n")


# ─────────────────────────────────────────────
# GERAÇÃO DE DADOS SIMULADOS
# ─────────────────────────────────────────────

def gerar_dataset_simulado(
    qtd: int = 2000, percentual_fraude: float = 0.15,
    digito_forcado: int = 9, seed: int = 42,
) -> pd.DataFrame:
    rng    = np.random.default_rng(seed)
    valores = rng.lognormal(mean=8, sigma=1.2, size=qtd).tolist()
    for i in rng.choice(qtd, int(qtd * percentual_fraude), replace=False):
        s = str(int(valores[i]))
        valores[i] = float(str(digito_forcado) + s[1:]) if len(s) > 1 else float(digito_forcado)
    return pd.DataFrame(dict(
        valor  = valores,
        orgao  = rng.choice(["MEC","MS","MDR","MF"], size=qtd),
        ano    = rng.choice([2021,2022,2023,2024], size=qtd),
        funcao = rng.choice(["Educação","Saúde","Infraestrutura","Defesa"], size=qtd),
    ))


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s  %(levelname)-8s  %(message)s",
                        datefmt="%H:%M:%S")

    df = gerar_dataset_simulado(qtd=3000, percentual_fraude=0.18, digito_forcado=9)
    df_result, metricas = detectar_fraude(df, colunas_cluster=["orgao","ano","funcao"])
    imprimir_relatorio(df_result, metricas)
    df_result.to_csv("resultado_fraude.csv", index=False)
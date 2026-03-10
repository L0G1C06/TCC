"""
Sistema de Detecção de Fraude — Análise de Benford Multi-Dígito
Implementação completa seguindo o modelo matemático do TCC.
"""

from __future__ import annotations

import logging
import math
import time
import warnings
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
from scipy.stats import chi2, kstest, shapiro
from tqdm import tqdm

warnings.filterwarnings("ignore")

# ── Logging ───────────────────────────────────────────────────────────────────

log = logging.getLogger(__name__)

@contextmanager
def _cronometrar(label: str):
    """Loga início, fim e duração de um bloco."""
    log.info("  ▶  %s ...", label)
    t0 = time.perf_counter()
    yield
    log.info("  ✔  %s — %.2fs", label, time.perf_counter() - t0)

# ─────────────────────────────────────────────
# CONFIGURAÇÃO DE PESOS E LIMIARES
# ─────────────────────────────────────────────

WEIGHTS = dict(w1=0.20, w2=0.20, w3=0.20, w4=0.25, w5=0.15)

MAD_THRESHOLDS = dict(
    d1=0.015,   # limiar aceitável para 1º dígito  (NIGRINI 2012)
    d2=0.012,
    d12=0.0012,
    last=0.008,
)

MARGEM_SUSPEITA = 0.02   # desvio mínimo acima do esperado para marcar dígito suspeito
ALPHA           = 0.05   # nível de significância chi²


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
class TransactionResult:
    index: int
    valor: float
    outlier_iqr: bool
    outlier_z: bool
    outlier_mad: bool
    flag_benford: int          # 0-4  (um por nível de dígito)
    cluster_alto_risco: bool
    score_raw: float = 0.0
    score_norm: float = 0.0
    classificacao: str = "NORMAL"


@dataclass
class ClusterResult:
    chave: tuple
    n: int
    taxa_outliers: float
    mad_d1: float
    alto_risco: bool
    benford_d1: Optional[BenfordResult] = None


# ─────────────────────────────────────────────
# ETAPA 1 — PRÉ-PROCESSAMENTO
# ─────────────────────────────────────────────

def preprocessar(df: pd.DataFrame, coluna_valor: str = "valor") -> pd.DataFrame:
    """Remove nulos e valores <= 0."""
    antes = len(df)
    df = df.dropna(subset=[coluna_valor])
    df = df[df[coluna_valor] > 0].copy()
    df = df.reset_index(drop=True)
    removidos = antes - len(df)
    log.info("    Pré-processamento: %d → %d registros (%d removidos)",
             antes, len(df), removidos)
    return df


# ─────────────────────────────────────────────
# ETAPA 2 — DETECÇÃO INDIVIDUAL DE OUTLIERS
# ─────────────────────────────────────────────

def detectar_outliers(X: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Retorna (outlier_iqr, outlier_z, outlier_mad) como arrays bool."""

    # IQR
    Q1, Q3 = np.percentile(X, 25), np.percentile(X, 75)
    IQR = Q3 - Q1
    outlier_iqr = (X < Q1 - 1.5 * IQR) | (X > Q3 + 1.5 * IQR)

    # Z-score
    media, desvio = X.mean(), X.std()
    z = (X - media) / (desvio if desvio > 0 else 1)
    outlier_z = np.abs(z) > 3

    # MAD robusto (modified Z-score)
    mediana = np.median(X)
    mad = np.median(np.abs(X - mediana)) or 1e-9
    outlier_mad = np.abs(0.6745 * (X - mediana) / mad) > 3.5

    log.info("    Outliers — IQR: %d (%.1f%%)  Z: %d (%.1f%%)  MAD: %d (%.1f%%)",
             outlier_iqr.sum(), outlier_iqr.mean() * 100,
             outlier_z.sum(),   outlier_z.mean()   * 100,
             outlier_mad.sum(), outlier_mad.mean()  * 100)

    return outlier_iqr, outlier_z, outlier_mad


# ─────────────────────────────────────────────
# ETAPA 3 — TESTES DE NORMALIDADE
# ─────────────────────────────────────────────

def testar_normalidade(X: np.ndarray) -> dict:
    """Shapiro-Wilk (amostras <= 5000) + KS."""
    sample = X if len(X) <= 5000 else np.random.choice(X, 5000, replace=False)
    _, p_shapiro = shapiro(sample)
    _, p_ks      = kstest((X - X.mean()) / (X.std() or 1), "norm")
    normal = p_shapiro > ALPHA and p_ks > ALPHA
    log.info("    Normalidade — Shapiro p=%.4f  KS p=%.4f  normal=%s",
             p_shapiro, p_ks, normal)
    return dict(p_shapiro=p_shapiro, p_ks=p_ks, normal=normal)


# ─────────────────────────────────────────────
# EXTRAÇÃO DE DÍGITOS — VETORIZADA
# ─────────────────────────────────────────────

def _extrair_digitos_vetorizado(X: np.ndarray) -> dict[str, np.ndarray]:
    """
    Extrai os 4 níveis de dígito de uma vez para todo o array.
    Retorna dict com arrays int64 para d1, d2, d12, last.
    Valores sem dígito suficiente recebem -1 (sentinela, filtrado depois).
    """
    inteiros = np.abs(X).astype(np.int64)

    with np.errstate(divide="ignore", invalid="ignore"):
        n_digits = np.where(inteiros > 0, np.floor(np.log10(inteiros)).astype(int) + 1, 1)

    pot  = (10 ** (n_digits - 1)).astype(np.int64)
    pot2 = (10 ** np.maximum(n_digits - 2, 0)).astype(np.int64)

    d1   = (inteiros // pot) % 10
    d2   = np.where(n_digits >= 2, (inteiros // (pot // 10)) % 10, -1)
    d12  = np.where(n_digits >= 2, (inteiros // pot2) % 100,       -1)
    last = inteiros % 10

    return dict(d1=d1, d2=d2, d12=d12, last=last)


# ─────────────────────────────────────────────
# FREQUÊNCIAS ESPERADAS
# ─────────────────────────────────────────────

def freq_esperada_d1() -> dict:
    return {d: math.log10(1 + 1 / d) for d in range(1, 10)}


def freq_esperada_d2() -> dict:
    return {d: sum(math.log10(1 + 1 / (10 * k + d)) for k in range(1, 10))
            for d in range(0, 10)}


def freq_esperada_d12() -> dict:
    return {n: math.log10(1 + 1 / n) for n in range(10, 100)}


def freq_esperada_last() -> dict:
    return {d: 0.1 for d in range(0, 10)}


# ─────────────────────────────────────────────
# NÚCLEO BENFORD — calcula MAD, chi², dígitos suspeitos
# ─────────────────────────────────────────────

def _analisar_distribuicao(valores: np.ndarray | list, freq_exp: dict, label: str) -> BenfordResult:
    arr   = np.asarray(valores)
    arr   = arr[arr >= 0]           # remove sentinela -1
    total = len(arr)

    if total == 0:
        return BenfordResult(0, 0, 1, {}, freq_exp, [], False)

    digitos  = sorted(freq_exp.keys())
    counts   = Counter(arr.tolist())
    freq_obs = {d: counts.get(d, 0) / total for d in digitos}

    mad = float(np.mean([abs(freq_obs[d] - freq_exp[d]) for d in digitos]))

    chi2_stat = sum(
        ((freq_obs[d] - freq_exp[d]) ** 2) / freq_exp[d]
        for d in digitos if freq_exp[d] > 0
    ) * total

    p_value = 1 - chi2.cdf(chi2_stat, len(digitos) - 1)

    digitos_suspeitos = [d for d in digitos if freq_obs[d] > freq_exp[d] + MARGEM_SUSPEITA]
    desvio = mad > MAD_THRESHOLDS.get(label, 0.015) or p_value < ALPHA

    return BenfordResult(
        mad=mad,
        chi2_stat=chi2_stat,
        chi2_pvalue=p_value,
        freq_obs=freq_obs,
        freq_exp=freq_exp,
        digitos_suspeitos=digitos_suspeitos,
        desvio=desvio,
    )


# ─────────────────────────────────────────────
# ETAPA 4 — BENFORD MULTI-DÍGITO
# ─────────────────────────────────────────────

def analisar_benford_completo(
    valores: list | np.ndarray,
    digitos_vetorizados: Optional[dict[str, np.ndarray]] = None,
) -> dict[str, BenfordResult]:
    """
    Executa análise Benford nos 4 níveis de dígito.

    Se `digitos_vetorizados` for fornecido (dict retornado por
    _extrair_digitos_vetorizado), reutiliza os arrays já calculados —
    útil no loop de clusters para evitar reprocessamento.
    """
    if digitos_vetorizados is None:
        digitos_vetorizados = _extrair_digitos_vetorizado(np.asarray(valores, dtype=np.float64))

    d = digitos_vetorizados
    return {
        "d1":   _analisar_distribuicao(d["d1"],   freq_esperada_d1(),   "d1"),
        "d2":   _analisar_distribuicao(d["d2"],   freq_esperada_d2(),   "d2"),
        "d12":  _analisar_distribuicao(d["d12"],  freq_esperada_d12(),  "d12"),
        "last": _analisar_distribuicao(d["last"], freq_esperada_last(), "last"),
    }


# ─────────────────────────────────────────────
# ETAPA 5 — DESVIO GLOBAL BENFORD
# ─────────────────────────────────────────────

def benford_desvio_global(resultados: dict[str, BenfordResult]) -> bool:
    return any(r.desvio for r in resultados.values())


# ─────────────────────────────────────────────
# ETAPA 6 — FLAGS POR TRANSAÇÃO (VETORIZADA)
# ─────────────────────────────────────────────

def calcular_flags_benford_vetorizado(
    digitos: dict[str, np.ndarray],
    benford_global: dict[str, BenfordResult],
) -> np.ndarray:
    """
    Substitui o loop Python de flag_benford_transacao por operações NumPy.

    Para cada nível usa np.isin() — O(n) com lookup em hash set interno —
    em vez de chamar uma função Python por transação.
    """
    n     = len(digitos["d1"])
    flags = np.zeros(n, dtype=np.int32)

    for nivel, arr in digitos.items():
        suspeitos = np.array(benford_global[nivel].digitos_suspeitos, dtype=np.int64)
        if suspeitos.size == 0:
            continue
        valido   = arr >= 0                          # exclui sentinela -1
        suspeito = np.isin(arr, suspeitos) & valido
        flags   += suspeito.astype(np.int32)

    return flags


# Mantido para compatibilidade com testes unitários
def flag_benford_transacao(valor: float, resultados: dict[str, BenfordResult]) -> int:
    s = str(int(abs(valor)))
    mapa = {
        "d1":   int(s[0]),
        "d2":   int(s[1]) if len(s) >= 2 else -1,
        "d12":  int(s[:2]) if len(s) >= 2 else -1,
        "last": int(s[-1]),
    }
    return sum(
        1 for nivel, d in mapa.items()
        if d >= 0 and d in resultados[nivel].digitos_suspeitos
    )


# ─────────────────────────────────────────────
# ETAPA 7 — ANÁLISE POR CLUSTER
# ─────────────────────────────────────────────

def analisar_clusters(
    df: pd.DataFrame,
    colunas_cluster: list[str],
    coluna_valor: str,
    outlier_mask: np.ndarray,
    digitos_globais: dict[str, np.ndarray],
    limiar_mad: float = 0.015,
    limiar_taxa_outliers: float = 0.20,
) -> dict[tuple, ClusterResult]:
    """
    Analisa cada cluster.

    Recebe `digitos_globais` para fatiar os arrays por índice em vez de
    recalcular a extração de dígitos dentro de cada grupo.
    """
    grupos       = list(df.groupby(colunas_cluster))
    resultados:  dict[tuple, ClusterResult] = {}
    n_alto_risco = 0

    for chave, grupo in tqdm(grupos, desc="Clusters", unit="cluster"):
        idx  = grupo.index.to_numpy()
        vals = grupo[coluna_valor].to_numpy()

        digitos_cluster = {k: v[idx] for k, v in digitos_globais.items()}
        benford         = analisar_benford_completo(vals, digitos_vetorizados=digitos_cluster)

        taxa_outliers = outlier_mask[idx].mean()
        mad_d1        = benford["d1"].mad
        alto_risco    = (mad_d1 > limiar_mad) and (taxa_outliers > limiar_taxa_outliers)

        if alto_risco:
            n_alto_risco += 1

        chave_t = chave if isinstance(chave, tuple) else (chave,)
        resultados[chave_t] = ClusterResult(
            chave=chave_t,
            n=len(vals),
            taxa_outliers=taxa_outliers,
            mad_d1=mad_d1,
            alto_risco=alto_risco,
            benford_d1=benford["d1"],
        )

    log.info("    Clusters: %d total, %d alto risco", len(resultados), n_alto_risco)
    return resultados


def mapear_cluster_risco(
    df: pd.DataFrame,
    colunas_cluster: list[str],
    cluster_results: dict[tuple, ClusterResult],
) -> np.ndarray:
    """
    Mapeia alto_risco de volta para o DataFrame via merge vetorizado,
    em vez de iterar sobre cada cluster com máscara booleana.
    """
    mapa = {chave: res.alto_risco for chave, res in cluster_results.items()}

    chave_col = df[colunas_cluster].apply(
        lambda row: tuple(row) if len(colunas_cluster) > 1 else (row.iloc[0],),
        axis=1,
    )
    return chave_col.map(mapa).fillna(False).to_numpy(dtype=bool)


# ─────────────────────────────────────────────
# ETAPA 8 — SCORE FINAL
# ─────────────────────────────────────────────

def calcular_scores(
    outlier_iqr: np.ndarray,
    outlier_z: np.ndarray,
    outlier_mad_arr: np.ndarray,
    flags_benford: np.ndarray,
    cluster_risco: np.ndarray,
    weights: dict = WEIGHTS,
) -> tuple[np.ndarray, np.ndarray]:

    flag_norm = flags_benford / 4.0

    raw = (
        weights["w1"] * outlier_iqr.astype(float)
      + weights["w2"] * outlier_z.astype(float)
      + weights["w3"] * outlier_mad_arr.astype(float)
      + weights["w4"] * flag_norm
      + weights["w5"] * cluster_risco.astype(float)
    )

    mn, mx     = raw.min(), raw.max()
    norm_score = (raw - mn) / (mx - mn + 1e-12)

    return raw, norm_score


def classificar(score: float) -> str:
    if score >= 0.7:
        return "ALTA SUSPEITA"
    elif score >= 0.4:
        return "SUSPEITA"
    return "NORMAL"


def _classificar_array(norm_score: np.ndarray) -> np.ndarray:
    """Versão vetorizada de classificar() — evita loop Python."""
    result = np.full(len(norm_score), "NORMAL", dtype=object)
    result[norm_score >= 0.4] = "SUSPEITA"
    result[norm_score >= 0.7] = "ALTA SUSPEITA"
    return result


# ─────────────────────────────────────────────
# PIPELINE PRINCIPAL
# ─────────────────────────────────────────────

def detectar_fraude(
    df: pd.DataFrame,
    coluna_valor: str = "valor",
    colunas_cluster: Optional[list[str]] = None,
) -> tuple[pd.DataFrame, dict]:
    """
    Executa o pipeline completo de detecção de fraude.

    Parâmetros
    ----------
    df : DataFrame com ao menos a coluna de valor.
    coluna_valor : nome da coluna monetária.
    colunas_cluster : colunas para agrupamento (ex: ['orgao','ano','funcao']).

    Retorna
    -------
    df_result : DataFrame original enriquecido com todas as flags e scores.
    metricas  : dicionário com resultados agregados (Benford, clusters, normalidade).
    """
    t_total = time.perf_counter()
    bar = tqdm(total=7, desc="Pipeline", unit="etapa", ncols=80, leave=True)

    def step(label: str) -> None:
        bar.set_postfix_str(label)
        bar.update(1)

    # ── 1. Pré-processamento ──────────────────────────────────────────
    step("pré-processamento")
    with _cronometrar("Pré-processamento"):
        df = preprocessar(df, coluna_valor)
        X  = df[coluna_valor].values

    # ── 2. Extração de dígitos (uma única vez para todo o array) ──────
    step("extração de dígitos")
    with _cronometrar("Extração de dígitos"):
        digitos_globais = _extrair_digitos_vetorizado(X)
        log.info("    Arrays extraídos: d1, d2, d12, last — %d registros", len(X))

    # ── 3. Outliers ───────────────────────────────────────────────────
    step("outliers")
    with _cronometrar("Outliers"):
        outlier_iqr, outlier_z, outlier_mad_arr = detectar_outliers(X)

    # ── 4. Normalidade ────────────────────────────────────────────────
    step("normalidade")
    with _cronometrar("Normalidade"):
        norm_result = testar_normalidade(X)

    # ── 5. Benford global + flags vetorizados ─────────────────────────
    step("benford global + flags")
    with _cronometrar("Benford global"):
        benford_global = analisar_benford_completo(X, digitos_vetorizados=digitos_globais)
        for nivel, res in benford_global.items():
            log.info("    [%s] MAD=%.5f  χ²=%.2f  p=%.4f  suspeitos=%s  desvio=%s",
                     nivel.upper(), res.mad, res.chi2_stat, res.chi2_pvalue,
                     res.digitos_suspeitos, res.desvio)

    with _cronometrar("Flags Benford por transação (vetorizado)"):
        flags_benford = calcular_flags_benford_vetorizado(digitos_globais, benford_global)
        log.info("    Transações com flag > 0: %d (%.1f%%)",
                 (flags_benford > 0).sum(), (flags_benford > 0).mean() * 100)

    # ── 6. Clusters ───────────────────────────────────────────────────
    step("clusters")
    with _cronometrar("Clusters"):
        if colunas_cluster and all(c in df.columns for c in colunas_cluster):
            outlier_any = outlier_iqr | outlier_z | outlier_mad_arr
            log.info("    Agrupando por: %s — %d grupos únicos",
                     colunas_cluster,
                     df.groupby(colunas_cluster).ngroups)
            cluster_results = analisar_clusters(
                df, colunas_cluster, coluna_valor, outlier_any, digitos_globais
            )
            cluster_risco = mapear_cluster_risco(df, colunas_cluster, cluster_results)
            log.info("    Registros em cluster alto risco: %d (%.1f%%)",
                     cluster_risco.sum(), cluster_risco.mean() * 100)
        else:
            log.info("    Clusters ignorados (sem colunas de cluster válidas).")
            cluster_results = {}
            cluster_risco   = np.zeros(len(df), dtype=bool)

    # ── 7. Score final e classificação ────────────────────────────────
    step("score + classificação")
    with _cronometrar("Score final"):
        raw, norm_score = calcular_scores(
            outlier_iqr, outlier_z, outlier_mad_arr, flags_benford, cluster_risco
        )
        classificacao = _classificar_array(norm_score)
        for cls in ["ALTA SUSPEITA", "SUSPEITA", "NORMAL"]:
            n = (classificacao == cls).sum()
            log.info("    %s: %d (%.1f%%)", cls, n, n / len(df) * 100)

    bar.close()

    # ── Montar resultado ──────────────────────────────────────────────
    df_result = df.copy()
    df_result["outlier_iqr"]        = outlier_iqr
    df_result["outlier_z"]          = outlier_z
    df_result["outlier_mad"]        = outlier_mad_arr
    df_result["flag_benford"]       = flags_benford
    df_result["cluster_alto_risco"] = cluster_risco
    df_result["score_raw"]          = raw
    df_result["score_norm"]         = norm_score
    df_result["classificacao"]      = classificacao

    metricas = dict(
        normalidade=norm_result,
        benford_global={k: v for k, v in benford_global.items()},
        benford_desvio=benford_desvio_global(benford_global),
        clusters=cluster_results,
    )

    log.info("Pipeline completo em %.2fs", time.perf_counter() - t_total)
    return df_result, metricas


# ─────────────────────────────────────────────
# RELATÓRIO
# ─────────────────────────────────────────────

def imprimir_relatorio(df_result: pd.DataFrame, metricas: dict) -> None:
    sep = "=" * 65

    print(f"\n{sep}")
    print("  RELATÓRIO DE DETECÇÃO DE FRAUDE")
    print(sep)

    n = metricas["normalidade"]
    print(f"\n📊 NORMALIDADE")
    print(f"   Shapiro p={n['p_shapiro']:.4f} | KS p={n['p_ks']:.4f} | "
          f"Normal={'✅' if n['normal'] else '❌'}")

    print(f"\n🔢 BENFORD MULTI-DÍGITO (Global)")
    for nivel, res in metricas["benford_global"].items():
        status = "🚨" if res.desvio else "✅"
        print(f"   [{nivel.upper():4s}] MAD={res.mad:.5f}  "
              f"χ²={res.chi2_stat:.2f}  p={res.chi2_pvalue:.4f}  "
              f"Suspeitos={res.digitos_suspeitos}  {status}")
    print(f"\n   Desvio global: {'🚨 SIM' if metricas['benford_desvio'] else '✅ NÃO'}")

    print(f"\n⚠️  OUTLIERS")
    for col, label in [("outlier_iqr", "IQR"), ("outlier_z", "Z  "), ("outlier_mad", "MAD")]:
        n_out = df_result[col].sum()
        pct   = df_result[col].mean() * 100
        print(f"   {label}: {n_out:6,} ({pct:.1f}%)")

    clusters = metricas.get("clusters", {})
    if clusters:
        n_risco = sum(1 for c in clusters.values() if c.alto_risco)
        print(f"\n🗂️  CLUSTERS — {len(clusters)} total, {n_risco} alto risco")
        for chave, c in sorted(clusters.items(), key=lambda x: x[1].mad_d1, reverse=True)[:15]:
            status = "🚨 ALTO RISCO" if c.alto_risco else "✅ Normal"
            print(f"   {str(chave)[:55]:55s} | n={c.n:5d} | "
                  f"outliers={c.taxa_outliers*100:5.1f}% | "
                  f"MAD_d1={c.mad_d1:.5f} | {status}")

    print(f"\n🎯 CLASSIFICAÇÃO FINAL")
    for cls in ["ALTA SUSPEITA", "SUSPEITA", "NORMAL"]:
        n_cls = (df_result["classificacao"] == cls).sum()
        print(f"   {cls:14s}: {n_cls:7,} ({n_cls/len(df_result)*100:.1f}%)")

    top = (df_result[df_result["classificacao"] == "ALTA SUSPEITA"]
           .sort_values("score_norm", ascending=False)
           .head(15))

    if not top.empty:
        print(f"\n🔴 TOP SUSPEITOS")
        ID_COLS    = ["fonte", "favorecido", "cpf_cnpj", "orgao", "ano"]
        SCORE_COLS = ["valor", "score_norm", "flag_benford",
                      "outlier_iqr", "outlier_z", "outlier_mad"]
        cols    = [c for c in ID_COLS + SCORE_COLS if c in top.columns]
        display = top[cols].copy()
        if "valor" in display.columns:
            display["valor"] = display["valor"].apply(
                lambda v: f"R$ {v/1_000_000:.2f} M" if v >= 1_000_000
                else (f"R$ {v/1_000:.1f} k" if v >= 1_000 else f"R$ {v:.2f}")
            )
        print(display.to_string(index=False))

    print(f"\n{sep}\n")


# ─────────────────────────────────────────────
# GERAÇÃO DE DADOS SIMULADOS
# ─────────────────────────────────────────────

def gerar_dataset_simulado(
    qtd: int = 2000,
    percentual_fraude: float = 0.15,
    digito_forcado: int = 9,
    seed: int = 42,
) -> pd.DataFrame:
    """Gera DataFrame simulado com colunas extras para teste de clusters."""
    rng = np.random.default_rng(seed)
    valores = rng.lognormal(mean=8, sigma=1.2, size=qtd).tolist()

    idx_fraude = rng.choice(qtd, int(qtd * percentual_fraude), replace=False)
    for i in idx_fraude:
        s = str(int(valores[i]))
        valores[i] = float(str(digito_forcado) + s[1:]) if len(s) > 1 else float(digito_forcado)

    return pd.DataFrame(dict(
        valor  = valores,
        orgao  = rng.choice(["MEC", "MS", "MDR", "MF"], size=qtd),
        ano    = rng.choice([2021, 2022, 2023, 2024], size=qtd),
        funcao = rng.choice(["Educação", "Saúde", "Infraestrutura", "Defesa"], size=qtd),
    ))


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    print("Gerando dataset simulado...")
    df = gerar_dataset_simulado(qtd=3000, percentual_fraude=0.18, digito_forcado=9)
    print(f"Total de registros: {len(df)}")
    print(df.head())

    df_result, metricas = detectar_fraude(
        df,
        coluna_valor="valor",
        colunas_cluster=["orgao", "ano", "funcao"],
    )

    imprimir_relatorio(df_result, metricas)

    output_csv = "resultado_fraude.csv"
    df_result.to_csv(output_csv, index=False)
    print(f"Resultado exportado para: {output_csv}")
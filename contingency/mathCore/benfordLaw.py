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
from typing import Iterator, Literal, Optional

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

# ── PATCH M2: limiares Nigrini 2012 com dois patamares (conforme / alerta / crítico) ──
# Substituiu o dict plano MAD_THRESHOLDS = dict(d1=0.015, ...) por estrutura aninhada.
# Mantido MAD_THRESHOLDS_LEGACY para não quebrar código externo que usava o formato antigo.
MAD_THRESHOLDS: dict[str, dict[str, float]] = {
    "d1":   {"conforme": 0.006, "alerta": 0.012},
    "d2":   {"conforme": 0.006, "alerta": 0.010},
    "d12":  {"conforme": 0.0012,"alerta": 0.0018},
    "last": {"conforme": 0.006, "alerta": 0.010},
}
MAD_THRESHOLDS_LEGACY = dict(d1=0.015, d2=0.012, d12=0.0012, last=0.008)  # compatibilidade

MARGEM_SUSPEITA = 0.02
ALPHA           = 0.05
CHUNK_SIZE      = 500_000
CLUSTER_BATCH_SIZE = 50

# ── PATCH M2: tipo do flag tri-estado ─────────────────────────────────────────
FlagEstado = Literal["conforme", "alerta", "crítico"]


def _calcular_flag(mad: float, pvalue: float, nivel: str) -> FlagEstado:
    """Regra única de classificação: MAD (magnitude) + p-valor (significância)."""
    t = MAD_THRESHOLDS.get(nivel, MAD_THRESHOLDS["d1"])
    if mad > t["alerta"] or pvalue < ALPHA / 5:
        return "crítico"
    if mad > t["conforme"] or pvalue < ALPHA:
        return "alerta"
    return "conforme"


# ─────────────────────────────────────────────
# ESTRUTURAS DE DADOS
# ─────────────────────────────────────────────

# ── PATCH M2: BenfordResult ganhou js_divergence + flag tri-estado ────────────
@dataclass
class BenfordResult:
    mad: float
    chi2_stat: float
    chi2_pvalue: float
    freq_obs: dict
    freq_exp: dict
    digitos_suspeitos: list
    desvio: bool
    # novos campos — opcionais para não quebrar instanciações legadas
    js_divergence: float = 0.0
    flag: FlagEstado = "conforme"

    def __post_init__(self) -> None:
        # Sempre recalcula flag a partir de mad + pvalue para garantir consistência
        nivel = getattr(self, "_nivel", "d1")
        self.flag = _calcular_flag(self.mad, self.chi2_pvalue, nivel)
        self.desvio = self.flag != "conforme"

    @property
    def emoji(self) -> str:
        return {"conforme": "✅", "alerta": "⚠️", "crítico": "🚨"}[self.flag]


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
    Extrai d1, d2, d12, last para todo o array de uma vez.
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
# NÚCLEO BENFORD
# ─────────────────────────────────────────────

# ── PATCH M2: _analisar_distribuicao calcula JS + flag tri-estado ─────────────
def _analisar_distribuicao(valores: np.ndarray, freq_exp: dict, nivel: str) -> BenfordResult:
    arr   = np.asarray(valores)
    arr   = arr[arr >= 0]
    total = len(arr)

    if total == 0:
        r = BenfordResult(0, 0, 1, {}, freq_exp, [], False)
        r._nivel = nivel
        r.__post_init__()
        return r

    digitos  = sorted(freq_exp.keys())
    counts   = Counter(arr.tolist())
    freq_obs = {d: counts.get(d, 0) / total for d in digitos}
    mad      = float(np.mean([abs(freq_obs[d] - freq_exp[d]) for d in digitos]))

    chi2_stat = sum(
        ((freq_obs[d] - freq_exp[d]) ** 2) / freq_exp[d]
        for d in digitos if freq_exp[d] > 0
    ) * total

    p_value = float(1 - chi2.cdf(chi2_stat, len(digitos) - 1))

    # Jensen-Shannon divergence (simétrica, bounded [0, 1])
    js = 0.0
    for d in digitos:
        m = (freq_obs[d] + freq_exp[d]) / 2
        if freq_obs[d] > 0 and m > 0:
            js += freq_obs[d] * math.log2(freq_obs[d] / m)
        if freq_exp[d] > 0 and m > 0:
            js += freq_exp[d] * math.log2(freq_exp[d] / m)
    js_divergence = float(js / 2)

    digitos_suspeitos = [d for d in digitos if abs(freq_obs[d] - freq_exp[d]) > MARGEM_SUSPEITA]

    r = BenfordResult(
        mad=mad, chi2_stat=chi2_stat, chi2_pvalue=p_value,
        freq_obs=freq_obs, freq_exp=freq_exp,
        digitos_suspeitos=digitos_suspeitos,
        desvio=False,           # recalculado em __post_init__
        js_divergence=js_divergence,
    )
    r._nivel = nivel
    r.__post_init__()
    return r


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

    # ── PATCH M2: finalizar() agora calcula JS + flag tri-estado ──────────────
    def finalizar(self) -> dict[str, BenfordResult]:
        """Calcula BenfordResult para cada nível a partir das contagens acumuladas."""
        resultados = {}
        for nivel, freq_exp in _FREQ_EXP.items():
            total = self._total[nivel]
            if total == 0:
                r = BenfordResult(0, 0, 1, {}, freq_exp, [], False)
                r._nivel = nivel
                r.__post_init__()
                resultados[nivel] = r
                continue

            digitos  = sorted(freq_exp.keys())
            freq_obs = {d: self._counts[nivel].get(d, 0) / total for d in digitos}
            mad      = float(np.mean([abs(freq_obs[d] - freq_exp[d]) for d in digitos]))

            chi2_stat = sum(
                ((freq_obs[d] - freq_exp[d]) ** 2) / freq_exp[d]
                for d in digitos if freq_exp[d] > 0
            ) * total

            p_value = float(1 - chi2.cdf(chi2_stat, len(digitos) - 1))

            # Jensen-Shannon divergence
            js = 0.0
            for d in digitos:
                m = (freq_obs[d] + freq_exp[d]) / 2
                if freq_obs[d] > 0 and m > 0:
                    js += freq_obs[d] * math.log2(freq_obs[d] / m)
                if freq_exp[d] > 0 and m > 0:
                    js += freq_exp[d] * math.log2(freq_exp[d] / m)
            js_div = float(js / 2)

            digitos_suspeitos = [d for d in digitos
                                  if abs(freq_obs[d] - freq_exp[d]) > MARGEM_SUSPEITA]

            r = BenfordResult(
                mad=mad, chi2_stat=chi2_stat, chi2_pvalue=p_value,
                freq_obs=freq_obs, freq_exp=freq_exp,
                digitos_suspeitos=digitos_suspeitos,
                desvio=False,
                js_divergence=js_div,
            )
            r._nivel = nivel
            r.__post_init__()
            resultados[nivel] = r

            log.info(
                "    [%s] MAD=%.5f  χ²=%.2f  p=%.4f  JS=%.5f  suspeitos=%s  %s",
                nivel.upper(), mad, chi2_stat, p_value, js_div,
                digitos_suspeitos, r.emoji,
            )

        return resultados


# ─────────────────────────────────────────────
# API PÚBLICA — compatibilidade total
# ─────────────────────────────────────────────

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


def flag_benford_transacao(valor: float, resultados: dict[str, BenfordResult]) -> int:
    """Compatibilidade com testes unitários."""
    s = str(int(abs(valor)))
    mapa = {"d1": int(s[0]), "d2": int(s[1]) if len(s) >= 2 else -1,
            "d12": int(s[:2]) if len(s) >= 2 else -1, "last": int(s[-1])}
    return sum(1 for nv, d in mapa.items()
               if d >= 0 and d in resultados[nv].digitos_suspeitos)


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


# ─────────────────────────────────────────────
# PATCH M4 — SCORE COMPOSTO + LATIN HYPERCUBE SAMPLING
# ─────────────────────────────────────────────

@dataclass
class ComponentesScore:
    """Os 5 componentes brutos de uma entidade, normalizados para [0, 1]."""
    mad_medio:       float
    chi2_pvalue_inv: float   # 1 − pvalue médio dos χ²
    js_medio:        float
    taxa_outliers:   float
    taxa_cluster:    float

    @property
    def vetor(self) -> np.ndarray:
        return np.array([
            self.mad_medio, self.chi2_pvalue_inv,
            self.js_medio, self.taxa_outliers, self.taxa_cluster,
        ])


@dataclass
class SensitivityResult:
    """Resultado da análise de sensibilidade LHS."""
    ranking_medio:     list
    estabilidade_top3: dict
    pesos_medios:      dict
    pesos_std:         dict
    n_amostras:        int

    def resumo(self) -> str:
        linhas = [f"Sensibilidade LHS — {self.n_amostras} cenários", "Estabilidade top-3:"]
        for ent, est in sorted(self.estabilidade_top3.items(), key=lambda x: -x[1]):
            bar = "█" * int(est * 20)
            linhas.append(f"  {str(ent)[:40]:40s} {est*100:5.1f}%  {bar}")
        return "\n".join(linhas)


def analisar_sensibilidade_lhs(
    componentes_por_entidade: dict,
    n_amostras: int = 500,
    seed: int = 42,
) -> SensitivityResult:
    """
    Gera n_amostras combinações de pesos via Latin Hypercube Sampling
    com restrição Σwi = 1 e calcula a estabilidade de ranking por órgão.

    Resultado publicável: top-3 estável em > 80% dos cenários.
    """
    try:
        from scipy.stats.qmc import LatinHypercube
    except ImportError:
        raise ImportError("scipy >= 1.7 necessário. pip install scipy")

    entidades = list(componentes_por_entidade.keys())
    n_ent     = len(entidades)
    if n_ent < 2:
        return SensitivityResult(
            ranking_medio=entidades,
            estabilidade_top3={e: 1.0 for e in entidades},
            pesos_medios={}, pesos_std={}, n_amostras=0,
        )

    X = np.array([componentes_por_entidade[e].vetor for e in entidades])  # (n_ent, 5)

    sampler      = LatinHypercube(d=5, seed=seed)
    raw_samples  = sampler.random(n=n_amostras)                           # (n_amostras, 5)
    pesos_matrix = raw_samples / raw_samples.sum(axis=1, keepdims=True)   # normaliza Σ=1

    scores_matrix  = pesos_matrix @ X.T                                   # (n_amostras, n_ent)
    posicao_matrix = np.argsort(np.argsort(-scores_matrix, axis=1), axis=1)

    top3_counts  = (posicao_matrix < 3).sum(axis=0)
    estabilidade = {e: float(top3_counts[i] / n_amostras) for i, e in enumerate(entidades)}

    pesos_medios_arr = pesos_matrix.mean(axis=0)
    scores_medios    = X @ pesos_medios_arr
    ranking_medio    = [entidades[i] for i in np.argsort(-scores_medios)]

    nomes = ["w_mad", "w_chi2", "w_js", "w_outlier", "w_cluster"]
    pm    = {n: float(pesos_medios_arr[i]) for i, n in enumerate(nomes)}
    ps    = {n: float(pesos_matrix.std(axis=0)[i]) for i, n in enumerate(nomes)}

    return SensitivityResult(
        ranking_medio=ranking_medio, estabilidade_top3=estabilidade,
        pesos_medios=pm, pesos_std=ps, n_amostras=n_amostras,
    )


# ─────────────────────────────────────────────
# PATCH — ELIGIBILITY FILTER
# ─────────────────────────────────────────────

@dataclass
class EligibilityResult:
    """
    Triagem de elegibilidade de uma partição para análise de Benford.

    decisao: 'elegível' | 'elegível_com_ressalva' | 'inelegível'
    """
    decisao:               str
    n_total:               int
    n_validos:             int
    ordens_magnitude:      int
    pct_nulos_zerados:     float
    truncamento_detectado: bool
    motivo_inelegivel:     Optional[str] = None

    @property
    def elegivel(self) -> bool:
        return self.decisao != "inelegível"


def verificar_elegibilidade(
    valores: np.ndarray,
    min_registros: int = 1_000,
    min_ordens: int = 3,
    max_pct_nulos: float = 0.50,
    limiar_truncamento: float = 0.30,
) -> EligibilityResult:
    """
    Verifica se uma série de valores é elegível para análise de Benford.
    Salvo no _eligibility.json da partição para não repetir a cada execução.
    """
    n_total   = len(valores)
    positivos = valores[np.isfinite(valores) & (valores > 0)]
    n_validos = len(positivos)
    pct_nulos = (n_total - n_validos) / max(n_total, 1)

    n_ordens = 0
    if n_validos > 0:
        ordens   = np.floor(np.log10(positivos)).astype(int)
        n_ordens = int(np.unique(ordens).size)

    truncamento = False
    if n_validos > 0:
        inteiros    = positivos.astype(np.int64)
        truncamento = bool(np.isin(inteiros % 10, [0, 5]).mean() > limiar_truncamento)

    motivo = None
    if n_validos < min_registros:
        decisao = "inelegível"
        motivo  = f"n_validos={n_validos} < min={min_registros}"
    elif n_ordens < min_ordens:
        decisao = "inelegível"
        motivo  = f"ordens_magnitude={n_ordens} < min={min_ordens}"
    elif pct_nulos > max_pct_nulos:
        decisao = "inelegível"
        motivo  = f"pct_nulos={pct_nulos:.1%} > max={max_pct_nulos:.1%}"
    elif truncamento or pct_nulos > 0.20:
        decisao = "elegível_com_ressalva"
    else:
        decisao = "elegível"

    return EligibilityResult(
        decisao=decisao, n_total=n_total, n_validos=n_validos,
        ordens_magnitude=n_ordens, pct_nulos_zerados=round(pct_nulos, 4),
        truncamento_detectado=truncamento, motivo_inelegivel=motivo,
    )


# ─────────────────────────────────────────────
# PATCH — THRESHOLD / BUNCHING (Lei 14.133/2021)
# ─────────────────────────────────────────────

@dataclass
class LimiarLegal:
    valor:      float
    descricao:  str
    modalidade: str
    lei:        str

LIMIARES_LEGAIS: dict[str, LimiarLegal] = {
    "dispensa_eletro_bens": LimiarLegal(
        50_000, "Dispensa eletrônica — bens e serviços",
        "Dispensa", "Lei 14.133/2021, art. 75, I",
    ),
    "dispensa_eletro_obras": LimiarLegal(
        100_000, "Dispensa eletrônica — obras",
        "Dispensa", "Lei 14.133/2021, art. 75, §1º",
    ),
    "pregao_eletronico": LimiarLegal(
        1_500_000, "Pregão eletrônico",
        "Pregão", "Lei 14.133/2021, art. 6º, XLI",
    ),
}


@dataclass
class BunchingResult:
    entidade:      str
    chave_limiar:  str
    limiar:        LimiarLegal
    n_observacoes: int
    iab:           float   # Índice de Acumulação Abaixo
    pvalue:        float
    suspeito:      bool

    @property
    def nivel_suspeicao(self) -> str:
        if self.iab > 3.0 and self.pvalue < 0.05: return "alto"
        if self.iab > 2.0 and self.pvalue < 0.10: return "moderado"
        return "normal"


def _integrar_kde(kde, a: float, b: float, n: int = 200) -> float:
    pts  = np.linspace(a, b, n)
    vals = kde(pts)
    return float(np.trapezoid(vals, pts) if hasattr(np, "trapezoid") else np.trapz(vals, pts))


def analisar_bunching(
    valores: np.ndarray,
    entidade: str = "global",
    largura: float = 0.15,
    n_bootstrap: int = 300,
    min_obs: int = 30,
    seed: int = 42,
) -> list[BunchingResult]:
    """
    Detecta acumulação de valores logo abaixo de limiares legais via KDE + IAB.
    IAB > 2.0 e p < 0.05 → suspeito.
    """
    from scipy.stats import gaussian_kde

    X   = np.asarray(valores, dtype=np.float64)
    X   = X[np.isfinite(X) & (X > 0)]
    rng = np.random.default_rng(seed)
    resultados = []

    for chave, lim in LIMIARES_LEGAIS.items():
        lo_ab  = lim.valor * (1 - largura)
        hi_ac  = lim.valor * (1 + largura)
        janela = X[(X >= lo_ab) & (X <= hi_ac)]
        if len(janela) < min_obs:
            continue
        try:
            kde = gaussian_kde(janela, bw_method="scott")
        except Exception:
            continue

        d_ab = _integrar_kde(kde, lo_ab, lim.valor)
        d_ac = _integrar_kde(kde, lim.valor, hi_ac)
        iab  = d_ab / (d_ac + 1e-12)

        count_ext = 0
        for _ in range(n_bootstrap):
            perm = rng.permutation(janela)
            try:
                kde_p = gaussian_kde(perm, bw_method="scott")
            except Exception:
                continue
            iab_p = _integrar_kde(kde_p, lo_ab, lim.valor) / (
                _integrar_kde(kde_p, lim.valor, hi_ac) + 1e-12
            )
            if iab_p >= iab:
                count_ext += 1
        pvalue = count_ext / n_bootstrap

        resultados.append(BunchingResult(
            entidade=entidade, chave_limiar=chave, limiar=lim,
            n_observacoes=len(janela), iab=iab, pvalue=pvalue,
            suspeito=(iab > 2.0 and pvalue < 0.05),
        ))

    return resultados


def analisar_bunching_por_orgao(
    df: pd.DataFrame,
    col_valor: str = "valor",
    col_orgao: str = "orgao",
    col_uf: Optional[str] = "uf",
    min_obs: int = 30,
    n_bootstrap: int = 200,
    seed: int = 42,
) -> pd.DataFrame:
    """Roda análise de bunching para cada combinação órgão × UF."""
    agrupar = [c for c in [col_orgao, col_uf] if c and c in df.columns]
    if not agrupar:
        return pd.DataFrame()

    linhas = []
    for chave_grp, grp in df.groupby(agrupar):
        orgao_uf = chave_grp if isinstance(chave_grp, tuple) else (chave_grp,)
        entidade = " | ".join(str(x) for x in orgao_uf)
        vals     = grp[col_valor].dropna().values
        vals     = vals[vals > 0]

        for r in analisar_bunching(vals, entidade, min_obs=min_obs,
                                   n_bootstrap=n_bootstrap, seed=seed):
            row = dict(zip(agrupar, orgao_uf))
            row.update({
                "chave_limiar":    r.chave_limiar,
                "limiar_valor":    r.limiar.valor,
                "iab":             round(r.iab, 4),
                "pvalue":          round(r.pvalue, 4),
                "suspeito":        r.suspeito,
                "n_obs":           r.n_observacoes,
                "nivel_suspeicao": r.nivel_suspeicao,
            })
            linhas.append(row)

    if not linhas:
        return pd.DataFrame()
    return pd.DataFrame(linhas).sort_values(["suspeito", "iab"], ascending=[False, False])


# ─────────────────────────────────────────────
# PATCH M7 — REDES DE BENEFICIÁRIOS
# ─────────────────────────────────────────────

def construir_grafo_contratacoes(
    df: pd.DataFrame,
    col_orgao: str = "orgao",
    col_fornecedor: str = "cpf_cnpj",
    col_valor: str = "valor",
):
    """Constrói grafo bipartido órgão ↔ fornecedor. Requer: pip install networkx"""
    try:
        import networkx as nx
    except ImportError:
        raise ImportError("networkx necessário. pip install networkx")

    G = nx.Graph()
    for _, row in df.iterrows():
        orgao = f"O_{row[col_orgao]}"
        forn  = f"F_{row[col_fornecedor]}"
        valor = float(row[col_valor]) if pd.notna(row[col_valor]) else 0.0

        if orgao not in G:
            G.add_node(orgao, type="orgao", volume_total=0.0)
        G.nodes[orgao]["volume_total"] += valor

        if forn not in G:
            G.add_node(forn, type="fornecedor")

        if G.has_edge(orgao, forn):
            G[orgao][forn]["peso"]        += valor
            G[orgao][forn]["n_contratos"] += 1
        else:
            G.add_edge(orgao, forn, peso=valor, n_contratos=1)

    return G


def detectar_empresa_prateleira(
    df: pd.DataFrame,
    col_orgao: str = "orgao",
    col_fornecedor: str = "cpf_cnpj",
    col_valor: str = "valor",
    col_constituicao: Optional[str] = None,
    limiar_concentracao: float = 0.80,
    janela_meses: int = 12,
) -> pd.DataFrame:
    """
    Identifica fornecedores com alta concentração em único órgão
    e/ou constituídos recentemente (empresa de prateleira).
    """
    resumo = []
    for forn, grp in df.groupby(col_fornecedor):
        total = grp[col_valor].sum()
        if total <= 0:
            continue
        por_orgao    = grp.groupby(col_orgao)[col_valor].sum()
        orgao_princ  = por_orgao.idxmax()
        concentracao = por_orgao.max() / total

        delta_dias = None
        if col_constituicao and col_constituicao in df.columns:
            const = grp[col_constituicao].dropna()
            if not const.empty:
                data_const  = pd.to_datetime(const.iloc[0])
                primeiro_ct = pd.to_datetime(grp.index.min()) if hasattr(grp.index, "min") else None
                if primeiro_ct is not None:
                    delta_dias = (primeiro_ct - data_const).days

        prateleira_tempo = delta_dias is not None and 0 <= delta_dias <= janela_meses * 30
        prateleira_conc  = concentracao >= limiar_concentracao
        score = int(prateleira_tempo) + int(prateleira_conc)

        if score >= 1:
            resumo.append({
                "cpf_cnpj":             forn,
                "orgao_principal":      orgao_princ,
                "concentracao":         round(concentracao, 4),
                "volume_total":         total,
                "prateleira_por_tempo": prateleira_tempo,
                "prateleira_por_conc":  prateleira_conc,
                "score_prateleira":     score,
                "nivel":                "alto" if score == 2 else "moderado",
            })

    if not resumo:
        return pd.DataFrame()
    return pd.DataFrame(resumo).sort_values(
        ["score_prateleira", "volume_total"], ascending=[False, False]
    )


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

    del X, digitos, outlier_iqr, outlier_z, outlier_mad
    del flags_benford, cluster_risco, raw, norm_score

    return chunk


# ─────────────────────────────────────────────
# PIPELINE CHUNKED — API PRINCIPAL PARA DATASETS GRANDES
# ─────────────────────────────────────────────

def detectar_fraude_chunked(
    chunks_fn,
    output_csv: str,
    colunas_cluster: list[str],
    coluna_valor: str = "valor",
    chunk_size: int = CHUNK_SIZE,
    # ── PATCH M4 / Bunching / M7: novos parâmetros opcionais ─────────────────
    incluir_sensibilidade: bool = True,
    incluir_bunching: bool = False,
    col_uf: Optional[str] = None,
    col_orgao: str = "orgao",
) -> dict:
    """
    Pipeline completo em duas passagens para datasets que não cabem na RAM.

    Passagem 1 — varre os chunks acumulando apenas contagens de dígitos
                 (O(1) memória extra por chunk).
    Passagem 2 — processa cada chunk com o Benford global, escreve CSV
                 incrementalmente e libera a RAM antes do próximo.

    Novos parâmetros
    ----------------
    incluir_sensibilidade : roda análise LHS (500 cenários) ao final
    incluir_bunching      : roda análise de bunching por órgão (requer col_uf)
    col_uf                : nome da coluna de UF (para bunching)
    col_orgao             : nome da coluna de órgão
    """
    t_total = time.perf_counter()

    # ── 1ª passagem ──────────────────────────────────────────────────
    log.info("Passagem 1/2 — acumulando estatísticas globais...")
    acum        = BenfordAccumulator()
    sample_vals = []
    n_total     = 0
    raw_min     = np.inf
    raw_max     = -np.inf

    # Acumula componentes por órgão para LHS (M4)
    orgao_mad:     dict[str, list] = {}
    orgao_chi2inv: dict[str, list] = {}
    orgao_js:      dict[str, list] = {}
    orgao_outlier: dict[str, list] = {}

    for chunk in tqdm(chunks_fn(), desc="Passagem 1", unit="chunk"):
        vals = chunk[coluna_valor].dropna()
        vals = vals[vals > 0].values
        if len(vals) == 0:
            continue
        acum.alimentar(vals)
        n_total += len(vals)

        if len(sample_vals) < 5000:
            sample_vals.extend(vals[:max(0, 5000 - len(sample_vals))].tolist())

        oir, oz, om = detectar_outliers(vals)
        raw_chunk   = (WEIGHTS["w1"] * oir.astype(float)
                     + WEIGHTS["w2"] * oz.astype(float)
                     + WEIGHTS["w3"] * om.astype(float))
        raw_min = min(raw_min, raw_chunk.min())
        raw_max = max(raw_max, raw_chunk.max())

        # Acumula componentes por órgão para LHS
        if col_orgao in chunk.columns and incluir_sensibilidade:
            digitos_chunk = _extrair_digitos_vetorizado(vals)
            bf_chunk      = analisar_benford_completo(vals, digitos_vetorizados=digitos_chunk)
            outlier_any   = oir | oz | om
            chunk_reset   = chunk.reset_index(drop=True)
            for orgao, grp in chunk_reset.groupby(col_orgao):
                k = str(orgao)
                orgao_mad.setdefault(k, []).append(
                    float(np.mean([bf_chunk[n].mad for n in bf_chunk]))
                )
                orgao_chi2inv.setdefault(k, []).append(
                    float(np.mean([1 - bf_chunk[n].chi2_pvalue for n in bf_chunk]))
                )
                orgao_js.setdefault(k, []).append(
                    float(np.mean([bf_chunk[n].js_divergence for n in bf_chunk]))
                )
                local_idx = grp.index.to_numpy()
                if len(local_idx):
                    orgao_outlier.setdefault(k, []).append(
                        float(outlier_any[local_idx].mean())
                    )

        del vals, oir, oz, om, raw_chunk

    with _cronometrar("Finalizando Benford global"):
        benford_global = acum.finalizar()
    del acum

    # Eligibility check global
    sample_arr = np.array(sample_vals)
    elig       = verificar_elegibilidade(sample_arr)
    if not elig.elegivel:
        log.warning("⚠️  Eligibilidade: %s — %s", elig.decisao, elig.motivo_inelegivel)
    else:
        log.info("✅ Eligibilidade: %s (n=%d, ordens=%d)",
                 elig.decisao, elig.n_validos, elig.ordens_magnitude)

    norm_result = testar_normalidade(sample_arr)
    del sample_vals, sample_arr

    log.info("  Total: %d registros  raw_score ∈ [%.4f, %.4f]", n_total, raw_min, raw_max)

    # ── 2ª passagem ──────────────────────────────────────────────────
    log.info("Passagem 2/2 — processando e gravando resultados...")
    primeiro   = True
    n_gravados = 0
    contadores: Counter = Counter()

    df_amostra_bunching: list[pd.DataFrame] = []
    MAX_AMOSTRA_BUNCHING = 100_000

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

        if incluir_bunching and n_gravados <= MAX_AMOSTRA_BUNCHING:
            cols_bch = [c for c in [coluna_valor, col_orgao, col_uf]
                        if c and c in resultado.columns]
            df_amostra_bunching.append(resultado[cols_bch].copy())

        del chunk, resultado

    metricas = dict(
        normalidade    = norm_result,
        benford_global = benford_global,
        benford_desvio = benford_desvio_global(benford_global),
        eligibility    = elig,
        n_total        = n_total,
        classificacao  = dict(contadores),
    )

    # ── Score composto + LHS (M4) ─────────────────────────────────────
    if incluir_sensibilidade and orgao_mad:
        log.info("Calculando Score Composto + Análise de Sensibilidade LHS...")
        comp_por_orgao = {
            orgao: ComponentesScore(
                mad_medio       = float(np.mean(orgao_mad[orgao])),
                chi2_pvalue_inv = float(np.mean(orgao_chi2inv.get(orgao, [0.5]))),
                js_medio        = float(np.mean(orgao_js.get(orgao, [0.0]))),
                taxa_outliers   = float(np.mean(orgao_outlier.get(orgao, [0.0]))),
                taxa_cluster    = 0.0,
            )
            for orgao in orgao_mad
        }
        try:
            sens = analisar_sensibilidade_lhs(comp_por_orgao)
            metricas["sensibilidade"]  = sens
            metricas["ranking_orgaos"] = sens.ranking_medio
            log.info("Sensibilidade: %d órgãos, %d cenários", len(comp_por_orgao), sens.n_amostras)
        except Exception as e:
            log.warning("Sensibilidade LHS falhou: %s", e)

    # ── Bunching ──────────────────────────────────────────────────────
    if incluir_bunching and df_amostra_bunching:
        log.info("Análise de bunching / limiares legais...")
        df_bch = pd.concat(df_amostra_bunching, ignore_index=True)
        del df_amostra_bunching
        try:
            metricas["bunching"] = analisar_bunching_por_orgao(
                df_bch, col_valor=coluna_valor,
                col_orgao=col_orgao, col_uf=col_uf,
                min_obs=20, n_bootstrap=200,
            )
        except Exception as e:
            log.warning("Bunching falhou: %s", e)
        del df_bch

    elapsed = time.perf_counter() - t_total
    metricas["elapsed_s"] = elapsed
    log.info("Pipeline completo — %d registros em %.1fs", n_gravados, elapsed)
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
        cluster_risco   = np.zeros(len(df), dtype=bool)
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

def imprimir_relatorio(df_result: Optional[pd.DataFrame], metricas: dict) -> None:
    sep = "=" * 65
    print(f"\n{sep}\n  RELATÓRIO DE DETECÇÃO DE FRAUDE\n{sep}")

    # ── PATCH: bloco de eligibilidade ────────────────────────────────
    elig = metricas.get("eligibility")
    if elig:
        print(f"\n🔍 ELIGIBILIDADE BENFORD")
        print(f"   Decisão: {elig.decisao.upper()}")
        print(f"   n válidos: {elig.n_validos:,}  |  ordens: {elig.ordens_magnitude}"
              f"  |  nulos/zeros: {elig.pct_nulos_zerados:.1%}")
        if elig.truncamento_detectado:
            print("   ⚠️  Truncamento artificial detectado")
        if elig.motivo_inelegivel:
            print(f"   Motivo: {elig.motivo_inelegivel}")

    n = metricas["normalidade"]
    print(f"\n📊 NORMALIDADE")
    print(f"   Shapiro p={n['p_shapiro']:.4f} | KS p={n['p_ks']:.4f} | "
          f"Normal={'✅' if n['normal'] else '❌'}")

    # ── PATCH M2: exibe JS + flag tri-estado no relatório ─────────────
    print(f"\n🔢 BENFORD MULTI-DÍGITO (Global)")
    for nivel, res in metricas["benford_global"].items():
        js_str = f"JS={res.js_divergence:.5f}  " if res.js_divergence else ""
        print(f"   [{nivel.upper():4s}] MAD={res.mad:.5f}  χ²={res.chi2_stat:.2f}  "
              f"p={res.chi2_pvalue:.4f}  {js_str}"
              f"Suspeitos={res.digitos_suspeitos}  {res.emoji}")
    print(f"\n   Desvio global: {'🚨 SIM' if metricas['benford_desvio'] else '✅ NÃO'}")

    # ── PATCH M4: bloco de sensibilidade LHS ─────────────────────────
    sens = metricas.get("sensibilidade")
    if sens:
        print(f"\n📐 ANÁLISE DE SENSIBILIDADE LHS ({sens.n_amostras} cenários)")
        print("   Estabilidade top-3:")
        for ent, est in sorted(sens.estabilidade_top3.items(), key=lambda x: -x[1])[:10]:
            bar = "█" * int(est * 20)
            print(f"   {str(ent)[:35]:35s} {est*100:5.1f}%  {bar}")

    ranking = metricas.get("ranking_orgaos")
    if ranking:
        print(f"\n🏆 RANKING DE ÓRGÃOS (mais suspeitos primeiro):")
        for i, orgao in enumerate(ranking[:10], 1):
            print(f"   {i:2d}. {orgao}")

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

    if "classificacao" in metricas:
        print(f"\n🎯 CLASSIFICAÇÃO FINAL (chunked)")
        total = sum(metricas["classificacao"].values())
        for cls, n in metricas["classificacao"].items():
            print(f"   {cls:14s}: {n:7,} ({n/max(total,1)*100:.1f}%)")

    # ── PATCH Bunching: bloco de bunching ─────────────────────────────
    bch = metricas.get("bunching")
    if bch is not None and not (hasattr(bch, "empty") and bch.empty):
        n_susp = bch["suspeito"].sum() if hasattr(bch, "columns") else 0
        print(f"\n⚖️  BUNCHING — {n_susp} combinações suspeitas abaixo de limiares legais")
        if n_susp > 0:
            cols_show = [c for c in ["orgao", "uf", "chave_limiar", "limiar_valor",
                                      "iab", "pvalue", "n_obs", "nivel_suspeicao"]
                         if c in bch.columns]
            print(bch[bch["suspeito"] == True][cols_show].head(10).to_string(index=False))

    elapsed = metricas.get("elapsed_s")
    if elapsed:
        print(f"\n⏱️  Tempo total: {elapsed:.1f}s")

    print(f"\n{sep}\n")
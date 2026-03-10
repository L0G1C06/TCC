"""
ingest.py — Baixa todas as fontes do S3 e persiste no DuckDB local.

Uso:
    python3 ingest.py                        # ingere tudo
    python3 ingest.py --fonte cpgf           # ingere só uma fonte
    python3 ingest.py --force                # reingere mesmo que já exista

Fontes disponíveis: cpgf, ceis, licitacoes, viagens, compras,
                    bndes_financiamento, bndes_exportacao
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

import duckdb
import pandas as pd
from dotenv import load_dotenv

# ── Bootstrap ────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

load_dotenv(PROJECT_ROOT / "dev.env")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "contingency.settings")

from apps.portal_da_transparencia.models.ceis import CEIS
from apps.portal_da_transparencia.models.cpgf import CPGF

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Configuração ─────────────────────────────────────────────────────────────

DB_PATH = Path(__file__).resolve().parent / "pipeline.duckdb"

S3_BUCKET = os.getenv("DATALAKE_BUCKET", "storage-rumolog")
S3_BASE   = f"s3://{S3_BUCKET}/data/portal_da_transparencia/parquet"
S3_BNDES  = f"s3://{S3_BUCKET}/data/bndes/parquet"

ANOS_CPGF       = [str(a) for a in range(2019, 2025)]
ANOS_LICITACOES = [str(a) for a in range(2013, 2025)]
ANOS_COMPRAS    = [str(a) for a in range(2013, 2025)]
ANOS_VIAGENS    = [str(a) for a in range(2011, 2025)]
MESES           = [f"{m:02d}" for m in range(1, 13)]

CEIS_ANO = "2026"
CEIS_MES = "03"

BNDES_FIN_FILES = [
    f"{S3_BNDES}/modulo=operacoes-de-financiamento/operacoes-financiamento-operacoes-indiretas-automaticas.parquet",
    f"{S3_BNDES}/modulo=operacoes-de-financiamento/operacoes-financiamento-operacoes-nao-automaticas.parquet",
]
BNDES_EXP_PREFIXES = [
    "operacoes-de-exportacao-pre-e-pos-embarque",
    "operacoes-de-exportacaoo-pre-e-pos-embarque",  # typo histórico no S3
    "operacoes-de-exportacao",
]

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS dados (
    valor       DOUBLE,
    orgao       VARCHAR,
    ano         INTEGER,
    funcao      VARCHAR,
    favorecido  VARCHAR,
    cpf_cnpj    VARCHAR,
    fonte       VARCHAR
)
"""

# ── Helpers de dados ─────────────────────────────────────────────────────────

def normalizar_br(series: pd.Series) -> pd.Series:
    """Converte valores monetários em formato BR (1.234,56) para float."""
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")
    return (
        series.astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.replace(r"[^\d.]", "", regex=True)
        .pipe(pd.to_numeric, errors="coerce")
    )


def extrair_ano(series: pd.Series) -> pd.Series:
    """Extrai o ano de uma série de datas em formatos variados."""
    parsed = pd.to_datetime(series, dayfirst=True, errors="coerce")
    fallback_mask = parsed.isna()
    if fallback_mask.any():
        parsed[fallback_mask] = pd.to_datetime(
            series[fallback_mask], format="%Y-%m-%d", errors="coerce"
        )
    return parsed.dt.year.astype("Int64")


def primeira_coluna(df: pd.DataFrame, *candidatas: str, default=None) -> pd.Series:
    """Retorna a primeira coluna encontrada no DataFrame entre as candidatas."""
    for col in candidatas:
        if col in df.columns:
            return df[col]
    return pd.Series(default, index=df.index)


def primeiro_valor_valido(df: pd.DataFrame, *candidatas: str) -> pd.Series | None:
    """Retorna a primeira coluna de valor monetário válida (com ao menos um não-nulo)."""
    for col in candidatas:
        if col in df.columns:
            series = normalizar_br(df[col])
            if series.notna().any():
                return series
    return None


def unificar(
    df: pd.DataFrame,
    *,
    valor: pd.Series,
    orgao: pd.Series,
    ano: pd.Series,
    funcao: pd.Series,
    favorecido: pd.Series,
    cnpj: pd.Series,
    fonte: str,
) -> pd.DataFrame:
    """Normaliza um DataFrame para o schema unificado da tabela `dados`."""
    return pd.DataFrame({
        "valor":      valor,
        "orgao":      orgao,
        "ano":        ano,
        "funcao":     funcao,
        "favorecido": favorecido,
        "cpf_cnpj":   cnpj,
        "fonte":      fonte,
    })


# ── Helpers de infraestrutura ─────────────────────────────────────────────────

def get_s3_conn() -> duckdb.DuckDBPyConnection:
    """Cria uma conexão DuckDB com credenciais S3 configuradas."""
    conn = duckdb.connect()
    conn.execute(f"""
        INSTALL httpfs; LOAD httpfs;
        SET s3_region='{os.getenv("AWS_DEFAULT_REGION", "sa-east-1")}';
        SET s3_access_key_id='{os.getenv("AWS_ACCESS_KEY_ID", "")}';
        SET s3_secret_access_key='{os.getenv("AWS_SECRET_ACCESS_KEY", "")}';
    """)
    return conn


def get_db() -> duckdb.DuckDBPyConnection:
    """Abre (ou cria) o banco local e garante que o schema existe."""
    db = duckdb.connect(str(DB_PATH))
    db.execute(SCHEMA_SQL)
    return db


def fonte_ja_ingerida(fonte: str) -> bool:
    """Verifica se uma fonte já possui registros no banco local."""
    with get_db() as db:
        count = db.execute(
            "SELECT COUNT(*) FROM dados WHERE fonte = ?", [fonte]
        ).fetchone()[0]
    return count > 0


def gravar(df: pd.DataFrame, fonte: str) -> None:
    """Substitui os registros da fonte no banco local (delete + insert)."""
    if df.empty:
        log.warning("DataFrame vazio para fonte '%s' — nada gravado.", fonte)
        return
    with get_db() as db:
        db.execute("DELETE FROM dados WHERE fonte = ?", [fonte])
        db.execute("INSERT INTO dados SELECT * FROM df")


def ler_parquet_s3(conn: duckdb.DuckDBPyConnection, path: str) -> pd.DataFrame:
    """Lê um arquivo Parquet do S3; retorna DataFrame vazio em caso de falha."""
    try:
        return conn.execute(f"SELECT * FROM read_parquet('{path}')").df()
    except Exception as exc:
        log.debug("Não foi possível ler '%s': %s", path, exc)
        return pd.DataFrame()


def listar_parquets(conn: duckdb.DuckDBPyConnection, prefix: str) -> list[str]:
    """Lista arquivos Parquet sob um prefixo S3."""
    try:
        rows = conn.execute(f"SELECT file FROM glob('{prefix}/**/*.parquet')").fetchall()
        return [r[0] for r in rows]
    except Exception:
        return []


# ── Ingestores ────────────────────────────────────────────────────────────────

def ingerir_cpgf() -> None:
    fonte = "CPGF"
    log.info("Iniciando ingestão: %s", fonte)
    partes: list[pd.DataFrame] = []

    for ano in ANOS_CPGF:
        for mes in MESES:
            try:
                df_pl = CPGF.polars(ano=ano, mes=mes).collect()
                if df_pl.is_empty():
                    continue
                df = df_pl.to_pandas()
                partes.append(unificar(
                    df,
                    valor      = normalizar_br(df["VALOR TRANSAÇÃO"]),
                    orgao      = primeira_coluna(df, "NOME ÓRGÃO SUPERIOR"),
                    ano        = pd.to_numeric(df["ANO EXTRATO"], errors="coerce").astype("Int64"),
                    funcao     = primeira_coluna(df, "NOME ÓRGÃO"),
                    favorecido = primeira_coluna(df, "NOME FAVORECIDO"),
                    cnpj       = primeira_coluna(df, "CNPJ OU CPF FAVORECIDO"),
                    fonte      = fonte,
                ))
                log.debug("  %s/%s → %d registros", ano, mes, len(partes[-1]))
            except Exception as exc:
                log.debug("  %s/%s ignorado: %s", ano, mes, type(exc).__name__)

    if not partes:
        log.warning("%s: nenhum dado carregado.", fonte)
        return

    result = pd.concat(partes, ignore_index=True)
    gravar(result, fonte)
    log.info("%s: %d registros gravados.", fonte, len(result))


def ingerir_ceis() -> None:
    fonte = "CEIS"
    log.info("Iniciando ingestão: %s", fonte)
    try:
        df = CEIS.polars(ano=CEIS_ANO, mes=CEIS_MES).collect().to_pandas()
        result = unificar(
            df,
            valor      = pd.Series(1.0, index=df.index),
            orgao      = primeira_coluna(df, "ÓRGÃO SANCIONADOR"),
            ano        = extrair_ano(primeira_coluna(df, "DATA INÍCIO SANÇÃO").astype(str)),
            funcao     = primeira_coluna(df, "CATEGORIA DA SANÇÃO"),
            favorecido = primeira_coluna(df, "NOME DO SANCIONADO"),
            cnpj       = primeira_coluna(df, "CPF OU CNPJ DO SANCIONADO"),
            fonte      = fonte,
        )
        gravar(result, fonte)
        log.info("%s: %d registros gravados.", fonte, len(result))
    except Exception as exc:
        log.error("%s: %s — %s", fonte, type(exc).__name__, exc)


def _ingerir_particionado(
    fonte: str,
    anos: list[str],
    prefix_template: str,
    construir_df: Callable[[pd.DataFrame, str], pd.DataFrame | None],
) -> None:
    """Genérico para fontes particionadas por ano/mês no S3."""
    log.info("Iniciando ingestão: %s", fonte)
    conn = get_s3_conn()
    partes: list[pd.DataFrame] = []

    try:
        for ano in anos:
            for mes in MESES:
                prefix = prefix_template.format(ano=ano, mes=mes)
                arquivos = listar_parquets(conn, prefix)
                if not arquivos:
                    continue
                sub: list[pd.DataFrame] = []
                for arq in arquivos:
                    df = ler_parquet_s3(conn, arq)
                    resultado = construir_df(df, ano)
                    if resultado is not None and not resultado.empty:
                        sub.append(resultado)
                if sub:
                    parte = pd.concat(sub, ignore_index=True)
                    partes.append(parte)
                    log.debug("  %s/%s → %d registros", ano, mes, len(parte))
    finally:
        conn.close()

    if not partes:
        log.warning("%s: nenhuma partição carregada.", fonte)
        return

    result = pd.concat(partes, ignore_index=True)
    gravar(result, fonte)
    log.info("%s: %d registros gravados.", fonte, len(result))


def ingerir_licitacoes() -> None:
    fonte = "LICITACOES"
    VAL_COLS = ["Valor Licitação", "Valor Empenho (R$)"]

    def construir(df: pd.DataFrame, ano: str) -> pd.DataFrame | None:
        if df.empty or not any(c in df.columns for c in ["Código Participante", "Nome Participante"]):
            return None
        if "Flag Vencedor" in df.columns:
            df = df[df["Flag Vencedor"].astype(str).str.upper().isin(["S", "SIM", "1", "TRUE"])]
        if df.empty:
            return None
        val = primeiro_valor_valido(df, *VAL_COLS) or pd.Series(1.0, index=df.index)
        return unificar(
            df,
            valor      = val,
            orgao      = primeira_coluna(df, "Nome Órgão", "Nome Órgão Superior"),
            ano        = pd.Series([int(ano)] * len(df), dtype="Int64"),
            funcao     = primeira_coluna(df, "Modalidade Compra"),
            favorecido = primeira_coluna(df, "Nome Participante"),
            cnpj       = primeira_coluna(df, "Código Participante"),
            fonte      = fonte,
        )

    _ingerir_particionado(
        fonte,
        ANOS_LICITACOES,
        f"{S3_BASE}/modulo=licitacoes/ano={{ano}}/mes={{mes}}",
        construir,
    )


def ingerir_compras() -> None:
    fonte = "COMPRAS"
    VAL_COLS = [
        "Valor Item", "Valor Inicial Compra", "Valor Final Compra",
        "Valor Apostilamento", "Valor Licitação",
    ]

    def construir(df: pd.DataFrame, ano: str) -> pd.DataFrame | None:
        if df.empty:
            return None
        val = primeiro_valor_valido(df, *VAL_COLS)
        if val is None:
            return None
        return unificar(
            df,
            valor      = val,
            orgao      = primeira_coluna(df, "Nome Órgão", "Nome Órgão Superior"),
            ano        = pd.Series([int(ano)] * len(df), dtype="Int64"),
            funcao     = primeira_coluna(df, "Descrição Item Compra", "Modalidade Compra", "Objeto"),
            favorecido = primeira_coluna(df, "Nome Contratado"),
            cnpj       = primeira_coluna(df, "Código Contratado", "Código UG"),
            fonte      = fonte,
        )

    _ingerir_particionado(
        fonte,
        ANOS_COMPRAS,
        f"{S3_BASE}/modulo=compras/ano={{ano}}/mes={{mes}}",
        construir,
    )


def ingerir_viagens() -> None:
    fonte = "VIAGENS"
    VAL_COLS = ["Valor", "Valor diárias", "Valor passagens"]
    log.info("Iniciando ingestão: %s", fonte)
    conn = get_s3_conn()
    partes: list[pd.DataFrame] = []

    try:
        for ano in ANOS_VIAGENS:
            path = f"{S3_BASE}/modulo=viagens/ano={ano}/{ano}_Pagamento.parquet"
            df = ler_parquet_s3(conn, path)
            if df.empty:
                continue
            val = primeiro_valor_valido(df, *VAL_COLS)
            if val is None:
                log.debug("  %s: sem coluna de valor", ano)
                continue
            partes.append(unificar(
                df,
                valor      = val,
                orgao      = primeira_coluna(df, "Nome do órgão superior", "Nome do órgao pagador"),
                ano        = pd.Series([int(ano)] * len(df), dtype="Int64"),
                funcao     = primeira_coluna(df, "Tipo de pagamento"),
                favorecido = primeira_coluna(df, "Nome"),
                cnpj       = primeira_coluna(df, "CPF viajante"),
                fonte      = fonte,
            ))
            log.debug("  %s → %d registros", ano, len(partes[-1]))
    finally:
        conn.close()

    if not partes:
        log.warning("%s: nenhuma partição carregada.", fonte)
        return

    result = pd.concat(partes, ignore_index=True)
    gravar(result, fonte)
    log.info("%s: %d registros gravados.", fonte, len(result))


def ingerir_bndes_financiamento() -> None:
    fonte = "BNDES_FINANCIAMENTO"
    VAL_COLS = ["valor_desembolsado_reais", "valor_contratado_reais", "valor_da_operacao_em_reais"]
    log.info("Iniciando ingestão: %s", fonte)
    try:
        files_literal = "', '".join(BNDES_FIN_FILES)
        conn = get_s3_conn()
        df = conn.execute(
            f"SELECT * FROM read_parquet(['{files_literal}'], union_by_name=true)"
        ).df()
        conn.close()

        val = primeiro_valor_valido(df, *VAL_COLS)
        if val is None:
            raise ValueError("Nenhuma coluna de valor encontrada.")

        result = unificar(
            df,
            valor      = val,
            orgao      = primeira_coluna(df, "setor_bndes"),
            ano        = extrair_ano(df["data_da_contratacao"].astype(str)),
            funcao     = primeira_coluna(df, "subsetor_bndes"),
            favorecido = primeira_coluna(df, "cliente"),
            cnpj       = primeira_coluna(df, "cpf_cnpj", "cnpj"),
            fonte      = fonte,
        )
        gravar(result, fonte)
        log.info("%s: %d registros gravados.", fonte, len(result))
    except Exception as exc:
        log.error("%s: %s — %s", fonte, type(exc).__name__, exc)


def ingerir_bndes_exportacao() -> None:
    fonte = "BNDES_EXPORTACAO"
    VAL_COLS = ["valor_desembolsado_em_reais", "valor_da_operacao_em_reais"]
    log.info("Iniciando ingestão: %s", fonte)
    conn = get_s3_conn()
    df = pd.DataFrame()

    try:
        for prefix in BNDES_EXP_PREFIXES:
            try:
                df = conn.execute(
                    f"SELECT * FROM read_parquet('{S3_BNDES}/modulo={prefix}/**/*.parquet', union_by_name=true)"
                ).df()
                if not df.empty:
                    break
            except Exception:
                continue
    finally:
        conn.close()

    if df.empty:
        log.warning("%s: fonte não encontrada no S3.", fonte)
        return

    val = primeiro_valor_valido(df, *VAL_COLS)
    if val is None:
        log.warning("%s: sem coluna de valor.", fonte)
        return

    result = unificar(
        df,
        valor      = val,
        orgao      = primeira_coluna(df, "setor_bndes"),
        ano        = extrair_ano(df["data_da_contratacao"].astype(str)),
        funcao     = primeira_coluna(df, "subsetor_bndes"),
        favorecido = primeira_coluna(df, "exportador", "cliente"),
        cnpj       = primeira_coluna(df, "cnpj_do_exportador", "cpf_cnpj"),
        fonte      = fonte,
    )
    gravar(result, fonte)
    log.info("%s: %d registros gravados.", fonte, len(result))


# ── Registro de ingestores ────────────────────────────────────────────────────

INGESTORES: dict[str, Callable[[], None]] = {
    "cpgf":                ingerir_cpgf,
    "ceis":                ingerir_ceis,
    "licitacoes":          ingerir_licitacoes,
    "viagens":             ingerir_viagens,
    "compras":             ingerir_compras,
    "bndes_financiamento": ingerir_bndes_financiamento,
    "bndes_exportacao":    ingerir_bndes_exportacao,
}


# ── Entrypoint ────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingestão S3 → DuckDB local")
    parser.add_argument(
        "--fonte",
        choices=list(INGESTORES.keys()),
        help="Ingere só uma fonte específica.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reingere mesmo que a fonte já exista no DB.",
    )
    return parser.parse_args()


def _resumo_db() -> None:
    """Imprime o estado atual do banco após a ingestão."""
    with get_db() as db:
        rows = db.execute("""
            SELECT fonte, COUNT(*) AS n, MIN(ano) AS ano_min, MAX(ano) AS ano_max
            FROM dados
            GROUP BY fonte
            ORDER BY fonte
        """).fetchall()

    log.info("Estado atual do DB (%s):", DB_PATH)
    for fonte, n, ano_min, ano_max in rows:
        log.info("  %-28s %10d registros  (%s → %s)", fonte, n, ano_min, ano_max)


def main() -> None:
    args = _parse_args()

    # Garante que o DB e a tabela existem antes de qualquer operação
    get_db().close()

    fontes_alvo: list[str] = [args.fonte] if args.fonte else list(INGESTORES.keys())

    if not args.force:
        ja_ingeridas = [f for f in fontes_alvo if fonte_ja_ingerida(f.upper())]
        fontes_alvo  = [f for f in fontes_alvo if f not in ja_ingeridas]
        if ja_ingeridas:
            log.info("Já ingeridas (use --force para re-ingerir): %s", ", ".join(ja_ingeridas))

    if not fontes_alvo:
        log.info("Todas as fontes já estão no DB. Nada a fazer.")
        return

    log.info("Ingerindo em paralelo: %s", ", ".join(fontes_alvo))
    t0 = time.perf_counter()
    erros: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=len(fontes_alvo)) as executor:
        futures = {executor.submit(INGESTORES[f]): f for f in fontes_alvo}
        for future in as_completed(futures):
            nome = futures[future]
            try:
                future.result()
            except Exception as exc:
                erros[nome] = str(exc)
                log.error("%s falhou: %s", nome, exc)

    elapsed = time.perf_counter() - t0
    log.info("Ingestão concluída em %.1fs.", elapsed)
    _resumo_db()

    if erros:
        for nome, msg in erros.items():
            log.error("Erro em '%s': %s", nome, msg)
        sys.exit(1)


if __name__ == "__main__":
    main()
"""
ingest.py — Lê Parquet de um servidor SSH via Paramiko/SFTP e persiste no DuckDB local.

Uso:
    python3 ingest.py                        # ingere tudo
    python3 ingest.py --fonte cpgf           # ingere só uma fonte
    python3 ingest.py --force                # reingere mesmo que já exista
    python3 ingest.py --chunk-size 50000     # ajusta RAM por chunk (padrão 50k)

VARIÁVEIS DE AMBIENTE (dev.env):
    SSH_HOST        — hostname ou IP do servidor
    SSH_PORT        — porta SSH (padrão 22)
    SSH_USER        — usuário (ex: edu)
    SSH_PASSWORD    — senha (opcional se usar SSH_KEY_PATH)
    SSH_KEY_PATH    — caminho para chave privada (opcional)
    SSH_BASE_PATH   — raiz dos dados no servidor
                      ex: /home/edu/comum_henry/data/pd_data
    SSH_BNDES_PATH  — raiz dos dados BNDES no servidor
                      ex: /home/edu/comum_henry/data/bndes

ESTRATÉGIA DE RAM (16 GB):
    - Execução SEQUENCIAL entre fontes.
    - Cada arquivo Parquet é lido via SFTP para BytesIO (nunca salvo em disco).
    - O BytesIO é lido direto pelo DuckDB via read_parquet na memória.
    - union_by_name=True em todos os read_parquet para tolerar schema mismatch.
    - chunk_size padrão = 50_000 registros.
    - gc.collect() explícito após cada arquivo/chunk.

Fontes disponíveis (apenas as presentes no SSH):
    compras, convenios, despesas, licitacoes, viagens
    + qualquer outra que você adicionar em SSH_BASE_PATH
"""

from __future__ import annotations

import argparse
import gc
import io
import logging
import os
import sys
import time
from pathlib import Path, PurePosixPath
from typing import Callable, Iterator

import django
import duckdb
import pandas as pd
import paramiko
from dotenv import load_dotenv

# ── Bootstrap ────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

load_dotenv(PROJECT_ROOT / "dev.env")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "contingency.settings")

django.setup()

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Configuração ─────────────────────────────────────────────────────────────

DB_PATH = Path(__file__).resolve().parent / "pipeline.duckdb"

# Configuração SSH (lida do .env)
SSH_HOST      = os.getenv("SSH_HOST", "contingency")
SSH_PORT      = int(os.getenv("SSH_PORT", "22"))
SSH_USER      = os.getenv("SSH_USER", "edu")
SSH_PASSWORD  = os.getenv("SSH_PASSWORD")          # None → usa chave
SSH_KEY_PATH  = os.getenv("SSH_KEY_PATH")          # ex: ~/.ssh/id_rsa
SSH_BASE_PATH = os.getenv("SSH_BASE_PATH", "/home/edu/comum_henry/data/pd_data")
SSH_BNDES_PATH = os.getenv("SSH_BNDES_PATH", "/home/edu/comum_henry/data/bndes")

MESES = [f"{m:02d}" for m in range(1, 13)]

# Ranges de anos por fonte
ANOS = {
    "cpgf":              range(2013, 2027),
    "cpcc":              range(2014, 2027),
    "cpdc":              range(2013, 2027),
    "licitacoes":        range(2013, 2025),
    "compras":           range(2013, 2027),
    "despesas":          range(2013, 2027),
    "despesas_execucao": range(2014, 2027),
    "transferencias":    range(2014, 2027),
    "bolsa_pag":         range(2013, 2022),
    "bolsa_saq":         range(2013, 2022),
    "bpc":               range(2019, 2027),
    "auxilio_brasil":    range(2021, 2024),
    "auxilio_emerg":     range(2020, 2025),
    "viagens":           range(2011, 2027),
}

CHUNK_SIZE = 50_000

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

# ── Helpers SSH/SFTP ──────────────────────────────────────────────────────────

def _make_ssh_client() -> paramiko.SSHClient:
    """Abre e retorna um SSHClient autenticado."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    connect_kwargs: dict = dict(
        hostname=SSH_HOST,
        port=SSH_PORT,
        username=SSH_USER,
        timeout=30,
    )
    if SSH_KEY_PATH:
        connect_kwargs["key_filename"] = os.path.expanduser(SSH_KEY_PATH)
    if SSH_PASSWORD:
        connect_kwargs["password"] = SSH_PASSWORD

    client.connect(**connect_kwargs)
    log.debug("SSH conectado: %s@%s:%s", SSH_USER, SSH_HOST, SSH_PORT)
    return client


def _listar_parquets_sftp(sftp: paramiko.SFTPClient, base_path: str) -> list[str]:
    """
    Lista recursivamente todos os .parquet abaixo de base_path via SFTP.
    Ignora arquivos que comecem com '_' (metadados como _eligibility.json).
    """
    result: list[str] = []
    try:
        entries = sftp.listdir_attr(base_path)
    except FileNotFoundError:
        return result

    for entry in entries:
        name = entry.filename
        full = f"{base_path}/{name}"
        import stat
        if stat.S_ISDIR(entry.st_mode):
            result.extend(_listar_parquets_sftp(sftp, full))
        elif name.endswith(".parquet") and not name.startswith("_"):
            result.append(full)

    return result


def _ler_parquet_sftp(sftp: paramiko.SFTPClient, remote_path: str) -> pd.DataFrame:
    """
    Baixa um arquivo Parquet do servidor SSH para memória (BytesIO)
    e retorna um DataFrame. Nunca salva em disco.
    """
    buf = io.BytesIO()
    try:
        sftp.getfo(remote_path, buf)
        buf.seek(0)
        # DuckDB lê direto do BytesIO via pandas → parquet
        return pd.read_parquet(buf)
    except Exception as exc:
        log.debug("Não foi possível ler '%s': %s", remote_path, exc)
        return pd.DataFrame()
    finally:
        buf.close()


def _prefixos_ano_mes_ssh(modulo: str, anos: range) -> list[str]:
    """Gera lista de caminhos SSH no padrão modulo/ano=X/mes=Y."""
    return [
        f"{SSH_BASE_PATH}/{modulo}/ano={ano}/mes={mes}"
        for ano in anos
        for mes in MESES
    ]


def _prefixos_ano_ssh(modulo: str, anos: range) -> list[str]:
    """Gera lista de caminhos SSH no padrão modulo/ano=X."""
    return [
        f"{SSH_BASE_PATH}/{modulo}/ano={ano}"
        for ano in anos
    ]


# ── Helpers de dados ──────────────────────────────────────────────────────────

def normalizar_br(series: pd.Series) -> pd.Series:
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
    parsed = pd.to_datetime(series, dayfirst=True, errors="coerce")
    mask = parsed.isna()
    if mask.any():
        parsed[mask] = pd.to_datetime(series[mask], format="%Y-%m-%d", errors="coerce")
    return parsed.dt.year.astype("Int64")


def col(df: pd.DataFrame, *candidatas: str, default: object = None) -> pd.Series:
    """Retorna a primeira coluna existente; senão Series com default."""
    for c in candidatas:
        if c in df.columns:
            return df[c]
    return pd.Series(default, index=df.index, dtype="object")


def val_col(df: pd.DataFrame, *candidatas: str) -> "pd.Series | None":
    """Retorna a primeira coluna de valor numérico válida encontrada."""
    for c in candidatas:
        if c in df.columns:
            s = normalizar_br(df[c])
            if s.notna().any():
                return s
    return None


def unificar(df, *, valor, orgao, ano, funcao, favorecido, cnpj, fonte) -> pd.DataFrame:
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

def get_db() -> duckdb.DuckDBPyConnection:
    db = duckdb.connect(str(DB_PATH))
    db.execute(SCHEMA_SQL)
    return db


def fonte_ja_ingerida(fonte: str) -> bool:
    with get_db() as db:
        n = db.execute(
            "SELECT COUNT(*) FROM dados WHERE fonte = ?", [fonte]
        ).fetchone()[0]
    return n > 0


def _em_chunks(df: pd.DataFrame, size: int) -> Iterator[pd.DataFrame]:
    for start in range(0, len(df), size):
        yield df.iloc[start: start + size]


def _gravar_chunks(
    db: duckdb.DuckDBPyConnection,
    df: pd.DataFrame,
    fonte: str,
    chunk_size: int,
    primeiro: bool,
) -> tuple[int, bool]:
    total = 0
    for chunk in _em_chunks(df, chunk_size):
        if chunk.empty:
            del chunk
            continue
        if primeiro:
            db.execute("DELETE FROM dados WHERE fonte = ?", [fonte])
            primeiro = False
        db.execute("INSERT INTO dados SELECT * FROM chunk")
        total += len(chunk)
        del chunk
    return total, primeiro


def gravar(df: pd.DataFrame, fonte: str, chunk_size: int = CHUNK_SIZE) -> None:
    if df.empty:
        log.warning("DataFrame vazio para '%s' — nada gravado.", fonte)
        return
    with get_db() as db:
        n, _ = _gravar_chunks(db, df, fonte, chunk_size, True)
    log.info("%s: %d registros gravados.", fonte, n)


def _log_total(fonte: str, total: int) -> None:
    if total == 0:
        log.warning("%s: nenhum dado carregado.", fonte)
    else:
        log.info("%s: %d registros gravados.", fonte, total)


def _ano_do_path(path: str) -> int:
    """Extrai o ano de um caminho estilo .../ano=2021/..."""
    return int(path.split("/ano=")[1].split("/")[0].rstrip("/"))


# ── Núcleo genérico: lê SSH arquivo por arquivo ───────────────────────────────

def _ingerir_ssh_por_arquivo(
    fonte: str,
    prefixos: list[str],
    construir: Callable[[pd.DataFrame, str], "pd.DataFrame | None"],
    chunk_size: int,
) -> None:
    """
    Para cada prefixo, lista arquivos Parquet via SFTP, lê UM por vez,
    transforma com `construir(df, prefix)` e grava em chunks.
    Nunca mantém mais de 1 arquivo na RAM além dos chunks.
    """
    log.info("Iniciando ingestão SSH: %s", fonte)
    ssh    = _make_ssh_client()
    sftp   = ssh.open_sftp()
    total  = 0
    primeiro = True

    try:
        with get_db() as db:
            for prefix in prefixos:
                arquivos = _listar_parquets_sftp(sftp, prefix)
                if not arquivos:
                    continue

                for arq in arquivos:
                    df = _ler_parquet_sftp(sftp, arq)
                    if df.empty:
                        del df
                        continue

                    result = construir(df, prefix)
                    del df
                    gc.collect()

                    if result is None or result.empty:
                        if result is not None:
                            del result
                        continue

                    n, primeiro = _gravar_chunks(db, result, fonte, chunk_size, primeiro)
                    total += n
                    del result
                    gc.collect()
                    log.debug("  %s → %d (acum: %d)", arq.split("/")[-1], n, total)
    finally:
        sftp.close()
        ssh.close()

    _log_total(fonte, total)


# ── Ingestores ────────────────────────────────────────────────────────────────

def ingerir_acordos_leniencia(chunk_size: int = CHUNK_SIZE) -> None:
    fonte = "ACORDOS_LENIENCIA"

    def construir(df: pd.DataFrame, _p: str) -> "pd.DataFrame | None":
        return unificar(
            df,
            valor      = pd.Series(1.0, index=df.index),
            orgao      = col(df, "ÓRGÃO SANCIONADOR"),
            ano        = extrair_ano(col(df, "DATA DE INÍCIO DO ACORDO").astype(str)),
            funcao     = col(df, "EFEITO DO ACORDO DE LENIENCIA",
                              "SITUAÇÃO DO ACORDO DE LENIÊNICA", "SITUAÇÃO DO ACORDO DE LENIENCIA"),
            favorecido = col(df, "RAZÃO SOCIAL  CADASTRO RECEITA",
                              "RAZÃO SOCIAL CADASTRO RECEITA"),
            cnpj       = col(df, "CNPJ DO SANCIONADO"),
            fonte      = fonte,
        )

    _ingerir_ssh_por_arquivo(
        fonte,
        [f"{SSH_BASE_PATH}/acordos-leniencia/ano=2026/mes=03"],
        construir, chunk_size,
    )


def ingerir_apoiamento_emendas(chunk_size: int = CHUNK_SIZE) -> None:
    fonte = "APOIAMENTO_EMENDAS"

    def construir(df: pd.DataFrame, _p: str) -> "pd.DataFrame | None":
        ano_series = pd.to_numeric(col(df, "ano"), errors="coerce").astype("Int64")
        return unificar(
            df,
            valor      = val_col(df, "Valor Empenhado", "Valor Pago") or pd.Series(1.0, index=df.index),
            orgao      = col(df, "Órgão Superior", "Órgão"),
            ano        = ano_series,
            funcao     = col(df, "Tipo de Emenda"),
            favorecido = col(df, "Favorecido"),
            cnpj       = col(df, "Código favorecido"),
            fonte      = fonte,
        )

    _ingerir_ssh_por_arquivo(
        fonte,
        _prefixos_ano_ssh("apoiamento-emendas-parlamentares-documentos", range(2020, 2026)),
        construir, chunk_size,
    )


def ingerir_auxilio_brasil(chunk_size: int = CHUNK_SIZE) -> None:
    fonte = "AUXILIO_BRASIL"

    def construir(df: pd.DataFrame, prefix: str) -> "pd.DataFrame | None":
        ano = _ano_do_path(prefix)
        return unificar(
            df,
            valor      = val_col(df, "VALOR PARCELA") or pd.Series(1.0, index=df.index),
            orgao      = col(df, "UF"),
            ano        = pd.Series(ano, index=df.index, dtype="Int64"),
            funcao     = "Auxílio Brasil",
            favorecido = col(df, "NOME FAVORECIDO"),
            cnpj       = col(df, "CPF FAVORECIDO"),
            fonte      = fonte,
        )

    _ingerir_ssh_por_arquivo(
        fonte, _prefixos_ano_mes_ssh("auxilio-brasil", ANOS["auxilio_brasil"]),
        construir, chunk_size,
    )


def ingerir_auxilio_emergencial(chunk_size: int = CHUNK_SIZE) -> None:
    fonte = "AUXILIO_EMERGENCIAL"

    def construir(df: pd.DataFrame, prefix: str) -> "pd.DataFrame | None":
        ano = _ano_do_path(prefix)
        return unificar(
            df,
            valor      = val_col(df, "VALOR BENEFÍCIO") or pd.Series(1.0, index=df.index),
            orgao      = col(df, "UF"),
            ano        = pd.Series(ano, index=df.index, dtype="Int64"),
            funcao     = "Auxílio Emergencial",
            favorecido = col(df, "NOME BENEFICIÁRIO"),
            cnpj       = col(df, "CPF BENEFICIÁRIO"),
            fonte      = fonte,
        )

    _ingerir_ssh_por_arquivo(
        fonte, _prefixos_ano_mes_ssh("auxilio-emergencial", ANOS["auxilio_emerg"]),
        construir, chunk_size,
    )


def ingerir_auxilio_reconstrucao(chunk_size: int = CHUNK_SIZE) -> None:
    fonte = "AUXILIO_RECONSTRUCAO"

    def construir(df: pd.DataFrame, _p: str) -> "pd.DataFrame | None":
        return unificar(
            df,
            valor      = val_col(df, "VALOR PARCELA") or pd.Series(1.0, index=df.index),
            orgao      = col(df, "UF"),
            ano        = pd.Series(2025, index=df.index, dtype="Int64"),
            funcao     = "Reconstrução",
            favorecido = col(df, "NOME FAVORECIDO"),
            cnpj       = col(df, "CPF FAVORECIDO"),
            fonte      = fonte,
        )

    _ingerir_ssh_por_arquivo(
        fonte,
        [f"{SSH_BASE_PATH}/auxilio-reconstrucao/ano=2025/mes=07"],
        construir, chunk_size,
    )


def ingerir_bolsa_familia_pagamentos(chunk_size: int = CHUNK_SIZE) -> None:
    fonte = "BOLSA_FAMILIA_PAGAMENTOS"

    def construir(df: pd.DataFrame, prefix: str) -> "pd.DataFrame | None":
        ano = _ano_do_path(prefix)
        return unificar(
            df,
            valor      = val_col(df, "VALOR PARCELA") or pd.Series(1.0, index=df.index),
            orgao      = col(df, "UF"),
            ano        = pd.Series(ano, index=df.index, dtype="Int64"),
            funcao     = "Bolsa Família",
            favorecido = col(df, "NOME FAVORECIDO"),
            cnpj       = col(df, "CPF FAVORECIDO"),
            fonte      = fonte,
        )

    _ingerir_ssh_por_arquivo(
        fonte, _prefixos_ano_mes_ssh("bolsa-familia-pagamentos", ANOS["bolsa_pag"]),
        construir, chunk_size,
    )


def ingerir_bolsa_familia_saques(chunk_size: int = CHUNK_SIZE) -> None:
    fonte = "BOLSA_FAMILIA_SAQUES"

    def construir(df: pd.DataFrame, prefix: str) -> "pd.DataFrame | None":
        ano = _ano_do_path(prefix)
        return unificar(
            df,
            valor      = val_col(df, "VALOR PARCELA") or pd.Series(1.0, index=df.index),
            orgao      = col(df, "UF"),
            ano        = pd.Series(ano, index=df.index, dtype="Int64"),
            funcao     = "Saque",
            favorecido = col(df, "NOME FAVORECIDO"),
            cnpj       = col(df, "CPF FAVORECIDO"),
            fonte      = fonte,
        )

    _ingerir_ssh_por_arquivo(
        fonte, _prefixos_ano_mes_ssh("bolsa-familia-saques", ANOS["bolsa_saq"]),
        construir, chunk_size,
    )


def ingerir_bpc(chunk_size: int = CHUNK_SIZE) -> None:
    fonte = "BPC"

    def construir(df: pd.DataFrame, prefix: str) -> "pd.DataFrame | None":
        ano = _ano_do_path(prefix)
        return unificar(
            df,
            valor      = val_col(df, "VALOR PARCELA") or pd.Series(1.0, index=df.index),
            orgao      = col(df, "UF"),
            ano        = pd.Series(ano, index=df.index, dtype="Int64"),
            funcao     = "BPC",
            favorecido = col(df, "NOME BENEFICIÁRIO"),
            cnpj       = col(df, "CPF BENEFICIÁRIO"),
            fonte      = fonte,
        )

    _ingerir_ssh_por_arquivo(
        fonte, _prefixos_ano_mes_ssh("bpc", ANOS["bpc"]),
        construir, chunk_size,
    )


def ingerir_ceaf(chunk_size: int = CHUNK_SIZE) -> None:
    fonte = "CEAF"

    def construir(df: pd.DataFrame, _p: str) -> "pd.DataFrame | None":
        return unificar(
            df,
            valor      = pd.Series(1.0, index=df.index),
            orgao      = col(df, "ÓRGÃO SANCIONADOR"),
            ano        = extrair_ano(col(df, "DATA INÍCIO SANÇÃO").astype(str)),
            funcao     = col(df, "CATEGORIA DA SANÇÃO"),
            favorecido = col(df, "NOME DO SANCIONADO"),
            cnpj       = col(df, "CPF OU CNPJ DO SANCIONADO"),
            fonte      = fonte,
        )

    _ingerir_ssh_por_arquivo(
        fonte,
        [f"{SSH_BASE_PATH}/ceaf/ano=2026/mes=03"],
        construir, chunk_size,
    )


def ingerir_ceis(chunk_size: int = CHUNK_SIZE) -> None:
    fonte = "CEIS"

    def construir(df: pd.DataFrame, _p: str) -> "pd.DataFrame | None":
        return unificar(
            df,
            valor      = pd.Series(1.0, index=df.index),
            orgao      = col(df, "ÓRGÃO SANCIONADOR"),
            ano        = extrair_ano(col(df, "DATA INÍCIO SANÇÃO").astype(str)),
            funcao     = col(df, "CATEGORIA DA SANÇÃO"),
            favorecido = col(df, "NOME DO SANCIONADO"),
            cnpj       = col(df, "CPF OU CNPJ DO SANCIONADO"),
            fonte      = fonte,
        )

    _ingerir_ssh_por_arquivo(
        fonte,
        [f"{SSH_BASE_PATH}/ceis/ano=2026/mes=03"],
        construir, chunk_size,
    )


def ingerir_cepim(chunk_size: int = CHUNK_SIZE) -> None:
    fonte = "CEPIM"

    def construir(df: pd.DataFrame, _p: str) -> "pd.DataFrame | None":
        return unificar(
            df,
            valor      = pd.Series(1.0, index=df.index),
            orgao      = col(df, "ÓRGÃO CONCEDENTE"),
            ano        = pd.Series(2026, index=df.index, dtype="Int64"),
            funcao     = col(df, "MOTIVO DO IMPEDIMENTO"),
            favorecido = col(df, "NOME ENTIDADE"),
            cnpj       = col(df, "CNPJ ENTIDADE"),
            fonte      = fonte,
        )

    _ingerir_ssh_por_arquivo(
        fonte,
        [f"{SSH_BASE_PATH}/cepim/ano=2026/mes=03"],
        construir, chunk_size,
    )


def ingerir_cnep(chunk_size: int = CHUNK_SIZE) -> None:
    fonte = "CNEP"

    def construir(df: pd.DataFrame, _p: str) -> "pd.DataFrame | None":
        return unificar(
            df,
            valor      = val_col(df, "VALOR DA MULTA") or pd.Series(1.0, index=df.index),
            orgao      = col(df, "ÓRGÃO SANCIONADOR"),
            ano        = extrair_ano(col(df, "DATA INÍCIO SANÇÃO").astype(str)),
            funcao     = col(df, "CATEGORIA DA SANÇÃO"),
            favorecido = col(df, "NOME DO SANCIONADO"),
            cnpj       = col(df, "CPF OU CNPJ DO SANCIONADO"),
            fonte      = fonte,
        )

    _ingerir_ssh_por_arquivo(
        fonte,
        [f"{SSH_BASE_PATH}/cnep/ano=2026/mes=03"],
        construir, chunk_size,
    )


def ingerir_convenios(chunk_size: int = CHUNK_SIZE) -> None:
    fonte = "CONVENIOS"

    def construir(df: pd.DataFrame, _p: str) -> "pd.DataFrame | None":
        return unificar(
            df,
            valor      = val_col(df, "VALOR LIBERADO", "VALOR CONVÊNIO") or pd.Series(1.0, index=df.index),
            orgao      = col(df, "NOME ÓRGÃO CONCEDENTE", "NOME ÓRGÃO SUPERIOR"),
            ano        = extrair_ano(col(df, "DATA PUBLICAÇÃO").astype(str)),
            funcao     = col(df, "TIPO INSTRUMENTO", "SITUAÇÃO CONVÊNIO"),
            favorecido = col(df, "NOME CONVENENTE"),
            cnpj       = col(df, "CÓDIGO CONVENENTE"),
            fonte      = fonte,
        )

    _ingerir_ssh_por_arquivo(
        fonte,
        [f"{SSH_BASE_PATH}/convenios/ano=2026/mes=02"],
        construir, chunk_size,
    )


def ingerir_cpcc(chunk_size: int = CHUNK_SIZE) -> None:
    fonte = "CPCC"

    def construir(df: pd.DataFrame, _p: str) -> "pd.DataFrame | None":
        return unificar(
            df,
            valor      = val_col(df, "VALOR TRANSAÇÃO") or pd.Series(1.0, index=df.index),
            orgao      = col(df, "NOME ÓRGÃO SUPERIOR", "NOME ÓRGÃO"),
            ano        = pd.to_numeric(col(df, "ANO EXTRATO"), errors="coerce").astype("Int64"),
            funcao     = col(df, "TIPO AQUISIÇÃO"),
            favorecido = col(df, "NOME FAVORECIDO"),
            cnpj       = col(df, "CNPJ OU CPF FAVORECIDO"),
            fonte      = fonte,
        )

    _ingerir_ssh_por_arquivo(
        fonte, _prefixos_ano_mes_ssh("cpcc", ANOS["cpcc"]),
        construir, chunk_size,
    )


def ingerir_cpdc(chunk_size: int = CHUNK_SIZE) -> None:
    fonte = "CPDC"

    def construir(df: pd.DataFrame, _p: str) -> "pd.DataFrame | None":
        return unificar(
            df,
            valor      = val_col(df, "VALOR TRANSAÇÃO") or pd.Series(1.0, index=df.index),
            orgao      = col(df, "NOME ÓRGÃO SUPERIOR", "NOME ÓRGÃO"),
            ano        = pd.to_numeric(col(df, "ANO EXTRATO"), errors="coerce").astype("Int64"),
            funcao     = col(df, "NOME CONVENENTE", "EXECUTOR DESPESA"),
            favorecido = col(df, "NOME FAVORECIDO"),
            cnpj       = col(df, "CNPJ OU CPF FAVORECIDO"),
            fonte      = fonte,
        )

    _ingerir_ssh_por_arquivo(
        fonte, _prefixos_ano_mes_ssh("cpdc", ANOS["cpdc"]),
        construir, chunk_size,
    )


def ingerir_cpgf(chunk_size: int = CHUNK_SIZE) -> None:
    fonte = "CPGF"

    def construir(df: pd.DataFrame, _p: str) -> "pd.DataFrame | None":
        return unificar(
            df,
            valor      = val_col(df, "VALOR TRANSAÇÃO") or pd.Series(1.0, index=df.index),
            orgao      = col(df, "NOME ÓRGÃO SUPERIOR"),
            ano        = pd.to_numeric(col(df, "ANO EXTRATO"), errors="coerce").astype("Int64"),
            funcao     = col(df, "NOME ÓRGÃO"),
            favorecido = col(df, "NOME FAVORECIDO"),
            cnpj       = col(df, "CNPJ OU CPF FAVORECIDO"),
            fonte      = fonte,
        )

    _ingerir_ssh_por_arquivo(
        fonte, _prefixos_ano_mes_ssh("cpgf", ANOS["cpgf"]),
        construir, chunk_size,
    )


def ingerir_licitacoes(chunk_size: int = CHUNK_SIZE) -> None:
    fonte = "LICITACOES"

    def construir(df: pd.DataFrame, prefix: str) -> "pd.DataFrame | None":
        if "Nome Participante" not in df.columns and "Nome Vencedor" not in df.columns:
            return None
        if "Flag Vencedor" in df.columns:
            df = df[df["Flag Vencedor"].astype(str).str.upper().isin(["S", "SIM", "1", "TRUE"])]
        if df.empty:
            return None
        ano = _ano_do_path(prefix)
        return unificar(
            df,
            valor      = val_col(df, "Valor Licitação", "Valor Empenho (R$)", "Valor Item") or pd.Series(1.0, index=df.index),
            orgao      = col(df, "Nome Órgão Superior", "Nome Órgão"),
            ano        = pd.Series(ano, index=df.index, dtype="Int64"),
            funcao     = col(df, "Modalidade Compra"),
            favorecido = col(df, "Nome Participante", "Nome Vencedor"),
            cnpj       = col(df, "Código Participante", "Código Vencedor"),
            fonte      = fonte,
        )

    _ingerir_ssh_por_arquivo(
        fonte, _prefixos_ano_mes_ssh("licitacoes", ANOS["licitacoes"]),
        construir, chunk_size,
    )


def ingerir_compras(chunk_size: int = CHUNK_SIZE) -> None:
    fonte = "COMPRAS"

    def construir(df: pd.DataFrame, prefix: str) -> "pd.DataFrame | None":
        v = val_col(df, "Valor Item", "Valor Inicial Compra", "Valor Final Compra", "Valor Apostilamento")
        if v is None:
            return None
        ano = _ano_do_path(prefix)
        return unificar(
            df,
            valor      = v,
            orgao      = col(df, "Nome Órgão Superior", "Nome Órgão"),
            ano        = pd.Series(ano, index=df.index, dtype="Int64"),
            funcao     = col(df, "Descrição Item Compra", "Modalidade Compra", "Objeto"),
            favorecido = col(df, "Nome Contratado"),
            cnpj       = col(df, "Código Contratado", "Código UG"),
            fonte      = fonte,
        )

    _ingerir_ssh_por_arquivo(
        fonte, _prefixos_ano_mes_ssh("compras", ANOS["compras"]),
        construir, chunk_size,
    )


def ingerir_viagens(chunk_size: int = CHUNK_SIZE) -> None:
    fonte = "VIAGENS"

    def construir(df: pd.DataFrame, prefix: str) -> "pd.DataFrame | None":
        v = val_col(df, "Valor", "Valor diárias", "Valor passagens", "Valor da passagem")
        if v is None:
            return None
        ano = _ano_do_path(prefix)
        return unificar(
            df,
            valor      = v,
            orgao      = col(df, "Nome do órgão superior", "Nome do órgao pagador"),
            ano        = pd.Series(ano, index=df.index, dtype="Int64"),
            funcao     = col(df, "Tipo de pagamento", "Motivo"),
            favorecido = col(df, "Nome"),
            cnpj       = col(df, "CPF viajante"),
            fonte      = fonte,
        )

    _ingerir_ssh_por_arquivo(
        fonte, _prefixos_ano_ssh("viagens", ANOS["viagens"]),
        construir, chunk_size,
    )


def ingerir_despesas(chunk_size: int = CHUNK_SIZE) -> None:
    fonte = "DESPESAS"

    def construir(df: pd.DataFrame, prefix: str) -> "pd.DataFrame | None":
        v = val_col(df, "Valor Pago (R$)", "Valor Liquidado (R$)",
                    "Valor Restos a Pagar Pagos (R$)", "Valor Total")
        if v is None:
            return None
        ano = _ano_do_path(prefix)
        return unificar(
            df,
            valor      = v,
            orgao      = col(df, "Órgão Superior", "Órgão"),
            ano        = pd.Series(ano, index=df.index, dtype="Int64"),
            funcao     = col(df, "Função", "Elemento de Despesa", "Tipo Documento"),
            favorecido = col(df, "Favorecido"),
            cnpj       = col(df, "Código Favorecido"),
            fonte      = fonte,
        )

    _ingerir_ssh_por_arquivo(
        fonte, _prefixos_ano_mes_ssh("despesas", ANOS["despesas"]),
        construir, chunk_size,
    )


def ingerir_despesas_execucao(chunk_size: int = CHUNK_SIZE) -> None:
    fonte = "DESPESAS_EXECUCAO"

    def construir(df: pd.DataFrame, prefix: str) -> "pd.DataFrame | None":
        v = val_col(df, "Valor Pago (R$)", "Valor Liquidado (R$)", "Valor Empenhado (R$)")
        if v is None:
            return None
        ano = _ano_do_path(prefix)
        return unificar(
            df,
            valor      = v,
            orgao      = col(df, "Nome Órgão Superior", "Nome Órgão Subordinado"),
            ano        = pd.Series(ano, index=df.index, dtype="Int64"),
            funcao     = col(df, "Nome Função"),
            favorecido = col(df, "Nome Autor Emenda", "Nome Subtítulo"),
            cnpj       = col(df, "Código Autor Emenda"),
            fonte      = fonte,
        )

    _ingerir_ssh_por_arquivo(
        fonte, _prefixos_ano_mes_ssh("despesas-execucao", ANOS["despesas_execucao"]),
        construir, chunk_size,
    )


def ingerir_emendas_parlamentares(chunk_size: int = CHUNK_SIZE) -> None:
    fonte = "EMENDAS_PARLAMENTARES"

    def construir(df: pd.DataFrame, _p: str) -> "pd.DataFrame | None":
        return unificar(
            df,
            valor      = val_col(df, "Valor Empenhado", "Valor Pago", "Valor Recebido") or pd.Series(1.0, index=df.index),
            orgao      = col(df, "UF Favorecido", "UF"),
            ano        = pd.to_numeric(col(df, "Ano da Emenda", "Ano/Mês"), errors="coerce").astype("Int64"),
            funcao     = col(df, "Tipo de Emenda"),
            favorecido = col(df, "Favorecido"),
            cnpj       = col(df, "Código do Favorecido"),
            fonte      = fonte,
        )

    _ingerir_ssh_por_arquivo(
        fonte,
        [f"{SSH_BASE_PATH}/emendas-parlamentares"],
        construir, chunk_size,
    )


def ingerir_transferencias(chunk_size: int = CHUNK_SIZE) -> None:
    fonte = "TRANSFERENCIAS"

    def construir(df: pd.DataFrame, prefix: str) -> "pd.DataFrame | None":
        ano = _ano_do_path(prefix)
        return unificar(
            df,
            valor      = val_col(df, "VALOR TRANSFERIDO") or pd.Series(1.0, index=df.index),
            orgao      = col(df, "NOME ÓRGÃO"),
            ano        = pd.Series(ano, index=df.index, dtype="Int64"),
            funcao     = col(df, "TIPO TRANSFERÊNCIA", "NOME FUNÇÃO"),
            favorecido = col(df, "NOME FAVORECIDO"),
            cnpj       = col(df, "CÓDIGO FAVORECIDO"),
            fonte      = fonte,
        )

    _ingerir_ssh_por_arquivo(
        fonte, _prefixos_ano_mes_ssh("transferencias", ANOS["transferencias"]),
        construir, chunk_size,
    )


def ingerir_bndes_financiamento(chunk_size: int = CHUNK_SIZE) -> None:
    """BNDES Financiamento: lê 2 arquivos consolidados via SFTP."""
    fonte = "BNDES_FINANCIAMENTO"
    log.info("Iniciando ingestão SSH: %s", fonte)

    bndes_files = [
        f"{SSH_BNDES_PATH}/modulo=operacoes-de-financiamento/operacoes-financiamento-operacoes-indiretas-automaticas.parquet",
        f"{SSH_BNDES_PATH}/modulo=operacoes-de-financiamento/operacoes-financiamento-operacoes-nao-automaticas.parquet",
    ]

    ssh  = _make_ssh_client()
    sftp = ssh.open_sftp()
    dfs: list[pd.DataFrame] = []

    try:
        for remote in bndes_files:
            df = _ler_parquet_sftp(sftp, remote)
            if not df.empty:
                dfs.append(df)
    finally:
        sftp.close()
        ssh.close()

    if not dfs:
        log.warning("%s: nenhum arquivo encontrado.", fonte)
        return

    df = pd.concat(dfs, ignore_index=True)
    del dfs; gc.collect()

    v = val_col(df, "valor_desembolsado_reais", "valor_contratado_reais", "valor_da_operacao_em_reais")
    if v is None:
        log.warning("%s: nenhuma coluna de valor.", fonte)
        del df; return

    result = unificar(
        df,
        valor      = v,
        orgao      = col(df, "setor_bndes"),
        ano        = extrair_ano(df["data_da_contratacao"].astype(str)),
        funcao     = col(df, "subsetor_bndes"),
        favorecido = col(df, "cliente"),
        cnpj       = col(df, "cpf_cnpj", "cnpj"),
        fonte      = fonte,
    )
    del df; gc.collect()
    gravar(result, fonte, chunk_size)


def ingerir_bndes_exportacao(chunk_size: int = CHUNK_SIZE) -> None:
    """BNDES Exportação: tenta múltiplos prefixos históricos (typo no servidor)."""
    fonte = "BNDES_EXPORTACAO"
    log.info("Iniciando ingestão SSH: %s", fonte)

    prefixes = [
        "operacoes-de-exportacao-pre-e-pos-embarque",
        "operacoes-de-exportacaoo-pre-e-pos-embarque",
        "operacoes-de-exportacao",
    ]

    ssh  = _make_ssh_client()
    sftp = ssh.open_sftp()
    df   = pd.DataFrame()

    try:
        for prefix in prefixes:
            remote_dir = f"{SSH_BNDES_PATH}/modulo={prefix}"
            arquivos   = _listar_parquets_sftp(sftp, remote_dir)
            if not arquivos:
                continue
            dfs = [_ler_parquet_sftp(sftp, a) for a in arquivos]
            dfs = [d for d in dfs if not d.empty]
            if dfs:
                df = pd.concat(dfs, ignore_index=True)
                del dfs; gc.collect()
                break
    finally:
        sftp.close()
        ssh.close()

    if df.empty:
        log.warning("%s: fonte não encontrada no servidor.", fonte)
        return

    v = val_col(df, "valor_desembolsado_em_reais", "valor_da_operacao_em_reais")
    if v is None:
        log.warning("%s: sem coluna de valor.", fonte)
        del df; return

    result = unificar(
        df,
        valor      = v,
        orgao      = col(df, "setor_bndes"),
        ano        = extrair_ano(df["data_da_contratacao"].astype(str)),
        funcao     = col(df, "subsetor_bndes"),
        favorecido = col(df, "exportador", "cliente"),
        cnpj       = col(df, "cnpj_do_exportador", "cpf_cnpj"),
        fonte      = fonte,
    )
    del df; gc.collect()
    gravar(result, fonte, chunk_size)


# ── Registro de ingestores ────────────────────────────────────────────────────

INGESTORES: dict[str, Callable] = {
    "acordos_leniencia":        ingerir_acordos_leniencia,
    "apoiamento_emendas":       ingerir_apoiamento_emendas,
    "auxilio_brasil":           ingerir_auxilio_brasil,
    "auxilio_emergencial":      ingerir_auxilio_emergencial,
    "auxilio_reconstrucao":     ingerir_auxilio_reconstrucao,
    "bolsa_familia_pagamentos": ingerir_bolsa_familia_pagamentos,
    "bolsa_familia_saques":     ingerir_bolsa_familia_saques,
    "bpc":                      ingerir_bpc,
    "ceaf":                     ingerir_ceaf,
    "ceis":                     ingerir_ceis,
    "cepim":                    ingerir_cepim,
    "cnep":                     ingerir_cnep,
    "compras":                  ingerir_compras,
    "convenios":                ingerir_convenios,
    "cpcc":                     ingerir_cpcc,
    "cpdc":                     ingerir_cpdc,
    "cpgf":                     ingerir_cpgf,
    "despesas":                 ingerir_despesas,
    "despesas_execucao":        ingerir_despesas_execucao,
    "emendas_parlamentares":    ingerir_emendas_parlamentares,
    "licitacoes":               ingerir_licitacoes,
    "transferencias":           ingerir_transferencias,
    "viagens":                  ingerir_viagens,
    "bndes_financiamento":      ingerir_bndes_financiamento,
    "bndes_exportacao":         ingerir_bndes_exportacao,
}


# ── Entrypoint ────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingestão SSH → DuckDB local")
    parser.add_argument("--fonte", choices=list(INGESTORES.keys()),
                        help="Ingere só uma fonte específica.")
    parser.add_argument("--force", action="store_true",
                        help="Reingere mesmo que a fonte já exista no DB.")
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE, dest="chunk_size",
                        help=f"Registros por chunk ao gravar no DuckDB (padrão {CHUNK_SIZE:,}).")
    return parser.parse_args()


def _resumo_db() -> None:
    with get_db() as db:
        rows = db.execute("""
            SELECT fonte, COUNT(*) AS n, MIN(ano) AS ano_min, MAX(ano) AS ano_max
            FROM dados GROUP BY fonte ORDER BY fonte
        """).fetchall()
    log.info("Estado atual do DB (%s):", DB_PATH)
    for fonte, n, ano_min, ano_max in rows:
        log.info("  %-32s %10d registros  (%s → %s)", fonte, n, ano_min, ano_max)


def main() -> None:
    args = _parse_args()
    get_db().close()  # garante schema

    fontes_alvo: list[str] = [args.fonte] if args.fonte else list(INGESTORES.keys())

    if not args.force:
        ja = [f for f in fontes_alvo if fonte_ja_ingerida(f.upper())]
        fontes_alvo = [f for f in fontes_alvo if f not in ja]
        if ja:
            log.info("Já ingeridas (use --force): %s", ", ".join(ja))

    if not fontes_alvo:
        log.info("Todas as fontes já estão no DB.")
        return

    log.info(
        "Ingerindo SEQUENCIALMENTE %d fonte(s) | chunk_size=%d",
        len(fontes_alvo), args.chunk_size,
    )
    t0    = time.perf_counter()
    erros: dict[str, str] = {}

    for nome in fontes_alvo:
        try:
            INGESTORES[nome](chunk_size=args.chunk_size)
        except Exception as exc:
            erros[nome] = str(exc)
            log.error("%s falhou: %s", nome, exc)
        finally:
            gc.collect()

    log.info("Ingestão concluída em %.1fs.", time.perf_counter() - t0)
    _resumo_db()

    if erros:
        for nome, msg in erros.items():
            log.error("Erro em '%s': %s", nome, msg)
        sys.exit(1)


if __name__ == "__main__":
    main()
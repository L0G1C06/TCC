"""S3 infrastructure utilities — shared by data_loader, partition, and M2 reader."""

import io
import json
import logging
import os
from pathlib import PurePosixPath

import boto3
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from botocore.config import Config
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# ── Configuração ──────────────────────────────────────────────────────────────

S3_BUCKET      = os.getenv("RUMOLOG_S3_BUCKET", "storage-rumolog")
S3_PREFIX_ROOT = os.getenv("RUMOLOG_S3_PREFIX", "data/")

_S3_CONFIG = Config(
    retries={"max_attempts": 5, "mode": "adaptive"},
    connect_timeout=10,
    read_timeout=120,
)


# ── Exceções ──────────────────────────────────────────────────────────────────

class PartitionReadError(Exception):
    """Raised when a partition cannot be read at all (zero files succeeded)."""
    pass


class CorruptedParquetError(Exception):
    """Raised when a parquet file is corrupted and cannot be recovered."""
    pass


# ── S3 client ─────────────────────────────────────────────────────────────────

def s3_client():
    return boto3.client("s3", config=_S3_CONFIG)


# ── Validação de chaves ───────────────────────────────────────────────────────

def is_valid_parquet_key(key: str) -> bool:
    """
    Aceita qualquer .parquet que não seja arquivo oculto ou artefato de SO.
    Os arquivos reais da pipeline de ingestão são nomeados tmp*.parquet.
    """
    name = PurePosixPath(key).name
    return (
        name.endswith(".parquet")
        and not name.startswith(".")   # ocultos Unix
        and not name.startswith("~")   # temporários Windows
    )


# ── Listagem de partições ─────────────────────────────────────────────────────

def list_partition_prefixes(
    module_prefix: str,
    bucket: str = S3_BUCKET,
) -> dict[str, int]:
    """
    Agrupa o tamanho total (bytes) por prefixo de partição.

    Retorna dict[partition_prefix → total_bytes].
    Usado por find_partitions() em partition.py.
    """
    client          = s3_client()
    partition_stats: dict[str, int] = {}
    kwargs: dict    = {"Bucket": bucket, "Prefix": module_prefix}

    while True:
        response = client.list_objects_v2(**kwargs)
        for obj in response.get("Contents", []):
            key  = obj["Key"]
            size = obj["Size"]
            if is_valid_parquet_key(key):
                parent = str(PurePosixPath(key).parent) + "/"
                partition_stats[parent] = partition_stats.get(parent, 0) + size

        if response.get("IsTruncated"):
            kwargs["ContinuationToken"] = response["NextContinuationToken"]
        else:
            break

    return partition_stats


# ── Deleção de objetos ────────────────────────────────────────────────────────

def delete_s3_object(key: str, bucket: str = S3_BUCKET) -> bool:
    """
    Deleta um único objeto S3.
    Retorna True se bem-sucedido, False caso contrário.
    """
    client = s3_client()
    try:
        client.delete_object(Bucket=bucket, Key=key)
        logger.info("Deleted corrupted file: s3://%s/%s", bucket, key)
        return True
    except ClientError as e:
        logger.error("Failed to delete %s: %s", key, e)
        return False


def remove_partition_files(
    partition_prefix: str,
    bucket: str = S3_BUCKET,
) -> int:
    """
    Localiza e deleta apenas os arquivos .parquet dentro de uma partição.

    Retorna a quantidade de arquivos deletados.
    """
    client        = s3_client()
    deleted_count = 0

    try:
        response = client.list_objects_v2(Bucket=bucket, Prefix=partition_prefix)
        if "Contents" not in response:
            return 0

        for obj in response["Contents"]:
            key = obj["Key"]
            if is_valid_parquet_key(key):
                if delete_s3_object(key, bucket):
                    deleted_count += 1

        if deleted_count > 0:
            logger.info(
                "Limpeza técnica: %d arquivo(s) .parquet removidos de %s",
                deleted_count, partition_prefix,
            )
    except Exception as e:
        logger.error("Erro ao limpar arquivos Parquet em %s: %s", partition_prefix, e)

    return deleted_count


# ── Recovery de Parquet corrompido ────────────────────────────────────────────

def try_recovery_read(
    key: str,
    bucket: str,
    columns: list[str] | None = None,
) -> pa.Table | None:
    """
    Tenta recuperar um arquivo parquet corrompido com três estratégias.

    Estratégias (em ordem):
    1. Leitura com validação de schema desabilitada
    2. Leitura de row groups individualmente
    3. Fallback para pandas

    Retorna PyArrow Table se recuperação bem-sucedida, None caso contrário.
    """
    client = s3_client()

    # Estratégia 1: leitura com validação mínima
    try:
        obj = client.get_object(Bucket=bucket, Key=key)
        buf = io.BytesIO(obj["Body"].read())
        pf  = pq.ParquetFile(buf)
        return pf.read(columns=columns)
    except Exception as e:
        logger.debug("Strategy 1 failed for %s: %s", key, e)

    # Estratégia 2: row groups individuais
    try:
        obj = client.get_object(Bucket=bucket, Key=key)
        buf = io.BytesIO(obj["Body"].read())
        pf  = pq.ParquetFile(buf)

        tables = []
        for i in range(pf.num_row_groups):
            try:
                tables.append(pf.read_row_group(i, columns=columns))
            except Exception as row_err:
                logger.warning("Failed row group %d in %s: %s", i, key, row_err)

        if tables:
            return pa.concat_tables(tables, promote_options="default")
    except Exception as e:
        logger.debug("Strategy 2 failed for %s: %s", key, e)

    # Estratégia 3: fallback pandas
    try:
        obj = client.get_object(Bucket=bucket, Key=key)
        buf = io.BytesIO(obj["Body"].read())
        df  = pd.read_parquet(buf, engine="pyarrow", use_nullable_dtypes=True)
        if columns:
            df = df[[c for c in columns if c in df.columns]]
        return pa.Table.from_pandas(df)
    except Exception as e:
        logger.debug("Strategy 3 failed for %s: %s", key, e)

    return None


# ── S3Reader — descoberta de módulos e inputs do M2 ───────────────────────────

class S3Reader:
    """
    Leitura de metadados de elegibilidade do S3.
    Usado pelo M2 para descobrir módulos elegíveis e extrair contadores.
    """

    def __init__(self, bucket: str = S3_BUCKET):
        self.bucket = bucket
        self.client = s3_client()

    # ── Leitura genérica ──────────────────────────────────────────────────────

    def load_json(self, key: str) -> dict:
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return json.loads(response["Body"].read().decode("utf-8"))

    # ── Descoberta de módulos ─────────────────────────────────────────────────

    def list_eligible_modules(
        self,
        root_prefix: str = "data/portal_da_transparencia/parquet/",
    ) -> list[str]:
        """
        Varre o S3 em busca de _MODULE_ELIGIBILITY.json e retorna os paths
        dos módulos com ao menos uma coluna elegível.
        """
        eligible_paths = []
        paginator      = self.client.get_paginator("list_objects_v2")

        for page in paginator.paginate(Bucket=self.bucket, Prefix=root_prefix):
            for obj in page.get("Contents", []):
                if obj["Key"].endswith("_MODULE_ELIGIBILITY.json"):
                    module_path = str(PurePosixPath(obj["Key"]).parent)
                    if self._is_module_eligible(obj["Key"]):
                        eligible_paths.append(module_path)

        return eligible_paths

    def _is_module_eligible(self, report_key: str) -> bool:
        try:
            report = self.load_json(report_key)
            return report.get("eligible", False)
        except Exception as e:
            logger.error("Erro ao validar elegibilidade em %s: %s", report_key, e)
            return False

    # ── Descoberta de partições ───────────────────────────────────────────────

    def list_eligible_partitions(self, module_path: str) -> list[str]:
        """
        Lista as partições do módulo com _eligibility.json elegível.
        Exclui o _MODULE_ELIGIBILITY.json — só partições individuais.
        """
        prefix    = module_path.rstrip("/") + "/"
        paginator = self.client.get_paginator("list_objects_v2")
        eligible  = []

        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if (key.endswith("_eligibility.json")
                        and "_MODULE_ELIGIBILITY.json" not in key):
                    partition_path = str(PurePosixPath(key).parent)
                    if self._is_partition_eligible(key):
                        eligible.append(partition_path)

        return sorted(eligible)

    def _is_partition_eligible(self, report_key: str) -> bool:
        try:
            report = self.load_json(report_key)
            return report.get("eligible", False)
        except Exception as e:
            logger.error("Erro ao validar elegibilidade em %s: %s", report_key, e)
            return False

    # ── Input para o M2Engine — nível módulo ──────────────────────────────────

    def get_analysis_input(self, module_path: str) -> dict[str, dict]:
        """
        Lê o _MODULE_ELIGIBILITY.json e extrai contadores brutos
        de todas as colunas elegíveis para as três lanes do M2.
        """
        key    = f"{module_path.rstrip('/')}/_MODULE_ELIGIBILITY.json"
        report = self.load_json(key)
        return self._extract_inputs(report, level="módulo")

    # ── Input para o M2Engine — nível partição ────────────────────────────────

    def get_partition_input(self, partition_path: str) -> dict[str, dict]:
        """
        Lê o _eligibility.json de uma partição individual e extrai
        contadores brutos de todas as colunas elegíveis.
        """
        key    = f"{partition_path.rstrip('/')}/_eligibility.json"
        report = self.load_json(key)
        return self._extract_inputs(report, level="partição")

    # ── Extração comum ────────────────────────────────────────────────────────

    def _extract_inputs(self, report: dict, level: str) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for col, data in report.get("columns", {}).items():
            inputs = parse_column_inputs(data, col)
            if inputs is not None:
                result[col] = inputs
            else:
                logger.debug(
                    "[%s] Coluna '%s' inelegível — ignorada.", level, col
                )
        return result


# ── Helpers de parsing ────────────────────────────────────────────────────────

def _parse_counts(source: dict, counts_key: str) -> dict[str, int]:
    return {str(k): int(v) for k, v in source.get(counts_key, {}).items()}


def parse_column_inputs(data: dict, col: str) -> dict | None:
    if not data.get("eligible"):
        return None

    trunc = data.get("truncation_diagnostics", {})
    first = _parse_counts(data,  "first_digit_counts")
    two   = _parse_counts(data,  "two_digit_counts")
    last  = _parse_counts(trunc, "last_digit_counts")

    if not last:
        logger.warning(
            "Coluna '%s' sem last_digit_counts brutos — Lane 3 indisponível.", col
        )
    if not two:
        logger.warning(
            "Coluna '%s' sem two_digit_counts — Lane 2 indisponível.", col
        )

    return {
        "first_digit_counts": first,
        "two_digit_counts":   two,
        "last_digit_counts":  last,
    }
"""Data loading utilities — reads Parquet files directly from S3 via boto3."""

import io
import logging
import re
from collections.abc import Generator
from pathlib import PurePosixPath

import pyarrow as pa
import pyarrow.parquet as pq
import pandas as pd

from src.io.reader.s3_reader import (s3_client, is_valid_parquet_key, PartitionReadError, S3_BUCKET, try_recovery_read, \
                                     delete_s3_object)

logger = logging.getLogger(__name__)

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    tqdm = lambda x, **kwargs: x


def partition_prefix(partition_path: str) -> str:
    """
    Normalise a partition path to an S3 prefix string.

    Accepts:
      - Full S3 key prefix already:   'data/portal_da_transparencia/parquet/modulo=viagens/ano=2017/mes=unknown/'
      - Legacy local absolute path:   '/home/henry/storage-rumolog-s3/data/portal_da_transparencia/...'

    Returns an S3 prefix with trailing slash.
    """
    s = str(partition_path).strip()

    # Strip local filesystem prefix if present
    match = re.search(r'(data/.*)', s)
    if match:
        s = match.group(1)

    # Ensure trailing slash so list_objects scopes correctly
    if not s.endswith("/"):
        s += "/"

    return s


def list_partition_keys(prefix: str, bucket: str = S3_BUCKET) -> list[str]:
    """
    List all valid .parquet object keys under an S3 prefix.

    Args:
        prefix:  S3 key prefix, e.g. 'data/portal_da_transparencia/parquet/modulo=viagens/ano=2017/mes=unknown/'
        bucket:  S3 bucket name

    Returns:
        Sorted list of S3 object keys
    """
    client = s3_client()
    keys = []
    kwargs = {"Bucket": bucket, "Prefix": prefix}

    while True:
        response = client.list_objects_v2(**kwargs)
        for obj in response.get("Contents", []):
            key = obj["Key"]
            if is_valid_parquet_key(key):
                keys.append(key)
        if response.get("IsTruncated"):
            kwargs["ContinuationToken"] = response["NextContinuationToken"]
        else:
            break

    skipped_tmp = [
        PurePosixPath(obj["Key"]).name
        for obj in response.get("Contents", [])  # last page only, good enough for logging
        if obj["Key"].endswith(".parquet") and not is_valid_parquet_key(obj["Key"])
    ]
    if skipped_tmp:
        logger.warning("Skipped temp/hidden files in %s: %s", prefix, skipped_tmp)

    return sorted(keys)


def iter_partition_chunks(
        partition_path: str,
        columns: list[str],
        chunk_size: int = 100_000,
        bucket: str = S3_BUCKET,
        delete_corrupted: bool = True,
        use_recovery: bool = True,
        show_progress: bool = True,
        max_recovery_attempts: int = 3,
) -> Generator[pd.DataFrame, None, None]:
    prefix = partition_prefix(partition_path)
    keys = list_partition_keys(prefix, bucket)

    if not keys:
        raise PartitionReadError(f"No .parquet files found at s3://{bucket}/{prefix}")

    files_ok = 0
    files_failed = 0
    files_deleted = 0

    pbar = (tqdm(total=len(keys), desc="Files", unit="file", leave=False)
            if show_progress and TQDM_AVAILABLE else None)

    try:
        for key in keys:
            if pbar: pbar.set_postfix_str(PurePosixPath(key).name, refresh=False)

            success = False
            # --- TENTATIVA 1: Leitura Padrão ---
            try:
                client = s3_client()
                obj = client.get_object(Bucket=bucket, Key=key)
                buf = io.BytesIO(obj["Body"].read())
                pf = pq.ParquetFile(buf)

                available = set(pf.schema_arrow.names)
                cols_to_read = [c for c in columns if c in available]

                if cols_to_read:
                    for batch in pf.iter_batches(batch_size=chunk_size, columns=cols_to_read):
                        yield pa.Table.from_batches([batch]).to_pandas()
                success = True
                files_ok += 1

            except Exception as e:
                logger.warning("Standard read failed for %s: %s", key, e)

                # --- TENTATIVA 2 a N: Recovery Mode ---
                if use_recovery:
                    attempt = 1
                    while attempt <= max_recovery_attempts and not success:
                        logger.info("Recovery attempt %d/3 for %s", attempt, key)
                        recovered = try_recovery_read(key, bucket, columns)

                        if recovered is not None:
                            for batch in recovered.to_batches(max_chunksize=chunk_size):
                                yield batch.to_pandas()
                            success = True
                            files_ok += 1
                            logger.info("Recovery succeeded for %s", key)
                        else:
                            attempt += 1

                # --- FALHA TOTAL: Deletar se solicitado ---
                if not success:
                    files_failed += 1
                    if delete_corrupted:
                        # Chama sua função que deleta apenas o arquivo .parquet específico
                        if delete_s3_object(key, bucket):
                            files_deleted += 1

            if pbar: pbar.update(1)
    finally:
        if pbar: pbar.close()

    if files_ok == 0:
        raise PartitionReadError(f"All {files_failed} files at {prefix} failed.")

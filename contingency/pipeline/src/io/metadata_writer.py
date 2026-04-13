"""Metadata writing utilities — writes directly to S3."""

import json
import logging
import os
from typing import Any

import boto3

from src.core.serializable import convert_to_serializable

logger = logging.getLogger(__name__)

S3_BUCKET = os.getenv("RUMOLOG_S3_BUCKET", "storage-rumolog")


def write_eligibility_metadata(
    partition_path: str,
    eligibility: dict[str, Any],
    bucket: str = S3_BUCKET,
) -> str:
    """
    Write eligibility report as JSON to S3 alongside the partition data.

    Args:
        partition_path: S3 prefix, e.g. 'data/.../modulo=licitacoes/ano=2013/mes=05/'
        eligibility:    Eligibility report dict
        bucket:         S3 bucket name

    Returns:
        Full S3 key of the written metadata file
    """
    # Normalise prefix — ensure trailing slash then append filename
    prefix = partition_path if partition_path.endswith("/") else partition_path + "/"
    key    = prefix + "_eligibility.json"

    serializable = convert_to_serializable(eligibility)
    body         = json.dumps(serializable, indent=2, ensure_ascii=False).encode("utf-8")

    client = boto3.client("s3")
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=body,
        ContentType="application/json",
    )

    logger.debug("Wrote eligibility metadata to s3://%s/%s", bucket, key)
    return f"s3://{bucket}/{key}"
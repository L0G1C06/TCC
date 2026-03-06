import os
import duckdb
from django.conf import settings


class DataLakeConfig:

    BUCKET = settings.DATALAKE_BUCKET

    @staticmethod
    def storage_options() -> dict:
        return {
            "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
            "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
            "aws_region": os.getenv("AWS_DEFAULT_REGION", "sa-east-1"),
        }

    @classmethod
    def connect(cls) -> duckdb.DuckDBPyConnection:
        conn = duckdb.connect(":memory:")
        conn.execute("INSTALL httpfs; LOAD httpfs;")
        conn.execute(f"SET s3_region             = '{os.getenv('AWS_DEFAULT_REGION', 'sa-east-1')}'")
        conn.execute(f"SET s3_access_key_id      = '{settings.AWS_ACCESS_KEY_ID}'")
        conn.execute(f"SET s3_secret_access_key  = '{settings.AWS_SECRET_ACCESS_KEY}'")
        return conn
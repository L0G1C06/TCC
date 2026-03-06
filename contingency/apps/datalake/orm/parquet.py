import duckdb
from ..engine.s3 import DataLakeConfig


class DuckDBRelation:
    """
    Wrapper que mantém a conexão viva enquanto a Relation existir
    e delega todos os métodos nativos do DuckDB.
    """

    def __init__(self, conn: duckdb.DuckDBPyConnection, rel: duckdb.DuckDBPyRelation):
        self._conn = conn  # impede o GC de fechar a conexão
        self._rel = rel

    # delega qualquer atributo/método para a relation original
    def __getattr__(self, name):
        return getattr(self._rel, name)

    def __repr__(self):
        return repr(self._rel)


class ParquetEngine:

    BASE_PATH = "data"

    @classmethod
    def scan(cls, path: str, hive_partitioning: bool = True) -> DuckDBRelation:
        conn = DataLakeConfig.connect()
        s3_glob = (
            f"s3://{DataLakeConfig.BUCKET}"
            f"/{cls.BASE_PATH}/{path.rstrip('/')}/**/*.parquet"
        )
        rel = conn.read_parquet(s3_glob, hive_partitioning=hive_partitioning)
        return DuckDBRelation(conn, rel)
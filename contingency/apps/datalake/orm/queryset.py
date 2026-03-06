import polars as pl

from .parquet import ParquetEngine
from ..cache.memory import MemoryCache
from ..utils import make_cache_key


class PolarsQuerySet:
    # Ordem importa: reflete a hierarquia do Hive no S3
    PARTITION_COLS = ("modulo", "ano", "mes")

    def __init__(self, dataset_path: str):
        self.dataset_path = dataset_path
        self.partition_filters: dict = {}  # viram path: modulo=x/ano=y/mes=z
        self.col_filters: dict = {}  # viram pl.col() expressions
        self._lf: pl.LazyFrame | None = None

    # ------------------------------------------------------------------ #
    # LazyFrame — só instanciado na primeira leitura                       #
    # ------------------------------------------------------------------ #

    @property
    def lf(self) -> pl.LazyFrame:
        if self._lf is None:
            subpath = self.dataset_path.rstrip("/")  # ← remove barra final
            for col in self.PARTITION_COLS:
                if col in self.partition_filters:
                    subpath += f"/{col}={self.partition_filters[col]}"

            self._lf = ParquetEngine.scan(subpath)

            for field, value in self.col_filters.items():
                casted = self._cast_value(field, value)
                self._lf = self._lf.filter(pl.col(field) == casted)

        return self._lf

    # ------------------------------------------------------------------ #
    # Internos                                                             #
    # ------------------------------------------------------------------ #

    def _cast_value(self, field: str, value):
        schema = self.lf.collect_schema()
        col_type = schema.get(field)

        if col_type is None:
            return value

        if col_type in (pl.String, pl.Utf8):
            return str(value)

        if col_type in (pl.Int8, pl.Int16, pl.Int32, pl.Int64,
                        pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64):
            return int(value)

        if col_type in (pl.Float32, pl.Float64):
            return float(value)

        if col_type == pl.Boolean:
            return bool(value)

        return value

    # ------------------------------------------------------------------ #
    # API pública                                                          #
    # ------------------------------------------------------------------ #

    def filter(self, **kwargs):
        for field, value in kwargs.items():
            if field in self.PARTITION_COLS:
                # Partição → vira segmento do path S3, não filtro Polars
                self.partition_filters[field] = value
            else:
                # Coluna normal → vira expressão pl.col()
                self.col_filters[field] = value
        return self

    def limit(self, n: int):
        self._lf = self.lf.limit(n)
        return self

    def order_by(self, *fields: str, descending: bool = False):
        self._lf = self.lf.sort(list(fields), descending=descending)
        return self

    def select(self, *fields: str):
        self._lf = self.lf.select(list(fields))
        return self

    # ------------------------------------------------------------------ #
    # Materialização                                                        #
    # ------------------------------------------------------------------ #

    def collect(self) -> pl.DataFrame:
        key = make_cache_key(
            self.dataset_path,
            {**self.partition_filters, **self.col_filters}
        )

        cached = MemoryCache.get(key)
        if cached is not None:
            return cached

        df = self.lf.collect()
        MemoryCache.set(key, df)
        return df

    def all(self) -> list[dict]:
        return self.collect().to_dicts()

    def first(self) -> dict | None:
        df = self.limit(1).collect()
        return None if df.is_empty() else df.to_dicts()[0]

    def count(self) -> int:
        return self.lf.select(pl.len()).collect().item()

    def exists(self) -> bool:
        return self.count() > 0

import duckdb
import polars as pl
from .parquet import ParquetEngine


class DuckDBModel:
    """
    Classe base para modelos do Data Lake.

    Cada subclasse define dataset_path e ganha .scan() que
    devolve uma DuckDBPyRelation — use a API nativa do DuckDB
    ou converta para Polars com .pl() / .polars().

    Exemplo de uso:
        # DuckDB puro
        PortalTransparencia.scan()
            .filter("ano = '2024' AND mes = '01'")
            .select("cpf, valor, orgao")
            .order("valor DESC")
            .limit(100)
            .fetchdf()

        # Polars LazyFrame
        PortalTransparencia.polars(modulo="contratos", ano="2024")
            .filter(pl.col("valor") > 10_000)
            .select(["cpf", "valor"])
            .collect()
    """

    dataset_path: str = None

    # ------------------------------------------------------------------ #
    # Helpers de path                                                      #
    # ------------------------------------------------------------------ #

    @classmethod
    def _resolve_path(cls, **partitions: str) -> str:
        if cls.dataset_path is None:
            raise NotImplementedError(f"{cls.__name__} deve definir 'dataset_path'")

        PARTITION_ORDER = ("modulo", "ano", "mes")
        path = cls.dataset_path.rstrip("/")

        # injeta o modulo da classe se não foi passado explicitamente
        if "modulo" not in partitions and hasattr(cls, "modulo"):
            partitions = {"modulo": cls.modulo, **partitions}

        for col in PARTITION_ORDER:
            if col in partitions:
                path += f"/{col}={partitions[col]}"

        return path

    # ------------------------------------------------------------------ #
    # API principal                                                        #
    # ------------------------------------------------------------------ #

    @classmethod
    def scan(cls, **partitions: str) -> duckdb.DuckDBPyRelation:
        """
        Retorna uma DuckDBPyRelation.
        Partições opcionais viram segmentos do path S3 (sem varredura full).

        Uso:
            Vendas.scan()                          # tudo
            Vendas.scan(ano="2024")                # só ano=2024
            Vendas.scan(ano="2024", mes="03")      # ano + mês
        """
        return ParquetEngine.scan(cls._resolve_path(**partitions))

    @classmethod
    def polars(cls, **partitions: str) -> pl.LazyFrame:
        """
        Atalho para quem prefere trabalhar com Polars.
        Retorna um LazyFrame — chame .collect() quando quiser os dados.

        Uso:
            Vendas.polars(ano="2024").filter(pl.col("valor") > 500).collect()
        """
        rel = cls.scan(**partitions)
        # .arrow() é zero-copy entre DuckDB e Polars
        return pl.from_arrow(rel.arrow()).lazy()

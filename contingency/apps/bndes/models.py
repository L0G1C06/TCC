from apps.datalake.orm.model import DuckDBModel


class Bndes(DuckDBModel):
    dataset_path = "bndes/parquet/"
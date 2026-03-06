from apps.datalake.orm.model import DuckDBModel


class PortalTransparencia(DuckDBModel):
    dataset_path = "portal_da_transparencia/parquet/"
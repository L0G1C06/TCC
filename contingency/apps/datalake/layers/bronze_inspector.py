# apps/datalake/layers/bronze_inspector.py

from __future__ import annotations
from dataclasses import dataclass
import duckdb
import polars as pl

from apps.datalake.engine.s3 import DataLakeConfig
from apps.datalake.engine.scanner import S3PartitionScanner, PartitionMap


@dataclass
class ColumnInfo:
    name: str
    raw_type: str  # tipo exato que veio do parquet
    nullable: bool = True

    def __repr__(self):
        return f"{self.name}: {self.raw_type}"


@dataclass
class DatasetSchema:
    dataset: str
    modulo: str
    columns: list[ColumnInfo]
    partitions: PartitionMap

    def __repr__(self) -> str:
        lines = [f"\nDatasetSchema → {self.dataset} / modulo={self.modulo}"]
        lines.append("  Colunas:")
        for col in self.columns:
            lines.append(f"    {col.name:<35} {col.raw_type}")
        lines.append(f"\n  Partições disponíveis:")
        for ano in self.partitions.anos(self.modulo):
            meses = self.partitions.meses(self.modulo, ano)
            n_arquivos = sum(
                self.partitions.arquivos(self.modulo, ano, mes)
                for mes in meses
            )
            lines.append(f"    ano={ano}  meses={meses}  arquivos={n_arquivos}")
        return "\n".join(lines)


class BronzeInspector:
    """
    Combina S3PartitionScanner (estrutura Hive) com DuckDB (schema real)
    para gerar um mapa completo de cada dataset na camada Bronze.
    """

    def __init__(self):
        self._scanner = S3PartitionScanner()
        self._conn = DataLakeConfig.connect()

    def inspect(self, dataset_path: str) -> list[DatasetSchema]:
        pm = self._scanner.scan(dataset_path)
        schemas = []

        for modulo in pm.modulos:
            columns = self._read_schema(dataset_path, modulo, pm.is_flat(modulo))
            schemas.append(DatasetSchema(
                dataset=dataset_path,
                modulo=modulo,
                columns=columns,
                partitions=pm,
            ))

        return schemas

    def inspect_all(self, datasets: dict[str, str]) -> dict[str, list[DatasetSchema]]:
        """Inspeciona múltiplos datasets de uma vez."""
        return {
            nome: self.inspect(path)
            for nome, path in datasets.items()
        }

    # ── Interno ────────────────────────────────────────────────────────

    def _read_schema(self, dataset_path: str, modulo: str, flat: bool) -> list[ColumnInfo]:
        base = (
            f"s3://{DataLakeConfig.BUCKET}"
            f"/data/{dataset_path.rstrip('/')}"
            f"/modulo={modulo}"
        )
        # flat: arquivos direto no módulo; hive: desce recursivamente
        s3_glob = f"{base}/*.parquet" if flat else f"{base}/**/*.parquet"

        try:
            rel = self._conn.sql(
                f"SELECT * FROM read_parquet('{s3_glob}', "
                f"hive_partitioning=true, union_by_name=true) LIMIT 0"
            )
            return [
                ColumnInfo(name=name, raw_type=str(dtype))
                for name, dtype in zip(rel.columns, rel.dtypes)
            ]
        except Exception as e:
            return [ColumnInfo(name="__error__", raw_type=str(e))]

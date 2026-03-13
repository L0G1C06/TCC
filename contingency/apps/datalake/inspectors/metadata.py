# apps/datalake/inspectors/metadata.py
"""
Inspector para extração de metadados rápidos de datasets da camada Bronze.

Usa DuckDB para ler apenas uma amostra (LIMIT 100) dos arquivos parquet
e extrair:
- schema (nome, tipo, nullable)
- contagem de linhas aproximada
- valores únicos e nulos por coluna
- amostras de valores

Integra com o S3PartitionScanner para saber número de arquivos e partições.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List
import duckdb
import polars as pl

from apps.datalake.engine.s3 import DataLakeConfig
from apps.datalake.engine.scanner import S3PartitionScanner


@dataclass
class ColumnMetadata:
    """
    Metadados de uma coluna extraídos do parquet.
    """
    name: str
    raw_type: str
    nullable: bool
    sample_values: List[str] = None
    unique_count: int = 0
    null_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.raw_type,
            "nullable": self.nullable,
            "sample_values": self.sample_values,
            "unique_count": self.unique_count,
            "null_count": self.null_count,
        }


@dataclass
class DatasetMetadata:
    """
    Metadados completos de um dataset (modulo).
    """
    dataset_name: str
    modulo: str
    columns: List[ColumnMetadata]
    row_count: int
    total_files: int
    partitions_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "modulo": self.modulo,
            "schema": [c.to_dict() for c in self.columns],
            "row_count": self.row_count,
            "total_files": self.total_files,
            "partitions_count": self.partitions_count,
            "sample_values": {c.name: c.sample_values for c in self.columns if c.sample_values},
            "unique_counts": {c.name: c.unique_count for c in self.columns},
            "null_counts": {c.name: c.null_count for c in self.columns},
        }


class MetadataInspector:
    """
    Combina S3PartitionScanner (estrutura Hive) com DuckDB (schema real)
    para gerar um resumo leve de cada dataset na camada Bronze.
    """

    SAMPLE_SIZE = 100  # Limit de linhas para leitura leve

    def __init__(self):
        self._scanner = S3PartitionScanner()
        self._conn = DataLakeConfig.connect()

    def inspect(self, dataset_path: str, modulo: str) -> DatasetMetadata:
        """
        Inspeciona um único módulo de um dataset.
        """
        # 1. Escaneando estrutura Hive (arquivos e partições)
        pm = self._scanner.scan(dataset_path)
        
        # Contar arquivos e partições do módulo específico
        total_files = sum(
            pm.arquivos(modulo, ano, mes)
            for ano in pm.anos(modulo)
            for mes in pm.meses(modulo, ano)
        ) + pm.flat_modulos.get(modulo, 0)
        
        partitions_count = len(pm.anos(modulo)) * len(pm.meses(modulo, list(pm.anos(modulo))[0])) if pm.anos(modulo) else 0
        
        # 2. Lendo schema + amostra com DuckDB
        base_path = f"s3://{DataLakeConfig.BUCKET}/data/{dataset_path.rstrip('/')}/modulo={modulo}"
        
        # Detectar se é hive ou flat
        is_flat = modulo in pm.flat_modulos
        s3_glob = f"{base_path}/*.parquet" if is_flat else f"{base_path}/**/*.parquet"
        
        try:
            # Query para schema
            rel = self._conn.sql(
                f"SELECT * FROM read_parquet('{s3_glob}', "
                f"hive_partitioning=true, union_by_name=true) LIMIT 0"
            )
            
            # Query para amostra (compartilhar a mesma conexão)
            sample_rel = self._conn.sql(
                f"SELECT * FROM read_parquet('{s3_glob}', "
                f"hive_partitioning=true, union_by_name=true) LIMIT {self.SAMPLE_SIZE}"
            )
            
            # Converter para Polars para facilitar cálculos
            df = sample_rel.fetchdf()
            
            # Extrair metadados de cada coluna
            columns = []
            for col_name in df.columns:
                col_data = df[col_name]
                raw_type = str(col_data.dtype)
                
                # Determinar nullable
                null_count = int(col_data.isna().sum())
                nullable = null_count > 0
                
                # Valores únicos
                unique_count = int(col_data.nunique())
                
                # Amostras (máximo 3 valores não-nulos)
                non_null_values = col_data.dropna().head(3).astype(str).tolist()
                
                columns.append(ColumnMetadata(
                    name=col_name,
                    raw_type=raw_type,
                    nullable=nullable,
                    sample_values=non_null_values if non_null_values else None,
                    unique_count=unique_count,
                    null_count=null_count,
                ))
            
            return DatasetMetadata(
                dataset_name=dataset_path,
                modulo=modulo,
                columns=columns,
                row_count=len(df),  # Aproximado (pode ser menor que SAMPLE_SIZE se o dataset for pequeno)
                total_files=total_files,
                partitions_count=partitions_count,
            )
            
        except Exception as e:
            # Em caso de erro, retornar schema vazio com mensagem de erro
            return DatasetMetadata(
                dataset_name=dataset_path,
                modulo=modulo,
                columns=[],
                row_count=0,
                total_files=total_files,
                partitions_count=partitions_count,
            )

    def inspect_all(self, dataset_path: str) -> List[DatasetMetadata]:
        """
        Inspeciona todos os módulos de um dataset.
        """
        pm = self._scanner.scan(dataset_path)
        metadatas = []
        
        for modulo in pm.modulos:
            metadata = self.inspect(dataset_path, modulo)
            metadatas.append(metadata)
        
        return metadatas

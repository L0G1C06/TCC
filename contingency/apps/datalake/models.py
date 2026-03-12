# apps/datalake/models.py
"""
Modelo de cache para metadados de datasets.

Guarda resumos rápidos de cada dataset para visualização em cards
(com nome das colunas, tipos, contagens, etc.), sem precisar ler
o parquet completo toda vez.
"""

from __future__ import annotations
from django.db import models


class DatasetMetadata(models.Model):
    """
    Cache de metadados de um dataset da camada Bronze.

    Atualizado periodicamente via management command `extract_metadata`.
    Usado para renderizar cards no frontend (ex: dashboard de datasets).
    """

    dataset_name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Nome do dataset (ex: 'portal_da_transparencia/compras')"
    )
    
    modulo = models.CharField(
        max_length=100,
        blank=True,
        help_text="Módulo Hive (ex: 'compras', 'licitacoes')"
    )
    
    schema = models.JSONField(
        help_text="Lista de colunas: [{'name': '...', 'type': 'VARCHAR', 'nullable': True}, ...]"
    )
    
    row_count = models.BigIntegerField(
        default=0,
        help_text="Número aproximado de linhas (baseado no sample)"
    )
    
    sample_values = models.JSONField(
        null=True, blank=True,
        help_text="Exemplos de valores por coluna: {'col': ['val1', 'val2', ...]}"
    )
    
    unique_counts = models.JSONField(
        null=True, blank=True,
        help_text="Contagem de valores únicos por coluna: {'col': 123}"
    )
    
    null_counts = models.JSONField(
        null=True, blank=True,
        help_text="Contagem de valores nulos por coluna: {'col': 5}"
    )
    
    total_files = models.IntegerField(
        default=0,
        help_text="Número total de arquivos parquet encontrados"
    )
    
    partitions_count = models.IntegerField(
        default=0,
        help_text="Número total de partições Hive encontradas"
    )
    
    last_inspection = models.DateTimeField(
        auto_now=True,
        help_text="Data da última inspeção"
    )

    class Meta:
        verbose_name = "Metadata de Dataset"
        verbose_name_plural = "Metadados de Datasets"
        indexes = [
            models.Index(fields=["dataset_name"]),
            models.Index(fields=["modulo"]),
        ]

    def __str__(self):
        return f"{self.dataset_name} / {self.modulo or 'all'}"

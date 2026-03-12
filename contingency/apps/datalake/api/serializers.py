# apps/datalake/api/serializers.py
"""
Serializers para metadados de datasets.
"""

from rest_framework import serializers
from apps.datalake.models import DatasetMetadata


class DatasetMetadataSerializer(serializers.ModelSerializer):
    """
    Serializer completo para metadados.
    """
    class Meta:
        model = DatasetMetadata
        fields = [
            "dataset_name",
            "modulo",
            "schema",
            "row_count",
            "sample_values",
            "unique_counts",
            "null_counts",
            "total_files",
            "partitions_count",
            "last_inspection",
        ]


class DatasetMetadataCardSerializer(serializers.ModelSerializer):
    """
    Serializer simplificado para cards (frontend).
    Exclui dados pesados (amostras detalhadas) se necessário.
    """
    class Meta:
        model = DatasetMetadata
        fields = [
            "dataset_name",
            "modulo",
            "schema",
            "row_count",
            "total_files",
            "partitions_count",
            "last_inspection",
        ]

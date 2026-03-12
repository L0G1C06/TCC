# apps/datalake/api/views.py
"""
Views para metadados de datasets.
"""

from rest_framework import viewsets
from apps.datalake.models import DatasetMetadata
from .serializers import DatasetMetadataSerializer, DatasetMetadataCardSerializer
from drf_spectacular.utils import extend_schema, OpenApiParameter

@extend_schema(tags=['Metadata'])
class DatasetMetadataViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Retorna metadados completos dos datasets inspecionados.
    """
    queryset = DatasetMetadata.objects.all()
    serializer_class = DatasetMetadataSerializer


@extend_schema(
    tags=['Cards'],
    summary='Cards simplificados para exibição no frontend',
    parameters=[
        OpenApiParameter(
            name='modulo',
            description='Filtrar por módulo (ex: compras, viagens)',
            required=False,
            type=str,
        ),
    ],
)
class DatasetMetadataViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API para metadados de datasets.

    Endpoints:
        GET /api/metadata/           # Lista todos
        GET /api/metadata/{id}/      # Detalhes de um
        GET /api/metadata/cards/     # Cards simplificados (sem amostras pesadas)
    """
    queryset = DatasetMetadata.objects.all()
    serializer_class = DatasetMetadataSerializer

    def get_serializer_class(self):
        if self.action == 'list':
            return DatasetMetadataSerializer
        return super().get_serializer_class()


class DatasetMetadataCardViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet simplificado para cards (frontend).
    """
    queryset = DatasetMetadata.objects.all()
    serializer_class = DatasetMetadataCardSerializer

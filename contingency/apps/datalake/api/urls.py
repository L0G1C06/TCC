# apps/datalake/api/urls.py
"""
URLs para API de metadados.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DatasetMetadataViewSet, DatasetMetadataCardViewSet

router = DefaultRouter()
router.register(r'metadata', DatasetMetadataViewSet)
router.register(r'cards', DatasetMetadataCardViewSet, basename='cards')

urlpatterns = [
    path('', include(router.urls)),
]

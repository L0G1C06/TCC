from .queryset import PolarsQuerySet
from .parquet import ParquetEngine


class PolarsManager:

    def __init__(self, dataset_path: str):
        self.dataset_path = dataset_path

    def get_queryset(self) -> PolarsQuerySet:
        return PolarsQuerySet(self.dataset_path)

    def filter(self, **kwargs) -> PolarsQuerySet:
        return self.get_queryset().filter(**kwargs)

    def all(self) -> list[dict]:
        return self.get_queryset().all()

    def first(self) -> dict | None:
        return self.get_queryset().first()
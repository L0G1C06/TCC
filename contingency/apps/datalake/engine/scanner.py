from __future__ import annotations

import re
from dataclasses import dataclass, field
from collections import defaultdict

import boto3
from django.conf import settings

from .s3 import DataLakeConfig


# ── Estrutura de resultado ─────────────────────────────────────────────

@dataclass
class PartitionMap:
    dataset: str
    tree: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    # novo: guarda quantos arquivos existem em cada partição
    file_count: dict[str, int] = field(default_factory=dict)

    def _partition_key(self, modulo: str, ano: str, mes: str) -> str:
        return f"modulo={modulo}/ano={ano}/mes={mes}"

    def arquivos(self, modulo: str, ano: str, mes: str) -> int:
        return self.file_count.get(self._partition_key(modulo, ano, mes), 0)

    def __repr__(self) -> str:
        lines = [f"PartitionMap → {self.dataset}"]
        for modulo, anos in sorted(self.tree.items()):
            lines.append(f"  modulo={modulo}")
            for ano, meses in sorted(anos.items()):
                for mes in sorted(meses):
                    n = self.arquivos(modulo, ano, mes)
                    lines.append(f"    ano={ano}  mes={mes}  arquivos={n}")
        lines.append(f"  total de partições: {self.total_particoes()}")
        return "\n".join(lines)

    # ── helpers de leitura ─────────────────────────────────────────────

    @property
    def modulos(self) -> list[str]:
        return sorted(self.tree.keys())

    def anos(self, modulo: str) -> list[str]:
        return sorted(self.tree.get(modulo, {}).keys())

    def meses(self, modulo: str, ano: str) -> list[str]:
        return sorted(self.tree.get(modulo, {}).get(ano, []))

    def total_particoes(self) -> int:
        return sum(
            len(meses)
            for modulo in self.tree.values()
            for meses in modulo.values()
        )

    def __repr__(self) -> str:
        lines = [f"PartitionMap → {self.dataset}"]
        for modulo, anos in sorted(self.tree.items()):
            lines.append(f"  modulo={modulo}")
            for ano, meses in sorted(anos.items()):
                lines.append(f"    ano={ano}  meses={sorted(meses)}")
        lines.append(f"  total de partições: {self.total_particoes()}")
        return "\n".join(lines)


# ── Scanner ────────────────────────────────────────────────────────────

class S3PartitionScanner:
    """
    Varre o S3 e devolve um PartitionMap por dataset.

    Espera a estrutura Hive:
        s3://<bucket>/data/<dataset>/modulo=X/ano=Y/mes=Z/
    """

    BASE_PATH = "data"

    # regex que captura os três níveis de partição
    _RE = re.compile(
        r"modulo=(?P<modulo>[^/]+)"
        r"/ano=(?P<ano>[^/]+)"
        r"/mes=(?P<mes>[^/]+)"
    )

    def __init__(self):
        opts = DataLakeConfig.storage_options()
        self._s3 = boto3.client(
            "s3",
            aws_access_key_id=opts["aws_access_key_id"],
            aws_secret_access_key=opts["aws_secret_access_key"],
            region_name=opts["aws_region"],
        )
        self._bucket = DataLakeConfig.BUCKET

    # ── API pública ────────────────────────────────────────────────────

    def scan(self, dataset_path: str) -> PartitionMap:
        prefix = f"{self.BASE_PATH}/{dataset_path.strip('/')}/"
        tree: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
        file_count: dict[str, int] = defaultdict(int)  # novo

        paginator = self._s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key: str = obj["Key"]
                if not key.endswith(".parquet"):  # ignora arquivos que não são parquet
                    continue
                m = self._RE.search(key)
                if m:
                    modulo = m.group("modulo")
                    ano = m.group("ano")
                    mes = m.group("mes")

                    if mes not in tree[modulo][ano]:
                        tree[modulo][ano].append(mes)

                    pk = f"modulo={modulo}/ano={ano}/mes={mes}"
                    file_count[pk] += 1  # novo

        return PartitionMap(
            dataset=dataset_path,
            tree={k: dict(v) for k, v in tree.items()},
            file_count=dict(file_count),
        )

    def scan_all(self, datasets: dict[str, str]) -> dict[str, PartitionMap]:
        """
        Escaneia todos os datasets do registry de uma vez.

        Uso:
            from datalake.registry import DATASETS

            scanner = S3PartitionScanner()
            maps = scanner.scan_all(DATASETS)

            for nome, pm in maps.items():
                print(pm)
        """
        return {nome: self.scan(path) for nome, path in datasets.items()}

"""
Factory de I/O — escolhe entre S3 e pendrive local.

Retorna um Pipeline com todas as dependências de I/O resolvidas.
main.py nunca importa S3Reader, LocalReader, iter_partition_chunks, etc.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from src.io.data_loader import partition_prefix


@dataclass(frozen=True)
class Pipeline:
    """
    Todas as dependências de I/O do fluxo M1 + M2 em um único objeto.

    Campos:
        reader          — S3Reader | LocalReader  (M2, descoberta de módulos)
        find_partitions — (base_path) → list[str]
        process_partition — encapsula chunk_iter_fn + write_meta_fn já injetados
        aggregator      — objeto com .aggregate(base_path, config) → dict
        target_desc     — label para prints ("s3://bucket/..." | "/mnt/pendrive")
    """
    reader:             Any
    find_partitions:    Callable[[str], list[str]]
    process_partition:  Callable[..., dict]
    aggregator:         Any
    target_desc:        str
    resolve_module_key: Callable[[str], str]  # ← novo


def build_pipeline(args: argparse.Namespace) -> Pipeline:
    """
    Ponto único de decisão S3 vs local.

    Seleção (ordem de precedência):
      1. --local  /  RING_LOCAL=1   → local filesystem
      2. padrão                     → S3
    """
    use_local = (
        getattr(args, "local", False)
        or os.getenv("RING_LOCAL", "").lower() in ("1", "true")
    )

    return _local_pipeline(args) if use_local else _s3_pipeline(args)


# ── S3 ────────────────────────────────────────────────────────────────────────

def _s3_pipeline(args: argparse.Namespace) -> Pipeline:
    from src.io.data_loader import iter_partition_chunks
    from src.io.metadata_writer import write_eligibility_metadata
    from src.core.partition import find_partitions
    from src.preprocessing.module_aggregator import ModuleAggregator
    from src.io.reader.s3_reader import S3Reader

    bucket = args.bucket

    reader      = S3Reader(bucket=bucket)
    aggregator  = ModuleAggregator(bucket=bucket)

    def _find(base_path: str) -> list[str]:
        return find_partitions(base_path)

    def _process(path, config, **kwargs):
        from src.core.partition import process_partition
        return process_partition(
            path, config,
            chunk_iter_fn=iter_partition_chunks,
            write_meta_fn=write_eligibility_metadata,
            **kwargs,
        )

    return Pipeline(
        reader=reader,
        find_partitions=_find,
        process_partition=_process,
        aggregator=aggregator,
        target_desc=f"s3://{bucket}",
        resolve_module_key=partition_prefix,  # comportamento atual
    )


# ── Local ─────────────────────────────────────────────────────────────────────

def _local_pipeline(args: argparse.Namespace) -> Pipeline:
    from src.io.reader.local_data_loader import (
        LocalReader,
        LocalModuleAggregator,
        iter_local_chunks,
        write_local_eligibility,
        list_local_partition_prefixes,
    )

    root = Path(
        getattr(args, "pendrive_root", None)
        or os.getenv("RING_PENDRIVE_ROOT", "/media/henry/pd_data")
    )

    reader     = LocalReader(root=root)
    aggregator = LocalModuleAggregator(root=root)

    def _find(base_path: str) -> list[str]:
        module_dir = root / Path(base_path).name
        return [str(p) for p in list_local_partition_prefixes(module_dir)]

    def _process(path, config, **kwargs):
        from src.core.partition import process_partition
        return process_partition(
            path, config,
            chunk_iter_fn=iter_local_chunks,
            write_meta_fn=write_local_eligibility,
            **kwargs,
        )

    def _module_key(base_path: str) -> str:
        # "compras" → "compras"   (get_module_config já aceita o nome simples)
        return Path(base_path).name

    return Pipeline(
        reader=reader,
        find_partitions=_find,
        process_partition=_process,
        aggregator=aggregator,
        target_desc=str(root),
        resolve_module_key=_module_key,
    )
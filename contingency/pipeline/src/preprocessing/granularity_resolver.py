"""Granularity resolution utilities for time-based data analysis."""

from typing import Optional

def resolve_granularity(
        total_rows: int,
        partition_path: Optional[str] = None,
        min_threshold: int = 1_000
) -> str:
    """
    Identifica a granularidade da partição e valida se o volume de dados
    sustenta a análise estatística naquele nível.
    """
    # 1. Trava de Segurança: Se a partição é minúscula, a granularidade
    # estatística "útil" é o Ano (agrupamento maior), independente do path.
    if total_rows < min_threshold:
        return "year"

    # 2. Inferência por Hierarquia de Path (S3 Standard)
    if partition_path:
        p_str = str(partition_path).lower()

        # Ordem de prioridade: do mais específico para o mais genérico
        if 'dia=' in p_str or 'day=' in p_str:
            return "day"
        if 'mes=' in p_str or 'month=' in p_str:
            return "month"
        if 'trim=' in p_str or 'quarter=' in p_str:
            return "quarter"
        if 'ano=' in p_str or 'year=' in p_str:
            return "year"

    # 3. Default (Fallback)
    return "year"

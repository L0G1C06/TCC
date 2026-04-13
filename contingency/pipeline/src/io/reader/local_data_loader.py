"""Local filesystem infrastructure — drop-in replacement for S3 stack.

Mirrors the public API of:
  src/io/s3_reader.py      → LocalReader  +  helpers
  src/io/data_loader.py    → iter_local_chunks
  src/io/metadata_writer.py→ write_local_eligibility

Root: /mnt/pendrive/
Structure expected:
  /mnt/pendrive/<modulo>/[ano=YYYY/][mes=MM/]*.parquet
  /mnt/pendrive/<modulo>/[ano=YYYY/][mes=MM/]_eligibility.json
  /mnt/pendrive/<modulo>/_MODULE_ELIGIBILITY.json
"""

from __future__ import annotations

import io
import json
import logging
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# Re-export so callers that import from here stay consistent.
from src.io.reader.s3_reader import PartitionReadError                 # noqa: F401
from src.core.serializable import convert_to_serializable
from src.preprocessing.eligibility_decider import BenfordEligibilityDecider

logger = logging.getLogger(__name__)

try:
    from tqdm import tqdm
    _TQDM = True
except ImportError:
    _TQDM = False
    tqdm = lambda x, **kw: x                                    # type: ignore[assignment]

# ── Configuração ──────────────────────────────────────────────────────────────

PENDRIVE_ROOT: Path = Path("/media/henry/pd_data")


# ── Validação de arquivos ─────────────────────────────────────────────────────

def is_valid_parquet_file(path: Path) -> bool:
    """Aceita qualquer .parquet que não seja oculto ou artefato de SO."""
    name = path.name
    return (
        name.endswith(".parquet")
        and not name.startswith(".")
        and not name.startswith("~")
    )


# ── Listagem de partições ─────────────────────────────────────────────────────

def list_local_partition_prefixes(module_path: Path) -> dict[Path, int]:
    """
    Agrupa o tamanho total (bytes) por diretório de partição.

    Espelha list_partition_prefixes() do s3_reader, mas retorna
    dict[Path → total_bytes] em vez de dict[str → total_bytes].

    Considerado "partição" qualquer diretório que contenha pelo
    menos um .parquet válido.
    """
    partition_stats: dict[Path, int] = {}

    for parquet_file in module_path.rglob("*.parquet"):
        if is_valid_parquet_file(parquet_file):
            parent = parquet_file.parent
            partition_stats[parent] = (
                partition_stats.get(parent, 0) + parquet_file.stat().st_size
            )

    return partition_stats


# ── Recovery de Parquet corrompido ────────────────────────────────────────────

def try_local_recovery_read(
    path: Path,
    columns: list[str] | None = None,
) -> pa.Table | None:
    """
    Tenta recuperar um arquivo parquet corrompido — mesmas três
    estratégias do try_recovery_read() do s3_reader.
    """
    raw = path.read_bytes()

    # Estratégia 1: leitura com validação mínima
    try:
        pf = pq.ParquetFile(io.BytesIO(raw))
        return pf.read(columns=columns)
    except Exception as e:
        logger.debug("Local recovery strategy 1 failed for %s: %s", path, e)

    # Estratégia 2: row groups individuais
    try:
        pf = pq.ParquetFile(io.BytesIO(raw))
        tables: list[pa.Table] = []
        for i in range(pf.num_row_groups):
            try:
                tables.append(pf.read_row_group(i, columns=columns))
            except Exception as rg_err:
                logger.warning("Failed row group %d in %s: %s", i, path, rg_err)
        if tables:
            return pa.concat_tables(tables, promote_options="default")
    except Exception as e:
        logger.debug("Local recovery strategy 2 failed for %s: %s", path, e)

    # Estratégia 3: fallback pandas
    try:
        df = pd.read_parquet(io.BytesIO(raw), engine="pyarrow", use_nullable_dtypes=True)
        if columns:
            df = df[[c for c in columns if c in df.columns]]
        return pa.Table.from_pandas(df)
    except Exception as e:
        logger.debug("Local recovery strategy 3 failed for %s: %s", path, e)

    return None


# ── iter_local_chunks — substitui iter_partition_chunks ──────────────────────

def iter_local_chunks(
    partition_path: str | Path,
    columns: list[str],
    chunk_size: int = 100_000,
    delete_corrupted: bool = False,       # False por segurança no pendrive
    use_recovery: bool = True,
    show_progress: bool = True,
    max_recovery_attempts: int = 3,
) -> Generator[pd.DataFrame, None, None]:
    """
    Itera chunks de DataFrames lendo arquivos .parquet locais.

    API idêntica a iter_partition_chunks(), sem o parâmetro `bucket`.
    `delete_corrupted` é False por padrão — evita apagar dados do pendrive
    acidentalmente; passe True se quiser o comportamento análogo ao S3.
    """
    root = Path(partition_path)
    keys = sorted(p for p in root.rglob("*.parquet") if is_valid_parquet_file(p))

    if not keys:
        raise PartitionReadError(f"No .parquet files found at {root}")

    files_ok = files_failed = files_deleted = 0

    pbar = (
        tqdm(total=len(keys), desc="Files", unit="file", leave=False)
        if show_progress and _TQDM
        else None
    )

    try:
        for key in keys:
            if pbar:
                pbar.set_postfix_str(key.name, refresh=False)

            success = False

            # --- Tentativa 1: leitura padrão ---
            try:
                pf = pq.ParquetFile(key)
                available = set(pf.schema_arrow.names)
                cols_to_read = [c for c in columns if c in available]

                if cols_to_read:
                    for batch in pf.iter_batches(
                        batch_size=chunk_size, columns=cols_to_read
                    ):
                        yield pa.Table.from_batches([batch]).to_pandas()

                success = True
                files_ok += 1

            except Exception as e:
                logger.warning("Standard read failed for %s: %s", key, e)

                # --- Tentativas 2..N: recovery ---
                if use_recovery:
                    attempt = 1
                    while attempt <= max_recovery_attempts and not success:
                        logger.info("Recovery attempt %d/%d for %s", attempt, max_recovery_attempts, key)
                        recovered = try_local_recovery_read(key, columns)
                        if recovered is not None:
                            for batch in recovered.to_batches(max_chunksize=chunk_size):
                                yield batch.to_pandas()
                            success = True
                            files_ok += 1
                            logger.info("Recovery succeeded for %s", key)
                        else:
                            attempt += 1

                # --- Falha total ---
                if not success:
                    files_failed += 1
                    if delete_corrupted:
                        try:
                            key.unlink()
                            files_deleted += 1
                            logger.info("Deleted corrupted file: %s", key)
                        except OSError as del_err:
                            logger.error("Failed to delete %s: %s", key, del_err)

            if pbar:
                pbar.update(1)

    finally:
        if pbar:
            pbar.close()

    if files_ok == 0:
        raise PartitionReadError(
            f"All {files_failed} file(s) at {root} failed to read."
        )


# ── write_local_eligibility — substitui write_eligibility_metadata ───────────

def write_local_eligibility(
    partition_path: str | Path,
    eligibility: dict[str, Any],
    filename: str = "_eligibility.json",
) -> Path:
    """
    Persiste o relatório de elegibilidade como JSON local.

    Espelha write_eligibility_metadata(), sem bucket/boto3.
    Retorna o Path do arquivo escrito.
    """
    dest = Path(partition_path) / filename
    dest.parent.mkdir(parents=True, exist_ok=True)

    serializable = convert_to_serializable(eligibility)
    dest.write_text(
        json.dumps(serializable, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.debug("Wrote eligibility metadata to %s", dest)
    return dest


# ── LocalReader — substitui S3Reader ─────────────────────────────────────────

class LocalReader:
    """
    Leitura de metadados de elegibilidade do filesystem local.
    API pública idêntica a S3Reader — substitui-o sem alterar M2Engine
    nem qualquer outro consumidor.
    """

    def __init__(self, root: str | Path = PENDRIVE_ROOT):
        self.root = Path(root)

    # ── Leitura genérica ──────────────────────────────────────────────────────

    def load_json(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    # ── Descoberta de módulos ─────────────────────────────────────────────────

    def list_eligible_modules(self, root_prefix: str | Path | None = None) -> list[str]:
        """
        Varre o root em busca de _MODULE_ELIGIBILITY.json e retorna os
        paths (como strings) dos módulos com ao menos uma coluna elegível.

        Espelha S3Reader.list_eligible_modules().
        `root_prefix` é ignorado se fornecido — existe apenas para
        compatibilidade de assinatura com o S3Reader.
        """
        eligible: list[str] = []

        for meta in self.root.rglob("_MODULE_ELIGIBILITY.json"):
            if self._is_module_eligible(meta):
                eligible.append(str(meta.parent))

        return eligible

    def _is_module_eligible(self, report_path: Path) -> bool:
        try:
            return self.load_json(report_path).get("eligible", False)
        except Exception as e:
            logger.error("Erro ao validar elegibilidade em %s: %s", report_path, e)
            return False

    # ── Descoberta de partições ───────────────────────────────────────────────

    def list_eligible_partitions(self, module_path: str | Path) -> list[str]:
        """
        Lista as partições do módulo com _eligibility.json elegível.
        Exclui o _MODULE_ELIGIBILITY.json — só partições individuais.
        Espelha S3Reader.list_eligible_partitions().
        """
        module_dir = Path(module_path)
        eligible: list[str] = []

        for meta in module_dir.rglob("_eligibility.json"):
            if meta.name == "_MODULE_ELIGIBILITY.json":
                continue
            if self._is_partition_eligible(meta):
                eligible.append(str(meta.parent))

        return sorted(eligible)

    def _is_partition_eligible(self, report_path: Path) -> bool:
        try:
            return self.load_json(report_path).get("eligible", False)
        except Exception as e:
            logger.error("Erro ao validar elegibilidade em %s: %s", report_path, e)
            return False

    # ── Input para o M2Engine — nível módulo ──────────────────────────────────

    def get_analysis_input(self, module_path: str | Path) -> dict[str, dict]:
        """
        Lê o _MODULE_ELIGIBILITY.json e extrai contadores brutos.
        Espelha S3Reader.get_analysis_input().
        """
        key = Path(module_path) / "_MODULE_ELIGIBILITY.json"
        report = self.load_json(key)
        return self._extract_inputs(report, level="módulo")

    # ── Input para o M2Engine — nível partição ────────────────────────────────

    def get_partition_input(self, partition_path: str | Path) -> dict[str, dict]:
        """
        Lê o _eligibility.json de uma partição individual.
        Espelha S3Reader.get_partition_input().
        """
        key = Path(partition_path) / "_eligibility.json"
        report = self.load_json(key)
        return self._extract_inputs(report, level="partição")

    # ── Extração comum ────────────────────────────────────────────────────────

    def _extract_inputs(self, report: dict, level: str) -> dict[str, dict]:
        """Idêntico ao _extract_inputs do S3Reader — reutiliza _parse_column_inputs."""
        from src.io.reader.s3_reader import parse_column_inputs   # função pura, sem boto3

        result: dict[str, dict] = {}
        for col, data in report.get("columns", {}).items():
            inputs = parse_column_inputs(data, col)
            if inputs is not None:
                result[col] = inputs
            else:
                logger.debug("[%s] Coluna '%s' inelegível — ignorada.", level, col)
        return result


# ── Helpers de conveniência ───────────────────────────────────────────────────

def module_path(module_name: str, root: Path = PENDRIVE_ROOT) -> Path:
    """
    Resolve o Path de um módulo pelo nome simples.

    Exemplos:
        module_path("compras")    → Path("/mnt/pendrive/compras")
        module_path("licitacoes") → Path("/mnt/pendrive/licitacoes")
    """
    return root / module_name


def list_modules(root: Path = PENDRIVE_ROOT) -> list[str]:
    """Lista todos os subdiretórios de primeiro nível no pendrive."""
    return sorted(d.name for d in root.iterdir() if d.is_dir())


class LocalModuleAggregator:
    """
    Espelha a interface de ModuleAggregator para o filesystem local.
    Lê os _eligibility.json das partições, agrega contadores e
    persiste _MODULE_ELIGIBILITY.json — tudo em disco.
    """

    def __init__(self, root: str | Path = PENDRIVE_ROOT):
        self.root = Path(root)

    def aggregate(self, base_path: str, config) -> dict[str, Any]:
        from src.preprocessing.module_aggregator import _ColAccumulator, _format_column_report

        module_dir = self.root / Path(base_path).name
        meta_files = sorted(module_dir.rglob("_eligibility.json"))
        meta_files = [f for f in meta_files if f.name != "_MODULE_ELIGIBILITY.json"]

        # ── espelha o S3: inicializa acumuladores pelas colunas do config ────────
        accumulators: dict[str, _ColAccumulator] = {
            col: _ColAccumulator() for col in config.numeric_columns
        }
        partitions_analyzed = 0
        partitions_skipped = 0

        for meta_path in meta_files:
            try:
                report = json.loads(meta_path.read_text(encoding="utf-8"))
                col_reports = report.get("columns", {})
                for col in config.numeric_columns:
                    col_report = col_reports.get(col)
                    if col_report and col_report.get("found", False):
                        accumulators[col].ingest(col_report)
                partitions_analyzed += 1
            except Exception as e:
                logger.warning("Skipping %s: %s", meta_path, e)
                partitions_skipped += 1

        decider = BenfordEligibilityDecider()
        columns_report: dict[str, Any] = {}
        for col, acc in accumulators.items():
            if acc._partition_count == 0:
                columns_report[col] = {
                    "found": False,
                    "eligible": False,
                    "reasons": ["Column not found in any partition"],
                }
                continue

            # ── assinatura correta: (col, skip_truncation_check) ─────────────────
            metrics = acc.to_metrics(col, config.skip_truncation_check)
            result = decider.decide(metrics)
            columns_report[col] = _format_column_report(metrics, result, acc)

        eligible_cols = [c for c, r in columns_report.items() if r.get("eligible")]
        n = len(eligible_cols)
        decision = (
            "eligible" if n == len(config.numeric_columns)
            else "eligible_with_reservation" if n > 0
            else "ineligible"
        )

        module_report: dict[str, Any] = {
            "eligible": n > 0,
            "decision": decision,
            "columns": columns_report,
            "module_path": str(module_dir),
            "partitions_analyzed": partitions_analyzed,
            "partitions_skipped": partitions_skipped,
            "summary": {
                "total_columns": len(config.numeric_columns),
                "eligible_columns": n,
            },
        }

        write_local_eligibility(module_dir, module_report, filename="_MODULE_ELIGIBILITY.json")
        logger.info("Module report → %s", module_dir / "_MODULE_ELIGIBILITY.json")
        return module_report
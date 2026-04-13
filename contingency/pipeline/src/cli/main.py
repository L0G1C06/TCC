"""
Benford's Law Eligibility Pipeline — RUMOLOG
Lê diretamente do S3. Path padrão: data/portal_da_transparencia/parquet/
"""
import argparse
import logging
import os
from dotenv import load_dotenv

from src.analysis.engine.m2_engine import M2Engine
from src.analysis.engine.scorer import M4Scorer, ColumnScore
from src.io.reader.reader_factory import build_pipeline, Pipeline

load_dotenv()

from src.core.module_config import get_module_config

# ── M2 ────────────────────────────────────────────────────────────────────────

logger = logging.getLogger(__name__)

DEFAULT_BASE = "data/portal_da_transparencia/parquet/modulo=compras"


# ── Modo M1: elegibilidade por partição ───────────────────────────────────────

def _run_partitions(base_path: str, args: argparse.Namespace, pipeline: Pipeline) -> None:
    print(f"Scanning: {pipeline.target_desc}/{base_path}")

    partitions = pipeline.find_partitions(base_path)
    print(f"Found {len(partitions)} partitions")

    if args.year:
        partitions = [p for p in partitions if f"ano={args.year}" in p]
        print(f"Filtered to {len(partitions)} partitions for year {args.year}")

    if args.month:
        partitions = [p for p in partitions if f"mes={args.month}" in p]
        print(f"Filtered to {len(partitions)} partitions for month {args.month}")

    config = get_module_config(pipeline.resolve_module_key(base_path))
    results = []

    for p in partitions:
        try:
            eligibility = pipeline.process_partition(p, config, chunk_size=args.chunk_size)
            results.append({
                "path": p,
                "decision": eligibility["decision"],
                "eligible": eligibility["eligible"],
            })
        except Exception as e:
            print(f"  ERROR {p}: {e}")
            results.append({"path": p, "decision": "error", "eligible": False, "error": str(e)})

    print(f"\n{'-' * 60}")
    print("GENERATING MODULE-LEVEL REPORT")
    print(f"{'-' * 60}")

    try:
        module_report = pipeline.aggregator.aggregate(base_path, config)
        print(f"Module Decision: {module_report['decision'].upper()}")
        print(
            f"Eligible Columns: "
            f"{module_report['summary']['eligible_columns']}/"
            f"{module_report['summary']['total_columns']}"
        )
    except Exception as e:
        print(f"Error aggregating module: {e}")

    _print_m1_summary(results)


def _print_m1_summary(results: list[dict]) -> None:
    print(f"\n{'=' * 60}")
    print("PROCESSING SUMMARY")
    print(f"{'=' * 60}")
    print(f"Total:          {len(results)}")
    print(f"  Eligible:     {sum(1 for r in results if r['eligible'])}")
    print(f"  Ineligible:   {sum(1 for r in results if r['decision'] == 'ineligible')}")
    print(f"  Reserva:      {sum(1 for r in results if r['decision'] == 'eligible_with_reservation')}")
    print(f"  Erros:        {sum(1 for r in results if r['decision'] == 'error')}")

    errors = [r for r in results if r["decision"] == "error"]
    if errors:
        print("\nErros:")
        for r in errors:
            print(f"  {r['path']}: {r.get('error', '?')}")


# ── Modo M2: análise estatística completa ─────────────────────────────────────

def _print_global_scores(
        all_scores: dict[str, dict[str, "ColumnScore"]],
) -> None:
    print(f"\n{'─' * 60}")
    print("  RANKING GLOBAL (normalização cross-módulo)")
    print(f"{'─' * 60}")

    # Agrega por escopo: score do escopo = max score entre colunas
    scope_summary = {
        scope: max(cs.score for cs in cols.values())
        for scope, cols in all_scores.items()
        if cols
    }
    for scope, score in sorted(scope_summary.items(), key=lambda x: -x[1]):
        bar = _score_bar(score)
        print(f"  {scope:<40} {bar}  {score:.4f}")


def _print_score_table(
        scores: dict[str, "ColumnScore"],
        verbose: bool,
        prefix: str = " ",
) -> None:
    ranked = sorted(scores.values(), key=lambda s: s.score, reverse=True)
    for cs in ranked:
        flag_label = cs.flag.value.upper().ljust(8)
        bar = _score_bar(cs.score)
        print(f"{prefix} {cs.column:<32} [{flag_label}]  {bar}  {cs.score:.4f}")

        if verbose or cs.is_suspicious:
            for component, w in cs.weighted.items():
                raw = cs.raw_values.get(component, 0.0)
                print(f"  {'':>{len(prefix)}}   {component:<15} raw={raw:.6f}  contrib={w:.4f}")


def _print_temporal_comparison(
        partition_scores: dict[str, dict[str, "ColumnScore"]],
        module_scores: dict[str, "ColumnScore"],
) -> None:
    """
    Detecta partições onde o score individual é significativamente
    mais alto que o score agregado do módulo — sinal de anomalia temporal.

    Threshold: score_partição > score_módulo + 0.20
    Indica que a fraude está concentrada naquele período.
    """
    _DELTA_THRESHOLD = 0.20

    anomalias: list[tuple[str, str, float, float]] = []  # (partição, coluna, score_part, score_mod)

    for label, scores in partition_scores.items():
        for col, cs in scores.items():
            mod_score = module_scores.get(col)
            if mod_score is None:
                continue
            delta = cs.score - mod_score.score
            if delta >= _DELTA_THRESHOLD:
                anomalias.append((label, col, cs.score, mod_score.score))

    if not anomalias:
        print(f"\n{'─' * 60}")
        print("  COMPARATIVO TEMPORAL — sem anomalias concentradas")
        print(f"{'─' * 60}")
        return

    print(f"\n{'─' * 60}")
    print(f"  COMPARATIVO TEMPORAL — {len(anomalias)} anomalia(s) concentrada(s)")
    print(f"{'─' * 60}")
    print(f"  {'Partição':<20} {'Coluna':<25} {'Score part.':<14} {'Score módulo':<14} {'Delta'}")
    print(f"  {'─' * 18} {'─' * 23} {'─' * 12} {'─' * 12} {'─' * 8}")

    # Ordena por delta decrescente — mais suspeito primeiro
    for label, col, sp, sm in sorted(anomalias, key=lambda x: x[2] - x[3], reverse=True):
        delta = sp - sm
        print(f"  {label:<20} {col:<25} {sp:<14.4f} {sm:<14.4f} +{delta:.4f}  ⚠")


def _run_analysis(base_path: str, args: argparse.Namespace, pipeline: Pipeline) -> None:
    """
    Executa M2 + M4 em dois níveis:
      1. Módulo agregado   — detecta anomalia sistêmica
      2. Cada partição elegível — detecta anomalia temporal

    Pré-condição: M1 já executado (JSONs presentes no S3).
    """


    reader = pipeline.reader
    engine = M2Engine(max_workers=args.max_workers)
    scorer = M4Scorer()

    is_root = not any(seg in base_path for seg in ("modulo=", "ano=", "mes="))

    if is_root:
        print(f"Scanning all eligible modules under: s3://{args.bucket}/{base_path}")
        module_paths = reader.list_eligible_modules(base_path)
        if not module_paths:
            print(
                "Nenhum módulo elegível encontrado.\n"
                "Execute o pipeline sem --analyze para gerar os _MODULE_ELIGIBILITY.json."
            )
            return
        print(f"Found {len(module_paths)} eligible module(s)\n")
    else:
        module_paths = [base_path.rstrip("/")]

    for module_path in module_paths:
        print(f"\n{'═' * 60}")
        print(f"MÓDULO: {module_path.split('/')[-1]}")
        print(f"{'═' * 60}")
        _analyze_module(module_path, reader, engine, scorer, args)

    from ..analysis.engine.scorer import GlobalScorer
    from ..analysis.engine.sensitivity import LHSSensitivityAnalyzer

    # Reaplica o engine com GlobalScorer para normalização cross-módulo
    if len(module_paths) > 1 or args.sensitivity:
        print(f"\n{'═' * 60}")
        print("NORMALIZAÇÃO GLOBAL + ANÁLISE DE SENSIBILIDADE LHS")
        print(f"{'═' * 60}")

        global_scorer = GlobalScorer()

        for module_path in module_paths:
            try:
                inputs = reader.get_analysis_input(module_path)
                analyses = engine.run(inputs)
                global_scorer.register(module_path.split("/")[-1], analyses)
            except Exception as e:
                logger.warning("GlobalScorer: pulando %s — %s", module_path, e)

        if len(global_scorer.raw_values) >= 2:
            all_global_scores = global_scorer.score_all()
            _print_global_scores(all_global_scores)

            if args.sensitivity:
                analyzer = LHSSensitivityAnalyzer(
                    n_samples=args.lhs_samples,
                    k=3,
                    seed=42,
                )
                result = analyzer.analyze(global_scorer.raw_values)
                print(result.summary())
        else:
            print("  Menos de 2 módulos disponíveis — LHS requer ao menos 2 escopos.")


def _analyze_module(
        module_path: str,
        reader: "S3Reader",
        engine: "M2Engine",
        scorer: "M4Scorer",
        args: argparse.Namespace,
) -> None:
    # ── Nível 1: módulo agregado ──────────────────────────────────────────
    print(f"\n{'─' * 60}")
    print("  NÍVEL MÓDULO (agregado)")
    print(f"{'─' * 60}")

    module_scores: dict[str, "ColumnScore"] = {}
    try:
        inputs = reader.get_analysis_input(module_path)
        analyses = engine.run(inputs)
        module_scores = scorer.score_module(analyses)
        _print_score_table(module_scores, args.verbose)
    except Exception as e:
        print(f"  ERRO no nível módulo: {e}")
        logger.exception("Falha no M2 módulo %s", module_path)

    # ── Nível 2: partições individuais elegíveis ──────────────────────────
    print(f"\n{'─' * 60}")
    print("  NÍVEL PARTIÇÃO (individual)")
    print(f"{'─' * 60}")

    try:
        partition_paths = reader.list_eligible_partitions(module_path)
    except Exception as e:
        print(f"  ERRO ao listar partições: {e}")
        return

    if not partition_paths:
        print("  Nenhuma partição elegível individualmente.")
        return

    print(f"  Partições elegíveis: {len(partition_paths)}\n")

    partition_scores: dict[str, dict[str, "ColumnScore"]] = {}

    for part_path in partition_paths:
        label = _partition_label(part_path)
        try:
            inputs = reader.get_partition_input(part_path)
            analyses = engine.run(inputs)
            scores = scorer.score_module(analyses)
            partition_scores[label] = scores
            _print_score_table(scores, args.verbose, prefix=f"  [{label}]")
        except Exception as e:
            print(f"  [{label}] ERRO: {e}")
            logger.exception("Falha no M2 partição %s", part_path)

    # ── Comparativo: partições vs módulo ──────────────────────────────────
    if partition_scores and module_scores:
        _print_temporal_comparison(partition_scores, module_scores)


def _partition_label(partition_path: str) -> str:
    """
    Extrai um label legível do path da partição.
    'data/.../modulo=compras/ano=2023/mes=06' → '2023/mes=06'
    """
    parts = partition_path.rstrip("/").split("/")
    ano = next((p for p in parts if p.startswith("ano=")), "")
    mes = next((p for p in parts if p.startswith("mes=")), "")
    if ano and mes:
        return f"{ano.split('=')[1]}/{mes}"
    return parts[-1]


def _score_bar(score: float, width: int = 20) -> str:
    filled = round(score * width)
    return f"[{'█' * filled}{'░' * (width - filled)}]"


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s %(name)s — %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Benford's Law Pipeline — Portal da Transparência",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
exemplos — S3 (padrão):
  python -m src.cli.main data/.../modulo=compras                        # M1 — elegibilidade
  python -m src.cli.main data/.../modulo=compras --year 2023 --month 06 # M1 — filtro temporal
  python -m src.cli.main data/.../modulo=compras --analyze              # M2 — score por módulo
  python -m src.cli.main data/.../parquet/ --analyze --sensitivity      # M2 — cross-módulo + LHS
  python -m src.cli.main data/.../modulo=compras --analyze --verbose    # M2 — detalhe por coluna

exemplos — pendrive local (--local):
  python -m src.cli.main compras --local                                # M1
  python -m src.cli.main compras --local --year 2023 --month 06        # M1 — filtro temporal
  python -m src.cli.main compras --local --analyze                      # M2
  python -m src.cli.main . --local --analyze --sensitivity              # M2 — cross-módulo + LHS
  python -m src.cli.main compras --local --pendrive-root /media/henry/dados

exemplos — teste modulos de benford, MAD, JS e etc.
    uv run pytest src/analysis/tests/ -v
    
via env var:
  RING_LOCAL=1 python main.py compras --analyze
  RING_LOCAL=1 RING_PENDRIVE_ROOT=/media/henry/dados python main.py compras
        """,
    )

    parser.add_argument(
        "base_path",
        nargs="?",
        default=DEFAULT_BASE,
        help="Prefixo S3 ou nome do módulo local (ex: compras)",
    )

    # ── Filtros ───────────────────────────────────────────────────────────────
    parser.add_argument("--year",  type=str, help="Filtrar por ano  (ex: 2023)")
    parser.add_argument("--month", type=str, help="Filtrar por mês  (ex: 01)")

    # ── Modos de execução ─────────────────────────────────────────────────────
    parser.add_argument("--analyze",     action="store_true", help="Executa M2 + Score M4")
    parser.add_argument("--sensitivity", action="store_true",
                        help="LHS de sensibilidade dos pesos (requer ≥ 2 módulos)")
    parser.add_argument("--verbose",     action="store_true",
                        help="Detalha componentes por coluna no output")

    # ── Backend de I/O ────────────────────────────────────────────────────────
    parser.add_argument("--local", action="store_true",
                        help="Lê do pendrive local em vez do S3")
    parser.add_argument("--pendrive-root", type=str, default=None, metavar="PATH",
                        help="Raiz do pendrive (default: /mnt/pendrive ou RING_PENDRIVE_ROOT)")
    parser.add_argument("--bucket", type=str,
                        default=os.getenv("RUMOLOG_S3_BUCKET", "rumolog-s3"),
                        help="S3 bucket (default: $RUMOLOG_S3_BUCKET)")

    # ── Tuning ────────────────────────────────────────────────────────────────
    parser.add_argument("--lhs-samples",      type=int, default=500,
                        help="Amostras LHS (default: 500; TCC: 1000+)")
    parser.add_argument("--chunk-size",       type=int, default=100_000)
    parser.add_argument("--max-workers",      type=int, default=6)
    parser.add_argument("--delete-corrupted", action="store_true")
    parser.add_argument("--no-recovery",      action="store_true")

    args     = parser.parse_args()
    os.environ["RUMOLOG_S3_BUCKET"] = args.bucket
    pipeline = build_pipeline(args)

    if args.analyze:
        _run_analysis(args.base_path, args, pipeline)
    else:
        _run_partitions(args.base_path, args, pipeline)


if __name__ == "__main__":
    main()

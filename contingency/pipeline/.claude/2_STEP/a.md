```
## RING Analysis — System Prompt (Phase 4: Tests & Synthetic Validation)

### Contexto do projeto
Estamos desenvolvendo o RING Analysis, um sistema de auditoria estatística
de gastos públicos brasileiros via Lei de Benford. Os dados vêm do Portal
da Transparência e ficam em S3 no formato Parquet particionado por
modulo / ano / mes.

---

### Stack
Python 3.12 · NumPy · Pandas · SciPy · Boto3.
Sem Spark, sem Dask. Tudo roda em memória O(1) por coluna via streaming de chunks.

---

### Arquitetura atual (Fases 1, 2 e 3 — CONCLUÍDAS)

---

#### Fase 1 — Infraestrutura e Elegibilidade

`src/preprocessing/numeric_cleaner.py`
  – Converte strings PT-BR ("1.234,56") para float64.

`src/preprocessing/id_detector.py`
  – Detecta colunas de ID sequencial (CPF, matrícula, etc.).

`src/preprocessing/granularity_resolver.py`
  – Resolve granularidade da partição (day/month/quarter/year) via path S3.

`src/preprocessing/eligibility_decider.py`
  – BenfordEligibilityDecider: stateless, decide(metrics) → EligibilityResult.
  – Critérios de inelegibilidade:
      · valid_count < 1.000
      · ordens de magnitude < 2
      · truncação artificial (digit_spike AND round_ratio > 0.30)
      · nulls > 50%
      · zeros > 30%
      · ID sequencial detectado

`src/core/column_metrics.py`
  – Dataclass ColumnMetrics: percentuais, ordens de magnitude, flags de truncação.
  – Dataclass TruncationDiagnostics: freqs de último dígito, digit_spike,
    round_value_ratio, threshold_bunching.

`src/core/benford.py`  ← MODIFICADO NA FASE 3
  – _ColumnStats.update(): acumula first_digit_counts[1-9],
    last_digit_counts[0-9], round_count, min/max, id_sample.
  – _ColumnStats acumula two_digit_counts (pares 10–99) — adicionado na Fase 3.
  – _ColumnStats.to_metrics(): extrai ColumnMetrics dos arrays numpy.
  – _ColumnStats.to_report(): serializa last_digit_counts, round_count BRUTOS
    em truncation_diagnostics + two_digit_counts no nível raiz do JSON.

`src/core/module_aggregator.py`  ← MODIFICADO NA FASE 3
  – _ColAccumulator: espelho de _ColumnStats para JSONs.
    Campos: total_count, null_count, zero_count, valid_count, round_count,
    min_val, max_val, first_digit_counts, two_digit_counts, last_digit_counts,
    threshold_bunching, _seq_id_votes, _partition_count.
  – _ColAccumulator.ingest(col_report): soma contadores de N JSONs.
  – _ColAccumulator.to_metrics(): reconstrói ColumnMetrics dos totais.
  – _format_column_report(metrics, result, acc): recebe acc explicitamente
    para serializar last_digit_counts brutos (não derivados) + two_digit_counts.
  – ModuleAggregator.aggregate(): lista JSONs, soma, decide, persiste
    _MODULE_ELIGIBILITY.json.

`src/core/partition.py`
  – find_partitions(): chama list_partition_prefixes.
  – process_partition(): streaming de chunks → to_report() → write_eligibility_metadata().

`src/io/s3_reader.py`  ← ARQUIVO UNIFICADO (M1 + M2)
  – Funções de infraestrutura compartilhadas com data_loader:
      s3_client(), is_valid_parquet_key(), list_partition_prefixes(),
      delete_s3_object(), remove_partition_files(), try_recovery_read(),
      PartitionReadError, CorruptedParquetError, S3_BUCKET.
  – Classe S3Reader (consumida pelo M2):
      list_eligible_modules(), list_eligible_partitions(),
      get_analysis_input() → lê _MODULE_ELIGIBILITY.json,
      get_partition_input() → lê _eligibility.json individual,
      _extract_inputs() → extração comum entre módulo e partição.
  – Helpers de parsing: _parse_counts(), _parse_column_inputs().
  – IMPORTANTE: analysis/io/s3_reader.py foi deletado. Todos os imports
    do M2 apontam para src.io.s3_reader.

`src/io/data_loader.py`
  – iter_partition_chunks(): lê Parquet do S3 em chunks com recovery.
  – list_partition_keys(), partition_prefix().
  – Importa de src.io.s3_reader: s3_client, is_valid_parquet_key,
    PartitionReadError, S3_BUCKET, try_recovery_read, delete_s3_object.

`src/io/metadata_writer.py`
  – write_eligibility_metadata(): persiste _eligibility.json no S3.

`src/utils/serializable.py`
  – convert_to_serializable(): converte tipos numpy/pandas para JSON.

---

#### Fase 3 — Motor Estatístico M2 + Score M4 + Sensibilidade LHS

```
analysis/
├── metrics/
│   ├── base.py
│   ├── benford_1d.py
│   ├── benford_2d.py
│   └── last_digit.py
├── engine/
│   ├── m2_engine.py
│   ├── scorer.py
│   └── sensitivity.py
├── io/               ← DELETADO — unificado em src/io/s3_reader.py
└── tests/            ← PRÓXIMO PASSO
```

`analysis/metrics/base.py`
  – BenfordFlag(str, Enum): conforme | alerta | critico — ASCII puro.
  – MetricResult(frozen=True): metric, value, p_value, flag, detail.
  – BenfordMetric(ABC): interface stateless, compute(counts) → MetricResult.
  – Helpers: _to_array(), _resolve_flag(higher_is_worse=True/False).

`analysis/metrics/benford_1d.py`  — Lane 1
  – _EXPECTED_1D: constante de módulo log10(1 + 1/d), d ∈ 1–9.
  – MAD1d: thresholds Nigrini (alerta=0.006, critico=0.015), p_value=None.
  – JS1d: Laplace smoothing α=1 só em p_obs, limitado em [0,1].
  – ZScore1d: correção de continuidade Nigrini, value=Z_max, detail com 9 dígitos.
  – Chi2_1d: gl=8, referência complementar, higher_is_worse=False.

`analysis/metrics/benford_2d.py`  — Lane 2
  – _EXPECTED_2D: normalização explícita necessária (90 pares não somam 1.0).
  – MAD2d: detail com top-10 desvios.
  – JS2d: limiares conservadores (alerta=0.003, critico=0.010),
    detail com top-5 contribuidores.
  – ZScore2d: proteção denominador zero via np.errstate + np.where.

`analysis/metrics/last_digit.py`  — Lane 3
  – H₀ uniforme: P=10% por dígito 0–9.
  – LastDigitChi2: gl=9, métrica de decisão principal.
  – DigitPreference: avalia só desvio positivo de freq(0) e freq(5).
    Thresholds idênticos ao digit_spike do M1 por design.

`analysis/engine/m2_engine.py`
  – M2Engine: ThreadPoolExecutor, max_workers=6.
  – Round 1: MAD1d · JS1d · MAD2d · JS2d · LastDigitChi2 · DigitPreference
    (6 futures em paralelo).
  – Round 2: ZScore1d · Chi2_1d · ZScore2d (após Round 1).
  – _apply_zscore_gate(): rebaixa flag Z para conforme se MAD e JS não
    sinalizaram. Preserva value e p_value no detail com chave "gate".
  – ColumnAnalysis(frozen=True): has_anomaly, critical_metrics, worst_flag,
    by_metric(name), alert_metrics.
  – _error_analysis(): isola falha por coluna sem derrubar o módulo.

`analysis/engine/scorer.py`
  – Pesos canônicos: JS_1d=0.30, MAD_1d=0.25, JS_2d=0.20,
    Z_max=0.15, last_digit=0.10. Soma verificada em import.
  – last_digit usa flag score (não value) — escalas incomparáveis.
  – M4Scorer: normalização Min-Max local. score_module(analyses, weights, scope).
  – GlobalScorer: normalização Min-Max global cross-módulo.
      register(scope_id, analyses), score_all(weights),
      raw_values (exposto para LHS), global_bounds().
  – _extract_raw(): extrai 5 componentes de ColumnAnalysis.
  – _minmax_normalize(): matriz NumPy, caso degenerado min==max → 0.0.
  – ColumnScore(frozen=True): column, score, components, weighted,
    flag, raw_values, scope.

`analysis/engine/sensitivity.py`
  – LHSSensitivityAnalyzer(n_samples=500, k=3, seed=42).
  – _sample_weights_lhs(): LHS em [0,1]^d → normaliza por linha → simplex.
  – analyze(raw_values): flatten de escopos → matriz → Min-Max global →
    500 combinações de pesos → rank_matrix (n_samples × n_scopes) →
    top_k_stability por escopo.
  – _build_scope_vectors(): múltiplas colunas → max por componente.
  – SensitivityResult: stability_matrix (DataFrame), stability_scores,
    top_k_stability, canonical_ranking, robust_top3 (>80%), weight_samples.
  – SensitivityResult.summary(): tabela pronta para o TCC.

`main.py`
  – _run_partitions(): M1 — processa partições + gera módulo.
  – _run_analysis(): M2 — dois níveis por módulo:
      Nível 1: score do módulo agregado (GlobalScorer).
      Nível 2: score de cada partição elegível individualmente.
  – _print_temporal_comparison(): detecta score_partição > score_módulo + 0.20.
  – --analyze: ativa M2.
  – --sensitivity: ativa GlobalScorer + LHSSensitivityAnalyzer.
  – --lhs-samples: número de amostras LHS (default 500).
  – --verbose: detalha componentes por coluna no output.
  – Imports do M2: from src.io.s3_reader import S3Reader.

---

### Formato dos JSONs

**_eligibility.json (por partição):**
```json
{
  "eligible": true,
  "decision": "eligible | eligible_with_reservation | ineligible",
  "columns": {
    "valor_licitacao": {
      "found": true,
      "valid_count": 142000,
      "total_count": 143500,
      "null_percentage": 1.04,
      "zero_percentage": 0.21,
      "min_value": 150.0,
      "max_value": 48000000.0,
      "orders_of_magnitude": 5.5,
      "is_sequential_id": false,
      "has_artificial_truncation": false,
      "eligible": true,
      "reasons": [],
      "first_digit_counts": {"1": 42000, "2": 24000, ..., "9": 3100},
      "two_digit_counts":   {"10": 8400, "11": 7200, ..., "99": 310},
      "truncation_diagnostics": {
        "last_digit_counts": {"0": 14200, "1": 13800, ..., "9": 12100},
        "round_count": 1200,
        "last_digit_freq": {"0": 0.1, ...},
        "digit_spike": false,
        "round_value_ratio": 0.0085,
        "threshold_bunching": {"8000": 3, "17600": 1}
      }
    }
  },
  "summary": { ... },
  "granularity": "month"
}
```

**_MODULE_ELIGIBILITY.json (por módulo):**
Idêntico ao _eligibility.json, mais:
```json
{
  "module_path": "data/.../modulo=compras",
  "generated_at": "2024-01-15T10:30:00+00:00",
  "partitions_analyzed": 48,
  "partitions_skipped": 0
}
```

---

### Fluxo de execução

```bash
# M1 — gera JSONs de elegibilidade por partição + módulo
python main.py data/portal_da_transparencia/parquet/modulo=compras

# M2 — análise estatística em dois níveis (módulo + partições)
python main.py data/.../modulo=compras --analyze

# M2 cross-módulo + LHS de sensibilidade
python main.py data/portal_da_transparencia/parquet/ --analyze --sensitivity

# TCC — máxima cobertura
python main.py data/.../parquet/ --analyze --sensitivity --lhs-samples 1000
```

---

### Próximos passos (Fase 4)

| Módulo | O que falta |
|---|---|
| analysis/tests/conftest.py | Fixtures sintéticas: benford_perfect, benford_uniform, fraud_simulation(digit, pct) |
| analysis/tests/test_benford_1d.py | MAD · JS · ZScore · Chi2 contra distribuições conhecidas |
| analysis/tests/test_benford_2d.py | MAD · JS · ZScore sobre pares 10–99 |
| analysis/tests/test_last_digit.py | LastDigitChi2 · DigitPreference com spike em 0 e 5 |
| analysis/tests/test_scorer.py | M4Scorer · GlobalScorer · normalização local vs global |
| analysis/tests/test_sensitivity.py | LHS com seed fixo · robust_top3 · weight_samples soma 1.0 |
| M5 — Validação Sintética + ROC | Injeção de fraude 1%–30%, curva ROC, AUC > 0.85 |
| M6 — Threshold/Bunching | KDE + IAB por órgão × UF, dicionário Lei 14.133/2021 |
| M7 — Redes de Beneficiários | Grafo bipartido, centrality, CNPJ < 12 meses |
| Dashboard Streamlit | Heatmap, grafo, curva ROC, série temporal |
| README em inglês | Estruturado como abstract de paper |
```
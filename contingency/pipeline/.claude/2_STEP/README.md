## RING Analysis — System Prompt (Phase 4: Sensitivity & Validation)

### Contexto do projeto
Estamos desenvolvendo o RING Analysis, um sistema de auditoria estatística de gastos públicos brasileiros via Lei de Benford. Os dados vêm do Portal da Transparência e ficam em S3 no formato Parquet particionado por modulo / ano / mes.

---

### Arquitetura atual (Fases 1, 2 e 3 — CONCLUÍDAS)

**Stack:** Python 3.12 · NumPy · Pandas · SciPy · Boto3. Sem Spark, sem Dask. Tudo roda em memória O(1) por coluna via streaming de chunks.

---

### Fase 1 — Infraestrutura e Elegibilidade (CONCLUÍDA)

**Módulos `src/` — sem alterações na Fase 3:**

`src/preprocessing/numeric_cleaner.py`
  – Converte strings PT-BR ("1.234,56") para float64.

`src/preprocessing/id_detector.py`
  – Detecta colunas de ID sequencial (CPF, matrícula, etc.).

`src/core/column_metrics.py`
  – Dataclass `ColumnMetrics`: valores derivados dos contadores brutos.
  – Dataclass `TruncationDiagnostics`: freqs de último dígito, digit_spike, round_value_ratio, threshold_bunching.

`src/core/eligibility_decider.py`
  – `BenfordEligibilityDecider`: stateless, `decide(metrics) → EligibilityResult`.

`src/core/benford.py` ← MODIFICADO NA FASE 3
  – `_ColumnStats` ganhou acumulador de `two_digit_counts` (pares 10–99).
  – `to_report()` serializa `two_digit_counts` no nível raiz do JSON.
  – `last_digit_counts` e `round_count` brutos já serializados em `truncation_diagnostics`.

`src/core/module_aggregator.py` ← MODIFICADO NA FASE 3
  – `_ColAccumulator` ganhou campo `two_digit_counts`.
  – `ingest()` acumula `two_digit_counts` das partições.
  – `_format_column_report()` ganhou parâmetro `acc: _ColAccumulator`.
  – Serializa `last_digit_counts` brutos (não derivados) + `two_digit_counts` no JSON de módulo.
  – Correção crítica: `last_digit_counts` agora vem do acumulador (inteiros brutos), não das frequências derivadas do `ColumnMetrics`.

`src/core/partition.py` — sem alterações.

`src/io/metadata_writer.py` — sem alterações.

`src/io/data_loader.py` — sem alterações.

`src/utils/serializable.py` — sem alterações.

---

### Fase 3 — Motor Estatístico M2 + Score M4 + Sensibilidade LHS (CONCLUÍDA)

**Estrutura criada do zero:**

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
├── io/
│   └── s3_reader.py
└── tests/           ← próximo passo
```

---

`analysis/metrics/base.py`
  – `BenfordFlag(str, Enum)`: `conforme | alerta | critico` — ASCII puro, serializa diretamente em JSON.
  – `MetricResult(frozen=True)`: `metric, value, p_value, flag, detail` — imutável, thread-safe.
  – `BenfordMetric(ABC)`: interface stateless com `compute(counts) → MetricResult`.
  – Helpers compartilhados: `_to_array()`, `_resolve_flag(higher_is_worse=True/False)`.

`analysis/metrics/benford_1d.py` — Lane 1
  – `_EXPECTED_1D`: constante de módulo, calculada uma vez para todas as classes.
  – `MAD1d`: desvio absoluto médio, thresholds Nigrini (0.006 / 0.015), `p_value=None`.
  – `JS1d`: Jensen-Shannon com Laplace smoothing só em `p_obs`, limitado em [0,1].
  – `ZScore1d`: correção de continuidade Nigrini, `value=Z_max`, `detail` com todos os 9 dígitos.
  – `Chi2_1d`: gl=8, referência complementar, `higher_is_worse=False` no flag.

`analysis/metrics/benford_2d.py` — Lane 2
  – `_EXPECTED_2D`: normalização explícita necessária — 90 pares não somam exatamente 1.0 em ponto flutuante.
  – `MAD2d`: mesmo threshold que Lane 1, `detail` com top-10 desvios (não todos os 90).
  – `JS2d`: limiares mais conservadores (0.003/0.010), `detail` com top-5 contribuidores.
  – `ZScore2d`: proteção contra denominador zero via `np.errstate` + `np.where` para pares raros.

`analysis/metrics/last_digit.py` — Lane 3
  – H₀ distinta de Benford: distribuição uniforme P=10% por dígito.
  – `LastDigitChi2`: gl=9, métrica de decisão principal (não referência complementar).
  – `DigitPreference`: avalia só desvio positivo de freq(0) e freq(5). Thresholds idênticos ao `digit_spike` do M1 por design — consistência intencional entre camadas.

`analysis/engine/m2_engine.py`
  – `M2Engine`: dois rounds explícitos de `ThreadPoolExecutor`.
    - Round 1: `MAD1d · JS1d · MAD2d · JS2d · LastDigitChi2 · DigitPreference` — 6 futures em paralelo.
    - Round 2: `ZScore1d · Chi2_1d · ZScore2d` — submetidos após Round 1 completar.
  – `_apply_zscore_gate()`: rebaixa flag do Z-Score para `conforme` se MAD e JS não sinalizaram. Preserva `value` e `p_value` no `detail` com chave `"gate"`.
  – `ColumnAnalysis(frozen=True)`: `has_anomaly`, `critical_metrics`, `worst_flag`, `by_metric(name)`.
  – `_error_analysis()`: isola falha por coluna sem derrubar o módulo.

`analysis/engine/scorer.py`
  – Pesos canônicos: `JS_1d=0.30, MAD_1d=0.25, JS_2d=0.20, Z_max=0.15, last_digit=0.10`.
  – `last_digit` usa flag score (não value) — `LastDigitChi2` e `DigitPreference` têm escalas incomparáveis.
  – `M4Scorer`: normalização Min-Max **local** (dentro do módulo). Para análise isolada.
  – `GlobalScorer`: normalização Min-Max **global** across todos os escopos registrados.
    - `register(scope_id, analyses)` — acumula N módulos/partições.
    - `score_all(weights)` — normaliza globalmente, retorna scores.
    - `raw_values` — exposto para o `LHSSensitivityAnalyzer`.
    - `global_bounds()` — reporta faixa de normalização por componente.

`analysis/engine/sensitivity.py`
  – `LHSSensitivityAnalyzer`: gera N combinações de pesos via `scipy.stats.qmc.LatinHypercube`.
    - `_sample_weights_lhs()`: LHS em [0,1]^d → normaliza por linha → simplex uniforme.
    - `analyze(raw_values)`: matriz de rankings (n_samples × n_scopes), estabilidade por escopo.
  – `SensitivityResult`:
    - `stability_matrix`: DataFrame — posição no ranking para cada cenário de peso.
    - `top_k_stability`: fração dos cenários em que o escopo ficou no top-k.
    - `robust_top3`: escopos que ficaram no top-3 em >80% dos cenários.
    - `summary()`: tabela pronta para o TCC.

`analysis/io/s3_reader.py`
  – `get_analysis_input(module_path)`: lê `_MODULE_ELIGIBILITY.json` → nível módulo.
  – `get_partition_input(partition_path)`: lê `_eligibility.json` → nível partição.
  – `list_eligible_partitions(module_path)`: lista partições elegíveis individualmente.
  – `_extract_inputs()`: extração comum entre módulo e partição — mesma estrutura JSON.
  – `_parse_column_inputs()`: emite warning se `last_digit_counts` ou `two_digit_counts` ausentes (módulo gerado por versão anterior do M1).

`main.py` ← MODIFICADO
  – `--analyze`: executa M2 em dois níveis — módulo agregado + cada partição elegível.
  – `_print_temporal_comparison()`: detecta partições onde `score_partição > score_módulo + 0.20` — anomalia concentrada no tempo.
  – `--sensitivity`: executa `GlobalScorer` + `LHSSensitivityAnalyzer` após o loop de módulos.
  – `--lhs-samples`: número de amostras LHS (default 500, recomendado 1000+ para TCC).

---

### Formato dos JSONs — adições da Fase 3

**`_eligibility.json` e `_MODULE_ELIGIBILITY.json` — campos adicionados:**
```json
{
  "columns": {
    "valor_licitacao": {
      "two_digit_counts": {"10": 8400, "11": 7200, ..., "99": 310},
      "truncation_diagnostics": {
        "last_digit_counts": {"0": 14200, "1": 13800, ..., "9": 12100},
        "round_count": 1200
      }
    }
  }
}
```

---

### Fluxo completo de execução

```bash
# Fase 1+2 — M1: gera JSONs de elegibilidade
python main.py data/portal_da_transparencia/parquet/modulo=compras

# Fase 3 — M2: análise estatística em dois níveis
python main.py data/.../modulo=compras --analyze

# Fase 3 — M2 cross-módulo + LHS de sensibilidade
python main.py data/portal_da_transparencia/parquet/ --analyze --sensitivity

# TCC — máxima cobertura
python main.py data/.../parquet/ --analyze --sensitivity --lhs-samples 1000
```

---

### Próximos passos (Fases 4 e 5)

| Módulo | O que falta | Prioridade |
|---|---|---|
| `analysis/tests/` | `conftest.py` + fixtures sintéticas + `test_*.py` para todas as métricas | Imediato |
| M5 — Validação Sintética + ROC | Injeção de fraude 1%–30%, curva ROC, AUC > 0.85 | Após testes |
| M6 — Threshold/Bunching | KDE + IAB por órgão × UF, dicionário Lei 14.133/2021 | Após M5 |
| M7 — Redes de Beneficiários | Grafo bipartido, centrality, CNPJ < 12 meses | Após M6 |
| Dashboard Streamlit | Leitura direta do S3, heatmap, grafo, curva ROC | Nível 3 |
| README em inglês | Estruturado como abstract de paper | Nível 3 |
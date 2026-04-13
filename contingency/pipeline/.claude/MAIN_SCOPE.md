---

# Mapa de Esforço Técnico — Revisado

---

## 🔴 Nível 1 — Fundação (Semanas 1–2)
> *Com S3 + Parquet particionado já resolvido, este nível é apenas ajuste fino.*

**1.1 — Adaptador de Leitura Particionada**

Você já tem a infraestrutura. O único esforço aqui é garantir que o pipeline lê as partições de forma **seletiva e eficiente** — nunca carregando a base inteira na memória quando só precisa de um subconjunto.

```python
# O que já deve existir ou é trivial para você:
ds = pq.ParquetDataset(
    "s3://bucket/modulo=viagens/ano=2024/",
    filters=[("mes", "=", "11")]
)
df = ds.read_table(columns=["valor", "orgao", "uf"]).to_pandas()
```

O único item que merece atenção aqui é o **filtro de elegibilidade de Benford** — ele precisa ser executado *antes* de qualquer cálculo estatístico e seu resultado deve ser **persistido como metadado na própria partição** (um arquivo `_eligibility.json` por partição) para não repetir a triagem toda vez.

**O que registrar no `_eligibility.json`:**
- Ordens de magnitude cobertas
- Presença de truncamento artificial detectado
- Percentual de valores nulos/zerados descartados
- Decisão final: `elegível | inelegível | elegível_com_ressalva`

Isso vira uma tabela de metodologia no TCC e demonstra rigor que trabalhos importados não têm.

---

## 🔴 Nível 1.2 — Motor Estatístico (M2) — Semanas 2–5
> *Este ainda é fundação. Não tem atalho.*

A única mudança em relação ao mapa anterior é que com Parquet no S3 você consegue rodar o motor em **chunks por partição** naturalmente — o que significa que seu pipeline escala para bases de dezenas de milhões de registros sem esforço adicional.

Estrutura de classes recomendada:

```
analysis/
├── metrics/
│   ├── benford.py        # MAD, JS, Qui-Quadrado, Z-Score
│   ├── last_digit.py     # Last Digit Test χ²
│   └── base.py           # Classe abstrata BenfordMetric
├── io/
│   └── s3_reader.py      # Leitura particionada + eligibility check
└── tests/
    └── test_metrics.py   # pytest com distribuições sintéticas
```

O detalhe que eleva o trabalho: cada classe de métrica deve aceitar um `pd.Series` e devolver um **dataclass tipado** com o valor da métrica, o p-valor quando aplicável, e o flag de interpretação (`conforme | alerta | crítico`). Isso torna o M4 (Score Composto) trivial de implementar e o código autodocumentado.

---

## 🟠 Nível 2 — Diferencial Técnico (Semanas 5–16)
> *É aqui que a nota e o portfólio são construídos.*

**2.1 — Score Composto + Análise de Sensibilidade (M4)**

Este é o módulo de maior retorno acadêmico por hora investida. A análise de sensibilidade dos pesos é o que transforma o TCC em linguagem de paper.

O esforço concreto está em três etapas:

**Etapa A — Implementação do Score:**
Normalização Min-Max por métrica calculada *across* todas as partições processadas — o min e max precisam ser globais, não locais por partição. Isso é um detalhe sutil que a maioria erra e que um avaliador técnico vai notar.

**Etapa B — Latin Hypercube Sampling dos pesos:**
Gerar 500+ combinações de pesos $(w_1...w_5)$ com restrição $\sum w_i = 1$ usando `scipy.stats.qmc.LatinHypercube`. Para cada combinação, calcular o ranking das bases e registrar a posição de cada uma. O resultado é uma **matriz de estabilidade de ranking** — a figura mais poderosa que você pode colocar no TCC.

**Etapa C — Resultado esperado para o TCC:**
As 3 bases mais suspeitas devem manter suas posições em >80% dos cenários. Se mantiverem, você prova que o resultado não é artefato da escolha de pesos. Isso é rigor científico real.

---

**2.2 — Protocolo de Validação Sintética + Curva ROC (M5)**

Este é o módulo que separa demonstração de ciência — e com sua infraestrutura S3, você tem uma vantagem: pode versionar as bases adulteradas como partições separadas (`/validacao=sintetica/nivel=1/`) e rodar o pipeline exatamente como em produção.

Os 3 níveis de injeção já definidos, mas o esforço técnico está na **curva ROC**:

- Variar o percentual de adulteração de 1% a 30% em passos de 1%
- Para cada percentual, rodar o pipeline completo e registrar Score Composto
- Definir um limiar de decisão e calcular TPR/FPR
- Plotar a curva ROC e calcular AUC

**AUC > 0.85 = resultado publicável.** Esta é a única métrica que um comitê de admissão de qualquer país do mundo vai olhar e entender imediatamente o que o sistema faz.

Com seu particionamento por mês/dia, você tem um bônus: pode rodar a validação sintética em janelas temporais e mostrar que o sistema detecta adulteração mesmo em subconjuntos pequenos — isso vira um resultado adicional na seção de experimentos.

---

**2.3 — Análise de Proximidade de Limiares Legais (Threshold/Bunching)**

Com Parquet particionado por módulo, este módulo fica natural: você roda especificamente sobre `modulo=licitacoes` filtrando `modalidade=Dispensa`.

O esforço real está em dois pontos:

- Construir e manter um **dicionário de limiares legais** versionado (os valores da Lei nº 14.133/2021 corrigidos por índice) — isso é trabalho de pesquisa jurídica, não de código, e vai aparecer como contribuição metodológica no TCC
- Implementar o KDE com `scipy.stats.gaussian_kde` e calcular o IAB para cada órgão × UF — a saída é um heatmap de suspeição geográfica que é visualmente impactante

---

**2.4 — Análise de Redes de Beneficiários (M7)**

Com seu nível em grafos e o S3 já estruturado, este módulo é o de **maior retorno para a candidatura à pós** por hora investida.

O particionamento que você já tem ajuda diretamente: você pode construir o grafo incrementalmente por partição temporal e detectar quando um novo CNPJ aparece pela primeira vez — o delta entre data de constituição da empresa (consultável via API da Receita Federal) e data do primeiro contrato é uma feature poderosa.

Esforço técnico concentrado em:

- Construção do grafo bipartido órgão–fornecedor com arestas ponderadas por volume financeiro acumulado
- Cálculo de degree centrality e clustering coefficient por componente
- **A feature mais valiosa:** identificar CNPJs com alta concentração em um único órgão pagador *e* constituídos há menos de 12 meses antes do contrato — isso é a assinatura de empresa de prateleira

O grafo como figura no TCC e no GitHub README é o elemento visualmente mais marcante do portfólio inteiro.

---

## 🟡 Nível 3 — Acabamento Acadêmico (Semanas 17–22)
> *Transforma bom projeto em candidatura forte.*

**3.1 — Dashboard (Streamlit)**

Com S3 como backend, o dashboard lê diretamente das partições processadas — não precisa reprocessar nada. Isso significa que você pode ter um dashboard em produção real apontando para dados reais, o que é raro em TCCs.

Componentes obrigatórios em ordem de impacto visual:
1. Heatmap de Score Composto por órgão × UF
2. Grafo de rede interativo (Pyvis embarcado no Streamlit)
3. Curva ROC da validação sintética
4. Série temporal de scores com marcadores de eventos históricos

**3.2 — Repositório GitHub como Portfólio**

Este item não é código — é apresentação. Com seu nível, o README em inglês estruturado como abstract de paper é questão de algumas horas e vale mais do que qualquer funcionalidade adicional para a candidatura.

Estrutura do README:

```
## RING Analysis
Automated multi-metric anomaly detection pipeline for Brazilian 
public expenditure data using Benford's Law and complementary 
statistical divergence measures.

### Results
- AUC: 0.XX (synthetic validation)
- Detects manipulation from X% of tampered records
- Processes 1M+ records in < 5 min on commodity hardware

### Architecture
[diagrama simples do pipeline S3 → métricas → score → dashboard]
```

**3.3 — Seção de Trabalhos Futuros**

Para a candidatura à pós esta seção sinaliza que você enxerga uma agenda de pesquisa, não só um projeto concluído. Descrever M8 (STL + CUSUM), M9 (Z-Score de preço) e M10 (consistência cruzada entre bases) com complexidade técnica mapeada mostra maturidade que comitês de Carnegie Mellon, ETH Zurich e UBC reconhecem diretamente.

---

## Mapa Final Revisado

| Módulo | Semanas | Impacto na Nota | Impacto na Pós | Observação |
|---|---|---|---|---|
| Eligibility Filter + S3 Adapter | 1–2 | ★★★☆☆ | ★★☆☆☆ | Já 80% resolvido pela sua infra |
| M2 — Motor Estatístico | 2–5 | ★★★★★ | ★★★★★ | Coração do trabalho |
| M4 — Score + LHS Sensitivity | 5–9 | ★★★★★ | ★★★★★ | Linguagem de paper |
| M5 — Validação Sintética + ROC | 8–13 | ★★★★★ | ★★★★★ | AUC é o resultado universal |
| Threshold/Bunching | 11–14 | ★★★★☆ | ★★★★☆ | Exclusivo do contexto BR |
| M7 — Redes/Grafos | 13–16 | ★★★☆☆ | ★★★★★ | Maior diferencial de portfólio |
| Dashboard Streamlit + S3 | 17–19 | ★★★☆☆ | ★★★☆☆ | Demo ao vivo na defesa |
| GitHub README em inglês | 20 | ★★☆☆☆ | ★★★★★ | 4 horas, retorno enorme |

---

O próximo passo mais natural seria o esqueleto do M2 — quer que eu gere as classes Python com a estrutura de dataclass tipada e os testes unitários já integrados, assumindo leitura via PyArrow do S3?
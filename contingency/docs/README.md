# Data Lake — Guia de Mapeamento de Módulos

## Visão Geral

Este guia documenta o processo completo para mapear um novo módulo do S3
como um `DuckDBModel` na camada Bronze.

```
S3 (parquet bruto)
      │
      ├── 1. Scanner        → descobre estrutura Hive (modulo/ano/mes)
      ├── 2. Inspector      → lê schema real das colunas via DuckDB
      ├── 3. fields.py      → tipos declarativos baseados no schema
      ├── 4. BronzeModel    → classe que espelha o parquet
      └── 5. Teste          → valida leitura real do S3
```

---

## Pré-requisitos

### Variáveis de ambiente (`dev.env`)

```bash
DJANGO_SETTINGS_MODULE=contingency.settings
DATALAKE_BUCKET=seu-bucket
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=sa-east-1
```

### Estrutura esperada no S3

```
s3://<bucket>/data/<dataset>/modulo=X/ano=Y/mes=Z/*.parquet
```

---

## Passo 1 — Descobrir a estrutura do S3

Execute o management command para inspecionar todos os módulos disponíveis:

```bash
# inspecionar tudo e salvar
uv run manage.py inspect_bronze > bronze_schema.txt 2>&1

# ou focar em um dataset específico
uv run manage.py inspect_bronze --dataset portal_transparencia
```

### O que o comando faz

O `BronzeInspector` combina dois clientes:

- **boto3** (`S3PartitionScanner`) → varre o bucket e descobre a árvore
  `modulo/ano/mes` sem ler os arquivos
- **DuckDB** → lê `LIMIT 0` de um parquet para extrair colunas e tipos

### Output esperado

```
DatasetSchema → portal_da_transparencia/parquet/ / modulo=cpgf
  Colunas:
    CÓDIGO ÓRGÃO SUPERIOR     VARCHAR
    NOME ÓRGÃO SUPERIOR       VARCHAR
    CPF PORTADOR              VARCHAR
    CNPJ OU CPF FAVORECIDO    VARCHAR
    VALOR TRANSAÇÃO           VARCHAR
    DATA TRANSAÇÃO            VARCHAR
    ...
    ano                       BIGINT
    mes                       VARCHAR
    modulo                    VARCHAR

  Partições disponíveis:
    ano=2013  meses=['01'..'12']  arquivos=12
    ...
    ano=2026  meses=['01', '02']  arquivos=2
```

### Problemas conhecidos no output

| Sintoma                    | Causa                                        | Ação                                |
|----------------------------|----------------------------------------------|-------------------------------------|
| `__error__` HTTP 403       | Credenciais não configuradas no DuckDB       | Aplicar fix paramétrico no `s3.py`  |
| `__error__` file too small | Arquivo temporário `tmp*.parquet` corrompido | Ignorar — não afeta outros arquivos |
| `mes=unknown`              | Dataset publicado anualmente pelo governo    | Normal — aceitar como valor válido  |
| `ano=unknown`              | Dataset sem partição temporal                | Normal — ex: emendas-parlamentares  |

---

## Passo 2 — Analisar o schema

Com o `bronze_schema.txt` em mãos, identificar para cada módulo:

**a) Tipos de colunas presentes**

| Tipo DuckDB | Field a usar                                           |
|-------------|--------------------------------------------------------|
| `VARCHAR`   | `StringField` ou semântico (CPF, CNPJ, Money, Date...) |
| `BIGINT`    | `BigIntField` ou semântico (NIS, códigos)              |
| `INTEGER`   | `IntegerField`                                         |
| `TIMESTAMP` | `DateTimeField`                                        |
| `DOUBLE`    | `FloatField`                                           |

**b) Chaves de correlação** — colunas que ligam datasets entre si

| Padrão no nome da coluna             | Field semântico            |
|--------------------------------------|----------------------------|
| contém `CPF` e `CNPJ` no mesmo campo | `CPFCNPJField`             |
| contém só `CPF`                      | `CPFField`                 |
| contém só `CNPJ`                     | `CNPJField`                |
| contém `NIS` como BIGINT             | `NISField`                 |
| contém `NIS` como VARCHAR            | `NISVarcharField`          |
| contém `VALOR`                       | `MoneyField`               |
| contém `DATA` ou `DT`                | `DateVarcharField`         |
| contém `CÓDIGO ÓRGÃO SUPERIOR`       | `CodigoOrgaoSuperiorField` |
| contém `CÓDIGO UNIDADE GESTORA`      | `CodigoUGField`            |
| contém `CNPJ` (apenas)               | `CNAEField` se for CNAE    |

**c) Inconsistências a documentar para a Silver**

Anotar no `description` do field quando:

- mesmo conceito tem tipos diferentes entre módulos
  (ex: `NIS` é `BIGINT` em `auxilio-brasil` e `VARCHAR` em `bolsa-familia`)
- valores monetários têm formatos diferentes (`'1.234,56'` vs `'1234.56'`)
- datas têm formatos diferentes (`'DD/MM/YYYY'` vs `'YYYY-MM-DD'`)

---

## Passo 3 — Verificar o `fields.py`

Antes de criar o modelo, confirmar se o field necessário já existe:

```python
# apps/datalake/orm/fields.py

# tipos primitivos
StringField, BigIntField, IntegerField, FloatField, BooleanField, DateTimeField

# partições
PartitionAnoField, PartitionMesField, PartitionModuloField

# identificadores de pessoas
CPFField, CNPJField, CPFCNPJField, NISField, NISVarcharField, IdServidorField

# identificadores de órgãos
CodigoOrgaoSuperiorField, CodigoOrgaoField, CodigoUGField
CodigoUnidadeOrcamentariaField

# geográficos
UFField, CodigoMunicipioSIAFIField, CodigoMunicipioIBGEField
NomeMunicipioField, CEPField

# orçamentários
CodigoFuncaoField, CodigoSubfuncaoField, CodigoProgramaField
CodigoAcaoField, CodigoElementoDespesaField, CodigoGrupoDespesaField
CodigoModalidadeAplicacaoField

# documentos e processos
NumeroProcessoField, NumeroConvenioField, NumeroLicitacaoField
NumeroContratoField, ChaveNFeField, CodigoEmendaField, CodigoAutorEmendaField

# classificação econômica
CNAEField, NaturezaJuridicaField, NCMField, CFOPField

# datas
DateVarcharField, AnoExercicioField

# valores
MoneyField, PercentualField

# sanção e compliance
CodigoSancaoField, TipoPessoaField, EsferaOrgaoField, FundamentacaoLegalField

# programas sociais
SituacaoBeneficioField, EnquadramentoField, RGPField, NumeroBeneficioField

# servidores
CargoField, FuncaoConfiancaField, OrgaoLotacaoField

# viagens
PCDPField, JustificativaField

# notas fiscais
InscricaoEstadualField, IndicadorIEField, ModeloDocFiscalField
```

Se o field necessário não existir, criar em `fields.py` antes de continuar.

---

## Passo 4 — Criar o modelo Bronze

### Localização do arquivo

```
apps/
└── <nome_do_app>/
    └── models/
        └── <modulo>.py
```

Módulos agrupados por afinidade:

| Arquivo             | Módulos                                                                                              |
|---------------------|------------------------------------------------------------------------------------------------------|
| `beneficios.py`     | bolsa-familia-*, auxilio-*, novo-bolsa-familia, bpc, pe-de-meia, peti, seguro-defeso, garantia-safra |
| `servidores.py`     | servidores, pep, imoveis-funcionais, viagens                                                         |
| `despesas.py`       | despesas, despesas-execucao, despesas-favorecidos                                                    |
| `compras.py`        | compras, licitacoes, notas-fiscais                                                                   |
| `transferencias.py` | transferencias, convenios, emendas-parlamentares*                                                    |
| `receitas.py`       | receitas, orcamento-despesa                                                                          |
| `sancoes.py`        | ceis, cnep, ceaf, acordos-leniencia, cepim                                                           |
| `cartoes.py`        | cpgf, cpdc, cpcc                                                                                     |
| `cadastros.py`      | favorecidos-pj, renuncias                                                                            |

### Estrutura obrigatória do modelo

```python
# apps/<app>/models/<modulo>.py
"""
<Nome Completo do Módulo>

Fonte    : <órgão> — <sistema>
S3       : <dataset_path>/modulo=<modulo>/
Histórico: <ano_inicio> → <ano_fim>
Arquivos : ~<n> por ano

<Descrição do que são os dados>

Chaves de correlação:
    <CAMPO>  → <outros modulos que têm o mesmo campo>
"""

from apps.datalake.orm.fields import (

...)
from apps.datalake.orm.model import DuckDBModel


class <NomeClasse > (DuckDBModel):
    """
    <Módulo> — camada Bronze.
    Espelho fiel do parquet no S3. Nenhuma transformação aplicada.

    Uso:
        <NomeClasse>.scan(ano="2024", mes="01").limit(5).show()
        <NomeClasse>.polars(ano="2024").filter(...).collect()
    """

    dataset_path = "<dataset_path>/"
    modulo = "<nome-do-modulo>"  # ← string usada no path S3

    # ── <Grupo de campos> ─────────────────────────────────────────────
    NOME_CAMPO = TipoField(
        source_name="NOME ORIGINAL NO PARQUET",
        description="O que é + o que Silver precisa fazer + com quem correlaciona",
    )
    ...

    # ── Partições Hive ────────────────────────────────────────────────
    partition_ano = PartitionAnoField()
    partition_mes = PartitionMesField()
    partition_modulo = PartitionModuloField()
```

### Regras de nomenclatura

| O que              | Convenção             | Exemplo                      |
|--------------------|-----------------------|------------------------------|
| Nome da classe     | PascalCase            | `BolsaFamiliaPagamentos`     |
| Atributo `modulo`  | string exata do S3    | `"bolsa-familia-pagamentos"` |
| Campos de dados    | UPPER_SNAKE_CASE      | `CPF_FAVORECIDO`             |
| Campos de partição | `partition_` + nome   | `partition_ano`              |
| `source_name`      | nome exato do parquet | `"CPF FAVORECIDO"`           |

> ⚠️ **Nunca** usar `modulo` como nome de campo — conflita com o atributo
> de classe `modulo = "nome-do-modulo"`. Sempre usar `partition_modulo`.

---

## Passo 5 — Testar o modelo

```python
# uv run manage.py shell

from apps. < app >.models. < modulo >
import < NomeClasse >

# 5.1 confirmar o path gerado antes de bater no S3
print( < NomeClasse >._resolve_path(ano="2024", mes="01"))
# esperado: <dataset_path>/modulo=<modulo>/ano=2024/mes=01

# 5.2 testar conexão e schema
rel = < NomeClasse >.scan(ano="2024", mes="01")
print(rel.columns)
print(rel.dtypes)

# 5.3 testar leitura de dados reais
rel.limit(5).show()

# 5.4 testar via Polars
import polars as pl

df = < NomeClasse >.polars(ano="2024", mes="01").limit(10).collect()
print(df)

# 5.5 testar scan sem partição (lê tudo — cuidado com volume)
< NomeClasse >.scan().limit(5).show()
```

### Erros comuns e soluções

| Erro                                                  | Causa                                            | Solução                                   |
|-------------------------------------------------------|--------------------------------------------------|-------------------------------------------|
| `No files found ... modulo=PartitionModuloField(...)` | Campo `modulo` sobrescrevendo atributo de classe | Renomear para `partition_modulo`          |
| `No files found ... /ano=2024/mes=01/`                | `modulo` não injetado no path                    | Verificar `_resolve_path` no `model.py`   |
| `HTTP 403 Forbidden`                                  | Credenciais no DuckDB com f-string quebrando     | Usar `SET ... = ?` paramétrico no `s3.py` |
| `file too small`                                      | Arquivo `tmp*.parquet` corrompido no S3          | Ignorar — testar com outra partição       |

---

## Checklist de um módulo pronto

```
[ ] bronze_schema.txt consultado para o módulo
[ ] Todos os tipos de campo existem no fields.py
[ ] Classe criada no arquivo correto (grupo por afinidade)
[ ] dataset_path e modulo definidos como strings
[ ] source_name preenchido com nome exato do parquet
[ ] description documenta Silver + correlações
[ ] Campos de partição nomeados como partition_ano/mes/modulo
[ ] _resolve_path() retorna path correto
[ ] scan(ano, mes).limit(5).show() retorna dados reais
[ ] polars(ano, mes).limit(10).collect() retorna DataFrame
```

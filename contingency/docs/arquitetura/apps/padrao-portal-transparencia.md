# Padrão Estrutural — Portal da Transparência

## Observações críticas antes de modelar

### ❌ Corrompidos / ilegíveis

| Módulo | Problema |
|---|---|
| `despesas` | Arquivo `tmp12sdzffu.parquet` corrompido em `ano=2013/mes=12` — arquivos temporários não removidos do S3 |

---

### 📅 Sem partição mensal (`mes=unknown`)

Esses módulos são publicados **anualmente** pelo governo — não têm granularidade mensal:

| Módulo | Anos disponíveis | Observação |
|---|---|---|
| `viagens` | 2011→2026 | Maior cobertura histórica do dataset |
| `receitas` | 2013→2026 | Orçamento federal anual |
| `orcamento-despesa` | 2014→2026 | LOA anual |
| `renuncias` | 2015→2024 | Benefícios fiscais por CNPJ |
| `emendas-parlamentares` | `ano=unknown` também | Duplo unknown — ano E mês desconhecidos |
| `emendas-parlamentares-documentos` | 2014→2026 | Só mês unknown |
| `apoiamento-emendas-parlamentares-documentos` | 2020→2025 | Só mês unknown |
| `orcamento-despesa` | 2014→2026 | Só mês unknown |

---

## Padrão de campos por módulo

### Grupo 1 — Benefícios sociais (CPF como chave)

| Campo | `bolsa-familia-pagamentos` | `auxilio-brasil` | `auxilio-emergencial` | `novo-bolsa-familia` | `bpc` | `pe-de-meia` | `seguro-defeso` | `auxilio-reconstrucao` | `peti` | `garantia-safra` |
|---|---|---|---|---|---|---|---|---|---|---|
| MÊS COMPETÊNCIA | ✅ VARCHAR | ✅ BIGINT | ❌ | ✅ VARCHAR | ✅ VARCHAR | ❌ | ❌ | ❌ | ❌ | ❌ |
| MÊS REFERÊNCIA | ✅ VARCHAR | ✅ BIGINT | ❌ | ✅ VARCHAR | ✅ VARCHAR | ✅ VARCHAR | ✅ VARCHAR | ✅ BIGINT | ✅ VARCHAR | ✅ VARCHAR |
| UF | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| CÓDIGO MUNICÍPIO SIAFI | ✅ VARCHAR | ✅ BIGINT | ❌ | ✅ VARCHAR | ✅ VARCHAR | ✅ VARCHAR | ✅ VARCHAR | ✅ BIGINT | ✅ VARCHAR | ✅ VARCHAR |
| CÓDIGO MUNICÍPIO IBGE | ❌ | ❌ | ✅ BIGINT | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| NOME MUNICÍPIO | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| CPF FAVORECIDO | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ |
| CPF BENEFICIÁRIO | ❌ | ❌ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| CPF RESPONSÁVEL | ❌ | ❌ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| NIS FAVORECIDO | ✅ VARCHAR | ✅ BIGINT | ❌ | ✅ VARCHAR | ❌ | ❌ | ✅ VARCHAR | ✅ BIGINT | ✅ VARCHAR | ✅ VARCHAR |
| NIS BENEFICIÁRIO | ❌ | ❌ | ✅ BIGINT | ❌ | ✅ VARCHAR | ✅ VARCHAR | ❌ | ❌ | ❌ | ❌ |
| NOME FAVORECIDO | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ |
| NOME BENEFICIÁRIO | ❌ | ❌ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| VALOR PARCELA | ✅ VARCHAR | ✅ VARCHAR | ❌ | ✅ VARCHAR | ✅ VARCHAR | ✅ VARCHAR | ✅ VARCHAR | ✅ VARCHAR | ✅ VARCHAR | ✅ VARCHAR |
| VALOR BENEFÍCIO | ❌ | ❌ | ✅ VARCHAR | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

> ⚠️ **Inconsistências críticas para Silver:**
> - `CÓDIGO MUNICÍPIO SIAFI` ora é `VARCHAR` ora é `BIGINT`
> - `NIS` ora é `VARCHAR` ora é `BIGINT`
> - `MÊS COMPETÊNCIA/REFERÊNCIA` ora é `VARCHAR` ora é `BIGINT`
> - CPF do beneficiário tem **3 nomes diferentes**: `CPF FAVORECIDO`, `CPF BENEFICIÁRIO`, campo `CPF`

---

### Grupo 2 — Servidores e pessoas físicas (CPF como chave)

| Campo | `servidores` | `pep` | `imoveis-funcionais` | `viagens` |
|---|---|---|---|---|
| CPF | ✅ VARCHAR | ✅ VARCHAR | ✅ VARCHAR | `CPF viajante` VARCHAR |
| NOME | ✅ VARCHAR | `Nome_PEP` VARCHAR | `Nome Permissionário` VARCHAR | `Nome` VARCHAR |
| CARGO/FUNÇÃO | ❌ | `Sigla_Função` + `Descrição_Função` | `Cargo ou Função` | `Cargo` + `Função` |
| ÓRGÃO | `EMPRESA` VARCHAR | `Nome_Órgão` VARCHAR | `Órgão Exercício` VARCHAR | `Nome órgão solicitante` VARCHAR |
| VALOR | ✅ VARCHAR | ❌ | ❌ | `Valor diárias` + `Valor passagens` |
| Id_SERVIDOR_PORTAL | ✅ VARCHAR | ❌ | ❌ | ❌ |
| DATA INÍCIO | ❌ | ✅ VARCHAR | `Data de Ocupação` VARCHAR | `Período - Data de início` VARCHAR |
| DATA FIM | ❌ | ✅ VARCHAR | ❌ | `Período - Data de fim` VARCHAR |

> ⚠️ `servidores` é o único módulo onde `ano` e `mes` **não vêm como colunas de partição Hive** — vêm como `ANO BIGINT` e `MES VARCHAR` dentro do próprio arquivo.

---

### Grupo 3 — Sanções (CPF ou CNPJ como chave)

| Campo | `ceis` | `cnep` | `ceaf` | `acordos-leniencia` | `cepim` |
|---|---|---|---|---|---|
| CPF OU CNPJ DO SANCIONADO | ✅ | ✅ | ✅ | ❌ | ❌ |
| CNPJ DO SANCIONADO | ❌ | ❌ | ❌ | ✅ | ❌ |
| CNPJ ENTIDADE | ❌ | ❌ | ❌ | ❌ | ✅ |
| TIPO DE PESSOA | ✅ | ✅ | ✅ | ❌ | ❌ |
| NOME DO SANCIONADO | ✅ | ✅ | ✅ | `RAZÃO SOCIAL CADASTRO RECEITA` | `NOME ENTIDADE` |
| DATA INÍCIO SANÇÃO | ✅ | ✅ | ✅ | `DATA DE INÍCIO DO ACORDO` | ❌ |
| ÓRGÃO SANCIONADOR | ✅ | ✅ | ✅ | ✅ | `ÓRGÃO CONCEDENTE` |
| VALOR DA MULTA | ❌ | ✅ | ❌ | ❌ | ❌ |

---

### Grupo 4 — Cartões de pagamento (CPF/CNPJ como chave)

| Campo | `cpgf` | `cpdc` | `cpcc` |
|---|---|---|---|
| CPF PORTADOR | ✅ VARCHAR | ✅ VARCHAR | ❌ |
| CNPJ OU CPF FAVORECIDO | ✅ VARCHAR | ✅ VARCHAR | ✅ VARCHAR |
| VALOR TRANSAÇÃO | ✅ VARCHAR | ✅ VARCHAR | ✅ VARCHAR |
| DATA TRANSAÇÃO | ✅ VARCHAR | ✅ VARCHAR | ✅ VARCHAR |
| TRANSAÇÃO | ✅ VARCHAR | ✅ VARCHAR | ✅ VARCHAR |
| NÚMERO CONVÊNIO | ❌ | ✅ VARCHAR | ❌ |
| REPASSE | ❌ | ✅ VARCHAR | ❌ |

> ✅ Grupo mais consistente — schema quase idêntico entre os 3 módulos.

---

### Grupo 5 — Compras e contratos (CNPJ como chave)

| Campo | `compras` | `licitacoes` | `notas-fiscais` |
|---|---|---|---|
| Código Órgão | ✅ VARCHAR | ✅ VARCHAR | `CÓDIGO ÓRGÃO DESTINATÁRIO` VARCHAR |
| CNPJ/CPF Emitente | ❌ | ❌ | ✅ VARCHAR |
| CNPJ DESTINATÁRIO | ❌ | ❌ | ✅ VARCHAR |
| Número Contrato | ✅ VARCHAR | `Número Licitação` VARCHAR | ❌ |
| Valor | `Valor Item` VARCHAR | ❌ | `VALOR TOTAL` VARCHAR |

---

### Grupo 6 — Despesas orçamentárias (sem chave CPF/CNPJ direta)

| Campo | `despesas` | `despesas-execucao` | `despesas-favorecidos` |
|---|---|---|---|
| Código Favorecido | ❌ | ❌ | ✅ VARCHAR |
| Nome Favorecido | ❌ | ❌ | ✅ VARCHAR |
| Valor Pago | ❌ | ✅ VARCHAR | `Valor Recebido` VARCHAR |
| Valor Empenhado | ❌ | ✅ VARCHAR | ❌ |
| Código Órgão Superior | ❌ | ✅ VARCHAR | ✅ VARCHAR |

> ⚠️ `despesas` base tem `__error__` — precisará de fallback para outra partição no inspector.

---

## Resumo de decisões de arquitetura

```
BRONZE (espelho fiel do S3)
│
│  Respeitar tipos originais — não converter nada
│  Nomes de colunas exatamente como no parquet (com espaços, acentos)
│  mes=unknown → aceitar como valor válido
│  Arquivos tmp*.parquet → ignorar no inspector
│
SILVER (normalização)
│
│  CPF FAVORECIDO + CPF BENEFICIÁRIO + CPF → campo único: cpf
│  CÓDIGO MUNICÍPIO SIAFI VARCHAR/BIGINT  → sempre VARCHAR
│  NIS VARCHAR/BIGINT                     → sempre VARCHAR
│  VALOR * VARCHAR                        → Decimal (limpeza de R$ e vírgulas)
│  Nomes de colunas → snake_case sem acentos
│
GOLD (correlações)
│
│  CPF  → cruza servidores × benefícios × sanções × viagens × BNDES
│  CNPJ → cruza compras × notas-fiscais × sanções × renuncias × BNDES
```

---

Está alinhado com o que você esperava? Com esse mapa podemos criar o `fields.py` e os `BronzeModel` sabendo exatamente quais tipos e inconsistências tratar em cada camada.
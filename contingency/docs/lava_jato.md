Aqui está o guia prático e direto ao ponto. Separei por fonte, com o nome exato do dataset e o período recomendado.

---

## 1. Portal da Transparência Federal (CGU) — Download Direto em CSV

**URL base:** `portaldatransparencia.gov.br/download-de-dados`

| Dataset | Nome no Portal | Anos Disponíveis | Período Recomendado |
|---|---|---|---|
| Contratos (histórico) | **Contratos — Páginas de Transparência** | 2006–2012 (histórico) + 2013–atual | **2006–2016** |
| Licitações | **Licitações realizadas** | A partir de 2013 | **2013–2016** |
| Despesas (empenhos) | **Despesas Públicas** | A partir de 2004 | **2006–2016** |
| Viagens e Diárias | **Viagens a Serviço** | A partir de 2011 | **2011–2016** |
| Convênios | **Convênios e Outros Acordos** | A partir de 2008 | **2008–2016** |

> **Atenção importante:** dados anteriores a 2013 estão na seção "Páginas de Transparência Pública" e são disponibilizados em formato CSV separado. [Portal da Transparência](https://portaldatransparencia.gov.br/download-de-dados/historico/paginas-de-transparencia) Você precisará baixar dois blocos: o histórico (pré-2013) e o moderno (pós-2013), depois concatenar no pandas.

---

## 2. BNDES — Operações de Financiamento

**URL:** `dadosabertos.bndes.gov.br`

| Dataset | Nome no Portal | Anos Disponíveis | Período Recomendado |
|---|---|---|---|
| Financiamentos domésticos | **Operações de Financiamento** | A partir de 2002 | **2002–2016** |
| Exportação de serviços | **Operações de Exportação** | A partir de 1998 | **2007–2016** |

O dataset de Operações de Financiamento contém dados detalhados das condições das operações contratadas, incluindo porte do cliente e produto contratado, com dados a partir de 2002. [Bndes](https://dadosabertos.bndes.gov.br/dataset/operacoes-financiamento)

Este é o dataset mais poderoso para a Lava Jato. Cerca de US$ 10,5 bilhões foram desembolsados entre 1998 e 2017, com Odebrecht concentrando 76% dos valores, Andrade Gutierrez 14%, Queiroz Galvão 4%, Camargo Corrêa 2% e OAS 2%. [BNDES Aberto](https://aberto.bndes.gov.br/aberto/caso/exportacao/)

---

## 3. Mapa de Download por Fase da Lava Jato

```
Fase Pré-Operação (fraude ativa, sem pressão):
→ BNDES Exportação:          2007 – 2013
→ Contratos CGU:             2008 – 2013
→ Convênios CGU:             2008 – 2013

Fase Operação (pressão investigativa):
→ Todos os datasets acima:   2014 – 2016

Grupo Controle (baseline limpo):
→ Despesas Públicas gerais:  2010 – 2016
   (excluindo órgãos com contratos das empreiteiras)
```

---

## 4. Nomes Exatos dos Arquivos CSV que Você Vai Baixar

| Arquivo | Contém |
|---|---|
| `Contratos_AAAA.csv` | Valor, fornecedor CNPJ, órgão, modalidade |
| `Licitacoes_AAAA.csv` | Modalidade, participantes, valor estimado |
| `Viagens_AAAA.csv` | Diárias — útil para digit preference test |
| `Despesas_AAAA.csv` | Empenhos — maior volume, baseline |
| `operacoes-financiamento.csv` | BNDES — valores de financiamento |

O padrão é um arquivo por ano. Para o seu pipeline você vai empilhar todos com `pd.concat()`.

---

## 5. Dica de Filtragem no Pandas (pós-download)

```python
# CNPJs das principais investigadas na Lava Jato
cnpjs_investigadas = [
    '07206477000100',  # Odebrecht Engenharia
    '04711685000140',  # OAS
    '17260197000104',  # Andrade Gutierrez
    '61522512000162',  # Camargo Corrêa
    '33389822000108',  # UTC Engenharia
]

df_suspeito = df[df['cnpj_fornecedor'].isin(cnpjs_investigadas)]
df_suspeito = df_suspeito[
    (df_suspeito['ano'] >= 2007) & 
    (df_suspeito['ano'] <= 2016)
]
```

---

Comece pelo **BNDES Operações de Financiamento** — é o mais limpo, bem estruturado, e tem os valores mais expressivos (múltiplas ordens de magnitude), o que satisfaz perfeitamente a pré-condição de Benford. Quer que eu monte o código do M1 já apontando para esses arquivos?

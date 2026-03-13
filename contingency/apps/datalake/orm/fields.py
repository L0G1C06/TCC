# apps/datalake/orm/fields.py
"""
Fields declarativos para modelos do Data Lake — dados governamentais brasileiros.

Baseado nos tipos reais encontrados no bronze_schema.txt do Portal da Transparência
e padrões recorrentes em bases públicas brasileiras (CGU, BNDES, Receita Federal,
IBGE, TCU, STN, SIAFI, SIASG, CEIS, CNEP, etc.)

Não fazem nada em runtime — são descritores declarativos para:
    1. Documentar o schema de cada BronzeModel
    2. Guiar as transformações da camada Silver
    3. Identificar chaves de correlação entre datasets
"""

from __future__ import annotations
from dataclasses import dataclass


# ── Base ──────────────────────────────────────────────────────────────────────

@dataclass
class Field:
    """
    Classe base de todos os campos.

    Atributos:
        nullable    : o campo pode ser nulo no parquet
        description : documentação livre sobre o campo
        source_name : nome original no parquet (quando diferente do atributo Python)
                      ex: source_name="CPF FAVORECIDO" no atributo cpf
    """
    nullable:     bool = True
    description:  str  = ""
    source_name:  str  = ""

    duck_type:    str  = "VARCHAR"
    polars_type:  str  = "Utf8"

    is_partition: bool = False
    is_join_key:  bool = False

    def __repr__(self) -> str:
        extras = []
        if self.is_partition: extras.append("partition")
        if self.is_join_key:  extras.append("join_key")
        if self.source_name:  extras.append(f"src='{self.source_name}'")
        tag = f" [{', '.join(extras)}]" if extras else ""
        return f"{self.__class__.__name__}{tag}"


# ─────────────────────────────────────────────────────────────────────────────
# TIPOS PRIMITIVOS — mapeamento direto dos tipos encontrados no S3
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class StringField(Field):
    """
    VARCHAR — tipo mais comum no S3.
    Usado para nomes, códigos, descrições, valores monetários crus (ex: '1.234,56').
    """
    duck_type:   str = "VARCHAR"
    polars_type: str = "Utf8"


@dataclass
class BigIntField(Field):
    """
    BIGINT — IDs numéricos, anos, NIS, códigos municipais.

    Aparece em:
        - NIS FAVORECIDO (auxilio-brasil, auxilio-emergencial)
        - CÓDIGO MUNICÍPIO SIAFI (auxilio-brasil)
        - MÊS COMPETÊNCIA / MÊS REFERÊNCIA (auxilio-brasil)
        - ANO, ID DO ACORDO, Código Apoiador, etc.
    """
    duck_type:   str = "BIGINT"
    polars_type: str = "Int64"


@dataclass
class IntegerField(Field):
    """
    INTEGER — aparece raramente.
    Encontrado em: DATA DA INFORMAÇÃO (acordos-leniencia).
    """
    duck_type:   str = "INTEGER"
    polars_type: str = "Int32"


@dataclass
class FloatField(Field):
    """
    DOUBLE — valores numéricos com casas decimais já convertidos.
    Raro na camada Bronze — bases governamentais geralmente entregam
    valores monetários como VARCHAR. Presente em alguns datasets do BNDES
    e Receita Federal.
    """
    duck_type:   str = "DOUBLE"
    polars_type: str = "Float64"


@dataclass
class BooleanField(Field):
    """
    BOOLEAN — flags binárias.
    Raro na camada Bronze. Aparece em alguns datasets como VARCHAR
    com valores 'S'/'N', 'Sim'/'Não', '0'/'1', 'true'/'false'.
    Silver deve normalizar para bool.
    """
    duck_type:   str = "BOOLEAN"
    polars_type: str = "Boolean"


@dataclass
class DateTimeField(Field):
    """
    TIMESTAMP — datas com hora.
    Encontrado em:
        - Data do Apoio (apoiamento-emendas-parlamentares-documentos)
        - Data Retirada do Apoio (idem)
    """
    duck_type:   str = "TIMESTAMP"
    polars_type: str = "Datetime"


# ─────────────────────────────────────────────────────────────────────────────
# CAMPOS DE PARTIÇÃO HIVE
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PartitionAnoField(BigIntField):
    """
    Partição 'ano' — vira segmento do path S3: /ano=2024/

    ⚠️ Em 'emendas-parlamentares': ano=unknown (dataset sem partição temporal).
    Tipo BIGINT na maioria; VARCHAR em emendas-parlamentares.
    """
    is_partition: bool = True
    description:  str  = "Partição ano — segmento do path S3"


@dataclass
class PartitionMesField(StringField):
    """
    Partição 'mes' — vira segmento do path S3: /mes=03/

    ⚠️ Pode ser 'unknown' para datasets com publicação apenas anual:
        viagens, receitas, orcamento-despesa, renuncias,
        emendas-parlamentares*, apoiamento-emendas-parlamentares-documentos
    """
    is_partition: bool = True
    description:  str  = "Partição mês — segmento do path S3. Pode ser 'unknown'."


@dataclass
class PartitionModuloField(StringField):
    """
    Partição 'modulo' — segmento do path S3: /modulo=bolsa-familia-pagamentos/
    Sempre VARCHAR. Vem no schema do parquet junto com as colunas de dados.
    """
    is_partition: bool = True
    description:  str  = "Partição módulo — segmento do path S3"


# ─────────────────────────────────────────────────────────────────────────────
# IDENTIFICADORES DE PESSOAS — chaves de correlação entre datasets
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CPFField(StringField):
    """
    CPF — Cadastro de Pessoas Físicas. String de 11 dígitos.
    Chave principal de correlação entre datasets de pessoas físicas.

    Aparece como:
        'CPF FAVORECIDO'          → bolsa-familia, auxilio-brasil, novo-bolsa-familia,
                                    seguro-defeso, auxilio-reconstrucao
        'CPF BENEFICIÁRIO'        → auxilio-emergencial, bpc, pe-de-meia
        'CPF RESPONSÁVEL'         → auxilio-emergencial, bpc, pe-de-meia
        'CPF PORTADOR'            → cpgf, cpdc
        'CPF'                     → servidores, pep, imoveis-funcionais
        'CPF viajante'            → viagens
        'CPF OU CNPJ DO SANCIONADO' → ceis, cnep, ceaf (compartilhado com CNPJ)

    Silver: normalizar todos para campo único 'cpf'.
    """
    is_join_key: bool = True
    description: str  = "CPF — 11 dígitos, chave de correlação PF"


@dataclass
class CNPJField(StringField):
    """
    CNPJ — Cadastro Nacional de Pessoas Jurídicas. String de 14 dígitos.
    Chave principal de correlação entre datasets de pessoas jurídicas.

    Aparece como:
        'CNPJ DO SANCIONADO'        → acordos-leniencia
        'CNPJ ENTIDADE'             → cepim
        'CNPJ'                      → favorecidos-pj, renuncias
        'CNPJ OU CPF FAVORECIDO'    → cpcc, cpgf, cpdc
        'CPF/CNPJ Emitente'         → notas-fiscais
        'CNPJ DESTINATÁRIO'         → notas-fiscais
        'CPF OU CNPJ DO SANCIONADO' → ceis, cnep, ceaf

    Silver: normalizar todos para campo único 'cnpj'.
    """
    is_join_key: bool = True
    description: str  = "CNPJ — 14 dígitos, chave de correlação PJ"


@dataclass
class CPFCNPJField(StringField):
    """
    Campo que pode ser CPF (11 dígitos) ou CNPJ (14 dígitos) no mesmo campo.
    Recorrente em bases governamentais.

    Aparece como:
        'CPF OU CNPJ DO SANCIONADO' → ceis, cnep, ceaf
        'CNPJ OU CPF FAVORECIDO'    → cpcc, cpgf, cpdc
        'CPF/CNPJ Emitente'         → notas-fiscais
        'CNPJ OU CPF FAVORECIDO'    → notas-fiscais

    Silver: separar em cpf e cnpj com base no tamanho após limpeza.
    """
    is_join_key: bool = True
    description: str  = "CPF ou CNPJ no mesmo campo — Silver separa pelo tamanho"


@dataclass
class NISField(BigIntField):
    """
    NIS (BIGINT) — Número de Identificação Social.
    Chave de correlação entre programas sociais.

    ⚠️ Inconsistência no S3:
        BIGINT em: auxilio-brasil, auxilio-emergencial
        VARCHAR em: bolsa-familia, novo-bolsa-familia, bpc, seguro-defeso, peti

    Silver: converter para VARCHAR em todos os casos.
    """
    is_join_key: bool = True
    description: str  = "NIS BIGINT — Silver converte para VARCHAR"


@dataclass
class NISVarcharField(StringField):
    """
    NIS (VARCHAR) — para os módulos onde o S3 armazena como string.
    Ver NISField para a variante BIGINT.
    """
    is_join_key: bool = True
    description: str  = "NIS VARCHAR"


@dataclass
class IdServidorField(StringField):
    """
    Id_SERVIDOR_PORTAL — identificador interno do servidor no Portal da Transparência.
    Presente em: servidores.
    Correlaciona registros do mesmo servidor ao longo do tempo.
    """
    is_join_key: bool = True
    description: str  = "ID interno do servidor no Portal da Transparência"


# ─────────────────────────────────────────────────────────────────────────────
# IDENTIFICADORES DE ÓRGÃOS E UNIDADES — estrutura SIAFI/SIAPE
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CodigoOrgaoSuperiorField(StringField):
    """
    Código do órgão superior na estrutura SIAFI.
    Ex: '26000' = Ministério da Educação.
    Presente em quase todos os módulos de despesa, cartão, transferências.
    """
    is_join_key: bool = True
    description: str  = "Código órgão superior SIAFI — chave de correlação entre módulos"


@dataclass
class CodigoOrgaoField(StringField):
    """
    Código do órgão subordinado na estrutura SIAFI.
    Nível abaixo do órgão superior.
    """
    is_join_key: bool = True
    description: str  = "Código órgão subordinado SIAFI"


@dataclass
class CodigoUGField(StringField):
    """
    Código da Unidade Gestora (UG) no SIAFI.
    Unidade orçamentária executora do gasto.
    Presente em: compras, licitacoes, cpgf, cpdc, cpcc, despesas-execucao.
    """
    is_join_key: bool = True
    description: str  = "Código Unidade Gestora SIAFI"


@dataclass
class CodigoUnidadeOrcamentariaField(StringField):
    """
    Código da Unidade Orçamentária — nível entre órgão e UG.
    Presente em: despesas-execucao, orcamento-despesa, emendas-parlamentares-documentos.
    """
    description: str = "Código Unidade Orçamentária SIAFI"


# ─────────────────────────────────────────────────────────────────────────────
# IDENTIFICADORES GEOGRÁFICOS — municípios e estados brasileiros
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class UFField(StringField):
    """
    UF — sigla de 2 letras do estado brasileiro.
    Presente em praticamente todos os datasets.
    Ex: 'SP', 'RJ', 'MG'.
    """
    description: str = "Sigla UF — 2 letras"


@dataclass
class CodigoMunicipioSIAFIField(StringField):
    """
    Código do município no SIAFI.

    ⚠️ Inconsistência no S3:
        VARCHAR em: bolsa-familia, novo-bolsa-familia, bpc, seguro-defeso
        BIGINT  em: auxilio-brasil, auxilio-reconstrucao

    Silver: normalizar para VARCHAR sempre.
    Diferente do código IBGE — não são intercambiáveis.
    """
    is_join_key: bool = True
    description: str  = "Código município SIAFI — Silver normaliza para VARCHAR"


@dataclass
class CodigoMunicipioIBGEField(StringField):
    """
    Código do município no IBGE — 7 dígitos.
    Presente em: auxilio-emergencial (como BIGINT), emendas-parlamentares-documentos.

    Silver: normalizar para VARCHAR com zero-fill até 7 dígitos.
    Chave de correlação com datasets do IBGE (censo, PIB municipal, etc.)
    """
    is_join_key: bool = True
    description: str  = "Código município IBGE 7 dígitos — chave com datasets IBGE"


@dataclass
class NomeMunicipioField(StringField):
    """
    Nome do município.
    ⚠️ Não usar como chave de join — grafias inconsistentes entre datasets.
    Usar CodigoMunicipioSIAFIField ou CodigoMunicipioIBGEField.
    """
    description: str = "Nome município — não usar como chave, grafias inconsistentes"


@dataclass
class CEPField(StringField):
    """
    CEP — Código de Endereçamento Postal. 8 dígitos.
    Presente em: favorecidos-pj.
    Silver: remover hífen se presente → '01310-100' → '01310100'.
    """
    description: str = "CEP 8 dígitos — Silver remove hífen"


# ─────────────────────────────────────────────────────────────────────────────
# IDENTIFICADORES ORÇAMENTÁRIOS — estrutura LOA/SIAFI
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CodigoFuncaoField(StringField):
    """
    Código da função orçamentária.
    Ex: '12' = Educação, '10' = Saúde, '08' = Assistência Social.
    Presente em: despesas-execucao, orcamento-despesa, emendas-parlamentares,
                 transferencias.
    """
    description: str = "Código função orçamentária LOA"


@dataclass
class CodigoSubfuncaoField(StringField):
    """
    Código da subfunção orçamentária.
    Detalhamento da função. Ex: '122' = Administração Geral.
    """
    description: str = "Código subfunção orçamentária LOA"


@dataclass
class CodigoProgramaField(StringField):
    """
    Código do programa orçamentário no PPA.
    Liga despesas ao planejamento plurianual do governo.
    """
    description: str = "Código programa orçamentário PPA"


@dataclass
class CodigoAcaoField(StringField):
    """
    Código da ação orçamentária.
    Nível mais granular da estrutura LOA.
    Presente em: despesas-execucao, orcamento-despesa, transferencias,
                 emendas-parlamentares-documentos.
    """
    description: str = "Código ação orçamentária LOA"


@dataclass
class CodigoElementoDespesaField(StringField):
    """
    Código do elemento de despesa — natureza do gasto.
    Ex: '33' = Passagens, '39' = Outros Serviços de Terceiros PJ.
    """
    description: str = "Código elemento de despesa"


@dataclass
class CodigoGrupoDespesaField(StringField):
    """
    Código do grupo de despesa.
    Ex: '1' = Pessoal, '3' = Outras Despesas Correntes, '4' = Investimentos.
    """
    description: str = "Código grupo de despesa"


@dataclass
class CodigoModalidadeAplicacaoField(StringField):
    """
    Código da modalidade de aplicação.
    Indica se o recurso é aplicado diretamente ou transferido.
    Ex: '90' = Aplicação Direta, '40' = Transferência a Municípios.
    """
    description: str = "Código modalidade de aplicação"


# ─────────────────────────────────────────────────────────────────────────────
# IDENTIFICADORES DE DOCUMENTOS E PROCESSOS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class NumeroProcessoField(StringField):
    """
    Número de processo administrativo.
    Formato variável entre órgãos.
    Presente em: acordos-leniencia, ceis, cnep, licitacoes.
    """
    description: str = "Número processo administrativo — formato variável"


@dataclass
class NumeroConvenioField(StringField):
    """
    Número do convênio federal.
    Chave de correlação entre convenios, cpdc e emendas-parlamentares-documentos.
    """
    is_join_key: bool = True
    description: str  = "Número convênio — chave entre convenios e cartões"


@dataclass
class NumeroLicitacaoField(StringField):
    """
    Número da licitação.
    Chave de correlação entre licitacoes e compras.
    """
    is_join_key: bool = True
    description: str  = "Número licitação — chave entre licitacoes e compras"


@dataclass
class NumeroContratoField(StringField):
    """
    Número do contrato.
    Presente em: compras.
    Chave futura com datasets de contratos do SIASG/ComprasNet.
    """
    is_join_key: bool = True
    description: str  = "Número contrato SIASG"


@dataclass
class ChaveNFeField(StringField):
    """
    Chave de acesso da NF-e — 44 dígitos.
    Presente em: notas-fiscais.
    Identificador único nacional de cada nota fiscal eletrônica.
    """
    is_join_key: bool = True
    description: str  = "Chave acesso NF-e 44 dígitos — identificador único"


@dataclass
class CodigoEmendaField(StringField):
    """
    Código da emenda parlamentar.
    Presente em: emendas-parlamentares, emendas-parlamentares-documentos,
                 apoiamento-emendas-parlamentares-documentos.
    Chave de correlação entre os três módulos de emendas.
    """
    is_join_key: bool = True
    description: str  = "Código emenda parlamentar — chave entre módulos de emendas"


@dataclass
class CodigoAutorEmendaField(StringField):
    """
    Código do autor da emenda parlamentar — identificador do parlamentar.
    Correlaciona com dados do TSE (candidatos, financiamento de campanha).
    """
    is_join_key: bool = True
    description: str  = "Código autor emenda — correlaciona com TSE"


# ─────────────────────────────────────────────────────────────────────────────
# CAMPOS DE CLASSIFICAÇÃO ECONÔMICA E EMPRESARIAL
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CNAEField(StringField):
    """
    CNAE — Classificação Nacional de Atividades Econômicas.
    Presente em: favorecidos-pj, renuncias.
    Chave de correlação com dados da Receita Federal (CNPJ aberto).
    Ex: '4711-3/01' = Comércio varejista de mercadorias em geral.
    """
    is_join_key: bool = True
    description: str  = "Código CNAE — correlaciona com Receita Federal"


@dataclass
class NaturezaJuridicaField(StringField):
    """
    Código de natureza jurídica.
    Presente em: favorecidos-pj (COD_NATJURIDICA).
    Classifica o tipo de empresa: SA, Ltda, MEI, ONG, etc.
    Ex: '2062' = Sociedade Empresária Limitada.
    """
    description: str = "Código natureza jurídica — tipo de empresa"


@dataclass
class NCMField(StringField):
    """
    NCM/SH — Nomenclatura Comum do Mercosul.
    Presente em: notas-fiscais (CÓDIGO NCM/SH).
    Classifica produtos em notas fiscais.
    Chave de correlação com tabelas de importação/exportação (MDIC/SECEX).
    """
    is_join_key: bool = True
    description: str  = "Código NCM/SH — correlaciona com MDIC/SECEX"


@dataclass
class CFOPField(StringField):
    """
    CFOP — Código Fiscal de Operações e Prestações.
    Presente em: notas-fiscais.
    Determina a natureza da operação fiscal.
    Ex: '6101' = Venda de produção do estabelecimento.
    """
    description: str = "Código CFOP — natureza da operação fiscal"


# ─────────────────────────────────────────────────────────────────────────────
# CAMPOS DE DATA — a maioria chega como VARCHAR no S3
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DateVarcharField(StringField):
    """
    Data armazenada como VARCHAR no S3 — padrão mais comum nas bases governamentais.

    Formatos encontrados (variam por órgão e dataset):
        'DD/MM/YYYY'  → Portal da Transparência (maioria)
        'YYYY-MM-DD'  → alguns datasets do SIAFI
        'MM/YYYY'     → datas de competência (MÊS COMPETÊNCIA)
        'YYYYMM'      → formato compacto (alguns datasets da CGU)

    Silver: normalizar para Date após detecção automática do formato.
    """
    description: str = "Data como VARCHAR — Silver normaliza para Date"


@dataclass
class AnoExercicioField(StringField):
    """
    Ano do exercício orçamentário — VARCHAR de 4 dígitos.
    Presente em: receitas (ANO EXERCÍCIO), cpcc (ANO EXTRATO), cpdc (ANO EXTRATO).
    Diferente da partição 'ano' — é uma coluna de dado, não de partição.
    """
    description: str = "Ano exercício orçamentário — coluna de dado, não partição"


# ─────────────────────────────────────────────────────────────────────────────
# CAMPOS DE VALOR MONETÁRIO
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class MoneyField(StringField):
    """
    Valores monetários — armazenados como VARCHAR no S3.

    Exemplos reais encontrados:
        'VALOR PARCELA', 'VALOR TRANSAÇÃO', 'VALOR TOTAL',
        'Valor Empenhado', 'Valor Pago', 'VALOR TRANSFERIDO',
        'VALOR CONVÊNIO', 'VALOR LIBERADO', 'VALOR CONTRAPARTIDA'

    ⚠️ Formatos inconsistentes entre datasets:
        '1.234,56'    → Portal da Transparência (ponto milhar, vírgula decimal)
        '1234.56'     → alguns datasets do BNDES
        '1234'        → valores inteiros sem centavos
        '-1.234,56'   → valores negativos (devoluções, cancelamentos)

    Silver: limpar e converter para Decimal(15,2).
    """
    description: str = "Valor monetário cru VARCHAR — Silver converte para Decimal"


@dataclass
class PercentualField(StringField):
    """
    Percentual armazenado como VARCHAR.
    Presente em: receitas (PERCENTUAL REALIZADO),
                 orcamento-despesa (% REALIZADO DO ORÇAMENTO).

    ⚠️ Pode vir como '95,23' ou '95.23' ou '95,23%'.
    Silver: remover '%' e normalizar para Float.
    """
    description: str = "Percentual VARCHAR — Silver normaliza para Float"


# ─────────────────────────────────────────────────────────────────────────────
# CAMPOS DE SANÇÃO E COMPLIANCE
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CodigoSancaoField(StringField):
    """
    Código da sanção aplicada.
    Presente em: ceis, cnep, ceaf.
    Identifica o tipo de penalidade dentro do cadastro.
    """
    description: str = "Código sanção — ceis, cnep, ceaf"


@dataclass
class TipoPessoaField(StringField):
    """
    Tipo de pessoa — 'F' (Física) ou 'J' (Jurídica).
    Presente em: ceis, cnep, ceaf, favorecidos-pj.
    Silver: usar para decidir se CPF ou CNPJ do campo CPFCNPJField.
    """
    description: str = "Tipo pessoa F/J — guia separação CPF/CNPJ na Silver"


@dataclass
class EsferaOrgaoField(StringField):
    """
    Esfera do órgão sancionador: Federal, Estadual, Municipal.
    Presente em: ceis, cnep, ceaf.
    """
    description: str = "Esfera órgão: Federal/Estadual/Municipal"


@dataclass
class FundamentacaoLegalField(StringField):
    """
    Fundamentação legal da sanção ou benefício.
    Presente em: ceis, cnep, ceaf, renuncias (Base Legal).
    Texto livre com artigos de lei.
    """
    description: str = "Fundamentação legal — texto livre com artigos de lei"


# ─────────────────────────────────────────────────────────────────────────────
# CAMPOS DE PROGRAMAS SOCIAIS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SituacaoBeneficioField(StringField):
    """
    Situação do benefício social.
    Presente em: peti (SITUAÇÃO BENEFÍCIO).
    Ex: 'Ativo', 'Suspenso', 'Cancelado', 'Bloqueado'.
    """
    description: str = "Situação do benefício — ativo/suspenso/cancelado"


@dataclass
class EnquadramentoField(StringField):
    """
    Enquadramento do beneficiário no programa social.
    Presente em: auxilio-emergencial (ENQUADRAMENTO).
    Ex: 'Trabalhador Informal', 'MEI', 'Desempregado'.
    """
    description: str = "Enquadramento beneficiário no programa"


@dataclass
class RGPField(StringField):
    """
    RGP — Registro Geral da Pesca.
    Presente em: seguro-defeso (RGP FAVORECIDO).
    Identifica pescadores artesanais no sistema federal.
    Chave de correlação futura com dados do MPA (Ministério da Pesca).
    """
    is_join_key: bool = True
    description: str  = "Registro Geral da Pesca — correlaciona com MPA"


@dataclass
class NumeroBeneficioField(StringField):
    """
    Número do benefício previdenciário/assistencial.
    Presente em: bpc (NÚMERO BENEFÍCIO).
    Identificador do benefício no INSS/DATAPREV.
    """
    is_join_key: bool = True
    description: str  = "Número benefício INSS/DATAPREV"


# ─────────────────────────────────────────────────────────────────────────────
# CAMPOS DE SERVIDORES E RECURSOS HUMANOS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CargoField(StringField):
    """
    Cargo efetivo do servidor.
    Presente em: imoveis-funcionais (Cargo ou Função), viagens (Cargo),
                 ceaf (CARGO EFETIVO).
    """
    description: str = "Cargo efetivo do servidor"


@dataclass
class FuncaoConfiancaField(StringField):
    """
    Função de confiança ou cargo em comissão (DAS, NES, etc.).
    Presente em: pep (Sigla_Função, Descrição_Função, Nível_Função),
                 ceaf (FUNÇÃO OU CARGO DE CONFIANÇA), viagens (Função).
    """
    description: str = "Função de confiança / cargo comissionado"


@dataclass
class OrgaoLotacaoField(StringField):
    """
    Órgão de lotação do servidor.
    Presente em: ceaf (ÓRGÃO DE LOTAÇÃO), imoveis-funcionais (Órgão Exercício).
    Diferente do órgão pagador — servidor pode estar cedido.
    """
    description: str = "Órgão de lotação — pode diferir do órgão pagador"


# ─────────────────────────────────────────────────────────────────────────────
# CAMPOS DE VIAGENS E DIÁRIAS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PCDPField(StringField):
    """
    PCDP — Proposta de Concessão de Diárias e Passagens.
    Presente em: viagens (Número da Proposta (PCDP)).
    Identificador único do processo de viagem no SCDP.
    """
    is_join_key: bool = True
    description: str  = "Número PCDP — identificador processo de viagem SCDP"


@dataclass
class JustificativaField(StringField):
    """
    Texto livre de justificativa.
    Presente em: viagens (Justificativa Urgência Viagem, Motivo).
    Conteúdo textual para NLP futuro.
    """
    description: str = "Texto livre de justificativa — candidato a NLP"


# ─────────────────────────────────────────────────────────────────────────────
# CAMPOS DE NOTAS FISCAIS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class InscricaoEstadualField(StringField):
    """
    Inscrição Estadual do emitente da NF-e.
    Presente em: notas-fiscais.
    Formato variável por estado.
    """
    description: str = "Inscrição estadual — formato variável por UF"


@dataclass
class IndicadorIEField(StringField):
    """
    Indicador de Inscrição Estadual do destinatário.
    Presente em: notas-fiscais (INDICADOR IE DESTINATÁRIO).
    Valores: '1' = Contribuinte, '2' = Isento, '9' = Não contribuinte.
    """
    description: str = "Indicador IE: 1=Contribuinte, 2=Isento, 9=Não contribuinte"


@dataclass
class ModeloDocFiscalField(StringField):
    """
    Modelo do documento fiscal.
    Presente em: notas-fiscais (MODELO).
    Ex: '55' = NF-e, '57' = CT-e, '65' = NFC-e.
    """
    description: str = "Modelo documento fiscal: 55=NF-e, 57=CT-e, 65=NFC-e"

@dataclass
class CodigoCategoriaDespesaField(StringField):
    """
    Código da categoria econômica da despesa.
    Nível mais alto da classificação da natureza de despesa na estrutura LOA/SIAFI.

    Valores possíveis:
        '3' = Despesas Correntes (pessoal, custeio, transferências)
        '4' = Despesas de Capital (investimentos, inversões, amortização)
        '9' = Reserva de Contingência

    Presente em: despesas-execucao, orcamento-despesa, emendas-parlamentares-documentos.

    Hierarquia completa da natureza de despesa:
        Categoria Econômica → Grupo → Modalidade de Aplicação → Elemento → SubElemento
    """
    description: str = "Código categoria econômica da despesa: 3=Correntes, 4=Capital, 9=Reserva"


@dataclass
class CodigoSubElementoDespesaField(StringField):
    """
    Código do subelemento de despesa — detalhamento do elemento de despesa.
    Nível mais granular da classificação da natureza de despesa no SIAFI.

    Presente em: despesas-execucao (quando disponível), notas de empenho detalhadas.

    ⚠️ Nem todos os órgãos utilizam o subelemento — campo frequentemente nulo
    ou preenchido com '00' (sem desdobramento). Silver deve tratar '00' como ausente.

    Hierarquia completa da natureza de despesa:
        Categoria Econômica → Grupo → Modalidade de Aplicação → Elemento → SubElemento
    """
    description: str = "Código subelemento de despesa — nível mais granular do SIAFI; '00' = sem desdobramento"
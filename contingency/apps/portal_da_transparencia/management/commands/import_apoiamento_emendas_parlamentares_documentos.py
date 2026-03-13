from apps.datalake.management.commands._base_import import BaseImportCommand
from apps.portal_da_transparencia.models.apoiamento_emendas_parlamentares_documentos import ApoiamentoEmendasParlamentaresDocumentos
from apps.portal_da_transparencia.models.silver import ApoiamentoEmendasParlamentaresDocumentosRecord


class Command(BaseImportCommand):
    help = "Importa N registros de Apoiamento em Emendas Parlamentares - Documentos (S3) para o banco Django"

    duckdb_model = ApoiamentoEmendasParlamentaresDocumentos
    django_model = ApoiamentoEmendasParlamentaresDocumentosRecord
    default_ano  = "2024"
    default_mes  = "01"

    field_map = {
        "Código Apoiador":                          "codigo_apoiador",
        "Apoiador":                                 "apoiador",
        "Data do Apoio":                            "data_apoio",
        "Data Retirada do Apoio":                   "data_retirada_apoio",
        "Empenho":                                  "empenho",
        "Data última movimentação Empenho":         "data_ultima_movimentacao_empenho",
        "Código favorecido":                        "codigo_favorecido",
        "Favorecido":                               "favorecido",
        "Tipo Favorecido":                          "tipo_favorecido",
        "UF Favorecido":                            "uf_favorecido",
        "Município Favorecido":                     "municipio_favorecido",
        "Código da Emenda":                         "codigo_da_emenda",
        "Tipo de Emenda":                           "tipo_de_emenda",
        "Ano da Emenda":                            "ano_da_emenda",
        "Código do Autor da Emenda":                "codigo_do_autor_da_emenda",
        "Nome do Autor da Emenda":                  "nome_do_autor_da_emenda",
        "Número da emenda":                         "numero_da_emenda",
        "Localidade de aplicação do recurso":       "localidade_de_aplicacao_do_recurso",
        "Código UG":                                "codigo_ug",
        "UG":                                       "ug",
        "Código Unidade Orçamentária":              "codigo_unidade_orcamentaria",
        "Unidade Orçamentária":                     "unidade_orcamentaria",
        "Código Órgão SIAFI":                       "codigo_orgao_siafi",
        "Órgão":                                    "orgao",
        "Código Órgão Superior SIAFI":              "codigo_orgao_superior_siafi",
        "Órgão Superior":                           "orgao_superior",
        "Código Ação":                              "codigo_acao",
        "Ação":                                     "acao",
        "Valor Empenhado":                          "valor_empenhado",
        "Valor Cancelado":                          "valor_cancelado",
        "Valor Pago":                               "valor_pago",
    }

from apps.datalake.management.commands._base_import import BaseImportCommand
from apps.portal_da_transparencia.models.pgd import PGD
from apps.portal_da_transparencia.models.silver import PGDRecord


class Command(BaseImportCommand):
    help = "Importa N registros de PGD (S3) para o banco Django"

    duckdb_model = PGD
    django_model = PGDRecord
    default_ano  = "2022"
    default_mes  = "05"

    field_map = {
        "Código Órgão Superior":                   "codigo_orgao_superior",
        "Órgão Superior":                           "orgao_superior",
        "Código Órgão":                            "codigo_orgao",
        "Órgão":                                    "orgao",
        "Código Unidade Gestora":                  "codigo_unidade_gestora",
        "Unidade Gestora":                          "unidade_gestora",
        "Código Categoria de Despesa":              "codigo_categoria_despesa",
        "Categoria de Despesa":                     "categoria_despesa",
        "Código Grupo de Despesa":                  "codigo_grupo_despesa",
        "Grupo de Despesa":                         "grupo_despesa",
        "Código Modalidade de Aplicação":           "codigo_modalidade_aplicacao",
        "Modalidade de Aplicação":                  "modalidade_aplicacao",
        "Código Elemento de Despesa":               "codigo_elemento_despesa",
        "Elemento de Despesa":                      "elemento_despesa",
        "Código SubElemento de Despesa":            "codigo_subelemento_despesa",
        "SubElemento de Despesa":                   "subelemento_despesa",
        "Descrição":                                "descricao",
        "Quantidade":                               "quantidade",
        "Valor Unitário":                           "valor_unitario",
        "Valor Total":                              "valor_total",
        "Data Emissão":                             "data_emissao",
        "Código Tipo Documento":                    "codigo_tipo_documento",
        "Tipo Documento":                           "tipo_documento",
        "Tipo OB":                                  "tipo_ob",
        "Extraorçamentário":                        "extraorcamentario",
    }

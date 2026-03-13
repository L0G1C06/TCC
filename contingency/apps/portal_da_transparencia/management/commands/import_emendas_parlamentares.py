from apps.datalake.management.commands._base_import import BaseImportCommand
from apps.portal_da_transparencia.models.emendas_parlamentares import EmendasParlamentares
from apps.portal_da_transparencia.models.silver import EmendasParlamentaresRecord


class Command(BaseImportCommand):
    help = "Importa N registros de Emendas Parlamentares (S3) para o banco Django"

    duckdb_model = EmendasParlamentares
    django_model = EmendasParlamentaresRecord
    default_ano  = "2022"
    default_mes  = "05"

    field_map = {
        "Código da Emenda":                         "codigo_da_emenda",
        "Número da emenda":                         "numero_da_emenda",
        "Tipo de Emenda":                           "tipo_de_emenda",
        "Código do Autor":                          "codigo_do_autor",
        "Nome do Autor":                            "nome_do_autor",
        "Sigla do Partido":                         "sigla_do_partido",
        "UF do Autor":                              "uf_do_autor",
        "Valor da Emenda":                          "valor_da_emenda",
        "Valor Empenhado":                          "valor_empenhado",
        "Valor Pago":                               "valor_pago",
        "Situação da Emenda":                       "situacao_da_emenda",
        "Localidade de Aplicação":                  "localidade_de_aplicacao",
        "Código Município SIAFI":                   "codigo_municipio_siafi",
        "Nome Município":                           "nome_municipio",
        "UF Município":                             "uf_municipio",
        "Código Função":                            "codigo_funcao",
        "Função":                                   "funcao",
        "Código Subfunção":                         "codigo_subfuncao",
        "Subfunção":                                "subfuncao",
        "Código Programa":                          "codigo_programa",
        "Programa":                                 "programa",
        "Código Ação":                              "codigo_acao",
        "Ação":                                     "acao",
    }

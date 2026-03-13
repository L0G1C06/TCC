from apps.datalake.management.commands._base_import import BaseImportCommand
from apps.portal_da_transparencia.models.cnep import CNEP
from apps.portal_da_transparencia.models.silver import CNEPRecord


class Command(BaseImportCommand):
    help = "Importa N registros de CNEP (S3) para o banco Django"

    duckdb_model = CNEP
    django_model = CNEPRecord
    default_ano  = "2026"
    default_mes  = "03"

    field_map = {
        "CADASTRO":                                "cadastro",
        "CÓDIGO DA SANÇÃO":                        "codigo_sancao",
        "TIPO DE PESSOA":                          "tipo_de_pessoa",
        "CPF OU CNPJ DO SANCIONADO":               "cpf_ou_cnpj_do_sancionado",
        "NOME DO SANCIONADO":                      "nome_do_sancionado",
        "NOME INFORMADO PELO ÓRGÃO SANCIONADOR":   "nome_informado_pelo_orgao",
        "RAZÃO SOCIAL - CADASTRO RECEITA":         "razao_social_receita",
        "NOME FANTASIA - CADASTRO RECEITA":        "nome_fantasia_receita",
        "NÚMERO DO PROCESSO":                      "numero_do_processo",
        "CATEGORIA DA SANÇÃO":                     "categoria_sancao",
        "VALOR DA MULTA":                          "valor_multa",
        "DATA INÍCIO SANÇÃO":                      "data_inicio_sancao",
        "DATA FINAL SANÇÃO":                       "data_final_sancao",
        "DATA PUBLICAÇÃO":                         "data_publicacao",
        "PUBLICAÇÃO":                              "publicacao",
        "DETALHAMENTO DO MEIO DE PUBLICAÇÃO":      "detalhamento_meio_publicacao",
        "DATA DO TRÂNSITO EM JULGADO":             "data_transito_em_julgado",
        "ABRAGÊNCIA DA SANÇÃO":                    "abrangencia_sancao",
        "ÓRGÃO SANCIONADOR":                       "orgao_sancionador",
        "UF ÓRGÃO SANCIONADOR":                    "uf_orgao_sancionador",
        "ESFERA ÓRGÃO SANCIONADOR":                "esfera_orgao_sancionador",
        "FUNDAMENTAÇÃO LEGAL":                     "fundamentacao_legal",
        "DATA ORIGEM INFORMAÇÃO":                  "data_origem_informacao",
        "ORIGEM INFORMAÇÕES":                      "origem_informacoes",
        "OBSERVAÇÕES":                             "observacoes",
    }

from apps.datalake.management.commands._base_import import BaseImportCommand
from apps.portal_da_transparencia.models.ceaf import CEAF
from apps.portal_da_transparencia.models.silver import CEAFRecord


class Command(BaseImportCommand):
    help = "Importa N registros de CEAF (S3) para o banco Django"

    duckdb_model = CEAF
    django_model = CEAFRecord
    default_ano  = "2026"
    default_mes  = "03"

    field_map = {
        "CADASTRO":                                "cadastro",
        "CÓDIGO DA SANÇÃO":                        "codigo_sancao",
        "TIPO DE PESSOA":                          "tipo_de_pessoa",
        "CPF OU CNPJ DO SANCIONADO":               "cpf_ou_cnpj_do_sancionado",
        "NOME DO SANCIONADO":                      "nome_do_sancionado",
        "CATEGORIA DA SANÇÃO":                     "categoria_sancao",
        "NÚMERO DO DOCUMENTO":                     "numero_do_documento",
        "NÚMERO DO PROCESSO":                      "numero_do_processo",
        "DATA INÍCIO SANÇÃO":                      "data_inicio_sancao",
        "DATA FINAL SANÇÃO":                       "data_final_sancao",
        "DATA PUBLICAÇÃO":                         "data_publicacao",
        "PUBLICAÇÃO":                              "publicacao",
        "DETALHAMENTO  DO MEIO DE PUBLICAÇÃO":     "detalhamento_meio_publicacao",
        "DATA DO TRÂNSITO EM JULGADO":             "data_transito_em_julgado",
        "ABRAGÊNCIA DA SANÇÃO":                    "abrangencia_sancao",
        "CARGO EFETIVO":                           "cargo_efetivo",
        "FUNÇÃO OU CARGO DE CONFIANÇA":            "funcao_ou_cargo_de_confianca",
        "ÓRGÃO DE LOTAÇÃO":                        "orgao_lotacao",
        "ÓRGÃO SANCIONADOR":                       "orgao_sancionador",
        "UF ÓRGÃO SANCIONADOR":                    "uf_orgao_sancionador",
        "ESFERA ÓRGÃO SANCIONADOR":                "esfera_orgao_sancionador",
        "FUNDAMENTAÇÃO LEGAL":                     "fundamentacao_legal",
        "DATA ORIGEM INFORMAÇÃO":                  "data_origem_informacao",
        "ORIGEM INFORMAÇÕES":                      "origem_informacoes",
        "OBSERVAÇÕES":                             "observacoes",
    }

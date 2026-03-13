from apps.datalake.management.commands._base_import import BaseImportCommand
from apps.portal_da_transparencia.models.convenios import Convenios
from apps.portal_da_transparencia.models.silver import ConveniosRecord


class Command(BaseImportCommand):
    help = "Importa N registros de Convênios (S3) para o banco Django"

    duckdb_model = Convenios
    django_model = ConveniosRecord
    default_ano  = "2026"
    default_mes  = "02"

    field_map = {
        "NÚMERO CONVÊNIO":                          "numero_convenio",
        "NÚMERO ORIGINAL":                          "numero_original",
        "DATA EMISSÃO OB":                          "data_emissao_ob",
        "NÚMERO DA ORDEM BANCÁRIA":                "numero_ordem_bancaria",
        "VALOR LIBERADO":                           "valor_liberado",
        "UF":                                       "uf",
        "CÓDIGO SIAFI MUNICÍPIO":                  "codigo_siafi_municipio",
        "NOME MUNICÍPIO":                           "nome_municipio",
        "SITUAÇÃO CONVÊNIO":                        "situacao_convenio",
        "NÚMERO PROCESSO DO CONVÊNIO":             "numero_processo_convenio",
        "OBJETO DO CONVÊNIO":                       "objeto_convenio",
        "CÓDIGO ÓRGÃO SUPERIOR":                   "codigo_orgao_superior",
        "NOME ÓRGÃO SUPERIOR":                     "nome_orgao_superior",
        "CÓDIGO ÓRGÃO CONCEDENTE":                 "codigo_orgao_concedente",
        "NOME ÓRGÃO CONCEDENTE":                   "nome_orgao_concedente",
        "CÓDIGO UG CONCEDENTE":                    "codigo_ug_concedente",
        "NOME UG CONCEDENTE":                      "nome_ug_concedente",
        "CÓDIGO CONVENENTE":                       "codigo_convenente",
        "TIPO CONVENENTE":                         "tipo_convenente",
        "NOME CONVENENTE":                         "nome_convenente",
        "TIPO ENTE CONVENENTE":                    "tipo_ente_convenente",
        "TIPO INSTRUMENTO":                        "tipo_instrumento",
        "VALOR CONVÊNIO":                           "valor_convenio",
        "DATA PUBLICAÇÃO":                         "data_publicacao",
        "DATA INÍCIO VIGÊNCIA":                    "data_inicio_vigencia",
        "DATA FINAL VIGÊNCIA":                     "data_final_vigencia",
        "VALOR CONTRAPARTIDA":                     "valor_contrapartida",
        "DATA ÚLTIMA LIBERAÇÃO":                   "data_ultima_liberacao",
        "VALOR ÚLTIMA LIBERAÇÃO":                  "valor_ultima_liberacao",
    }

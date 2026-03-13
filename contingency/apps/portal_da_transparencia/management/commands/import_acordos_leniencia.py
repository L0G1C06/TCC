from apps.datalake.management.commands._base_import import BaseImportCommand
from apps.portal_da_transparencia.models.acordos_leniencia import AcordosLeniencia
from apps.portal_da_transparencia.models.silver import AcordosLenienciaRecord


class Command(BaseImportCommand):
    help = "Importa N registros de Acordos de Leniência (S3) para o banco Django"

    duckdb_model = AcordosLeniencia
    django_model = AcordosLenienciaRecord
    default_ano  = "2026"
    default_mes  = "03"

    field_map = {
        "ID DO ACORDO":                             "id_do_acordo",
        "EFEITO DO ACORDO DE LENIENCIA":            "efeito_do_acordo",
        "COMPLEMENTO":                              "complemento",
        "CNPJ DO SANCIONADO":                       "cnpj_do_sancionado",
        "RAZÃO SOCIAL – CADASTRO RECEITA":          "razao_social_receita",
        "NOME FANTASIA – CADASTRO RECEITA":         "nome_fantasia_receita",
        "DATA DE INÍCIO DO ACORDO":                 "data_inicio_acordo",
        "DATA DE FIM DO ACORDO":                    "data_fim_acordo",
        "SITUAÇÃO DO ACORDO DE LENIÊNCIA":          "situacao_acordo",
        "DATA DA INFORMAÇÃO":                       "data_informacao",
        "NÚMERO DO PROCESSO":                       "numero_do_processo",
        "TERMOS DO ACORDO":                         "termos_do_acordo",
        "ÓRGÃO SANCIONADOR":                        "orgao_sancionador",
    }

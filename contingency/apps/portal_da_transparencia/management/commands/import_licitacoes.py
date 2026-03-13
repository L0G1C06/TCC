from apps.datalake.management.commands._base_import import BaseImportCommand
from apps.portal_da_transparencia.models.licitacoes import Licitacoes
from apps.portal_da_transparencia.models.silver import LicitacoesRecord


class Command(BaseImportCommand):
    help = "Importa N registros de Licitações (S3) para o banco Django"

    duckdb_model = Licitacoes
    django_model = LicitacoesRecord
    default_ano  = "2024"
    default_mes  = "01"

    field_map = {
        "Número Licitação":                         "numero_licitacao",
        "Número Processo":                          "numero_processo",
        "Código Modalidade Compra":                 "codigo_modalidade_compra",
        "Modalidade Compra":                        "modalidade_compra",
        "Código Órgão":                             "codigo_orgao",
        "Nome Órgão":                               "nome_orgao",
        "Código UG":                                "codigo_ug",
        "Nome UG":                                  "nome_ug",
        "Código Item Compra":                       "codigo_item_compra",
        "Descrição Item Compra":                    "descricao_item_compra",
        "Código Participante":                      "codigo_participante",
        "Nome Participante":                        "nome_participante",
        "Flag Vencedor":                            "flag_vencedor",
    }

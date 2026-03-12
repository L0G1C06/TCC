from apps.datalake.management.commands._base_import import BaseImportCommand
from apps.portal_da_transparencia.models.compras import Compras
from apps.portal_da_transparencia.models.silver import ComprasRecord


class Command(BaseImportCommand):
    help = "Importa N registros de Compras (S3) para o banco Django"

    duckdb_model = Compras
    django_model = ComprasRecord
    default_ano  = "2024"
    default_mes  = "01"

    field_map = {
        "Código Órgão":                             "codigo_orgao",
        "Nome Órgão":                               "nome_orgao",
        "Código UG":                                "codigo_ug",
        "Nome UG":                                  "nome_ug",
        "Número Contrato":                          "numero_contrato",
        "Código Item Compra":                       "codigo_item_compra",
        "Descrição Item Compra":                    "descricao_item_compra",
        "Descrição Complementar Item Compra":       "descricao_complementar_item_compra",
        "Quantidade Item":                          "quantidade_item",
        "Valor Item":                               "valor_item",
    }

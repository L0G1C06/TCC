# apps/datalake/management/commands/inspect_bronze.py

from django.core.management.base import BaseCommand
from apps.datalake.layers.bronze_inspector import BronzeInspector
from apps.datalake.layers.bronze_generator import generate_model_code

DATASETS = {
    "portal_transparencia": "portal_da_transparencia/parquet/",
    "bndes":                "bndes/parquet/",
    # adicione quantos quiser
}

class Command(BaseCommand):
    help = "Inspeciona os datasets Bronze no S3 e gera os models"

    def add_arguments(self, parser):
        parser.add_argument(
            "--generate",
            action="store_true",
            help="Gera o código Python dos models além de inspecionar",
        )
        parser.add_argument(
            "--dataset",
            type=str,
            help="Inspeciona só um dataset específico",
        )

    def handle(self, *args, **options):
        inspector = BronzeInspector()
        target    = options.get("dataset")
        datasets  = (
            {target: DATASETS[target]}
            if target and target in DATASETS
            else DATASETS
        )

        result = inspector.inspect_all(datasets)

        for app_name, schemas in result.items():
            for schema in schemas:
                # imprime o schema estruturado
                self.stdout.write(str(schema))

                if options["generate"]:
                    code = generate_model_code(schema, app_name)
                    self.stdout.write("\n" + "─" * 60)
                    self.stdout.write(code)
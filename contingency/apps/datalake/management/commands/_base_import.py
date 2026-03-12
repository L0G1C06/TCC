"""
Base reutilizável para importar qualquer DuckDB model para o banco Django.

Uso (herdar em cada command específico):

    from apps.datalake.management.commands._base_import import BaseImportCommand

    class Command(BaseImportCommand):
        duckdb_model   = CPGF
        django_model   = CPGFRecord
        default_ano    = "2024"
        default_mes    = "01"
        field_map      = {
            "NOME ORIGINAL NO PARQUET": "campo_django",
            ...
        }
"""

from django.core.management.base import BaseCommand


class BaseImportCommand(BaseCommand):
    duckdb_model = None
    django_model = None
    default_ano  = "2024"
    default_mes  = "01"
    field_map: dict = {}

    def add_arguments(self, parser):
        parser.add_argument("--ano",   default=self.default_ano)
        parser.add_argument("--mes",   default=self.default_mes)
        parser.add_argument("--limit", default=30, type=int)
        parser.add_argument("--reset", action="store_true")

    def _read_data(self, ano, mes, limit):
        """Leitura padrão — sobrescrever em datasets sem partição de mês."""
        return self.duckdb_model.polars(ano=ano, mes=mes).limit(limit).collect()

    def handle(self, *args, **options):
        ano   = options["ano"]
        mes   = options["mes"]
        limit = options["limit"]
        label = self.duckdb_model.__name__

        if options["reset"]:
            deleted, _ = self.django_model.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"🗑️  {deleted} registros de {label} apagados."))

        self.stdout.write(f"🔍 Lendo {limit} registros de {label} (ano={ano}, mes={mes})...")

        try:
            df = self._read_data(ano, mes, limit)  # ← usa o método sobrescrito se existir
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"❌ Erro ao ler S3: {e}"))
            return

        self.stdout.write(f"✅ {len(df)} registros lidos. Salvando no banco...")

        records = []
        for row in df.iter_rows(named=True):
            fields = {
                django_field: row.get(source_col)
                for source_col, django_field in self.field_map.items()
            }
            records.append(self.django_model(**fields))

        self.django_model.objects.bulk_create(records)

        self.stdout.write(self.style.SUCCESS(
            f"🎉 {len(records)} registros de {label} salvos "
            f"em '{self.django_model._meta.db_table}'."
        ))
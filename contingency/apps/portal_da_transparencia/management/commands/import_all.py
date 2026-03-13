# management/commands/import_all.py
from django.core.management.base import BaseCommand
from django.core.management import call_command
from pathlib import Path


class Command(BaseCommand):
    help = "Roda todos os commands import_* desta pasta em sequência"

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip",
            nargs="*",
            default=[],
            help="Commands a pular. Ex: --skip import_bpc import_ceis",
        )

    def handle(self, *args, **options):
        commands_dir = Path(__file__).parent
        skip = set(options["skip"])

        commands = sorted(
            p.stem
            for p in commands_dir.glob("import_*.py")
            if p.stem not in skip
        )

        self.stdout.write(f"Encontrados {len(commands)} commands\n")

        for cmd in commands:
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n▶ {cmd}"))
            try:
                call_command(cmd)
                self.stdout.write(self.style.SUCCESS(f"✔ {cmd}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"✘ {cmd}: {e}"))
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "DEV ONLY - migrate the django SQL DB (users, sessions...), then flush all its data."

    def add_arguments(self, parser):
        parser.add_argument("--noinput", "--no-input", action="store_false", dest="interactive", help="no confirmation")

    def handle(self, *args, interactive, **options):
        if not settings.DEBUG:
            raise CommandError("Can't reset django DB in non-DEBUG mode")
        call_command("migrate", interactive=False)
        call_command("flush", interactive=interactive)  # flush asks for confirmation itself

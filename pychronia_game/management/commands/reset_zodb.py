import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "DEV ONLY - wipe the whole ZODB (all game instances), then create a fresh 'DEMO' game instance."

    def add_arguments(self, parser):
        parser.add_argument("--noinput", "--no-input", action="store_false", dest="interactive", help="no confirmation")
        parser.add_argument(
            "--use-fixture",
            action="store_true",
            help='load "scenario_fixtures/_PROD_DUMP.yaml" of GAME_FILES_ROOT, without initializations/randomizations',
        )

    def handle(self, *args, use_fixture, interactive, **options):
        if not settings.DEBUG:
            raise CommandError("Can't reset ZODB in non-DEBUG mode")
        target = settings.ZODB_URL or settings.ZODB_FILE
        if interactive:
            answer = input(
                "This will DELETE ALL GAME INSTANCES of the ZODB %r (settings %s).\nType 'yes' to continue: "
                % (target, os.environ.get("DJANGO_SETTINGS_MODULE"))
            )
            if answer != "yes":
                raise CommandError("ZODB reset cancelled")

        from pychronia_game.datamanager.datamanager_administrator import create_game_instance, reset_zodb_structure

        if settings.ZODB_FILE and os.path.exists(settings.ZODB_FILE):
            os.remove(settings.ZODB_FILE)

        reset_zodb_structure()

        if use_fixture:
            yaml_fixture = os.path.join(settings.GAME_FILES_ROOT, "scenario_fixtures", "_PROD_DUMP.yaml")
        else:
            yaml_fixture = None
        create_game_instance(
            game_instance_id="DEMO",
            creator_login="ze_creator",
            skip_initializations=use_fixture,
            yaml_fixture=yaml_fixture,
            skip_randomizations=use_fixture,
        )
        self.stdout.write(self.style.SUCCESS("ZODB reset, game instance 'DEMO' created"))

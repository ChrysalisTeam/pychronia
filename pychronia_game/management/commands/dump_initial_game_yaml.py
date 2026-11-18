from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Dump the initial data of a new game instance to a YAML file "
        "(eg. for murder-party sheet generators, which reuse encyclopedia articles, text messages, objects...)."
    )

    def add_arguments(self, parser):
        parser.add_argument("output_file", nargs="?", default="initial_data_dump.yaml")
        parser.add_argument("--language", help="eg. 'en', defaults to GAME_DEFAULT_LANGUAGE setting")
        parser.add_argument("--scenario", help="key of GAME_SCENARIOS setting, defaults to the default scenario")

    def handle(self, *args, output_file, language, scenario, **options):
        from pychronia_game.scripts import dump_initial_game_yaml

        dump_initial_game_yaml.execute(output_file, game_language=language, game_scenario=scenario)

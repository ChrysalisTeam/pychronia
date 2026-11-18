from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Extract all dispatched messages of a game instance, as reusable message templates in a YAML file."

    def add_arguments(self, parser):
        parser.add_argument("game_instance_id")

    def handle(self, *args, game_instance_id, **options):
        from pychronia_game.scripts import extract_reusable_bits_from_game

        extract_reusable_bits_from_game.execute(game_instance_id)

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Save a backup (in ZODB) of the data of each game instance."

    def handle(self, *args, **options):
        from pychronia_game.scripts import backup_all_games

        count = backup_all_games.execute()
        self.stdout.write(self.style.SUCCESS("%s game instances were autosaved" % count))

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Check the data coherence of each game instance (errors are logged)."

    def handle(self, *args, **options):
        from pychronia_game.scripts import check_global_sanity

        count, success = check_global_sanity.execute()
        if not success:
            raise CommandError("Some of the %s game instances are incoherent, see logs" % count)
        self.stdout.write(self.style.SUCCESS("All %s game instances are coherent" % count))

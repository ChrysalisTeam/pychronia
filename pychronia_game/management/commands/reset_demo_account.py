from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Delete the 'DEMO' game instance (if any), and recreate it from scratch."

    def handle(self, *args, **options):
        from pychronia_game.scripts import reset_demo_account

        reset_demo_account.execute()
        self.stdout.write(self.style.SUCCESS("Game instance '%s' recreated" % reset_demo_account.DEMO_NAME))

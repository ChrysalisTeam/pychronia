from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Email players of active game instances about their new radio playlist items and text messages."

    def handle(self, *args, **options):
        from pychronia_game.scripts import notify_novelties_by_email

        notify_novelties_by_email.execute()

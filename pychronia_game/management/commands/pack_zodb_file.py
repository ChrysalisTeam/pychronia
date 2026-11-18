from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Pack the local ZODB file (ZODB_FILE setting), in case it gets too heavy - the server must not be running. "
        "For a RelStorage ZODB (ZODB_URL setting), use relstorage's zodbpack instead."
    )

    def handle(self, *args, **options):
        from pychronia_game import utilities

        if not utilities.config.ZODB_FILE:
            raise CommandError("No ZODB_FILE setting, this command only works with a local ZODB file")
        db = utilities.open_zodb_file(utilities.config.ZODB_FILE)
        db.pack(days=1)
        self.stdout.write(
            self.style.SUCCESS("Successfully packed ZODB items older than 1 day in %s" % utilities.config.ZODB_FILE)
        )

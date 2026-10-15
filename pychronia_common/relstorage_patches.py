# -*- coding: utf-8 -*-
"""
Compatibility patches for running RelStorage (MySQL adapter) on a MariaDB server.

RelStorage only supports MySQL, and picks SQL dialect features by comparing the
server version against MySQL version numbers. MariaDB reports versions >= 10,
so it is wrongly assumed to support MySQL 8.0.19's row alias syntax for upserts
(``INSERT ... VALUES (...) AS excluded ON DUPLICATE KEY UPDATE col = excluded.col``),
which MariaDB doesn't implement (https://jira.mariadb.org/browse/MDEV-29919):
every commit then fails with a SQL syntax error (packing isn't affected).

Besides, creating a fresh schema fails on MariaDB >= 10.5, which (unlike MySQL)
enforces inline column ``REFERENCES`` clauses: those of "object_state" point
BIGINT columns at the BIGINT UNSIGNED "transaction.tid", hence a malformed
foreign key error. Like MySQL, we just ignore these inline clauses.
"""

import re

from relstorage.adapters.mysql.schema import MySQLSchemaInstaller, MySQLVersionDetector


def _is_mariadb(version_detector, cursor):
    return "mariadb" in version_detector.get_version(cursor).lower()


def apply_mariadb_patches():
    if getattr(MySQLVersionDetector, "_pychronia_mariadb_patched", False):
        return

    original_requires_values_upsert_alias = MySQLVersionDetector.requires_values_upsert_alias

    def requires_values_upsert_alias(self, cursor):
        if _is_mariadb(self, cursor):
            return False  # fall back to "col = VALUES(col)", which MariaDB supports
        return original_requires_values_upsert_alias(self, cursor)

    MySQLVersionDetector.requires_values_upsert_alias = requires_values_upsert_alias

    original_create_object_state = MySQLSchemaInstaller._create_object_state

    def _create_object_state(self, cursor):
        if not _is_mariadb(self.version_detector, cursor):
            return original_create_object_state(self, cursor)
        script = re.sub(r'\s+REFERENCES "transaction"', '', self.CREATE_OBJECT_STATE_TMPL)
        self.runner.run_script(cursor, script)

    MySQLSchemaInstaller._create_object_state = _create_object_state

    MySQLVersionDetector._pychronia_mariadb_patched = True

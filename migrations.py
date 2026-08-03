"""
PostgreSQL migration stub.
Schema creation and idempotent DDL are handled in `db.init_db()`.
"""

import logging

logger = logging.getLogger(__name__)


def run_all_migrations():
    """No-op: PostgreSQL schema is initialized from db.init_db()."""
    logger.info("PostgreSQL mode: run_all_migrations() skipped (handled by db.init_db)")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run_all_migrations()
    print("PostgreSQL mode: no standalone migrations to run.")

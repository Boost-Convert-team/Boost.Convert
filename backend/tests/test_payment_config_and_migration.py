import sys
import tempfile
import unittest
from pathlib import Path

from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from flask import Flask
from flask_migrate import Migrate, downgrade, upgrade
from sqlalchemy import inspect


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from config import validate_mercado_pago_config
from extensions import db
import models  # noqa: F401 - registers the complete migration metadata


class PaymentConfigAndMigrationTests(unittest.TestCase):
    def test_payment_migration_is_the_single_head_after_c4(self) -> None:
        config = AlembicConfig(str(BACKEND_ROOT / "migrations" / "alembic.ini"))
        config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
        script = ScriptDirectory.from_config(config)
        self.assertEqual(script.get_heads(), ["e2f7a9c4d1b6"])
        self.assertEqual(script.get_revision("e2f7a9c4d1b6").down_revision, "c4a8e2f1b7d9")

    def test_payment_migration_upgrades_and_downgrades_isolated_database(self) -> None:
        migrations_path = BACKEND_ROOT / "migrations"
        with tempfile.TemporaryDirectory(prefix="boost-migration-test-") as directory:
            database_path = Path(directory) / "migration.sqlite"
            app = Flask("migration")
            app.config.update(
                SQLALCHEMY_DATABASE_URI=f"sqlite:///{database_path.as_posix()}",
                SQLALCHEMY_TRACK_MODIFICATIONS=False,
            )
            db.init_app(app)
            Migrate(app, db, directory=str(migrations_path))
            with app.app_context():
                upgrade(directory=str(migrations_path))
                inspector = inspect(db.engine)
                column_details = {
                    column["name"]: column for column in inspector.get_columns("payments")
                }
                columns = set(column_details)
                self.assertTrue(
                    {"attempt_id", "provider_payment_method_id", "payment_type", "last_provider_sync_at"}
                    <= columns
                )
                self.assertFalse(column_details["attempt_id"]["nullable"])
                constraint_names = {
                    constraint["name"]
                    for constraint in inspector.get_unique_constraints("payments")
                }
                self.assertIn("uq_payments_provider_attempt_id", constraint_names)
                indexes = {
                    index["name"]: index for index in inspector.get_indexes("payments")
                }
                self.assertTrue(
                    indexes["uq_payments_provider_attempt_external_reference"]["unique"]
                )

                downgrade(directory=str(migrations_path), revision="c4a8e2f1b7d9")
                columns = {column["name"] for column in inspect(db.engine).get_columns("payments")}
                self.assertNotIn("attempt_id", columns)

                upgrade(directory=str(migrations_path))
                columns = {column["name"] for column in inspect(db.engine).get_columns("payments")}
                self.assertIn("attempt_id", columns)
                db.session.remove()
                db.engine.dispose()

    def test_production_rejects_missing_or_test_credentials(self) -> None:
        missing = Flask("missing")
        missing.config.update(APP_ENV="production", MERCADO_PAGO_ENVIRONMENT="production")
        with self.assertRaises(RuntimeError):
            validate_mercado_pago_config(missing)

        test_credentials = self.valid_app("production")
        test_credentials.config.update(
            MERCADO_PAGO_ACCESS_TOKEN="TEST-token",
            MERCADO_PAGO_PUBLIC_KEY="TEST-key",
        )
        with self.assertRaises(RuntimeError):
            validate_mercado_pago_config(test_credentials)

    def test_test_environment_rejects_live_credentials(self) -> None:
        app = self.valid_app("test")
        app.config.update(
            APP_ENV="development",
            MERCADO_PAGO_ACCESS_TOKEN="APP_USR-live-token",
            MERCADO_PAGO_PUBLIC_KEY="APP_USR-live-key",
        )
        with self.assertRaises(RuntimeError):
            validate_mercado_pago_config(app)

    def test_real_payments_are_blocked_outside_production_app(self) -> None:
        app = self.valid_app("production")
        app.config["APP_ENV"] = "development"
        with self.assertRaises(RuntimeError):
            validate_mercado_pago_config(app)

    def test_valid_production_configuration_passes(self) -> None:
        validate_mercado_pago_config(self.valid_app("production"))

    @staticmethod
    def valid_app(environment: str) -> Flask:
        app = Flask(environment)
        is_production = environment == "production"
        app.config.update(
            APP_ENV="production" if is_production else "development",
            BASE_URL="https://boostconvert.com.br",
            MERCADO_PAGO_ENVIRONMENT=environment,
            MERCADO_PAGO_ACCESS_TOKEN=(
                "APP_USR-production-token" if is_production else "TEST-token"
            ),
            MERCADO_PAGO_PUBLIC_KEY=(
                "APP_USR-production-key" if is_production else "TEST-key"
            ),
            MERCADO_PAGO_WEBHOOK_SECRET="webhook-secret",
            MERCADO_PAGO_COLLECTOR_ID="123456",
        )
        return app


if __name__ == "__main__":
    unittest.main()

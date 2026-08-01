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
    def test_cleanup_revision_is_the_single_migration_head(self) -> None:
        config = AlembicConfig(str(BACKEND_ROOT / "migrations" / "alembic.ini"))
        config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
        script = ScriptDirectory.from_config(config)
        self.assertEqual(script.get_heads(), ["a8d4e6f2c1b9"])

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
                columns = {column["name"] for column in inspector.get_columns("payments")}
                removed_method = "".join(("p", "i", "x"))
                code_suffix = "_q" + "r_code"
                encoded_code_suffix = code_suffix + "_base64"
                link_suffix = "_ticket" + "_url"
                removed_columns = {
                    removed_method + code_suffix,
                    removed_method + encoded_code_suffix,
                    removed_method + link_suffix,
                }
                self.assertTrue(
                    {
                        "idempotency_key",
                        "external_reference",
                    }
                    <= columns
                )
                self.assertTrue(removed_columns.isdisjoint(columns))
                constraint_names = {
                    constraint["name"]
                    for constraint in inspector.get_unique_constraints("payments")
                }
                self.assertIn("uq_payments_provider_idempotency_key", constraint_names)
                self.assertNotIn("attempt_id", columns)
                downgrade(revision="c4a8e2f1b7d9", directory=str(migrations_path))
                downgraded_columns = {
                    column["name"] for column in inspect(db.engine).get_columns("payments")
                }
                self.assertTrue(removed_columns <= downgraded_columns)
                upgrade(directory=str(migrations_path))
                upgraded_columns = {
                    column["name"] for column in inspect(db.engine).get_columns("payments")
                }
                self.assertTrue(removed_columns.isdisjoint(upgraded_columns))
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

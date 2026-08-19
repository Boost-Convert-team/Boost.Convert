import sys
import unittest
from pathlib import Path

from flask import Flask

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from config import validate_payment_config


class PaymentConfigTests(unittest.TestCase):
    def test_development_logs_each_missing_field_without_values(self):
        app = Flask(__name__)
        app.config.update(APP_ENV="development")
        with self.assertLogs(app.logger.name, level="WARNING") as logs:
            validate_payment_config(app)
        output = "\n".join(logs.output)
        self.assertIn("field=MERCADOPAGO_ACCESS_TOKEN", output)
        self.assertIn("field=MERCADOPAGO_WEBHOOK_URL", output)
        self.assertIn("field=MERCADOPAGO_WEBHOOK_SECRET", output)

    def test_production_refuses_missing_payment_configuration(self):
        app = Flask(__name__)
        app.config.update(APP_ENV="production")
        with self.assertRaisesRegex(RuntimeError, "MERCADOPAGO_ACCESS_TOKEN"):
            validate_payment_config(app)

    def test_production_accepts_required_https_configuration(self):
        app = Flask(__name__)
        app.config.update(
            APP_ENV="production",
            BASE_URL="https://boostconvert.com.br",
            MERCADOPAGO_PUBLIC_KEY="public-key",
            MERCADOPAGO_ACCESS_TOKEN="not-logged",
            MERCADOPAGO_WEBHOOK_URL=(
                "https://boostconvert.com.br/webhooks/mercado-pago"
            ),
            MERCADOPAGO_WEBHOOK_SECRET="not-logged",
        )
        validate_payment_config(app)


if __name__ == "__main__":
    unittest.main()

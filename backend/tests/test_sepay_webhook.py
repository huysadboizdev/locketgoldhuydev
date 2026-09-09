import hashlib
import hmac
import json
import os
import time
import unittest

from flask import Flask

from locket.sepay_webhook import sepay_webhook_bp


class SePayWebhookTestCase(unittest.TestCase):
    SECRET = "test-sepay-webhook-secret-with-sufficient-length"

    def setUp(self):
        self.old_env = {
            key: os.environ.get(key)
            for key in (
                "PAYMENT_WEBHOOK_ENABLED",
                "SEPAY_WEBHOOK_SECRET",
                "SEPAY_WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS",
            )
        }
        os.environ["PAYMENT_WEBHOOK_ENABLED"] = "1"
        os.environ["SEPAY_WEBHOOK_SECRET"] = self.SECRET
        os.environ["SEPAY_WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS"] = "300"

        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(sepay_webhook_bp)
        self.client = app.test_client()

    def tearDown(self):
        for key, value in self.old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _signed_headers(self, body: bytes, timestamp: int | None = None):
        timestamp_text = str(timestamp if timestamp is not None else int(time.time()))
        signed = timestamp_text.encode("ascii") + b"." + body
        digest = hmac.new(self.SECRET.encode(), signed, hashlib.sha256).hexdigest()
        return {
            "Content-Type": "application/json",
            "X-SePay-Timestamp": timestamp_text,
            "X-SePay-Signature": f"sha256={digest}",
        }

    @staticmethod
    def _payload():
        return {
            "id": 92704,
            "gateway": "TPBank",
            "accountNumber": "test-account",
            "code": "LOCKETGOLDHUYDEV123",
            "content": "LOCKETGOLDHUYDEV123",
            "transferType": "in",
            "transferAmount": 50000,
            "referenceCode": "FT24012345678",
        }

    def test_valid_signature_is_accepted(self):
        body = json.dumps(self._payload(), separators=(",", ":")).encode()
        response = self.client.post(
            "/api/payment/webhook",
            data=body,
            headers=self._signed_headers(body),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"success": True})

    def test_invalid_signature_is_rejected(self):
        body = json.dumps(self._payload()).encode()
        headers = self._signed_headers(body)
        headers["X-SePay-Signature"] = "sha256=" + "0" * 64
        response = self.client.post("/api/payment/webhook", data=body, headers=headers)
        self.assertEqual(response.status_code, 401)

    def test_stale_timestamp_is_rejected(self):
        body = json.dumps(self._payload()).encode()
        response = self.client.post(
            "/api/payment/webhook",
            data=body,
            headers=self._signed_headers(body, int(time.time()) - 301),
        )
        self.assertEqual(response.status_code, 401)

    def test_raw_body_changes_invalidate_signature(self):
        compact = json.dumps(self._payload(), separators=(",", ":")).encode()
        pretty = json.dumps(self._payload(), indent=2).encode()
        response = self.client.post(
            "/api/payment/webhook",
            data=pretty,
            headers=self._signed_headers(compact),
        )
        self.assertEqual(response.status_code, 401)

    def test_disabled_webhook_is_rejected(self):
        os.environ["PAYMENT_WEBHOOK_ENABLED"] = "0"
        body = json.dumps(self._payload()).encode()
        response = self.client.post(
            "/api/payment/webhook",
            data=body,
            headers=self._signed_headers(body),
        )
        self.assertEqual(response.status_code, 503)

    def test_missing_secret_fails_closed(self):
        os.environ.pop("SEPAY_WEBHOOK_SECRET", None)
        body = json.dumps(self._payload()).encode()
        response = self.client.post("/api/payment/webhook", data=body)
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()

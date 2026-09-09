import os
import unittest
from unittest.mock import Mock, patch

from locket import notifications


class TelegramNotificationTestCase(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(
            os.environ,
            {
                "TELEGRAM_NOTIFICATIONS_ENABLED": "1",
                "TELEGRAM_BOT_TOKEN": "123456:test-token",
                "TELEGRAM_CHAT_ID": "-100123456789",
                "TELEGRAM_NOTIFY_NEW_ORDERS": "1",
                "TELEGRAM_NOTIFY_ACTIVATION_SUCCESS": "1",
                "TELEGRAM_ADMIN_ORDERS_URL": "https://locketgoldhuy.io.vn/admin?tab=orders",
            },
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_order_message_highlights_manual_contact_and_escapes_html(self):
        order = {
            "id": 17,
            "user_id": 9,
            "plan_name_snapshot": "VPN <Pro>",
            "price_vnd_snapshot": 50000,
            "price_coin_snapshot": 50,
            "payment_method": "qr",
            "platform": "ios",
            "fulfillment_mode_snapshot": "manual_contact",
            "contact_zalo": "+84912345678",
            "contact_facebook": "https://facebook.com/a?x=1&y=2",
            "coupon_code_snapshot": "VIP20",
            "discount_vnd_snapshot": 10000,
            "created_at": 0,
        }
        user = {
            "display_name": "Huy & Admin",
            "username": "huydev",
            "email": "huy@example.com",
        }
        payment = {
            "amount_vnd": 40000,
            "transfer_code": "LOCKETGOLDHUYDEV428",
            "paid_at": 0,
        }

        message = notifications._order_message(order, user, payment)

        self.assertIn("ĐƠN MỚI · CẦN ADMIN XỬ LÝ", message)
        self.assertIn("<b>Thực trả:</b> <b>40.000 đ</b>", message)
        self.assertIn("LOCKETGOLDHUYDEV428", message)
        self.assertIn("VIP20", message)
        self.assertIn("THÔNG TIN LIÊN HỆ", message)
        self.assertIn("VPN &lt;Pro&gt;", message)
        self.assertIn("Huy &amp; Admin", message)
        self.assertNotIn("VPN <Pro>", message)
        self.assertLessEqual(len(message), 4096)

    @patch("locket.notifications.requests.post")
    def test_send_message_uses_safe_telegram_payload(self, post):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"ok": True}
        post.return_value = response

        sent = notifications._send_message(
            "<b>Test</b>",
            {"inline_keyboard": [[{"text": "Mở đơn", "url": "https://example.com"}]]},
        )

        self.assertTrue(sent)
        _, kwargs = post.call_args
        self.assertEqual(kwargs["json"]["chat_id"], "-100123456789")
        self.assertEqual(kwargs["json"]["parse_mode"], "HTML")
        self.assertEqual(kwargs["json"]["link_preview_options"], {"is_disabled": True})
        self.assertIn("reply_markup", kwargs["json"])
        self.assertEqual(kwargs["timeout"], (3.05, 5))

    @patch("locket.notifications._send_async")
    @patch("locket.db.get_user_by_id")
    @patch("locket.db.get_activation_order_by_id")
    def test_paid_order_notification_has_single_admin_button(
        self, get_order, get_user, send_async
    ):
        get_order.return_value = {
            "id": 20,
            "user_id": 4,
            "plan_name_snapshot": "Locket Gold Android",
            "price_vnd_snapshot": 20000,
            "price_coin_snapshot": 20,
            "payment_method": "coin",
            "platform": "android",
            "fulfillment_mode_snapshot": "apk_download",
            "created_at": 100,
        }
        get_user.return_value = {
            "display_name": "Khách hàng",
            "username": "customer",
            "email": "customer@example.com",
        }
        send_async.return_value = True

        self.assertTrue(notifications.notify_paid_order(20))
        text, keyboard = send_async.call_args.args
        self.assertIn("20 Coin", text)
        self.assertIn("Đã mở quyền tải Android", text)
        self.assertEqual(len(keyboard["inline_keyboard"]), 1)
        self.assertEqual(len(keyboard["inline_keyboard"][0]), 1)

    @patch("locket.notifications.requests.post")
    def test_disabled_or_missing_credentials_never_calls_telegram(self, post):
        with patch.dict(os.environ, {"TELEGRAM_NOTIFICATIONS_ENABLED": "0"}):
            self.assertFalse(notifications._send_message("test"))
        post.assert_not_called()

    def test_non_https_admin_url_is_not_used(self):
        with patch.dict(
            os.environ,
            {"TELEGRAM_ADMIN_ORDERS_URL": "http://unsafe.example/admin"},
        ):
            self.assertIsNone(notifications._order_admin_url())

    @patch("locket.notifications.requests.post")
    def test_flask_testing_mode_never_sends_external_message(self, post):
        from flask import Flask

        app = Flask(__name__)
        app.config["TESTING"] = True
        with app.app_context():
            self.assertFalse(notifications._send_message("test"))
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()

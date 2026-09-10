from unittest.mock import patch, MagicMock
from locket.locket_api import LocketAPI


def test_getSubscriber_parses_gold():
    api = LocketAPI(token="dummy")
    fake_resp = MagicMock()
    fake_resp.ok = True
    fake_resp.status_code = 200
    fake_resp.json.return_value = {
        "subscriber": {"entitlements": {"Gold": {
            "product_identifier": "locket_199_1m",
            "expires_date": "2026-12-31T00:00:00Z"}}}
    }
    with patch("locket.locket_api._get_with_proxy", return_value=fake_resp):
        out = api.getSubscriber("UID28CHARS12345678901234567")
    assert out["subscriber"]["entitlements"]["Gold"]["product_identifier"] == "locket_199_1m"

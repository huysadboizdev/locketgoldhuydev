"""LunaKey activation provider client.

LunaKey exposes two endpoints on a fixed, operator-controlled base URL:

- ``POST /api/v1/lookup``   -> read-only profile / Gold status lookup.
- ``POST /api/v1/gold``     -> paid Gold activation, idempotent per request_id.

Design rules enforced here (see ``docs/opencode-lunakey-implementation-prompt.md``):

- The API key is read from ``LUNAKEY_API_KEY`` only and never logged.
- The base URL is allow-listed; a caller can never supply it per request.
- Redirects are disabled so the ``X-API-Key`` header cannot leak to another host.
- TLS verification is always on.
- Connect/read timeouts are finite. This module never retries: retry policy is
  owned by the persistent provider job so idempotency stays under our control.
- Response bodies are validated; a 200 with an unusable body is reported as an
  *unclear* outcome, never silently treated as success or failure.

The transport is injectable so tests can run without any network access.
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://locket.lunakey.net"
DEFAULT_ALLOWED_HOSTS = ("locket.lunakey.net",)
LOOKUP_PATH = "/api/v1/lookup"
ACTIVATE_PATH = "/api/v1/gold"
DEFAULT_TIMEOUT_SECONDS = 20
MAX_TIMEOUT_SECONDS = 120
MAX_BODY_CHARS = 4000

# Provider categories we are allowed to send. Only ``yearly`` is documented by
# the provider; anything else must be added here together with a confirmed
# contract. We never invent monthly/quarterly categories.
KNOWN_CATEGORIES = ("yearly",)


class LunaKeyError(Exception):
    """Base error with a stable, machine-readable classification."""

    category = "unclear"
    retryable = False
    http_status = None

    def __init__(self, code, message, *, http_status=None, retryable=None, category=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        if retryable is not None:
            self.retryable = retryable
        if category is not None:
            self.category = category

    def as_dict(self):
        return {
            "category": self.category,
            "code": self.code,
            "message": self.message,
            "http_status": self.http_status,
            "retryable": self.retryable,
        }


class LunaKeyConfigError(LunaKeyError):
    category = "configuration"


class LunaKeyAuthError(LunaKeyError):
    category = "auth"


class LunaKeyInsufficientFundsError(LunaKeyError):
    category = "insufficient_funds"


class LunaKeyInvalidRequestError(LunaKeyError):
    category = "invalid_request"


class LunaKeyConfirmationRequiredError(LunaKeyError):
    category = "confirmation_required"


class LunaKeyUnavailableError(LunaKeyError):
    category = "unavailable"
    retryable = True


class LunaKeyUnclearError(LunaKeyError):
    """Result could not be verified (timeout, 502, unparseable body, mismatch)."""

    category = "unclear"
    retryable = True


# Vietnamese messages shown to customers. Internal codes stay stable.
PUBLIC_MESSAGES = {
    "provider_not_configured": "Nguồn kích hoạt LunaKey chưa được cấu hình. Vui lòng liên hệ hỗ trợ.",
    "provider_disabled": "Nguồn kích hoạt LunaKey đang tạm dừng. Vui lòng thử lại sau.",
    "provider_paused": "Nguồn kích hoạt LunaKey đang tạm dừng để kiểm tra. Vui lòng thử lại sau.",
    "lookup_not_found": "Không tìm thấy tài khoản Locket với thông tin đã nhập.",
    "lookup_failed": "Không thể tra cứu tài khoản Locket lúc này. Vui lòng thử lại sau.",
    "invalid_request": "Yêu cầu kích hoạt không hợp lệ hoặc tài khoản không đủ điều kiện.",
    "confirmation_required": "Nguồn kích hoạt yêu cầu bước xác nhận bổ sung. Vui lòng liên hệ hỗ trợ.",
    "insufficient_funds": "Nguồn kích hoạt tạm thời không đủ số dư. Đơn của bạn đã được ghi nhận và sẽ xử lý sớm.",
    "provider_auth": "Nguồn kích hoạt từ chối xác thực. Quản trị viên đã được thông báo.",
    "unavailable": "Nguồn kích hoạt đang bận. Hệ thống sẽ tự động thử lại.",
    "unclear": "Chưa xác minh được kết quả kích hoạt. Đơn đang chờ đối soát, vui lòng không thanh toán lại.",
}


def public_message(code: str, fallback: str = None) -> str:
    return PUBLIC_MESSAGES.get(code, fallback or PUBLIC_MESSAGES["unclear"])


def _env_flag(name: str, default: str = "0") -> bool:
    return (os.getenv(name, default) or "").strip().lower() in {"1", "true", "yes", "on"}


def get_api_key() -> str:
    return (os.getenv("LUNAKEY_API_KEY") or "").strip()


def is_configured() -> bool:
    return bool(get_api_key())


def _allowed_hosts() -> set:
    raw = (os.getenv("LUNAKEY_ALLOWED_HOSTS") or "").strip()
    if not raw:
        return set(DEFAULT_ALLOWED_HOSTS)
    hosts = {item.strip().lower() for item in re.split(r"[,;\s]+", raw) if item.strip()}
    return hosts or set(DEFAULT_ALLOWED_HOSTS)


def get_base_url() -> str:
    """Return the validated base URL, or raise LunaKeyConfigError."""
    raw = (os.getenv("LUNAKEY_BASE_URL") or DEFAULT_BASE_URL).strip().rstrip("/")
    try:
        parsed = urlparse(raw)
    except ValueError as exc:
        raise LunaKeyConfigError("invalid_base_url", "LUNAKEY_BASE_URL không hợp lệ.") from exc
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise LunaKeyConfigError(
            "invalid_base_url",
            "LUNAKEY_BASE_URL phải là HTTPS hợp lệ và không chứa thông tin đăng nhập.",
        )
    host = parsed.hostname.lower()
    if host not in _allowed_hosts():
        raise LunaKeyConfigError(
            "base_url_not_allowed",
            f"Host LunaKey '{host}' không nằm trong allowlist.",
        )
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise LunaKeyConfigError("invalid_base_url", "LUNAKEY_BASE_URL không được chứa path/query.")
    return f"https://{host}"


def get_timeout() -> tuple:
    raw = (os.getenv("LUNAKEY_TIMEOUT_SECONDS") or "").strip()
    try:
        value = int(raw) if raw else DEFAULT_TIMEOUT_SECONDS
    except (TypeError, ValueError):
        value = DEFAULT_TIMEOUT_SECONDS
    value = max(3, min(value, MAX_TIMEOUT_SECONDS))
    # (connect, read)
    return (min(5, value), value)


def is_enabled() -> bool:
    return _env_flag("LUNAKEY_ENABLED", "1")


def _default_transport(method, url, *, headers, json_body, timeout):
    """Perform a single HTTP request. No retries, no redirects, TLS verified."""
    return requests.request(
        method,
        url,
        headers=headers,
        json=json_body,
        timeout=timeout,
        allow_redirects=False,
        verify=True,
    )


def _safe_log(**fields):
    """Log only non-sensitive correlation fields."""
    logger.info(
        "lunakey request provider=%s op=%s request_id=%s order_id=%s attempt=%s",
        "lunakey",
        fields.get("op"),
        fields.get("request_id"),
        fields.get("order_id"),
        fields.get("attempt"),
    )


class LunaKeyClient:
    """Thin LunaKey client. All state is injected; nothing happens at import."""

    provider_name = "lunakey"

    def __init__(self, api_key=None, base_url=None, transport=None, timeout=None):
        self._api_key = api_key
        self._base_url = base_url
        self._transport = transport
        self._timeout = timeout

    # -- config helpers -------------------------------------------------

    def _resolve_key(self) -> str:
        key = (self._api_key if self._api_key is not None else get_api_key()).strip()
        if not key:
            raise LunaKeyConfigError(
                "provider_not_configured", public_message("provider_not_configured")
            )
        return key

    def _resolve_base(self) -> str:
        return self._base_url if self._base_url else get_base_url()

    def _resolve_timeout(self):
        return self._timeout if self._timeout else get_timeout()

    # -- transport ------------------------------------------------------

    def _request(self, method, path, *, payload, idempotency_key=None, op="request"):
        key = self._resolve_key()
        base = self._resolve_base()
        url = f"{base}{path}"
        headers = {
            "X-API-Key": key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        transport = self._transport or _default_transport
        _safe_log(op=op, request_id=idempotency_key, order_id=None, attempt=None)
        try:
            response = transport(
                method,
                url,
                headers=headers,
                json_body=payload,
                timeout=self._resolve_timeout(),
            )
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError,
                requests.exceptions.SSLError, requests.exceptions.ChunkedEncodingError) as exc:
            # Network-level failure: result unknown. Retry is the job's decision.
            raise LunaKeyUnclearError(
                "network_error", public_message("unclear"), retryable=True
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise LunaKeyUnclearError(
                "transport_error", public_message("unclear"), retryable=True
            ) from exc
        return self._parse(response, op=op)

    @staticmethod
    def _response_text(response) -> str:
        try:
            text = response.text or ""
        except Exception:
            return ""
        return text[:MAX_BODY_CHARS]

    def _parse(self, response, *, op):
        status = getattr(response, "status_code", None)
        body_text = self._response_text(response)
        data = None
        if body_text:
            try:
                data = json.loads(body_text)
            except (ValueError, TypeError):
                data = None

        if status == 200:
            if not isinstance(data, dict):
                raise LunaKeyUnclearError(
                    "malformed_success_body", public_message("unclear"), http_status=200, retryable=True
                )
            return data

        if status == 400:
            raise LunaKeyInvalidRequestError(
                "invalid_request", public_message("invalid_request"), http_status=400
            )
        if status == 401:
            raise LunaKeyAuthError(
                "provider_auth", public_message("provider_auth"), http_status=401
            )
        if status == 402:
            raise LunaKeyInsufficientFundsError(
                "insufficient_funds", public_message("insufficient_funds"), http_status=402
            )
        if status == 409:
            raise LunaKeyConfirmationRequiredError(
                "confirmation_required", public_message("confirmation_required"), http_status=409
            )
        if status in (500, 502, 503, 504):
            raise LunaKeyUnavailableError(
                "upstream_error", public_message("unavailable"), http_status=status, retryable=True
            )
        if status in (301, 302, 303, 307, 308):
            # Redirects are disabled; a redirect is a contract violation, not a
            # reason to follow the Location (which could leak the API key).
            raise LunaKeyUnavailableError(
                "unexpected_redirect", public_message("unavailable"), http_status=status, retryable=False
            )
        raise LunaKeyUnclearError(
            "unexpected_status", public_message("unclear"), http_status=status, retryable=True
        )

    # -- public API -----------------------------------------------------

    def lookup(self, user):
        """Look up a Locket profile. Returns a normalized dict."""
        if not isinstance(user, str) or not user.strip():
            raise LunaKeyInvalidRequestError(
                "invalid_user", public_message("lookup_not_found"), http_status=400
            )
        data = self._request("POST", LOOKUP_PATH, payload={"user": user.strip()}, op="lookup")
        if data.get("success") is not True:
            # A lookup miss is a normal business outcome, never retried.
            raise LunaKeyInvalidRequestError(
                "lookup_not_found", public_message("lookup_not_found"), http_status=200
            )
        profile = data.get("profile")
        if not isinstance(profile, dict):
            raise LunaKeyUnclearError(
                "malformed_profile", public_message("lookup_failed"), http_status=200, retryable=True
            )
        return normalize_profile(profile)

    def activate(self, user, category, request_id, confirm=True):
        """Request a paid Gold activation. Returns a normalized result dict.

        The same ``request_id`` (sent both as ``request_id`` and
        ``Idempotency-Key``) must be reused for every retry of one order.
        """
        if not isinstance(user, str) or not user.strip():
            raise LunaKeyInvalidRequestError("invalid_user", public_message("invalid_request"), http_status=400)
        if not isinstance(category, str) or not category.strip():
            raise LunaKeyInvalidRequestError("invalid_category", public_message("invalid_request"), http_status=400)
        if category.strip() not in KNOWN_CATEGORIES:
            raise LunaKeyConfigError(
                "unknown_category", "Category LunaKey chưa được xác nhận trong hợp đồng."
            )
        if not isinstance(request_id, str) or not request_id.strip():
            raise LunaKeyConfigError("missing_request_id", "Thiếu request_id cho đơn kích hoạt.")

        payload = {
            "user": user.strip(),
            "category": category.strip(),
            "confirm": bool(confirm),
            "request_id": request_id.strip(),
        }
        data = self._request(
            "POST",
            ACTIVATE_PATH,
            payload=payload,
            idempotency_key=request_id.strip(),
            op="activate",
        )

        if data.get("success") is not True:
            # A 200 without success=true cannot be treated as a completed
            # activation. It is an unclear outcome requiring reconciliation.
            raise LunaKeyUnclearError(
                "success_false", public_message("unclear"), http_status=200, retryable=True
            )

        order_code = data.get("order_code")
        if not isinstance(order_code, str) or not order_code.strip():
            raise LunaKeyUnclearError(
                "missing_order_code", public_message("unclear"), http_status=200, retryable=True
            )
        returned_request_id = data.get("request_id")
        if returned_request_id is not None and str(returned_request_id).strip() != request_id.strip():
            # The provider echoed a different request id: do not claim success.
            raise LunaKeyUnclearError(
                "request_id_mismatch", public_message("unclear"), http_status=200, retryable=True
            )

        price_deducted = data.get("price_deducted")
        if price_deducted is not None and (
            isinstance(price_deducted, bool) or not isinstance(price_deducted, int)
        ):
            price_deducted = None
        remaining_balance = data.get("remaining_balance")
        if remaining_balance is not None and (
            isinstance(remaining_balance, bool) or not isinstance(remaining_balance, int)
        ):
            remaining_balance = None

        return {
            "success": True,
            "order_code": order_code.strip(),
            "request_id": request_id.strip(),
            "price_deducted": price_deducted,
            "remaining_balance": remaining_balance,
            "currency": "VND",
            "message": str(data.get("message") or "").strip()[:500],
            "profile": normalize_profile(data.get("profile")) if isinstance(data.get("profile"), dict) else None,
        }


def normalize_profile(profile):
    """Normalize a provider profile into a stable, frontend-safe shape."""
    if not isinstance(profile, dict):
        return None
    has_gold = profile.get("has_gold")
    if has_gold is None:
        has_gold = None
    else:
        has_gold = bool(has_gold)
    days_left = profile.get("gold_days_left")
    if isinstance(days_left, bool) or not isinstance(days_left, int):
        days_left = None
    return {
        "username": str(profile.get("username") or "").strip()[:100] or None,
        "name": str(profile.get("name") or "").strip()[:150] or None,
        "avatar": str(profile.get("avatar") or "").strip()[:1000] or None,
        "uid": str(profile.get("uid") or "").strip()[:64] or None,
        "has_gold": has_gold,
        "gold_expiry": str(profile.get("gold_expiry") or "").strip()[:64] or None,
        "gold_days_left": days_left,
    }


def new_request_id(order_id, env=None):
    """Build a globally unique, namespaced request id for one order."""
    namespace = (env or os.getenv("LUNAKEY_REQUEST_NAMESPACE") or "locketgold").strip()
    namespace = re.sub(r"[^A-Za-z0-9_.-]", "-", namespace)[:40] or "locketgold"
    token = uuid.uuid4().hex[:16]
    return f"{namespace}-{int(order_id)}-{token}"


def payload_hash(user, category, request_id):
    """Stable hash of the immutable activation payload (no secrets)."""
    import hashlib

    raw = json.dumps(
        {"user": user, "category": category, "request_id": request_id, "confirm": True},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


__all__ = [
    "LunaKeyClient",
    "LunaKeyError",
    "LunaKeyConfigError",
    "LunaKeyAuthError",
    "LunaKeyInsufficientFundsError",
    "LunaKeyInvalidRequestError",
    "LunaKeyConfirmationRequiredError",
    "LunaKeyUnavailableError",
    "LunaKeyUnclearError",
    "normalize_profile",
    "new_request_id",
    "payload_hash",
    "public_message",
    "is_configured",
    "is_enabled",
    "get_base_url",
    "KNOWN_CATEGORIES",
]

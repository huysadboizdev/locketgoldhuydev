"""Strict Google OAuth ID-token verification for customer sign-in."""

import os
import time

import requests


GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
ALLOWED_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}
MAX_ID_TOKEN_LENGTH = 16_384


def get_google_client_id() -> str:
    """Read the expected OAuth audience at request time."""
    return (os.getenv("GOOGLE_CLIENT_ID") or "").strip()


def verify_google_token(id_token: str) -> tuple[bool, dict | None, str | None]:
    """Verify a Google ID token and return ``(valid, claims, message)``."""
    if not isinstance(id_token, str):
        return False, None, "Token Google không hợp lệ."

    id_token = id_token.strip()
    if not id_token or len(id_token) > MAX_ID_TOKEN_LENGTH:
        return False, None, "Token Google không hợp lệ."

    expected_client_id = get_google_client_id()
    # Fail closed: without an expected audience, a token minted for an
    # unrelated Google OAuth client could otherwise be accepted.
    if not expected_client_id:
        return False, None, "Google Sign-In chưa được cấu hình trên máy chủ."

    try:
        response = requests.get(
            GOOGLE_TOKENINFO_URL,
            params={"id_token": id_token},
            timeout=5.0,
            headers={"Accept": "application/json"},
        )
    except requests.Timeout:
        return False, None, "Kết nối tới Google quá thời gian. Vui lòng thử lại."
    except requests.RequestException:
        # Do not include exception details because they can contain the URL
        # and therefore the credential supplied as a query parameter.
        return False, None, "Không thể kết nối tới Google để xác thực. Vui lòng thử lại."

    if response.status_code != 200:
        return False, None, "Token Google không hợp lệ hoặc đã hết hạn."

    try:
        payload = response.json()
    except (TypeError, ValueError):
        return False, None, "Phản hồi xác thực từ Google không hợp lệ."

    if not isinstance(payload, dict):
        return False, None, "Phản hồi xác thực từ Google không hợp lệ."

    if payload.get("iss") not in ALLOWED_ISSUERS:
        return False, None, "Issuer của token Google không hợp lệ."

    subject = str(payload.get("sub") or "").strip()
    if not subject:
        return False, None, "Token Google không có mã định danh người dùng."

    email = str(payload.get("email") or "").strip()
    if not email:
        return False, None, "Tài khoản Google không cung cấp địa chỉ email."

    if str(payload.get("email_verified")).lower() not in {"true", "1"}:
        return False, None, "Email Google chưa được xác thực."

    try:
        expires_at = float(payload.get("exp"))
    except (TypeError, ValueError):
        return False, None, "Thời gian hết hạn của token Google không hợp lệ."
    if expires_at <= time.time():
        return False, None, "Token Google đã hết hạn."

    if payload.get("aud") != expected_client_id:
        return False, None, "Audience của token Google không khớp cấu hình máy chủ."

    return True, payload, None

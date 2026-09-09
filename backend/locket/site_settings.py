"""Site-wide toggleable settings (popup notice + maintenance mode).

Two JSON blobs stored in the `site_settings` key/value table:

- `popup`      → {enabled, title, message, icon, button_text}
- `maintenance`→ {enabled, end_at (ISO+TZ), title, message,
                  contacts:[{role,name,url}], allow_admin}

Reads are cheap and uncached — SQLite + tiny rows. Public endpoint hits
this on every page load.
"""

from datetime import datetime, timezone
import json
import os
import re
import threading
import time
import urllib.parse

from . import db


POPUP_KEY = "popup"
MAINT_KEY = "maintenance"
THEME_KEY = "theme"
LAYOUT_KEY = "layout"

THEMES = ("gold", "aurora", "sunset", "mono")
LAYOUTS = ("stacked", "split", "spotlight")
POPUP_ICONS = ("info", "sparkles", "party", "warning", "help", "gift", "bell", "wrench", "shield", "success", "error", "question")
POPUP_AUDIENCES = ("all", "guests", "logged_in")
POPUP_DISPLAY_MODES = ("every_visit", "once_per_session", "once_per_version")

_DEFAULTS = {
    POPUP_KEY: {
        "enabled": False,
        "version": 1,
        "title": "Thông báo",
        "message": "",
        "icon": "info",
        "button_text": "",
        "button_url": "",
        "dismissible": True,
        "audience": "all",
        "display_mode": "every_visit",
        "routes": ["*"],
        "start_at": None,
        "end_at": None,
    },
    THEME_KEY: {"name": "gold"},
    LAYOUT_KEY: {"name": "stacked"},
    MAINT_KEY: {
        "enabled": False,
        "end_at": "",
        "start_at": "",
        "title": "Bảo Trì Máy Chủ",
        "message": (
            "Hệ thống đang được nâng cấp để mang đến trải nghiệm tốt hơn. "
            "Vui lòng quay lại sau khi bảo trì hoàn tất."
        ),
        "notice": (
            "Máy chủ đang trong quá trình bảo trì định kỳ, không phải gặp sự "
            "cố hay sập máy chủ. Toàn bộ dữ liệu của bạn vẫn được bảo toàn an "
            "toàn. Hệ thống sẽ hoạt động bình thường trở lại sau khi bảo trì "
            "hoàn tất. Cảm ơn bạn đã kiên nhẫn chờ đợi!"
        ),
        "contacts": [
            {"role": "Founder", "name": "nguyenthanhson.dev",
             "url": "https://nguyenthanhson.dev"},
            {"role": "Founder", "name": "maihuybao.dev",
             "url": "https://maihuybao.dev"},
        ],
        "allow_admin": True,
    },
}

_lock = threading.Lock()


def _normalize_popup_dict(raw):
    """Normalize legacy popup keys (content -> message, button_link -> button_url) and apply defaults."""
    if not isinstance(raw, dict):
        return dict(_DEFAULTS[POPUP_KEY])
    d = dict(_DEFAULTS[POPUP_KEY])
    src = dict(raw)

    # Legacy field mappings
    if "content" in src and "message" not in src:
        src["message"] = src.get("content")
    if "button_link" in src and "button_url" not in src:
        src["button_url"] = src.get("button_link")

    for k in d:
        if k in src and src[k] is not None:
            d[k] = src[k]

    # Type normalization
    d["enabled"] = bool(d.get("enabled", False))
    try:
        d["version"] = max(1, int(d.get("version", 1)))
    except (ValueError, TypeError):
        d["version"] = 1

    d["title"] = str(d.get("title") or "").strip()
    d["message"] = str(d.get("message") or "").strip()
    d["button_text"] = str(d.get("button_text") or "").strip()
    d["button_url"] = str(d.get("button_url") or "").strip()

    icon = str(d.get("icon") or "info").lower().strip()
    d["icon"] = icon if icon in POPUP_ICONS else "info"

    d["dismissible"] = bool(d.get("dismissible", True))

    aud = str(d.get("audience") or "all").lower().strip()
    aud = {"guest": "guests", "authenticated": "logged_in"}.get(aud, aud)
    d["audience"] = aud if aud in POPUP_AUDIENCES else "all"

    disp = str(d.get("display_mode") or "every_visit").lower().strip()
    disp = "every_visit" if disp == "always" else disp
    d["display_mode"] = disp if disp in POPUP_DISPLAY_MODES else "every_visit"

    routes = d.get("routes")
    if not isinstance(routes, list) or len(routes) == 0:
        d["routes"] = ["*"]
    else:
        norm_routes = []
        for r in routes:
            r_str = str(r).strip()
            if r_str and len(r_str) <= 100:
                norm_routes.append(r_str)
        d["routes"] = norm_routes if norm_routes else ["*"]

    # Datetimes
    for dt_field in ("start_at", "end_at"):
        val = d.get(dt_field)
        if val:
            val_str = str(val).strip()
            d[dt_field] = val_str if val_str else None
        else:
            d[dt_field] = None

    return d


def validate_popup_payload(payload):
    """Validate admin-supplied popup configuration. Returns None if valid or raises ValueError with reason."""
    if not isinstance(payload, dict):
        raise ValueError("Payload popup phải là một JSON object.")

    # 1. enabled
    if "enabled" in payload and not isinstance(payload["enabled"], bool):
        raise ValueError("Trường 'enabled' phải là giá trị boolean (true/false).")

    # 2. version
    if "version" in payload:
        try:
            v = payload["version"]
            if type(v) is not int or v < 1:
                raise ValueError
        except (ValueError, TypeError):
            raise ValueError("Phiên bản popup 'version' phải là số nguyên >= 1.")

    # 3. title
    title = payload.get("title", "")
    if title is not None:
        if len(str(title).strip()) > 120:
            raise ValueError("Tiêu đề popup không được vượt quá 120 ký tự.")

    # 4. message / content
    msg = payload.get("message")
    if msg is None and "content" in payload:
        msg = payload.get("content")
    if msg is not None:
        if len(str(msg).strip()) > 2000:
            raise ValueError("Nội dung thông báo popup không được vượt quá 2.000 ký tự.")

    if payload.get("enabled"):
        if not str(title or "").strip():
            raise ValueError("Tiêu đề popup là bắt buộc khi bật thông báo.")
        if not str(msg or "").strip():
            raise ValueError("Nội dung popup là bắt buộc khi bật thông báo.")

    # 5. button_text
    btn_text = payload.get("button_text")
    if btn_text is not None and len(str(btn_text).strip()) > 80:
        raise ValueError("Nhãn nút hành động không được vượt quá 80 ký tự.")

    # 6. button_url / button_link
    btn_url = payload.get("button_url")
    if btn_url is None and "button_link" in payload:
        btn_url = payload.get("button_link")
    if btn_url:
        u = str(btn_url).strip()
        if len(u) > 500:
            raise ValueError("Đường dẫn nút hành động không được vượt quá 500 ký tự.")
        if re.search(r"[\x00-\x20\x7f]", u) or "\\" in u:
            raise ValueError("Đường dẫn nút hành động chứa ký tự không an toàn.")
        low = u.lower()
        if any(low.startswith(bad) for bad in ("javascript:", "data:", "file:", "vbscript:")):
            raise ValueError("Đường dẫn nút hành động chứa giao thức không an toàn.")
        if u.startswith("/"):
            parsed = urllib.parse.urlsplit(u)
            if u.startswith("//") or parsed.scheme or parsed.netloc:
                raise ValueError("Đường dẫn nội bộ của popup không hợp lệ.")
        elif u.startswith("https://"):
            try:
                parsed = urllib.parse.urlsplit(u)
                _ = parsed.port
            except ValueError:
                raise ValueError("URL nút hành động không hợp lệ.")
            if (parsed.scheme != "https" or not parsed.hostname
                    or parsed.username or parsed.password):
                raise ValueError("URL nút hành động HTTPS không hợp lệ.")
        else:
            raise ValueError("Đường dẫn nút hành động phải là đường dẫn nội bộ (bắt đầu bằng '/') hoặc URL bảo mật (bắt đầu bằng 'https://').")

    if bool(str(btn_text or "").strip()) != bool(str(btn_url or "").strip()):
        raise ValueError("Nhãn nút và đường dẫn nút hành động phải được nhập cùng nhau.")

    # 7. icon
    if "icon" in payload and payload["icon"] is not None:
        icon = str(payload["icon"]).strip().lower()
        if icon not in POPUP_ICONS and icon != "question":
            raise ValueError(f"Biểu tượng không hợp lệ. Cho phép: {', '.join(POPUP_ICONS)}")

    # 8. dismissible
    if "dismissible" in payload and not isinstance(payload["dismissible"], bool):
        raise ValueError("Trường 'dismissible' phải là giá trị boolean (true/false).")

    # 9. audience
    if "audience" in payload and payload["audience"] is not None:
        aud = str(payload["audience"]).strip().lower()
        if aud not in POPUP_AUDIENCES:
            raise ValueError(f"Đối tượng hiển thị không hợp lệ. Cho phép: {', '.join(POPUP_AUDIENCES)}")

    # 10. display_mode
    if "display_mode" in payload and payload["display_mode"] is not None:
        disp = str(payload["display_mode"]).strip().lower()
        if disp not in POPUP_DISPLAY_MODES:
            raise ValueError(f"Chế độ hiển thị không hợp lệ. Cho phép: {', '.join(POPUP_DISPLAY_MODES)}")

    # 11. routes
    if "routes" in payload and payload["routes"] is not None:
        if not isinstance(payload["routes"], list):
            raise ValueError("Trường 'routes' phải là danh sách các đường dẫn.")
        for r in payload["routes"]:
            if not isinstance(r, str):
                raise ValueError("Mỗi đường dẫn trong 'routes' phải là chuỗi.")
            r_str = r.strip()
            if not r_str:
                continue
            if len(r_str) > 100:
                raise ValueError("Mỗi đường dẫn trong 'routes' không được vượt quá 100 ký tự.")
            if r_str != "*":
                if (not r_str.startswith("/") or r_str.startswith("//")
                        or "\\" in r_str or "?" in r_str or "#" in r_str
                        or ("*" in r_str and not r_str.endswith("*"))):
                    raise ValueError(f"Đường dẫn popup không hợp lệ: '{r_str}'.")

    # 12. start_at & end_at
    parsed_start = None
    parsed_end = None
    start_val = payload.get("start_at")
    if start_val:
        try:
            s_clean = str(start_val).strip().replace("Z", "+00:00")
            parsed_start = datetime.fromisoformat(s_clean)
            if parsed_start.tzinfo is None:
                parsed_start = parsed_start.replace(tzinfo=timezone.utc)
            else:
                parsed_start = parsed_start.astimezone(timezone.utc)
        except (ValueError, TypeError):
            raise ValueError("Thời gian bắt đầu 'start_at' không đúng định dạng ISO datetime.")

    end_val = payload.get("end_at")
    if end_val:
        try:
            e_clean = str(end_val).strip().replace("Z", "+00:00")
            parsed_end = datetime.fromisoformat(e_clean)
            if parsed_end.tzinfo is None:
                parsed_end = parsed_end.replace(tzinfo=timezone.utc)
            else:
                parsed_end = parsed_end.astimezone(timezone.utc)
        except (ValueError, TypeError):
            raise ValueError("Thời gian kết thúc 'end_at' không đúng định dạng ISO datetime.")

    if parsed_start and parsed_end:
        if parsed_end <= parsed_start:
            raise ValueError("Thời gian kết thúc 'end_at' phải sau thời gian bắt đầu 'start_at'.")

    return None


def is_popup_active(popup=None, now=None):
    """Check if the popup is actively scheduled and enabled."""
    if popup is None:
        popup = get_popup()
    if not isinstance(popup, dict) or not popup.get("enabled"):
        return False

    current_dt = datetime.now(timezone.utc) if now is None else now
    if current_dt.tzinfo is None:
        current_dt = current_dt.replace(tzinfo=timezone.utc)

    start_at = popup.get("start_at")
    if start_at:
        try:
            s_dt = datetime.fromisoformat(str(start_at).strip().replace("Z", "+00:00"))
            if s_dt.tzinfo is None:
                s_dt = s_dt.replace(tzinfo=timezone.utc)
            if current_dt < s_dt:
                return False
        except (ValueError, TypeError):
            pass

    end_at = popup.get("end_at")
    if end_at:
        try:
            e_dt = datetime.fromisoformat(str(end_at).strip().replace("Z", "+00:00"))
            if e_dt.tzinfo is None:
                e_dt = e_dt.replace(tzinfo=timezone.utc)
            if current_dt > e_dt:
                return False
        except (ValueError, TypeError):
            pass

    return True


def _read(key):
    row = db.get_conn().execute(
        "SELECT value FROM site_settings WHERE key=?", (key,)
    ).fetchone()
    if row is None:
        return dict(_DEFAULTS[key])
    try:
        raw_val = json.loads(row["value"])
        if key == POPUP_KEY:
            return _normalize_popup_dict(raw_val)
        merged = dict(_DEFAULTS[key])
        if isinstance(raw_val, dict):
            merged.update(raw_val)
        return merged
    except (ValueError, TypeError):
        return dict(_DEFAULTS[key])


def _write(key, value):
    payload = json.dumps(value)
    db.get_conn().execute(
        "INSERT INTO site_settings (key, value, updated_at) VALUES (?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
        (key, payload, time.time()),
    )


def get_popup():
    with _lock:
        return _read(POPUP_KEY)


def set_popup(value):
    cur = get_popup()
    # Normalize legacy and apply updates
    raw_incoming = dict(value or {})
    if "content" in raw_incoming and "message" not in raw_incoming:
        raw_incoming["message"] = raw_incoming.pop("content")
    if "button_link" in raw_incoming and "button_url" not in raw_incoming:
        raw_incoming["button_url"] = raw_incoming.pop("button_link")

    for k, v in raw_incoming.items():
        if k in _DEFAULTS[POPUP_KEY]:
            cur[k] = v

    # Validate before coercive legacy normalization so JSON strings/floats do
    # not silently turn into booleans or integers.
    validate_popup_payload(cur)
    cur = _normalize_popup_dict(cur)
    with _lock:
        _write(POPUP_KEY, cur)
    return cur


def get_maintenance():
    with _lock:
        return _read(MAINT_KEY)


def set_maintenance(value):
    cur = get_maintenance()
    allowed = set(_DEFAULTS[MAINT_KEY].keys())
    for k, v in (value or {}).items():
        if k in allowed:
            cur[k] = v
    cur["enabled"] = bool(cur.get("enabled"))
    cur["allow_admin"] = bool(cur.get("allow_admin", True))
    if not isinstance(cur.get("contacts"), list):
        cur["contacts"] = list(_DEFAULTS[MAINT_KEY]["contacts"])
    with _lock:
        _write(MAINT_KEY, cur)
    return cur


def get_theme():
    with _lock:
        v = _read(THEME_KEY)
    name = v.get("name") if isinstance(v, dict) else None
    if name not in THEMES:
        name = "gold"
    return {"name": name}


def set_theme(value):
    name = (value or {}).get("name")
    if name not in THEMES:
        raise ValueError(f"Unknown theme '{name}'. Allowed: {', '.join(THEMES)}")
    with _lock:
        _write(THEME_KEY, {"name": name})
    return {"name": name}


def get_layout():
    with _lock:
        v = _read(LAYOUT_KEY)
    name = v.get("name") if isinstance(v, dict) else None
    if name not in LAYOUTS:
        name = "stacked"
    return {"name": name}


def set_layout(value):
    name = (value or {}).get("name")
    if name not in LAYOUTS:
        raise ValueError(f"Unknown layout '{name}'. Allowed: {', '.join(LAYOUTS)}")
    with _lock:
        _write(LAYOUT_KEY, {"name": name})
    return {"name": name}


import os
import re
import urllib.parse


_SAFE_PROFILE_RE = re.compile(r"^[a-zA-Z0-9_-]{4,32}$")
_DEFAULT_DNS_PROFILE = "a1e971"


def get_public_dns_config():
    """Return safe public DNS config derived from NEXTDNS_PROFILE environment variable.
    Never exposes NEXTDNS_KEY or any secret tokens.
    """
    raw_profile = os.environ.get("NEXTDNS_PROFILE", _DEFAULT_DNS_PROFILE).strip()
    profile = raw_profile if _SAFE_PROFILE_RE.match(raw_profile) else _DEFAULT_DNS_PROFILE
    quoted_profile = urllib.parse.quote(profile)
    hostname = f"{profile}.dns.nextdns.io"
    apple_url = f"https://apple.nextdns.io/{quoted_profile}"
    doh_url = f"https://dns.nextdns.io/{quoted_profile}"

    return {
        "profile_id": profile,
        "hostname": hostname,
        "doh_url": doh_url,
        "apple_url": apple_url,
        "instructions": {
            "android": {
                "private_dns_hostname": hostname,
            },
            "ios": {
                "mobileconfig_url": "/api/mobileconfig",
                "apple_dns_url": apple_url,
            },
        },
    }


def public_view():
    """Trimmed payload safe to expose to anonymous clients."""
    dns_cfg = get_public_dns_config()
    popup = get_popup()
    popup_public = dict(popup)
    popup_public["active"] = is_popup_active(popup)
    return {
        "popup": popup_public,
        "maintenance": get_maintenance(),
        "theme": get_theme(),
        "layout": get_layout(),
        "dns": dns_cfg,
        "nextdns_profile": dns_cfg["profile_id"],
        "nextdns_hostname": dns_cfg["hostname"],
        "nextdns_apple_url": dns_cfg["apple_url"],
    }


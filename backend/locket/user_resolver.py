import re
import urllib.parse
import urllib.request
import logging

logger = logging.getLogger(__name__)


def resolve_locket_uid(username_or_link):
    """Resolve a 28-character Locket UID from a username, raw UID, or invite link."""
    if not username_or_link:
        return None

    raw = str(username_or_link).strip()

    # 1. Direct 28-character UID string
    if len(raw) == 28 and re.match(r"^[A-Za-z0-9]{28}$", raw):
        return raw

    # 2. Link containing /invites/<UID>
    m = re.search(r"/invites/([A-Za-z0-9]{28})", raw)
    if m:
        return m.group(1)

    # 3. Clean handle if passed as a URL
    clean_handle = raw
    if "locket.cam/" in clean_handle:
        clean_handle = clean_handle.split("locket.cam/")[-1].split("?")[0].strip("/")
    elif "locket.camera/links/" in clean_handle:
        clean_handle = clean_handle.split("locket.camera/links/")[-1].split("?")[0].strip("/")

    # Check if cleaned is now a UID
    if len(clean_handle) == 28 and re.match(r"^[A-Za-z0-9]{28}$", clean_handle):
        return clean_handle

    # 4. Fetch https://locket.cam/{clean_handle} and parse redirect / HTML
    url = f"https://locket.cam/{clean_handle}"
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
        "Accept": "text/html,application/xhtml+xml",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            final_url = str(resp.url)

            # Check final URL
            m = re.search(r"/invites/([A-Za-z0-9]{28})", final_url)
            if m:
                return m.group(1)

            # Check HTML body
            m = re.search(r"/invites/([A-Za-z0-9]{28})", html)
            if m:
                return m.group(1)

            # Check link= query parameter in deep links
            lp = re.search(r"link=([^\s\"'>]+)", html)
            if lp:
                decoded = urllib.parse.unquote(lp.group(1))
                dm = re.search(r"/invites/([A-Za-z0-9]{28})", decoded)
                if dm:
                    return dm.group(1)
    except Exception as e:
        logger.debug("Could not resolve UID via locket.cam for %s: %s", clean_handle, e)

    return None

"""Upload and immediately delete a tiny image to verify Cloudinary permissions.

Run from the backend directory after loading the same environment file used by
the service. No credentials or remote URLs are printed.
"""

import io
import sys

from flask import Flask
from PIL import Image

from locket import env
from locket.config import configure
from locket.image_storage import delete_stored_image, save_processed_image


def console_safe(value: object) -> str:
    """Keep diagnostics printable on Windows consoles using legacy encodings."""
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    return str(value).encode(encoding, errors="backslashreplace").decode(encoding)


def main() -> int:
    env.init_env()
    app = Flask("cloudinary-smoke-test")
    configure(app)
    if app.config["REVIEW_STORAGE_PROVIDER"] != "cloudinary":
        print("FAIL: REVIEW_STORAGE_PROVIDER is not cloudinary.")
        return 1

    encoded = io.BytesIO()
    Image.new("RGB", (8, 8), (255, 180, 0)).save(encoded, format="WEBP")
    stored = None

    with app.app_context():
        try:
            stored = save_processed_image(
                encoded.getvalue(),
                app.config["REVIEW_STORAGE_ROOT"],
                "webp",
                "review",
            )
            print("OK: Cloudinary create permission works.")
            return 0
        except Exception as exc:
            print(f"FAIL: {console_safe(exc)}")
            return 1
        finally:
            if stored:
                delete_stored_image(
                    stored["storage_name"],
                    app.config["REVIEW_STORAGE_ROOT"],
                    "review",
                )
                print("OK: diagnostic asset was deleted.")


if __name__ == "__main__":
    sys.exit(main())

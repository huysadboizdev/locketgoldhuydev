"""Public TikTok creator showcase and safe screenshot processing."""

import io
import os
import time
import warnings

from flask import Blueprint, abort, current_app, jsonify, make_response
from PIL import Image, ImageDraw, ImageOps, ImageStat

from . import db
from .image_storage import (
    ImageStorageConfigurationError,
    ImageStorageUploadError,
    SAFE_STORAGE_NAME,
    delete_stored_image,
    save_processed_image,
    serve_stored_image,
)

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass


creators_bp = Blueprint("creators", __name__, url_prefix="/api/creators")

MAX_CREATOR_IMAGE_SIZE = 5 * 1024 * 1024
MAX_CREATOR_PIXELS = 20_000_000
SAFE_CREATOR_FILENAME = SAFE_STORAGE_NAME


def creator_image_mimetype(storage_name):
    return "image/jpeg" if str(storage_name or "").lower().endswith(".jpg") else "image/webp"


def get_creator_storage_root():
    root = current_app.config.get("CREATOR_STORAGE_ROOT")
    if root:
        return os.path.abspath(root)
    return os.path.abspath(os.path.join(current_app.root_path, "..", "storage", "creators"))


def process_creator_screenshot(file_storage, crop_percent=24):
    """Validate, create a privacy-safe profile header and persist it as WebP.

    Only the cropped derivative is saved. The uploaded original (which may
    contain phone numbers or other profile bio details) is never persisted.
    The lower-left bio area inside the kept header is covered while the
    right-side TikTok avatar remains visible in full.
    """
    try:
        crop_percent = max(12, min(45, int(crop_percent)))
        raw = file_storage.read(MAX_CREATOR_IMAGE_SIZE + 1)
        if len(raw) > MAX_CREATOR_IMAGE_SIZE:
            return None, "Ảnh TikTok không được vượt quá 5MB."
        if len(raw) < 16 or file_storage.read(1):
            return None, "Tệp ảnh TikTok không hợp lệ."

        with warnings.catch_warnings():
            warnings.filterwarnings("error", category=Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as check:
                if check.format not in ("JPEG", "PNG", "WEBP", "HEIF", "HEIC"):
                    return None, "Chỉ hỗ trợ ảnh JPG, PNG, WebP hoặc HEIC."
                if getattr(check, "is_animated", False) or getattr(check, "n_frames", 1) > 1:
                    return None, "Không hỗ trợ ảnh động."
                width, height = check.size
                if width <= 0 or height <= 0:
                    return None, "Kích thước ảnh TikTok không hợp lệ."
                if width * height > MAX_CREATOR_PIXELS:
                    return None, "Ảnh vượt quá giới hạn an toàn 20 megapixel."
                check.verify()

        with Image.open(io.BytesIO(raw)) as image:
            image = ImageOps.exif_transpose(image)
            width, height = image.size
            crop_height = max(200, min(height, round(height * crop_percent / 100)))
            image = image.crop((0, 0, width, crop_height)).convert("RGB")

            # TikTok places the avatar on the right and the free-form bio on
            # the lower-left. Keep enough height for the entire avatar, then
            # permanently cover the bio/contact zone in the public derivative.
            # Sampling the top band preserves both light and dark screenshots.
            sample_height = max(1, min(crop_height, round(crop_height * 0.16)))
            background = tuple(
                int(channel)
                for channel in ImageStat.Stat(image.crop((0, 0, width, sample_height))).median[:3]
            )
            private_top = round(crop_height * 0.74)
            private_right = round(width * 0.72)
            ImageDraw.Draw(image).rectangle(
                (0, private_top, private_right, crop_height),
                fill=background,
            )
            image.thumbnail((1400, 900), Image.Resampling.LANCZOS)
            width, height = image.size

            # Encode before touching storage. Some minimal Pillow builds on VPS
            # do not include WebP; a clean JPEG derivative is a safe fallback.
            encoded = io.BytesIO()
            extension = "webp"
            try:
                image.save(encoded, format="WEBP", quality=84, method=6)
            except (KeyError, OSError, ValueError):
                encoded = io.BytesIO()
                image.save(encoded, format="JPEG", quality=88, optimize=True, progressive=True)
                extension = "jpg"

            stored = save_processed_image(
                encoded.getvalue(),
                get_creator_storage_root(),
                extension,
                "creator",
            )
            return {
                "storage_name": stored["storage_name"],
                "width": width,
                "height": height,
                "file_size": stored["file_size"],
                "mime_type": stored["mime_type"],
            }, None
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        return None, "Ảnh vượt quá giới hạn an toàn."
    except PermissionError:
        current_app.logger.exception(
            "Creator screenshot storage is not writable: %s",
            get_creator_storage_root(),
        )
        return None, "Máy chủ chưa có quyền lưu ảnh KOL. Vui lòng kiểm tra thư mục CREATOR_STORAGE_ROOT."
    except ImageStorageConfigurationError as exc:
        current_app.logger.error("Creator image storage is not configured: %s", exc)
        return None, str(exc)
    except ImageStorageUploadError as exc:
        return None, str(exc)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        current_app.logger.warning(
            "Unable to process creator screenshot (%s)", type(exc).__name__
        )
        return None, "Không thể xử lý ảnh TikTok. Vui lòng chọn ảnh khác."


def delete_creator_image(storage_name):
    delete_stored_image(storage_name, get_creator_storage_root(), "creator")


@creators_bp.route("", methods=["GET"])
def public_creators():
    creators = []
    for row in db.list_public_creators():
        review_images = []
        if row.get("review_id"):
            for image in db.get_review_images(row["review_id"]):
                review_images.append({
                    "id": image["id"],
                    "url": f"/api/reviews/images/{image['storage_name']}",
                    "width": image.get("width"),
                    "height": image.get("height"),
                })
        creators.append({
            "id": row["id"],
            "display_name": row["display_name"],
            "tiktok_handle": row["tiktok_handle"],
            "tiktok_url": row["tiktok_url"],
            "screenshot_url": f"/api/creators/images/{row['screenshot_name']}",
            "follower_count": row.get("follower_count"),
            "is_featured": bool(row.get("is_featured")),
            "plan_name": row.get("plan_name"),
            "review": None if not row.get("review_id") else {
                "id": row["review_id"],
                "rating": row.get("rating"),
                "content": row.get("review_content") or "",
                "created_at": row.get("review_created_at"),
                "images": review_images,
            },
        })

    response = make_response(jsonify({"success": True, "creators": creators, "total": len(creators)}))
    response.headers["Cache-Control"] = "no-store"
    return response


@creators_bp.route("/images/<storage_name>", methods=["GET"])
def public_creator_image(storage_name):
    if not SAFE_CREATOR_FILENAME.fullmatch(storage_name):
        abort(404)
    creator = db.get_creator_by_storage_name(storage_name)
    if not creator or not creator.get("is_active") or not creator.get("user_is_active"):
        abort(404)
    if creator.get("require_review"):
        review = db.get_review_by_user_id(creator["user_id"])
        if not review or review.get("status") != "approved":
            abort(404)
    response = serve_stored_image(
        storage_name,
        get_creator_storage_root(),
        "creator",
        "public, max-age=300, must-revalidate",
    )
    if response is None:
        abort(404)
    return response

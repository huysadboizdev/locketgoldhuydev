"""Shared local/Cloudinary storage for processed review and creator images.

Only already-decoded and metadata-stripped derivatives are passed here. New
Cloudinary assets use a recognizable filename prefix so old local images keep
working even when the configured provider changes later.
"""

import io
import logging
import os
import re
import uuid
from urllib.parse import quote

from flask import current_app, make_response, redirect, send_file


logger = logging.getLogger(__name__)

CLOUDINARY_STORAGE_PREFIX = "cld_"
SAFE_STORAGE_NAME = re.compile(r"^(?:cld_)?[a-f0-9]{32}\.(?:webp|jpg)$")
SAFE_CLOUDINARY_FOLDER = re.compile(r"^[A-Za-z0-9_/-]+$")


class ImageStorageConfigurationError(RuntimeError):
    """Raised when the selected storage provider cannot be used safely."""


class ImageStorageUploadError(RuntimeError):
    """Raised when a processed derivative cannot be persisted remotely."""


def storage_provider() -> str:
    provider = str(
        current_app.config.get("REVIEW_STORAGE_PROVIDER")
        or os.getenv("REVIEW_STORAGE_PROVIDER")
        or "local"
    ).strip().lower()
    return provider if provider in {"local", "cloudinary"} else "local"


def is_cloudinary_name(storage_name: str) -> bool:
    return bool(storage_name and storage_name.startswith(CLOUDINARY_STORAGE_PREFIX))


def _cloudinary_folder(asset_kind: str) -> str:
    if asset_kind == "creator":
        folder = (
            current_app.config.get("CLOUDINARY_CREATOR_FOLDER")
            or os.getenv("CLOUDINARY_CREATOR_FOLDER")
            or "locket-gold/creators"
        )
    else:
        folder = (
            current_app.config.get("CLOUDINARY_FOLDER")
            or os.getenv("CLOUDINARY_FOLDER")
            or "locket-gold/reviews"
        )
    folder = str(folder).strip().strip("/")
    if not folder or not SAFE_CLOUDINARY_FOLDER.fullmatch(folder) or ".." in folder.split("/"):
        raise ImageStorageConfigurationError("Cloudinary folder không hợp lệ.")
    return folder


def _cloudinary_credentials():
    cloud_name = str(
        current_app.config.get("CLOUDINARY_CLOUD_NAME")
        or os.getenv("CLOUDINARY_CLOUD_NAME")
        or ""
    ).strip()
    api_key = str(
        current_app.config.get("CLOUDINARY_API_KEY")
        or os.getenv("CLOUDINARY_API_KEY")
        or ""
    ).strip()
    api_secret = str(
        current_app.config.get("CLOUDINARY_API_SECRET")
        or os.getenv("CLOUDINARY_API_SECRET")
        or ""
    ).strip()
    if not cloud_name or not api_key or not api_secret:
        raise ImageStorageConfigurationError(
            "Cloudinary chưa được cấu hình đầy đủ trên máy chủ."
        )
    return cloud_name, api_key, api_secret


def _configure_cloudinary():
    try:
        import cloudinary
        import cloudinary.uploader
    except ImportError as exc:
        raise ImageStorageConfigurationError(
            "Máy chủ chưa cài thư viện Cloudinary."
        ) from exc

    cloud_name, api_key, api_secret = _cloudinary_credentials()
    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True,
    )
    return cloudinary.uploader


def save_processed_image(
    encoded_bytes: bytes,
    local_root: str,
    extension: str,
    asset_kind: str,
) -> dict:
    """Persist a safe derivative and return its storage metadata."""
    extension = extension.lower().lstrip(".")
    if extension not in {"webp", "jpg"}:
        raise ValueError("Unsupported processed image extension")
    if not encoded_bytes:
        raise ValueError("Processed image is empty")

    use_cloudinary = storage_provider() == "cloudinary"
    stem = f"{CLOUDINARY_STORAGE_PREFIX if use_cloudinary else ''}{uuid.uuid4().hex}"
    storage_name = f"{stem}.{extension}"

    if use_cloudinary:
        uploader = _configure_cloudinary()
        folder = _cloudinary_folder(asset_kind)
        try:
            result = uploader.upload(
                io.BytesIO(encoded_bytes),
                resource_type="image",
                type="upload",
                folder=folder,
                public_id=stem,
                format=extension,
                overwrite=False,
                unique_filename=False,
                use_filename=False,
            )
        except Exception as exc:
            logger.exception("Cloudinary upload failed for %s image", asset_kind)
            raise ImageStorageUploadError(
                "Không thể tải ảnh lên Cloudinary lúc này. Vui lòng thử lại sau."
            ) from exc
        if not result or result.get("resource_type") != "image" or not result.get("secure_url"):
            raise ImageStorageUploadError(
                "Cloudinary không trả về tệp ảnh hợp lệ. Vui lòng thử lại sau."
            )
        stored_size = int(result.get("bytes") or len(encoded_bytes))
    else:
        os.makedirs(local_root, exist_ok=True)
        target_path = os.path.join(local_root, storage_name)
        temp_path = f"{target_path}.tmp"
        try:
            with open(temp_path, "xb") as output:
                output.write(encoded_bytes)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temp_path, target_path)
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
        stored_size = os.path.getsize(target_path)

    return {
        "storage_name": storage_name,
        "file_size": stored_size,
        "mime_type": "image/webp" if extension == "webp" else "image/jpeg",
    }


def _cloudinary_public_id(storage_name: str, asset_kind: str) -> str:
    if not SAFE_STORAGE_NAME.fullmatch(storage_name) or not is_cloudinary_name(storage_name):
        raise ValueError("Invalid Cloudinary storage name")
    stem = storage_name.rsplit(".", 1)[0]
    return f"{_cloudinary_folder(asset_kind)}/{stem}"


def cloudinary_delivery_url(storage_name: str, asset_kind: str) -> str:
    cloud_name = str(
        current_app.config.get("CLOUDINARY_CLOUD_NAME")
        or os.getenv("CLOUDINARY_CLOUD_NAME")
        or ""
    ).strip()
    if not cloud_name or not re.fullmatch(r"[A-Za-z0-9_-]+", cloud_name):
        raise ImageStorageConfigurationError("Cloudinary cloud name không hợp lệ.")
    public_id = _cloudinary_public_id(storage_name, asset_kind)
    extension = storage_name.rsplit(".", 1)[1]
    encoded_path = "/".join(quote(part, safe="") for part in public_id.split("/"))
    return (
        f"https://res.cloudinary.com/{quote(cloud_name, safe='')}/image/upload/"
        f"f_auto,q_auto/{encoded_path}.{extension}"
    )


def delete_stored_image(storage_name: str, local_root: str, asset_kind: str) -> None:
    if not storage_name or not SAFE_STORAGE_NAME.fullmatch(storage_name):
        return
    if is_cloudinary_name(storage_name):
        try:
            uploader = _configure_cloudinary()
            uploader.destroy(
                _cloudinary_public_id(storage_name, asset_kind),
                resource_type="image",
                type="upload",
                invalidate=True,
            )
        except Exception:
            # Database deletion must not be rolled back merely because remote
            # cleanup is temporarily unavailable. Log enough to retry safely.
            logger.exception("Could not delete Cloudinary %s image %s", asset_kind, storage_name)
        return

    try:
        os.remove(os.path.join(local_root, storage_name))
    except FileNotFoundError:
        pass
    except OSError:
        logger.exception("Could not delete local %s image %s", asset_kind, storage_name)


def serve_stored_image(
    storage_name: str,
    local_root: str,
    asset_kind: str,
    cache_control: str,
    accel_prefix: str | None = None,
):
    """Return a safe local response or redirect for an authorized DB asset."""
    if not SAFE_STORAGE_NAME.fullmatch(storage_name):
        return None
    mimetype = "image/webp" if storage_name.endswith(".webp") else "image/jpeg"

    if is_cloudinary_name(storage_name):
        try:
            response = redirect(cloudinary_delivery_url(storage_name, asset_kind), code=302)
        except (ImageStorageConfigurationError, ValueError):
            logger.exception("Could not build Cloudinary delivery URL for %s", storage_name)
            return None
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = cache_control
        return response

    file_path = os.path.join(local_root, storage_name)
    if not os.path.exists(file_path):
        return None
    if accel_prefix and os.environ.get("ENABLE_ACCEL_REDIRECT") == "1":
        response = make_response("")
        response.headers["X-Accel-Redirect"] = f"{accel_prefix.rstrip('/')}/{storage_name}"
        response.headers["Content-Type"] = mimetype
    else:
        response = send_file(file_path, mimetype=mimetype, max_age=300)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = cache_control
    return response

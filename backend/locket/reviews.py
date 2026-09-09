"""Review and Rating system for Locket Gold.

Enforces:
- Completed-service or Admin-verified KOL eligibility (verified reviews only).
- Active rating selection (1-5 stars, no defaults).
- Optional plaintext feedback (maximum 1000 characters).
- Secure image processing via Pillow:
  - Max 3 images per review, max 8MB each.
  - Formats: JPEG, PNG, WEBP.
  - Image.MAX_IMAGE_PIXELS = 20_000_000 (decompression bomb protection).
  - EXIF orientation transposed, metadata stripped.
  - Resized to max 1600x1600, converted to optimized WebP/JPEG.
  - Atomic write via temporary file, .tmp cleaned in finally.
- Auto-published reviews are immediately public; rejected/hidden legacy images remain private.
- Private owner route: GET /api/reviews/me/images/<image_id> for the owner to view current or legacy review images.
- Atomic SQLite transactions with rollback on failure and 409 on UNIQUE constraint.
"""

import io
import json
import logging
import os
import sqlite3
import time
import warnings

from flask import (
    Blueprint,
    abort,
    current_app,
    g,
    jsonify,
    make_response,
    request,
)
from PIL import Image, ImageOps
from werkzeug.utils import secure_filename

from . import db
from .image_storage import (
    ImageStorageConfigurationError,
    ImageStorageUploadError,
    SAFE_STORAGE_NAME,
    delete_stored_image,
    save_processed_image,
    serve_stored_image,
)
from .token_auth import access_required
from .user_auth import add_no_store_headers, get_client_ip, is_rate_limited, validate_csrf

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    # Local/test installations may not need HEIC. Production requirements
    # install pillow-heif so photos selected directly from iPhone are accepted.
    pass

logger = logging.getLogger(__name__)

reviews_bp = Blueprint("reviews", __name__, url_prefix="/api/reviews")

# Pillow safety settings: Convert DecompressionBombWarning to error and cap pixels
warnings.filterwarnings("error", category=Image.DecompressionBombWarning)
Image.MAX_IMAGE_PIXELS = 20_000_000  # 20 Megapixels limit to prevent zip bombs
MAX_IMAGE_SIZE = 8 * 1024 * 1024      # 8MB per mobile photo
MAX_IMAGES_PER_REVIEW = 3
SAFE_FILENAME_REGEX = SAFE_STORAGE_NAME


def get_storage_root() -> str:
    """Resolve storage root lazily from current_app config or environment."""
    try:
        if current_app:
            root = current_app.config.get("REVIEW_STORAGE_ROOT")
            if root:
                return os.path.abspath(root)
    except Exception:
        pass
    env_root = os.environ.get("REVIEW_STORAGE_ROOT")
    if env_root:
        return os.path.abspath(env_root)
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "storage", "reviews")
    )


# Storage root alias for compatibility with external module references
class _StorageRootProxy:
    def __str__(self):
        return get_storage_root()

    def __fspath__(self):
        return get_storage_root()

    def __repr__(self):
        return get_storage_root()

    def __eq__(self, other):
        return str(self) == str(other)


STORAGE_ROOT = _StorageRootProxy()

def invalidate_reviews_cache():
    """Compatibility hook; public reviews are intentionally always fresh."""
    return None


def process_and_save_image(file_storage, target_dir):
    """Safely validate, strip EXIF, resize, and convert image to WebP.

    Enforces:
    - Max 8MB read limit (no unbounded memory read).
    - JPEG, PNG, static WebP, HEIC or HEIF (animated images rejected).
    - Max 20 megapixel image dimensions.
    - EXIF transposed orientation, GPS/device metadata stripped.
    - WebP quality 82, thumbnail resize preserving aspect ratio (no crop).
    - Atomic file write via .tmp file with cleanup in finally.

    Returns:
        (image_meta_dict, error_message)
    """
    try:
        # Other libraries/tests may alter the process-wide warning filters
        # after this module is imported. Reinforce the bomb policy at the
        # point of use so oversized images are always rejected, never warned
        # and processed further.
        warnings.filterwarnings("error", category=Image.DecompressionBombWarning)
        # Stream read up to MAX_IMAGE_SIZE + 1 to prevent unbounded RAM usage
        raw_bytes = file_storage.read(MAX_IMAGE_SIZE + 1)
        if len(raw_bytes) > MAX_IMAGE_SIZE:
            return None, "Kích thước mỗi ảnh không được vượt quá 8MB."
        if len(raw_bytes) < 16:
            return None, "Tệp ảnh không hợp lệ hoặc bị rỗng."
        # If there are more bytes in stream, reject
        extra_chunk = file_storage.read(1)
        if extra_chunk:
            return None, "Kích thước mỗi ảnh không được vượt quá 8MB."

        # Pass 1: Verify format, animation, and dimensions
        try:
            with Image.open(io.BytesIO(raw_bytes)) as check_img:
                fmt = check_img.format
                if fmt not in ("JPEG", "PNG", "WEBP", "HEIF", "HEIC"):
                    return None, f"Định dạng ảnh '{fmt}' không được hỗ trợ. Vui lòng chọn JPG, PNG, WebP hoặc HEIC."

                # Reject animated WebP or GIFs/multi-frame images
                if getattr(check_img, "is_animated", False) or getattr(check_img, "n_frames", 1) > 1:
                    return None, "Ảnh động (animated WebP/GIF) không được hỗ trợ. Vui lòng chọn ảnh tĩnh."

                w, h = check_img.size
                if w * h > 20_000_000:
                    return None, "Kích thước điểm ảnh quá lớn vượt ngưỡng an toàn (tối đa 20 megapixel)."

                check_img.verify()
        except (Image.DecompressionBombError, Image.DecompressionBombWarning):
            return None, "Hình ảnh quá lớn vượt ngưỡng an toàn điểm ảnh (Decompression Bomb)."
        except Exception:
            return None, "Tệp không phải là hình ảnh hợp lệ hoặc dữ liệu bị hỏng."

        # Pass 2: Process & convert to WebP
        with Image.open(io.BytesIO(raw_bytes)) as img:
            w, h = img.size
            if w * h > 20_000_000:
                return None, "Kích thước điểm ảnh quá lớn vượt ngưỡng an toàn (tối đa 20 megapixel)."

            # Transpose orientation according to EXIF before stripping metadata
            try:
                img = ImageOps.exif_transpose(img)
            except Exception:
                pass

            # Convert color space safely
            if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                img = img.convert("RGBA")
            else:
                img = img.convert("RGB")

            # Thumbnail resize: max 1600px edge while strictly preserving aspect ratio (no crop!)
            img.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            width, height = img.size

            # Encode before storage. A JPEG fallback keeps uploads working on
            # minimal Pillow builds that do not include the WebP encoder.
            encoded = io.BytesIO()
            extension = "webp"
            try:
                img.save(encoded, format="WEBP", quality=82, method=6)
            except (KeyError, OSError, ValueError):
                encoded = io.BytesIO()
                if img.mode != "RGB":
                    background = Image.new("RGB", img.size, "white")
                    background.paste(img, mask=img.getchannel("A"))
                    img = background
                img.save(encoded, format="JPEG", quality=88, optimize=True, progressive=True)
                extension = "jpg"

            stored = save_processed_image(
                encoded.getvalue(),
                target_dir,
                extension,
                "review",
            )
            orig_name = secure_filename(file_storage.filename or "image.webp")

            return {
                "storage_name": stored["storage_name"],
                "original_filename": orig_name,
                "file_size": stored["file_size"],
                "mime_type": stored["mime_type"],
                "width": width,
                "height": height,
            }, None

    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        return None, "Hình ảnh quá lớn vượt ngưỡng an toàn điểm ảnh (Decompression Bomb)."
    except ImageStorageConfigurationError as e:
        logger.error("Review image storage is not configured: %s", e)
        return None, str(e)
    except ImageStorageUploadError as e:
        return None, str(e)
    except Exception as e:
        logger.error("Error processing review image: %s", e, exc_info=True)
        return None, "Không thể xử lý tệp hình ảnh. Vui lòng kiểm tra và thử lại với ảnh khác."


# ---- Public Endpoints ----

@reviews_bp.route("", methods=["GET"])
def get_public_reviews():
    """Always-fresh public list of approved reviews with stats and pagination."""
    limit_raw = request.args.get("limit", 12)
    offset_raw = request.args.get("offset", 0)

    try:
        limit = int(limit_raw)
    except (TypeError, ValueError):
        limit = 12
    limit = max(1, min(50, limit))

    try:
        offset = int(offset_raw)
    except (TypeError, ValueError):
        offset = 0
    offset = max(0, offset)

    # Fetch approved reviews from database with pagination and stats over all approved reviews
    result = db.get_approved_reviews(limit=limit, offset=offset)

    # Format image URLs for client consumption
    formatted_reviews = []
    for r in result["reviews"]:
        images = []
        for img in r.get("images", []):
            images.append({
                "id": img["id"],
                "url": f"/api/reviews/images/{img['storage_name']}",
                "width": img.get("width"),
                "height": img.get("height"),
            })
        formatted_reviews.append({
            "id": r["id"],
            "display_name": r.get("display_name") or r.get("masked_username") or "Người dùng Locket",
            "masked_username": r.get("masked_username"),
            "rating": r["rating"],
            "content": r["content"],
            "is_verified": bool(r["is_verified"]),
            "approved_at": r.get("approved_at"),
            "created_at": r["created_at"],
            "images": images,
        })

    payload = {
        "success": True,
        "reviews": formatted_reviews,
        "stats": result["stats"],
        "pagination": result.get("pagination", {
            "total": result["stats"]["total"],
            "limit": limit,
            "offset": offset,
            "has_more": (offset + len(formatted_reviews)) < result["stats"]["total"],
        }),
    }

    resp = make_response(jsonify(payload))
    # Reviews are polled by the landing page. Do not let a browser, reverse
    # proxy, or another worker serve a stale list after a new review is posted.
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    return resp


@reviews_bp.route("/images/<storage_name>", methods=["GET"])
def get_review_image(storage_name):
    """Serve approved review image. Strictly 404 for pending/rejected/hidden images."""
    if not SAFE_FILENAME_REGEX.match(storage_name):
        abort(404)

    # Check database permission & review status
    img_row = db.get_review_image_by_storage_name(storage_name)
    if not img_row:
        abort(404)

    # Public endpoint strictly only serves approved images
    if img_row.get("review_status") != "approved":
        abort(404)

    resp = serve_stored_image(
        storage_name,
        get_storage_root(),
        "review",
        "public, max-age=300, must-revalidate",
        accel_prefix="/protected_reviews",
    )
    if resp is None:
        abort(404)
    return resp


# ---- Authenticated User Endpoints ----

@reviews_bp.route("/me/images/<int:image_id>", methods=["GET"])
@access_required
def get_my_review_image(image_id):
    """Serve review image for the review owner. Allows viewing own pending/rejected/approved images."""
    user_id = g.current_user["id"]
    img_row = db.get_review_image_by_id_and_user(image_id, user_id)
    if not img_row:
        abort(404)

    resp = serve_stored_image(
        img_row["storage_name"],
        get_storage_root(),
        "review",
        "private, no-store",
    )
    if resp is None:
        abort(404)
    return resp


@reviews_bp.route("/me", methods=["GET"])
@access_required
def get_my_review():
    """Get current user's review status and eligibility. Uses private image URLs."""
    user_id = g.current_user["id"]

    is_eligible = db.is_review_eligible(user_id)
    existing_review = db.get_review_by_user_id(user_id)

    formatted_review = None
    if existing_review:
        formatted_images = []
        for img in existing_review.get("images", []):
            formatted_images.append({
                "id": img["id"],
                "url": f"/api/reviews/me/images/{img['id']}",
                "original_filename": img.get("original_filename"),
                "file_size": img.get("file_size"),
                "width": img.get("width"),
                "height": img.get("height"),
            })
        formatted_review = {
            "id": existing_review["id"],
            "rating": existing_review["rating"],
            "content": existing_review["content"],
            "status": existing_review["status"],
            "admin_note": existing_review.get("admin_note"),
            "is_verified": bool(existing_review["is_verified"]),
            "approved_at": existing_review.get("approved_at"),
            "created_at": existing_review["created_at"],
            "updated_at": existing_review["updated_at"],
            "images": formatted_images,
        }

    resp = make_response(jsonify({
        "success": True,
        "eligible": is_eligible,
        "has_review": existing_review is not None,
        "review": formatted_review,
    }))
    return add_no_store_headers(resp)


@reviews_bp.route("", methods=["POST"])
@access_required
def submit_review():
    """Submit a real user review with atomic transaction and rollback."""
    user_id = g.current_user["id"]

    # Rate limiting
    ip = get_client_ip()
    if is_rate_limited(f"rev_submit:{user_id}", max_requests=5, window_seconds=900) or \
       is_rate_limited(f"rev_submit_ip:{ip}", max_requests=10, window_seconds=900):
        resp = make_response(jsonify({
            "success": False,
            "error": "rate_limited",
            "msg": "Bạn thao tác quá nhanh. Vui lòng đợi vài phút trước khi thử lại.",
        }), 429)
        return add_no_store_headers(resp)

    # CSRF Check
    if not validate_csrf():
        resp = make_response(jsonify({
            "success": False,
            "error": "invalid_csrf_token",
            "msg": "Phiên làm việc đã hết hạn hoặc CSRF không hợp lệ. Vui lòng tải lại trang.",
        }), 403)
        return add_no_store_headers(resp)

    # Eligibility: completed service or an Admin-created TikTok/KOL profile.
    if not db.is_review_eligible(user_id):
        resp = make_response(jsonify({
            "success": False,
            "error": "not_eligible",
            "msg": "Bạn cần hoàn tất một lần nâng cấp Locket Gold hoặc được Admin xác thực là TikToker/KOL để gửi đánh giá.",
        }), 403)
        return add_no_store_headers(resp)

    # 1 review per account constraint pre-check
    if db.get_review_by_user_id(user_id):
        resp = make_response(jsonify({
            "success": False,
            "error": "review_already_exists",
            "msg": "Bạn đã gửi đánh giá trước đó. Bạn có thể chỉnh sửa hoặc xóa đánh giá của mình.",
        }), 409)
        return add_no_store_headers(resp)

    # Extract rating & content
    if request.is_json and request.json:
        rating_raw = request.json.get("rating")
        content_raw = request.json.get("content")
    else:
        rating_raw = request.form.get("rating")
        content_raw = request.form.get("content")

    # Validate Rating (active selection required 1-5)
    try:
        rating = int(rating_raw)
        if rating < 1 or rating > 5:
            raise ValueError()
    except (TypeError, ValueError):
        resp = make_response(jsonify({
            "success": False,
            "error": "invalid_rating",
            "msg": "Vui lòng chọn số sao đánh giá hợp lệ từ 1 đến 5 sao.",
        }), 400)
        return add_no_store_headers(resp)

    # Content is optional; keep only the upper bound for storage and abuse control.
    content = (content_raw or "").strip()
    if len(content) > 1000:
        resp = make_response(jsonify({
            "success": False,
            "error": "invalid_content_length",
            "msg": f"Nội dung đánh giá không được vượt quá 1000 ký tự (hiện tại: {len(content)} ký tự).",
        }), 400)
        return add_no_store_headers(resp)

    # Validate and process images
    uploaded_files = [f for f in request.files.getlist("images") if f and f.filename]
    if len(uploaded_files) > MAX_IMAGES_PER_REVIEW:
        for f in uploaded_files:
            try:
                f.close()
            except Exception:
                pass
        resp = make_response(jsonify({
            "success": False,
            "error": "too_many_images",
            "msg": f"Chỉ được tải lên tối đa {MAX_IMAGES_PER_REVIEW} hình ảnh đính kèm.",
        }), 400)
        return add_no_store_headers(resp)

    storage_root = get_storage_root()
    saved_images = []
    try:
        for idx, f in enumerate(uploaded_files):
            meta, err = process_and_save_image(f, storage_root)
            if err:
                for s in saved_images:
                    delete_stored_image(s["storage_name"], storage_root, "review")
                resp = make_response(jsonify({
                    "success": False,
                    "error": "image_processing_failed",
                    "msg": err,
                }), 400)
                return add_no_store_headers(resp)
            meta["sort_order"] = idx
            saved_images.append(meta)
    finally:
        for f in uploaded_files:
            try:
                f.close()
            except Exception:
                pass

    # Atomic transaction to insert review and image records
    conn = db.get_conn()
    conn.execute("BEGIN IMMEDIATE")
    try:
        # Check UNIQUE again inside transaction
        existing = conn.execute("SELECT id FROM reviews WHERE user_id = ?", (user_id,)).fetchone()
        if existing:
            conn.execute("ROLLBACK")
            for s in saved_images:
                delete_stored_image(s["storage_name"], storage_root, "review")
            resp = make_response(jsonify({
                "success": False,
                "error": "review_already_exists",
                "msg": "Bạn đã gửi đánh giá trước đó. Bạn có thể chỉnh sửa hoặc xóa đánh giá của mình.",
            }), 409)
            return add_no_store_headers(resp)

        now = time.time()
        cursor = conn.execute(
            """INSERT INTO reviews (user_id, rating, content, status, is_verified, approved_at, created_at, updated_at)
               VALUES (?, ?, ?, 'approved', 1, ?, ?, ?)""",
            (user_id, rating, content, now, now, now),
        )
        review_id = cursor.lastrowid

        for img in saved_images:
            conn.execute(
                """INSERT INTO review_images
                   (review_id, storage_name, original_filename, file_size, mime_type, width, height, sort_order, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (review_id, img["storage_name"], img["original_filename"], img["file_size"],
                 img["mime_type"], img["width"], img["height"], img["sort_order"], now),
            )

        conn.execute("COMMIT")
    except sqlite3.IntegrityError:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        for s in saved_images:
            delete_stored_image(s["storage_name"], storage_root, "review")
        resp = make_response(jsonify({
            "success": False,
            "error": "review_already_exists",
            "msg": "Bạn đã gửi đánh giá trước đó. Bạn có thể chỉnh sửa hoặc xóa đánh giá của mình.",
        }), 409)
        return add_no_store_headers(resp)
    except Exception as e:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        for s in saved_images:
            delete_stored_image(s["storage_name"], storage_root, "review")
        logger.error("Failed to insert review in transaction: %s", e, exc_info=True)
        resp = make_response(jsonify({
            "success": False,
            "error": "create_failed",
            "msg": "Không thể gửi đánh giá. Vui lòng thử lại sau.",
        }), 500)
        return add_no_store_headers(resp)

    invalidate_reviews_cache()

    resp = make_response(jsonify({
        "success": True,
        "msg": "Đánh giá của bạn đã được đăng công khai thành công.",
        "review_id": review_id,
    }), 201)
    return add_no_store_headers(resp)


@reviews_bp.route("/me", methods=["PUT"])
@access_required
def update_my_review():
    """Update current user's review and images in atomic transaction.
    Supports keeping specific existing images and uploading new images."""
    user_id = g.current_user["id"]

    # CSRF Check
    if not validate_csrf():
        resp = make_response(jsonify({
            "success": False,
            "error": "invalid_csrf_token",
            "msg": "Phiên làm việc đã hết hạn hoặc CSRF không hợp lệ. Vui lòng tải lại trang.",
        }), 403)
        return add_no_store_headers(resp)

    review = db.get_review_by_user_id(user_id)
    if not review:
        resp = make_response(jsonify({
            "success": False,
            "error": "not_found",
            "msg": "Bạn chưa có đánh giá nào để chỉnh sửa.",
        }), 404)
        return add_no_store_headers(resp)

    if request.is_json and request.json:
        rating_raw = request.json.get("rating")
        content_raw = request.json.get("content")
        raw_keep = request.json.get("keep_image_ids", [])
    else:
        rating_raw = request.form.get("rating")
        content_raw = request.form.get("content")
        raw_keep = request.form.getlist("keep_image_ids")
        if not raw_keep and request.form.get("keep_image_ids"):
            val = request.form.get("keep_image_ids")
            try:
                parsed = json.loads(val)
                if isinstance(parsed, list):
                    raw_keep = parsed
            except Exception:
                raw_keep = [x.strip() for x in val.split(",") if x.strip().isdigit()]

    # Validate Rating
    try:
        rating = int(rating_raw)
        if rating < 1 or rating > 5:
            raise ValueError()
    except (TypeError, ValueError):
        resp = make_response(jsonify({
            "success": False,
            "error": "invalid_rating",
            "msg": "Vui lòng chọn số sao đánh giá hợp lệ từ 1 đến 5 sao.",
        }), 400)
        return add_no_store_headers(resp)

    # Content is optional; keep only the upper bound for storage and abuse control.
    content = (content_raw or "").strip()
    if len(content) > 1000:
        resp = make_response(jsonify({
            "success": False,
            "error": "invalid_content_length",
            "msg": f"Nội dung đánh giá không được vượt quá 1000 ký tự (hiện tại: {len(content)} ký tự).",
        }), 400)
        return add_no_store_headers(resp)

    # Parse and validate keep_image_ids against user's actual review images
    existing_images = review.get("images", [])
    valid_existing_ids = {img["id"]: img for img in existing_images}

    keep_ids = []
    if raw_keep is not None:
        for k in raw_keep:
            try:
                kid = int(k)
                if kid not in valid_existing_ids:
                    resp = make_response(jsonify({
                        "success": False,
                        "error": "invalid_image_id",
                        "msg": "Danh sách hình ảnh giữ lại không hợp lệ.",
                    }), 400)
                    return add_no_store_headers(resp)
                if kid not in keep_ids:
                    keep_ids.append(kid)
            except (TypeError, ValueError):
                pass

    uploaded_files = [f for f in request.files.getlist("images") if f and f.filename]
    if len(keep_ids) + len(uploaded_files) > MAX_IMAGES_PER_REVIEW:
        for f in uploaded_files:
            try:
                f.close()
            except Exception:
                pass
        resp = make_response(jsonify({
            "success": False,
            "error": "too_many_images",
            "msg": f"Tổng số ảnh giữ lại và ảnh mới không được vượt quá {MAX_IMAGES_PER_REVIEW} ảnh.",
        }), 400)
        return add_no_store_headers(resp)

    # Process new images to storage
    storage_root = get_storage_root()
    new_saved_images = []
    try:
        for idx, f in enumerate(uploaded_files):
            meta, err = process_and_save_image(f, storage_root)
            if err:
                for s in new_saved_images:
                    delete_stored_image(s["storage_name"], storage_root, "review")
                resp = make_response(jsonify({
                    "success": False,
                    "error": "image_processing_failed",
                    "msg": err,
                }), 400)
                return add_no_store_headers(resp)
            new_saved_images.append(meta)
    finally:
        for f in uploaded_files:
            try:
                f.close()
            except Exception:
                pass

    # Determine unkept images to delete
    images_to_delete = [img for img in existing_images if img["id"] not in keep_ids]

    # Database transaction
    conn = db.get_conn()
    conn.execute("BEGIN IMMEDIATE")
    try:
        now = time.time()
        # 1. Updates are published immediately; no moderation queue is required.
        conn.execute(
            """UPDATE reviews
               SET rating = ?, content = ?, status = 'approved', approved_at = ?, updated_at = ?
               WHERE id = ?""",
            (rating, content, now, now, review["id"]),
        )

        # 2. Delete unkept image rows
        for old_img in images_to_delete:
            conn.execute("DELETE FROM review_images WHERE id = ? AND review_id = ?", (old_img["id"], review["id"]))

        # 3. Re-index sort order for kept images
        for idx, kid in enumerate(keep_ids):
            conn.execute("UPDATE review_images SET sort_order = ? WHERE id = ?", (idx, kid))

        # 4. Insert newly saved images
        start_sort = len(keep_ids)
        for idx, img in enumerate(new_saved_images):
            conn.execute(
                """INSERT INTO review_images
                   (review_id, storage_name, original_filename, file_size, mime_type, width, height, sort_order, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (review["id"], img["storage_name"], img["original_filename"], img["file_size"],
                 img["mime_type"], img["width"], img["height"], start_sort + idx, now),
            )

        conn.execute("COMMIT")
    except Exception as e:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        for s in new_saved_images:
            delete_stored_image(s["storage_name"], storage_root, "review")
        logger.error("Failed to update review in transaction: %s", e, exc_info=True)
        resp = make_response(jsonify({
            "success": False,
            "error": "update_failed",
            "msg": "Không thể cập nhật đánh giá. Vui lòng thử lại sau.",
        }), 500)
        return add_no_store_headers(resp)

    # ONLY after transaction commit succeeds: clean up old unkept files from disk
    for old_img in images_to_delete:
        delete_stored_image(old_img["storage_name"], storage_root, "review")

    invalidate_reviews_cache()

    resp = make_response(jsonify({
        "success": True,
        "msg": "Đánh giá của bạn đã được cập nhật và hiển thị công khai.",
    }))
    return add_no_store_headers(resp)


@reviews_bp.route("/me", methods=["DELETE"])
@access_required
def delete_my_review():
    """Delete current user's review and images in atomic transaction."""
    user_id = g.current_user["id"]

    # CSRF Check
    if not validate_csrf():
        resp = make_response(jsonify({
            "success": False,
            "error": "invalid_csrf_token",
            "msg": "Phiên làm việc đã hết hạn hoặc CSRF không hợp lệ. Vui lòng tải lại trang.",
        }), 403)
        return add_no_store_headers(resp)

    review = db.get_review_by_user_id(user_id)
    if not review:
        resp = make_response(jsonify({
            "success": False,
            "error": "not_found",
            "msg": "Bạn chưa có đánh giá nào để xóa.",
        }), 404)
        return add_no_store_headers(resp)

    storage_root = get_storage_root()
    storage_names = []

    conn = db.get_conn()
    conn.execute("BEGIN IMMEDIATE")
    try:
        img_rows = conn.execute("SELECT storage_name FROM review_images WHERE review_id = ?", (review["id"],)).fetchall()
        storage_names = [r["storage_name"] for r in img_rows]

        cursor = conn.execute("DELETE FROM reviews WHERE id = ? AND user_id = ?", (review["id"], user_id))
        if cursor.rowcount == 0:
            conn.execute("ROLLBACK")
            resp = make_response(jsonify({
                "success": False,
                "error": "not_found",
                "msg": "Bạn chưa có đánh giá nào để xóa.",
            }), 404)
            return add_no_store_headers(resp)

        conn.execute("COMMIT")
    except Exception as e:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        logger.error("Failed to delete review in transaction: %s", e, exc_info=True)
        resp = make_response(jsonify({
            "success": False,
            "error": "delete_failed",
            "msg": "Không thể xóa đánh giá. Vui lòng thử lại sau.",
        }), 500)
        return add_no_store_headers(resp)

    # ONLY after transaction commit succeeds: clean up physical files
    for name in storage_names:
        delete_stored_image(name, storage_root, "review")

    invalidate_reviews_cache()

    resp = make_response(jsonify({
        "success": True,
        "msg": "Đánh giá của bạn đã được xóa thành công. Bạn có thể gửi lại đánh giá mới bất cứ lúc nào.",
    }))
    return add_no_store_headers(resp)

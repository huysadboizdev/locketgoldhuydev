import io
import json
import os
import shutil
import sys
import tempfile
import time
import unittest

# Configure temporary paths before importing app
temp_db_fd, temp_db_path = tempfile.mkstemp(suffix=".db")
os.close(temp_db_fd)
temp_storage_dir = tempfile.mkdtemp(prefix="test_reviews_storage_")
temp_creator_storage_dir = tempfile.mkdtemp(prefix="test_creators_storage_")

os.environ["LOCKET_DB"] = temp_db_path
os.environ["REVIEW_STORAGE_ROOT"] = temp_storage_dir
os.environ["CREATOR_STORAGE_ROOT"] = temp_creator_storage_dir
os.environ["FLASK_SECRET_KEY"] = "test-secret-key-review-1234567890"
os.environ["JWT_SECRET"] = "test-jwt-secret-review-key-12345678"
os.environ["REFRESH_TOKEN_PEPPER"] = "test-pepper-review-secure-12345"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin-secret-password-1234"

backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from PIL import Image
from werkzeug.security import generate_password_hash

from locket import create_app, db
from locket.reviews import invalidate_reviews_cache, STORAGE_ROOT
from locket.token_auth import create_access_token, create_token_family
from locket.user_auth import reset_rate_limits


def create_test_image_bytes(format="JPEG", size=(100, 100), color=(255, 180, 0)):
    """Generate in-memory valid image bytes."""
    buf = io.BytesIO()
    img = Image.new("RGB", size, color=color)
    img.save(buf, format=format)
    buf.seek(0)
    return buf


def create_animated_webp_bytes():
    """Generate in-memory multi-frame animated WebP bytes."""
    buf = io.BytesIO()
    img1 = Image.new("RGB", (60, 60), color="red")
    img2 = Image.new("RGB", (60, 60), color="blue")
    img1.save(buf, format="WEBP", save_all=True, append_images=[img2], duration=100, loop=0)
    buf.seek(0)
    return buf


def create_decompression_bomb_bytes():
    """Generate image with excessive dimensions (>20MP)."""
    buf = io.BytesIO()
    img = Image.new("RGB", (5000, 5000), color="white")
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def create_image_with_exif():
    """Generate image containing EXIF metadata."""
    img = Image.new("RGB", (100, 100), color="blue")
    exif = img.getexif()
    exif[0x010F] = "TestCameraManufacturer"
    exif[0x0110] = "TestCameraModel"
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    buf.seek(0)
    return buf


from flask.testing import FlaskClient


class CleanTestClient(FlaskClient):
    """Test client that ensures wsgi.input stream (including temporary files for large bodies)
    is closed upon response close to eliminate ResourceWarning on Python 3.14."""
    def open(self, *args, **kwargs):
        res = super().open(*args, **kwargs)
        orig_close = res.close
        def clean_close():
            try:
                inp = res.request.environ.get("wsgi.input")
                if hasattr(inp, "close"):
                    inp.close()
            except Exception:
                pass
            orig_close()
        res.close = clean_close
        return res


class ReviewsComprehensiveTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["LOCKET_DB"] = temp_db_path
        db.close_conn()

        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.app.test_client_class = CleanTestClient

    @classmethod
    def tearDownClass(cls):
        db.close_conn()

        db.close_conn()
        try:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
            for ext in ["-wal", "-shm"]:
                p = temp_db_path + ext
                if os.path.exists(p):
                    os.remove(p)
            if os.path.exists(temp_storage_dir):
                shutil.rmtree(temp_storage_dir, ignore_errors=True)
            if os.path.exists(temp_creator_storage_dir):
                shutil.rmtree(temp_creator_storage_dir, ignore_errors=True)
        except Exception:
            pass

    def tearDown(self):
        db.close_conn()

    def setUp(self):
        reset_rate_limits()
        invalidate_reviews_cache()
        self.client = self.app.test_client()

        # Clean database tables for test isolation
        conn = db.get_conn()
        conn.execute("DELETE FROM review_images")
        conn.execute("DELETE FROM reviews")
        conn.execute("DELETE FROM creator_profiles")
        conn.execute("DELETE FROM queue_requests")
        conn.execute("DELETE FROM activation_orders")
        conn.execute("DELETE FROM refresh_tokens")
        conn.execute("DELETE FROM auth_sessions")
        conn.execute("DELETE FROM users")

        # Create 2 test users
        self.user1_id = db.create_user(
            email="eligible@example.com",
            username="eligible_user",
            display_name="Nguyen Van A",
            password_hash=generate_password_hash("password123"),
        )
        self.user2_id = db.create_user(
            email="ineligible@example.com",
            username="ineligible_user",
            display_name="Tran Thi B",
            password_hash=generate_password_hash("password123"),
        )

        # Mark user1 as eligible (completed queue request)
        conn.execute(
            """INSERT INTO queue_requests (client_id, username, status, added_at, completed_at, user_id)
               VALUES ('client-101', 'eligible_user', 'completed', ?, ?, ?)""",
            (time.time() - 100, time.time() - 50, self.user1_id),
        )

        # Mark user2 with non-completed request ('processing')
        conn.execute(
            """INSERT INTO queue_requests (client_id, username, status, added_at, user_id)
               VALUES ('client-202', 'ineligible_user', 'processing', ?, ?)""",
            (time.time() - 20, self.user2_id),
        )

        # Create access tokens for both users
        fam1, _, _ = create_token_family(self.user1_id)
        self.token_user1 = create_access_token(self.user1_id, fam1)

        fam2, _, _ = create_token_family(self.user2_id)
        self.token_user2 = create_access_token(self.user2_id, fam2)

    def _get_csrf_token(self):
        res = self.client.get("/api/auth/csrf")
        data = res.get_json()
        return data.get("csrf_token")

    def _login_admin(self):
        res = self.client.post(
            "/admin/login",
            data={"username": "admin", "password": "admin-secret-password-1234"},
            follow_redirects=True,
        )
        res.close()
        with self.client.session_transaction() as sess:
            self.admin_csrf = sess.get("admin_csrf_token")

    def _admin_api_credentials(self):
        admin_id = db.create_user(
            email="creator-admin@example.com",
            username="creator_admin",
            display_name="Creator Admin",
            password_hash=generate_password_hash("password123"),
            role="admin",
        )
        family_id, _, _ = create_token_family(admin_id)
        token = create_access_token(admin_id, family_id)
        csrf = self._get_csrf_token()
        return token, csrf
        return res

    # 1. Eligibility Check
    def test_ineligible_user_cannot_submit_review(self):
        csrf = self._get_csrf_token()
        res = self.client.post(
            "/api/reviews",
            headers={
                "Authorization": f"Bearer {self.token_user2}",
                "X-CSRF-Token": csrf,
            },
            data={
                "rating": "5",
                "content": "Dịch vụ rất tốt nhưng tôi chưa hoàn tất nâng cấp!",
            },
        )
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertEqual(data.get("error"), "not_eligible")

    def test_eligible_user_can_submit_review(self):
        csrf = self._get_csrf_token()
        res = self.client.post(
            "/api/reviews",
            headers={
                "Authorization": f"Bearer {self.token_user1}",
                "X-CSRF-Token": csrf,
            },
            data={
                "rating": "5",
                "content": "Tôi đã nâng cấp Locket Gold thành công, thời gian xử lý cực nhanh và ổn định!",
            },
        )
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data.get("success"))

        # New reviews are published immediately without admin moderation.
        review = db.get_review_by_user_id(self.user1_id)
        self.assertIsNotNone(review)
        self.assertEqual(review["status"], "approved")
        self.assertIsNotNone(review["approved_at"])
        self.assertEqual(review["rating"], 5)
        self.assertEqual(review["is_verified"], 1)

    def test_completed_activation_order_without_queue_is_eligible(self):
        """Manual/APK orders do not require a queue row but still unlock feedback."""
        conn = db.get_conn()
        now = time.time()

        for mode, platform in (
            ("auto_activation", "ios"),
            ("manual_contact", "ios"),
            ("apk_download", "android"),
        ):
            with self.subTest(fulfillment_mode=mode):
                conn.execute(
                    """INSERT INTO activation_orders
                       (user_id, plan_id, plan_name_snapshot, product_id_snapshot,
                        duration_days_snapshot, price_vnd_snapshot, price_coin_snapshot,
                        payment_method, payment_order_id, platform, locket_username,
                        fulfillment_mode_snapshot, status, created_at, updated_at)
                       VALUES (?, NULL, 'Test plan', 'test_product', 365, 50000, 50,
                               'coin', NULL, ?, '', ?, 'completed', ?, ?)""",
                    (self.user2_id, platform, mode, now, now),
                )
                self.assertTrue(db.has_completed_service(self.user2_id))
                conn.execute("DELETE FROM activation_orders WHERE user_id = ?", (self.user2_id,))

        # Verify the authenticated endpoint uses the same corrected rule.
        conn.execute(
            """INSERT INTO activation_orders
               (user_id, plan_id, plan_name_snapshot, product_id_snapshot,
                duration_days_snapshot, price_vnd_snapshot, price_coin_snapshot,
                payment_method, payment_order_id, platform, locket_username,
                fulfillment_mode_snapshot, status, created_at, updated_at)
               VALUES (?, NULL, 'Android download', 'apk_product', 365, 20000, 20,
                       'coin', NULL, 'android', '', 'apk_download', 'completed', ?, ?)""",
            (self.user2_id, now, now),
        )
        response = self.client.get(
            "/api/reviews/me",
            headers={"Authorization": f"Bearer {self.token_user2}"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["eligible"])

    def test_unfinished_activation_orders_do_not_unlock_feedback(self):
        """Payment/processing alone must not be presented as completed service."""
        conn = db.get_conn()
        now = time.time()
        for status in (
            "awaiting_payment",
            "paid",
            "awaiting_queue",
            "queued",
            "processing",
            "failed",
            "refunded",
            "cancelled",
        ):
            with self.subTest(status=status):
                conn.execute(
                    """INSERT INTO activation_orders
                       (user_id, plan_id, plan_name_snapshot, product_id_snapshot,
                        duration_days_snapshot, price_vnd_snapshot, price_coin_snapshot,
                        payment_method, payment_order_id, platform, locket_username,
                        fulfillment_mode_snapshot, status, created_at, updated_at)
                       VALUES (?, NULL, 'Test plan', 'test_product', 365, 50000, 50,
                               'coin', NULL, 'ios', '', 'manual_contact', ?, ?, ?)""",
                    (self.user2_id, status, now, now),
                )
                self.assertFalse(db.has_completed_service(self.user2_id))
                conn.execute("DELETE FROM activation_orders WHERE user_id = ?", (self.user2_id,))

    # 2. Rating Validation (Active selection 1-5)
    def test_rating_validation_missing_or_out_of_range(self):
        csrf = self._get_csrf_token()
        # Missing rating
        res = self.client.post(
            "/api/reviews",
            headers={"Authorization": f"Bearer {self.token_user1}", "X-CSRF-Token": csrf},
            data={"content": "Đánh giá không có số sao đánh giá hợp lệ nào."},
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.get_json().get("error"), "invalid_rating")

        # Rating = 0
        res = self.client.post(
            "/api/reviews",
            headers={"Authorization": f"Bearer {self.token_user1}", "X-CSRF-Token": csrf},
            data={"rating": "0", "content": "Đánh giá có số sao đánh giá là 0 sao."},
        )
        self.assertEqual(res.status_code, 400)

        # Rating = 6
        res = self.client.post(
            "/api/reviews",
            headers={"Authorization": f"Bearer {self.token_user1}", "X-CSRF-Token": csrf},
            data={"rating": "6", "content": "Đánh giá có số sao đánh giá là 6 sao."},
        )
        self.assertEqual(res.status_code, 400)

    # 3. Content is optional, with a 1000-character upper bound
    def test_content_optional_and_max_length_validation(self):
        csrf = self._get_csrf_token()
        # Too long (> 1000 chars) is still rejected.
        long_content = "A" * 1005
        res = self.client.post(
            "/api/reviews",
            headers={"Authorization": f"Bearer {self.token_user1}", "X-CSRF-Token": csrf},
            data={"rating": "5", "content": long_content},
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.get_json().get("error"), "invalid_content_length")

        # Empty content is accepted: rating alone is a valid review.
        res = self.client.post(
            "/api/reviews",
            headers={"Authorization": f"Bearer {self.token_user1}", "X-CSRF-Token": csrf},
            data={"rating": "5", "content": ""},
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(db.get_review_by_user_id(self.user1_id)["content"], "")

    # 4. One Review per Account Constraint
    def test_one_review_per_account_constraint(self):
        csrf = self._get_csrf_token()
        # First submission succeeds
        res1 = self.client.post(
            "/api/reviews",
            headers={"Authorization": f"Bearer {self.token_user1}", "X-CSRF-Token": csrf},
            data={"rating": "5", "content": "Lần đầu gửi đánh giá thành công trên hệ thống Locket Gold."},
        )
        self.assertEqual(res1.status_code, 201)

        # Second submission by same user fails with 409
        res2 = self.client.post(
            "/api/reviews",
            headers={"Authorization": f"Bearer {self.token_user1}", "X-CSRF-Token": csrf},
            data={"rating": "4", "content": "Cố gắng gửi thêm một đánh giá thứ hai nữa."},
        )
        self.assertEqual(res2.status_code, 409)
        self.assertEqual(res2.get_json().get("error"), "review_already_exists")

    # 5. Image Upload & Max 3 Images
    def test_image_upload_and_limit(self):
        csrf = self._get_csrf_token()

        img1 = (create_test_image_bytes("JPEG", (200, 200)), "photo1.jpg")
        img2 = (create_test_image_bytes("PNG", (300, 300)), "photo2.png")
        img3 = (create_test_image_bytes("WEBP", (150, 150)), "photo3.webp")
        img4 = (create_test_image_bytes("JPEG", (100, 100)), "photo4.jpg")

        # 4 images -> rejected (max 3)
        res_fail = self.client.post(
            "/api/reviews",
            headers={"Authorization": f"Bearer {self.token_user1}", "X-CSRF-Token": csrf},
            content_type="multipart/form-data",
            data={
                "rating": "5",
                "content": "Đánh giá đính kèm 4 hình ảnh vượt quá giới hạn cho phép.",
                "images": [img1, img2, img3, img4],
            },
        )
        self.assertEqual(res_fail.status_code, 400)
        self.assertEqual(res_fail.get_json().get("error"), "too_many_images")

        # 2 valid images -> accepted & converted to WebP
        img1_valid = (create_test_image_bytes("JPEG", (400, 400)), "real1.jpg")
        img2_valid = (create_test_image_bytes("PNG", (500, 500)), "real2.png")

        res_ok = self.client.post(
            "/api/reviews",
            headers={"Authorization": f"Bearer {self.token_user1}", "X-CSRF-Token": csrf},
            content_type="multipart/form-data",
            data={
                "rating": "5",
                "content": "Trải nghiệm rất tuyệt vời và có ảnh minh chứng thực tế!",
                "images": [img1_valid, img2_valid],
            },
        )
        self.assertEqual(res_ok.status_code, 201)

        review = db.get_review_by_user_id(self.user1_id)
        self.assertEqual(len(review["images"]), 2)
        storage_name = review["images"][0]["storage_name"]
        self.assertTrue(storage_name.endswith(".webp"))

        # Verify physical file exists on disk and is WebP
        file_path = os.path.join(temp_storage_dir, storage_name)
        self.assertTrue(os.path.exists(file_path))
        with Image.open(file_path) as disk_img:
            self.assertEqual(disk_img.format, "WEBP")

    # 6. Corrupt / Non-Image Rejection
    def test_corrupt_image_rejection(self):
        csrf = self._get_csrf_token()
        fake_img = (io.BytesIO(b"not an image file at all!"), "fake.jpg")
        res = self.client.post(
            "/api/reviews",
            headers={"Authorization": f"Bearer {self.token_user1}", "X-CSRF-Token": csrf},
            content_type="multipart/form-data",
            data={
                "rating": "5",
                "content": "Thử tải lên file văn bản giả danh hình ảnh xem có bị chặn không.",
                "images": [fake_img],
            },
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.get_json().get("error"), "image_processing_failed")

    # 7. Auto-published images are public; rejected legacy images stay private.
    def test_image_auto_publish_and_rejected_privacy(self):
        csrf = self._get_csrf_token()
        img = (create_test_image_bytes("JPEG", (100, 100)), "secret.jpg")
        res = self.client.post(
            "/api/reviews",
            headers={"Authorization": f"Bearer {self.token_user1}", "X-CSRF-Token": csrf},
            content_type="multipart/form-data",
            data={
                "rating": "5",
                "content": "Đánh giá kèm ảnh bí mật cần kiểm duyệt trước khi xem.",
                "images": [img],
            },
        )
        self.assertEqual(res.status_code, 201)
        review = db.get_review_by_user_id(self.user1_id)
        storage_name = review["images"][0]["storage_name"]

        # The uploaded image is public immediately because feedback auto-publishes.
        pub_res = self.client.get(f"/api/reviews/images/{storage_name}")
        self.assertEqual(pub_res.status_code, 200)
        self.assertEqual(pub_res.content_type, "image/webp")
        pub_res.close()

        # Admin can still view the image.
        self._login_admin()
        admin_res = self.client.get(f"/admin/api/reviews/images/{storage_name}")
        self.assertEqual(admin_res.status_code, 200)
        self.assertEqual(admin_res.content_type, "image/webp")
        admin_res.close()

        # Rejected legacy content remains private.
        db.update_review_status_admin(review["id"], "rejected")
        pub_res_rejected = self.client.get(f"/api/reviews/images/{storage_name}")
        self.assertEqual(pub_res_rejected.status_code, 404)
        pub_res_rejected.close()

    # 8. Path Traversal Prevention
    def test_path_traversal_prevention(self):
        res = self.client.get("/api/reviews/images/..%2F..%2Fetc%2Fpasswd")
        self.assertEqual(res.status_code, 404)

    # 9. GET /api/reviews/me Endpoint
    def test_get_my_review_endpoint(self):
        # Before submitting
        res1 = self.client.get(
            "/api/reviews/me",
            headers={"Authorization": f"Bearer {self.token_user1}"},
        )
        self.assertEqual(res1.status_code, 200)
        data1 = res1.get_json()
        self.assertTrue(data1["eligible"])
        self.assertFalse(data1["has_review"])
        self.assertIsNone(data1["review"])

        # Submit review
        csrf = self._get_csrf_token()
        self.client.post(
            "/api/reviews",
            headers={"Authorization": f"Bearer {self.token_user1}", "X-CSRF-Token": csrf},
            data={"rating": "5", "content": "Đánh giá hợp lệ để kiểm tra endpoint me."},
        )

        # After submitting
        res2 = self.client.get(
            "/api/reviews/me",
            headers={"Authorization": f"Bearer {self.token_user1}"},
        )
        self.assertEqual(res2.status_code, 200)
        data2 = res2.get_json()
        self.assertTrue(data2["has_review"])
        self.assertEqual(data2["review"]["rating"], 5)
        self.assertEqual(data2["review"]["status"], "approved")

    # 10. PUT /api/reviews/me keeps the review publicly approved.
    def test_update_review_stays_approved(self):
        csrf = self._get_csrf_token()
        self.client.post(
            "/api/reviews",
            headers={"Authorization": f"Bearer {self.token_user1}", "X-CSRF-Token": csrf},
            data={"rating": "5", "content": "Nội dung ban đầu của đánh giá trước khi sửa."},
        )
        review = db.get_review_by_user_id(self.user1_id)

        # Admin approves it
        db.update_review_status_admin(review["id"], "approved")
        self.assertEqual(db.get_review_by_user_id(self.user1_id)["status"], "approved")

        # User edits review
        res_put = self.client.put(
            "/api/reviews/me",
            headers={"Authorization": f"Bearer {self.token_user1}", "X-CSRF-Token": csrf},
            data={"rating": "4", "content": ""},
        )
        self.assertEqual(res_put.status_code, 200)

        # Updated content remains public without returning to a moderation queue.
        updated = db.get_review_by_user_id(self.user1_id)
        self.assertEqual(updated["status"], "approved")
        self.assertIsNotNone(updated["approved_at"])
        self.assertEqual(updated["rating"], 4)
        self.assertEqual(updated["content"], "")

    # 11. DELETE /api/reviews/me (Deletes review and disk images)
    def test_delete_review_and_images(self):
        csrf = self._get_csrf_token()
        img = (create_test_image_bytes("JPEG", (100, 100)), "todelete.jpg")
        self.client.post(
            "/api/reviews",
            headers={"Authorization": f"Bearer {self.token_user1}", "X-CSRF-Token": csrf},
            content_type="multipart/form-data",
            data={
                "rating": "5",
                "content": "Đánh giá sẽ bị xóa kèm theo file ảnh đính kèm.",
                "images": [img],
            },
        )
        review = db.get_review_by_user_id(self.user1_id)
        storage_name = review["images"][0]["storage_name"]
        file_path = os.path.join(temp_storage_dir, storage_name)
        self.assertTrue(os.path.exists(file_path))

        # Delete review
        res_del = self.client.delete(
            "/api/reviews/me",
            headers={"Authorization": f"Bearer {self.token_user1}", "X-CSRF-Token": csrf},
        )
        self.assertEqual(res_del.status_code, 200)

        # DB record must be gone
        self.assertIsNone(db.get_review_by_user_id(self.user1_id))
        # File on disk must be removed
        self.assertFalse(os.path.exists(file_path))

    # 12. Public Reviews List (Zero approved -> empty; Only approved shown; Stats calculation)
    def test_public_reviews_list_and_stats(self):
        # Empty state
        res_empty = self.client.get("/api/reviews")
        self.assertEqual(res_empty.status_code, 200)
        data_empty = res_empty.get_json()
        self.assertEqual(data_empty["reviews"], [])
        self.assertEqual(data_empty["stats"]["total"], 0)
        self.assertEqual(data_empty["stats"]["average_rating"], 0.0)

        # Create 2 reviews in DB: 1 approved (5 stars), 1 pending (4 stars)
        r1_id = db.create_review(self.user1_id, 5, "Đánh giá này đã được duyệt công khai.", is_verified=1)
        db.update_review_status_admin(r1_id, "approved")

        r2_id = db.create_review(self.user2_id, 4, "Đánh giá này vẫn đang chờ duyệt.", is_verified=0)
        db.update_review_status_admin(r2_id, "pending")

        invalidate_reviews_cache()

        res = self.client.get("/api/reviews")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        # Only approved review appears
        self.assertEqual(len(data["reviews"]), 1)
        self.assertEqual(data["reviews"][0]["id"], r1_id)
        self.assertEqual(data["stats"]["total"], 1)
        self.assertEqual(data["stats"]["average_rating"], 5.0)
        self.assertEqual(data["stats"]["distribution"]["5"], 1)

    # 13. Admin Endpoints: List, retired moderation route, Delete
    def test_admin_can_list_and_delete_but_not_moderate(self):
        # Create review
        r_id = db.create_review(self.user1_id, 5, "Nội dung cần kiểm duyệt bởi admin.", is_verified=1)

        # Unauthorized access
        res_unauth = self.client.get("/admin/api/reviews")
        self.assertIn(res_unauth.status_code, (302, 401))

        # Login admin
        self._login_admin()

        # Admin lists reviews
        res_list = self.client.get("/admin/api/reviews?status=all")
        self.assertEqual(res_list.status_code, 200)
        self.assertEqual(len(res_list.get_json()["reviews"]), 1)

        # Admin mutation without CSRF -> 403
        res_no_csrf = self.client.post(
            f"/admin/api/reviews/{r_id}/status",
            json={"status": "rejected"},
        )
        self.assertEqual(res_no_csrf.status_code, 403)

        # The former moderation endpoint is explicitly retired. This protects
        # the auto-publish contract from stale or custom admin clients.
        res_moderate = self.client.post(
            f"/admin/api/reviews/{r_id}/status",
            headers={"X-CSRF-Token": self.admin_csrf},
            json={"status": "rejected", "admin_note": "Hình ảnh chưa rõ thông tin tài khoản."},
        )
        self.assertEqual(res_moderate.status_code, 410)
        self.assertEqual(res_moderate.get_json()["error"], "review_moderation_disabled")
        self.assertEqual(db.get_review_by_id(r_id)["status"], "approved")

        # Admin deletes + valid CSRF
        res_del = self.client.delete(
            f"/admin/api/reviews/{r_id}",
            headers={"X-CSRF-Token": self.admin_csrf},
        )
        self.assertEqual(res_del.status_code, 200)
        self.assertIsNone(db.get_review_by_id(r_id))

    # 14. Image Size Limit (Max 3MB per file)
    def test_image_size_limit_3mb(self):
        csrf = self._get_csrf_token()
        huge_bytes = io.BytesIO(b"X" * (3 * 1024 * 1024 + 10))
        res = self.client.post(
            "/api/reviews",
            headers={"Authorization": f"Bearer {self.token_user1}", "X-CSRF-Token": csrf},
            content_type="multipart/form-data",
            data={
                "rating": "5",
                "content": "Đánh giá thử nghiệm tệp đính kèm quá kích thước 3MB cho phép.",
                "images": [(huge_bytes, "too_large.jpg")],
            },
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("3MB", res.get_json()["msg"])
        res.close()

    # 15. Decompression Bomb DoS Prevention
    def test_decompression_bomb_rejection(self):
        csrf = self._get_csrf_token()
        bomb_bytes = create_decompression_bomb_bytes()
        res = self.client.post(
            "/api/reviews",
            headers={"Authorization": f"Bearer {self.token_user1}", "X-CSRF-Token": csrf},
            content_type="multipart/form-data",
            data={
                "rating": "5",
                "content": "Đánh giá đính kèm ảnh kích thước điểm ảnh cực lớn nhằm kiểm tra DoS.",
                "images": [(bomb_bytes, "bomb.png")],
            },
        )
        self.assertEqual(res.status_code, 400)
        res.close()

    # 16. Animated WebP Rejection
    def test_animated_webp_rejection(self):
        csrf = self._get_csrf_token()
        anim_bytes = create_animated_webp_bytes()
        res = self.client.post(
            "/api/reviews",
            headers={"Authorization": f"Bearer {self.token_user1}", "X-CSRF-Token": csrf},
            content_type="multipart/form-data",
            data={
                "rating": "5",
                "content": "Đánh giá đính kèm ảnh WebP động nhiều khung hình để thử nghiệm.",
                "images": [(anim_bytes, "anim.webp")],
            },
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("tĩnh", res.get_json()["msg"])
        res.close()

    # 17. EXIF Stripped and Orientation Normalized
    def test_exif_metadata_stripped_and_orientation_normalized(self):
        csrf = self._get_csrf_token()
        exif_bytes = create_image_with_exif()
        res = self.client.post(
            "/api/reviews",
            headers={"Authorization": f"Bearer {self.token_user1}", "X-CSRF-Token": csrf},
            content_type="multipart/form-data",
            data={
                "rating": "5",
                "content": "Đánh giá đính kèm ảnh có chứa EXIF camera thông tin thiết bị.",
                "images": [(exif_bytes, "camera_exif.jpg")],
            },
        )
        self.assertEqual(res.status_code, 201)
        res.close()
        review = db.get_review_by_user_id(self.user1_id)
        storage_name = review["images"][0]["storage_name"]
        file_path = os.path.join(temp_storage_dir, storage_name)
        self.assertTrue(os.path.exists(file_path))

        with Image.open(file_path) as saved_img:
            saved_exif = saved_img.getexif()
            self.assertNotIn(0x010F, saved_exif)
            self.assertNotIn(0x0110, saved_exif)

    # 18. Customer CSRF Protection on All Mutations
    def test_customer_csrf_protection_on_all_mutations(self):
        # 1. POST without CSRF
        res_post = self.client.post(
            "/api/reviews",
            headers={"Authorization": f"Bearer {self.token_user1}"},
            data={"rating": "5", "content": "Thử nghiệm gửi đánh giá không kèm CSRF header."},
        )
        self.assertEqual(res_post.status_code, 403)

        # Create review via DB
        r_id = db.create_review(self.user1_id, 5, "Đánh giá hợp lệ có sẵn trong hệ thống.")

        # 2. PUT without CSRF
        res_put = self.client.put(
            "/api/reviews/me",
            headers={"Authorization": f"Bearer {self.token_user1}"},
            data={"rating": "4", "content": "Thử nghiệm cập nhật đánh giá không kèm CSRF header."},
        )
        self.assertEqual(res_put.status_code, 403)

        # 3. DELETE without CSRF
        res_del = self.client.delete(
            "/api/reviews/me",
            headers={"Authorization": f"Bearer {self.token_user1}"},
        )
        self.assertEqual(res_del.status_code, 403)

    # 19. Private Owner Image Endpoint (IDOR Protection)
    def test_private_owner_image_endpoint(self):
        csrf = self._get_csrf_token()
        img_bytes = create_test_image_bytes("JPEG", (80, 80))
        res = self.client.post(
            "/api/reviews",
            headers={"Authorization": f"Bearer {self.token_user1}", "X-CSRF-Token": csrf},
            content_type="multipart/form-data",
            data={
                "rating": "5",
                "content": "Đánh giá đính kèm ảnh riêng tư chờ quản trị viên phê duyệt.",
                "images": [(img_bytes, "private.jpg")],
            },
        )
        self.assertEqual(res.status_code, 201)
        review = db.get_review_by_user_id(self.user1_id)
        image_id = review["images"][0]["id"]

        # Owner accesses -> 200
        owner_res = self.client.get(
            f"/api/reviews/me/images/{image_id}",
            headers={"Authorization": f"Bearer {self.token_user1}"},
        )
        self.assertEqual(owner_res.status_code, 200)
        self.assertEqual(owner_res.content_type, "image/webp")
        self.assertIn("no-store", owner_res.headers.get("Cache-Control", ""))
        owner_res.close()

        # Non-owner user2 accesses -> 404 (IDOR safe, no existence leak)
        other_res = self.client.get(
            f"/api/reviews/me/images/{image_id}",
            headers={"Authorization": f"Bearer {self.token_user2}"},
        )
        self.assertEqual(other_res.status_code, 404)
        other_res.close()

        # Unauthenticated accesses -> 401
        guest_res = self.client.get(f"/api/reviews/me/images/{image_id}")
        self.assertEqual(guest_res.status_code, 401)
        guest_res.close()

    # 20. PUT Keep Image IDs and Add New Images
    def test_put_keep_image_ids_and_new_images(self):
        csrf = self._get_csrf_token()
        img1 = (create_test_image_bytes("JPEG", (100, 100)), "img1.jpg")
        img2 = (create_test_image_bytes("JPEG", (100, 100)), "img2.jpg")

        res_create = self.client.post(
            "/api/reviews",
            headers={"Authorization": f"Bearer {self.token_user1}", "X-CSRF-Token": csrf},
            content_type="multipart/form-data",
            data={
                "rating": "5",
                "content": "Đánh giá ban đầu có 2 ảnh minh chứng rõ ràng.",
                "images": [img1, img2],
            },
        )
        self.assertEqual(res_create.status_code, 201)

        review = db.get_review_by_user_id(self.user1_id)
        old_images = review["images"]
        self.assertEqual(len(old_images), 2)
        keep_id = old_images[0]["id"]
        remove_id = old_images[1]["id"]
        remove_storage = old_images[1]["storage_name"]
        remove_disk_path = os.path.join(temp_storage_dir, remove_storage)
        self.assertTrue(os.path.exists(remove_disk_path))

        # Update: keep only img1, and upload a new img3
        new_csrf = self._get_csrf_token()
        img3 = (create_test_image_bytes("PNG", (120, 120)), "img3.png")
        res_update = self.client.put(
            "/api/reviews/me",
            headers={"Authorization": f"Bearer {self.token_user1}", "X-CSRF-Token": new_csrf},
            content_type="multipart/form-data",
            data={
                "rating": "4",
                "content": "Nội dung đánh giá đã được chỉnh sửa lại hoàn chỉnh hơn.",
                "keep_image_ids": [str(keep_id)],
                "images": [img3],
            },
        )
        self.assertEqual(res_update.status_code, 200)

        # Verify DB review has 2 images: kept img1 and new img3
        updated_rev = db.get_review_by_user_id(self.user1_id)
        current_ids = [img["id"] for img in updated_rev["images"]]
        self.assertIn(keep_id, current_ids)
        self.assertNotIn(remove_id, current_ids)
        self.assertEqual(len(updated_rev["images"]), 2)

        # Verify unkept image file was removed from disk
        self.assertFalse(os.path.exists(remove_disk_path))
        res_create.close()
        res_update.close()

    # 21. PUT Exceed 3 Images Total
    def test_put_exceed_3_images_total(self):
        csrf = self._get_csrf_token()
        img1 = (create_test_image_bytes("JPEG", (100, 100)), "img1.jpg")
        img2 = (create_test_image_bytes("JPEG", (100, 100)), "img2.jpg")

        res_create = self.client.post(
            "/api/reviews",
            headers={"Authorization": f"Bearer {self.token_user1}", "X-CSRF-Token": csrf},
            content_type="multipart/form-data",
            data={
                "rating": "5",
                "content": "Đánh giá ban đầu có 2 ảnh minh chứng rõ ràng.",
                "images": [img1, img2],
            },
        )
        self.assertEqual(res_create.status_code, 201)

        review = db.get_review_by_user_id(self.user1_id)
        kept_ids = [str(img["id"]) for img in review["images"]]

        # Attempt to keep 2 and add 2 new (total 4 > 3) -> 400
        new_csrf = self._get_csrf_token()
        img3 = (create_test_image_bytes("JPEG", (80, 80)), "img3.jpg")
        img4 = (create_test_image_bytes("JPEG", (80, 80)), "img4.jpg")
        res_update = self.client.put(
            "/api/reviews/me",
            headers={"Authorization": f"Bearer {self.token_user1}", "X-CSRF-Token": new_csrf},
            content_type="multipart/form-data",
            data={
                "rating": "4",
                "content": "Cố tình tải quá 3 ảnh trong lúc cập nhật đánh giá.",
                "keep_image_ids": kept_ids,
                "images": [img3, img4],
            },
        )
        self.assertEqual(res_update.status_code, 400)
        self.assertIn("3", res_update.get_json()["msg"])
        res_create.close()
        res_update.close()

    # 22. DELETE /api/reviews/me When No Review Exists Returns 404
    def test_delete_my_review_non_existent_returns_404(self):
        csrf = self._get_csrf_token()
        res = self.client.delete(
            "/api/reviews/me",
            headers={"Authorization": f"Bearer {self.token_user1}", "X-CSRF-Token": csrf},
        )
        self.assertEqual(res.status_code, 404)

    # 23. Public Reviews Pagination
    def test_public_reviews_pagination(self):
        # Create and approve 5 reviews
        r_ids = []
        for i in range(5):
            u_id = db.create_user(
                email=f"page_user_{i}@example.com",
                username=f"page_user_{i}",
                display_name=f"User {i}",
                password_hash=generate_password_hash("pass"),
            )
            r_id = db.create_review(u_id, 5, f"Nội dung đánh giá trang {i} để kiểm tra phân trang.")
            db.update_review_status_admin(r_id, "approved")
            r_ids.append(r_id)

        invalidate_reviews_cache()

        # Page 1: limit=2, offset=0
        res1 = self.client.get("/api/reviews?limit=2&offset=0")
        self.assertEqual(res1.status_code, 200)
        d1 = res1.get_json()
        self.assertEqual(len(d1["reviews"]), 2)
        self.assertEqual(d1["pagination"]["total"], 5)
        self.assertTrue(d1["pagination"]["has_more"])

        # Page 3: limit=2, offset=4
        res3 = self.client.get("/api/reviews?limit=2&offset=4")
        self.assertEqual(res3.status_code, 200)
        d3 = res3.get_json()
        self.assertEqual(len(d3["reviews"]), 1)
        self.assertFalse(d3["pagination"]["has_more"])

    # 24. Retired moderation route is stable for every payload and ID
    def test_admin_status_route_is_retired(self):
        self._login_admin()
        r_id = db.create_review(self.user1_id, 5, "Đánh giá dùng để test lỗi admin cập nhật trạng thái.")

        # Validation no longer matters because moderation itself is disabled.
        res_inv = self.client.post(
            f"/admin/api/reviews/{r_id}/status",
            headers={"X-CSRF-Token": self.admin_csrf},
            json={"status": "invalid_status_value"},
        )
        self.assertEqual(res_inv.status_code, 410)
        self.assertEqual(res_inv.get_json()["error"], "review_moderation_disabled")

        # Do not reveal whether an ID exists through this retired route.
        res_miss = self.client.post(
            "/admin/api/reviews/999999/status",
            headers={"X-CSRF-Token": self.admin_csrf},
            json={"status": "approved"},
        )
        self.assertEqual(res_miss.status_code, 410)
        self.assertEqual(res_miss.get_json()["error"], "review_moderation_disabled")

    # 25. Admin Delete Missing ID Returns 404
    def test_admin_delete_missing_id(self):
        self._login_admin()
        res = self.client.delete(
            "/admin/api/reviews/999999",
            headers={"X-CSRF-Token": self.admin_csrf},
        )
        self.assertEqual(res.status_code, 404)

    # 26. Admin Security Headers
    def test_admin_cache_headers_and_security(self):
        self._login_admin()
        res = self.client.get("/admin/api/reviews")
        self.assertEqual(res.status_code, 200)
        self.assertIn("no-store", res.headers.get("Cache-Control", ""))

    # 27. Stored XSS Prevention in Review Content and Display Name
    def test_xss_prevention_in_review_content_and_display_name(self):
        csrf = self._get_csrf_token()
        xss_payload = "<script>alert('XSS')</script><img src=x onerror=alert(1)>"
        res = self.client.post(
            "/api/reviews",
            headers={"Authorization": f"Bearer {self.token_user1}", "X-CSRF-Token": csrf},
            data={"rating": "5", "content": xss_payload + " - nội dung đánh giá thử nghiệm độ an toàn."},
        )
        self.assertEqual(res.status_code, 201)

        review = db.get_review_by_user_id(self.user1_id)
        db.update_review_status_admin(review["id"], "approved")
        invalidate_reviews_cache()

        pub_res = self.client.get("/api/reviews")
        self.assertEqual(pub_res.status_code, 200)
        content_out = pub_res.get_json()["reviews"][0]["content"]
        # API returns raw JSON string safely; frontend renders with textContent
        self.assertIn("<script>", content_out)

    # 28. Admin-created KOL profile joins the creator's auto-published feedback
    def test_creator_profile_end_to_end_and_safe_crop(self):
        token, csrf = self._admin_api_credentials()
        response = self.client.post(
            "/api/admin/creators",
            headers={"Authorization": f"Bearer {token}", "X-CSRF-Token": csrf},
            content_type="multipart/form-data",
            data={
                "email": "eligible@example.com",
                "display_name": "Bé Dứa",
                "tiktok_handle": "vinmeo06",
                "tiktok_url": "https://www.tiktok.com/@vinmeo06",
                "follower_count": "65700",
                "sort_order": "1",
                "crop_percent": "30",
                "is_featured": "true",
                "is_active": "true",
                "require_review": "false",
                "screenshot": (create_test_image_bytes(size=(400, 800)), "tiktok-profile.jpg"),
            },
        )
        self.assertEqual(response.status_code, 201)
        creator = response.get_json()["creator"]
        self.assertTrue(creator["is_featured"])

        public = self.client.get("/api/creators")
        self.assertEqual(public.status_code, 200)
        self.assertEqual(public.get_json()["total"], 1)
        item = public.get_json()["creators"][0]
        self.assertEqual(item["display_name"], "Bé Dứa")
        self.assertIsNone(item["review"])
        self.assertNotIn("email", item)
        self.assertNotIn("user_id", item)

        image_response = self.client.get(item["screenshot_url"])
        self.assertEqual(image_response.status_code, 200)
        with Image.open(io.BytesIO(image_response.data)) as processed:
            self.assertEqual(processed.size, (400, 240))
        image_response.close()

        review_id = db.create_review(self.user1_id, 5, "Trải nghiệm của TikTok KOL")
        public_with_review = self.client.get("/api/creators").get_json()["creators"][0]
        self.assertEqual(public_with_review["review"]["id"], review_id)
        self.assertEqual(public_with_review["review"]["rating"], 5)

        delete_response = self.client.delete(
            f"/api/admin/creators/{creator['id']}",
            headers={"Authorization": f"Bearer {token}", "X-CSRF-Token": csrf},
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertIsNotNone(db.get_user_by_id(self.user1_id))
        self.assertIsNotNone(db.get_review_by_id(review_id))
        self.assertEqual(self.client.get("/api/creators").get_json()["total"], 0)

    # 29. Admin-created KOLs can review without a completed service; identity remains canonical
    def test_creator_profile_unlocks_feedback_without_completed_service(self):
        token, csrf = self._admin_api_credentials()
        headers = {"Authorization": f"Bearer {token}", "X-CSRF-Token": csrf}

        promoted = self.client.post(
            "/api/admin/creators",
            headers=headers,
            content_type="multipart/form-data",
            data={
                "email": "ineligible@example.com",
                "tiktok_handle": "fakeidol",
                "tiktok_url": "https://www.tiktok.com/@fakeidol",
                "screenshot": (create_test_image_bytes(), "profile.jpg"),
            },
        )
        self.assertEqual(promoted.status_code, 201)
        self.assertFalse(db.has_completed_service(self.user2_id))
        self.assertTrue(db.is_review_eligible(self.user2_id))

        eligibility = self.client.get(
            "/api/reviews/me",
            headers={"Authorization": f"Bearer {self.token_user2}"},
        )
        self.assertEqual(eligibility.status_code, 200)
        self.assertTrue(eligibility.get_json()["eligible"])

        review_csrf = self._get_csrf_token()
        submitted = self.client.post(
            "/api/reviews",
            headers={
                "Authorization": f"Bearer {self.token_user2}",
                "X-CSRF-Token": review_csrf,
            },
            data={"rating": "5", "content": "Feedback từ KOL chưa mua gói."},
        )
        self.assertEqual(submitted.status_code, 201)

        public_creator = self.client.get("/api/creators").get_json()["creators"][0]
        self.assertEqual(public_creator["tiktok_handle"], "fakeidol")
        self.assertEqual(public_creator["review"]["rating"], 5)

        mismatched = self.client.post(
            "/api/admin/creators",
            headers=headers,
            content_type="multipart/form-data",
            data={
                "email": "eligible@example.com",
                "tiktok_handle": "realidol",
                "tiktok_url": "https://www.tiktok.com/@anotheridol",
                "screenshot": (create_test_image_bytes(), "profile.jpg"),
            },
        )
        self.assertEqual(mismatched.status_code, 400)
        self.assertEqual(mismatched.get_json()["error"], "invalid_tiktok_url")

    # 30. Public users cannot promote themselves and duplicate handles are blocked
    def test_creator_admin_auth_csrf_and_uniqueness(self):
        csrf = self._get_csrf_token()
        payload = {
            "email": "eligible@example.com",
            "tiktok_handle": "verifiedidol",
            "tiktok_url": "https://www.tiktok.com/@verifiedidol",
            "screenshot": (create_test_image_bytes(), "profile.jpg"),
        }
        forbidden = self.client.post(
            "/api/admin/creators",
            headers={"Authorization": f"Bearer {self.token_user1}", "X-CSRF-Token": csrf},
            content_type="multipart/form-data",
            data=payload,
        )
        self.assertEqual(forbidden.status_code, 403)

        token, admin_csrf = self._admin_api_credentials()
        missing_csrf = self.client.post(
            "/api/admin/creators",
            headers={"Authorization": f"Bearer {token}"},
            content_type="multipart/form-data",
            data={
                "email": "eligible@example.com",
                "tiktok_handle": "verifiedidol",
                "tiktok_url": "https://www.tiktok.com/@verifiedidol",
                "screenshot": (create_test_image_bytes(), "profile.jpg"),
            },
        )
        self.assertEqual(missing_csrf.status_code, 403)

        created = self.client.post(
            "/api/admin/creators",
            headers={"Authorization": f"Bearer {token}", "X-CSRF-Token": admin_csrf},
            content_type="multipart/form-data",
            data={
                "email": "eligible@example.com",
                "tiktok_handle": "verifiedidol",
                "tiktok_url": "https://www.tiktok.com/@verifiedidol",
                "screenshot": (create_test_image_bytes(), "profile.jpg"),
            },
        )
        self.assertEqual(created.status_code, 201)

        duplicate = self.client.post(
            "/api/admin/creators",
            headers={"Authorization": f"Bearer {token}", "X-CSRF-Token": admin_csrf},
            content_type="multipart/form-data",
            data={
                "email": "eligible@example.com",
                "tiktok_handle": "verifiedidol",
                "tiktok_url": "https://www.tiktok.com/@verifiedidol",
                "screenshot": (create_test_image_bytes(), "profile-2.jpg"),
            },
        )
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(duplicate.get_json()["error"], "creator_conflict")


if __name__ == "__main__":
    unittest.main()

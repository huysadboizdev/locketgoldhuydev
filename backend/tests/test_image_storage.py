import os
import shutil
import tempfile
import unittest
from unittest.mock import Mock, patch

from flask import Flask

from locket.image_storage import (
    ImageStorageUploadError,
    cloudinary_delivery_url,
    delete_stored_image,
    save_processed_image,
    serve_stored_image,
)


class ImageStorageTestCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="image-storage-test-")
        self.app = Flask(__name__)
        self.context = self.app.test_request_context("/")
        self.context.push()

    def tearDown(self):
        self.context.pop()
        shutil.rmtree(self.root, ignore_errors=True)

    def test_local_storage_remains_backward_compatible(self):
        self.app.config["REVIEW_STORAGE_PROVIDER"] = "local"
        result = save_processed_image(b"processed-image", self.root, "jpg", "review")

        self.assertRegex(result["storage_name"], r"^[a-f0-9]{32}\.jpg$")
        self.assertTrue(os.path.exists(os.path.join(self.root, result["storage_name"])))
        response = serve_stored_image(
            result["storage_name"], self.root, "review", "private, no-store"
        )
        self.assertEqual(response.status_code, 200)
        response.close()

        delete_stored_image(result["storage_name"], self.root, "review")
        self.assertFalse(os.path.exists(os.path.join(self.root, result["storage_name"])))

    def test_cloudinary_upload_delivery_and_delete_use_the_same_asset(self):
        self.app.config.update(
            REVIEW_STORAGE_PROVIDER="cloudinary",
            CLOUDINARY_CLOUD_NAME="demo-cloud",
            CLOUDINARY_API_KEY="test-key",
            CLOUDINARY_API_SECRET="test-secret",
            CLOUDINARY_FOLDER="locket-gold/reviews",
        )
        uploader = Mock()
        uploader.upload.return_value = {
            "resource_type": "image",
            "secure_url": "https://res.cloudinary.com/demo-cloud/image/upload/example.webp",
            "bytes": 123,
        }

        with patch("locket.image_storage._configure_cloudinary", return_value=uploader):
            result = save_processed_image(b"safe-webp", self.root, "webp", "review")
            self.assertRegex(result["storage_name"], r"^cld_[a-f0-9]{32}\.webp$")
            self.assertFalse(os.path.exists(os.path.join(self.root, result["storage_name"])))

            url = cloudinary_delivery_url(result["storage_name"], "review")
            self.assertIn("/locket-gold/reviews/", url)
            self.assertTrue(url.endswith(f"{result['storage_name'][:-5]}.webp"))

            response = serve_stored_image(
                result["storage_name"], self.root, "review", "public, max-age=300"
            )
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.headers["Location"], url)

            delete_stored_image(result["storage_name"], self.root, "review")
            expected_public_id = f"locket-gold/reviews/{result['storage_name'][:-5]}"
            uploader.destroy.assert_called_once_with(
                expected_public_id,
                resource_type="image",
                type="upload",
                invalidate=True,
            )

    def test_cloudinary_network_failure_has_a_safe_actionable_error(self):
        self.app.config.update(
            REVIEW_STORAGE_PROVIDER="cloudinary",
            CLOUDINARY_CLOUD_NAME="demo-cloud",
            CLOUDINARY_API_KEY="test-key",
            CLOUDINARY_API_SECRET="test-secret",
            CLOUDINARY_FOLDER="locket-gold/reviews",
        )
        uploader = Mock()
        uploader.upload.side_effect = TimeoutError("upstream timeout")
        with patch("locket.image_storage._configure_cloudinary", return_value=uploader):
            with self.assertRaisesRegex(ImageStorageUploadError, "Cloudinary"):
                save_processed_image(b"safe-webp", self.root, "webp", "review")


if __name__ == "__main__":
    unittest.main()

import builtins
import io
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask
from PIL import Image
from werkzeug.datastructures import FileStorage

from locket.creators import (
    creator_image_mimetype,
    process_creator_screenshot,
)


def _image_upload(size=(1178, 2560)):
    data = io.BytesIO()
    Image.new("RGB", size, color=(250, 250, 250)).save(data, format="JPEG")
    data.seek(0)
    return FileStorage(data, filename="tiktok-profile.jpg", content_type="image/jpeg")


class CreatorImageProcessingTestCase(unittest.TestCase):
    def setUp(self):
        self.storage = tempfile.mkdtemp(prefix="creator-image-test-")
        self.app = Flask(__name__)
        self.app.config["CREATOR_STORAGE_ROOT"] = self.storage
        self.context = self.app.app_context()
        self.context.push()

    def tearDown(self):
        self.context.pop()
        shutil.rmtree(self.storage, ignore_errors=True)

    def test_realistic_tiktok_screenshot_is_cropped_and_saved(self):
        meta, error = process_creator_screenshot(_image_upload(), 24)

        self.assertIsNone(error)
        self.assertIsNotNone(meta)
        self.assertEqual(meta["width"], 1178)
        self.assertEqual(meta["height"], 614)
        self.assertTrue(os.path.exists(os.path.join(self.storage, meta["storage_name"])))

    def test_missing_webp_encoder_falls_back_to_safe_jpeg(self):
        original_save = Image.Image.save

        def save_without_webp(image, fp, format=None, **params):
            if format == "WEBP":
                raise OSError("WebP encoder unavailable")
            return original_save(image, fp, format=format, **params)

        with patch.object(Image.Image, "save", new=save_without_webp):
            meta, error = process_creator_screenshot(_image_upload((400, 800)), 30)

        self.assertIsNone(error)
        self.assertTrue(meta["storage_name"].endswith(".jpg"))
        self.assertEqual(meta["mime_type"], "image/jpeg")
        self.assertEqual(creator_image_mimetype(meta["storage_name"]), "image/jpeg")
        with Image.open(os.path.join(self.storage, meta["storage_name"])) as saved:
            self.assertEqual(saved.size, (400, 240))
            self.assertEqual(saved.format, "JPEG")

    def test_storage_permission_error_is_reported_clearly(self):
        with patch.object(builtins, "open", side_effect=PermissionError("denied")):
            meta, error = process_creator_screenshot(_image_upload((400, 800)), 30)

        self.assertIsNone(meta)
        self.assertIn("CREATOR_STORAGE_ROOT", error)


if __name__ == "__main__":
    unittest.main()

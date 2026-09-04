import io

from django.test import TestCase
from django.urls import reverse
from PIL import Image

from .forms import PhotoUploadForm


def make_uploaded_image(name="test.png", fmt="PNG"):
    from django.core.files.uploadedfile import SimpleUploadedFile

    buffer = io.BytesIO()
    Image.new("RGB", (10, 10), color="red").save(buffer, format=fmt)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class HealthCheckTests(TestCase):
    def test_health_check_returns_ok(self):
        response = self.client.get(reverse("health-check"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})


class GalleryIndexTests(TestCase):
    def test_index_renders_with_no_photos(self):
        response = self.client.get(reverse("gallery-index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No photos yet")


class PhotoUploadFormTests(TestCase):
    def test_valid_image_is_accepted(self):
        form = PhotoUploadForm(
            data={"description": "A red square"},
            files={"image": make_uploaded_image()},
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_non_image_file_is_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        bogus = SimpleUploadedFile("not-an-image.png", b"not an image", content_type="image/png")
        form = PhotoUploadForm(data={"description": "Nope"}, files={"image": bogus})
        self.assertFalse(form.is_valid())
        self.assertIn("image", form.errors)


class UploadViewTests(TestCase):
    def test_upload_creates_photo_and_redirects(self):
        response = self.client.post(
            reverse("gallery-upload"),
            data={"description": "A red square", "image": make_uploaded_image()},
        )
        self.assertRedirects(response, reverse("gallery-index"))

        from .models import Photo

        self.assertEqual(Photo.objects.count(), 1)


class DeleteViewTests(TestCase):
    def test_delete_removes_photo_and_redirects(self):
        from .models import Photo

        self.client.post(
            reverse("gallery-upload"),
            data={"description": "A red square", "image": make_uploaded_image()},
        )
        photo = Photo.objects.get()

        response = self.client.post(reverse("gallery-delete", args=[photo.pk]))

        self.assertRedirects(response, reverse("gallery-index"))
        self.assertEqual(Photo.objects.count(), 0)

    def test_delete_requires_post(self):
        from .models import Photo

        self.client.post(
            reverse("gallery-upload"),
            data={"description": "A red square", "image": make_uploaded_image()},
        )
        photo = Photo.objects.get()

        response = self.client.get(reverse("gallery-delete", args=[photo.pk]))

        self.assertEqual(response.status_code, 405)
        self.assertEqual(Photo.objects.count(), 1)

    def test_delete_unknown_photo_returns_404(self):
        response = self.client.post(reverse("gallery-delete", args=[999]))
        self.assertEqual(response.status_code, 404)

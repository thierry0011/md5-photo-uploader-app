import io

from django import forms
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import Photo

MAX_UPLOAD_SIZE_BYTES = 8 * 1024 * 1024  # 8 MB
MAX_DIMENSION = 1600
JPEG_QUALITY = 82


class PhotoUploadForm(forms.ModelForm):
    class Meta:
        model = Photo
        fields = ["image", "description"]
        widgets = {
            "description": forms.TextInput(attrs={"placeholder": "Say something about this photo", "maxlength": 280}),
        }

    def clean_image(self):
        image = self.cleaned_data["image"]

        if image.size > MAX_UPLOAD_SIZE_BYTES:
            raise ValidationError("Image is too large (max 8 MB).")

        try:
            with Image.open(image) as img:
                img.verify()
        except (UnidentifiedImageError, OSError) as exc:
            raise ValidationError("File is not a valid image.") from exc

        image.seek(0)
        return self._resize_and_compress(image)

    def _resize_and_compress(self, image):
        # Client-uploaded photos are often full-resolution camera originals
        # (several MB) - stored/served at that size they make the gallery
        # grid painfully slow to load. Downscale + re-encode once here so
        # every future page load only ever transfers the smaller version.
        with Image.open(image) as img:
            img = ImageOps.exif_transpose(img)  # bake in rotation before EXIF is dropped
            img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")

            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
            buffer.seek(0)

        name = image.name.rsplit(".", 1)[0] + ".jpg"
        return InMemoryUploadedFile(
            buffer, "image", name, "image/jpeg", buffer.getbuffer().nbytes, None
        )

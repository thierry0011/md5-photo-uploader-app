from django import forms
from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

from .models import Photo

MAX_UPLOAD_SIZE_BYTES = 8 * 1024 * 1024  # 8 MB


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
        return image

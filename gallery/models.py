from django.db import models


class Photo(models.Model):
    image = models.ImageField(upload_to="")
    description = models.CharField(max_length=280)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.description or self.image.name

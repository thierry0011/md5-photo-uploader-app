from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

from gallery import views

urlpatterns = [
    path("", views.gallery_index, name="gallery-index"),
    path("upload/", views.upload_photo, name="gallery-upload"),
    path("photos/<int:pk>/delete/", views.delete_photo, name="gallery-delete"),
    path("health/", views.health_check, name="health-check"),
    path("admin/", admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

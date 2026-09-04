from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import PhotoUploadForm
from .models import Photo


def gallery_index(request):
    photos = Photo.objects.all()
    return render(request, "gallery/index.html", {"photos": photos, "form": PhotoUploadForm()})


def upload_photo(request):
    if request.method != "POST":
        return redirect("gallery-index")

    form = PhotoUploadForm(request.POST, request.FILES)
    if form.is_valid():
        form.save()
        messages.success(request, "Photo uploaded.")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field}: {error}")

    return redirect("gallery-index")


@require_POST
def delete_photo(request, pk):
    photo = get_object_or_404(Photo, pk=pk)
    photo.image.delete(save=False)  # removes the S3/local object, not just the DB row
    photo.delete()
    messages.success(request, "Photo deleted.")
    return redirect("gallery-index")


def health_check(request):
    """Liveness check for the ALB target groups. Deliberately does not touch
    the database so a slow/unavailable DB never flaps ECS task health."""
    return JsonResponse({"status": "ok"})

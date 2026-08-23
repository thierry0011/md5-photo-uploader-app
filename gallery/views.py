from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render

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


def health_check(request):
    """Liveness check for the ALB target groups. Deliberately does not touch
    the database so a slow/unavailable DB never flaps ECS task health."""
    return JsonResponse({"status": "ok"})

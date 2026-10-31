"""Загрузка фото исполнителей: проверяем, уменьшаем и храним в базе данных.

Файлы на диске бесплатного Render пропадают при перезапуске, база Neon остаётся.
Фото сжимается до 1600 px по длинной стороне (примерно 150–400 КБ), чтобы база не разрасталась.
"""

import io

from django.core.exceptions import ValidationError
from django.db import transaction
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import ServiceImage, ServiceImageBlob

MAX_PHOTOS = 10
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_PIXELS = 50_000_000
LONG_SIDE = 1600


def _compress(upload):
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError(f"«{upload.name}» больше 15 МБ.")
    try:
        image = Image.open(upload)
        if image.width * image.height > MAX_PIXELS:
            raise ValidationError(f"«{upload.name}» слишком большое по размеру в пикселях.")
        image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValidationError(f"«{upload.name}» не похоже на фото. Подойдут JPG, PNG или WEBP.")
    image = ImageOps.exif_transpose(image)  # фото с телефона не будет лежать на боку
    if image.mode != "RGB":
        background = Image.new("RGB", image.size, (255, 255, 255))
        rgba = image.convert("RGBA")
        background.paste(rgba, mask=rgba.split()[-1])
        image = background
    image.thumbnail((LONG_SIDE, LONG_SIDE))
    out = io.BytesIO()
    image.save(out, "JPEG", quality=82, optimize=True, progressive=True)
    return out.getvalue()


def add_photos(service, uploads):
    """Сохранить фото. Первое фото услуги становится главным. Возвращает список ошибок."""
    errors = []
    count = service.images.count()
    for upload in uploads:
        if count >= MAX_PHOTOS:
            errors.append(f"Можно не больше {MAX_PHOTOS} фото. Остальные не загружены.")
            break
        try:
            data = _compress(upload)
        except ValidationError as error:
            errors.extend(error.messages)
            continue
        with transaction.atomic():
            image = ServiceImage.objects.create(service=service, stored=True, order=count, alt=service.title)
            ServiceImageBlob.objects.create(image=image, data=data)
        count += 1
    return errors


def make_main(image):
    """Поставить фото первым: оно станет обложкой в каталоге."""
    others = [img for img in image.service.images.exclude(pk=image.pk)]
    image.order = 0
    image.save(update_fields=["order"])
    for position, other in enumerate(others, start=1):
        if other.order != position:
            other.order = position
            other.save(update_fields=["order"])

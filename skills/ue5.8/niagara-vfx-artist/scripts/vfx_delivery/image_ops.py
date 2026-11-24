from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageFilter


def image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def crop_image(source: Path, target: Path, box: tuple[int, int, int, int]) -> tuple[int, int]:
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        cropped = image.crop(box)
        cropped.save(target)
        return cropped.size


def upscale_image(source: Path, target: Path, scale: float, sharpen: float = 1.0) -> tuple[int, int]:
    if scale <= 1.0:
        raise ValueError("scale must be > 1.0")
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        width, height = image.size
        resized = image.resize((int(width * scale), int(height * scale)), Image.Resampling.LANCZOS)
        if sharpen > 0:
            resized = resized.filter(ImageFilter.UnsharpMask(radius=1.5, percent=int(120 * sharpen), threshold=2))
        resized.save(target)
        return resized.size

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

GREEN = (83, 252, 24, 255)
BLACK = (11, 14, 15, 255)
TRANSPARENT = (0, 0, 0, 0)

RESAMPLE = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
CUSTOM_NAMES = (
    "rika-icon.jpg",
    "rika-icon.jpeg",
    "rika-icon.png",
    "rika-icon.webp",
    "icon-source.png",
    "icon-source.jpg",
    "icon-source.webp",
    "homura.png",
    "homura.jpg",
    "homura.jpeg",
    "homura.webp",
    "kick-homu.png",
    "custom.png",
    "custom.jpg",
    "custom.webp",
)


def assets_dir() -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / "assets"
    return Path(__file__).resolve().parent / "assets"


def _find(names: tuple[str, ...]) -> Path | None:
    for name in names:
        candidate = assets_dir() / name
        if candidate.is_file():
            return candidate
    return None


def custom_image_path() -> Path | None:
    return _find(CUSTOM_NAMES)


def _square(image: Image.Image, size: int) -> Image.Image:
    image = image.convert("RGBA")
    width, height = image.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    cropped = image.crop((left, top, left + side, top + side))
    return cropped.resize((size, size), RESAMPLE)


def _generated_image(size: int) -> Image.Image:
    scale = 8
    canvas = max(size, 16) * scale
    image = Image.new("RGBA", (canvas, canvas), TRANSPARENT)
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        (0, 0, canvas - 1, canvas - 1),
        radius=int(canvas * 0.22),
        fill=BLACK,
    )

    bar = int(canvas * 0.13)
    left = int(canvas * 0.23)
    right = int(canvas * 0.77)
    top = int(canvas * 0.21)
    bottom = int(canvas * 0.79)
    gap = int(canvas * 0.07)
    arm = int(canvas * 0.15)

    draw.rectangle((left, top, left + bar, bottom), fill=GREEN)
    draw.rectangle((left + bar + gap, top, right, top + arm), fill=GREEN)
    draw.rectangle((left + bar + gap, bottom - arm, right, bottom), fill=GREEN)

    return image.resize((size, size), RESAMPLE)


def make_image(size: int = 64) -> Image.Image:
    path = custom_image_path()
    if path is not None:
        try:
            with Image.open(path) as source:
                return _square(source, size)
        except Exception:
            pass
    return _generated_image(size)


def save_ico(path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    make_image(256).save(
        target,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    return target


def main(argv: list[str]) -> int:
    target = argv[1] if len(argv) > 1 else "assets/kick.ico"
    saved = save_ico(target)
    print(f"Icono generado: {saved}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

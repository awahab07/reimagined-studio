#!/usr/bin/env python3
"""Generate browser-ready and Play Store media from approved source artwork."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageOps


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "source-assets" / "website-graphics"
PUBLIC_ASSETS_DIR = ROOT / "site" / "assets"
ARTWORK_DIR = PUBLIC_ASSETS_DIR / "artwork"
BRAND_DIR = PUBLIC_ASSETS_DIR / "brand"
PRODUCT_DIR = PUBLIC_ASSETS_DIR / "products"
PLAY_STORE_DIR = PUBLIC_ASSETS_DIR / "play-store"

MAX_PLAY_STORE_BYTES = 1_000_000
WEB_ARTWORK_WIDTH = 1600
SMALL_ARTWORK_WIDTH = 960


@dataclass(frozen=True)
class ProductCrop:
    slug: str
    box: tuple[int, int, int, int]


PRODUCT_CROPS = (
    ProductCrop("bomb-duel-arena", (30, 338, 310, 644)),
    ProductCrop("mindful-adventures", (322, 338, 612, 644)),
    ProductCrop("imagine-world", (626, 338, 896, 644)),
    ProductCrop("curiosity-lab", (902, 338, 1190, 644)),
    ProductCrop("tales-unfolded", (1204, 338, 1504, 644)),
)


def ensure_directories() -> None:
    for directory in (ARTWORK_DIR, BRAND_DIR, PRODUCT_DIR, PLAY_STORE_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def resize_to_width(image: Image.Image, width: int) -> Image.Image:
    if image.width == width:
        return image.copy()

    height = round(image.height * width / image.width)
    return image.resize((width, height), Image.Resampling.LANCZOS)


def make_transparent_logo(source: Image.Image) -> Image.Image:
    rgb = source.convert("RGB")
    white = Image.new("RGB", rgb.size, "white")
    difference = ImageChops.difference(rgb, white)
    red, green, blue = difference.split()
    strongest_difference = ImageChops.lighter(ImageChops.lighter(red, green), blue)

    def alpha_for_difference(value: int) -> int:
        if value <= 12:
            return 0
        if value >= 52:
            return 255
        progress = (value - 12) / 40
        smooth_progress = progress * progress * (3 - (2 * progress))
        return round(smooth_progress * 255)

    alpha = strongest_difference.point(alpha_for_difference).filter(
        ImageFilter.MedianFilter(3)
    )

    unmatted_pixels: list[tuple[int, int, int, int]] = []
    for color, alpha_value in zip(rgb.getdata(), alpha.getdata()):
        if alpha_value == 0:
            unmatted_pixels.append((0, 0, 0, 0))
            continue

        if alpha_value == 255:
            unmatted_pixels.append((*color, 255))
            continue

        alpha_fraction = alpha_value / 255
        foreground = tuple(
            max(
                0,
                min(
                    255,
                    round(
                        (channel - (255 * (1 - alpha_fraction))) / alpha_fraction
                    ),
                ),
            )
            for channel in color
        )
        unmatted_pixels.append((*foreground, alpha_value))

    rgba = Image.new("RGBA", rgb.size)
    rgba.putdata(unmatted_pixels)

    bounds = alpha.getbbox()
    if bounds is None:
        raise ValueError("Logo extraction produced an empty image")

    cropped = rgba.crop(bounds)
    padding = max(32, round(max(cropped.size) * 0.07))
    canvas_size = max(cropped.size) + (padding * 2)
    canvas = Image.new("RGBA", (canvas_size, canvas_size), (255, 255, 255, 0))
    position = (
        (canvas_size - cropped.width) // 2,
        (canvas_size - cropped.height) // 2,
    )
    canvas.alpha_composite(cropped, position)
    return canvas.resize((1024, 1024), Image.Resampling.LANCZOS)


def composite_logo(
    transparent_logo: Image.Image,
    size: int,
    background: tuple[int, int, int],
    logo_scale: float,
) -> Image.Image:
    canvas = Image.new("RGB", (size, size), background)
    mark_size = round(size * logo_scale)
    mark = transparent_logo.resize((mark_size, mark_size), Image.Resampling.LANCZOS)
    position = ((size - mark_size) // 2, (size - mark_size) // 2)
    canvas.paste(mark, position, mark)
    return canvas


def save_play_store_header(source: Image.Image, destination: Path) -> int:
    header = ImageOps.fit(
        source.convert("RGB"),
        (4096, 2304),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )

    for quality in range(88, 44, -2):
        header.save(
            destination,
            "JPEG",
            quality=quality,
            optimize=True,
            progressive=True,
            subsampling=2,
        )
        if destination.stat().st_size <= MAX_PLAY_STORE_BYTES:
            return quality

    raise ValueError("Unable to encode the Play Store header below 1 MB")


def prepare_artwork() -> None:
    for number in range(1, 9):
        source_path = SOURCE_DIR / f"reimagined-studio-{number}.jpeg"
        with Image.open(source_path) as source:
            rgb = source.convert("RGB")
            full = resize_to_width(rgb, min(WEB_ARTWORK_WIDTH, rgb.width))
            small = resize_to_width(rgb, min(SMALL_ARTWORK_WIDTH, rgb.width))
            full.save(
                ARTWORK_DIR / f"reimagined-studio-{number}.webp",
                "WEBP",
                quality=84,
                method=6,
            )
            small.save(
                ARTWORK_DIR / f"reimagined-studio-{number}-960.webp",
                "WEBP",
                quality=80,
                method=6,
            )

    with Image.open(SOURCE_DIR / "reimagined-studio-1.jpeg") as source:
        social_preview = ImageOps.fit(
            source.convert("RGB"),
            (1200, 630),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.46),
        )
        social_preview.save(
            ARTWORK_DIR / "social-preview.jpg",
            "JPEG",
            quality=84,
            optimize=True,
            progressive=True,
        )


def prepare_brand() -> Image.Image:
    with Image.open(SOURCE_DIR / "logo.jpeg") as source:
        transparent_logo = make_transparent_logo(source)

    transparent_logo.save(BRAND_DIR / "logo-transparent.png", optimize=True)
    transparent_logo.resize((512, 512), Image.Resampling.LANCZOS).save(
        BRAND_DIR / "logo-512.png",
        optimize=True,
    )
    transparent_logo.resize((32, 32), Image.Resampling.LANCZOS).save(
        BRAND_DIR / "favicon-32.png",
        optimize=True,
    )
    transparent_logo.resize((256, 256), Image.Resampling.LANCZOS).save(
        BRAND_DIR / "favicon.ico",
        format="ICO",
        sizes=((16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)),
    )

    for size in (180, 192, 512):
        icon = composite_logo(transparent_logo, size, (4, 12, 35), 0.84)
        filename = "apple-touch-icon.png" if size == 180 else f"icon-{size}.png"
        icon.save(BRAND_DIR / filename, optimize=True)

    return transparent_logo


def prepare_products() -> None:
    with Image.open(SOURCE_DIR / "reimagined-studio-6.jpeg") as source:
        rgb = source.convert("RGB")
        for product in PRODUCT_CROPS:
            crop = rgb.crop(product.box)
            card_image = ImageOps.fit(
                crop,
                (640, 700),
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )
            card_image.save(
                PRODUCT_DIR / f"{product.slug}.webp",
                "WEBP",
                quality=86,
                method=6,
            )


def prepare_play_store(transparent_logo: Image.Image) -> int:
    developer_icon = composite_logo(transparent_logo, 512, (255, 255, 255), 0.86)
    developer_icon.save(
        PLAY_STORE_DIR / "developer-icon.png",
        "PNG",
        optimize=True,
    )

    with Image.open(SOURCE_DIR / "reimagined-studio-1.jpeg") as source:
        return save_play_store_header(
            source,
            PLAY_STORE_DIR / "header-image.jpg",
        )


def main() -> None:
    ensure_directories()
    prepare_artwork()
    transparent_logo = prepare_brand()
    prepare_products()
    header_quality = prepare_play_store(transparent_logo)

    print(f"Generated public assets in {PUBLIC_ASSETS_DIR}")
    print(f"Play Store header JPEG quality: {header_quality}")
    for path in sorted(PUBLIC_ASSETS_DIR.rglob("*")):
        if path.is_file():
            print(f"{path.relative_to(ROOT)}\t{path.stat().st_size} bytes")


if __name__ == "__main__":
    main()

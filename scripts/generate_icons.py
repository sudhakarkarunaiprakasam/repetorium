from __future__ import annotations

import struct
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ICON_DIR = Path(__file__).resolve().parents[1] / "src" / "repetorium" / "qml" / "icons"
STORE_TILE_PATH = Path(__file__).resolve().parents[1] / "store-assets" / "repetorium-app-tile-300x300.png"
STORE_ICON_1024_PATH = (
    Path(__file__).resolve().parents[1] / "store-assets" / "repetorium-app-icon-1024x1024.png"
)
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


def render_png(renderer: QSvgRenderer, size: int) -> bytes:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.setDotsPerMeterX(3780)
    image.setDotsPerMeterY(3780)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    buffer = QBuffer()
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly) or not image.save(buffer, "PNG"):
        raise RuntimeError(f"Could not render the project icon at {size}px.")
    return bytes(buffer.data())


def generate_icons(icon_dir: Path = ICON_DIR) -> None:
    renderer = QSvgRenderer(str(icon_dir / "repetorium.svg"))
    if not renderer.isValid():
        raise RuntimeError(f"Could not load {icon_dir / 'repetorium.svg'}.")
    (icon_dir / "repetorium.png").write_bytes(render_png(renderer, 512))

    images = [render_png(renderer, size) for size in ICON_SIZES]
    offset = 6 + 16 * len(images)
    entries = []
    for size, image in zip(ICON_SIZES, images, strict=True):
        # ICO stores 256px dimensions as zero; each frame contains a PNG image.
        dimension = size if size < 256 else 0
        entries.append(struct.pack("<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(image), offset))
        offset += len(image)
    (icon_dir / "repetorium.ico").write_bytes(
        struct.pack("<HHH", 0, 1, len(images)) + b"".join(entries) + b"".join(images)
    )


def _generate_store_image(icon_dir: Path, output_path: Path, size: int) -> None:
    renderer = QSvgRenderer(str(icon_dir / "repetorium.svg"))
    if not renderer.isValid():
        raise RuntimeError(f"Could not load {icon_dir / 'repetorium.svg'}.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(render_png(renderer, size))


def generate_store_tile(icon_dir: Path = ICON_DIR, output_path: Path = STORE_TILE_PATH) -> None:
    _generate_store_image(icon_dir, output_path, 300)


def generate_store_icon_1024(
    icon_dir: Path = ICON_DIR,
    output_path: Path = STORE_ICON_1024_PATH,
) -> None:
    _generate_store_image(icon_dir, output_path, 1024)


if __name__ == "__main__":
    generate_icons()
    generate_store_tile()
    generate_store_icon_1024()
    print(f"Generated project icons in {ICON_DIR} and Store assets in {STORE_TILE_PATH.parent}")

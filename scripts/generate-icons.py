#!/usr/bin/env python3
"""Regenerate PNG launcher icons from debian/icons/ethereum-vanity.svg."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
SVG = ROOT / "debian" / "icons" / "ethereum-vanity.svg"
OUT_ROOT = ROOT / "debian" / "icons" / "hicolor"
SIZES = (16, 32, 48, 64, 128, 256)


def main() -> int:
    if not SVG.is_file():
        print(f"Missing SVG: {SVG}", file=sys.stderr)
        return 1

    app = QApplication(sys.argv)
    for size in SIZES:
        out_dir = OUT_ROOT / f"{size}x{size}" / "apps"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "ethereum-vanity.png"
        renderer = QSvgRenderer(str(SVG))
        image = QImage(QSize(size, size), QImage.Format.Format_ARGB32)
        image.fill(0)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        image.save(str(out_path))
        print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

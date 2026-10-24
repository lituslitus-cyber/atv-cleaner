# -*- coding: utf-8 -*-
"""Готовит для сборки exe значок и сведения о версии (вкладка «Подробно» в свойствах файла).

Запуск: python tools/make_build_files.py  ->  build/icon.ico, build/version_info.txt
"""
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import atv_cleaner  # noqa: E402

OUT = "build"


def make_icon(path):
    """Телевизор с метлой: синий экран, светлая рамка."""
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((16, 36, 240, 190), radius=22, fill=(32, 33, 36, 255))
    d.rounded_rectangle((30, 50, 226, 176), radius=12, fill=(26, 115, 232, 255))
    d.rectangle((112, 190, 144, 214), fill=(32, 33, 36, 255))
    d.rounded_rectangle((72, 210, 184, 228), radius=8, fill=(32, 33, 36, 255))
    # Метла на экране
    d.line((168, 66, 104, 138), fill=(255, 255, 255, 255), width=12)
    d.polygon([(92, 124), (122, 154), (96, 168), (70, 160), (74, 140)],
              fill=(255, 214, 102, 255))
    img.save(path, sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])


def make_version_info(path):
    v = atv_cleaner.__version__
    nums = (v.split(".") + ["0"] * 4)[:4]
    tup = ", ".join(str(int(n)) for n in nums)
    text = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({tup}), prodvers=({tup}), mask=0x3f, flags=0x0,
                    OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('041904B0', [
      StringStruct('CompanyName', 'lituslitus-cyber'),
      StringStruct('FileDescription', 'ATV Cleaner: очистка Android TV через ADB'),
      StringStruct('FileVersion', '{v}'),
      StringStruct('InternalName', 'ATVCleaner'),
      StringStruct('LegalCopyright', 'github.com/lituslitus-cyber/atv-cleaner'),
      StringStruct('OriginalFilename', 'ATVCleaner.exe'),
      StringStruct('ProductName', 'ATV Cleaner'),
      StringStruct('ProductVersion', '{v}')])]),
    VarFileInfo([VarStruct('Translation', [0x0419, 1200])])
  ]
)
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    make_icon(os.path.join(OUT, "icon.ico"))
    make_version_info(os.path.join(OUT, "version_info.txt"))
    print("build/icon.ico и build/version_info.txt готовы, версия", atv_cleaner.__version__)

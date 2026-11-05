"""번들 서체를 현재 프로세스에만 등록합니다. Windows에는 설치하지 않습니다."""
import ctypes
import logging
import os

from paths import RESOURCES

FONT_FAMILY = "Maplestory"
_loaded = False


def load_fonts():
    global _loaded
    if _loaded or os.name != "nt":
        return
    # 독립 DLL 핸들을 사용해 다른 UI 라이브러리의 ctypes 선언을 바꾸지 않습니다.
    add_font = ctypes.WinDLL("gdi32", use_last_error=True).AddFontResourceExW
    add_font.argtypes = [ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p]
    add_font.restype = ctypes.c_int
    for name in ["Maplestory Light.ttf", "Maplestory Bold.ttf"]:
        path = RESOURCES / "assets" / "fonts" / name
        if not add_font(str(path), 0x10, None):  # FR_PRIVATE
            logging.warning("번들 서체를 읽지 못했습니다: %s", path)
    _loaded = True

"""Vietnamese / English i18n for Lappa IDE chrome.

Usage:
    from lappa.i18n import tr, set_language, VI, EN

    # Set language at startup
    set_language(VI)

    # Translate a string
    label = tr("Open Workspace")
"""

from __future__ import annotations

from typing import Final

EN: Final[str] = "en"
VI: Final[str] = "vi"

_current_lang: str = EN

# ── English → Vietnamese translation map ─────────────────────────────

_TRANSLATIONS: dict[str, dict[str, str]] = {
    # ── Window titles ────────────────────────────────────────────────
    "Lappa - ROS2 Package IDE - v{version}": {
        VI: "Lappa - ROS2 Package IDE - v{version}",
    },
    "Welcome - Lappa ROS2 Package IDE - v{version}": {
        VI: "Chào mừng - Lappa ROS2 Package IDE - v{version}",
    },
    "Lappa - ROS2 Package IDE": {
        VI: "Lappa - ROS2 Package IDE",
    },
    "Unsaved changes": {
        VI: "Thay đổi chưa lưu",
    },

    # ── Welcome screen ───────────────────────────────────────────────
    "Lappa": {
        VI: "Lappa",
    },
    "ROS2 PACKAGE IDE": {
        VI: "ROS2 PACKAGE IDE",
    },
    "ROS2 Package IDE": {
        VI: "ROS2 Package IDE",
    },
    "Start with a ROS2 workspace": {
        VI: "Bắt đầu với một ROS2 workspace",
    },
    "Open Workspace": {
        VI: "Mở Workspace",
    },
    "Open ROS Package": {
        VI: "Mở ROS Package",
    },
    "New Empty Workspace": {
        VI: "Workspace trống mới",
    },
    "Continue to IDE": {
        VI: "Tiếp tục vào IDE",
    },

    # ── Panels ───────────────────────────────────────────────────────
    "Workspace": {
        VI: "Workspace",
    },
    "No folders added": {
        VI: "Chưa có thư mục nào",
    },
    "Open a workspace folder to discover ROS2 packages.": {
        VI: "Mở thư mục workspace để khám phá các ROS2 packages.",
    },
    "Package": {
        VI: "Package",
    },
    "Explorer": {
        VI: "Explorer",
    },
    "Source Editor": {
        VI: "Trình soạn thảo",
    },
    "Live Simulation": {
        VI: "Mô phỏng trực tiếp",
    },
    "No file open": {
        VI: "Không có file nào mở",
    },

    # ── Simulation panel ─────────────────────────────────────────────
    "Idle": {
        VI: "Chờ",
    },
    "Simulation is not running": {
        VI: "Mô phỏng chưa chạy",
    },
    "No package selected": {
        VI: "Chưa chọn package",
    },
    "Fixed Frame": {
        VI: "Khung cố định",
    },
    "View": {
        VI: "Xem",
    },
    "Simulation package": {
        VI: "Package mô phỏng",
    },
    "Native teleop ready": {
        VI: "Teleop sẵn sàng",
    },
    "SLAM Toolbox  waiting for Docker /map": {
        VI: "SLAM Toolbox đang chờ Docker /map",
    },

    # ── Docker panel ─────────────────────────────────────────────────
    "Checking Docker runtime...": {
        VI: "Đang kiểm tra Docker...",
    },
    "Live Docker / native launch output": {
        VI: "Đầu ra Docker / native launch",
    },

    # ── Editor panel ─────────────────────────────────────────────────
    "Ln {line}, Col {col} | {suffix}": {
        VI: "Dòng {line}, Cột {col} | {suffix}",
    },
    "Saved": {
        VI: "Đã lưu",
    },
    "Unsaved": {
        VI: "Chưa lưu",
    },

    # ── AI panel ─────────────────────────────────────────────────────
    "AI Assistant": {
        VI: "Trợ lý AI",
    },
    "Ask AI anything about your ROS2 package...": {
        VI: "Hỏi AI về ROS2 package của bạn...",
    },

    # ── Language toggle ──────────────────────────────────────────────
    "English": {
        VI: "Tiếng Anh",
    },
    "Tiếng Việt": {
        EN: "Vietnamese",
    },

    # ── Tooltips ────────────────────────────────────────────────────
    "Add a folder containing one or more ROS2 packages": {
        VI: "Thêm thư mục chứa một hoặc nhiều ROS2 packages",
    },
    "Open a folder that contains package.xml": {
        VI: "Mở thư mục chứa package.xml",
    },
    "Switch language": {
        VI: "Chuyển đổi ngôn ngữ",
    },
}


def set_language(lang: str) -> None:
    """Set the active language code."""
    global _current_lang  # noqa: PLW0603
    _current_lang = lang


def get_language() -> str:
    """Return the current language code."""
    return _current_lang


def tr(text: str, **kwargs: str | float) -> str:
    """Translate *text* to the current language.

    Falls back to the original text when no translation is registered.
    Supports ``{placeholder}`` substitution via ``**kwargs``.
    """
    entry = _TRANSLATIONS.get(text, {})
    translated = entry.get(_current_lang) or text
    if kwargs:
        try:
            return translated.format(**kwargs)
        except KeyError:
            return translated
    return translated


def available_languages() -> list[tuple[str, str]]:
    """Return list of (code, display_name) pairs."""
    return [
        (EN, tr("English")),
        (VI, tr("Tiếng Việt")),
    ]
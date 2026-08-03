"""i18n module for Lappa IDE — EN/VI string tables."""

from __future__ import annotations

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "app.title": "Lappa IDE",
        "app.subtitle": "ROS2 package workspace shell",
        "nav.packages": "Packages",
        "nav.editor": "Editor",
        "nav.sim": "Sim / build",
        "nav.foxglove": "Foxglove Bridge",
        "nav.terminal": "Terminal",
        "terminal.native": "Native",
        "terminal.docker": "Docker",
        "terminal.all": "All",
        "terminal.clear": "Clear",
        "sim.open_workspace": "Open a workspace via {cmd}.",
        "editor.scaffold": "Scaffold UI — connect to Lappa server API for file tree and build.",
        "sim.metrics": "Native sim metrics and colcon status appear here.",
        "foxglove.checking": "Checking rosbridge...",
        "foxglove.connected": "Connected to rosbridge",
        "foxglove.offline": "Foxglove Bridge Offline",
        "foxglove.offline_hint": "Start the Docker ROS2 runtime to connect.",
    },
    "vi": {
        "app.title": "Lappa IDE",
        "app.subtitle": "Không gian làm việc gói ROS2",
        "nav.packages": "Gói",
        "nav.editor": "Trình soạn thảo",
        "nav.sim": "Mô phỏng / Xây dựng",
        "nav.foxglove": "Cầu Foxglove",
        "nav.terminal": "Thiết bị đầu cuối",
        "terminal.native": "Nội bộ",
        "terminal.docker": "Docker",
        "terminal.all": "Tất cả",
        "terminal.clear": "Xóa",
        "sim.open_workspace": "Mở không gian làm việc qua {cmd}.",
        "editor.scaffold": "Giao diện khung — kết nối API máy chủ Lappa để xem cây tệp và xây dựng.",
        "sim.metrics": "Số liệu mô phỏng nội bộ và trạng thái colcon xuất hiện ở đây.",
        "foxglove.checking": "Đang kiểm tra rosbridge...",
        "foxglove.connected": "Đã kết nối rosbridge",
        "foxglove.offline": "Cầu Foxglove Ngoại tuyến",
        "foxglove.offline_hint": "Khởi động Docker ROS2 để kết nối.",
    },
}

SUPPORTED_LOCALES = list(STRINGS.keys())
DEFAULT_LOCALE = "en"


def get_string(key: str, locale: str = DEFAULT_LOCALE, **kwargs) -> str:
    table = STRINGS.get(locale, STRINGS[DEFAULT_LOCALE])
    text = table.get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass
    return text


def get_all(locale: str = DEFAULT_LOCALE) -> dict[str, str]:
    return STRINGS.get(locale, STRINGS[DEFAULT_LOCALE])

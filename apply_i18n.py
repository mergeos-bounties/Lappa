#!/usr/bin/env python3
"""Apply i18n changes to main_window.py."""
import re

path = "/tmp/waterWang-Lappa/packages/server/src/lappa/gui/main_window.py"
with open(path, "r") as f:
    content = f.read()

# 1. Add import
content = content.replace(
    "from lappa.gui.styles import STYLESHEET",
    "from lappa.gui.styles import STYLESHEET\nfrom lappa.i18n import tr, set_language, get_language, VI, EN"
)

# 2. Add _init_language call after setStyleSheet
content = content.replace(
    "self.setStyleSheet(STYLESHEET)\n\n        central = QWidget()",
    "self.setStyleSheet(STYLESHEET)\n        self._init_language()\n\n        central = QWidget()"
)

# 3. Add language methods before __init__ ends (before "central = QWidget()")
lang_methods = """
    # ── Language i18n ────────────────────────────────────────────────

    def _init_language(self) -> None:
        \"\"\"Restore language preference from QSettings.\"\"\"
        from PySide6.QtCore import QSettings
        s = QSettings()
        lang = s.value("ui/language", EN)
        set_language(lang)

    def _update_lang_button(self) -> None:
        text = "EN" if get_language() == VI else "VI"
        self.lang_btn.setText(text)

    def _toggle_language(self) -> None:
        \"\"\"Cycle between English and Vietnamese.\"\"\"
        from PySide6.QtCore import QSettings
        new = VI if get_language() == EN else EN
        set_language(new)
        s = QSettings()
        s.setValue("ui/language", new)
        self._update_lang_button()
        self._refresh_ui()

    def _refresh_ui(self) -> None:
        \"\"\"Re-apply all translatable strings in the UI.\"\"\"
        self.setWindowTitle(
            tr("Lappa - ROS2 Package IDE - v{version}", version=__version__)
        )
        self.lang_btn.setToolTip(tr("Switch language"))
"""

# Add after the last line before the huge central widget setup
content = content.replace(
    "self.setStyleSheet(STYLESHEET)\n        self._init_language()\n\n        central = QWidget()",
    "self.setStyleSheet(STYLESHEET)\n        self._init_language()\n" + lang_methods + "\n        central = QWidget()"
)

# 4. Replace window title
content = content.replace(
    'self.setWindowTitle(f"Lappa - ROS2 Package IDE - v{__version__}")',
    'self.setWindowTitle(tr("Lappa - ROS2 Package IDE - v{version}", version=__version__))'
)

# 5. Replace welcome window title
content = content.replace(
    'self.setWindowTitle(f"Welcome - Lappa ROS2 Package IDE - v{__version__}")',
    'self.setWindowTitle(tr("Welcome - Lappa ROS2 Package IDE - v{version}", version=__version__))'
)

# 6. Welcome screen translations
content = content.replace('brand = QLabel("Lappa")\n        brand.setObjectName("welcomeBrand")', 'brand = QLabel(tr("Lappa"))\n        brand.setObjectName("welcomeBrand")')
content = content.replace('product = QLabel("ROS2 PACKAGE IDE")\n        product.setObjectName("welcomeProduct")', 'product = QLabel(tr("ROS2 PACKAGE IDE"))\n        product.setObjectName("welcomeProduct")')
content = content.replace('headline = QLabel("Start with a ROS2 workspace")\n        headline.setObjectName("welcomeTitle")', 'headline = QLabel(tr("Start with a ROS2 workspace"))\n        headline.setObjectName("welcomeTitle")')
content = content.replace(
    '"Open package source, inspect robot models, and run simulation in one workbench."',
    'tr("Open package source, inspect robot models, and run simulation in one workbench.")'
)

# 7. Action buttons
content = content.replace('open_workspace = self._action_button("Open Workspace"', 'open_workspace = self._action_button(tr("Open Workspace")')
content = content.replace('open_workspace.setToolTip("Add a folder containing one or more ROS2 packages")', 'open_workspace.setToolTip(tr("Add a folder containing one or more ROS2 packages"))')
content = content.replace('open_package = self._action_button("Open ROS Package"', 'open_package = self._action_button(tr("Open ROS Package")')
content = content.replace('open_package.setToolTip("Open a folder that contains package.xml")', 'open_package.setToolTip(tr("Open a folder that contains package.xml"))')
content = content.replace('new_workspace = self._action_button("New Empty Workspace"', 'new_workspace = self._action_button(tr("New Empty Workspace")')
content = content.replace('continue_button = self._action_button("Continue to IDE"', 'continue_button = self._action_button(tr("Continue to IDE")')

# 8. Workspace panel
content = content.replace('self.workspace_name = QLabel("Workspace")\n        self.workspace_name.setObjectName("welcomeWorkspaceName")', 'self.workspace_name = QLabel(tr("Workspace"))\n        self.workspace_name.setObjectName("welcomeWorkspaceName")')
content = content.replace('self.workspace_meta = QLabel("No folders added")\n        self.workspace_meta.setObjectName("welcomeMeta")', 'self.workspace_meta = QLabel(tr("No folders added"))\n        self.workspace_meta.setObjectName("welcomeMeta")')
content = content.replace('self.workspace_root = QLabel("Open a workspace folder to discover ROS2 packages.")', 'self.workspace_root = QLabel(tr("Open a workspace folder to discover ROS2 packages."))')

# 9. Topbar translations
content = content.replace('brand = QLabel("Lappa")\n        brand.setObjectName("brand")\n        subtitle = QLabel("ROS2 Package IDE")\n        subtitle.setObjectName("brandSub")', 'brand = QLabel(tr("Lappa"))\n        brand.setObjectName("brand")\n        subtitle = QLabel(tr("ROS2 Package IDE"))\n        subtitle.setObjectName("brandSub")')
content = content.replace('layout.addWidget(QLabel("Package"))', 'layout.addWidget(QLabel(tr("Package")))')

# 10. Add language toggle button in topbar
content = content.replace(
    'layout.addWidget(self.pkg_combo)\n\n        self.header_file_label = QLabel("No file open")',
    'layout.addWidget(self.pkg_combo)\n\n        # ── Language toggle ──\n        self.lang_btn = QPushButton()\n        self.lang_btn.setObjectName("langToggle")\n        self.lang_btn.setFixedSize(28, 28)\n        self.lang_btn.setToolTip(tr("Switch language"))\n        self.lang_btn.clicked.connect(self._toggle_language)\n        self._update_lang_button()\n        layout.addWidget(self.lang_btn)\n\n        self.header_file_label = QLabel("No file open")'
)

# 11. Explorer panel
content = content.replace('title = QLabel("Explorer")\n        title.setObjectName("panelTitleSmall")', 'title = QLabel(tr("Explorer"))\n        title.setObjectName("panelTitleSmall")')

# 12. Editor panel
content = content.replace('title = QLabel("Source Editor")\n        title.setObjectName("panelTitle")\n        self.ed_path_label = QLabel("No file open")', 'title = QLabel(tr("Source Editor"))\n        title.setObjectName("panelTitle")\n        self.ed_path_label = QLabel(tr("No file open"))')

# 13. Sim panel
content = content.replace('title = QLabel("Live Simulation")\n        title.setObjectName("panelTitle")\n        self.sim_state_pill = QLabel("Idle")', 'title = QLabel(tr("Live Simulation"))\n        title.setObjectName("panelTitle")\n        self.sim_state_pill = QLabel(tr("Idle"))')
content = content.replace('self.sim_placeholder_title = QLabel("Simulation is not running")', 'self.sim_placeholder_title = QLabel(tr("Simulation is not running"))')
content = content.replace('self.sim_placeholder_package = QLabel("No package selected")', 'self.sim_placeholder_package = QLabel(tr("No package selected"))')

# 14. Sim control labels
content = content.replace('control_layout.addWidget(QLabel("Simulation package"))', 'control_layout.addWidget(QLabel(tr("Simulation package")))')
content = content.replace('self.keyboard_status = QLabel("Native teleop ready")', 'self.keyboard_status = QLabel(tr("Native teleop ready"))')

# 15. Docker panel
content = content.replace('self.docker_guidance = QLabel("Checking Docker runtime...")', 'self.docker_guidance = QLabel(tr("Checking Docker runtime..."))')
content = content.replace('launch_log_header.addWidget(QLabel("Live Docker / native launch output"))', 'launch_log_header.addWidget(QLabel(tr("Live Docker / native launch output")))')

# 16. SLAM status
content = content.replace('self.slam_status_label = QLabel("SLAM Toolbox  waiting for Docker /map")', 'self.slam_status_label = QLabel(tr("SLAM Toolbox  waiting for Docker /map"))')

# 17. Save dialog
content = content.replace('box.setWindowTitle("Unsaved changes")', 'box.setWindowTitle(tr("Unsaved changes"))')

# 18. View bar
content = content.replace('view_bar.addWidget(QLabel("Fixed Frame"))\n        view_bar.addWidget(QLabel("View"))', 'view_bar.addWidget(QLabel(tr("Fixed Frame")))\n        view_bar.addWidget(QLabel(tr("View")))')

with open(path, "w") as f:
    f.write(content)

print("Done! All patches applied.")
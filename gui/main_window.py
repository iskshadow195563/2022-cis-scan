import sys
import os
import json
import ctypes
import re
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QFileDialog,
                             QProgressBar, QComboBox, QLineEdit, QTableWidget,
                             QTableWidgetItem, QHeaderView, QMessageBox, QApplication, QStyle)
from PyQt5.QtCore import Qt, QProcess, QUrl, QSize
from PyQt5.QtGui import QDesktopServices
from core.cis_selection import apply_bulk_selection, row_matches_query
from core.language_manager import tr, lang_manager
from core.scanner import Scanner
from gui.background_manager import BackgroundWidget, BackgroundManager
from gui.theme_tokens import build_theme_stylesheet, resolve_theme_name
from core.os_detection import is_client_supported

class MainWindow(QMainWindow):
    COL_NUMBER = 0
    COL_LEVEL = 1
    COL_NAME = 2
    COL_ASSESSMENT = 3
    COL_STATUS = 4

    def __init__(self):
        super().__init__()
        self.scanner = None
        self.selected_codes = set()
        self.apply_process = None
        self.apply_report_dir = None
        self._benchmark_metadata = None
        self.init_ui()
        self.load_styles()
        self.load_items()

    def load_styles(self):
        theme_name = resolve_theme_name(QApplication.instance())
        self.setStyleSheet(build_theme_stylesheet(theme_name))

    def init_ui(self):
        self.setWindowTitle(tr("app_title"))
        self.setMinimumSize(1100, 700)

        # Main Widget
        self._bg_manager = BackgroundManager()
        central_widget = BackgroundWidget(self._bg_manager)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Top Bar: Env check, Language, Admin status
        top_layout = QHBoxLayout()
        self.btn_check_env = QPushButton(tr("check_env"))
        self.btn_check_env.clicked.connect(self.check_environment)
        top_layout.addWidget(self.btn_check_env)

        self.btn_apply_defaults = QPushButton(tr("apply_defaults"))
        self.btn_apply_defaults.setObjectName("applyDefaultsButton")
        self.btn_apply_defaults.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self.btn_apply_defaults.setIconSize(QSize(18, 18))
        self.btn_apply_defaults.setToolTip(tr("apply_defaults_tooltip"))
        self.btn_apply_defaults.setAccessibleName(tr("apply_defaults_accessible_name"))
        self.btn_apply_defaults.setAccessibleDescription(tr("apply_defaults_accessible_desc"))
        self.btn_apply_defaults.clicked.connect(self.on_apply_defaults_clicked)
        top_layout.addWidget(self.btn_apply_defaults)

        # Help button with icon and accessibility
        self.btn_help = QPushButton(" ? ")
        self.btn_help.setObjectName("helpButton")
        self.btn_help.setToolTip(tr("help_tooltip"))
        self.btn_help.setAccessibleName(tr("help_accessible_name"))
        self.btn_help.setAccessibleDescription(tr("help_accessible_desc"))
        self.btn_help.clicked.connect(self.show_help_panel)
        self.btn_help.setMinimumWidth(36)
        top_layout.addWidget(self.btn_help)

        self.btn_bg = QPushButton(tr("bg_button"))
        self.btn_bg.setObjectName("bgButton")
        self.btn_bg.setToolTip(tr("bg_tooltip"))
        self.btn_bg.clicked.connect(self.show_background_dialog)
        top_layout.addWidget(self.btn_bg)



        top_layout.addStretch()

        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["English", "繁體中文"])
        self.lang_combo.currentIndexChanged.connect(self.change_language)
        top_layout.addWidget(self.lang_combo)
        # Keyboard shortcut for Help (F1)
        try:
            from PyQt5.QtWidgets import QShortcut
            from PyQt5.QtGui import QKeySequence
            self.help_shortcut = QShortcut(QKeySequence("F1"), self)
            self.help_shortcut.activated.connect(self.show_help_panel)
        except Exception:
            pass

        main_layout.addLayout(top_layout)

        # Output Path Selection
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel(tr("output_path")))
        self.path_edit = QLabel(os.path.join(os.getcwd(), "results"))
        path_layout.addWidget(self.path_edit)
        self.btn_browse = QPushButton(tr("browse"))
        self.btn_browse.clicked.connect(self.browse_path)
        path_layout.addWidget(self.btn_browse)
        main_layout.addLayout(path_layout)

        self.guide_card = QWidget()
        self.guide_card.setProperty("card", True)
        guide_layout = QVBoxLayout(self.guide_card)
        guide_layout.setContentsMargins(12, 10, 12, 10)
        self.guide_title = QLabel(tr("guide_title"))
        self.guide_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        guide_layout.addWidget(self.guide_title)
        self.guide_body = QLabel(tr("guide_body"))
        self.guide_body.setWordWrap(True)
        self.guide_body.setTextFormat(Qt.RichText)
        guide_layout.addWidget(self.guide_body)
        main_layout.addWidget(self.guide_card)

        # Item Selection Area
        selection_main_layout = QHBoxLayout()

        self.items_container = QWidget()
        self.items_container.setProperty("card", True)
        self.items_layout = QVBoxLayout(self.items_container)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(tr("search_placeholder"))
        self.search_edit.textChanged.connect(self.filter_items)
        self.items_layout.addWidget(self.search_edit)
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(5)
        self.items_table.setAlternatingRowColors(True)
        self.items_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.items_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.items_table.verticalHeader().setVisible(False)
        self.items_table.setSortingEnabled(True)
        self.items_table.setWordWrap(False)
        self.items_table.setTextElideMode(Qt.ElideNone)
        self.items_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.items_table.horizontalHeader().setMinimumSectionSize(60)
        self.items_table.itemChanged.connect(self.on_table_item_changed)
        self.items_layout.addWidget(self.items_table)
        selection_main_layout.addWidget(self.items_container, 4)

        # Control Buttons
        btn_panel = QVBoxLayout()
        self.btn_all_l1 = QPushButton(tr("select_all_l1"))
        self.btn_all_l1.clicked.connect(lambda: self.select_by_filter("L1"))

        self.btn_all_l2 = QPushButton(tr("select_all_l2"))
        self.btn_all_l2.clicked.connect(lambda: self.select_by_filter("L2"))

        self.btn_l1_l2 = QPushButton(tr("select_l1_l2"))
        self.btn_l1_l2.clicked.connect(lambda: self.select_by_filter("L1_L2"))

        self.btn_all = QPushButton(tr("select_all"))
        self.btn_all.clicked.connect(lambda: self.select_all(True))

        self.btn_none = QPushButton(tr("deselect_all"))
        self.btn_none.clicked.connect(lambda: self.select_all(False))

        self.btn_import_ps = QPushButton(tr("import_ps_script"))
        self.btn_import_ps.clicked.connect(self.import_ps_script)

        self.btn_delete_ps = QPushButton(tr("delete_ps_script"))
        self.btn_delete_ps.clicked.connect(self.delete_ps_scripts)

        self.btn_profile = QPushButton(tr("profile_manage"))
        self.btn_profile.setToolTip(tr("profile_manage_tooltip"))
        self.btn_profile.clicked.connect(self.open_profile_manager)

        btn_panel.addWidget(self.btn_all_l1)
        btn_panel.addWidget(self.btn_all_l2)
        btn_panel.addWidget(self.btn_l1_l2)
        btn_panel.addWidget(self.btn_all)
        btn_panel.addWidget(self.btn_none)
        btn_panel.addWidget(self.btn_import_ps)
        btn_panel.addWidget(self.btn_delete_ps)
        btn_panel.addWidget(self.btn_profile)
        btn_panel.addStretch()

        # Button to re-open last report (as requested)
        self.btn_reopen = QPushButton(tr("reopen_report"))
        self.btn_reopen.clicked.connect(self.open_latest_report)
        self.btn_reopen.setEnabled(False) # Enable if a report exists
        btn_panel.addWidget(self.btn_reopen)

        selection_main_layout.addLayout(btn_panel, 1)
        main_layout.addLayout(selection_main_layout)

        # Scan Mode Selection
        scan_mode_layout = QHBoxLayout()
        scan_mode_layout.addWidget(QLabel(tr("scan_mode_label")))
        self.scan_mode_combo = QComboBox()
        self.scan_mode_combo.addItem(tr("scan_mode_local"), "local")
        self.scan_mode_combo.addItem(tr("scan_mode_domain"), "domain")
        self.scan_mode_combo.addItem(tr("scan_mode_remote"), "remote")
        self.scan_mode_combo.currentIndexChanged.connect(self.on_scan_mode_changed)
        scan_mode_layout.addWidget(self.scan_mode_combo)

        self.remote_target_label = QLabel(tr("remote_target_label"))
        scan_mode_layout.addWidget(self.remote_target_label)
        self.remote_target_edit = QLineEdit()
        self.remote_target_edit.setPlaceholderText(tr("remote_target_placeholder"))
        self.remote_target_edit.setMinimumWidth(150)
        scan_mode_layout.addWidget(self.remote_target_edit)
        self.remote_target_label.setVisible(False)
        self.remote_target_edit.setVisible(False)

        self.btn_remote_config = QPushButton(tr("remote_config_button"))
        self.btn_remote_config.setToolTip(tr("remote_config_button_tooltip"))
        self.btn_remote_config.clicked.connect(self.open_remote_config)
        scan_mode_layout.addWidget(self.btn_remote_config)

        scan_mode_layout.addStretch()
        main_layout.addLayout(scan_mode_layout)

        # Bottom: Progress and Run
        bottom_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        bottom_layout.addWidget(self.progress_bar)

        self.btn_run = QPushButton(tr("run_audit"))
        self.btn_run.clicked.connect(self.start_audit)
        self.btn_run.setMinimumHeight(40)
        bottom_layout.addWidget(self.btn_run)

        self.btn_cancel = QPushButton(tr("cancel"))
        self.btn_cancel.clicked.connect(self.cancel_audit)
        self.btn_cancel.setEnabled(False)
        bottom_layout.addWidget(self.btn_cancel)

        main_layout.addLayout(bottom_layout)

        # Status Message Label
        self.status_label = QLabel("")
        self.status_label.setObjectName("status_label")
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(30)
        main_layout.addWidget(self.status_label)

        self.check_latest_report()
        self.retranslate_ui()
        # Reflect current language in combo box
        try:
            self.lang_combo.blockSignals(True)
            self.lang_combo.setCurrentIndex(0 if lang_manager.current_language == "en" else 1)
        finally:
            self.lang_combo.blockSignals(False)
        try:
            if not is_client_supported():
                self.show()
        except Exception:
            pass



    def show_help_panel(self):
        try:
            from gui.help_panel import HelpPanel
            dlg = HelpPanel(self)
            # Position near the help button for better context
            btn = self.btn_help
            pos = btn.mapToGlobal(btn.rect().bottomLeft())
            dlg.move(pos)
            dlg.exec_()
        except Exception as e:
            self.show_message(tr("help_error", str(e)), is_error=True)

    def show_background_dialog(self):
        try:
            from gui.background_dialog import BackgroundDialog
            dlg = BackgroundDialog(self._bg_manager, self)
            dlg.exec_()
        except Exception as e:
            self.show_message(tr("background_error", str(e)), is_error=True)

    def open_remote_config(self):
        try:
            from gui.remote_config_dialog import RemoteConfigDialog
            dlg = RemoteConfigDialog(self)
            dlg.exec_()
        except Exception as e:
            self.show_message(tr("remote_config_error", str(e)), is_error=True)

    def get_benchmark_txt_path(self):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        from core.os_detection import get_server_family
        server_family = get_server_family() or ""
        benchmark_map = {
            "Windows Server 2025": "CIS_Microsoft_Windows_Server_2022_Benchmark_v4.0.0.txt",
            "Windows Server 2022": "CIS_Microsoft_Windows_Server_2022_Benchmark_v4.0.0.txt",
            "Windows Server 2019": "CIS_Microsoft_Windows_Server_2019_Benchmark_v1.0.0.txt",
            "Windows Server 2016": "CIS_Microsoft_Windows_Server_2016_Benchmark_v1.0.0.txt",
            "Windows Server 2012 R2": "CIS_Microsoft_Windows_Server_2012_R2_Benchmark_v1.0.0.txt",
            "Windows Server 2012": "CIS_Microsoft_Windows_Server_2012_Benchmark_v1.0.0.txt",
            "Windows Server 2008 R2": "CIS_Microsoft_Windows_Server_2008_R2_Benchmark_v1.0.0.txt",
        }
        if server_family in benchmark_map:
            candidate = os.path.join(base_dir, benchmark_map[server_family])
            if os.path.exists(candidate):
                return candidate
        # Fallback to Server 2022 if specific version not found
        default = os.path.join(base_dir, "CIS_Microsoft_Windows_Server_2022_Benchmark_v4.0.0.txt")
        if os.path.exists(default):
            return default
        # Last resort: find any CIS benchmark file
        for filename in os.listdir(base_dir):
            if filename.lower().startswith("cis_microsoft") and filename.lower().endswith(".txt"):
                return os.path.join(base_dir, filename)
        return default

    def get_zh_overlay_path(self):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        from core.os_detection import get_server_family
        server_family = get_server_family() or ""
        zh_overlay_map = {
            "Windows Server 2025": "cis_items.zh_hk.json",
            "Windows Server 2022": "cis_items.zh_hk.json",
            "Windows Server 2019": "cis_items.2019.zh_hk.json",
            "Windows Server 2016": "cis_items.2016.zh_hk.json",
            "Windows Server 2012 R2": "cis_items.2012r2.zh_hk.json",
            "Windows Server 2012": "cis_items.2012.zh_hk.json",
            "Windows Server 2008 R2": "cis_items.2008r2.zh_hk.json",
        }
        if server_family in zh_overlay_map:
            candidate = os.path.join(base_dir, "data", zh_overlay_map[server_family])
            if os.path.exists(candidate):
                return candidate
        # Fallback to default zh overlay
        default = os.path.join(base_dir, "data", "cis_items.zh_hk.json")
        if os.path.exists(default):
            return default
        return None

    def load_benchmark_metadata(self):
        if self._benchmark_metadata is not None:
            return self._benchmark_metadata
        txt_path = self.get_benchmark_txt_path()
        if not txt_path or not os.path.exists(txt_path):
            self._benchmark_metadata = {}
            return self._benchmark_metadata
        try:
            from core.cis_parser import build_benchmark_metadata_index
            self._benchmark_metadata = build_benchmark_metadata_index(txt_path)
        except Exception:
            self._benchmark_metadata = {}
        return self._benchmark_metadata

    def load_items(self):
        json_path = os.path.join(os.path.dirname(__file__), "..", "data", "cis_items.json")
        zh_overlay_path = self.get_zh_overlay_path()
        benchmark_metadata = self.load_benchmark_metadata()
        overlay = {}
        if lang_manager.current_language.startswith("zh") and zh_overlay_path and os.path.exists(zh_overlay_path):
            try:
                with open(zh_overlay_path, "r", encoding="utf-8") as fzh:
                    data = json.load(fzh)
                    if isinstance(data, list):
                        overlay = {d.get("code"): d for d in data if isinstance(d, dict)}
                    elif isinstance(data, dict):
                        overlay = data
            except Exception:
                overlay = {}
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                items = json.load(f)
                self.items_table.blockSignals(True)
                for item in items:
                    it = dict(item)
                    ov = overlay.get(it.get("code"))
                    meta = benchmark_metadata.get(it.get("code", ""))
                    if meta:
                        for key in ("name", "verb", "recommended", "assessment", "tags", "full_text"):
                            if meta.get(key) and not it.get(key):
                                it[key] = meta.get(key)
                    if ov:
                        for key in ("description", "name", "verb", "recommended", "assessment", "tags", "full_text", "level"):
                            if ov.get(key) is not None:
                                it[key] = ov[key]
                    self.add_item_row(it)
                self.items_table.blockSignals(False)
        self.items_table.setColumnWidth(self.COL_NUMBER, 150)
        self.items_table.setColumnWidth(self.COL_LEVEL, 80)
        self.items_table.setColumnWidth(self.COL_NAME, 340)
        self.items_table.setColumnWidth(self.COL_ASSESSMENT, 180)
        self.items_table.setColumnWidth(self.COL_STATUS, 140)
        self.filter_items(self.search_edit.text())
        try:
            if is_client_supported():
                self.items_container.setVisible(True)
                self.btn_all_l1.setVisible(True)
                self.btn_all_l2.setVisible(True)
                self.btn_l1_l2.setVisible(True)
                self.btn_all.setVisible(True)
                self.btn_none.setVisible(True)
                self.btn_run.setVisible(True)
                self.btn_cancel.setVisible(True)
                self.btn_import_ps.setVisible(False)
                self.btn_delete_ps.setVisible(False)
                self.btn_apply_defaults.setVisible(False)
                self.btn_profile.setVisible(True)
            else:
                self.items_container.setVisible(True)
                self.btn_all_l1.setVisible(True)
                self.btn_all_l2.setVisible(True)
                self.btn_l1_l2.setVisible(True)
                self.btn_all.setVisible(True)
                self.btn_none.setVisible(True)
                self.btn_import_ps.setVisible(True)
                self.btn_delete_ps.setVisible(True)
                self.btn_apply_defaults.setVisible(True)
                self.btn_profile.setVisible(True)
                self.btn_run.setVisible(True)
                self.btn_cancel.setVisible(True)
        except Exception:
            pass

    def refresh_cis_items(self):
        # Save custom items
        custom_items = []
        for row in range(self.items_table.rowCount()):
            number_item = self.items_table.item(row, self.COL_NUMBER)
            if number_item:
                item_data = number_item.data(Qt.UserRole)
                if item_data and item_data.get("level") == "Custom":
                    custom_items.append(item_data)
        # Clear table
        self.items_table.setRowCount(0)
        # Reload CIS items
        self.load_items()
        # Re-add custom items
        for item in custom_items:
            self.add_item_row(item)
        # Restore filter
        self.filter_items(self.search_edit.text())

    def add_item_row(self, item):
        row = self.items_table.rowCount()
        self.items_table.insertRow(row)

        name, assessment = self.get_item_display_values(item)
        number_item = QTableWidgetItem(item.get("code", ""))
        number_item.setFlags(number_item.flags() | Qt.ItemIsUserCheckable)
        code = item.get("code", "")
        number_item.setCheckState(Qt.Checked if code in self.selected_codes else Qt.Unchecked)
        number_item.setData(Qt.UserRole, item)
        self.items_table.setItem(row, self.COL_NUMBER, number_item)

        level_item = QTableWidgetItem(item.get("level", ""))
        level_item.setTextAlignment(Qt.AlignCenter)
        self.items_table.setItem(row, self.COL_LEVEL, level_item)

        name_item = QTableWidgetItem(name)
        tooltip_text = (item.get("description", "") or name).strip()
        if tooltip_text:
            name_item.setToolTip(tooltip_text)
        self.items_table.setItem(row, self.COL_NAME, name_item)

        assessment_item = QTableWidgetItem(assessment)
        assessment_item.setTextAlignment(Qt.AlignCenter)
        self.items_table.setItem(row, self.COL_ASSESSMENT, assessment_item)

        status_text = self.get_translation_status(item)
        status_item = QTableWidgetItem(status_text)
        status_item.setTextAlignment(Qt.AlignCenter)
        if status_text == tr("translation_pending"):
            status_item.setForeground(Qt.red)
        self.items_table.setItem(row, self.COL_STATUS, status_item)

    def get_item_display_values(self, item):
        description = item.get("description", "")
        parsed_name, parsed_assessment = self.parse_item_description(description)
        name = parsed_name or (item.get("name", "") or "").strip() or (description or "").strip()
        untranslated_note = ""
        # If current language is Chinese but the chosen name is mostly ASCII (likely English),
        # prefer the description if it contains Chinese characters.
        try:
            from core.language_manager import lang_manager
            if lang_manager.current_language.startswith("zh"):
                def is_mostly_ascii(s: str) -> bool:
                    s = (s or "").strip()
                    if not s:
                        return False
                    ascii_count = sum(1 for ch in s if ord(ch) < 128)
                    return ascii_count / max(1, len(s)) > 0.7

                def contains_cjk(s: str) -> bool:
                    return any('\u4e00' <= ch <= '\u9fff' for ch in (s or ""))

                if is_mostly_ascii(name):
                    if contains_cjk(description):
                        name = description.strip()
                    else:
                        untranslated_note = "（英文）"
        except Exception:
            pass
        assessment = parsed_assessment
        if not assessment and item.get("assessment"):
            assessment = self.format_assessment_value(item.get("assessment"))
        if not assessment and item.get("tags"):
            assessment = self.format_assessment_value(item.get("tags"))
        if not assessment:
            assessment = tr("unknown")
        return f"{name}{untranslated_note}".strip(), assessment

    def normalize_assessment_tag(self, tag):
        value = " ".join((tag or "").split()).strip()
        mapping = {
            "automated": "Automated",
            "manual": "Manual",
            "ms only": "MS only",
            "dc only": "DC only"
        }
        return mapping.get(value.lower(), value)

    def format_assessment_value(self, value):
        if isinstance(value, str):
            tags = [part.strip() for part in value.split(",") if part.strip()]
        else:
            tags = [str(part).strip() for part in (value or []) if str(part).strip()]
        normalized = [self.normalize_assessment_tag(tag) for tag in tags]
        if lang_manager.current_language.startswith("zh"):
            zh_map = {
                "Automated": "自動化",
                "Manual": "手動",
                "MS only": "僅限 MS",
                "DC only": "僅限 DC"
            }
            normalized = [zh_map.get(tag, tag) for tag in normalized]
        return ", ".join(normalized)

    def parse_item_description(self, description):
        text = (description or "").strip()
        if not text:
            return "", ""
        tag_match = re.search(r"((?:\s*\([^()]*\))+)\s*$", text)
        if tag_match:
            tag_text = tag_match.group(1)
            base_name = text[:tag_match.start()].strip()
            tags = [part.strip() for part in re.findall(r"\(([^()]*)\)", tag_text) if part.strip()]
            return base_name, self.format_assessment_value(tags)
        return text, ""

    def get_translation_status(self, item):
        description = (item.get("description") or "").strip()
        if description.endswith("(待翻譯)") or description.endswith(" (待翻譯)"):
            return tr("translation_pending")
        return tr("translation_done")

    def check_environment(self):
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        status = tr("env_yes") if is_admin else tr("env_no")
        min_version = (3, 7)
        detected = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        required = f"{min_version[0]}.{min_version[1]}+"
        python_ok = (sys.version_info.major, sys.version_info.minor) >= min_version
        from core.os_detection import get_detailed_os_info
        try:
            osinfo = get_detailed_os_info()
        except Exception as e:
            osinfo = {"name": tr("unknown"), "version": "", "build": "", "product_type": "", "architecture": ""}
        lines = [tr("env_admin", status)]
        lines.append(tr("env_os_line", osinfo.get("name", ""), osinfo.get("version", "")))
        lines.append(tr("env_build_line", osinfo.get("build", ""), osinfo.get("architecture", ""), osinfo.get("product_type", "")))
        if python_ok:
            lines.append(tr("env_python_ok", detected, required))
        else:
            lines.append(tr("env_python_bad", detected, required))
        self.show_message("\n".join(lines), is_error=not python_ok)

    def is_running_as_admin(self):
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False

    def restart_as_admin(self):
        try:
            params = ""
            if getattr(sys, "frozen", False):
                exe = sys.executable
                params = ""
            else:
                base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
                exe = sys.executable
                script = os.path.join(base_dir, "main.py")
                params = f"\"{script}\""
            ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
            QApplication.quit()
        except Exception as exc:
            self.show_message(tr("apply_defaults_restart_failed", str(exc)), is_error=True)

    def ensure_cis_items_index(self):
        txt_path = self.get_benchmark_txt_path()
        json_path = os.path.join(os.path.dirname(__file__), "..", "data", "cis_items.json")
        if os.path.exists(json_path):
            return True, json_path
        if not txt_path or not os.path.exists(txt_path):
            return False, txt_path or ""
        try:
            from core.cis_parser import parse_benchmark_txt, write_items_json
            items = parse_benchmark_txt(txt_path)
            write_items_json(items, json_path)
            return True, json_path
        except Exception:
            return False, json_path

    def collect_checked_cis_codes(self):
        codes = []
        for row in range(self.items_table.rowCount()):
            number_item = self.items_table.item(row, self.COL_NUMBER)
            if not number_item:
                continue
            if number_item.checkState() != Qt.Checked:
                continue
            data = number_item.data(Qt.UserRole) or {}
            code = data.get("code") or number_item.text()
            if code:
                codes.append(code)
        return codes

    def on_apply_defaults_clicked(self):
        ok, detail = self.ensure_cis_items_index()
        if not ok:
            self.show_message(tr("apply_defaults_missing_data", detail), is_error=True)
            return
        checked_codes = self.collect_checked_cis_codes()
        count_text = str(len(checked_codes)) if checked_codes else tr("apply_defaults_all_hint")

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle(tr("apply_defaults_confirm_title"))
        msg.setText(tr("apply_defaults_confirm_text", count_text))

        btn_apply = msg.addButton(tr("apply_defaults_confirm_apply"), QMessageBox.AcceptRole)
        btn_undo = msg.addButton(tr("apply_defaults_confirm_undo"), QMessageBox.DestructiveRole)
        btn_save = msg.addButton(tr("apply_defaults_save_baseline"), QMessageBox.ActionRole)
        btn_restore = msg.addButton(tr("apply_defaults_restore_baseline"), QMessageBox.ActionRole)
        msg.addButton(tr("cancel"), QMessageBox.RejectRole)
        msg.exec_()

        clicked = msg.clickedButton()
        if clicked == btn_apply:
            self.start_apply_defaults(checked_codes)
        elif clicked == btn_undo:
            self.start_apply_defaults(checked_codes, undo=True)
        elif clicked == btn_save:
            self.start_save_baseline()
        elif clicked == btn_restore:
            self.start_restore_baseline()

    def build_apply_defaults_process_args(self, codes, report_dir, undo=False):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        script_path = os.path.join(base_dir, "scripts", "cis_apply.ps1")
        json_path = os.path.join(base_dir, "data", "cis_items.json")
        custom_mapping = os.path.join(base_dir, "data", "cis_mapping.custom.json")
        mapping_path = custom_mapping if os.path.exists(custom_mapping) else os.path.join(base_dir, "data", "cis_mapping.json")

        args = [
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            script_path,
            "-JsonPath",
            json_path,
            "-MappingPath",
            mapping_path,
            "-ReportDir",
            report_dir,
        ]

        if undo:
            args.append("-Undo")
            return "powershell.exe", args

        if codes:
            args.append("-Items")
            args.extend(codes)
        else:
            args.append("-SelectAll")

        return "powershell.exe", args

    def start_save_baseline(self):
        if not self.is_running_as_admin():
            self.show_message(tr("apply_defaults_not_admin"), is_error=True)
            return
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        script_path = os.path.join(base_dir, "scripts", "cis_apply.ps1")
        report_dir = self.path_edit.text()
        proc = QProcess(self)
        proc.setProgram("powershell.exe")
        proc.setArguments(["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path, "-ReportDir", report_dir, "-SaveBaseline"])
        self.btn_apply_defaults.setEnabled(False)
        self.progress_bar.setMaximum(0)
        self.progress_bar.setValue(0)
        self.show_message(tr("apply_defaults_saving_baseline"))
        proc.readyReadStandardOutput.connect(self.on_apply_defaults_output)
        proc.readyReadStandardError.connect(self.on_apply_defaults_output)
        proc.finished.connect(self.on_apply_defaults_finished)
        proc.start()
        self.apply_process = proc

    def start_restore_baseline(self):
        if not self.is_running_as_admin():
            self.show_message(tr("apply_defaults_not_admin"), is_error=True)
            return
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        script_path = os.path.join(base_dir, "scripts", "cis_apply.ps1")
        report_dir = self.path_edit.text()
        proc = QProcess(self)
        proc.setProgram("powershell.exe")
        proc.setArguments(["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path, "-ReportDir", report_dir, "-RestoreBaseline"])
        self.btn_apply_defaults.setEnabled(False)
        self.progress_bar.setMaximum(0)
        self.progress_bar.setValue(0)
        self.show_message(tr("apply_defaults_restoring_baseline"))
        proc.readyReadStandardOutput.connect(self.on_apply_defaults_output)
        proc.readyReadStandardError.connect(self.on_apply_defaults_output)
        proc.finished.connect(self.on_apply_defaults_finished)
        proc.start()
        self.apply_process = proc

    def start_apply_defaults(self, codes, undo=False):
        if self.apply_process is not None and self.apply_process.state() != QProcess.NotRunning:
            self.show_message(tr("apply_defaults_already_running"), is_error=True)
            return
        if not self.is_running_as_admin():
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle(tr("apply_defaults_not_admin_title"))
            msg.setText(tr("apply_defaults_not_admin"))
            btn_restart = msg.addButton(tr("apply_defaults_restart_admin"), QMessageBox.AcceptRole)
            msg.addButton(tr("cancel"), QMessageBox.RejectRole)
            msg.exec_()
            if msg.clickedButton() == btn_restart:
                self.restart_as_admin()
            return

        try:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        except Exception:
            timestamp = "now"

        base_report = self.path_edit.text()
        report_dir = os.path.join(base_report, f"cis_apply_{timestamp}")
        self.apply_report_dir = report_dir

        program, args = self.build_apply_defaults_process_args(codes, report_dir, undo=undo)

        self.btn_apply_defaults.setEnabled(False)
        self.progress_bar.setMaximum(0)
        self.progress_bar.setValue(0)
        self.show_message(tr("apply_defaults_running"))

        proc = QProcess(self)
        proc.setProgram(program)
        proc.setArguments(args)
        proc.readyReadStandardOutput.connect(self.on_apply_defaults_output)
        proc.readyReadStandardError.connect(self.on_apply_defaults_output)
        proc.finished.connect(self.on_apply_defaults_finished)
        proc.start()
        self.apply_process = proc

    def on_apply_defaults_output(self):
        if not self.apply_process:
            return
        out = bytes(self.apply_process.readAllStandardOutput()).decode("utf-8", errors="ignore").strip()
        err = bytes(self.apply_process.readAllStandardError()).decode("utf-8", errors="ignore").strip()
        combined = "\n".join([s for s in (out, err) if s]).strip()
        if combined:
            self.show_message(combined[:800])

    def on_apply_defaults_finished(self, exit_code, exit_status):
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.btn_apply_defaults.setEnabled(True)

        ok = (exit_status == QProcess.NormalExit and exit_code == 0)
        if not ok:
            self.show_message(tr("apply_defaults_failed", str(exit_code)), is_error=True)
            return

        report_dir = self.apply_report_dir or ""
        report_html = os.path.join(report_dir, "cis_apply.html")
        self.show_message(tr("apply_defaults_done", report_dir))
        if os.path.exists(report_html):
            try:
                QDesktopServices.openUrl(QUrl.fromLocalFile(report_html))
            except Exception:
                self.show_message(tr("apply_defaults_report_open_failed", report_html), is_error=True)

    def show_message(self, message, is_error=False):
        color = "#e74c3c" if is_error else "#2ecc71"
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {color}; font-weight: bold; padding: 5px; border: 1px solid {color}; border-radius: 5px; background-color: #fdfdfd;")

    def browse_path(self):
        dir_path = QFileDialog.getExistingDirectory(self, tr("select_output_path"))
        if dir_path:
            self.path_edit.setText(dir_path)

    def on_table_item_changed(self, item):
        if not item or item.column() != self.COL_NUMBER:
            return
        data = item.data(Qt.UserRole) or {}
        code = data.get("code") or item.text()
        if not code:
            return
        if item.checkState() == Qt.Checked:
            self.selected_codes.add(code)
        else:
            self.selected_codes.discard(code)

    def row_to_search_dict(self, row):
        number_item = self.items_table.item(row, self.COL_NUMBER)
        level_item = self.items_table.item(row, self.COL_LEVEL)
        name_item = self.items_table.item(row, self.COL_NAME)
        assessment_item = self.items_table.item(row, self.COL_ASSESSMENT)

        number_text = number_item.text() if number_item else ""
        level_text = level_item.text() if level_item else ""
        name_text = name_item.text() if name_item else ""
        assessment_text = assessment_item.text() if assessment_item else ""

        return {
            "code": (number_item.data(Qt.UserRole) or {}).get("code") if number_item else number_text,
            "number": number_text,
            "level": level_text,
            "name": name_text,
            "assessment": assessment_text,
        }

    def sync_checkstates_from_selected_codes(self):
        self.items_table.blockSignals(True)
        for row in range(self.items_table.rowCount()):
            number_item = self.items_table.item(row, self.COL_NUMBER)
            if not number_item:
                continue
            data = number_item.data(Qt.UserRole) or {}
            code = data.get("code") or number_item.text()
            if not code:
                continue
            number_item.setCheckState(Qt.Checked if code in self.selected_codes else Qt.Unchecked)
        self.items_table.blockSignals(False)

    def select_all(self, state):
        query_snapshot = self.search_edit.text()
        rows = [self.row_to_search_dict(row) for row in range(self.items_table.rowCount())]
        self.selected_codes = apply_bulk_selection(
            rows=rows,
            selected_codes=self.selected_codes,
            query=query_snapshot,
            select_state=state,
        )
        self.sync_checkstates_from_selected_codes()

    def select_by_filter(self, filter_str):
        query_snapshot = self.search_edit.text()
        level_filter = None
        if filter_str == "L1":
            level_filter = {"L1"}
        elif filter_str == "L2":
            level_filter = {"L2"}
        elif filter_str == "L1_L2":
            level_filter = {"L1", "L2"}

        rows = [self.row_to_search_dict(row) for row in range(self.items_table.rowCount())]
        next_selected = set(self.selected_codes)
        for row in rows:
            if not row_matches_query(row, query_snapshot):
                continue
            code = row.get("code") or row.get("number")
            if not code:
                continue
            if level_filter is not None and row.get("level") in level_filter:
                next_selected.add(code)
            else:
                next_selected.discard(code)
        self.selected_codes = next_selected
        self.sync_checkstates_from_selected_codes()

    def filter_items(self, text):
        query = text or ""
        for row in range(self.items_table.rowCount()):
            is_match = row_matches_query(self.row_to_search_dict(row), query)
            self.items_table.setRowHidden(row, not is_match)

    def import_ps_script(self):
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Question)
        msg.setWindowTitle(tr("import_ps_script"))
        msg.setText(tr("import_ps_choose_format"))

        btn_file = msg.addButton(tr("import_ps_from_file"), QMessageBox.AcceptRole)
        btn_paste = msg.addButton(tr("import_ps_paste_script"), QMessageBox.ActionRole)
        msg.addButton(tr("cancel"), QMessageBox.RejectRole)

        msg.exec_()
        clicked = msg.clickedButton()

        if clicked == btn_file:
            path, _ = QFileDialog.getOpenFileName(self, tr("import_ps_script"), "", "PowerShell Script (*.ps1)")
            if not path:
                return
            item = {
                "code": f"PS:{os.path.basename(path)}",
                "level": "Custom",
                "description": tr("ps_user_audit"),
                "script_path": path
            }
            self.add_item_row(item)
            self.filter_items(self.search_edit.text())
            self.show_message(tr("import_ps_success"))
            return

        if clicked == btn_paste:
            existing_codes = set()
            for row in range(self.items_table.rowCount()):
                number_item = self.items_table.item(row, self.COL_NUMBER)
                if not number_item:
                    continue
                data = number_item.data(Qt.UserRole) or {}
                code = data.get("code") or number_item.text()
                if code:
                    existing_codes.add(code)

            from gui.ps_import_dialog import PsScriptImportDialog
            dialog = PsScriptImportDialog(self, existing_codes=existing_codes)
            if dialog.exec_() == dialog.Accepted and dialog.result_item:
                self.add_item_row(dialog.result_item)
                self.filter_items(self.search_edit.text())
                self.show_message(tr("import_ps_success"))
            return

    def open_profile_manager(self):
        from gui.profile_dialog import ProfileDialog
        dialog = ProfileDialog(self, selected_codes=self.selected_codes)
        if dialog.exec_() == dialog.Accepted:
            profile_codes = getattr(dialog, "selected_profile_codes", None)
            if profile_codes is not None:
                self.apply_profile_codes(profile_codes)
        dialog.deleteLater()

    def apply_profile_codes(self, codes):
        self.selected_codes = {str(code) for code in (codes or []) if str(code).strip()}
        self.sync_checkstates_from_selected_codes()
        self.filter_items(self.search_edit.text())
        self.show_message(tr("profile_loaded", len(self.selected_codes)))

    def delete_ps_scripts(self):
        selection_model = self.items_table.selectionModel()
        if selection_model is None:
            self.show_message(tr("delete_ps_select"), is_error=True)
            return

        selected_rows = sorted({idx.row() for idx in selection_model.selectedRows()})
        if not selected_rows:
            self.show_message(tr("delete_ps_select"), is_error=True)
            return

        targets = []
        skipped = 0
        for row in selected_rows:
            number_item = self.items_table.item(row, self.COL_NUMBER)
            data = number_item.data(Qt.UserRole) if number_item else None
            if not data or not data.get("script_path"):
                skipped += 1
                continue
            targets.append((row, data))

        if not targets:
            self.show_message(tr("delete_ps_none"), is_error=True)
            return

        preview_lines = []
        for row, data in targets[:8]:
            preview_lines.append(f"{data.get('code', '')} - {data.get('script_path', '')}")
        if len(targets) > 8:
            preview_lines.append(tr("delete_ps_more", len(targets) - 8))

        confirm = QMessageBox(self)
        confirm.setIcon(QMessageBox.Warning)
        confirm.setWindowTitle(tr("delete_ps_title"))
        confirm.setText(tr("delete_ps_confirm", len(targets)))
        info_text = "\n".join(preview_lines).strip()
        if skipped:
            skipped_text = tr("delete_ps_skip_non", skipped)
            info_text = (skipped_text + ("\n\n" + info_text if info_text else "")).strip()
        if info_text:
            confirm.setInformativeText(info_text)

        btn_delete = confirm.addButton(tr("delete_ps_delete"), QMessageBox.DestructiveRole)
        confirm.addButton(tr("cancel"), QMessageBox.RejectRole)
        confirm.exec_()
        if confirm.clickedButton() != btn_delete:
            return

        from core.ps_import import delete_script_file

        ok_targets = []
        failures = []
        for row, data in targets:
            ok, detail = delete_script_file(data.get("script_path"))
            if ok:
                ok_targets.append((row, data))
            else:
                failures.append(f"{data.get('code', '')} - {detail}")

        for row, data in sorted(ok_targets, key=lambda x: x[0], reverse=True):
            code = data.get("code")
            if code:
                self.selected_codes.discard(code)
            self.items_table.removeRow(row)

        self.filter_items(self.search_edit.text())

        if failures:
            details_text = "\n".join(failures[:50])
            summary = tr("delete_ps_partial", len(ok_targets), len(failures))
            self.show_message(f"{summary} — {tr('delete_ps_failed_text')} {details_text}", is_error=True)
            return

        self.show_message(tr("delete_ps_success", len(ok_targets)))

    def _get_items_without_scripts(self, selected_items):
        missing = []
        for item in selected_items:
            script_path = self.resolve_item_script_path(item)
            if not script_path or not os.path.isfile(script_path):
                missing.append(item.get("code", "") or item.get("description", ""))
        return missing

    def resolve_item_script_path(self, item):
        script_path = ((item or {}).get("script_path") or "").strip()
        if not script_path:
            return ""
        if os.path.isabs(script_path):
            return script_path
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        return os.path.normpath(os.path.join(base_dir, script_path))

    def on_scan_mode_changed(self, index):
        mode = self.scan_mode_combo.itemData(index)
        is_remote = (mode == "remote")
        self.remote_target_label.setVisible(is_remote)
        self.remote_target_edit.setVisible(is_remote)

    def validate_remote_target(self, target):
        value = (target or "").strip()
        if not value:
            return False
        if "://" in value or "/" in value or "\\" in value:
            return False
        return bool(re.fullmatch(r"[A-Za-z0-9_.:-]+", value))

    def start_audit(self):
        selected_items = []
        for row in range(self.items_table.rowCount()):
            number_item = self.items_table.item(row, self.COL_NUMBER)
            if number_item and number_item.checkState() == Qt.Checked:
                selected_items.append(number_item.data(Qt.UserRole))
        if not selected_items:
            self.show_message(tr("select_at_least_one"), is_error=True)
            return

        scan_mode = self.scan_mode_combo.currentData()
        remote_target = None
        if scan_mode == "remote":
            remote_target = self.remote_target_edit.text().strip()
            if not remote_target:
                self.show_message(tr("remote_target_required"), is_error=True)
                return
            if not self.validate_remote_target(remote_target):
                self.show_message(tr("remote_target_invalid"), is_error=True)
                return

        missing_scripts = self._get_items_without_scripts(selected_items)
        if missing_scripts:
            missing_count = len(missing_scripts)
            preview = ", ".join(missing_scripts[:8])
            if missing_count > 8:
                preview += f" ... (+{missing_count - 8})"

            if missing_count == len(selected_items):
                msg = tr("audit_all_missing_scripts", missing_count)
            else:
                msg = tr("audit_partial_missing_scripts", missing_count, len(selected_items))

            confirm = QMessageBox(self)
            confirm.setIcon(QMessageBox.Warning)
            confirm.setWindowTitle(tr("audit_missing_scripts_title"))
            confirm.setText(msg)
            confirm.setInformativeText(f"{tr('audit_missing_scripts_detail')}: {preview}")
            btn_continue = confirm.addButton(tr("audit_continue_anyway"), QMessageBox.AcceptRole)
            confirm.addButton(tr("cancel"), QMessageBox.RejectRole)
            confirm.exec_()
            if confirm.clickedButton() != btn_continue:
                return

        self.show_message(tr("scanning"))
        self.btn_run.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(len(selected_items))

        output_dir = self.path_edit.text()
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        self.scanner = Scanner(
            selected_items, output_dir,
            scan_mode=scan_mode,
            remote_target=remote_target
        )
        self.scanner.progress_signal.connect(self.update_progress)
        self.scanner.finished_signal.connect(self.audit_finished)
        self.scanner.start()

    def update_progress(self, val):
        self.progress_bar.setValue(val)

    def cancel_audit(self):
        if self.scanner:
            self.scanner.stop()
            self.btn_cancel.setEnabled(False)

    def audit_finished(self, report_path):
        self.btn_run.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.btn_reopen.setEnabled(True)
        if report_path:
            try:
                # Switch to report window
                from gui.report_window import ReportWindow
                self.report_window = ReportWindow(report_path)
                if hasattr(self.report_window, 'report_data'):
                    self.show_message(tr("scan_complete"))
                    self.report_window.show()
                else:
                    self.show_message(tr("report_load_failed"), is_error=True)
            except Exception as e:
                self.show_message(tr("report_open_failed", str(e)), is_error=True)
            # self.hide() # Keep main window open or hide it? User said "auto turn window"

    def open_latest_report(self):
        output_dir = self.path_edit.text()
        latest = self.find_latest_report(output_dir)
        if latest:
            try:
                from gui.report_window import ReportWindow
                self.report_window = ReportWindow(latest)
                if hasattr(self.report_window, 'report_data'):
                    self.show_message(tr("report_opened_latest"))
                    self.report_window.show()
                else:
                    self.show_message(tr("report_load_failed"), is_error=True)
            except Exception as e:
                self.show_message(tr("report_open_failed", str(e)), is_error=True)

    def check_latest_report(self):
        output_dir = self.path_edit.text()
        self.btn_reopen.setEnabled(bool(self.find_latest_report(output_dir)))

    def is_scan_report_file(self, path):
        filename = os.path.basename(path).lower()
        if not (filename.startswith("report_") and filename.endswith(".json")):
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return isinstance(data, dict) and isinstance(data.get("results"), list)
        except Exception:
            return False

    def find_latest_report(self, output_dir):
        if not os.path.isdir(output_dir):
            return ""
        files = []
        for filename in os.listdir(output_dir):
            path = os.path.join(output_dir, filename)
            if os.path.isfile(path) and self.is_scan_report_file(path):
                files.append(path)
        if not files:
            return ""
        return max(files, key=os.path.getmtime)

    def change_language(self, index):
        lang_code = "en" if index == 0 else "zh_hk"
        lang_manager.load_language(lang_code)
        self.retranslate_ui()
        self.refresh_cis_items()

    def retranslate_ui(self):
        self.setWindowTitle(tr("app_title"))
        self.btn_check_env.setText(tr("check_env"))
        self.btn_apply_defaults.setText(tr("apply_defaults"))
        self.btn_apply_defaults.setToolTip(tr("apply_defaults_tooltip"))
        self.btn_apply_defaults.setAccessibleName(tr("apply_defaults_accessible_name"))
        self.btn_apply_defaults.setAccessibleDescription(tr("apply_defaults_accessible_desc"))
        self.btn_help.setToolTip(tr("help_tooltip"))
        self.btn_bg.setText(tr("bg_button"))
        self.btn_bg.setToolTip(tr("bg_tooltip"))
        self.btn_browse.setText(tr("browse"))
        self.btn_all_l1.setText(tr("select_all_l1"))
        self.btn_all_l2.setText(tr("select_all_l2"))
        self.btn_l1_l2.setText(tr("select_l1_l2"))
        self.btn_all.setText(tr("select_all"))
        self.btn_none.setText(tr("deselect_all"))
        self.btn_import_ps.setText(tr("import_ps_script"))
        self.btn_delete_ps.setText(tr("delete_ps_script"))
        self.btn_profile.setText(tr("profile_manage"))
        self.btn_profile.setToolTip(tr("profile_manage_tooltip"))
        self.search_edit.setPlaceholderText(tr("search_placeholder"))
        self.btn_run.setText(tr("run_audit"))
        self.btn_cancel.setText(tr("cancel"))
        self.btn_reopen.setText(tr("reopen_report"))
        self.guide_title.setText(tr("guide_title"))
        self.guide_body.setText(tr("guide_body"))
        self.scan_mode_combo.setItemText(0, tr("scan_mode_local"))
        self.scan_mode_combo.setItemText(1, tr("scan_mode_domain"))
        self.scan_mode_combo.setItemText(2, tr("scan_mode_remote"))
        self.remote_target_label.setText(tr("remote_target_label"))
        self.remote_target_edit.setPlaceholderText(tr("remote_target_placeholder"))
        self.btn_remote_config.setText(tr("remote_config_button"))
        self.btn_remote_config.setToolTip(tr("remote_config_button_tooltip"))
        self.items_table.setHorizontalHeaderLabels([
            tr("cis_col_number"),
            tr("cis_col_level"),
            tr("cis_col_name"),
            tr("cis_col_assessment"),
            tr("cis_col_status")
        ])

def main():
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

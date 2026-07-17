import os
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QLineEdit, QTextEdit,
    QMessageBox, QFileDialog, QWidget, QSplitter, QGroupBox,
    QFormLayout, QDialogButtonBox, QAbstractItemView
)
from PyQt5.QtCore import Qt
from core.language_manager import tr
from core.profile_manager import (
    list_profiles, get_profile, save_profile, delete_profile,
    export_profile_to_file, import_profile_from_file
)


class ProfileDialog(QDialog):
    def __init__(self, parent=None, selected_codes=None):
        super().__init__(parent)
        self.selected_codes = selected_codes or set()
        self.selected_profile_codes = None
        self.current_profile_name = None
        self.setWindowTitle(tr("profile_dialog_title"))
        self.setMinimumSize(700, 500)
        self.init_ui()
        self.refresh_profile_list()

    def init_ui(self):
        main_layout = QHBoxLayout(self)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.profile_list = QListWidget()
        self.profile_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.profile_list.currentRowChanged.connect(self.on_profile_selected)
        self.profile_list.itemDoubleClicked.connect(lambda _item: self.on_load_profile())
        left_layout.addWidget(QLabel(tr("profile_name")))
        left_layout.addWidget(self.profile_list)

        btn_layout = QHBoxLayout()
        self.btn_new = QPushButton(tr("profile_new"))
        self.btn_new.clicked.connect(self.on_new_profile)
        self.btn_load = QPushButton(tr("profile_load"))
        self.btn_load.clicked.connect(self.on_load_profile)
        self.btn_delete = QPushButton(tr("profile_delete"))
        self.btn_delete.clicked.connect(self.on_delete_profile)
        btn_layout.addWidget(self.btn_new)
        btn_layout.addWidget(self.btn_load)
        btn_layout.addWidget(self.btn_delete)
        left_layout.addLayout(btn_layout)

        export_import_layout = QHBoxLayout()
        self.btn_export = QPushButton(tr("profile_export"))
        self.btn_export.clicked.connect(self.on_export_profile)
        self.btn_import = QPushButton(tr("profile_import"))
        self.btn_import.clicked.connect(self.on_import_profile)
        export_import_layout.addWidget(self.btn_export)
        export_import_layout.addWidget(self.btn_import)
        left_layout.addLayout(export_import_layout)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        form_group = QGroupBox(tr("profile_details"))
        form_layout = QFormLayout(form_group)

        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText(tr("profile_name"))
        form_layout.addRow(tr("profile_name"), self.edit_name)

        self.edit_target_os = QLineEdit()
        self.edit_target_os.setPlaceholderText("e.g. Windows Server 2022, Windows 11")
        form_layout.addRow(tr("profile_target_os"), self.edit_target_os)

        self.edit_description = QTextEdit()
        self.edit_description.setPlaceholderText(tr("profile_description"))
        self.edit_description.setMaximumHeight(80)
        form_layout.addRow(tr("profile_description"), self.edit_description)

        right_layout.addWidget(form_group)

        info_label = QLabel(tr("profile_current_items"))
        info_label.setWordWrap(True)
        right_layout.addWidget(info_label)

        self.items_count_label = QLabel(tr("profile_items_count", len(self.selected_codes)))
        right_layout.addWidget(self.items_count_label)

        right_layout.addStretch()

        button_box = QDialogButtonBox()
        self.btn_save = button_box.addButton(tr("profile_save"), QDialogButtonBox.AcceptRole)
        self.btn_cancel = button_box.addButton(tr("profile_cancel"), QDialogButtonBox.RejectRole)
        self.btn_save.clicked.connect(self.on_save_profile)
        self.btn_cancel.clicked.connect(self.reject)
        right_layout.addWidget(button_box)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 400])
        main_layout.addWidget(splitter)

    def refresh_profile_list(self):
        self.profile_list.blockSignals(True)
        self.profile_list.clear()
        profiles = list_profiles()
        target_row = -1
        for p in profiles:
            item = QListWidgetItem(p["name"])
            item.setData(Qt.UserRole, p)
            self.profile_list.addItem(item)
            if p["name"] == self.current_profile_name:
                target_row = self.profile_list.count() - 1
        self.profile_list.blockSignals(False)

        if target_row >= 0:
            self.profile_list.setCurrentRow(target_row)

    def on_profile_selected(self, row):
        if row < 0:
            self.clear_form()
            return
        item = self.profile_list.item(row)
        if not item:
            return
        profile_data = item.data(Qt.UserRole)
        if not profile_data:
            return
        self.current_profile_name = profile_data["name"]
        self.edit_name.setText(profile_data["name"])
        self.edit_target_os.setText(profile_data.get("target_os", ""))
        self.edit_description.setText(profile_data.get("description", ""))
        items = profile_data.get("items", [])
        self.items_count_label.setText(tr("profile_items_count", len(items)))

    def clear_form(self):
        self.current_profile_name = None
        self.edit_name.clear()
        self.edit_target_os.clear()
        self.edit_description.clear()
        self.items_count_label.setText(tr("profile_items_count", 0))

    def on_new_profile(self):
        self.clear_form()
        self.profile_list.clearSelection()
        self.edit_name.setFocus()

    def on_save_profile(self):
        name = self.edit_name.text().strip()
        if not name:
            QMessageBox.warning(self, tr("profile_name_required"), tr("profile_name_required"))
            self.edit_name.setFocus()
            return
        target_os = self.edit_target_os.text().strip()
        description = self.edit_description.toPlainText().strip()
        items = list(self.selected_codes)

        ok, result = save_profile(name, target_os, description, items)
        if ok:
            self.current_profile_name = name
            self.refresh_profile_list()
            QMessageBox.information(self, tr("profile_saved"), tr("profile_saved", name))
        else:
            QMessageBox.critical(self, tr("profile_save_failed"), tr("profile_save_failed", result))

    def on_load_profile(self):
        if not self.current_profile_name:
            QMessageBox.warning(self, tr("profile_no_selection"), tr("profile_no_selection"))
            return
        profile = get_profile(self.current_profile_name)
        if profile is None:
            QMessageBox.warning(self, tr("profile_no_selection"), tr("profile_no_selection"))
            return
        items = profile.get("items", [])
        if not isinstance(items, list):
            items = []
        self.selected_profile_codes = {str(code) for code in items if str(code).strip()}
        self.accept()

    def on_delete_profile(self):
        if not self.current_profile_name:
            QMessageBox.warning(self, tr("profile_no_selection"), tr("profile_no_selection"))
            return
        confirm = QMessageBox.question(
            self,
            tr("profile_confirm_delete_title"),
            tr("profile_confirm_delete", self.current_profile_name),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return
        ok, err = delete_profile(self.current_profile_name)
        if ok:
            self.clear_form()
            self.refresh_profile_list()
            QMessageBox.information(self, tr("profile_deleted"), tr("profile_deleted"))
        else:
            QMessageBox.critical(self, tr("profile_delete_failed"), tr("profile_delete_failed", err))

    def on_export_profile(self):
        if not self.current_profile_name:
            QMessageBox.warning(self, tr("profile_no_selection"), tr("profile_no_selection"))
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, tr("profile_export"), f"{self.current_profile_name}.json",
            tr("profile_export_filter")
        )
        if not file_path:
            return
        ok, result = export_profile_to_file(self.current_profile_name, file_path)
        if ok:
            QMessageBox.information(self, tr("profile_exported"), tr("profile_exported", result))
        else:
            QMessageBox.critical(self, tr("profile_export_failed"), tr("profile_export_failed", result))

    def on_import_profile(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, tr("profile_import"), "", tr("profile_import_filter")
        )
        if not file_path:
            return
        ok, result = import_profile_from_file(file_path)
        if ok:
            self.current_profile_name = result
            self.refresh_profile_list()
            QMessageBox.information(self, tr("profile_imported"), tr("profile_imported", result))
            profile = get_profile(result)
            items = profile.get("items", []) if profile else []
            if not isinstance(items, list):
                items = []
            self.selected_profile_codes = {str(code) for code in items if str(code).strip()}
            self.accept()
        else:
            QMessageBox.critical(self, tr("profile_import_failed"), tr("profile_import_failed", result))

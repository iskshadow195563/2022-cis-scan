import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
)

from core.language_manager import tr
from core.ps_import import (
    VALID_MODES,
    build_description,
    is_valid_script_number,
    normalize_mode,
    normalize_ps_code,
    normalize_powershell_script_text,
    normalize_script_number,
    save_powershell_script,
)


class PsScriptImportDialog(QDialog):
    def __init__(self, parent=None, existing_codes=None, scripts_dir=None):
        super().__init__(parent)
        self.existing_codes = set(existing_codes or set())
        if scripts_dir is None:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            scripts_dir = os.path.join(base_dir, "user_scripts")
        self.scripts_dir = scripts_dir
        self.result_item = None
        self._init_ui()
        self._revalidate()

    def _init_ui(self):
        self.setWindowTitle(tr("import_ps_paste_title"))
        self.setWindowModality(Qt.ApplicationModal)
        self.setMinimumSize(760, 560)

        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.number_edit = QLineEdit()
        self.number_edit.setPlaceholderText(tr("import_ps_number_placeholder"))
        self.number_edit.textChanged.connect(self._revalidate)
        form.addRow(tr("import_ps_number_label"), self.number_edit)

        self.level_combo = QComboBox()
        self.level_combo.setEditable(True)
        self.level_combo.addItem(tr("import_ps_level_custom"), "Custom")
        self.level_combo.addItem("L1", "L1")
        self.level_combo.addItem("L2", "L2")
        self.level_combo.currentTextChanged.connect(self._revalidate)
        form.addRow(tr("import_ps_level_label"), self.level_combo)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(tr("import_ps_name_placeholder"))
        self.name_edit.textChanged.connect(self._revalidate)
        form.addRow(tr("import_ps_name_label"), self.name_edit)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem(tr("import_ps_mode_auto"), "auto")
        self.mode_combo.addItem(tr("import_ps_mode_ms_only"), "ms only")
        self.mode_combo.addItem(tr("import_ps_mode_manual"), "manual")
        self.mode_combo.currentTextChanged.connect(self._revalidate)
        form.addRow(tr("import_ps_mode_label"), self.mode_combo)

        layout.addLayout(form)

        script_label_row = QHBoxLayout()
        script_label = QLabel(tr("import_ps_script_label"))
        script_label_row.addWidget(script_label)
        script_label_row.addStretch()
        layout.addLayout(script_label_row)

        self.script_edit = QTextEdit()
        self.script_edit.setAcceptRichText(False)
        self.script_edit.setFont(QFont("Consolas", 10))
        self.script_edit.textChanged.connect(self._revalidate)
        layout.addWidget(self.script_edit, 1)

        self.validation_label = QLabel("")
        self.validation_label.setWordWrap(True)
        layout.addWidget(self.validation_label)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self._on_save)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _set_field_error(self, widget, has_error: bool):
        if has_error:
            widget.setStyleSheet("border: 1px solid #e74c3c; border-radius: 4px;")
        else:
            widget.setStyleSheet("")

    def _validate(self):
        errors = []

        number_text = self.number_edit.text()
        number = normalize_script_number(number_text)
        number_required_error = False
        number_format_error = False
        number_duplicate_error = False
        if not number:
            number_required_error = True
            errors.append(tr("import_ps_err_number_required"))
        elif not is_valid_script_number(number):
            number_format_error = True
            errors.append(tr("import_ps_err_number_format"))

        code = normalize_ps_code(number)
        if code and code in self.existing_codes:
            number_duplicate_error = True
            errors.append(tr("import_ps_err_number_duplicate"))

        level = (self.level_combo.currentData() or self.level_combo.currentText() or "").strip()
        level_required_error = False
        if not level:
            level_required_error = True
            errors.append(tr("import_ps_err_level_required"))

        name = (self.name_edit.text() or "").strip()
        name_required_error = False
        if not name:
            name_required_error = True
            errors.append(tr("import_ps_err_name_required"))

        mode = normalize_mode(self.mode_combo.currentData() or self.mode_combo.currentText())
        mode_invalid_error = False
        if mode not in VALID_MODES:
            mode_invalid_error = True
            errors.append(tr("import_ps_err_mode_invalid"))

        script_raw = self.script_edit.toPlainText()
        normalized_script = normalize_powershell_script_text(script_raw)
        script_required_error = False
        if not normalized_script.strip():
            script_required_error = True
            errors.append(tr("import_ps_err_script_required"))

        field_errors = {
            "number": number_required_error or number_format_error or number_duplicate_error,
            "level": level_required_error,
            "name": name_required_error,
            "mode": mode_invalid_error,
            "script": script_required_error,
        }

        return errors, code, level, name, mode, normalized_script, field_errors

    def _revalidate(self):
        errors, code, level, name, mode, normalized_script, field_errors = self._validate()
        self._set_field_error(self.number_edit, field_errors["number"])
        self._set_field_error(self.level_combo, field_errors["level"])
        self._set_field_error(self.name_edit, field_errors["name"])
        self._set_field_error(self.mode_combo, field_errors["mode"])
        self._set_field_error(self.script_edit, field_errors["script"])

        save_btn = self.buttons.button(QDialogButtonBox.Save)
        save_btn.setEnabled(len(errors) == 0)

        if errors:
            self.validation_label.setText(errors[0])
            self.validation_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
        else:
            preview = build_description(name, mode)
            self.validation_label.setText(tr("import_ps_ready_preview", code, preview))
            self.validation_label.setStyleSheet("color: #2ecc71; font-weight: bold;")

    def _on_save(self):
        errors, code, level, name, mode, normalized_script, _field_errors = self._validate()
        if errors:
            self._revalidate()
            return

        filename_base = f"{normalize_script_number(code.replace('PS:', ''))}_{name}"
        script_path = save_powershell_script(normalized_script, self.scripts_dir, filename_base)

        item = {
            "code": code,
            "level": level,
            "description": build_description(name, mode),
            "script_path": script_path,
            "ps_mode": mode,
        }
        self.result_item = item
        self.accept()

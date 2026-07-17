import subprocess
import sys
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QGroupBox, QFormLayout, QMessageBox,
    QListWidget, QListWidgetItem, QAbstractItemView, QApplication
)
from core.language_manager import tr


class WinRMConfigWorker(QThread):
    output_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, commands, parent=None):
        super().__init__(parent)
        self.commands = commands

    def run(self):
        all_ok = True
        last_error = ""
        for title, cmd in self.commands:
            self.output_signal.emit(f">> {title}...\n")
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=30,
                    shell=True
                )
                if proc.stdout:
                    self.output_signal.emit(proc.stdout + "\n")
                if proc.stderr:
                    self.output_signal.emit(proc.stderr + "\n")
                if proc.returncode != 0:
                    all_ok = False
                    last_error = proc.stderr.strip()
                    self.output_signal.emit(f"  [WARNING] Exit code: {proc.returncode}\n")
                else:
                    self.output_signal.emit(f"  [OK]\n")
            except Exception as e:
                all_ok = False
                last_error = str(e)
                self.output_signal.emit(f"  [ERROR] {e}\n")
        self.finished_signal.emit(all_ok, last_error)


class RemoteConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("remote_config_title"))
        self.setMinimumSize(600, 500)
        self.setModal(True)
        self._worker = None
        self._is_admin = self._check_admin()
        self._init_ui()
        self._load_current_trusted_hosts()
        if not self._is_admin:
            self._show_admin_warning()

    @staticmethod
    def _check_admin():
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False

    def _show_admin_warning(self):
        self.admin_banner.setText(tr("remote_config_admin_warning"))
        self.admin_banner.setStyleSheet(
            "background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; "
            "border-radius: 6px; padding: 10px; font-weight: bold;"
        )
        self.admin_banner.setVisible(True)
        self.log_output.append(tr("remote_config_admin_warning"))
        self.log_output.append("")
        self._set_buttons_enabled(False)

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # --- Admin status banner ---
        self.admin_banner = QLabel()
        self.admin_banner.setVisible(False)
        self.admin_banner.setWordWrap(True)
        layout.addWidget(self.admin_banner)

        # --- Trusted Hosts Section ---
        trusted_group = QGroupBox(tr("remote_config_trusted_hosts"))
        trusted_layout = QVBoxLayout(trusted_group)

        ip_layout = QHBoxLayout()
        ip_layout.addWidget(QLabel(tr("remote_config_ip_label")))
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText(tr("remote_config_ip_placeholder"))
        ip_layout.addWidget(self.ip_input, 1)

        self.btn_add_trust = QPushButton(tr("remote_config_add_trust"))
        self.btn_add_trust.clicked.connect(self._add_trusted_host)
        ip_layout.addWidget(self.btn_add_trust)

        self.btn_remove_trust = QPushButton(tr("remote_config_remove_trust"))
        self.btn_remove_trust.clicked.connect(self._remove_trusted_host)
        ip_layout.addWidget(self.btn_remove_trust)

        trusted_layout.addLayout(ip_layout)

        self.trusted_list = QListWidget()
        self.trusted_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        trusted_layout.addWidget(self.trusted_list)

        layout.addWidget(trusted_group)

        # --- WinRM Status & Actions ---
        actions_group = QGroupBox(tr("remote_config_actions"))
        actions_layout = QVBoxLayout(actions_group)

        btn_layout = QHBoxLayout()
        self.btn_test_conn = QPushButton(tr("remote_config_test"))
        self.btn_test_conn.clicked.connect(self._test_connection)
        btn_layout.addWidget(self.btn_test_conn)

        self.btn_enable_winrm = QPushButton(tr("remote_config_enable_winrm"))
        self.btn_enable_winrm.clicked.connect(self._enable_winrm)
        btn_layout.addWidget(self.btn_enable_winrm)

        self.btn_open_firewall = QPushButton(tr("remote_config_firewall"))
        self.btn_open_firewall.clicked.connect(self._open_firewall)
        btn_layout.addWidget(self.btn_open_firewall)

        actions_layout.addLayout(btn_layout)

        layout.addWidget(actions_group)

        # --- Output Log ---
        log_group = QGroupBox(tr("remote_config_log"))
        log_layout = QVBoxLayout(log_group)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(self.log_output.font() or QApplication.font())
        log_layout.addWidget(self.log_output)
        layout.addWidget(log_group, 1)

        # --- Close Button ---
        btn_close_layout = QHBoxLayout()
        btn_close_layout.addStretch()
        self.btn_close = QPushButton(tr("close"))
        self.btn_close.clicked.connect(self.close)
        btn_close_layout.addWidget(self.btn_close)
        layout.addLayout(btn_close_layout)

    def _load_current_trusted_hosts(self):
        self.trusted_list.clear()
        try:
            proc = subprocess.run(
                'powershell.exe -NoProfile -Command "(Get-Item WSMan:\\localhost\\Client\\TrustedHosts).Value"',
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                shell=True
            )
            if proc.returncode == 0:
                value = proc.stdout.strip()
                if value:
                    entries = value.split(",")
                    for entry in entries:
                        entry = entry.strip()
                        if entry:
                            item = QListWidgetItem(entry)
                            self.trusted_list.addItem(item)
        except Exception:
            pass

    def _add_trusted_host(self):
        ip = self.ip_input.text().strip()
        if not ip:
            QMessageBox.warning(self, tr("remote_config_warning_title"), tr("remote_config_ip_required"))
            return

        existing = []
        for i in range(self.trusted_list.count()):
            existing.append(self.trusted_list.item(i).text())

        if ip in existing:
            QMessageBox.information(self, tr("remote_config_info_title"), tr("remote_config_already_exists"))
            return

        new_list = existing + [ip]
        joined = ",".join(new_list)
        ps_cmd = f'Set-Item WSMan:\\localhost\\Client\\TrustedHosts -Value \'{joined}\' -Force'
        self._run_commands([
            (tr("remote_config_adding", ip), f'powershell.exe -NoProfile -Command "{ps_cmd}"'),
        ])

    def _remove_trusted_host(self):
        selected = self.trusted_list.selectedItems()
        if not selected:
            QMessageBox.warning(self, tr("remote_config_warning_title"), tr("remote_config_select_remove"))
            return

        existing = []
        for i in range(self.trusted_list.count()):
            item = self.trusted_list.item(i)
            if item not in selected:
                existing.append(item.text())

        if existing:
            joined = ",".join(existing)
            ps_cmd = f'Set-Item WSMan:\\localhost\\Client\\TrustedHosts -Value \'{joined}\' -Force'
        else:
            ps_cmd = 'Clear-Item WSMan:\\localhost\\Client\\TrustedHosts -Force'
        self._run_commands([
            (tr("remote_config_removing"), f'powershell.exe -NoProfile -Command "{ps_cmd}"'),
        ])

    def _test_connection(self):
        ip = self.ip_input.text().strip()
        if not ip:
            QMessageBox.warning(self, tr("remote_config_warning_title"), tr("remote_config_ip_required"))
            return

        commands = [
            (tr("remote_config_testing_ping", ip), f"ping -n 2 {ip}"),
            (tr("remote_config_testing_winrm", ip), f'powershell.exe -NoProfile -Command "Test-WSMan -ComputerName {ip}"'),
        ]
        self._run_commands(commands)

    def _enable_winrm(self):
        commands = [
            (tr("remote_config_enabling_winrm"), "powershell.exe -NoProfile -Command \"Enable-PSRemoting -Force -SkipNetworkProfileCheck\""),
            (tr("remote_config_setting_auth"), 'powershell.exe -NoProfile -Command "Set-Item WSMan:\\localhost\\Service\\Auth\\Basic -Value $true -Force"'),
        ]
        self._run_commands(commands)

    def _open_firewall(self):
        commands = [
            (tr("remote_config_firewall_5985"), 'powershell.exe -NoProfile -Command "New-NetFirewallRule -DisplayName \'WinRM-HTTP\' -Direction Inbound -Protocol TCP -LocalPort 5985 -Action Allow -Profile Any -ErrorAction SilentlyContinue"'),
            (tr("remote_config_firewall_5986"), 'powershell.exe -NoProfile -Command "New-NetFirewallRule -DisplayName \'WinRM-HTTPS\' -Direction Inbound -Protocol TCP -LocalPort 5986 -Action Allow -Profile Any -ErrorAction SilentlyContinue"'),
        ]
        self._run_commands(commands)

    def _run_commands(self, commands):
        if self._worker and self._worker.isRunning():
            QMessageBox.warning(self, tr("remote_config_warning_title"), tr("remote_config_busy"))
            return

        self._set_buttons_enabled(False)
        self.log_output.clear()

        self._worker = WinRMConfigWorker(commands)
        self._worker.output_signal.connect(self._append_log)
        self._worker.finished_signal.connect(self._on_commands_finished)
        self._worker.start()

    def _append_log(self, text):
        self.log_output.append(text)

    def _on_commands_finished(self, success, error):
        self._set_buttons_enabled(True)
        self._load_current_trusted_hosts()
        if success:
            self.log_output.append(tr("remote_config_success"))
        else:
            self.log_output.append(tr("remote_config_failed", error))

    def _set_buttons_enabled(self, enabled):
        self.btn_add_trust.setEnabled(enabled)
        self.btn_remove_trust.setEnabled(enabled)
        self.btn_test_conn.setEnabled(enabled)
        self.btn_enable_winrm.setEnabled(enabled)
        self.btn_open_firewall.setEnabled(enabled)
        self.ip_input.setEnabled(enabled)

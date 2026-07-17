import sys
import importlib.util
import random
from core.language_manager import tr
from core.startup_manager import StartupManager

def check_python_version():
    """Checks if the Python version is 3.13 or lower (stable range)."""
    major, minor = sys.version_info[:2]
    if major != 3 or minor > 13:
        # If PyQt5 is available, use a GUI alert, otherwise use console
        warning_msg = tr("python_version_warning", f"{major}.{minor}")

        if importlib.util.find_spec("PyQt5") is not None:
            try:
                from PyQt5.QtWidgets import QApplication, QMessageBox
                # Check if an instance already exists
                app = QApplication.instance()
                if not app:
                    app = QApplication(sys.argv)

                msg = QMessageBox()
                msg.setIcon(QMessageBox.Warning)
                msg.setText(tr("incompatible_python_title"))
                msg.setInformativeText(tr("incompatible_python_informative", warning_msg))
                msg.setWindowTitle(tr("incompatible_python_title"))
                msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)

                if msg.exec_() == QMessageBox.No:
                    sys.exit(0)
            except Exception:
                print(warning_msg)
        else:
            print(warning_msg)
            choice = input(tr("continue_prompt")).lower()
            if choice != 'y':
                sys.exit(0)

def show_startup_error(title: str, message: str):
    if importlib.util.find_spec("PyQt5") is not None:
        try:
            from PyQt5.QtWidgets import QApplication, QMessageBox

            app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(None, title, message)
            return
        except Exception:
            pass

    print(f"{title}: {message}")


def check_dependencies(startup_manager: StartupManager = None):
    startup_manager = startup_manager or StartupManager()

    # Mapping of import name to pip package name
    dependencies = {
        "PyQt5": "PyQt5",
        "docx": "python-docx",
        "matplotlib": "matplotlib",
        "psutil": "psutil",
        "openpyxl": "openpyxl",
        "requests": "requests",
    }

    missing = []
    for imp_name, pkg_name in dependencies.items():
        if importlib.util.find_spec(imp_name) is None:
            missing.append((imp_name, pkg_name))

    if not missing:
        return True

    # If PyQt5 is missing, use console for interaction (language manager available)
    if importlib.util.find_spec("PyQt5") is None:
        missing_names = ", ".join([m[1] for m in missing])
        try:
            choice = input(tr("missing_dependencies_informative", missing_names) + " (y/n): ").lower()
        except Exception:
            print(tr("missing_dependencies_title"))
            print(tr("missing_dependencies_informative", missing_names))
            return False
        if choice == 'y':
            try:
                outcome = startup_manager.install_packages_and_restart([pkg_name for _, pkg_name in missing])
                if outcome.error:
                    title = tr("auto_restart_failed_title") if outcome.failed_stage == "restart" else tr("deps_install_failed_title")
                    message = tr("auto_restart_failed", outcome.error) if outcome.failed_stage == "restart" else tr("deps_install_failed", outcome.error)
                    print(f"{title}: {message}")
                return False
            except Exception as e:
                print(tr("deps_install_failed", str(e)))
                return False
        else:
            return False
    else:
        # Use PyQt5 to ask
        from PyQt5.QtWidgets import QApplication, QMessageBox
        app = QApplication(sys.argv)
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText(tr("missing_dependencies_title"))
        msg.setInformativeText(tr("missing_dependencies_informative", ", ".join([m[1] for m in missing])))
        msg.setWindowTitle(tr("missing_dependencies_title"))
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)

        retval = msg.exec_()
        if retval == QMessageBox.Yes:
            try:
                outcome = startup_manager.install_packages_and_restart([pkg_name for _, pkg_name in missing])
                if outcome.error:
                    title = tr("auto_restart_failed_title") if outcome.failed_stage == "restart" else tr("deps_install_failed_title")
                    message = tr("auto_restart_failed", outcome.error) if outcome.failed_stage == "restart" else tr("deps_install_failed", outcome.error)
                    QMessageBox.critical(None, title, message)
                return False
            except Exception as e:
                QMessageBox.critical(None, tr("deps_install_failed_title"), tr("deps_install_failed", str(e)))
                return False
        else:
            return False


def server_precheck() -> bool:
    from core.os_detection import is_os_supported, is_supported_server, get_windows_edition, get_server_family

    if is_os_supported():
        return True

    detected = get_server_family() or get_windows_edition() or tr("unknown")
    warning_msg = tr("server_console_warning", detected)

    if importlib.util.find_spec("PyQt5") is not None:
        try:
            from PyQt5.QtWidgets import QApplication, QMessageBox
            app = QApplication.instance() or QApplication(sys.argv)
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle(tr("server_only_title"))
            msg.setText(tr("server_only_text"))
            msg.setInformativeText(tr("server_only_informative", detected))
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()
        except Exception:
            print(warning_msg)
    else:
        print(warning_msg)

    return False


if __name__ == "__main__":
    if not server_precheck():
        sys.exit(0)

    check_python_version()
    startup_manager = StartupManager()
    first_run_outcome = startup_manager.bootstrap_first_launch()
    if first_run_outcome.error:
        title = tr("auto_restart_failed_title") if first_run_outcome.failed_stage == "restart" else tr("deps_install_failed_title")
        message = tr("auto_restart_failed", first_run_outcome.error) if first_run_outcome.failed_stage == "restart" else tr("deps_install_failed", first_run_outcome.error)
        show_startup_error(title, message)
        sys.exit(1)

    if not first_run_outcome.should_continue:
        sys.exit(0)

    if check_dependencies(startup_manager):
        try:
            from gui.main_window import MainWindow
            from gui.background_manager import background_manager
            from PyQt5.QtWidgets import QApplication
            from core.language_manager import lang_manager
            from core.os_detection import is_legacy, show_legacy_block_and_exit

            app = QApplication(sys.argv)
            lang_manager.initialize_language()
            if is_legacy():
                show_legacy_block_and_exit(app)
            startup_manager.mark_first_launch_completed()
            imgs = background_manager.list_images()
            if imgs:
                background_manager.set_selected_path(random.choice(imgs))
            window = MainWindow()
            window.show()
            sys.exit(app.exec_())
        except ImportError as e:
            print(tr("import_error", str(e)))
            # This might happen if dependencies were just installed but not yet available in the current process
            print(tr("restart_required"))

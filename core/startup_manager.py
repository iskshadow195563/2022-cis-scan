import importlib.util
import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, Optional, Sequence


LOGGER_NAME = "windows_security_auditor.startup"


@dataclass
class StartupOutcome:
    should_continue: bool
    restart_triggered: bool = False
    error: Optional[str] = None
    failed_stage: Optional[str] = None


def configure_startup_logging(log_file_path: Optional[str] = None) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    if log_file_path:
        try:
            os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
            file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as exc:
            logger.warning("Failed to create startup log file '%s': %s", log_file_path, exc)

    return logger


class StartupManager:
    def __init__(
        self,
        config_manager=None,
        find_spec: Optional[Callable[[str], object]] = None,
        process_factory: Optional[Callable[..., subprocess.Popen]] = None,
        exit_fn: Optional[Callable[[int], None]] = None,
        argv: Optional[Sequence[str]] = None,
        executable: Optional[str] = None,
        frozen: Optional[bool] = None,
        logger: Optional[logging.Logger] = None,
    ):
        if config_manager is None:
            from core.config_manager import ConfigManager

            config_manager = ConfigManager()

        self.config_manager = config_manager
        self.find_spec = find_spec or importlib.util.find_spec
        self.process_factory = process_factory or subprocess.Popen
        self.exit_fn = exit_fn or sys.exit
        self.argv = list(argv) if argv is not None else list(sys.argv)
        self.executable = executable or sys.executable
        self.frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
        self.logger = logger or configure_startup_logging(self.get_log_file_path())

    def get_log_file_path(self) -> str:
        config_dir = os.path.dirname(os.path.abspath(self.config_manager.config_path))
        return os.path.join(config_dir, "startup.log")

    def is_first_launch(self) -> bool:
        startup_state = self.config_manager.get().get("startup", {})
        return not bool(startup_state.get("first_launch_completed", False))

    def mark_first_launch_completed(self) -> bool:
        if not self.is_first_launch():
            return True

        ok = self.config_manager.update("startup.first_launch_completed", True)
        if ok:
            self.logger.info("Marked first launch as completed.")
        else:
            self.logger.error("Failed to persist the first-launch completion flag.")
        return ok

    def is_package_available(self, import_name: str) -> bool:
        return self.find_spec(import_name) is not None

    def bootstrap_first_launch(self) -> StartupOutcome:
        first_launch = self.is_first_launch()
        self.logger.info("Startup bootstrap running. first_launch=%s", first_launch)

        if not first_launch:
            return StartupOutcome(should_continue=True)

        if self.is_package_available("requests"):
            self.logger.info("First launch detected and 'requests' is already installed.")
            return StartupOutcome(should_continue=True)

        self.logger.info("First launch detected and 'requests' is missing. Installing now.")
        return self.install_packages_and_restart(["requests"], mark_first_launch=True)

    def start_pip_install(self, packages: Sequence[str]) -> subprocess.Popen:
        command = [self.executable, "-m", "pip", "install", *packages]
        self.logger.info("Starting pip install: %s", command)
        return self.process_factory(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def wait_for_install_completion(self, process: subprocess.Popen, packages: Sequence[str]) -> StartupOutcome:
        self.logger.info("Waiting for pip install to finish for packages: %s", list(packages))
        stdout, stderr = process.communicate()
        return_code = getattr(process, "returncode", 0)

        if stdout:
            self.logger.info("pip stdout:\n%s", stdout.strip())
        if stderr:
            self.logger.info("pip stderr:\n%s", stderr.strip())

        if return_code != 0:
            detail = (stderr or stdout or f"pip exited with code {return_code}").strip()
            self.logger.error("pip install failed for %s: %s", list(packages), detail)
            return StartupOutcome(should_continue=False, error=detail, failed_stage="install")

        self.logger.info("pip install completed successfully for %s", list(packages))
        return StartupOutcome(should_continue=True)

    def install_packages_and_restart(
        self,
        packages: Sequence[str],
        *,
        mark_first_launch: bool = False,
    ) -> StartupOutcome:
        process = self.start_pip_install(packages)
        install_outcome = self.wait_for_install_completion(process, packages)
        if not install_outcome.should_continue:
            return install_outcome

        if mark_first_launch and not self.mark_first_launch_completed():
            self.logger.warning("Continuing restart even though the first-launch flag was not saved.")

        try:
            self.relaunch_application()
        except Exception as exc:
            self.logger.exception("Failed to restart the application after installing %s", list(packages))
            return StartupOutcome(should_continue=False, error=str(exc), failed_stage="restart")

        self.logger.info("New application instance launched successfully. Exiting the current process.")
        self.exit_fn(0)
        return StartupOutcome(should_continue=False, restart_triggered=True)

    def build_restart_command(self) -> Sequence[str]:
        if self.frozen:
            return [self.executable, *self.argv[1:]]

        if self.argv:
            return [self.executable, *self.argv]

        return [self.executable]

    def relaunch_application(self) -> None:
        command = list(self.build_restart_command())
        self.logger.info("Relaunching application with command: %s", command)

        kwargs = {}
        if os.name == "nt":
            kwargs["creationflags"] = (
                getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                | getattr(subprocess, "DETACHED_PROCESS", 0)
                | getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
        else:
            kwargs["start_new_session"] = True

        self.process_factory(command, **kwargs)

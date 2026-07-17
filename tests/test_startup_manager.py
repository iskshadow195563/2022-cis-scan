import logging
import os
import tempfile
import unittest

from core.config_manager import ConfigManager
from core.startup_manager import StartupManager


class FakeProcess:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr
        self.communicate_called = False

    def communicate(self):
        self.communicate_called = True
        return self._stdout, self._stderr


class TestStartupManager(unittest.TestCase):
    def build_logger(self, name):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = False
        logger.addHandler(logging.NullHandler())
        return logger

    def test_first_launch_installs_requests_and_restarts(self):
        with tempfile.TemporaryDirectory() as td:
            cfg_path = os.path.join(td, "config.json")
            config_manager = ConfigManager(cfg_path)
            install_process = FakeProcess(stdout="installed requests")
            calls = []
            exit_codes = []

            def process_factory(command, **kwargs):
                calls.append((command, kwargs))
                if len(calls) == 1:
                    return install_process
                return object()

            manager = StartupManager(
                config_manager=config_manager,
                find_spec=lambda name: None if name == "requests" else object(),
                process_factory=process_factory,
                exit_fn=lambda code: exit_codes.append(code),
                argv=["main.py", "--demo"],
                executable="python",
                frozen=False,
                logger=self.build_logger("tests.startup.success"),
            )

            outcome = manager.bootstrap_first_launch()

            self.assertTrue(install_process.communicate_called)
            self.assertTrue(outcome.restart_triggered)
            self.assertFalse(outcome.should_continue)
            self.assertIsNone(outcome.error)
            self.assertEqual(exit_codes, [0])
            self.assertTrue(config_manager.get()["startup"]["first_launch_completed"])
            self.assertEqual(calls[0][0], ["python", "-m", "pip", "install", "requests"])
            self.assertEqual(calls[1][0], ["python", "main.py", "--demo"])

    def test_first_launch_flag_can_be_marked_after_normal_start(self):
        with tempfile.TemporaryDirectory() as td:
            cfg_path = os.path.join(td, "config.json")
            config_manager = ConfigManager(cfg_path)
            process_calls = []

            manager = StartupManager(
                config_manager=config_manager,
                find_spec=lambda name: object(),
                process_factory=lambda *args, **kwargs: process_calls.append((args, kwargs)),
                exit_fn=lambda code: None,
                argv=["main.py"],
                executable="python",
                frozen=False,
                logger=self.build_logger("tests.startup.mark"),
            )

            outcome = manager.bootstrap_first_launch()

            self.assertTrue(outcome.should_continue)
            self.assertFalse(outcome.restart_triggered)
            self.assertFalse(config_manager.get()["startup"]["first_launch_completed"])
            self.assertTrue(manager.mark_first_launch_completed())
            self.assertTrue(config_manager.get()["startup"]["first_launch_completed"])
            self.assertEqual(process_calls, [])

    def test_restart_failure_returns_error_without_exiting(self):
        with tempfile.TemporaryDirectory() as td:
            cfg_path = os.path.join(td, "config.json")
            config_manager = ConfigManager(cfg_path)
            install_process = FakeProcess(stdout="installed requests")
            exit_codes = []
            call_count = {"value": 0}

            def process_factory(command, **kwargs):
                call_count["value"] += 1
                if call_count["value"] == 1:
                    return install_process
                raise OSError("spawn failed")

            manager = StartupManager(
                config_manager=config_manager,
                find_spec=lambda name: None if name == "requests" else object(),
                process_factory=process_factory,
                exit_fn=lambda code: exit_codes.append(code),
                argv=["main.py"],
                executable="python",
                frozen=False,
                logger=self.build_logger("tests.startup.failure"),
            )

            outcome = manager.bootstrap_first_launch()

            self.assertTrue(install_process.communicate_called)
            self.assertFalse(outcome.should_continue)
            self.assertFalse(outcome.restart_triggered)
            self.assertEqual(outcome.failed_stage, "restart")
            self.assertIn("spawn failed", outcome.error)
            self.assertEqual(exit_codes, [])
            self.assertTrue(config_manager.get()["startup"]["first_launch_completed"])


if __name__ == "__main__":
    unittest.main()

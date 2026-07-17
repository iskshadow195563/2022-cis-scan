import glob
import os
import sys

from PyQt5.QtWidgets import QApplication

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from gui.main_window import MainWindow
from gui.report_window import ReportWindow
from gui.theme_tokens import build_theme_stylesheet


def latest_report_path(base_dir):
    report_files = sorted(glob.glob(os.path.join(base_dir, "results", "report_*.json")))
    return report_files[-1] if report_files else None


def capture_window(window, out_path):
    window.show()
    app = QApplication.instance()
    app.processEvents()
    pix = window.grab()
    pix.save(out_path)
    window.close()


def main():
    base_dir = BASE_DIR
    out_dir = os.path.join(base_dir, "artifacts", "visual-regression")
    os.makedirs(out_dir, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv)
    sizes = [(1366, 768), (1024, 768), (768, 1024)]
    themes = ["light", "dark"]
    report_path = latest_report_path(base_dir)

    for theme in themes:
        style = build_theme_stylesheet(theme)
        for width, height in sizes:
            main_win = MainWindow()
            main_win.setStyleSheet(style)
            main_win.resize(width, height)
            capture_window(main_win, os.path.join(out_dir, f"main_{theme}_{width}x{height}.png"))

            if report_path:
                report_win = ReportWindow(report_path)
                report_win.setStyleSheet(style)
                report_win.resize(width, height)
                capture_window(report_win, os.path.join(out_dir, f"report_{theme}_{width}x{height}.png"))


if __name__ == "__main__":
    main()

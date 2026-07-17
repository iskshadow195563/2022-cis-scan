import glob
import json
import os
import tempfile
import unittest

from core.hallucination_detector import HallucinationDetector
from core.hallucination_types import HallucinationReport, HallucinationIssue, HallucinationSeverity
from core.hallucination_monitor import HallucinationMonitor


class TestHallucinationMonitor(unittest.TestCase):
    def test_monitor_tracks_scans(self):
        with tempfile.TemporaryDirectory() as td:
            monitor = HallucinationMonitor(output_dir=td)
            report = HallucinationReport(
                scan_timestamp="2026-01-01T00:00:00",
                total_items=10,
                total_issues=2,
                issues=[],
                severity_counts={"medium": 2},
                category_counts={"fact_check": 2},
                confidence_score=0.95,
            )
            monitor.record_scan(report)
            summary = monitor.get_summary()
            self.assertEqual(summary["total_scans"], 1)

    def test_monitor_trend_is_stable_with_two_scans(self):
        with tempfile.TemporaryDirectory() as td:
            monitor = HallucinationMonitor(output_dir=td)
            for _ in range(5):
                report = HallucinationReport(
                    scan_timestamp="2026-01-01T00:00:00",
                    total_items=10,
                    total_issues=1,
                    issues=[],
                    severity_counts={"low": 1},
                    category_counts={"fact_check": 1},
                    confidence_score=0.96,
                )
                monitor.record_scan(report)
            summary = monitor.get_summary()
            self.assertIn(summary["trend"], ("stable", "improving", "degrading"))

    def test_monitor_no_data(self):
        with tempfile.TemporaryDirectory() as td:
            monitor = HallucinationMonitor(output_dir=td)
            summary = monitor.get_summary()
            self.assertEqual(summary["status"], "no_data")

    def test_monitor_persists_history(self):
        with tempfile.TemporaryDirectory() as td:
            monitor1 = HallucinationMonitor(output_dir=td)
            report = HallucinationReport(
                scan_timestamp="2026-01-01T00:00:00",
                total_items=5,
                total_issues=0,
                issues=[],
                severity_counts={},
                category_counts={},
                confidence_score=1.0,
            )
            monitor1.record_scan(report)

            monitor2 = HallucinationMonitor(output_dir=td)
            summary = monitor2.get_summary()
            self.assertEqual(summary["total_scans"], 1)

    def test_monitor_degrading_trend(self):
        with tempfile.TemporaryDirectory() as td:
            monitor = HallucinationMonitor(output_dir=td)
            for i in range(5):
                conf = 1.0 - (i * 0.05)
                report = HallucinationReport(
                    scan_timestamp=f"2026-01-01T00:00:0{i}",
                    total_items=10,
                    total_issues=i * 2,
                    issues=[],
                    severity_counts={"high": i},
                    category_counts={"fact_check": i * 2},
                    confidence_score=conf,
                )
                monitor.record_scan(report)
            summary = monitor.get_summary()
            self.assertEqual(summary["trend"], "degrading")


if __name__ == "__main__":
    unittest.main()

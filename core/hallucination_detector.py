import json
import logging
import os
import datetime
from typing import List, Dict, Any, Optional

from core.hallucination_types import (
    HallucinationIssue,
    HallucinationReport,
    HallucinationSeverity,
)
from core.fact_checker import FactChecker
from core.consistency_validator import ConsistencyValidator
from core.traceability import TraceabilityTracker
from core.hallucination_monitor import HallucinationMonitor

HALLUCINATION_LOG_NAME = "hallucination_report"


class HallucinationDetector:
    def __init__(
        self,
        output_dir: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
        enable_monitor: bool = False,
    ):
        self.output_dir = output_dir
        self._logger = logger or self._build_logger()
        self._fact_checker = FactChecker()
        self._consistency_validator = ConsistencyValidator()
        self._traceability_tracker = TraceabilityTracker()
        self._monitor = HallucinationMonitor(output_dir) if enable_monitor else None

    def _build_logger(self) -> logging.Logger:
        logger = logging.getLogger(f"project001.{HALLUCINATION_LOG_NAME}")
        if logger.handlers:
            return logger
        logger.setLevel(logging.INFO)
        logger.propagate = False
        if self.output_dir:
            try:
                os.makedirs(self.output_dir, exist_ok=True)
                handler = logging.FileHandler(
                    os.path.join(self.output_dir, f"{HALLUCINATION_LOG_NAME}.log"),
                    encoding="utf-8",
                )
                handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
                logger.addHandler(handler)
            except Exception:
                logger.addHandler(logging.NullHandler())
        else:
            logger.addHandler(logging.NullHandler())
        return logger

    def detect(self, report_data: Dict[str, Any], items: Optional[List[Dict[str, Any]]] = None) -> HallucinationReport:
        issues: List[HallucinationIssue] = []
        results = report_data.get("results") if isinstance(report_data, dict) else []

        if not isinstance(results, list):
            issues.append(HallucinationIssue(
                severity=HallucinationSeverity.CRITICAL,
                category="structure",
                code="GLOBAL",
                field="results",
                message="Report results is missing or not a list",
                recommendation="Ensure scan completes before generating report",
            ))
            return self._build_report(report_data, issues)

        total_items = len(results)

        issues.extend(self._fact_checker.check_all(results, items))

        issues.extend(self._consistency_validator.validate_all(results, report_data))

        items_for_trace = items if items else [
            {"code": r.get("code", ""), "description": r.get("description", ""),
             "level": r.get("level", ""), "name": r.get("name", ""),
             "recommended": r.get("recommended", "")}
            for r in results
        ]
        issues.extend(self._traceability_tracker.trace_all(results, items_for_trace))

        report = self._build_report(report_data, issues)
        self._log_report(report)

        if self._monitor:
            self._monitor.record_scan(report)

        return report

    def _build_report(self, report_data: Dict[str, Any], issues: List[HallucinationIssue]) -> HallucinationReport:
        scan_info = report_data.get("scan_info", {}) if isinstance(report_data, dict) else {}
        scan_timestamp = scan_info.get("nowtime") or scan_info.get("date", "")
        total_items = len(report_data.get("results", [])) if isinstance(report_data, dict) else 0

        severity_counts: Dict[str, int] = {}
        category_counts: Dict[str, int] = {}
        for issue in issues:
            severity_counts[issue.severity.value] = severity_counts.get(issue.severity.value, 0) + 1
            category_counts[issue.category] = category_counts.get(issue.category, 0) + 1

        critical_count = severity_counts.get(HallucinationSeverity.CRITICAL.value, 0)
        high_count = severity_counts.get(HallucinationSeverity.HIGH.value, 0)
        medium_count = severity_counts.get(HallucinationSeverity.MEDIUM.value, 0)
        low_count = severity_counts.get(HallucinationSeverity.LOW.value, 0)

        total_penalty = critical_count * 10 + high_count * 5 + medium_count * 2 + low_count * 1
        confidence_score = max(0.0, 1.0 - total_penalty / max(total_items * 10, 1))

        return HallucinationReport(
            scan_timestamp=str(scan_timestamp),
            total_items=total_items,
            total_issues=len(issues),
            issues=issues,
            severity_counts=severity_counts,
            category_counts=category_counts,
            integrity_hash=scan_info.get("integrity_hash"),
            confidence_score=round(confidence_score, 4),
        )

    def _log_report(self, report: HallucinationReport):
        self._logger.info(
            "hallucination_report timestamp=%s items=%d issues=%d critical=%d high=%d medium=%d low=%d confidence=%.4f",
            report.scan_timestamp,
            report.total_items,
            report.total_issues,
            report.severity_counts.get("critical", 0),
            report.severity_counts.get("high", 0),
            report.severity_counts.get("medium", 0),
            report.severity_counts.get("low", 0),
            report.confidence_score,
        )
        for issue in report.issues:
            self._logger.warning(
                "hallucination severity=%s category=%s code=%s field=%s message=%s",
                issue.severity.value,
                issue.category,
                issue.code,
                issue.field,
                issue.message,
            )

    def save_report(self, report: HallucinationReport) -> Optional[str]:
        if not self.output_dir:
            return None
        try:
            os.makedirs(self.output_dir, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"hallucination_{timestamp}.json"
            filepath = os.path.join(self.output_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
            self._logger.info("hallucination_report_saved path=%r", filepath)
            return filepath
        except Exception as exc:
            self._logger.error("hallucination_report_save_failed error=%s", exc)
            return None

    def get_monitor_summary(self) -> Optional[Dict[str, Any]]:
        if self._monitor:
            return self._monitor.get_summary()
        return None

    def close(self):
        handlers = list(self._logger.handlers)
        for handler in handlers:
            try:
                handler.flush()
            except Exception:
                pass
            try:
                handler.close()
            except Exception:
                pass
            try:
                self._logger.removeHandler(handler)
            except Exception:
                pass

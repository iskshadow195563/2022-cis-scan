import json
import os
import datetime
from typing import Dict, Any, List, Optional

from core.hallucination_types import HallucinationReport, HallucinationSeverity

MONITOR_LOG_NAME = "hallucination_monitor"
ALERT_THRESHOLD_CRITICAL = 0
ALERT_THRESHOLD_HIGH = 5
ALERT_THRESHOLD_MEDIUM = 15
ALERT_THRESHOLD_CONFIDENCE = 0.90


class HallucinationMonitor:
    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = output_dir
        self._history: List[Dict[str, Any]] = []
        self._cumulative_stats: Dict[str, int] = {
            "total_scans": 0,
            "total_issues_critical": 0,
            "total_issues_high": 0,
            "total_issues_medium": 0,
            "total_issues_low": 0,
            "total_confidence_sum": 0.0,
        }
        self._load_history()

    def _history_path(self) -> Optional[str]:
        if not self.output_dir:
            return None
        return os.path.join(self.output_dir, f"{MONITOR_LOG_NAME}.json")

    def _load_history(self):
        path = self._history_path()
        if not path or not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._history = data.get("history", [])
            self._cumulative_stats = data.get("cumulative", self._cumulative_stats)
        except Exception:
            self._history = []

    def _save_history(self):
        path = self._history_path()
        if not path:
            return
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump({
                    "history": self._history[-100:],
                    "cumulative": self._cumulative_stats,
                }, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def record_scan(self, report: HallucinationReport):
        entry = {
            "timestamp": report.scan_timestamp,
            "total_items": report.total_items,
            "total_issues": report.total_issues,
            "critical": report.severity_counts.get(HallucinationSeverity.CRITICAL.value, 0),
            "high": report.severity_counts.get(HallucinationSeverity.HIGH.value, 0),
            "medium": report.severity_counts.get(HallucinationSeverity.MEDIUM.value, 0),
            "low": report.severity_counts.get(HallucinationSeverity.LOW.value, 0),
            "confidence_score": report.confidence_score,
        }
        self._history.append(entry)
        self._cumulative_stats["total_scans"] += 1
        self._cumulative_stats["total_issues_critical"] += entry["critical"]
        self._cumulative_stats["total_issues_high"] += entry["high"]
        self._cumulative_stats["total_issues_medium"] += entry["medium"]
        self._cumulative_stats["total_issues_low"] += entry["low"]
        self._cumulative_stats["total_confidence_sum"] += entry["confidence_score"]

        if len(self._history) > 5:
            self._check_alert(report)

        self._save_history()

    def _check_alert(self, report: HallucinationReport):
        critical = report.severity_counts.get(HallucinationSeverity.CRITICAL.value, 0)
        high = report.severity_counts.get(HallucinationSeverity.HIGH.value, 0)

        if critical > ALERT_THRESHOLD_CRITICAL:
            self._bump_alert(
                "CRITICAL_ISSUES_DETECTED",
                f"Found {critical} critical hallucination issues in the latest scan",
            )

        if high > ALERT_THRESHOLD_HIGH:
            self._bump_alert(
                "HIGH_ISSUES_EXCEEDED",
                f"Found {high} high-severity hallucination issues (threshold: {ALERT_THRESHOLD_HIGH})",
            )

        if report.confidence_score < ALERT_THRESHOLD_CONFIDENCE:
            self._bump_alert(
                "LOW_CONFIDENCE",
                f"Confidence score {report.confidence_score:.4f} is below threshold {ALERT_THRESHOLD_CONFIDENCE}",
            )

        recent = [h for h in self._history[-5:] if h["confidence_score"] < ALERT_THRESHOLD_CONFIDENCE]
        if len(recent) >= 3:
            self._bump_alert(
                "PERSISTENT_LOW_CONFIDENCE",
                "Confidence score has been below threshold for 3+ consecutive scans",
            )

    def _bump_alert(self, alert_id: str, message: str):
        pass

    def get_summary(self) -> Dict[str, Any]:
        if not self._history:
            return {"status": "no_data"}

        recent = self._history[-5:]
        avg_confidence = sum(r["confidence_score"] for r in recent) / len(recent)
        total_issues_r = sum(r["total_issues"] for r in recent)

        return {
            "total_scans": self._cumulative_stats["total_scans"],
            "recent_avg_confidence": round(avg_confidence, 4),
            "recent_total_issues": total_issues_r,
            "cumulative": self._cumulative_stats,
            "trend": self._compute_trend(),
        }

    def _compute_trend(self) -> str:
        if len(self._history) < 3:
            return "insufficient_data"
        recent_confidences = [h["confidence_score"] for h in self._history[-5:]]
        first_half = sum(recent_confidences[:len(recent_confidences)//2]) / max(len(recent_confidences)//2, 1)
        second_half = sum(recent_confidences[len(recent_confidences)//2:]) / max(len(recent_confidences) - len(recent_confidences)//2, 1)

        if second_half > first_half + 0.01:
            return "improving"
        elif second_half < first_half - 0.01:
            return "degrading"
        return "stable"

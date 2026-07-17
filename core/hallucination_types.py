from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from enum import Enum


class HallucinationSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class HallucinationIssue:
    severity: HallucinationSeverity
    category: str
    code: str
    field: str
    message: str
    actual_value: Optional[str] = None
    expected_value: Optional[str] = None
    source: Optional[str] = None
    recommendation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "severity": self.severity.value,
            "category": self.category,
            "code": self.code,
            "field": self.field,
            "message": self.message,
        }
        if self.actual_value is not None:
            d["actual_value"] = self.actual_value
        if self.expected_value is not None:
            d["expected_value"] = self.expected_value
        if self.source is not None:
            d["source"] = self.source
        if self.recommendation is not None:
            d["recommendation"] = self.recommendation
        return d


@dataclass
class HallucinationReport:
    scan_timestamp: str
    total_items: int
    total_issues: int
    issues: List[HallucinationIssue]
    severity_counts: Dict[str, int] = field(default_factory=dict)
    category_counts: Dict[str, int] = field(default_factory=dict)
    integrity_hash: Optional[str] = None
    confidence_score: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scan_timestamp": self.scan_timestamp,
            "total_items": self.total_items,
            "total_issues": self.total_issues,
            "severity_counts": self.severity_counts,
            "category_counts": self.category_counts,
            "integrity_hash": self.integrity_hash,
            "confidence_score": self.confidence_score,
            "issues": [i.to_dict() for i in self.issues],
        }

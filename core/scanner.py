import logging
import json
import os
import datetime
import subprocess
import re
import hashlib
import tempfile
from typing import Any, Dict, Optional
from PyQt5.QtCore import QThread, pyqtSignal
from core.language_manager import lang_manager
from core.report_status import (
    FAIL_STATUS,
    PASS_STATUS,
    ERROR_STATUS,
    UNSUPPORTED_STATUS,
    MISSING_SCRIPT_STATUS,
    SCRIPT_ERROR_STATUS,
    normalize_report_status,
    is_meaningful_result,
    is_infrastructure_error,
)


def _is_zh_language():
    return (lang_manager.current_language or "").lower().startswith("zh")


def _policy_path_for_code(code):
    prefix = (code or "").strip()
    lang_zh = _is_zh_language()
    if prefix.startswith("1.1"):
        return "本地安全性原則 → 帳戶原則 → 密碼原則" if lang_zh else "Local Security Policy → Account Policies → Password Policy"
    if prefix.startswith("1.2"):
        return "本地安全性原則 → 帳戶原則 → 帳戶鎖定原則" if lang_zh else "Local Security Policy → Account Policies → Account Lockout Policy"
    if prefix.startswith("2.2"):
        return "本地安全性原則 → 本機原則 → 使用者權限指派" if lang_zh else "Local Security Policy → Local Policies → User Rights Assignment"
    if prefix.startswith("2.3"):
        return "本地安全性原則 → 本機原則 → 安全性選項" if lang_zh else "Local Security Policy → Local Policies → Security Options"
    if prefix.startswith("5"):
        return "系統服務" if lang_zh else "System Services"
    if prefix.startswith("9"):
        return "Windows Defender 防火牆（進階安全性）" if lang_zh else "Windows Defender Firewall with Advanced Security"
    if prefix.startswith("17"):
        return "進階稽核原則設定" if lang_zh else "Advanced Audit Policy Configuration"
    if prefix.startswith("18"):
        return "系統管理範本（電腦組態）" if lang_zh else "Administrative Templates (Computer Configuration)"
    if prefix.startswith("19"):
        return "系統管理範本（使用者組態）" if lang_zh else "Administrative Templates (User Configuration)"
    return "群組原則 / 本地安全性原則" if lang_zh else "Group Policy / Local Security Policy"


def _normalize_description(description):
    text = (description or "").strip()
    if not text:
        return ""
    if re.match(r"^ensure\s+", text, flags=re.IGNORECASE):
        text = re.sub(r"^ensure\s+", "", text, flags=re.IGNORECASE)
    if text.startswith("確保 "):
        text = text[3:]
    text = re.sub(r"\s*\([^()]*\)\s*$", "", text).strip()
    return text


def _extract_setting_value(text):
    if not text:
        return "", ""
    if "->" in text:
        left, right = text.split("->", 1)
        return left.strip().strip("'\""), right.strip().strip("'\"")
    if " = " in text:
        left, right = text.split(" = ", 1)
        return left.strip(), right.strip()
    match = re.search(r"(.+?)\s*(>=|<=|≥|≤|>|<)\s*(.+)", text)
    if match:
        return match.group(1).strip(), f"{match.group(2)} {match.group(3).strip()}"
    return text.strip(), ""


def build_suggestion(code, description, setting_name=None, recommended_value=None):
    if setting_name:
        setting = (setting_name or "").strip().strip("'\"")
        value = (recommended_value or "").strip().strip("'\"")
    else:
        norm = _normalize_description(description)
        setting, value = _extract_setting_value(norm)
    path = _policy_path_for_code(code)
    if _is_zh_language():
        if setting and value:
            return f"在 {path} 將「{setting}」設為「{value}」。"
        if setting:
            return f"在 {path} 依 CIS 建議設定「{setting}」。"
        return f"在 {path} 依 CIS 建議配置。"
    if setting and value:
        return f"Set '{setting}' to '{value}' in {path}."
    if setting:
        return f"Configure '{setting}' per CIS recommendation in {path}."
    return f"Configure this item per CIS recommendation in {path}."


def _build_scan_logger(output_dir):
    logger_name = f"project001.scan.{os.path.abspath(output_dir)}"
    logger = logging.getLogger(logger_name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    try:
        os.makedirs(output_dir, exist_ok=True)
        handler = logging.FileHandler(os.path.join(output_dir, "scan_debug.log"), encoding="utf-8")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    except Exception:
        logger.addHandler(logging.NullHandler())

    return logger

class Scanner(QThread):
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(str)
    hallucination_signal = pyqtSignal(str)

    def __init__(self, items, output_dir, subprocess_run=None, now_provider=None, logger=None, base_dir=None, enable_hallucination_detection=True, scan_mode="local", remote_target=None):
        super().__init__()
        self.items = items
        self.output_dir = output_dir
        self._is_running = True
        self._subprocess_run = subprocess_run
        self._now_provider = now_provider or datetime.datetime.now
        self._logger = logger or _build_scan_logger(output_dir)
        self._base_dir = base_dir or os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self._enable_hallucination_detection = enable_hallucination_detection
        self.scan_mode = scan_mode
        self.remote_target = remote_target
        self._temp_files = []

    def _resolve_script_path(self, script_path):
        if not script_path:
            return ""
        if os.path.isabs(script_path):
            return script_path
        return os.path.normpath(os.path.join(self._base_dir, script_path))

    def _mapping_path(self):
        custom_mapping = os.path.join(self._base_dir, "data", "cis_mapping.custom.json")
        if os.path.exists(custom_mapping):
            return custom_mapping
        return os.path.join(self._base_dir, "data", "cis_mapping.json")

    def _framework_path(self):
        return os.path.join(self._base_dir, "scripts", "cis_check_framework.ps1")

    def _is_builtin_cis_script(self, script_path):
        if not script_path:
            return False
        try:
            checks_dir = os.path.abspath(os.path.join(self._base_dir, "scripts", "checks"))
            abs_script = os.path.abspath(script_path)
            return os.path.commonpath([checks_dir, abs_script]) == checks_dir
        except Exception:
            return False

    def _ps_single_quoted(self, value):
        return "'" + str(value).replace("'", "''") + "'"

    def _ps_here_string(self, value):
        text = str(value).replace("\r\n", "\n").replace("\r", "\n")
        return "@'\n" + text + "\n'@"

    def _write_temp_powershell(self, content):
        temp_dir = self.output_dir if os.path.isdir(self.output_dir) else None
        fd, path = tempfile.mkstemp(suffix=".ps1", prefix="scan_bootstrap_", dir=temp_dir)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        self._temp_files.append(path)
        return path

    def _log_item_event(self, code, event, **details):
        payload = ", ".join(f"{key}={details[key]!r}" for key in sorted(details))
        if payload:
            self._logger.info("code=%s event=%s %s", code, event, payload)
        else:
            self._logger.info("code=%s event=%s", code, event)

    def _extract_json_payload(self, stdout) -> Optional[Dict[str, Any]]:
        if not stdout:
            return None
        text = stdout.strip()
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, ValueError):
            pass

        for line in reversed(text.splitlines()):
            line = line.strip()
            if not line or not (line.startswith("{") and line.endswith("}")):
                continue
            try:
                data = json.loads(line)
                if isinstance(data, dict):
                    return data
            except (json.JSONDecodeError, ValueError):
                continue
        return None

    def _parse_script_result(self, stdout):
        payload = self._extract_json_payload(stdout)
        if payload:
            status = payload.get("Status") or payload.get("status")
            detail = payload.get("Detail") or payload.get("detail")
            actual = payload.get("Actual")
            if actual is None:
                actual = payload.get("actual") or payload.get("Value") or payload.get("value")
            return {
                "status": normalize_report_status(status) if status is not None else None,
                "detail": str(detail) if detail is not None else "",
                "actual": str(actual) if actual is not None else None,
            }

        actual_value = (stdout or "").strip()
        match = re.search(r'(?:actual|current|value)[:\s=]+(.+)', stdout, re.IGNORECASE)
        if match:
            actual_value = match.group(1).strip()
        return {"status": None, "detail": "", "actual": actual_value or None}

    def _parse_script_output(self, stdout, item):
        return self._parse_script_result(stdout).get("actual")

    def _build_builtin_framework_command(self, code, remote=False):
        framework_path = self._framework_path()
        mapping_path = self._mapping_path()
        if not remote:
            return [
                "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", framework_path,
                "-Code", code,
                "-MappingPath", mapping_path,
            ]

        with open(framework_path, "r", encoding="utf-8") as f:
            framework_content = f.read()
        with open(mapping_path, "r", encoding="utf-8") as f:
            mapping_json = f.read()
        bootstrap = (
            "$ErrorActionPreference = 'Stop'\n"
            "$framework = " + self._ps_here_string(framework_content) + "\n"
            "$mappingJson = " + self._ps_here_string(mapping_json) + "\n"
            "$code = " + self._ps_single_quoted(code) + "\n"
            "$target = " + self._ps_single_quoted(self.remote_target) + "\n"
            "Invoke-Command -ComputerName $target -ScriptBlock {\n"
            "    param($FrameworkText, $MappingJsonText, $Code)\n"
            "    $sb = [scriptblock]::Create($FrameworkText)\n"
            "    & $sb -Code $Code -MappingJson $MappingJsonText\n"
            "} -ArgumentList $framework, $mappingJson, $code\n"
            "exit $LASTEXITCODE\n"
        )
        bootstrap_path = self._write_temp_powershell(bootstrap)
        return ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", bootstrap_path]

    def _build_remote_custom_script_command(self, script_path):
        with open(script_path, "r", encoding="utf-8") as f:
            script_content = f.read()
        bootstrap = (
            "$ErrorActionPreference = 'Stop'\n"
            "$scriptText = " + self._ps_here_string(script_content) + "\n"
            "$target = " + self._ps_single_quoted(self.remote_target) + "\n"
            "Invoke-Command -ComputerName $target -ScriptBlock {\n"
            "    param($ScriptText)\n"
            "    $sb = [scriptblock]::Create($ScriptText)\n"
            "    & $sb\n"
            "} -ArgumentList $scriptText\n"
            "exit $LASTEXITCODE\n"
        )
        bootstrap_path = self._write_temp_powershell(bootstrap)
        return ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", bootstrap_path]

    def _evaluate_item(self, item):
        code = item.get("code", "")
        script_path = self._resolve_script_path((item.get("script_path") or "").strip())

        if not script_path:
            self._log_item_event(code, "missing_script_path", assessment=item.get("assessment", ""))
            return MISSING_SCRIPT_STATUS, "missing_script_path", None

        if not os.path.isfile(script_path):
            self._log_item_event(code, "script_not_found", script_path=script_path)
            return MISSING_SCRIPT_STATUS, "script_not_found", None

        use_framework = self._is_builtin_cis_script(script_path) and os.path.isfile(self._framework_path())

        if self.scan_mode == "remote" and self.remote_target:
            if use_framework:
                cmd = self._build_builtin_framework_command(code, remote=True)
            else:
                cmd = self._build_remote_custom_script_command(script_path)
            self._log_item_event(code, "run_script_remote_start", script_path=script_path, remote_target=self.remote_target, framework=use_framework)
        elif self.scan_mode == "domain" and use_framework:
            cmd = self._build_builtin_framework_command(code, remote=False)
            self._log_item_event(code, "run_script_domain_start", script_path=script_path, framework=True)
        else:
            if use_framework:
                cmd = self._build_builtin_framework_command(code, remote=False)
            else:
                cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path]
            self._log_item_event(code, "run_script_start", script_path=script_path, command=cmd)

        runner = self._subprocess_run or subprocess.run
        try:
            proc = runner(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
            stdout = (proc.stdout or "").strip()
            stderr = (proc.stderr or "").strip()
            parsed = self._parse_script_result(stdout)
            actual_value = parsed.get("actual")
            if parsed.get("status"):
                status = parsed["status"]
                detail = parsed.get("detail") or ("compliant" if status == PASS_STATUS else "noncompliant")
            elif proc.returncode == 0:
                status = PASS_STATUS
                detail = "compliant"
            else:
                status = FAIL_STATUS
                detail = "noncompliant"
            self._log_item_event(
                code,
                "run_script_done",
                returncode=proc.returncode,
                status=status,
                stdout=stdout[:500],
                stderr=stderr[:500],
                actual_value=actual_value or "",
            )
            return status, detail, actual_value
        except subprocess.TimeoutExpired:
            self._log_item_event(code, "run_script_timeout", script_path=script_path, timeout=120)
            return ERROR_STATUS, "script_timeout", None
        except Exception as exc:
            self._log_item_event(code, "run_script_exception", script_path=script_path, error=str(exc))
            return ERROR_STATUS, "script_exception", None

    def _validate_scan_items(self):
        script_issues = []
        for item in self.items:
            code = item.get("code", "")
            script_path = self._resolve_script_path((item.get("script_path") or "").strip())
            if not script_path:
                script_issues.append((code, "missing_script_path"))
            elif not os.path.isfile(script_path):
                script_issues.append((code, f"script_not_found: {script_path}"))
        return script_issues

    def _compute_scan_hash(self, results):
        h = hashlib.sha256()
        for r in sorted(results, key=lambda x: x.get("code", "")):
            h.update(r.get("code", "").encode())
            h.update(r.get("status", "").encode())
            h.update(r.get("detail", "").encode())
        return h.hexdigest()

    def _close_logger(self):
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

    def _cleanup_temp_files(self):
        for path in list(self._temp_files):
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass
        self._temp_files = []

    def stop(self):
        self._is_running = False

    def run(self):
        results = []
        try:
            self._logger.info("scan_start item_count=%d output_dir=%r", len(self.items), self.output_dir)

            issues = self._validate_scan_items()
            if issues:
                issue_codes = [c for c, _ in issues[:10]]
                self._logger.warning(
                    "scan_items_without_scripts count=%d codes=%s",
                    len(issues),
                    ", ".join(issue_codes),
                )
                self._logger.info("scan_script_issues_detail %s", json.dumps(issues[:50]))

            for i, item in enumerate(self.items):
                if not self._is_running:
                    self._logger.info("scan_cancelled completed_items=%d", len(results))
                    break

                code = item.get("code", "")
                status, detail, actual_value = self._evaluate_item(item)
                now = self._now_provider()

                result_entry = {
                    "code": code,
                    "level": item["level"],
                    "description": item["description"],
                    "suggestion": build_suggestion(
                        item.get("code"),
                        item.get("description"),
                        setting_name=item.get("name"),
                        recommended_value=item.get("recommended"),
                    ),
                    "status": normalize_report_status(status),
                    "timestamp": now.isoformat(),
                    "detail": detail,
                }

                if actual_value is not None:
                    result_entry["actual_value"] = actual_value

                if is_meaningful_result(result_entry["status"]):
                    expected = item.get("recommended") or item.get("name")
                    if expected:
                        result_entry["expected_value"] = str(expected)

                results.append(result_entry)
                self._log_item_event(
                    code,
                    "result_recorded",
                    status=status,
                    detail=detail,
                    actual_value=actual_value or "",
                    index=i,
                )

                self.progress_signal.emit(i + 1)

            if self._is_running:
                now = self._now_provider()
                timestamp = now.strftime("%Y%m%d_%H%M%S")
                filename = f"report_{timestamp}.json"
                filepath = os.path.join(self.output_dir, filename)

                scan_hash = self._compute_scan_hash(results)
                total = len(results)
                passed = sum(1 for r in results if r["status"] == PASS_STATUS)
                failed = sum(1 for r in results if r["status"] == FAIL_STATUS)
                missing = sum(1 for r in results if r["status"] == MISSING_SCRIPT_STATUS)
                errors = sum(1 for r in results if r["status"] in (ERROR_STATUS, SCRIPT_ERROR_STATUS))

                local_ip = ""
                try:
                    import socket
                    local_ip = socket.gethostbyname(socket.gethostname())
                except Exception:
                    local_ip = "127.0.0.1"

                report_data = {
                    "scan_info": {
                        "date": now.strftime("%Y-%m-%d"),
                        "time": now.strftime("%H:%M:%S"),
                        "nowtime": now.isoformat(),
                        "total_items": len(self.items),
                        "completed_items": len(results),
                        "integrity_hash": scan_hash,
                        "scan_mode": self.scan_mode,
                        "remote_target": self.remote_target or "",
                        "local_ip": local_ip,
                    },
                    "scan_summary": {
                        "total": total,
                        "pass": passed,
                        "fail": failed,
                        "script_missing": missing,
                        "error": errors,
                    },
                    "results": results
                }

                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(report_data, f, indent=2, ensure_ascii=False)
                self._logger.info("scan_complete report_path=%r result_count=%d hash=%s", filepath, len(results), scan_hash[:16])

                self.finished_signal.emit(filepath)

                if self._enable_hallucination_detection:
                    self._run_hallucination_detection(report_data)

            else:
                self.finished_signal.emit("")
        finally:
            self._cleanup_temp_files()
            self._close_logger()

    def _run_hallucination_detection(self, report_data):
        try:
            from core.hallucination_detector import HallucinationDetector

            detector = HallucinationDetector(output_dir=self.output_dir, enable_monitor=True)
            h_report = detector.detect(report_data, items=self.items)
            saved_path = detector.save_report(h_report)
            detector.close()

            self._logger.info(
                "hallucination_detection_done issues=%d critical=%d high=%d confidence=%.4f",
                h_report.total_issues,
                h_report.severity_counts.get("critical", 0),
                h_report.severity_counts.get("high", 0),
                h_report.confidence_score,
            )

            if saved_path:
                self.hallucination_signal.emit(saved_path)

        except Exception as exc:
            self._logger.error("hallucination_detection_failed error=%s", exc)

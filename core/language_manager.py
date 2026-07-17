import json
import os
from datetime import datetime
try:
    from PyQt5.QtCore import QLocale, QSettings
except Exception:
    QLocale = None
    QSettings = None

class LanguageManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LanguageManager, cls).__new__(cls)
            cls._instance.current_language = "en"
            cls._instance.translations = {}
            cls._instance._fallback_en = {}
            cls._instance.initialize_language()
        return cls._instance

    def _load_file(self, lang_code):
        path = os.path.join(os.path.dirname(__file__), "..", "locales", f"{lang_code}.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def initialize_language(self):
        self._fallback_en = self._load_file("en")
        # preference via QSettings if available
        pref_lang = None
        if QSettings is not None:
            settings = QSettings("HKIIT", "WindowsSecurityAuditor")
            pref_lang = settings.value("language", type=str)
        if pref_lang:
            self.load_language(pref_lang)
            return
        # system detection
        sys_lang = "en"
        try:
            if QLocale is not None:
                ql = QLocale.system()
                if ql.language() in (QLocale.Chinese,):
                    sys_lang = "zh_hk"
            else:
                import locale as pylocale
                loc = pylocale.getdefaultlocale()[0] or ""
                if loc.lower().startswith("zh"):
                    sys_lang = "zh_hk"
        except Exception:
            sys_lang = "en"
        self.load_language(sys_lang)

    def load_language(self, lang_code):
        try:
            self.translations = self._load_file(lang_code)
            self.current_language = lang_code
            if QSettings is not None:
                settings = QSettings("HKIIT", "WindowsSecurityAuditor")
                settings.setValue("language", lang_code)
            return True
        except Exception as e:
            print(f"Error loading language {lang_code}: {e}")
        return False

    def get_text(self, key, *args):
        text = self.translations.get(key, None)
        if text is None:
            text = self._fallback_en.get(key, key)
        if args:
            try:
                return text.format(*args)
            except Exception:
                pass
        return text

    def format_date(self, date_str):
        # expects YYYY-MM-DD or ISO date; returns localized display
        try:
            dt = None
            for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
                try:
                    dt = datetime.strptime(date_str, fmt)
                    break
                except Exception:
                    continue
            if dt is None:
                dt = datetime.fromisoformat(date_str)
        except Exception:
            return date_str
        if self.current_language.startswith("zh"):
            return f"{dt.year}年{dt.month:02d}月{dt.day:02d}日"
        return dt.strftime("%Y-%m-%d")

    def format_time(self, time_str):
        # expects HH:MM:SS or ISO time; returns 24h format
        try:
            try:
                dt = datetime.strptime(time_str, "%H:%M:%S")
            except Exception:
                dt = datetime.fromisoformat(time_str)
        except Exception:
            return time_str
        if self.current_language.startswith("zh"):
            return dt.strftime("%H:%M:%S")
        return dt.strftime("%H:%M:%S")

lang_manager = LanguageManager()

def tr(key, *args):
    return lang_manager.get_text(key, *args)

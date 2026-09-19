"""安装器自己的 i18n，独立于主程序。"""

import json
import os

from PySide6.QtCore import QObject, Signal


class I18n(QObject):
    language_changed = Signal(str)

    def __init__(self, i18n_dir):
        super().__init__()
        self.i18n_dir = i18n_dir
        self.current_lang = ""
        self.translations = {}

    def available(self):
        """返回 [(code, display_name), ...]"""
        result = []
        if os.path.isdir(self.i18n_dir):
            for fn in sorted(os.listdir(self.i18n_dir)):
                if fn.endswith(".json"):
                    code = fn[:-5]
                    display = code
                    try:
                        with open(os.path.join(self.i18n_dir, fn),
                                  "r", encoding="utf-8") as f:
                            data = json.load(f)
                        display = data.get("_meta.name", code)
                    except Exception:
                        pass
                    result.append((code, display))
        return result

    def load(self, lang_code):
        path = os.path.join(self.i18n_dir, f"{lang_code}.json")
        if not os.path.exists(path):
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.translations = json.load(f)
            self.current_lang = lang_code
            self.language_changed.emit(lang_code)
            return True
        except Exception:
            return False

    def t(self, key, **kwargs):
        text = self.translations.get(key, key)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except Exception:
                pass
        return text
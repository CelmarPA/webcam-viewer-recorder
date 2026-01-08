# utils/settings_manager.py

import json
from pathlib import Path
from typing import Any, Optional

class SettingsManager:
    """
    Gerencia persistência de configurações do usuário para o Webcam Recorder.

    Salva e carrega um arquivo JSON em ~/.webcam_recorder/settings.json.
    """

    def __init__(self) -> None:
        self.settings_dir = Path.home() / ".webcam_recorder"
        self.settings_dir.mkdir(exist_ok=True)
        self.settings_file = self.settings_dir / "settings.json"
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """Carrega configurações do JSON, se existir."""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}
        else:
            self._data = {}

    def save(self, data: Optional[dict[str, Any]] = None) -> None:
        """
        Salva configurações no JSON.

        :param data: Se fornecido, substitui os dados atuais antes de salvar.
        """
        if data:
            self._data.update(data)
        try:
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=4)
        except Exception:
            pass  # Falha ao salvar não é crítica

    def get(self, key: str, default: Any = None) -> Any:
        """Retorna valor da configuração ou default se não existir."""
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Define valor de uma configuração e salva automaticamente."""
        self._data[key] = value
        self.save()

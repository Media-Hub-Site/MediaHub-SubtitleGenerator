"""
apps/media_converter/i18n.py
────────────────────────────
Gestor de internacionalización ligero para MediaHub-SubtitleGenerator.
"""

import os
import sys
import json
import locale

_CURRENT_LANG = None

STRINGS = {
    "es": {
        "app_title": "Generador de Subtítulos — Whisper AI",
        "btn_open_folder": "Abrir Carpeta",
        "btn_select_media": "Seleccionar Archivo Multimedia",
        "btn_generate": "Generar Subtítulos (.srt)",
        "btn_burn": "Exportar Video con Subtítulos",
        "btn_save_edits": "Guardar Cambios",
        "lbl_lang_spoken": "Idioma hablado:",
        "lbl_model": "Modelo Whisper:",
        "status_ready": "Listo para generar subtítulos.",
        "status_generating": "Transcribiendo audio con Whisper AI...",
        "status_exporting": "Incrustando subtítulos en el video...",
        "no_file_selected": "Ningún archivo cargado",
    },
    "en": {
        "app_title": "Subtitle Generator — Whisper AI",
        "btn_open_folder": "Open Folder",
        "btn_select_media": "Select Media File",
        "btn_generate": "Generate Subtitles (.srt)",
        "btn_burn": "Export Subtitled Video",
        "btn_save_edits": "Save Changes",
        "lbl_lang_spoken": "Spoken language:",
        "lbl_model": "Whisper Model:",
        "status_ready": "Ready to generate subtitles.",
        "status_generating": "Transcribing audio with Whisper AI...",
        "status_exporting": "Hardcoding subtitles into video...",
        "no_file_selected": "No file loaded",
    }
}


def get_current_language() -> str:
    global _CURRENT_LANG
    if _CURRENT_LANG:
        return _CURRENT_LANG

    # 1. CLI argument
    for arg in sys.argv[1:]:
        if arg.startswith("--lang="):
            val = arg.split("=", 1)[1].strip().lower()
            if val in ("es", "en"):
                _CURRENT_LANG = val
                return _CURRENT_LANG

    # 2. Environment variables
    for env_var in ("MEDIAHUB_APP_LANG", "MEDIAHUB_LANG", "LANG"):
        val = os.environ.get(env_var, "").lower()
        if val.startswith("es"):
            _CURRENT_LANG = "es"
            return "es"
        elif val.startswith("en"):
            _CURRENT_LANG = "en"
            return "en"

    # 3. Local config_lang.json
    base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    for cfg in [os.path.join(base_dir, "config_lang.json"), os.path.join(base_dir, "..", "config_lang.json")]:
        if os.path.isfile(cfg):
            try:
                with open(cfg, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    val = data.get("language")
                    if val in ("es", "en"):
                        _CURRENT_LANG = val
                        return _CURRENT_LANG
            except Exception:
                pass

    # 4. Fallback sistema
    try:
        lang, _ = locale.getdefaultlocale()
        if lang and lang.lower().startswith("es"):
            _CURRENT_LANG = "es"
            return "es"
    except Exception:
        pass

    _CURRENT_LANG = "es"
    return "es"


def t(key: str, **kwargs) -> str:
    lang = get_current_language()
    text = STRINGS.get(lang, STRINGS["es"]).get(key, STRINGS["es"].get(key, key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text

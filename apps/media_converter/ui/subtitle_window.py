"""
apps/media_converter/ui/subtitle_window.py
──────────────────────────────────────────
Ventana moderna de Generador de Subtítulos con Whisper AI.
Incluye:
  1. Selector visual de modelos Whisper (Tiny, Base, Small) con indicador de peso y velocidad.
  2. Selector de idioma y traducción automática al inglés/español.
  3. Previsualizador / Editor de texto del archivo SRT generado.
  4. Incrustador / Quemado directo de subtítulos en el video (Estilo Reels/TikTok o Blanco clásico).
"""

import os
import sys
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QMessageBox, QComboBox, QCheckBox, QFrame, QTextEdit,
    QProgressBar, QSplitter
)
from PyQt6.QtGui import QIcon, QFont
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from apps.media_converter.converters.whisper_logic import WhisperSubtitleLogic


def get_asset(filename):
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    p = os.path.join(base, "assets", "hub", filename)
    if os.path.isfile(p):
        return p
    return os.path.join(base, "assets", filename)


class SubtitleWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str, str)  # (srt_path, srt_content)
    error = pyqtSignal(str)

    def __init__(self, video_path: str, srt_out_path: str, model_size: str, lang: str, translate: bool, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.srt_out_path = srt_out_path
        self.model_size = model_size
        self.lang = lang
        self.translate = translate

    def run(self):
        self.progress.emit(10, "Preparando modelo Whisper e IA...")
        ok, res = WhisperSubtitleLogic.generar_subtitulos(
            self.video_path, self.srt_out_path, self.model_size, self.lang, self.translate
        )
        if not ok:
            self.error.emit(res)
            return

        content = ""
        if os.path.isfile(res):
            try:
                with open(res, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except Exception:
                pass

        self.progress.emit(100, "¡Subtítulos generados con éxito!")
        self.finished.emit(res, content)


class BurnWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, video_path: str, srt_path: str, out_video_path: str, style_name: str, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.srt_path = srt_path
        self.out_video_path = out_video_path
        self.style_name = style_name

    def run(self):
        self.progress.emit(20, "Incrustando subtítulos en el video...")
        ok, res = WhisperSubtitleLogic.quemar_subtitulos_en_video(
            self.video_path, self.srt_path, self.out_video_path, self.style_name
        )
        if not ok:
            self.error.emit(res)
        else:
            self.progress.emit(100, "¡Video con subtítulos listo!")
            self.finished.emit(res)


class SubtitleWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Subtitle Generator — Whisper AI")
        self.resize(980, 640)
        self.setMinimumSize(920, 580)

        icon_path = get_asset("Media-Hub.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.selected_media: str | None = None
        self.current_srt_path: str | None = None
        self.worker: SubtitleWorker | None = None
        self.burn_worker: BurnWorker | None = None

        self._init_ui()
        self._apply_styles()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(18)

        # Header
        header = QHBoxLayout()
        h_text = QVBoxLayout()
        h_text.setSpacing(2)

        title = QLabel("SUBTITLE GENERATOR")
        title.setObjectName("mainTitle")
        sub = QLabel("Transcripción y generación de subtítulos locales potenciado por Whisper AI")
        sub.setObjectName("subTitle")
        h_text.addWidget(title)
        h_text.addWidget(sub)
        header.addLayout(h_text)
        header.addStretch()

        self.btn_open_folder = QPushButton("Abrir Carpeta")
        self.btn_open_folder.setObjectName("btnSecondary")
        self.btn_open_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_folder.clicked.connect(self._open_downloads_dir)
        header.addWidget(self.btn_open_folder)
        main_layout.addLayout(header)

        # Barra de carga de archivo
        file_box = QFrame()
        file_box.setObjectName("cardBox")
        fb_layout = QHBoxLayout(file_box)
        fb_layout.setContentsMargins(16, 12, 16, 12)

        self.lbl_file = QLabel("Arrastra o selecciona un archivo de Video o Audio (.mp4, .mkv, .mp3, .wav, .m4a)")
        self.lbl_file.setObjectName("lblFile")
        fb_layout.addWidget(self.lbl_file, stretch=1)

        self.btn_select = QPushButton("Seleccionar Archivo")
        self.btn_select.setObjectName("btnPrimary")
        self.btn_select.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_select.clicked.connect(self._pick_file)
        fb_layout.addWidget(self.btn_select)
        main_layout.addWidget(file_box)

        # Splitter central: Ajustes + Editor de Subtítulos
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Panel izquierdo: Opciones del Modelo y Parámetros
        left_panel = QFrame()
        left_panel.setObjectName("cardBox")
        lp_layout = QVBoxLayout(left_panel)
        lp_layout.setContentsMargins(18, 16, 18, 16)
        lp_layout.setSpacing(12)

        sec_title = QLabel("Configuración de Whisper AI")
        sec_title.setStyleSheet("font-size:11pt; font-weight:700; color:#FFFFFF;")
        lp_layout.addWidget(sec_title)

        # Modelo
        lp_layout.addWidget(QLabel("Modelo de Transcripción:"))
        self.combo_model = QComboBox()
        self.combo_model.addItems([
            "Base (~145 MB • Balanceado y Recomendado)",
            "Tiny (~75 MB • Ultrarrápido)",
            "Small (~480 MB • Alta Precisión)"
        ])
        lp_layout.addWidget(self.combo_model)

        # Idioma
        lp_layout.addWidget(QLabel("Idioma del Audio:"))
        self.combo_lang = QComboBox()
        self.combo_lang.addItems(["auto (Detección Automática)", "es (Español)", "en (Inglés)", "fr (Francés)", "pt (Portugués)"])
        lp_layout.addWidget(self.combo_lang)

        # Traducir al inglés
        self.chk_translate = QCheckBox("Traducir contenido al Inglés (-tr)")
        lp_layout.addWidget(self.chk_translate)

        lp_layout.addSpacing(10)

        # Botón Generar SRT
        self.btn_generate = QPushButton("Generar Subtítulos (.srt)")
        self.btn_generate.setObjectName("btnAccent")
        self.btn_generate.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_generate.clicked.connect(self._start_transcription)
        lp_layout.addWidget(self.btn_generate)

        lp_layout.addSpacing(15)
        burn_title = QLabel("Incrustar en Video (Hardcode)")
        burn_title.setStyleSheet("font-size:10pt; font-weight:700; color:#FFFFFF;")
        lp_layout.addWidget(burn_title)

        self.combo_burn_style = QComboBox()
        self.combo_burn_style.addItems(["Amarillo estilo Reels / TikTok", "Blanco Clásico con Borde"])
        lp_layout.addWidget(self.combo_burn_style)

        self.btn_burn = QPushButton("Exportar Video con Subtítulos")
        self.btn_burn.setObjectName("btnBurn")
        self.btn_burn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_burn.setEnabled(False)
        self.btn_burn.clicked.connect(self._burn_subtitles)
        lp_layout.addWidget(self.btn_burn)

        lp_layout.addStretch()
        splitter.addWidget(left_panel)

        # Panel derecho: Editor / Visualizador SRT
        right_panel = QFrame()
        right_panel.setObjectName("cardBox")
        rp_layout = QVBoxLayout(right_panel)
        rp_layout.setContentsMargins(18, 16, 18, 16)
        rp_layout.setSpacing(10)

        rp_header = QHBoxLayout()
        rp_title = QLabel("Vista Previa y Editor SRT")
        rp_title.setStyleSheet("font-size:11pt; font-weight:700; color:#FFFFFF;")
        rp_header.addWidget(rp_title)
        rp_header.addStretch()

        self.btn_save_edits = QPushButton("Guardar Cambios")
        self.btn_save_edits.setObjectName("btnSecondary")
        self.btn_save_edits.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save_edits.setEnabled(False)
        self.btn_save_edits.clicked.connect(self._save_srt_edits)
        rp_header.addWidget(self.btn_save_edits)
        rp_layout.addLayout(rp_header)

        self.srt_editor = QTextEdit()
        self.srt_editor.setPlaceholderText("Los subtítulos generados aparecerán aquí para que puedas revisarlos y editarlos...")
        rp_layout.addWidget(self.srt_editor, stretch=1)

        splitter.addWidget(right_panel)
        splitter.setSizes([340, 600])

        main_layout.addWidget(splitter, stretch=1)

        # Footer con barra de estado y progreso
        footer = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(False)
        footer.addWidget(self.progress_bar, stretch=1)

        self.status_label = QLabel("Listo.")
        self.status_label.setObjectName("statusLabel")
        footer.addWidget(self.status_label)
        main_layout.addLayout(footer)

    def _pick_file(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Multimedia", "",
            "Multimedia (*.mp4 *.mkv *.avi *.mov *.webm *.mp3 *.wav *.m4a *.ogg *.flac)"
        )
        if file:
            self.selected_media = file
            self.lbl_file.setText(os.path.basename(file))
            self.status_label.setText("Archivo listo para transcribir.")
            self.current_srt_path = None
            self.srt_editor.clear()
            self.btn_burn.setEnabled(False)
            self.btn_save_edits.setEnabled(False)

    def _get_output_dir(self):
        home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
        dest = os.path.join(home, "Downloads", "MediaHub_Subtitles")
        os.makedirs(dest, exist_ok=True)
        return dest

    def _open_downloads_dir(self):
        d = self._get_output_dir()
        try:
            os.startfile(d)
        except Exception as e:
            QMessageBox.warning(self, "Aviso", f"No se pudo abrir la carpeta:\n{e}")

    def _start_transcription(self):
        if not self.selected_media or not os.path.isfile(self.selected_media):
            QMessageBox.warning(self, "Atención", "Por favor selecciona primero un archivo de video o audio.")
            return

        model_map = {0: "base", 1: "tiny", 2: "small"}
        model_size = model_map.get(self.combo_model.currentIndex(), "base")

        lang_raw = self.combo_lang.currentText()
        lang = lang_raw.split()[0] if "(" in lang_raw else "auto"

        translate = self.chk_translate.isChecked()

        out_dir = self._get_output_dir()
        base_name, _ = os.path.splitext(os.path.basename(self.selected_media))
        srt_out = os.path.join(out_dir, f"{base_name}.srt")

        self.btn_generate.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(20)
        self.status_label.setText("⏳ Transcribiendo con Whisper AI...")

        self.worker = SubtitleWorker(self.selected_media, srt_out, model_size, lang, translate, self)
        self.worker.progress.connect(self._on_worker_progress)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.error.connect(self._on_worker_error)
        self.worker.start()

    def _on_worker_progress(self, pct: int, msg: str):
        self.progress_bar.setValue(pct)
        self.status_label.setText(msg)

    def _on_worker_finished(self, srt_path: str, content: str):
        self.btn_generate.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.current_srt_path = srt_path
        self.srt_editor.setPlainText(content)
        self.status_label.setText(f"Subtítulos guardados en: {os.path.basename(srt_path)}")
        self.btn_save_edits.setEnabled(True)

        # Si el archivo original es video, habilitamos incrustar
        ext = os.path.splitext(self.selected_media)[1].lower()
        if ext in (".mp4", ".mkv", ".avi", ".mov", ".webm"):
            self.btn_burn.setEnabled(True)

    def _on_worker_error(self, err: str):
        self.btn_generate.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText("Error generando subtítulos")
        QMessageBox.critical(self, "Error de Transcripción", err)

    def _save_srt_edits(self):
        if not self.current_srt_path:
            return
        try:
            with open(self.current_srt_path, "w", encoding="utf-8") as f:
                f.write(self.srt_editor.toPlainText())
            self.status_label.setText("Cambios en el archivo SRT guardados correctamente.")
            QMessageBox.information(self, "Guardado", "El archivo SRT se ha actualizado.")
        except Exception as e:
            QMessageBox.critical(self, "Error al guardar", str(e))

    def _burn_subtitles(self):
        if not self.selected_media or not self.current_srt_path:
            return

        self._save_srt_edits()

        out_dir = self._get_output_dir()
        base_name, ext = os.path.splitext(os.path.basename(self.selected_media))
        out_video = os.path.join(out_dir, f"{base_name}_subtitled.mp4")

        style = self.combo_burn_style.currentText()

        self.btn_burn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(30)
        self.status_label.setText("⏳ Incrustando subtítulos en el video...")

        self.burn_worker = BurnWorker(self.selected_media, self.current_srt_path, out_video, style, self)
        self.burn_worker.progress.connect(self._on_worker_progress)
        self.burn_worker.finished.connect(self._on_burn_finished)
        self.burn_worker.error.connect(self._on_burn_error)
        self.burn_worker.start()

    def _on_burn_finished(self, out_path: str):
        self.btn_burn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"Video subtitulado exportado: {os.path.basename(out_path)}")
        QMessageBox.information(
            self, "Video Completado",
            f"El video con subtítulos incrustados se guardó en:\n{out_path}"
        )

    def _on_burn_error(self, err: str):
        self.btn_burn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText("Error incrustando subtítulos")
        QMessageBox.critical(self, "Error de Video", err)

    def _apply_styles(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0F1117;
                color: #F3F4F6;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }
            QLabel#mainTitle {
                color: #FFFFFF;
                font-size: 15pt;
                font-weight: 800;
                letter-spacing: -0.3px;
            }
            QLabel#subTitle {
                color: #828B9E;
                font-size: 9.5pt;
            }
            QFrame#cardBox {
                background-color: #161822;
                border: 1px solid #232736;
                border-radius: 12px;
            }
            QLabel#lblFile {
                color: #9CA3AF;
                font-size: 9.5pt;
                font-weight: 500;
            }
            QPushButton#btnPrimary {
                background-color: #1F2433;
                color: #FFFFFF;
                border: 1px solid #323A52;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 9.5pt;
                font-weight: 600;
            }
            QPushButton#btnPrimary:hover {
                background-color: #2B334A;
            }
            QPushButton#btnSecondary {
                background-color: #1A1D28;
                color: #D1D5DB;
                border: 1px solid #282E40;
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 9pt;
                font-weight: 600;
            }
            QPushButton#btnSecondary:hover {
                background-color: #252B3B;
                color: #FFFFFF;
            }
            QPushButton#btnAccent {
                background-color: #2563EB;
                color: #FFFFFF;
                border: none;
                border-radius: 9px;
                padding: 10px 18px;
                font-size: 10pt;
                font-weight: 700;
            }
            QPushButton#btnAccent:hover {
                background-color: #1D4ED8;
            }
            QPushButton#btnBurn {
                background-color: #059669;
                color: #FFFFFF;
                border: none;
                border-radius: 9px;
                padding: 10px 18px;
                font-size: 10pt;
                font-weight: 700;
            }
            QPushButton#btnBurn:hover {
                background-color: #047857;
            }
            QPushButton#btnBurn:disabled, QPushButton#btnAccent:disabled {
                background-color: #1E2333;
                color: #6B7280;
            }
            QComboBox, QCheckBox {
                background-color: #11131B;
                color: #F3F4F6;
                border: 1px solid #282E40;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 9pt;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 8px;
            }
            QComboBox QAbstractItemView {
                background-color: #1A1D28;
                color: #F3F4F6;
                selection-background-color: #2563EB;
                selection-color: #FFFFFF;
                border: 1px solid #282E40;
                outline: none;
                padding: 4px;
            }
            QComboBox QAbstractItemView::item {
                min-height: 28px;
                color: #F3F4F6;
                padding: 4px 8px;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #2563EB;
                color: #FFFFFF;
            }
            QTextEdit {
                background-color: #11131B;
                color: #E2E8F0;
                border: 1px solid #232736;
                border-radius: 8px;
                padding: 10px;
                font-family: "Consolas", "Courier New", monospace;
                font-size: 9.5pt;
                line-height: 1.4;
            }
            QLabel#statusLabel {
                color: #9CA3AF;
                font-size: 9pt;
                font-weight: 500;
            }
            QProgressBar {
                background-color: #161822;
                border: 1px solid #232736;
                border-radius: 6px;
                min-height: 8px;
            }
            QProgressBar::chunk {
                background-color: #2563EB;
                border-radius: 6px;
            }
        """)

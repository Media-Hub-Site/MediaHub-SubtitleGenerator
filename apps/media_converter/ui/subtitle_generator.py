import sys
import os
import datetime
import subprocess
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QFileDialog, QMessageBox, 
    QHBoxLayout, QComboBox, QFrame
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

from apps.media_converter.converters.conversion import SubtitleGeneratorLogic
from apps.media_converter.ui.ui_theme import (
    get_app_colors,
    get_button_style,
    get_drop_label_style,
    get_soft_button_style,
    get_remove_button_style,
    get_convert_button_style,
    apply_window_theme,
    make_card_container,
)

class MediaDropLabel(QLabel):
    def __init__(self, on_media_dropped, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText("Arrastra aquí tu Video o Audio")
        self.setStyleSheet(f"{get_drop_label_style()}min-height: 180px;")
        self.setAcceptDrops(True)
        self.on_media_dropped = on_media_dropped
        self.allowed_extensions = ('.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.mp3', '.wav', '.m4a', '.ogg')

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            valid = any(
                url.toLocalFile().lower().endswith(self.allowed_extensions)
                for url in event.mimeData().urls()
            )
            if valid:
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            valid_files = [
                url.toLocalFile()
                for url in event.mimeData().urls()
                if url.toLocalFile().lower().endswith(self.allowed_extensions)
            ]
            invalid_count = len(event.mimeData().urls()) - len(valid_files)
            if valid_files:
                self.on_media_dropped(valid_files)
            if invalid_count > 0:
                QMessageBox.warning(self, "Formato no soportado", f"{invalid_count} archivo(s) no son válidos y fueron ignorados.")
        else:
            event.ignore()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if hasattr(self.main_window, 'open_batch_manager'):
                self.main_window.open_batch_manager()


class SubtitleGeneratorUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Generador de Subtítulos (IA)")
        self.setGeometry(100, 100, 480, 560)
        apply_window_theme(self)
        self._colors = get_app_colors()
        
        self.batch_files = []
        self.init_ui()

    def init_ui(self):
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(26, 24, 26, 24)
        card, card_layout = make_card_container()

        top_layout = QHBoxLayout()
        back_btn = QPushButton("← Volver al Hub")
        back_btn.setFixedWidth(130)
        back_btn.clicked.connect(self.go_back)
        back_btn.setStyleSheet(get_soft_button_style())
        top_layout.addWidget(back_btn)
        top_layout.addStretch()
        card_layout.addLayout(top_layout)

        self.label = QLabel("Selecciona un archivo multimedia para generar subtítulos (.srt)")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet(f"color: {{self._colors['text_main']}}; font-size: 13pt; font-weight:600;")
        self.label.setWordWrap(True)
        card_layout.addWidget(self.label)

        self.info_label = QLabel("Utiliza Whisper AI para transcribir audios y videos con altísima precisión.")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet(f"color: {{self._colors['text_muted']}}; font-size: 10pt;")
        self.info_label.setWordWrap(True)
        card_layout.addWidget(self.info_label)

        # Settings Frame
        settings_frame = QFrame()
        settings_frame.setStyleSheet(f"background: {{self._colors['card']}}; border-radius: 8px; margin-top: 10px; margin-bottom: 10px;")
        settings_layout = QVBoxLayout(settings_frame)
        settings_layout.setContentsMargins(15, 15, 15, 15)
        
        # Model Selection
        model_layout = QHBoxLayout()
        model_label = QLabel("Modelo IA:")
        model_label.setStyleSheet(f"color: {{self._colors['text_muted']}}; font-weight: bold;")
        self.combo_model = QComboBox()
        self.combo_model.addItems(["Tiny (Rápido)", "Base (Balanceado)", "Small (Preciso)"])
        self.combo_model.setCurrentText("Base (Balanceado)")
        self.combo_model.setStyleSheet(f"background: {{self._colors['bg']}}; color: {{self._colors['text_main']}}; border: 1px solid {{self._colors['border']}}; border-radius: 4px; padding: 4px;")
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.combo_model)
        settings_layout.addLayout(model_layout)
        
        # Language Selection
        lang_layout = QHBoxLayout()
        lang_label = QLabel("Idioma:")
        lang_label.setStyleSheet(f"color: {{self._colors['text_muted']}}; font-weight: bold;")
        self.combo_lang = QComboBox()
        self.combo_lang.addItems(["Automático", "es (Español)", "en (Inglés)"])
        self.combo_lang.setStyleSheet(f"background: {{self._colors['bg']}}; color: {{self._colors['text_main']}}; border: 1px solid {{self._colors['border']}}; border-radius: 4px; padding: 4px;")
        lang_layout.addWidget(lang_label)
        lang_layout.addWidget(self.combo_lang)
        settings_layout.addLayout(lang_layout)
        
        card_layout.addWidget(settings_frame)

        self.media_label = MediaDropLabel(self.on_media_dropped, self)
        card_layout.addWidget(self.media_label)

        # Botones de Acción
        self.select_button = QPushButton("Seleccionar Archivos")
        self.select_button.clicked.connect(self.select_media)
        self.select_button.setStyleSheet(get_button_style())
        card_layout.addWidget(self.select_button)

        self.remove_button = QPushButton("Quitar todo")
        self.remove_button.clicked.connect(self.remove_media)
        self.remove_button.setEnabled(False)
        self.remove_button.setStyleSheet(get_remove_button_style())
        card_layout.addWidget(self.remove_button)

        self.convert_button = QPushButton("Generar Subtítulos")
        self.convert_button.clicked.connect(self.generate_subtitles)
        self.convert_button.setEnabled(False)
        self.convert_button.setStyleSheet(get_convert_button_style())
        card_layout.addWidget(self.convert_button)

        self.layout.addWidget(card)
        self.setLayout(self.layout)

    def open_batch_manager(self):
        if self.batch_files:
            from core.ui.batch_dialog import BatchDialog
            from PyQt6.QtWidgets import QDialog
            dialog = BatchDialog(self.batch_files, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.batch_files = dialog.get_files()
                if len(self.batch_files) == 0:
                    self.remove_media()
                elif len(self.batch_files) == 1:
                    self.media_label.clear()
                    self.media_label.setText(os.path.basename(self.batch_files[0]))
                else:
                    self.media_label.clear()
                    self.media_label.setText(f"{len(self.batch_files)} archivos seleccionados")

    def go_back(self):
        from core.ui.hub_window import HubWindow
        self.hub_window = HubWindow()
        self.hub_window.show()
        self.close()

    def select_media(self):
        file_dialog = QFileDialog()
        file_paths, _ = file_dialog.getOpenFileNames(self, "Seleccionar Multimedia", "", "Multimedia (*.mp4 *.mkv *.avi *.mov *.webm *.mp3 *.wav *.m4a *.ogg)")
        if file_paths:
            for fp in file_paths:
                if fp not in self.batch_files:
                    self.batch_files.append(fp)
            self._refresh_label()

    def on_media_dropped(self, file_paths):
        for fp in file_paths:
            if fp not in self.batch_files:
                self.batch_files.append(fp)
        self._refresh_label()

    def _refresh_label(self):
        if not self.batch_files:
            return
        if len(self.batch_files) == 1:
            self.media_label.clear()
            self.media_label.setText(os.path.basename(self.batch_files[0]))
        else:
            self.media_label.clear()
            self.media_label.setText(f"{len(self.batch_files)} archivos seleccionados")
        self.convert_button.setEnabled(True)
        self.remove_button.setEnabled(True)

    def remove_media(self):
        self.batch_files = []
        self.media_label.clear()
        self.media_label.setText("Arrastra aquí tu Video o Audio")
        self.convert_button.setEnabled(False)
        self.remove_button.setEnabled(False)

    def choose_output_folder(self):
        return QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de salida")

    def generate_subtitles(self):
        output_dir = self.choose_output_folder()
        if not output_dir:
            return

        model_map = {
            "Tiny (Rápido)": "tiny",
            "Base (Balanceado)": "base",
            "Small (Preciso)": "small"
        }
        selected_model = model_map.get(self.combo_model.currentText(), "base")
        
        lang_text = self.combo_lang.currentText()
        if lang_text == "Automático":
            language = "auto"
        elif "es" in lang_text:
            language = "es"
        else:
            language = "en"

        if self.batch_files:
            if len(self.batch_files) > 5:
                folder_name = "Subtitulos_Masivos_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                output_dir = os.path.join(output_dir, folder_name)
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                    
            converted = 0
            failed = 0
            total = len(self.batch_files)
            was_cancelled = False
            
            from core.ui.advanced_progress import AdvancedProgressDialog
            progress = AdvancedProgressDialog("Generando Subtítulos...", total, self)
            progress.show()
            QApplication.processEvents()

            try:
                for idx, file_path in enumerate(self.batch_files, start=1):
                    while progress.is_paused and not progress.is_cancelled:
                        import time
                        time.sleep(0.1)
                        QApplication.processEvents()
                        
                    if progress.is_cancelled:
                        was_cancelled = True
                        break
                        
                    nombre = os.path.splitext(os.path.basename(file_path))[0]
                    ruta_destino = os.path.join(output_dir, f"{nombre}.srt")
                    
                    resultado = SubtitleGeneratorLogic.generar_subtitulos(
                        ruta_origen=file_path,
                        ruta_destino=ruta_destino,
                        model_size=selected_model,
                        language=language
                    )
                    
                    if str(resultado).startswith("✅"):
                        converted += 1
                    else:
                        failed += 1
                        
                    progress.setLabelText(f"Transcribiendo... ({idx}/{total})")
                    progress.setValue(idx)
                    QApplication.processEvents()
            finally:
                progress.close()

            if was_cancelled:
                QMessageBox.warning(
                    self,
                    "Proceso Cancelado",
                    f"Proceso cancelado por el usuario.\nSe completaron {converted} de {total} archivos."
                )
            else:
                QMessageBox.information(
                    self,
                    "Proceso Masivo",
                    f"Procesados con éxito: {converted}\nFallidos: {failed}",
                )
            try:
                from core.ui.result_viewer import ResultViewerDialog
                viewer = ResultViewerDialog(output_dir, self)
                viewer.exec()
            except Exception:
                try:
                    os.startfile(output_dir)
                except AttributeError:
                    import subprocess
                    subprocess.Popen(["xdg-open", output_dir])

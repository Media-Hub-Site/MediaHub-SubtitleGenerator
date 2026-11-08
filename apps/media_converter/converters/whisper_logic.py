"""
Módulo de lógica para Subtitle Generator con Whisper AI y quemado de subtítulos en video.
"""

import os
import subprocess
import tempfile
import shutil
import uuid
import requests
import zipfile


def _find_ffmpeg() -> str | None:
    for name in ("ffmpeg.exe", "ffmpeg"):
        p = shutil.which(name)
        if p and os.path.isfile(p):
            return p

    home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    hub_ffmpeg = os.path.join(home, ".mediahub", "bin", "ffmpeg.exe")
    if os.path.isfile(hub_ffmpeg):
        return hub_ffmpeg

    try:
        import imageio_ffmpeg
        orig_exe = imageio_ffmpeg.get_ffmpeg_exe()
        if orig_exe and os.path.isfile(orig_exe):
            return orig_exe
    except Exception:
        pass
    return None


class WhisperSubtitleLogic:
    @staticmethod
    def _download_whisper_if_needed():
        home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
        whisper_dir = os.path.join(home, ".mediahub", "models", "whisper")
        os.makedirs(whisper_dir, exist_ok=True)
        exe_path = os.path.join(whisper_dir, "main.exe")

        if not os.path.exists(exe_path):
            zip_path = os.path.join(whisper_dir, "whisper-bin-x64.zip")
            url = "https://github.com/ggerganov/whisper.cpp/releases/download/v1.5.4/whisper-bin-x64.zip"
            resp = requests.get(url, stream=True, timeout=30)
            if resp.status_code == 200:
                with open(zip_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=65536):
                        f.write(chunk)
                with zipfile.ZipFile(zip_path, "r") as zf:
                    zf.extractall(whisper_dir)
                if os.path.exists(zip_path):
                    os.remove(zip_path)
            else:
                raise Exception("No se pudo descargar el binario de Whisper.")
        return exe_path

    @staticmethod
    def _download_model_if_needed(model_size="base"):
        home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
        models_dir = os.path.join(home, ".mediahub", "models", "whisper")
        os.makedirs(models_dir, exist_ok=True)

        model_name = f"ggml-{model_size}.bin"
        model_path = os.path.join(models_dir, model_name)

        if not os.path.exists(model_path):
            url = f"https://huggingface.co/ggerganov/whisper.cpp/resolve/main/{model_name}"
            resp = requests.get(url, stream=True, timeout=60)
            if resp.status_code == 200:
                with open(model_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=65536):
                        f.write(chunk)
            else:
                raise Exception(f"No se pudo descargar el modelo Whisper '{model_size}'.")
        return model_path

    @staticmethod
    def generar_subtitulos(ruta_origen: str, ruta_destino_srt: str, model_size="base", language="auto", translate=False):
        try:
            exe_path = WhisperSubtitleLogic._download_whisper_if_needed()
            model_path = WhisperSubtitleLogic._download_model_if_needed(model_size)

            os.makedirs(os.path.dirname(os.path.abspath(ruta_destino_srt)), exist_ok=True)
            temp_dir = tempfile.gettempdir()
            uid = str(uuid.uuid4())
            wav_tmp = os.path.join(temp_dir, f"audio_{uid}.wav")

            ffmpeg_path = _find_ffmpeg()
            if not ffmpeg_path:
                return False, "ffmpeg no está disponible para extraer el audio del archivo."

            cmd_ffmpeg = [
                ffmpeg_path, "-y", "-i", ruta_origen,
                "-vn", "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav_tmp
            ]
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            subprocess.run(cmd_ffmpeg, check=True, startupinfo=startupinfo, capture_output=True)

            cmd_whisper = [
                exe_path,
                "-m", model_path,
                "-f", wav_tmp,
                "-l", language,
                "-osrt"
            ]
            if translate:
                cmd_whisper.append("-tr")

            res = subprocess.run(cmd_whisper, check=False, startupinfo=startupinfo, capture_output=True, text=True)
            if res.returncode != 0:
                return False, f"Whisper reportó un fallo: {res.stderr}"

            srt_tmp = wav_tmp + ".srt"
            if os.path.exists(srt_tmp):
                shutil.copy2(srt_tmp, ruta_destino_srt)
                try:
                    os.remove(srt_tmp)
                except Exception:
                    pass
            else:
                return False, "Whisper no generó el archivo de subtítulos."

            if os.path.exists(wav_tmp):
                try:
                    os.remove(wav_tmp)
                except Exception:
                    pass

            return True, ruta_destino_srt
        except Exception as e:
            return False, str(e)

    @staticmethod
    def quemar_subtitulos_en_video(video_path: str, srt_path: str, output_video_path: str, style_name="Amarillo estilo Reels"):
        """Incrusta (hardcodea) los subtítulos SRT en el video MP4."""
        ffmpeg_path = _find_ffmpeg()
        if not ffmpeg_path:
            return False, "ffmpeg no disponible."

        os.makedirs(os.path.dirname(os.path.abspath(output_video_path)), exist_ok=True)

        # Configurar estilos de subtítulos ASS/SRT
        if "Amarillo" in style_name:
            style_filter = "Fontname=Arial,Fontsize=22,PrimaryColour=&H0000FFFF,BackColour=&H80000000,BorderStyle=3,Outline=2"
        else:
            style_filter = "Fontname=Arial,Fontsize=20,PrimaryColour=&H00FFFFFF,BackColour=&H80000000,BorderStyle=3,Outline=2"

        # En Windows los backslashes en subtitles filter deben ser escapados
        escaped_srt = srt_path.replace("\\", "/").replace(":", "\\:")
        sub_filter = f"subtitles='{escaped_srt}':force_style='{style_filter}'"

        cmd = [
            ffmpeg_path, "-y", "-i", video_path,
            "-vf", sub_filter,
            "-c:v", "libx264", "-crf", "22", "-preset", "fast",
            "-c:a", "copy",
            output_video_path
        ]

        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        try:
            subprocess.run(cmd, check=True, startupinfo=startupinfo, capture_output=True)
            return True, output_video_path
        except subprocess.CalledProcessError as e:
            return False, f"Error quemando subtítulos: {e.stderr.decode(errors='replace')}"

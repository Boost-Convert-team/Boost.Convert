import os
import shutil
import subprocess
import tempfile

from flask import Blueprint, render_template, request, send_file
from pytubefix import YouTube
from werkzeug.utils import secure_filename

from Blueprints.services.convertions_services.ffmpeg_runner import get_ffmpeg_command


yt_download_bp = Blueprint("youtube_downloads", __name__)


@yt_download_bp.route("/tools/youtube-download", methods=["GET"])
def youtube_download():
    return render_template("youtube_download.html")


@yt_download_bp.route("/tools/youtube-download/download", methods=["POST"])
def download_youtube():
    url = (request.form.get("url") or "").strip()
    qualidade = (request.form.get("qualidade") or "").strip()

    if not url:
        return "Envie uma URL do YouTube", 400
    if not qualidade:
        return "Escolha uma qualidade", 400

    temp_dir = None
    try:
        caminho_arquivo, filename, temp_dir = processar_download(url, qualidade)
        response = send_file(caminho_arquivo, as_attachment=True, download_name=filename)
        response.call_on_close(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        return response
    except ValueError as exc:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
        return str(exc), 400
    except Exception as exc:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
        return f"Erro ao processar o video: {exc}", 500


def processar_download(url, qualidade):
    yt = YouTube(url)
    video = buscar_video(yt, qualidade)

    if video is None:
        raise ValueError("Qualidade indisponivel")

    temp_dir = tempfile.mkdtemp(prefix="boost_youtube_")
    filename = get_output_filename(yt.title)

    if video.is_progressive:
        caminho_arquivo = video.download(output_path=temp_dir, filename=filename)
    else:
        audio = buscar_audio(yt)
        if audio is None:
            raise ValueError("Audio indisponivel para este video")

        video_path = video.download(output_path=temp_dir, filename="video.mp4")
        audio_path = audio.download(output_path=temp_dir, filename="audio.m4a")
        caminho_arquivo = os.path.join(temp_dir, filename)
        juntar_video_audio(video_path, audio_path, caminho_arquivo)

    if not os.path.exists(caminho_arquivo):
        raise ValueError("Arquivo final nao foi gerado")

    return caminho_arquivo, filename, temp_dir


def buscar_video(yt, qualidade):
    video = yt.streams.filter(
        progressive=True,
        file_extension="mp4",
        res=qualidade,
    ).first()

    if video is not None:
        return video

    return yt.streams.filter(
        adaptive=True,
        file_extension="mp4",
        res=qualidade,
    ).first()


def buscar_audio(yt):
    return yt.streams.get_audio_only()


def juntar_video_audio(video_path, audio_path, output_path):
    comando = [
        get_ffmpeg_command(),
        "-y",
        "-i",
        video_path,
        "-i",
        audio_path,
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        output_path,
    ]
    subprocess.run(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def get_output_filename(title):
    filename = secure_filename(title or "video")
    if not filename:
        filename = "video"
    return f"{filename}.mp4"

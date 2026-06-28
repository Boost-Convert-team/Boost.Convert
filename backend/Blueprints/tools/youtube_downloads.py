import os
import shutil
import subprocess
import tempfile
import uuid
from urllib.parse import urlparse

from flask import Blueprint, current_app, redirect, render_template, request, url_for
from flask_login import current_user
from pytubefix import YouTube
from werkzeug.utils import secure_filename

from Blueprints.handlers.conversion_handlers import save_and_submit_jobs
from Blueprints.handlers.conversion_error_pages import render_conversion_error_response
from Blueprints.services.convertions_services.ffmpeg_runner import get_ffmpeg_command
from Blueprints.services.convertions_services.upload_flow.job_factory import (
    build_conversion_job,
    create_job_directory,
    get_storage_filename,
)
from Blueprints.services.subscription.session_service import get_anonymous_session_id


yt_download_bp = Blueprint("youtube_downloads", __name__)
ALLOWED_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}
ALLOWED_QUALITIES = {"1080p", "720p", "480p", "360p"}


@yt_download_bp.route("/tools/youtube-download", methods=["GET"])
def youtube_download():
    return render_template("youtube_download.html")


@yt_download_bp.route("/tools/youtube-download/download", methods=["POST"])
def download_youtube():
    url = (request.form.get("url") or "").strip()
    qualidade = (request.form.get("qualidade") or "").strip()

    if not url:
        return render_conversion_error_response(ValueError("Envie uma URL do YouTube"), 400)
    if not qualidade:
        return render_conversion_error_response(ValueError("Escolha uma qualidade"), 400)
    try:
        validate_youtube_request(url, qualidade)
    except ValueError as exc:
        return render_conversion_error_response(exc, 400)

    try:
        job = create_youtube_download_job(url, qualidade)
        save_and_submit_jobs([job], convert_youtube_video)
        return redirect(url_for("home.conversion_status", job_id=job.id))
    except ValueError as exc:
        return render_conversion_error_response(exc, 400)
    except Exception as exc:
        current_app.logger.error("Erro ao processar video do YouTube: %s", type(exc).__name__, exc_info=False)
        return render_conversion_error_response(RuntimeError("Nao foi possivel processar o video do YouTube."), 500)


def create_youtube_download_job(url: str, qualidade: str):
    job_id = str(uuid.uuid4())
    job_dir = create_job_directory(job_id)
    output_path = os.path.join(job_dir, get_storage_filename("output", "mp4"))
    output_filename = f"youtube_{qualidade}.mp4"
    usuario = current_user if current_user.is_authenticated else None
    session_id = None if usuario is not None else get_anonymous_session_id()
    job = build_conversion_job(
        job_id,
        usuario,
        session_id,
        "youtube_download",
        f"Video do YouTube ({qualidade})",
        output_filename,
        "youtube_url",
        output_path,
        {"qualidade": qualidade},
    )
    job.runtime_options = {"url": url, "qualidade": qualidade}
    return job


def convert_youtube_video(input_path, output_path, options=None):
    options = options or {}
    url = (options.get("url") or input_path or "").strip()
    qualidade = (options.get("qualidade") or "").strip()
    validate_youtube_request(url, qualidade)

    temp_dir = None
    try:
        caminho_arquivo, _filename, temp_dir = processar_download(url, qualidade)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        shutil.move(caminho_arquivo, output_path)
    finally:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)


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
        audio_extension = getattr(audio, "subtype", None) or getattr(audio, "file_extension", None) or "m4a"
        audio_path = audio.download(output_path=temp_dir, filename=f"audio.{audio_extension}")
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
    ).order_by("fps").desc().first()

    if video is not None:
        return video

    return yt.streams.filter(
        adaptive=True,
        file_extension="mp4",
        res=qualidade,
    ).order_by("fps").desc().first()


def buscar_audio(yt):
    audio = yt.streams.filter(only_audio=True, file_extension="mp4").order_by("abr").desc().first()
    if audio is not None:
        return audio
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
        "-movflags",
        "+faststart",
        output_path,
    ]
    subprocess.run(
        comando,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        timeout=get_youtube_timeout_seconds(),
    )


def validate_youtube_request(url: str, qualidade: str) -> None:
    """Validate YouTube download form values before remote access.

    Example: validate_youtube_request(url, "720p")
    """
    if qualidade not in ALLOWED_QUALITIES:
        raise ValueError("Qualidade invalida.")
    validate_youtube_url(url)


def validate_youtube_url(url: str) -> None:
    """Accept only YouTube HTTPS/HTTP hosts for remote downloads.

    Example: validate_youtube_url("https://www.youtube.com/watch?v=abc")
    """
    parsed_url = urlparse(url)
    host = (parsed_url.hostname or "").lower().rstrip(".")
    if parsed_url.scheme not in {"http", "https"} or host not in ALLOWED_YOUTUBE_HOSTS:
        raise ValueError("URL do YouTube invalida.")


def get_youtube_timeout_seconds() -> int:
    """Return the subprocess timeout used while muxing YouTube media.

    Example: timeout = get_youtube_timeout_seconds()
    """
    try:
        return max(1, int(os.getenv("YOUTUBE_DOWNLOAD_TIMEOUT_SECONDS", "300")))
    except ValueError:
        return 300


def get_output_filename(title):
    filename = secure_filename(title or "video")
    if not filename:
        filename = "video"
    return f"{filename}.mp4"

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app  # noqa: E402
from Blueprints.tools import youtube_downloads  # noqa: E402


class YouTubeDownloadsTests(unittest.TestCase):
    def test_validate_youtube_request_accepts_supported_qualities(self) -> None:
        for quality in ("1080p", "720p", "480p", "360p"):
            with self.subTest(quality=quality):
                youtube_downloads.validate_youtube_request(
                    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    quality,
                )

    def test_validate_youtube_request_rejects_unknown_quality(self) -> None:
        with self.assertRaisesRegex(ValueError, "Qualidade invalida"):
            youtube_downloads.validate_youtube_request(
                "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "1440p",
            )

    def test_buscar_video_uses_adaptive_stream_for_1080p(self) -> None:
        adaptive = FakeStream("adaptive-1080p")
        yt = FakeYouTube(
            filters={
                ("progressive", "1080p"): [],
                ("adaptive", "1080p"): [adaptive],
            },
        )

        self.assertIs(youtube_downloads.buscar_video(yt, "1080p"), adaptive)

    def test_buscar_audio_prefers_mp4_audio(self) -> None:
        mp4_audio = FakeStream("audio-mp4")
        fallback_audio = FakeStream("audio-webm")
        yt = FakeYouTube(
            filters={("audio_mp4", None): [mp4_audio]},
            audio_only=fallback_audio,
        )

        self.assertIs(youtube_downloads.buscar_audio(yt), mp4_audio)

    def test_download_route_redirects_to_standard_status_page(self) -> None:
        app = create_app()
        app.config.update(TESTING=True, CSRF_ENABLED=False)

        with tempfile.TemporaryDirectory() as temp_dir:
            app.instance_path = str(Path(temp_dir) / "instance")
            with app.test_client() as client:
                with patch.object(youtube_downloads, "save_and_submit_jobs") as save:
                    response = client.post(
                        "/tools/youtube-download/download",
                        data={
                            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                            "qualidade": "1080p",
                        },
                    )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/conversions/", response.headers["Location"])
        save.assert_called_once()
        job = save.call_args.args[0][0]
        self.assertEqual(job.tool_name, "youtube_download")
        self.assertEqual(job.output_filename, "youtube_1080p.mp4")
        self.assertEqual(job.runtime_options["qualidade"], "1080p")

    def test_convert_youtube_video_writes_output_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            download_temp = root / "download_temp"
            download_temp.mkdir()
            temp_source = download_temp / "download.mp4"
            temp_source.write_bytes(b"video")
            output_path = root / "job" / "output.mp4"

            with patch.object(
                youtube_downloads,
                "processar_download",
                return_value=(str(temp_source), "video.mp4", str(download_temp)),
            ):
                youtube_downloads.convert_youtube_video(
                    "youtube_url",
                    output_path,
                    {
                        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                        "qualidade": "720p",
                    },
                )

            self.assertEqual(output_path.read_bytes(), b"video")


class FakeStream:
    def __init__(self, name: str):
        self.name = name


class FakeQuery:
    def __init__(self, streams):
        self.streams = streams

    def order_by(self, _field):
        return self

    def desc(self):
        return self

    def first(self):
        return self.streams[0] if self.streams else None


class FakeStreams:
    def __init__(self, filters, audio_only=None):
        self.filters = filters
        self.audio_only = audio_only

    def filter(self, **kwargs):
        if kwargs.get("progressive"):
            key = ("progressive", kwargs.get("res"))
        elif kwargs.get("adaptive"):
            key = ("adaptive", kwargs.get("res"))
        elif kwargs.get("only_audio") and kwargs.get("file_extension") == "mp4":
            key = ("audio_mp4", None)
        else:
            key = ("unknown", None)
        return FakeQuery(self.filters.get(key, []))

    def get_audio_only(self):
        return self.audio_only


class FakeYouTube:
    def __init__(self, filters, audio_only=None):
        self.streams = FakeStreams(filters, audio_only)


if __name__ == "__main__":
    unittest.main()

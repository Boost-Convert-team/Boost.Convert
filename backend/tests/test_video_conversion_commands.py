import sys
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.services.convertions_services.conversion_rules.conversion_options import (
    get_conversion_options,
)
from Blueprints.services.convertions_services.videos import (
    mp4_to_gif_service,
    mp4_to_webm_service,
)


class VideoConversionCommandTests(unittest.TestCase):
    def test_mp4_to_gif_uses_safe_defaults_without_form_options(self) -> None:
        with patch.object(mp4_to_gif_service, "run_ffmpeg") as run_ffmpeg:
            mp4_to_gif_service.convert_mp4_gif("input.mp4", "output.gif", options={})

        command = run_ffmpeg.call_args.args[0]
        filter_argument = command[command.index("-filter_complex") + 1]
        self.assertEqual(command[command.index("-t") + 1], "10")
        self.assertLess(command.index("-t"), command.index("-i"))
        self.assertIn("fps=10", filter_argument)
        self.assertIn("scale='min(480,iw)':-2:flags=lanczos", filter_argument)
        self.assertIn("palettegen=stats_mode=diff", filter_argument)
        self.assertIn("paletteuse=dither=bayer:bayer_scale=5", filter_argument)
        self.assertIn("-an", command)

    def test_mp4_to_gif_honors_explicit_original_options(self) -> None:
        with patch.object(mp4_to_gif_service, "run_ffmpeg") as run_ffmpeg:
            mp4_to_gif_service.convert_mp4_gif(
                "input.mp4",
                "output.gif",
                options={"gif_fps": "original", "gif_width": "original", "gif_duration": "original"},
            )

        command = run_ffmpeg.call_args.args[0]
        filter_argument = command[command.index("-filter_complex") + 1]
        self.assertNotIn("-t", command)
        self.assertIn("[0:v]null,split", filter_argument)
        self.assertNotIn("fps=", filter_argument)
        self.assertNotIn("scale=480", filter_argument)
        self.assertNotIn(",scale=", filter_argument)

    def test_mp4_to_webm_uses_balanced_fast_vp9_defaults_without_form_options(self) -> None:
        with patch.object(mp4_to_webm_service, "run_ffmpeg") as run_ffmpeg:
            mp4_to_webm_service.convert_mp4_webm("input.mp4", "output.webm", options={})

        command = run_ffmpeg.call_args.args[0]
        self.assertEqual(command[command.index("-crf") + 1], "30")
        self.assertEqual(command[command.index("-deadline") + 1], "good")
        self.assertEqual(command[command.index("-cpu-used") + 1], "4")
        self.assertEqual(command[command.index("-row-mt") + 1], "1")
        self.assertEqual(command[command.index("-threads") + 1], "0")
        self.assertEqual(command[command.index("-b:a") + 1], "128k")

    def test_mp4_to_webm_honors_explicit_high_quality(self) -> None:
        with patch.object(mp4_to_webm_service, "run_ffmpeg") as run_ffmpeg:
            mp4_to_webm_service.convert_mp4_webm(
                "input.mp4",
                "output.webm",
                options={"video_quality": "high"},
            )

        command = run_ffmpeg.call_args.args[0]
        self.assertEqual(command[command.index("-crf") + 1], "24")
        self.assertEqual(command[command.index("-cpu-used") + 1], "3")

    def test_mp4_to_webm_falls_back_to_balanced_for_invalid_quality(self) -> None:
        with patch.object(mp4_to_webm_service, "run_ffmpeg") as run_ffmpeg:
            mp4_to_webm_service.convert_mp4_webm(
                "input.mp4",
                "output.webm",
                options={"video_quality": "invalid"},
            )

        command = run_ffmpeg.call_args.args[0]
        self.assertEqual(command[command.index("-crf") + 1], "30")
        self.assertEqual(command[command.index("-cpu-used") + 1], "4")

    def test_converter_pages_default_to_fast_video_options(self) -> None:
        gif_options = {
            option["name"]: option["default"]
            for option in get_conversion_options("/convert/mp4-to-gif")
        }
        webm_options = {
            option["name"]: option["default"]
            for option in get_conversion_options("/convert/mp4-to-webm")
        }

        self.assertEqual(gif_options["gif_fps"], "10")
        self.assertEqual(gif_options["gif_width"], "480")
        self.assertEqual(gif_options["gif_duration"], "10")
        self.assertEqual(webm_options["video_quality"], "balanced")


if __name__ == "__main__":
    unittest.main()

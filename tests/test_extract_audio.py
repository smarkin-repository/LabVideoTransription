from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import os
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import extract_audio


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class ExtractAudioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="audio tests ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def command(self, *args):
        return subprocess.run(args, check=True, capture_output=True).stdout

    def fixture(self, name="video with spaces.mkv", codec="pcm_s16le", tracks=1):
        target = self.root / name
        command = ["ffmpeg", "-v", "error", "-nostdin", "-f", "lavfi", "-i", "color=size=16x16:rate=10:duration=0.3"]
        for n in range(tracks):
            command += ["-f", "lavfi", "-i", f"sine=frequency={440 + n * 400}:duration=0.3"]
        command += ["-map", "0:v"]
        for n in range(tracks):
            command += ["-map", f"{n + 1}:a"]
        command += ["-c:v", "ffv1", "-c:a", codec]
        if codec == "vorbis":
            command += ["-strict", "experimental", "-ac", "2"]
        if tracks:
            command += ["-metadata:s:a:0", "language=rus", "-metadata:s:a:0", "title=First"]
        self.command(*command, str(target))
        return target

    def digest(self, path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def decoded(self, path, stream=0):
        return self.command("ffmpeg", "-v", "error", "-i", str(path), "-map", f"0:a:{stream}", "-f", "s16le", "-")

    def test_copy_audio_equality_no_video_provenance_and_no_overwrite(self):
        source = self.fixture()
        original = self.digest(source)
        destination = self.root / "meeting folder"
        result = extract_audio.extract_audio(source, destination)
        audio = Path(result["audio_file"])
        metadata = json.loads(self.command("ffprobe", "-v", "error", "-show_streams", "-of", "json", str(audio)))
        self.assertEqual([(s["codec_type"], s["codec_name"]) for s in metadata["streams"]], [("audio", "pcm_s16le")])
        self.assertEqual(self.decoded(source), self.decoded(audio))
        sidecar = destination / "input.audio-source.json"
        self.assertEqual(json.loads(sidecar.read_text())["source_file"], str(source.resolve()))
        saved = self.digest(audio), self.digest(sidecar)
        with self.assertRaisesRegex(extract_audio.ExtractionError, "перезапись"):
            extract_audio.extract_audio(source, destination)
        self.assertEqual(saved, (self.digest(audio), self.digest(sidecar)))
        self.assertEqual(original, self.digest(source))
        self.assertEqual(sorted(p.name for p in destination.iterdir()), ["input.audio-source.json", "input.wav"])

    def test_multitrack_requires_explicit_audio_ordinal(self):
        source = self.fixture(tracks=2)
        with self.assertRaisesRegex(extract_audio.ExtractionError, "0: index=1, codec=pcm_s16le, lang=rus, title=First"):
            extract_audio.extract_audio(source, self.root / "out")
        result = extract_audio.extract_audio(source, self.root / "out", 1)
        self.assertEqual(result["stream_index"], 2)
        self.assertEqual(self.decoded(source, 1), self.decoded(Path(result["audio_file"])))
        self.assertNotEqual(self.decoded(source, 0), self.decoded(Path(result["audio_file"])))

    def test_no_audio_and_invalid_selection(self):
        with self.assertRaisesRegex(extract_audio.ExtractionError, "нет аудиопотоков"):
            extract_audio.extract_audio(self.fixture(tracks=0), self.root / "out")
        source = self.fixture(name="audio.mkv")
        for selection in (-1, "0", 1):
            with self.subTest(selection=selection), self.assertRaises(extract_audio.ExtractionError):
                extract_audio.extract_audio(source, self.root / "out", selection)

    def test_invalid_file_missing_file_and_commands(self):
        source = self.root / "bad.mp4"
        source.write_bytes(b"not media")
        with self.assertRaisesRegex(extract_audio.ExtractionError, "ffprobe"):
            extract_audio.extract_audio(source)
        with self.assertRaisesRegex(extract_audio.ExtractionError, "не найден"):
            extract_audio.extract_audio(self.root / "missing.mp4")
        for missing in ("ffmpeg", "ffprobe"):
            with self.subTest(missing=missing), patch("extract_audio.shutil.which", side_effect=lambda name: None if name == missing else "/usr/local/bin/" + name):
                with self.assertRaisesRegex(extract_audio.ExtractionError, missing):
                    extract_audio.extract_audio(source)

    def test_codec_copy_containers(self):
        # Compare compressed packet payloads: streamcopy must not change audio data.
        codecs = (("aac", "m4a"), ("alac", "m4a"), ("libmp3lame", "mp3"),
                  ("libopus", "opus"), ("vorbis", "ogg"), ("flac", "flac"), ("ac3", "ac3"))
        for encoder, extension in codecs:
            with self.subTest(encoder=encoder):
                source = self.fixture(name=f"{encoder}.mkv", codec=encoder)
                result = extract_audio.extract_audio(source, self.root / encoder)
                target = Path(result["audio_file"])
                self.assertEqual(target.suffix, "." + extension)
                self.assertEqual(self.packet_hashes(source), self.packet_hashes(target))

    def packet_hashes(self, path):
        data = json.loads(self.command("ffprobe", "-v", "error", "-select_streams", "a:0", "-show_packets", "-show_data_hash", "sha256", "-of", "json", str(path)))
        return [packet["data_hash"] for packet in data["packets"]]

    def test_sidecar_conflict_and_failed_publication_do_not_overwrite(self):
        source = self.fixture()
        destination = self.root / "out"
        destination.mkdir()
        sidecar = destination / "input.audio-source.json"
        sidecar.write_text("keep me")
        with self.assertRaises(extract_audio.ExtractionError):
            extract_audio.extract_audio(source, destination)
        self.assertFalse((destination / "input.wav").exists())
        self.assertEqual(sidecar.read_text(), "keep me")
        sidecar.unlink()
        real_link = extract_audio.os.link
        def conflict(staging, target):
            if Path(target).name == "input.audio-source.json":
                sidecar.write_text("concurrent file")
            real_link(staging, target)
        with patch("extract_audio.os.link", side_effect=conflict), self.assertRaises(extract_audio.ExtractionError):
            extract_audio.extract_audio(source, destination)
        self.assertEqual(sidecar.read_text(), "concurrent file")
        self.assertFalse((destination / "input.wav").exists())
        self.assertEqual(list(destination.iterdir()), [sidecar])

    def test_mp4_aac_cli_end_to_end(self):
        source = self.root / "typical recording.mp4"
        destination = self.root / "meeting output"
        self.command(
            "ffmpeg", "-v", "error", "-nostdin",
            "-f", "lavfi", "-i", "color=size=16x16:rate=10:duration=0.3",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=0.3",
            "-c:v", "mpeg4", "-c:a", "aac", str(source),
        )
        original_hash = self.digest(source)
        script = Path(extract_audio.__file__).resolve()
        stdout = self.command(sys.executable, str(script), str(source), "--output-dir", str(destination))
        target = destination / "input.m4a"
        self.assertTrue(target.is_file())
        self.assertIn("Кодек: aac", stdout.decode())
        metadata = json.loads(self.command("ffprobe", "-v", "error", "-show_streams", "-of", "json", str(target)))
        self.assertEqual([(stream["codec_type"], stream["codec_name"]) for stream in metadata["streams"]], [("audio", "aac")])
        self.assertEqual(self.packet_hashes(source), self.packet_hashes(target))
        self.assertEqual(self.digest(source), original_hash)

    def test_cli_default_directory_and_offset_warning(self):
        source = self.fixture()
        metadata = extract_audio.probe(source, shutil.which("ffprobe"))
        metadata["format"]["start_time"] = "0.0"
        metadata["streams"][1]["start_time"] = "0.5"
        stdout, stderr = io.StringIO(), io.StringIO()
        previous = Path.cwd()
        try:
            os.chdir(self.root)
            with patch("extract_audio.probe", return_value=metadata), redirect_stdout(stdout), redirect_stderr(stderr):
                self.assertEqual(extract_audio.main([str(source)]), 0)
        finally:
            os.chdir(previous)
        self.assertTrue((self.root / "output" / source.stem / "input.wav").is_file())
        self.assertIn("Размер:", stdout.getvalue())
        self.assertIn("0.5 с", stderr.getvalue())
        self.assertIn("сверьте", stderr.getvalue())

    def test_ffmpeg_failure_cleans_only_temporary_files(self):
        source = self.fixture()
        destination = self.root / "out"
        metadata = extract_audio.probe(source, shutil.which("ffprobe"))
        with patch("extract_audio.probe", return_value=metadata), patch("extract_audio.run_command", side_effect=extract_audio.ExtractionError("conversion failed")):
            with self.assertRaisesRegex(extract_audio.ExtractionError, "conversion failed"):
                extract_audio.extract_audio(source, destination)
        self.assertEqual(list(destination.iterdir()), [])
        self.assertTrue(source.is_file())

    def test_unsupported_codec_and_time_offset(self):
        source = self.fixture(codec="pcm_s16be")
        with self.assertRaisesRegex(extract_audio.ExtractionError, "main.py"):
            extract_audio.extract_audio(source, self.root / "out")
        self.assertEqual(extract_audio.start_offset("1.2", "1.7"), "0.5")
        self.assertIsNone(extract_audio.start_offset(None, "1.7"))
        self.assertIsNone(extract_audio.start_offset("0", "NaN"))


if __name__ == "__main__":
    unittest.main()

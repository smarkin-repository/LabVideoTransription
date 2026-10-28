import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


PROJECT = Path(__file__).resolve().parents[1]


class TranscriptionOutputTests(unittest.TestCase):
    def run_transcription(self, transcript, folder):
        recording = folder / "input.mp4"
        recording.write_bytes(b"offline test; never uploaded")
        sdk = ModuleType("assemblyai")
        v2 = ModuleType("assemblyai.prerecorded.v2")
        sdk.Client = SimpleNamespace
        sdk.Settings = SimpleNamespace
        v2.TranscriptionConfig = SimpleNamespace
        transcribe = unittest.mock.Mock(return_value=transcript)
        v2.Transcriber = lambda **kwargs: SimpleNamespace(transcribe=transcribe)
        modules = {"assemblyai": sdk, "assemblyai.prerecorded.v2": v2}
        out, err = io.StringIO(), io.StringIO()
        code = None
        with patch.dict(sys.modules, modules), patch.dict(
            os.environ, {"ASSEMBLYAI_API_KEY": "offline-placeholder"}, clear=True
        ), patch.object(sys, "argv", [str(PROJECT / "main.py"), str(recording)]), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                runpy.run_path(str(PROJECT / "main.py"), run_name="__main__")
            except SystemExit as error:
                code = str(error.code)
        transcribe.assert_called_once_with(str(recording))
        return code, out.getvalue(), err.getvalue()

    def transcript(self, start=0, utterances=True):
        word = SimpleNamespace(speaker="A", start=start, end=1234,
                               text="PRIVATE_SPOKEN_CONTENT", confidence=0.97)
        utterance = SimpleNamespace(speaker="A", start=start, end=1234,
                                    text=word.text, confidence=0.96, words=[word])
        return SimpleNamespace(status="completed", id="offline-transcript-id",
                               language_code="ru", confidence=0.95,
                               text=word.text, words=[word],
                               utterances=[utterance] if utterances else [])

    def test_full_json_and_dialogue_are_saved_but_not_printed(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            speakers = {"A": {"person_id": "p1", "name": "Анна", "role": "ведущая"}}
            (folder / "input.speakers.json").write_text(json.dumps(speakers))
            code, out, err = self.run_transcription(self.transcript(), folder)
            self.assertIsNone(code)
            self.assertEqual(err, "")
            self.assertEqual(len(out.splitlines()), 5)
            self.assertNotIn("PRIVATE_SPOKEN_CONTENT", out)
            self.assertNotIn("offline-placeholder", out)
            data = json.loads((folder / "input.json").read_text())
            self.assertEqual(data["text"], "PRIVATE_SPOKEN_CONTENT")
            self.assertEqual(data["words"][0]["text"], data["text"])
            self.assertEqual(data["utterances"][0]["words"], data["words"])
            self.assertEqual(data["utterances"][0]["start_ms"], 0)
            self.assertEqual(json.loads((folder / "input.speakers.json").read_text()), speakers)
            self.assertEqual((folder / "input.dialogue.md").read_text(),
                             "[U000001 | 00:00:00.000–00:00:01.234] A:Анна: PRIVATE_SPOKEN_CONTENT\n")

    def test_conversion_failure_preserves_json_and_explains_local_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            code, out, err = self.run_transcription(self.transcript(start=-1), folder)
            self.assertIn("dialogue conversion failed", code)
            self.assertIn("transcribing the recording again is not required", code)
            self.assertTrue((folder / "input.json").is_file())
            self.assertTrue((folder / "input.speakers.json").is_file())
            self.assertFalse((folder / "input.dialogue.md").exists())
            self.assertNotIn("PRIVATE_SPOKEN_CONTENT", out + err + code)

    def test_text_without_segments_is_not_silently_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            code, out, err = self.run_transcription(self.transcript(utterances=False), folder)
            self.assertIn("would lose content", code)
            self.assertEqual(json.loads((folder / "input.json").read_text())["text"],
                             "PRIVATE_SPOKEN_CONTENT")
            self.assertFalse((folder / "input.dialogue.md").exists())


if __name__ == "__main__":
    unittest.main()

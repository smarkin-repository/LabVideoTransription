import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from assemblyai import Client, Settings
from assemblyai.prerecorded.v2 import Transcriber, TranscriptionConfig

from create_dialogue import create_dialogue

api_key = os.getenv("ASSEMBLYAI_API_KEY")
if not api_key:
    sys.exit("Missing ASSEMBLYAI_API_KEY environment variable.")

if len(sys.argv) != 2:
    sys.exit("Usage: python main.py VIDEO_FILE")

video_path = Path(sys.argv[1])
if not video_path.is_file():
    sys.exit(f"File not found: {video_path}")

# Upload, transcription, and polling all use our EU endpoint.
client = Client(
    settings=Settings(
        api_key=api_key,
        base_url="https://api.eu.assemblyai.com",
    )
)

config = TranscriptionConfig(
    speech_models=["universal-3-5-pro", "universal-2"],
    language_detection=True,
    speaker_labels=True,
)

try:
    speakers_path = video_path.with_suffix(".speakers.json")
    speakers = {}
    if speakers_path.exists():
        speakers = json.loads(speakers_path.read_text(encoding="utf-8"))
        if not isinstance(speakers, dict) or any(
            not isinstance(value, dict) for value in speakers.values()
        ):
            raise ValueError("Speakers file must map speaker labels to objects.")

    transcript = Transcriber(client=client, config=config).transcribe(
        str(video_path)
    )
    if transcript.status == "error":
        raise RuntimeError(transcript.error)

    def serialize_word(word):
        return {
            "speaker": word.speaker,
            "start_ms": word.start,
            "end_ms": word.end,
            "text": word.text,
            "confidence": word.confidence,
        }

    utterances = transcript.utterances or []
    for utterance in utterances:
        if utterance.speaker is not None:
            speakers.setdefault(utterance.speaker, {
                "person_id": "",
                "name": "",
                "role": "",
            })

    result = {
        "source_file": str(video_path),
        "transcript_id": transcript.id,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "language_code": transcript.language_code,
        "confidence": transcript.confidence,
        "transcription_settings": {
            "base_url": "https://api.eu.assemblyai.com",
            "speech_models": config.speech_models,
            "language_detection": config.language_detection,
            "speaker_labels": config.speaker_labels,
        },
        "speakers_file": speakers_path.name,
        "text": transcript.text or "",
        "words": [serialize_word(word) for word in transcript.words or []],
        "utterances": [
            {
                "speaker": utterance.speaker,
                "start_ms": utterance.start,
                "end_ms": utterance.end,
                "text": utterance.text,
                "confidence": utterance.confidence,
                "words": [serialize_word(word) for word in utterance.words or []],
            }
            for utterance in utterances
        ],
    }
    output_json = json.dumps(result, ensure_ascii=False, indent=2)
    output_path = video_path.with_suffix(".json")
    output_path.write_text(output_json + "\n", encoding="utf-8")
    speakers_path.write_text(
        json.dumps(speakers, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Transcription completed: {transcript.id}")
    print(f"Language: {transcript.language_code}; utterances: {len(utterances)}")
    print(f"Transcript JSON: {output_path}")
    print(f"Speaker names and roles: {speakers_path}")

    dialogue_path = video_path.with_suffix(".dialogue.md")
    try:
        create_dialogue(output_path, speakers_path, dialogue_path)
    except (OSError, ValueError, AttributeError, TypeError) as error:
        sys.exit(
            f"Transcript JSON and speakers were saved, but dialogue conversion failed: {error}\n"
            "Fix the conversion issue and run create_dialogue.py locally; "
            "transcribing the recording again is not required."
        )
    print(f"Dialogue: {dialogue_path}")
except Exception as error:
    sys.exit(f"Transcription failed: {error}")

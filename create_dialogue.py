"""Convert a transcript and speaker names to a Markdown dialogue offline."""

import argparse
import json
from pathlib import Path


def format_timestamp(value, field, utterance_id):
    if value is None:
        return "??:??:??.???"
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{utterance_id}: {field} must be a non-negative integer in milliseconds or null.")
    seconds, milliseconds = divmod(value, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


def create_dialogue(transcript_path, speakers_path, output_path, short=False):
    transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    speakers = json.loads(speakers_path.read_text(encoding="utf-8"))
    utterances = transcript.get("utterances")
    if not isinstance(utterances, list):
        raise ValueError("Transcript must contain an utterances array.")
    if not isinstance(speakers, dict):
        raise ValueError("Speakers file must contain an object.")

    lines = []
    for index, utterance in enumerate(utterances, start=1):
        utterance_id = f"U{index:06d}"
        start_ms = utterance.get("start_ms")
        end_ms = utterance.get("end_ms")
        start = format_timestamp(start_ms, "start_ms", utterance_id)
        end = format_timestamp(end_ms, "end_ms", utterance_id)
        if start_ms is not None and end_ms is not None and end_ms < start_ms:
            raise ValueError(f"{utterance_id}: end_ms must be greater than or equal to start_ms.")
        label = utterance.get("speaker") or "?"
        participant = speakers.get(label, {})
        name = participant.get("name") or "Неизвестный"
        # Keep each utterance on one line, even if the input contains newlines.
        name = " ".join(name.split())
        text = " ".join((utterance.get("text") or "").split())
        prefix = name if short else f"{label}:{name}"
        lines.append(f"[{utterance_id} | {start}–{end}] {prefix}: {text}")

    # Blank lines preserve separate dialogue paragraphs in Markdown viewers.
    output_path.write_text("\n\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return len(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("transcript", type=Path, help="Transcript JSON file")
    parser.add_argument("--speakers", type=Path, help="Defaults to <transcript>.speakers.json")
    parser.add_argument("-o", "--output", type=Path, help="Defaults to <transcript>.dialogue.md")
    parser.add_argument("--short", action="store_true", help="Omit speaker labels, keeping utterance IDs and timestamps")
    args = parser.parse_args()
    speakers_path = args.speakers or args.transcript.with_suffix(".speakers.json")
    output_path = args.output or args.transcript.with_suffix(".dialogue.md")
    if output_path.resolve() in {args.transcript.resolve(), speakers_path.resolve()}:
        parser.error("Output must differ from the input files.")
    try:
        count = create_dialogue(args.transcript, speakers_path, output_path, short=args.short)
    except (OSError, ValueError, AttributeError, TypeError) as error:
        parser.exit(1, f"Could not create dialogue: {error}\n")
    print(f"Saved {count} utterances to: {output_path}")


if __name__ == "__main__":
    main()

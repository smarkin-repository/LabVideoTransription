"""Read selected utterances and their context from the current Markdown transcript."""

import argparse
from pathlib import Path
import re


TIMESTAMP = r"(?:\d{2,}:\d{2}:\d{2}\.\d{3}|\?\?:\?\?:\?\?\.\?\?\?)"
HEADER = re.compile(
    rf"^\[((?:[^\s\[\]|:]+:)?U\d{{6,}}) \| {TIMESTAMP}–{TIMESTAMP}\] [^\r\n]+:",
    re.MULTILINE,
)


def select_dialogue(source, requested_ids, context=2):
    """Return unchanged preamble and groups of unchanged Markdown utterance blocks."""
    if context < 0:
        raise ValueError("Context must be zero or greater.")
    matches = list(HEADER.finditer(source))
    if not matches:
        raise ValueError("No utterance IDs with dialogue timestamps found in this Markdown file.")
    positions = {}
    for index, match in enumerate(matches):
        utterance_id = match.group(1)
        if utterance_id in positions:
            raise ValueError(f"Duplicate utterance ID: {utterance_id}.")
        positions[utterance_id] = index
    missing = list(dict.fromkeys(item for item in requested_ids if item not in positions))
    if missing:
        raise ValueError(f"Utterance IDs not found: {', '.join(missing)}.")
    if not requested_ids:
        raise ValueError("Select at least one utterance ID.")

    included = set()
    for utterance_id in requested_ids:
        index = positions[utterance_id]
        included.update(range(max(0, index - context), min(len(matches), index + context + 1)))

    groups = []
    for index in sorted(included):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        block = source[matches[index].start():end]
        if not groups or index != groups[-1][-1][0] + 1:
            groups.append([])
        groups[-1].append((index, matches[index].group(1), block))
    return source[:matches[0].start()], groups


def render_selection(path, requested_ids, context=2):
    # Preserve line endings and all current edits; never consult the original JSON.
    with path.open(encoding="utf-8", newline="") as source_file:
        source = source_file.read()
    preamble, groups = select_dialogue(source, requested_ids, context)
    included_ids = [item[1] for group in groups for item in group]
    header = (
        "# Выборка из текущей транскрипции\n\n"
        f"Файл: {path}\n"
        f"Запрошены ID: {', '.join(dict.fromkeys(requested_ids))}\n"
        f"Включены ID: {', '.join(included_ids)}\n"
        f"Контекст: до {context} соседних реплик с каждой стороны.\n\n"
        "Это адресная выборка, а не полная транскрипция. Остальные реплики не показаны; "
        "ограничения и неясности исходного документа продолжают действовать.\n\n"
    )
    if preamble:
        header += "## Вступление исходного документа\n\n" + preamble
        if not header.endswith("\n"):
            header += "\n"
        header += "\n"
    header += "## Выбранные реплики\n\n"
    sections = ["".join(item[2] for item in group) for group in groups]
    return header + "\n\n--- Пропущены промежуточные реплики ---\n\n".join(sections)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Current Markdown transcript")
    parser.add_argument("ids", nargs="+", help="Utterance IDs, for example U000007 or Zoom:U000010")
    parser.add_argument("--context", type=int, default=2, help="Neighboring utterances on each side (default: 2)")
    args = parser.parse_args()
    try:
        result = render_selection(args.path, args.ids, args.context)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Could not read dialogue selection: {error}\n")
    print(result, end="")


if __name__ == "__main__":
    main()

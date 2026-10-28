from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from read_dialogue import render_selection, select_dialogue


def block(index, text=None):
    return f"[U{index:06d} | 00:00:00.000–00:00:01.234] A:Имя: {text or f'Реплика {index}'}\n\n"


class ReadDialogueTests(unittest.TestCase):
    def setUp(self):
        self.source = "".join(block(index) for index in range(1, 9))

    def ids(self, groups):
        return [[item[1] for item in group] for group in groups]

    def test_multiple_ids_remain_in_source_order(self):
        _, groups = select_dialogue(self.source, ["U000007", "U000002"], 0)
        self.assertEqual(self.ids(groups), [["U000002"], ["U000007"]])

    def test_context_at_both_boundaries(self):
        _, groups = select_dialogue(self.source, ["U000001", "U000008"], 2)
        self.assertEqual(self.ids(groups), [
            ["U000001", "U000002", "U000003"],
            ["U000006", "U000007", "U000008"],
        ])

    def test_overlap_and_repeated_requests_have_no_duplicate_blocks(self):
        _, groups = select_dialogue(self.source, ["U000003", "U000004", "U000003"], 2)
        self.assertEqual(self.ids(groups), [[f"U{index:06d}" for index in range(1, 7)]])

    def test_source_qualified_ids_are_distinct_and_keep_context(self):
        assembly = block(1, "Версия AssemblyAI").replace("[U000001", "[AssemblyAI:U000001")
        zoom = block(1, "Версия Zoom").replace("[U000001", "[Zoom:U000001")
        source = block(1) + assembly + zoom + block(2)
        _, groups = select_dialogue(source, ["Zoom:U000001"], 1)
        self.assertEqual(self.ids(groups), [["AssemblyAI:U000001", "Zoom:U000001", "U000002"]])
        self.assertEqual("".join(item[2] for item in groups[0]), assembly + zoom + block(2))
        _, groups = select_dialogue(source, ["U000001", "AssemblyAI:U000001"], 0)
        self.assertEqual(self.ids(groups), [["U000001", "AssemblyAI:U000001"]])
        with self.assertRaisesRegex(ValueError, "Duplicate utterance ID: Zoom:U000001"):
            select_dialogue(source + zoom, ["Zoom:U000001"], 0)

    def test_cli_accepts_source_qualified_ids(self):
        script = Path(__file__).resolve().parents[1] / "read_dialogue.py"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dialogue.md"
            path.write_text(block(1).replace("[U000001", "[Zoom:U000001"), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(script), str(path), "Zoom:U000001", "--context", "0"],
                capture_output=True, text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Запрошены ID: Zoom:U000001", result.stdout)
        self.assertIn("[Zoom:U000001 |", result.stdout)

    def test_preamble_multiline_diff_and_current_edits_are_preserved(self):
        preamble = "# Встреча\n\nИсточник: Zoom. Шкала смещена на 5 секунд.\nНеясность Q-1 не разрешена.\n\n"
        current = block(1, "Исправленное по записи слово.") + "Продолжение реплики.\n```diff\n- старое\n+ новое\n```\n\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "03 — Полная транскрипция.md"
            path.write_text(preamble + current + block(2), encoding="utf-8")
            path.with_suffix(".json").write_text('{"text": "Ошибочная старая версия"}', encoding="utf-8")
            result = render_selection(path, ["U000001"], 0)
        self.assertIn(preamble, result)
        self.assertTrue(result.endswith(current))
        self.assertNotIn("Ошибочная старая версия", result)
        self.assertIn("а не полная транскрипция", result)
        self.assertIn("Запрошены ID: U000001", result)
        self.assertIn("Включены ID: U000001", result)

    def test_gaps_are_explicit_and_source_blocks_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dialogue.md"
            path.write_text(self.source, encoding="utf-8")
            result = render_selection(path, ["U000001", "U000008"], 0)
        self.assertIn("Пропущены промежуточные реплики", result)
        self.assertIn(block(1), result)
        self.assertTrue(result.endswith(block(8)))
        self.assertNotIn(block(2), result)

    def test_selection_errors(self):
        cases = [
            (self.source, ["U999999"], 0, "not found"),
            ("No markers", ["U000001"], 0, "No utterance IDs"),
            (block(1) + block(1), ["U000001"], 0, "Duplicate"),
            (self.source, ["U000001"], -1, "zero or greater"),
        ]
        for source, requested, context, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                select_dialogue(source, requested, context)

    def test_cli_errors_do_not_print_partial_output(self):
        script = Path(__file__).resolve().parents[1] / "read_dialogue.py"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dialogue.md"
            path.write_text(self.source, encoding="utf-8")
            for arguments in [["U000001", "U999999"], ["U000001", "--context", "-1"]]:
                with self.subTest(arguments=arguments):
                    result = subprocess.run([sys.executable, str(script), str(path), *arguments], capture_output=True, text=True)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, "")
                    self.assertIn("Could not read dialogue selection:", result.stderr)


if __name__ == "__main__":
    unittest.main()

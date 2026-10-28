"""Extract one audio stream without decoding or re-encoding it."""

import argparse
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


class ExtractionError(Exception):
    """An actionable extraction failure."""


CODEC_EXTENSIONS = {
    "aac": "m4a", "alac": "m4a", "mp3": "mp3", "opus": "opus",
    "vorbis": "ogg", "flac": "flac", "ac3": "ac3",
    "pcm_u8": "wav", "pcm_s16le": "wav", "pcm_s24le": "wav",
    "pcm_s32le": "wav", "pcm_s64le": "wav", "pcm_f32le": "wav",
    "pcm_f64le": "wav", "pcm_alaw": "wav", "pcm_mulaw": "wav",
}
TIME_NOTE = (
    "После извлечения сверьте шкалу времени аудио с исходной записью: "
    "перенос в другой контейнер может изменить начальные метки времени."
)


def run_command(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise ExtractionError(f"Не найдена команда {command[0]}. Установите FFmpeg (ffmpeg и ffprobe).") from exc
    except OSError as exc:
        raise ExtractionError(f"Не удалось запустить {command[0]}: {exc}") from exc
    if result.returncode:
        detail = result.stderr.strip()[-2000:]
        raise ExtractionError(f"Ошибка {Path(command[0]).name}: {detail or 'не удалось обработать файл'}")
    return result.stdout


def probe(source, ffprobe):
    try:
        metadata = json.loads(run_command([
            ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(source),
        ]))
        if not isinstance(metadata, dict) or not isinstance(metadata.get("streams"), list):
            raise ValueError("нет списка потоков")
        return metadata
    except (ValueError, TypeError) as exc:
        raise ExtractionError(f"Некорректный ответ ffprobe: {exc}") from exc


def stream_description(ordinal, stream):
    tags = stream.get("tags") or {}
    return (f"  {ordinal}: index={stream.get('index')}, codec={stream.get('codec_name', '?')}, "
            f"lang={tags.get('language', '—')}, title={tags.get('title', '—')}")


def start_offset(format_start, audio_start):
    try:
        offset = Decimal(str(audio_start)) - Decimal(str(format_start))
        return str(offset) if offset.is_finite() else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def extract_audio(source, output_dir=None, audio_stream=None):
    source = Path(source).expanduser().resolve()
    if not source.is_file():
        raise ExtractionError(f"Файл не найден: {source}")
    if audio_stream is not None and (isinstance(audio_stream, bool) or not isinstance(audio_stream, int) or audio_stream < 0):
        raise ExtractionError("--audio-stream должен быть целым числом от 0 (номер среди аудиопотоков).")
    commands = {}
    for name in ("ffmpeg", "ffprobe"):
        commands[name] = shutil.which(name)
        if commands[name] is None:
            raise ExtractionError(f"Не найдена команда {name}. Установите FFmpeg (ffmpeg и ffprobe).")
    metadata = probe(source, commands["ffprobe"])
    streams = [stream for stream in metadata["streams"] if stream.get("codec_type") == "audio"]
    if not streams:
        raise ExtractionError("В файле нет аудиопотоков.")
    if len(streams) > 1 and audio_stream is None:
        listing = "\n".join(stream_description(n, stream) for n, stream in enumerate(streams))
        raise ExtractionError("Найдено несколько аудиопотоков. Выберите --audio-stream N "
                              "(номер среди аудио, от 0); остальные потоки не войдут в результат:\n" + listing)
    ordinal = 0 if audio_stream is None else audio_stream
    if ordinal >= len(streams):
        raise ExtractionError(f"Аудиопоток {ordinal} отсутствует; доступны номера 0–{len(streams) - 1}.")
    selected = streams[ordinal]
    codec = selected.get("codec_name", "unknown")
    extension = CODEC_EXTENSIONS.get(codec)
    if extension is None:
        raise ExtractionError(f"Кодек {codec!r} не поддерживается для автоматического извлечения. "
                              "Извлеките аудио вручную в совместимый контейнер с -c:a copy "
                              "или передайте исходное видео напрямую в main.py.")
    index = selected.get("index")
    if not isinstance(index, int) or index < 0:
        raise ExtractionError("ffprobe не сообщил корректный абсолютный индекс аудиопотока.")
    destination = Path(output_dir) if output_dir is not None else Path("output") / source.stem
    destination = destination.expanduser().resolve()
    audio_path = destination / f"input.{extension}"
    sidecar_path = destination / "input.audio-source.json"
    for target in (audio_path, sidecar_path):
        if os.path.lexists(target):
            raise ExtractionError(f"Файл уже существует, перезапись запрещена: {target}")
    format_start = (metadata.get("format") or {}).get("start_time")
    audio_start = selected.get("start_time")
    offset = start_offset(format_start, audio_start)
    provenance = {
        "source_file": str(source), "audio_file": str(audio_path), "codec": codec,
        "audio_stream_ordinal": ordinal, "stream_index": index,
        "format_start_time": format_start, "audio_start_time": audio_start,
        "audio_offset_seconds": offset, "timing_note": TIME_NOTE,
    }
    published = []
    try:
        destination.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".extract-audio-", dir=destination) as temporary:
            temporary = Path(temporary)
            temporary_audio = temporary / audio_path.name
            temporary_sidecar = temporary / sidecar_path.name
            run_command([
                commands["ffmpeg"], "-v", "error", "-nostdin", "-n", "-i", str(source),
                "-map", f"0:{index}", "-vn", "-c:a", "copy", str(temporary_audio),
            ])
            if not temporary_audio.is_file() or not temporary_audio.stat().st_size:
                raise ExtractionError("FFmpeg не создал непустой аудиофайл.")
            temporary_sidecar.write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            try:
                # Hard links publish complete files atomically and fail if a target exists.
                for staging, target in ((temporary_audio, audio_path), (temporary_sidecar, sidecar_path)):
                    os.link(staging, target)
                    published.append((staging, target))
            except OSError:
                for staging, target in reversed(published):
                    try:
                        if os.path.samestat(staging.stat(), target.stat()):
                            target.unlink()
                    except FileNotFoundError:
                        pass
                raise
    except OSError as exc:
        raise ExtractionError(f"Не удалось сохранить результат без перезаписи: {exc}") from exc
    return {**provenance, "input_bytes": source.stat().st_size, "output_bytes": audio_path.stat().st_size}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--audio-stream", type=int, help="номер среди аудиопотоков, начиная с 0")
    args = parser.parse_args(argv)
    try:
        result = extract_audio(args.video, args.output_dir, args.audio_stream)
    except ExtractionError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    print(f"Вход: {result['source_file']}\nВыход: {result['audio_file']}")
    print(f"Кодек: {result['codec']}; аудиопоток: {result['audio_stream_ordinal']} (index={result['stream_index']})")
    print(f"Размер: {result['input_bytes']} → {result['output_bytes']} байт")
    if result["audio_offset_seconds"] is not None and Decimal(result["audio_offset_seconds"]) != 0:
        print(f"Внимание: исходное смещение аудио относительно начала контейнера: {result['audio_offset_seconds']} с. {TIME_NOTE}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

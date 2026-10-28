# Установка и настройка

Здесь описана настройка среды для Linux и macOS. Назначение проекта и состав файлов — в [README.md](README.md), рабочий процесс — в [AGENTS.md](AGENTS.md).

## Получить проект

Если проект уже скачан, использовать его папку. При наличии Git можно клонировать репозиторий:

```bash
git clone https://github.com/smarkin-repository/LabVideoTransription.git
cd LabVideoTransription
```

Копия проекта должна включать скрытую папку `.agents/`. Зависимости перечислены в [requirements.txt](requirements.txt); пример имени переменной для API-ключа — в [.env.example](.env.example).

## Настроить Python и библиотеки

Установку выполнить один раз на каждом компьютере. Ниже команды для терминала **Bash или zsh**. Пути в кавычках заменить на свои; команды проекта выполнять из его корня, где находятся `main.py` и `create_dialogue.py`.

**До создания `.venv` проверить, нет ли готового окружения.** Если проект уже работает на этом компьютере, повторную установку и создание окружения пропустить, перейти к проверке импортов. Если папка проекта перенесена с другого компьютера вместе с `.venv`, сначала переименовать чужую `.venv`, например в свободное имя `.venv.previous`, затем выполнять команды создания новой. Готовое окружение между Linux и macOS не переносить.

### Что потребуется

| Компонент | Для чего нужен |
|---|---|
| Python 3 и модуль `venv` | Запуск скриптов в отдельном окружении `.venv` |
| `pip` | Установка Python-библиотеки и её зависимостей |
| `assemblyai==1.6.1` | Обращение к сервису распознавания из `main.py` |
| FFmpeg и FFprobe | Извлечение аудиодорожки из видео; для готового аудиофайла не требуются |
| Аккаунт AssemblyAI, API-ключ и доступ в интернет | Отправка записи и получение транскрипции |
| Копия проекта, включая скрытую папку `.agents/` | Скрипты и навыки корректуры и подготовки конспекта |
| Редактор Markdown и проигрыватель записи | Ручная проверка текста и спорных фрагментов |

В текущем рабочем окружении проверены **Python 3.14.4 и AssemblyAI SDK 1.6.1**. Ниже для macOS устанавливается ветка Python 3.14, для Ubuntu/Debian — Python 3 из репозитория дистрибутива. Версия `assemblyai` зафиксирована, потому что `main.py` использует конкретные импорты SDK. Остальные Python-зависимости SDK установит `pip`; `create_dialogue.py` и `read_dialogue.py` используют только стандартную библиотеку Python. [Документация SDK](https://github.com/assemblyai/assemblyai-python-sdk).

Распознавание выполняется в облаке. Локальные модели, GPU, CUDA и Node.js не требуются. Для предварительного извлечения аудио из видео установить FFmpeg и FFprobe по разделу ниже; готовый аудиофайл можно обрабатывать без них.

### Linux: Ubuntu / Debian

Установить Python, поддержку виртуальных окружений, `pip` и сертификаты для HTTPS:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip ca-certificates
python3 --version
```

В других дистрибутивах установить соответствующие пакеты через их пакетный менеджер; команды `apt` относятся к Ubuntu/Debian. Последующие команды проекта одинаковы. [Настройка Python в Ubuntu](https://ubuntu.com/developers/docs/howto/python-setup/).

Перейти в папку проекта и создать окружение:

```bash
cd "/путь/к/LabVideoTransription"
python3 -m venv .venv
```

После этого перейти к разделу «Общие шаги» ниже.

### macOS

Если Homebrew ещё не установлен, выполнить команду из [официальной инструкции Homebrew](https://brew.sh/):

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Дождаться завершения установки и выполнить показанные установщиком **Next steps**, чтобы добавить `brew` в `PATH`. Если установщик просит Command Line Tools, выполнить `xcode-select --install` и завершить установку в открывшемся окне.

Если после установки команда `brew` не находится, для текущего терминала выполнить подходящую строку:

```bash
# Apple Silicon: M1, M2, M3 и более новые
eval "$(/opt/homebrew/bin/brew shellenv)"
```

```bash
# Mac с процессором Intel и Homebrew в /usr/local
eval "$(/usr/local/bin/brew shellenv)"
```

Для следующих запусков терминала добавить соответствующую строку в файл настройки оболочки: обычно `~/.zprofile` для zsh или `~/.bash_profile` для Bash. Выполненные **Next steps** обычно уже включают эту настройку. Актуальные требования к macOS и поддержке Intel приведены в [документации Homebrew](https://docs.brew.sh/Installation). Если система не подходит для Homebrew, установить Python 3.14 через [официальный установщик Python для macOS](https://www.python.org/downloads/macos/), затем использовать ту же команду `python3.14 -m venv .venv`.

Установить Python и создать окружение проекта:

```bash
brew install python@3.14
python3.14 --version
cd "/путь/к/LabVideoTransription"
python3.14 -m venv .venv
```

Версионное имя `python3.14` позволяет явно выбрать установленный интерпретатор. [Пакет Python 3.14 в Homebrew](https://formulae.brew.sh/formula/python@3.14).

### Общие шаги: установить библиотеки и проверить скрипты

Находясь в корне проекта, выполнить:

```bash
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
.venv/bin/python --version
```

Устанавливать библиотеки в `.venv`, без `sudo pip`. Окружение создаётся заново на каждом новом компьютере и использует установленный на нём Python. [Устройство виртуальных окружений Python](https://docs.python.org/3/library/venv.html).

Проверить импорты, которые нужны `main.py`, без отправки записи в сервис:

```bash
.venv/bin/python -c 'from assemblyai import Client, Settings; from assemblyai.prerecorded.v2 import Transcriber, TranscriptionConfig; from importlib.metadata import version; print("AssemblyAI:", version("assemblyai")); print("Импорты main.py: OK")'
.venv/bin/python create_dialogue.py --help
.venv/bin/python read_dialogue.py --help
```

Ожидаемый результат: `pip check` сообщает `No broken requirements found`, проверка импортов выводит версию и `OK`, а конвертер — справку. У `main.py` флага `--help` нет: ему передаётся только путь к записи.

Во всех командах ниже используется явный путь `.venv/bin/python`, поэтому активировать окружение не обязательно. Если удобнее писать `python`, можно выполнить `source .venv/bin/activate`; для выхода — `deactivate`.

Локальные проверки конвертации, краткого вывода и адресного чтения запускаются без API-ключа и без сетевых запросов:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

### Задать API-ключ AssemblyAI

Получить ключ в аккаунте AssemblyAI. В том же терминале, из которого будет запускаться `main.py`, ввести ключ без отображения на экране:

```bash
printf 'Введите API-ключ AssemblyAI: '
read -r -s ASSEMBLYAI_API_KEY
printf '\n'
export ASSEMBLYAI_API_KEY
```

После вставки ключа нажать Enter. Проверить наличие переменной, не выводя её значение:

```bash
.venv/bin/python -c 'import os; print("API-ключ задан" if os.environ.get("ASSEMBLYAI_API_KEY") else "API-ключ не задан")'
```

Ключ действует в текущем терминале и запускаемых из него процессах. В новом терминале ввод повторить. Активация `.venv` не задаёт ключ, а существующий `.env` скрипт автоматически не читает.

## Установить FFmpeg для работы с видео

В Ubuntu/Debian:

```bash
sudo apt update
sudo apt install -y ffmpeg
```

В macOS с настроенным Homebrew:

```bash
brew install ffmpeg
```

Проверить, что обе команды доступны в терминале:

```bash
ffmpeg -version
ffprobe -version
.venv/bin/python extract_audio.py --help
```

FFmpeg устанавливается как системная программа, а не через `pip`. `extract_audio.py` использует стандартную библиотеку Python; дополнительных Python-пакетов нет. FFprobe определяет дорожки и кодек, FFmpeg копирует выбранную звуковую дорожку без повторного сжатия. [Документация FFmpeg](https://ffmpeg.org/ffmpeg.html).

После установки следовать развилке «готовое аудио / видео» в [AGENTS.md](AGENTS.md). Извлечение выполняется локально, без API-ключа и оплаты AssemblyAI.

## Настроить Zoom, если используется его транскрипция

Для облачной транскрипции нужны тариф Pro, Business, Education или Enterprise, облачная запись и включённая функция создания транскрипции. В веб-портале Zoom открыть настройки записи, включить **Cloud recording**, затем **Create audio transcript** в расширенных настройках облачной записи и сохранить изменения. Сделать это до встречи. Если настройка заблокирована администратором, её меняет администратор. [Настройка Zoom](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0065911).

После обработки скачать запись и файл транскрипции `.vtt` с таймкодами из раздела **Recordings & Transcripts → Cloud recordings**. Проверить язык: для русскоязычной встречи выбрать русский; при необходимости воспользоваться **Change Language** для повторного распознавания. [Работа с транскрипцией Zoom](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0064927).

Не подменять полную расшифровку автоматическим резюме встречи. Для этого процесса нужны сами реплики с таймкодами.

## Если запуск не получился

| Сообщение или ситуация | Что проверить |
|---|---|
| `python3: command not found` или `python3.14: command not found` | Выполнена ли установка Python и настроен ли `PATH`; на macOS — выполнены ли Next steps Homebrew. |
| `No module named venv` или ошибка `ensurepip` при создании окружения | В Ubuntu/Debian установить `python3-venv`; при выборе отдельной версии Python нужен соответствующий ей пакет `venv`. |
| `No module named assemblyai` | Установить SDK командой `.venv/bin/python -m pip install "assemblyai==1.6.1"` и запускать скрипт тем же Python. |
| Не находится `assemblyai.prerecorded.v2`, `Client` или `Settings` | Проверить версию через `.venv/bin/python -m pip show assemblyai`; использовать указанную выше версию SDK. |
| `externally-managed-environment` при установке пакетов | Установка попала в системный Python. Использовать `.venv/bin/python -m pip`, а не системный `pip`. |
| `Missing ASSEMBLYAI_API_KEY environment variable.` | Задать и экспортировать ключ в том же терминале. |
| `ffmpeg` или `ffprobe` не найден | Установить FFmpeg и проверить доступность обеих команд в `PATH`. |
| `File not found` | Проверить путь к записи и текущую папку; пути с пробелами заключать в кавычки. |
| Ошибка авторизации или лимита сервиса | Проверить ключ, доступ аккаунта и лимиты AssemblyAI. Повторная установка Python такую ошибку не исправляет. |

## После настройки

Среда готова, если импорты и локальные тесты проходят, а переменная `ASSEMBLYAI_API_KEY` задана в терминале, из которого будет запускаться распознавание. Для работы с видео также должны быть доступны FFmpeg и FFprobe. Локальное извлечение аудио, конвертация JSON и адресное чтение не требуют ключа или интернета.

Далее следовать [рабочему процессу в AGENTS.md](AGENTS.md). При повторной работе на том же компьютере заново устанавливать среду не требуется.

Команды относятся к текущим скриптам проекта. Сведения о сервисах проверены по документации 28 октября 2026 года; названия пунктов интерфейса и условия тарифов могут меняться.

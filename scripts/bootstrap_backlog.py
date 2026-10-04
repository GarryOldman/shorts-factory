"""Создаёт в GitHub метки, эпики и задачи начального бэклога (через gh CLI).

Запуск (один раз, нужен `gh auth login`):
    python scripts/bootstrap_backlog.py --repo GarryOldman/shorts [--project 1] [--dry-run]

Первым создаётся issue #1 (каркас репозитория) — номер issue == номер SF-N.
"""

import argparse
import subprocess
import urllib.parse
from dataclasses import dataclass, field

LABELS = {
    "epic": "5319e7",
    "task": "0e8a16",
    "spike": "fbca04",
    "priority:mvp": "d93f0b",
    "priority:later": "c5def5",
}

TASK_FOOTER = (
    "\n\n## Процесс\n"
    "Ветка `SF-<номер этой issue>-slug` от master, TDD (тест отдельным коммитом раньше кода), "
    "коммиты `[SF-N] по-русски`, один PR с `Closes #N`, ревью агентом `reviewer`."
)


@dataclass(frozen=True)
class Task:
    title: str
    desc: str
    accept: tuple[str, ...]
    labels: tuple[str, ...] = ("task", "priority:mvp")


@dataclass(frozen=True)
class Epic:
    title: str
    goal: str
    tasks: tuple[Task, ...] = field(default_factory=tuple)
    label: str = "priority:mvp"


SCAFFOLD = Task(
    "Каркас репозитория: процесс, CI, шаблоны, агент-ревьюер",
    "pyproject (ruff, pytest, покрытие 80%), CI, шаблоны issue/PR, CONTRIBUTING, CLAUDE.md, reviewer.",
    ("CI зелёный на ветке SF-1-process-scaffolding", "PR смержен в master"),
)

EPICS = (
    Epic(
        "Основа: конфиг, хранилище, ingest, оркестратор, CLI",
        "Минимальный каркас пайплайна, на который навешиваются этапы анализа и рендера. "
        "Без Celery/Redis на старте: этапы идемпотентны, артефакты кешируются на диск.",
        (
            Task(
                "Конфигурация: pydantic-settings, yaml, пути, секреты из .env",
                "Типизированный конфиг, валидация путей, секреты только локально.",
                ("Невалидный конфиг даёт понятную ошибку", "Секреты не попадают в логи и git"),
            ),
            Task(
                "Ingest из папки: сканирование, ffprobe-валидация, нормализация",
                "Берём идеи из legacy ingest.py: VFR→CFR, ограничение высоты, проверка места на диске.",
                (
                    "Битые/неподдерживаемые файлы отклоняются с причиной",
                    "Повторный ingest идемпотентен",
                ),
            ),
            Task(
                "Хранилище метаданных: SQLite (источники, этапы, кандидаты, оценки)",
                "Repository-слой, миграции, интерфейс через Protocol.",
                ("CRUD покрыт тестами на in-memory БД", "Миграции применяются с нуля"),
            ),
            Task(
                "Оркестратор пайплайна: этапы, кеш артефактов, возобновление",
                "Последовательность этапов, статус каждого, пропуск готовых, retry с backoff.",
                (
                    "Падение на этапе N не теряет результаты 1..N-1",
                    "Повторный запуск продолжает с места сбоя",
                ),
            ),
            Task(
                "CLI: shorts process <folder>, shorts review",
                "Точки входа: обработка папки и вывод кандидатов для ручного просмотра.",
                ("Команды документированы в README", "Коды возврата и ошибки читаемы"),
            ),
        ),
    ),
    Epic(
        "Понимание длинного видео: транскрипт, сигналы, тематические блоки",
        "Структурное представление длинного видео, из которого можно выбирать моменты.",
        (
            Task(
                "Транскрибация faster-whisper: word timestamps, чанки, кеш, GPU/CPU",
                "Длинные файлы режутся на чанки с перекрытием, результат склеивается.",
                (
                    "Тайминги слов монотонны на стыках чанков",
                    "Результат кешируется по хешу файла и модели",
                ),
            ),
            Task(
                "Сигналы: смена сцен, энергия аудио, паузы",
                "PySceneDetect + аудио-энергия + детекция тишины (из legacy analyze.py).",
                ("Каждый сигнал — чистая функция с тестами на синтетике",),
            ),
            Task(
                "Сегментация транскрипта: предложения и тематические блоки",
                "Границы предложений и смены темы (embeddings / TextTiling) — основа для границ клипов.",
                ("Блоки не режут предложения", "Параметры порога вынесены в конфиг"),
            ),
        ),
    ),
    Epic(
        "Выбор логических моментов (ключевое качество)",
        "Из длинного видео выбрать законченные по смыслу фрагменты 30–60 с (режим 60–150 с — опция). "
        "Решить: локальная LLM или Claude API — по качеству, скорости и стоимости.",
        (
            Task(
                "Спайк: локальная LLM vs Claude API — качество, скорость, стоимость",
                "Прогнать 2–3 реальных видео пользователя через оба варианта, посчитать токены и "
                "стоимость на час видео, сравнить кандидатов вслепую. Результат — docs/decisions/.",
                (
                    "Таблица: модель × качество (оценка пользователя) × время × цена за час видео",
                    "Рекомендация и обоснование зафиксированы в docs/decisions/",
                ),
                ("task", "spike", "priority:mvp"),
            ),
            Task(
                "Абстракция LLMProvider: Ollama и Claude API, structured output, учёт токенов",
                "Strategy-интерфейс, ретраи, таймауты, подсчёт токенов и стоимости.",
                ("Фейковый провайдер в тестах", "Невалидный JSON от модели обрабатывается ретраем"),
            ),
            Task(
                "Map-reduce анализ транскрипта: кандидаты моментов с обоснованием",
                "Чанкование длинного транскрипта, поиск хука и завершённой мысли, слияние результатов.",
                (
                    "Контекст не теряется на стыках чанков",
                    "Каждый кандидат содержит причину выбора",
                ),
            ),
            Task(
                "Границы клипа: привязка к предложениям, паузам, сценам; ограничения длительности",
                "Клип начинается и заканчивается на естественных границах, длительность в профиле.",
                (
                    "Ни один клип не обрывает слово или предложение",
                    "Профили standard/experimental в конфиге",
                ),
            ),
            Task(
                "Скоринг, дедупликация и ранжирование кандидатов",
                "Веса сигналов и оценки LLM (из legacy), подавление пересечений, top-N на видео.",
                ("Пересекающиеся кандидаты удаляются детерминированно",),
            ),
            Task(
                "Harness ручной оценки: экспорт кандидатов, сохранение оценок, сравнение версий",
                "Превью-клипы + таблица для оценки; сравнение моделей/промптов по оценкам пользователя.",
                ("Оценки сохраняются в хранилище", "Отчёт сравнивает две версии пайплайна"),
            ),
        ),
    ),
    Epic(
        "Рендер 9:16 и допконтент",
        "Нарезка и оформление вертикального формата. Допконтент — после качества нарезки.",
        (
            Task(
                "Нарезка кандидатов по таймкодам: ffmpeg, NVENC с fallback на libx264",
                "Точная нарезка без дрейфа A/V, превью-кадр.",
                ("Длительность результата совпадает с таймкодами ±1 кадр",),
            ),
            Task(
                "Редакция формата 9:16: blur / black / smart-crop",
                "Режимы из legacy render.py, автоопределение режима по исходнику.",
                ("Выход строго 1080x1920", "Режим выбирается по соотношению сторон источника"),
            ),
            Task(
                "Допконтент: субтитры, баннеры, gameplay-фон",
                "Низкий приоритет — после приёмки качества нарезки.",
                ("Каждая опция включается флагом конфига",),
                ("task", "priority:later"),
            ),
        ),
        label="priority:later",
    ),
)


def gh(*args: str, dry: bool = False) -> str:
    """Вызывает gh и возвращает stdout; в dry-run только печатает команду."""
    if dry:
        print("DRY gh", " ".join(args[:4]), "...")
        return "0\n0"
    result = subprocess.run(["gh", *args], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def body_of(task: Task) -> str:
    accept = "\n".join(f"- [ ] {item}" for item in task.accept)
    return f"{task.desc}\n\n## Критерии приёмки\n{accept}{TASK_FOOTER}"


def ensure_label(repo: str, name: str, color: str, dry: bool) -> None:
    """Создаёт метку через REST, а если она есть — обновляет цвет."""
    try:
        gh(
            "api",
            "-X",
            "POST",
            f"repos/{repo}/labels",
            "-f",
            f"name={name}",
            "-f",
            f"color={color}",
            dry=dry,
        )
    except subprocess.CalledProcessError:
        quoted = urllib.parse.quote(name, safe="")
        gh("api", "-X", "PATCH", f"repos/{repo}/labels/{quoted}", "-f", f"color={color}", dry=dry)


def create_issue(
    repo: str, title: str, body: str, labels: tuple[str, ...], dry: bool
) -> tuple[int, int]:
    """Создаёт issue через REST (GraphQL в сессиях Claude недоступен); возвращает (number, id)."""
    args = [
        "api",
        "-X",
        "POST",
        f"repos/{repo}/issues",
        "-f",
        f"title={title}",
        "-f",
        f"body={body}",
    ]
    for label in labels:
        args += ["-f", f"labels[]={label}"]
    number, issue_id = gh(*args, "--jq", ".number, .id", dry=dry).split()
    return int(number), int(issue_id)


def set_body(repo: str, number: int, body: str, dry: bool) -> None:
    gh("api", "-X", "PATCH", f"repos/{repo}/issues/{number}", "-f", f"body={body}", dry=dry)


def link_sub_issue(repo: str, parent: int, child_id: int, dry: bool) -> None:
    """Привязывает задачу как sub-issue к эпику (если API доступно)."""
    try:
        gh(
            "api",
            "-X",
            "POST",
            f"repos/{repo}/issues/{parent}/sub_issues",
            "-F",
            f"sub_issue_id={child_id}",
            dry=dry,
        )
    except subprocess.CalledProcessError as err:
        print(f"  ! sub-issue (id {child_id}) -> #{parent} не привязана: {err.stderr.strip()}")


def add_to_project(repo: str, project: int | None, number: int, dry: bool) -> None:
    """Добавляет issue в Project (gh project использует GraphQL — работает на вашем ПК)."""
    if project is None:
        return
    owner = repo.split("/")[0]
    url = f"https://github.com/{repo}/issues/{number}"
    try:
        gh("project", "item-add", str(project), "--owner", owner, "--url", url, dry=dry)
    except subprocess.CalledProcessError as err:
        print(f"  ! #{number} не добавлена в Project: {err.stderr.strip()}")


def create_epic(repo: str, epic: Epic, project: int | None, dry: bool) -> None:
    epic_no, _ = create_issue(repo, f"[Эпик] {epic.title}", epic.goal, ("epic", epic.label), dry)
    add_to_project(repo, project, epic_no, dry)
    lines = []
    for task in epic.tasks:
        no, issue_id = create_issue(repo, task.title, body_of(task), task.labels, dry)
        add_to_project(repo, project, no, dry)
        link_sub_issue(repo, epic_no, issue_id, dry)
        lines.append(f"- [ ] #{no} {task.title}")
        print(f"SF-{no}: {task.title}")
    set_body(repo, epic_no, f"{epic.goal}\n\n## Задачи\n" + "\n".join(lines), dry)
    print(f"Эпик #{epic_no}: {epic.title}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="owner/repo")
    parser.add_argument("--project", type=int, help="номер GitHub Project для добавления issues")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    for name, color in LABELS.items():
        ensure_label(args.repo, name, color, args.dry_run)
    first, _ = create_issue(
        args.repo, SCAFFOLD.title, body_of(SCAFFOLD), SCAFFOLD.labels, args.dry_run
    )
    if first != 1 and not args.dry_run:
        print(f"! Первая issue получила номер {first}, а не 1: коммиты каркаса надо переименовать.")
    add_to_project(args.repo, args.project, first, args.dry_run)
    for epic in EPICS:
        create_epic(args.repo, epic, args.project, args.dry_run)


if __name__ == "__main__":
    main()

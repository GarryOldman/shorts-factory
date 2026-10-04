"""Загрузка настроек из YAML, `.env` и переменных окружения."""

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from shorts.domain.config import Settings
from shorts.domain.errors import ConfigError

API_KEY_ENV = "SHORTS_LLM_API_KEY"
_PATH_KEYS = ("sources_dir", "workdir")


def parse_dotenv(text: str) -> dict[str, str]:
    """Разбирает содержимое `.env`: `KEY=VALUE`, комментарии и кавычки."""
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = _unquote(value.strip())
    return values


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as err:
        raise ConfigError(f"config.read: не удалось прочитать {path}: {err}") from err
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as err:
        raise ConfigError(f"config.parse: некорректный YAML в {path}") from err
    if not isinstance(data, dict):
        raise ConfigError(f"config.parse: корень {path} должен быть mapping")
    return data


def _forbid_secrets_in_yaml(data: Mapping[str, Any]) -> None:
    llm = data.get("llm")
    if isinstance(llm, dict) and "api_key" in llm:
        raise ConfigError(
            f"config.secrets: llm.api_key нельзя задавать в YAML, используйте {API_KEY_ENV}"
        )


def _resolve_paths(data: dict[str, Any], base: Path) -> None:
    paths = data.get("paths")
    if not isinstance(paths, dict):
        return
    for key in _PATH_KEYS:
        if isinstance(paths.get(key), str):
            paths[key] = str((base / Path(paths[key]).expanduser()).resolve())


def _inject_api_key(data: dict[str, Any], env: Mapping[str, str]) -> None:
    api_key = env.get(API_KEY_ENV)
    if not api_key:
        return
    llm = data.get("llm")
    if llm is None:
        llm = data["llm"] = {}
    if isinstance(llm, dict):
        llm["api_key"] = api_key


def _validate(data: dict[str, Any]) -> Settings:
    try:
        return Settings.model_validate(data)
    except ValidationError as err:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in e['loc'])}: {e['msg']}" for e in err.errors()
        )
        raise ConfigError(f"config.validate: {problems}") from err


def _check_sources_dir(settings: Settings) -> None:
    sources = settings.paths.sources_dir
    if not sources.is_dir():
        raise ConfigError(f"paths.sources_dir: {sources} не существует или не каталог")


def load_settings(
    config_path: Path,
    env: Mapping[str, str] | None = None,
    dotenv_path: Path | None = None,
) -> Settings:
    """Загружает настройки: YAML, поверх него секреты из `.env` и окружения.

    Приоритет секрета: переменная окружения > `.env`. Секреты в YAML запрещены.
    Относительные пути считаются от каталога файла конфигурации.
    """
    data = _read_yaml(config_path)
    _forbid_secrets_in_yaml(data)
    merged_env: dict[str, str] = {}
    if dotenv_path is not None and dotenv_path.is_file():
        merged_env.update(parse_dotenv(dotenv_path.read_text(encoding="utf-8")))
    merged_env.update(os.environ if env is None else env)
    _resolve_paths(data, config_path.parent.resolve())
    _inject_api_key(data, merged_env)
    settings = _validate(data)
    _check_sources_dir(settings)
    return settings

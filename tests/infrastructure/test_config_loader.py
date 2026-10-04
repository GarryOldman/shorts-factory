from pathlib import Path

import pytest

from shorts.domain.errors import ConfigError
from shorts.infrastructure.config_loader import load_settings, parse_dotenv


def write_config(tmp_path: Path, body: str = "") -> Path:
    sources = tmp_path / "videos"
    sources.mkdir(exist_ok=True)
    config = tmp_path / "config.yaml"
    config.write_text(f"paths:\n  sources_dir: videos\n  workdir: work\n{body}", encoding="utf-8")
    return config


def test_loads_minimal_config_and_resolves_paths_relative_to_config(tmp_path: Path) -> None:
    config = write_config(tmp_path)

    settings = load_settings(config, env={})

    assert settings.paths.sources_dir == (tmp_path / "videos").resolve()
    assert settings.paths.workdir == (tmp_path / "work").resolve()


def test_yaml_values_override_defaults(tmp_path: Path) -> None:
    config = write_config(tmp_path, "clip:\n  mode: experimental\n  clips_per_source: 3\n")

    settings = load_settings(config, env={})

    assert settings.clip.mode == "experimental"
    assert settings.clip.clips_per_source == 3


def test_missing_config_file_names_the_path(tmp_path: Path) -> None:
    missing = tmp_path / "nope.yaml"

    with pytest.raises(ConfigError, match="nope.yaml"):
        load_settings(missing, env={})


def test_invalid_yaml_syntax_raises_config_error(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("paths: [unclosed", encoding="utf-8")

    with pytest.raises(ConfigError, match="config.yaml"):
        load_settings(config, env={})


def test_yaml_root_must_be_a_mapping(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("- just\n- a list\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="mapping"):
        load_settings(config, env={})


def test_missing_sources_dir_raises_config_error(tmp_path: Path) -> None:
    config = write_config(tmp_path)
    (tmp_path / "videos").rmdir()

    with pytest.raises(ConfigError, match="sources_dir"):
        load_settings(config, env={})


def test_sources_dir_must_be_a_directory(tmp_path: Path) -> None:
    config = write_config(tmp_path)
    (tmp_path / "videos").rmdir()
    (tmp_path / "videos").write_text("not a dir", encoding="utf-8")

    with pytest.raises(ConfigError, match="sources_dir"):
        load_settings(config, env={})


def test_validation_error_mentions_field_path(tmp_path: Path) -> None:
    config = write_config(tmp_path, "clip:\n  mode: turbo\n")

    with pytest.raises(ConfigError, match=r"clip\.mode"):
        load_settings(config, env={})


def test_api_key_in_yaml_is_forbidden(tmp_path: Path) -> None:
    config = write_config(tmp_path, "llm:\n  provider: claude\n  api_key: sk-in-yaml\n")

    with pytest.raises(ConfigError, match="api_key") as info:
        load_settings(config, env={})

    assert "sk-in-yaml" not in str(info.value)


def test_api_key_is_read_from_environment(tmp_path: Path) -> None:
    config = write_config(tmp_path, "llm:\n  provider: claude\n")

    settings = load_settings(config, env={"SHORTS_LLM_API_KEY": "sk-from-env"})

    assert settings.llm.api_key is not None
    assert settings.llm.api_key.get_secret_value() == "sk-from-env"
    assert "sk-from-env" not in repr(settings)


def test_claude_provider_without_key_raises_config_error(tmp_path: Path) -> None:
    config = write_config(tmp_path, "llm:\n  provider: claude\n")

    with pytest.raises(ConfigError, match="api_key"):
        load_settings(config, env={})


def test_api_key_is_read_from_dotenv_and_environment_wins(tmp_path: Path) -> None:
    config = write_config(tmp_path, "llm:\n  provider: claude\n")
    dotenv = tmp_path / ".env"
    dotenv.write_text("SHORTS_LLM_API_KEY=sk-from-dotenv\n", encoding="utf-8")

    from_dotenv = load_settings(config, env={}, dotenv_path=dotenv)
    from_env = load_settings(config, env={"SHORTS_LLM_API_KEY": "sk-from-env"}, dotenv_path=dotenv)

    assert from_dotenv.llm.api_key is not None
    assert from_dotenv.llm.api_key.get_secret_value() == "sk-from-dotenv"
    assert from_env.llm.api_key is not None
    assert from_env.llm.api_key.get_secret_value() == "sk-from-env"


def test_missing_dotenv_file_is_ignored(tmp_path: Path) -> None:
    config = write_config(tmp_path)

    settings = load_settings(config, env={}, dotenv_path=tmp_path / ".env")

    assert settings.llm.api_key is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("A=1\nB=two\n", {"A": "1", "B": "two"}),
        ("# comment\n\nA=1\n", {"A": "1"}),
        ("A=\"quoted value\"\nB='single'\n", {"A": "quoted value", "B": "single"}),
        ("  A = spaced  \n", {"A": "spaced"}),
        ("A=x=y\n", {"A": "x=y"}),
        ("no_equals_sign\nA=1\n", {"A": "1"}),
        ("", {}),
    ],
)
def test_parse_dotenv(text: str, expected: dict[str, str]) -> None:
    assert parse_dotenv(text) == expected

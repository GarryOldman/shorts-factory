from pathlib import Path

import pytest
from pydantic import ValidationError

from shorts.domain.config import (
    ClipSettings,
    DurationProfile,
    LlmSettings,
    PathsSettings,
    Settings,
)

PATHS = PathsSettings(sources_dir=Path("src_videos"), workdir=Path("work"))


def make_settings(**overrides: object) -> Settings:
    return Settings(paths=PATHS, **overrides)


def test_defaults_use_standard_profile() -> None:
    settings = make_settings()

    profile = settings.clip.active_profile()

    assert (profile.min_sec, profile.target_sec, profile.max_sec) == (30, 45, 60)
    assert settings.clip.clips_per_source == 10
    assert settings.llm.provider == "ollama"


def test_experimental_mode_selects_longer_profile() -> None:
    clip = ClipSettings(mode="experimental")

    profile = clip.active_profile()

    assert (profile.min_sec, profile.target_sec, profile.max_sec) == (60, 90, 150)


@pytest.mark.parametrize(
    ("min_sec", "target_sec", "max_sec"),
    [
        (50, 45, 60),  # min > target
        (30, 70, 60),  # target > max
        (0, 10, 20),  # min должен быть положительным
        (-5, 10, 20),
    ],
)
def test_duration_profile_rejects_inconsistent_bounds(
    min_sec: float, target_sec: float, max_sec: float
) -> None:
    with pytest.raises(ValidationError):
        DurationProfile(min_sec=min_sec, target_sec=target_sec, max_sec=max_sec)


@pytest.mark.parametrize("value", [0, -1])
def test_clips_per_source_must_be_positive(value: int) -> None:
    with pytest.raises(ValidationError):
        ClipSettings(clips_per_source=value)


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        make_settings(unknown_section={"a": 1})


def test_unknown_mode_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ClipSettings(mode="turbo")


def test_claude_provider_requires_api_key() -> None:
    with pytest.raises(ValidationError, match="api_key"):
        LlmSettings(provider="claude")


def test_ollama_provider_works_without_api_key() -> None:
    assert LlmSettings(provider="ollama").api_key is None


def test_api_key_is_hidden_in_repr() -> None:
    llm = LlmSettings(provider="claude", api_key="sk-secret-value")

    assert "sk-secret-value" not in repr(llm)
    assert "sk-secret-value" not in repr(make_settings(llm=llm))
    assert llm.api_key is not None
    assert llm.api_key.get_secret_value() == "sk-secret-value"

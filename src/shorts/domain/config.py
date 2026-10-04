"""Типизированные неизменяемые настройки приложения."""

from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator


class _Frozen(BaseModel):
    """Базовая модель: неизменяема, неизвестные поля запрещены."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class DurationProfile(_Frozen):
    """Границы длительности клипа в секундах."""

    min_sec: float = Field(gt=0)
    target_sec: float = Field(gt=0)
    max_sec: float = Field(gt=0)

    @model_validator(mode="after")
    def _check_order(self) -> Self:
        if not self.min_sec <= self.target_sec <= self.max_sec:
            raise ValueError("ожидается min_sec <= target_sec <= max_sec")
        return self


class ClipSettings(_Frozen):
    """Параметры выбора клипов."""

    mode: Literal["standard", "experimental"] = "standard"
    clips_per_source: int = Field(default=10, gt=0)
    standard: DurationProfile = DurationProfile(min_sec=30, target_sec=45, max_sec=60)
    experimental: DurationProfile = DurationProfile(min_sec=60, target_sec=90, max_sec=150)

    def active_profile(self) -> DurationProfile:
        """Возвращает профиль длительности, выбранный в `mode`."""
        return self.experimental if self.mode == "experimental" else self.standard


class AnalysisSettings(_Frozen):
    """Параметры анализа видео."""

    whisper_model: str = "medium"
    whisper_device: Literal["auto", "cuda", "cpu"] = "auto"


class LlmSettings(_Frozen):
    """Параметры LLM-провайдера. Ключ API задаётся только через окружение."""

    provider: Literal["ollama", "claude"] = "ollama"
    model: str | None = None
    timeout_sec: int = Field(default=120, gt=0)
    api_key: SecretStr | None = None

    @model_validator(mode="after")
    def _check_api_key(self) -> Self:
        if self.provider == "claude" and self.api_key is None:
            raise ValueError("для provider=claude требуется api_key (SHORTS_LLM_API_KEY)")
        return self


class PathsSettings(_Frozen):
    """Пути к исходникам и рабочим артефактам пайплайна."""

    sources_dir: Path
    workdir: Path


class Settings(_Frozen):
    """Корневые настройки приложения."""

    paths: PathsSettings
    clip: ClipSettings = ClipSettings()
    analysis: AnalysisSettings = AnalysisSettings()
    llm: LlmSettings = LlmSettings()

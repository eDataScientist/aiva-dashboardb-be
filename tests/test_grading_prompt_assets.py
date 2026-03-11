from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import Settings
from app.schemas.grading_prompts import PromptDomain
from app.services.grading_prompt_assets import GradingPromptAssetError, load_prompt_pack


def test_load_prompt_pack_uses_repo_versioned_assets() -> None:
    settings = Settings.model_construct(
        grading_prompt_assets_root=None,
        grading_prompt_version="v1",
    )

    loaded_pack = load_prompt_pack(settings=settings)

    assert loaded_pack.manifest.version == "v1"
    assert loaded_pack.root_dir.name == "v1"
    assert "evaluate the AI assistant's performance across 5 dimensions" in loaded_pack.get_template(
        PromptDomain.AI_PERFORMANCE
    )
    assert "Arabia Insurance UAE's virtual assistant" in loaded_pack.system_prompt_text


def test_load_prompt_pack_rejects_missing_required_file(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings.model_construct(
        grading_prompt_assets_root=None,
        grading_prompt_version="v1",
    )
    target_file = settings.resolved_grading_prompt_assets_dir / "intent.md"
    original_is_file = Path.is_file

    def fake_is_file(path: Path) -> bool:
        if path == target_file:
            return False
        return original_is_file(path)

    monkeypatch.setattr(Path, "is_file", fake_is_file)

    with pytest.raises(GradingPromptAssetError, match="missing required files"):
        load_prompt_pack(settings=settings)


def test_load_prompt_pack_rejects_unsupported_placeholders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings.model_construct(
        grading_prompt_assets_root=None,
        grading_prompt_version="v1",
    )
    target_file = settings.resolved_grading_prompt_assets_dir / "intent.md"
    original_read_text = Path.read_text

    def fake_read_text(path: Path, *args, **kwargs) -> str:
        if path == target_file:
            return "Conversation:\n{{conversation}}\n{{unknown_placeholder}}\n"
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read_text)

    with pytest.raises(GradingPromptAssetError, match="unsupported placeholders"):
        load_prompt_pack(settings=settings)

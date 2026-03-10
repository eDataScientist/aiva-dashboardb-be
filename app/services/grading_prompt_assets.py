from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings, get_settings
from app.core.constants import (
    GRADING_DEFAULT_PROMPT_VERSION,
    GRADING_PROMPT_DOMAIN_ORDER,
    GRADING_PROMPT_DOMAIN_SYSTEM_PROMPT_KEYS,
    GRADING_PROMPT_DOMAIN_TO_TEMPLATE_FILE,
    GRADING_PROMPT_SYSTEM_PROMPT_FILE,
)
from app.schemas.grading_prompts import PromptDomain, PromptPackManifest, PromptTemplateSpec


class GradingPromptAssetError(RuntimeError):
    """Raised when prompt-pack assets cannot be resolved or loaded."""


@dataclass(frozen=True, slots=True)
class LoadedPromptPack:
    manifest: PromptPackManifest
    root_dir: Path
    system_prompt_text: str
    templates: dict[PromptDomain, str]

    def get_template(self, prompt_domain: PromptDomain | str) -> str:
        domain = PromptDomain(prompt_domain)
        return self.templates[domain]


def build_prompt_pack_manifest(
    version: str = GRADING_DEFAULT_PROMPT_VERSION,
) -> PromptPackManifest:
    template_specs = tuple(
        PromptTemplateSpec(
            prompt_key=PromptDomain(prompt_key),
            template_file=GRADING_PROMPT_DOMAIN_TO_TEMPLATE_FILE[prompt_key],
            output_fields=_output_fields_for_prompt_key(prompt_key),
            include_system_prompt=prompt_key in GRADING_PROMPT_DOMAIN_SYSTEM_PROMPT_KEYS,
            required_placeholders=(
                ("conversation", "system_prompt")
                if prompt_key in GRADING_PROMPT_DOMAIN_SYSTEM_PROMPT_KEYS
                else ("conversation",)
            ),
        )
        for prompt_key in GRADING_PROMPT_DOMAIN_ORDER
    )
    return PromptPackManifest(
        version=version,
        system_prompt_file=GRADING_PROMPT_SYSTEM_PROMPT_FILE,
        prompt_order=tuple(PromptDomain(prompt_key) for prompt_key in GRADING_PROMPT_DOMAIN_ORDER),
        prompt_templates=template_specs,
    )


def load_prompt_pack(*, settings: Settings | None = None) -> LoadedPromptPack:
    resolved_settings = settings or get_settings()
    manifest = build_prompt_pack_manifest(version=resolved_settings.grading_prompt_version)
    root_dir = resolved_settings.resolved_grading_prompt_assets_dir

    if not root_dir.exists() or not root_dir.is_dir():
        raise GradingPromptAssetError(
            f"Prompt-pack directory does not exist: {root_dir}"
        )

    try:
        system_prompt_text = (root_dir / manifest.system_prompt_file).read_text(
            encoding="utf-8"
        )
        templates = {
            template.prompt_key: (root_dir / template.template_file).read_text(
                encoding="utf-8"
            )
            for template in manifest.prompt_templates
        }
    except OSError as exc:
        raise GradingPromptAssetError(
            f"Failed to load prompt-pack assets from {root_dir}."
        ) from exc

    return LoadedPromptPack(
        manifest=manifest,
        root_dir=root_dir,
        system_prompt_text=system_prompt_text,
        templates=templates,
    )


def _output_fields_for_prompt_key(prompt_key: str) -> tuple[str, ...]:
    if prompt_key == "ai_performance":
        return (
            "relevancy_score",
            "relevancy_reasoning",
            "accuracy_score",
            "accuracy_reasoning",
            "completeness_score",
            "completeness_reasoning",
            "clarity_score",
            "clarity_reasoning",
            "tone_score",
            "tone_reasoning",
        )
    if prompt_key == "conversation_health":
        return (
            "resolution",
            "resolution_reasoning",
            "repetition_score",
            "repetition_reasoning",
            "loop_detected",
            "loop_detected_reasoning",
        )
    if prompt_key == "user_signals":
        return (
            "satisfaction_score",
            "satisfaction_reasoning",
            "frustration_score",
            "frustration_reasoning",
            "user_relevancy",
            "user_relevancy_reasoning",
        )
    if prompt_key == "escalation":
        return (
            "escalation_occurred",
            "escalation_occurred_reasoning",
            "escalation_type",
            "escalation_type_reasoning",
        )
    if prompt_key == "intent":
        return (
            "intent_label",
            "intent_reasoning",
        )
    raise GradingPromptAssetError(f"Unsupported prompt domain '{prompt_key}'.")

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .capabilities import capability_prompt_snapshot
from .config_paths import RuntimePaths
from .providers import MODE_PROMPT_FILE, load_yaml_resource


@dataclass(frozen=True)
class ProductPromptLayers:
    product_baseline: str
    capability_snapshot: str = ""
    mode_overlay: str = ""
    runtime_policy_overlay: str = ""
    delivery_overlay: str = ""

    def compile(self) -> str:
        return "\n\n".join(
            part.strip()
            for part in (
                self.product_baseline,
                self.capability_snapshot,
                self.mode_overlay,
                self.runtime_policy_overlay,
                self.delivery_overlay,
            )
            if part and part.strip()
        )

    def summaries(self) -> list[dict[str, str]]:
        return [
            {"id": "product_baseline", "summary": _first_line(self.product_baseline)},
            {"id": "capability_snapshot", "summary": _first_line(self.capability_snapshot)},
            {"id": "mode_overlay", "summary": _first_line(self.mode_overlay)},
            {"id": "runtime_policy_overlay", "summary": _first_line(self.runtime_policy_overlay)},
            {"id": "delivery_overlay", "summary": _first_line(self.delivery_overlay)},
        ]


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _first_line(value: str) -> str:
    return next((line.strip() for line in value.splitlines() if line.strip()), "")


def product_baseline_prompt() -> str:
    data = load_yaml_resource(MODE_PROMPT_FILE)
    if not isinstance(data, dict):
        raise ValueError("default_mode_prompt.yaml must contain a mapping")
    baseline = data.get("product_baseline")
    if not isinstance(baseline, dict) or not _as_text(baseline.get("system_hint")):
        raise ValueError("default_mode_prompt.yaml must contain product_baseline.system_hint")
    return _as_text(baseline.get("system_hint"))


def compile_product_prompt_layers(
    paths: RuntimePaths,
    *,
    mode_overlay: str,
    runtime_policy_overlay: str = "",
    delivery_overlay: str = "",
) -> ProductPromptLayers:
    return ProductPromptLayers(
        product_baseline=product_baseline_prompt(),
        capability_snapshot=capability_prompt_snapshot(paths),
        mode_overlay=mode_overlay,
        runtime_policy_overlay=runtime_policy_overlay,
        delivery_overlay=delivery_overlay,
    )

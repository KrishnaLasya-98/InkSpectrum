"""Declarative ModelsLab video capability contracts.

Keep provider routing facts in one place so educational pipelines can select a
model by operation without duplicating endpoint and parameter-family logic.
Unknown model identifiers use the unified v7 Video Fusion contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ModelsLabVideoContract:
    """Provider behavior for one ModelsLab model family."""

    name: str
    aliases: frozenset[str]
    operations: frozenset[str]
    endpoints: Mapping[str, str]
    poll_endpoint: str
    parameter_profile: str
    accepts_generate_audio: bool

    def endpoint_for(self, operation: str) -> str:
        try:
            return self.endpoints[operation]
        except KeyError as exc:
            supported = ", ".join(sorted(self.operations))
            raise ValueError(
                f"ModelsLab model family {self.name!r} does not support "
                f"operation {operation!r}; supported operations: {supported}"
            ) from exc


_V6 = "https://modelslab.com/api/v6/video"
_V7 = "https://modelslab.com/api/v7/video-fusion"

GENERIC_V7_CONTRACT = ModelsLabVideoContract(
    name="video-fusion-v7",
    aliases=frozenset(),
    operations=frozenset(
        {
            "text_to_video",
            "image_to_video",
            "reference_to_video",
            "video_to_video",
            "lip_sync",
        }
    ),
    endpoints={
        "text_to_video": f"{_V7}/text-to-video",
        "image_to_video": f"{_V7}/image-to-video",
        # Video Fusion currently accepts reference inputs through text-to-video.
        "reference_to_video": f"{_V7}/text-to-video",
        "video_to_video": f"{_V7}/video-to-video",
        "lip_sync": f"{_V7}/lip-sync",
    },
    poll_endpoint="video-fusion",
    parameter_profile="v7",
    accepts_generate_audio=True,
)

MODEL_CONTRACTS = (
    ModelsLabVideoContract(
        name="wan-2.2-text",
        aliases=frozenset({"wan2.2", "wan-2.2-t2v"}),
        operations=frozenset({"text_to_video"}),
        endpoints={"text_to_video": f"{_V6}/text2video_ultra"},
        poll_endpoint="video",
        parameter_profile="wan22_t2v",
        accepts_generate_audio=False,
    ),
    ModelsLabVideoContract(
        name="wan-2.2-image",
        aliases=frozenset({"wan-2.2-i2v"}),
        operations=frozenset({"image_to_video"}),
        endpoints={"image_to_video": f"{_V6}/img2video_ultra"},
        poll_endpoint="video",
        parameter_profile="wan22_i2v",
        accepts_generate_audio=False,
    ),
    ModelsLabVideoContract(
        name="h3-minimax-text",
        aliases=frozenset({"h3-minimax-t2v"}),
        operations=frozenset({"text_to_video"}),
        endpoints={"text_to_video": f"{_V6}/text2video"},
        poll_endpoint="video",
        parameter_profile="h3_minimax",
        accepts_generate_audio=False,
    ),
    ModelsLabVideoContract(
        name="h3-minimax-start-end-frame",
        aliases=frozenset({"h3-minimax-start-end-frame"}),
        operations=frozenset({"image_to_video"}),
        endpoints={"image_to_video": f"{_V6}/img2video"},
        poll_endpoint="video",
        parameter_profile="h3_minimax",
        accepts_generate_audio=False,
    ),
    ModelsLabVideoContract(
        name="h3-minimax-reference",
        aliases=frozenset(
            {
                "h3-minimax-r2v",
                "h3-minimax-ref-to-video-fast",
            }
        ),
        operations=frozenset({"reference_to_video"}),
        endpoints={"reference_to_video": f"{_V6}/img2video"},
        poll_endpoint="video",
        parameter_profile="h3_minimax",
        accepts_generate_audio=False,
    ),
)

DEFAULT_MODELS_BY_OPERATION: Mapping[str, str] = {
    "text_to_video": "seedance-t2v",
    "image_to_video": "seedance-i2v",
    "reference_to_video": "seedance-t2v",
    "video_to_video": "wan2.1",
    "lip_sync": "lipsync-2",
}


def resolve_modelslab_video_contract(
    model_id: str, operation: str
) -> ModelsLabVideoContract:
    """Resolve and validate the provider contract for a model and operation."""

    for contract in MODEL_CONTRACTS:
        if model_id in contract.aliases:
            contract.endpoint_for(operation)
            return contract
    GENERIC_V7_CONTRACT.endpoint_for(operation)
    return GENERIC_V7_CONTRACT

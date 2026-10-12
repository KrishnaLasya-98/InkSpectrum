"""Deterministic proposal, scene, and asset artifacts for chapter production."""
from __future__ import annotations

from typing import Any


def build_production_artifacts(
    config: dict[str, Any], educational_plan: dict[str, Any]
) -> dict[str, Any]:
    """Build auditable intermediate artifacts without subject-specific code."""
    providers = config.get("providers") or {}
    video_provider = providers.get("video") or {}
    if isinstance(video_provider, str):
        video_provider = {"provider": video_provider}
    render_policy = config.get("render_policy") or {}
    content_policy = config.get("content_policy") or {}
    approval_policy = str(config.get("approval_policy") or "guided")
    preauthorized = approval_policy == "full-run-preauthorized"

    title = educational_plan.get("title") or config.get("title") or "Educational Chapter"
    section_count = len(educational_plan.get("sections") or [])
    proposal = {
        "version": "1.0",
        "concept_options": [
            {
                "id": "c1", "title": "Source-faithful animated lesson",
                "hook": f"Let us discover {title} together!",
                "narrative_structure": "journey",
                "visual_approach": "Fresh child-friendly 3D motion with compact textbook teaching panels.",
                "target_duration_seconds": float(educational_plan.get("total_duration_seconds") or 1),
                "why_this_works": "It preserves textbook order while keeping young learners visually engaged.",
            },
            {
                "id": "c2", "title": "Precision-first classroom lesson",
                "hook": "Watch each idea become clear step by step.",
                "narrative_structure": "tutorial",
                "visual_approach": "Deterministic diagrams and stable reading screens with limited story motion.",
                "target_duration_seconds": float(educational_plan.get("total_duration_seconds") or 1),
                "why_this_works": "It maximizes accuracy for symbols, tables, worked examples, and exercises.",
            },
            {
                "id": "c3", "title": "Evidence-led visual explanation",
                "hook": "See how the lesson connects to the world around us.",
                "narrative_structure": "comparison",
                "visual_approach": "Reviewed factual references blended with authored teaching graphics.",
                "target_duration_seconds": float(educational_plan.get("total_duration_seconds") or 1),
                "why_this_works": "It suits factual chapters where authenticity matters more than character continuity.",
            },
        ],
        "selected_concept": {
            "concept_id": "c1",
            "rationale": "The approved educational standard requires source-faithful, child-friendly 3D motion and fixed HyperFrames teaching UI.",
        },
        "production_plan": {
            "pipeline": "educational-video",
            "stages": [
                {
                    "stage": "source_and_planning", "tools": [],
                    "approach": "Preserve every required source block and map it to narration, screen, and visual evidence.",
                },
                {
                    "stage": "media_generation", "tools": [],
                    "approach": "Generate ModelsLab narration and fresh 3D motion; use deterministic teaching modes where needed.",
                },
                {
                    "stage": "composition_and_qa", "tools": [],
                    "approach": "Compose with the locked HyperFrames template and block export on failed QA.",
                },
            ],
            "render_runtime": "hyperframes",
            "renderer_family": "animation-first",
            "composition_mode": "atelier",
            "art_direction": "Locked hyperframes-educational-v1 warm classroom film with cream panels and word-highlight subtitle lane.",
            "ui_template_id": render_policy.get("ui_template_id"),
            "ui_template_version": render_policy.get("ui_template_version"),
            "ui_template_package_sha256": render_policy.get(
                "ui_template_package_sha256"
            ),
            "visual_media": render_policy.get("visual_media", "animated-video-only"),
            "audio_provider": (providers.get("audio") or {}).get("provider", "modelslab")
            if isinstance(providers.get("audio") or {}, dict)
            else providers.get("audio"),
            "video_provider": video_provider.get("provider", "modelslab"),
            "fresh_assets_only": bool(video_provider.get("fresh_assets_only", True)),
            "allow_clip_reuse": bool(video_provider.get("allow_clip_reuse", False)),
            "delivery_promise": {
                "promise_type": "motion_led",
                "motion_required": True,
                "tone_mode": "educational",
                "quality_floor": "broadcast",
                "approved_fallback": None,
            },
        },
        "cost_estimate": {
            "total_estimated_usd": 0.0,
            "line_items": [{
                "tool": "modelslab",
                "operation": "chapter narration, character references, and generated motion",
                "quantity": section_count,
                "estimated_usd": 0.0,
                "notes": "Actual price is account/model dependent and is recorded from provider responses.",
            }],
            "budget_verdict": "no_budget_set",
        },
        "approval": {
            "status": "approved" if preauthorized else "pending",
            "user_notes": (
                "Full-run preauthorization recorded in chapter configuration."
                if preauthorized
                else "Awaiting proposal approval before paid generation."
            ),
        },
        "metadata": {
            "project_id": config.get("project_id"),
            "subject": config.get("subject"),
            "grade": config.get("grade"),
            "chapter": config.get("chapter"),
            "title": title,
            "source_input": config.get("source_input") or config.get("source_pdf"),
            "content_contract": {
                "source_fidelity": content_policy.get("source_fidelity"),
                "allow_invented_labels": bool(content_policy.get("allow_invented_labels", False)),
                "remove_redundant_text": bool(content_policy.get("remove_redundant_text", True)),
            },
        },
    }

    scenes: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    assets: list[dict[str, Any]] = []
    cursor = 0.0
    for index, section in enumerate(educational_plan.get("sections") or [], 1):
        section_id = str(section.get("section_id") or f"section-{index:04d}")
        render_mode = str(section.get("render_mode") or "video_gen")
        if render_mode == "video_gen":
            strategy = "generated_3d_video"
            provider = video_provider.get("provider", "modelslab")
            model_candidates = [
                video_provider.get("reference_model_id"),
                video_provider.get("image_model_id"),
                video_provider.get("model_id"),
                video_provider.get("fallback_model_id"),
            ]
            rationale = "Continuous story or explanation motion is required."
        elif render_mode == "manim":
            strategy = "precision_animation"
            provider = "manim"
            model_candidates = []
            rationale = "Exact quantities, diagrams, or processes require deterministic animation."
        elif render_mode == "hyperframes":
            strategy = "stable_teaching_ui"
            provider = "hyperframes"
            model_candidates = []
            rationale = "The learner must read or answer source-faithful content on a stable screen."
        else:
            strategy = "blocked"
            provider = None
            model_candidates = []
            rationale = f"Unsupported render mode: {render_mode}."

        duration = float(section.get("duration_seconds") or 0.0)
        scene_type = {
            "video_gen": "generated", "manim": "diagram", "hyperframes": "text_card"
        }.get(render_mode, "generated")
        scene = {
            "id": section_id,
            "type": scene_type,
            "description": section.get("description") or section.get("title") or "",
            "start_seconds": round(cursor, 3),
            "end_seconds": round(cursor + duration, 3),
            "script_section_id": section_id,
            "scene_id": section_id,
            "section_id": section_id,
            "order": index,
            "title": section.get("title", ""),
            "source_block_ids": list(section.get("source_block_ids") or []),
            "source_semantic_role": section.get("source_semantic_role"),
            "source_page_number": section.get("source_page_number"),
            "render_mode": render_mode,
            "duration_seconds": duration,
            "narration_text": section.get("narration_script", ""),
            "expected_visual": section.get("description") or section.get("title") or "",
            "transition_to_next": section.get("transition_to_next", "crossfade"),
        }
        cursor += duration
        scenes.append(scene)
        decisions.append({
            "scene_id": section_id,
            "selected_strategy": strategy,
            "provider": provider,
            "model_candidates": [value for value in model_candidates if value],
            "reason": rationale,
            "fresh_asset_required": strategy == "generated_3d_video",
            "stock_search_required": False,
            "status": "planned" if strategy != "blocked" else "blocked",
        })
        assets.append({
            "id": f"{section_id}:visual",
            "type": "video" if strategy == "generated_3d_video" else "animation",
            "scene_id": section_id,
            "source_tool": str(provider or "openmontage"),
            "source_block_ids": list(section.get("source_block_ids") or []),
            "strategy": strategy,
            "provider": provider,
            "status": "planned" if strategy != "blocked" else "blocked",
            "path": "",
            "qa_status": "pending" if strategy == "generated_3d_video" else "not_applicable",
        })

    scene_plan = {
        "version": "1.0",
        "scenes": scenes,
        "metadata": {
            "title": title,
            "subject": config.get("subject"),
            "total_scenes": len(scenes),
        },
    }
    asset_strategy = {
        "version": "1.0",
        "policy": "fresh-3d-motion-with-precision-teaching-modes",
        "decisions": decisions,
        "blocked_scene_ids": [
            item["scene_id"] for item in decisions if item["status"] == "blocked"
        ],
    }
    asset_manifest = {
        "version": "1.0",
        "assets": assets,
        "total_cost_usd": 0.0,
        "metadata": {
            "project_id": config.get("project_id"),
            "fresh_assets_only": proposal["production_plan"]["fresh_assets_only"],
        },
    }
    audio_provider = providers.get("audio") or {}
    if isinstance(audio_provider, str):
        audio_provider = {"provider": audio_provider}
    selected_audio_provider = str(audio_provider.get("provider") or "modelslab")
    audio_voice_id = str(audio_provider.get("voice_id") or "unspecified")
    decision_log = {
        "version": "1.0",
        "project_id": str(config.get("project_id") or "educational-project"),
        "decisions": [
            {
                "decision_id": "d-001",
                "stage": "proposal",
                "category": "pipeline_selection",
                "subject": "Educational production pipeline",
                "options_considered": [
                    {
                        "option_id": "educational-video",
                        "label": "Source-grounded educational video",
                        "score": 1.0,
                        "reason": "Preserves textbook coverage, teaching UI, synchronization, and encoded-output QA.",
                    }
                ],
                "selected": "educational-video",
                "reason": "The input is a textbook chapter requiring auditable source fidelity.",
                "user_visible": True,
                "user_approved": preauthorized,
                "confidence": 1.0,
            },
            {
                "decision_id": "d-002",
                "stage": "proposal",
                "category": "render_runtime_selection",
                "subject": "Composition runtime",
                "options_considered": [
                    {
                        "option_id": "hyperframes",
                        "label": "HyperFrames",
                        "score": 1.0,
                        "reason": "Matches the locked educational UI and word-highlight subtitle contract.",
                    },
                    {
                        "option_id": "remotion",
                        "label": "Remotion",
                        "score": 0.6,
                        "reason": "Available, but not the approved appearance/runtime for this educational program.",
                        "rejected_because": "The educational template is locked to HyperFrames.",
                    },
                ],
                "selected": "hyperframes",
                "reason": "The user selected HyperFrames and the shared educational template is version-locked to it.",
                "user_visible": True,
                "user_approved": preauthorized,
                "confidence": 1.0,
            },
            {
                "decision_id": "d-003",
                "stage": "proposal",
                "category": "provider_selection",
                "subject": "Generated educational motion provider",
                "options_considered": [
                    {
                        "option_id": "modelslab",
                        "label": "ModelsLab",
                        "score": 1.0,
                        "reason": "Configured for text, image, and reference-driven animated video generation.",
                    }
                ],
                "selected": "modelslab",
                "reason": "The chapter provider contract explicitly selects ModelsLab.",
                "user_visible": True,
                "user_approved": preauthorized,
                "confidence": 1.0,
            },
            {
                "decision_id": "d-004",
                "stage": "proposal",
                "category": "voice_selection",
                "subject": "Narration TTS provider",
                "options_considered": [
                    {
                        "option_id": selected_audio_provider,
                        "label": selected_audio_provider,
                        "score": 1.0,
                        "reason": (
                            "Uses one chapter-scoped voice with speech QA and word alignment; "
                            f"configured voice is {audio_voice_id}."
                        ),
                    }
                ],
                "selected": selected_audio_provider,
                "reason": "The configured narrator remains authoritative for the whole chapter.",
                "user_visible": True,
                "user_approved": preauthorized,
                "confidence": 1.0,
            },
        ],
    }
    return {
        "proposal_packet": proposal,
        "scene_plan": scene_plan,
        "asset_strategy": asset_strategy,
        "asset_manifest": asset_manifest,
        "decision_log": decision_log,
    }


def finalize_asset_manifest(
    asset_manifest: dict[str, Any], clip_manifest: list[dict[str, Any]]
) -> dict[str, Any]:
    """Attach concrete clip paths and QA evidence after rendering."""
    clips = {str(item.get("section_id")): item for item in clip_manifest}
    result = {**asset_manifest, "assets": []}
    for original in asset_manifest.get("assets") or []:
        asset = dict(original)
        clip = clips.get(str(asset.get("scene_id")))
        if clip:
            asset["path"] = clip.get("video_path") or ""
            asset["status"] = "ready" if clip.get("success") else "failed"
            asset["qa_status"] = (clip.get("qa_report") or {}).get(
                "status", "not_applicable"
            )
            asset["content_fingerprint"] = clip.get("content_fingerprint") or ""
        result["assets"].append(asset)
    result["ready"] = all(
        asset.get("status") == "ready"
        or asset.get("strategy") == "stable_teaching_ui"
        for asset in result["assets"]
    )
    return result

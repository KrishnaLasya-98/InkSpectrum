"""Character Consistency Manager for EduStream Pro.

Uses h3-minimax-r2v (Reference-to-Video) to maintain visual identity
across all video_gen clips within a subject.

How it works
------------
1. CharacterBible — generates canonical reference images for recurring
   characters discovered from the current chapter. The dynamic pipeline stores
   them in the chapter workspace and reuses them only while their source
   fingerprint remains unchanged.

2. CharacterConsistencyManager  — wraps every video_gen API call with
   h3-minimax-r2v instead of wan2.2, injecting reference images so the model
   sees "Image 1 = this character" before every scene.

3. Reference registry — projects/{project}/artifacts/character_bible.json maps
   character_id to a local ModelsLab reference image. RenderModeRouter receives
   matching paths explicitly when render_mode = "video_gen".

h3-minimax-r2v API contract (from llms.txt)
-------------------------------------------
  Endpoint : POST https://modelslab.com/api/v6/video/img2video
  model_id : h3-minimax-r2v
  init_image: array of reference image URLs (Image 1, Image 2, …)
  init_video: array of reference video clips
  init_audio: array of reference audio (2-15s each, ≤15s total)
  prompt    : references assets as "Image 1", "Image 2" in text
  duration  : 5-15 (seconds)
  Max total reference files: 12

Character prompt formula
------------------------
  "Keep Image 1's [character description] consistent: same face, same colours,
   same style, same proportions. Scene: [what happens]. Fixed camera,
   no text, no watermark, child-safe, flat educational illustration style."

Usage
-----
    from tools.video.character_consistency import CharacterConsistencyManager
    mgr = CharacterConsistencyManager()

    # Generate character bible (run once per subject)
    mgr.generate_bible("evs")

    # Generate a clip with character consistency enforced
    result = mgr.generate_consistent_clip(
        subject="evs",
        section_id="s01",
        scene_description="Fish glides once across the pond, fins fanning.",
        characters=["fish"],
        output_path=Path("renders/evs/clips/s01.mp4"),
    )
"""
from __future__ import annotations

import json
import hashlib
import os
import re
import time
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Character definitions per subject
# Character fields:
#   id          — used as lookup key
#   name        — human-readable label
#   description — full visual description for reference image generation
#   sections    — which section_ids this character appears in
# ---------------------------------------------------------------------------
CHARACTER_REGISTRY: dict[str, list[dict[str, Any]]] = {
    "evs": [
        {
            "id": "fish",
            "name": "Class 1 Fish",
            "description": (
                "A bright orange-and-white fish with rounded fins, large friendly eyes, "
                "smooth scales, swimming in clear blue-green water. Flat educational "
                "illustration style, warm palette, child-safe, accurate fish anatomy, "
                "no text, no background clutter."
            ),
            "sections": ["s01", "s03", "s12", "s15"],
            "seed": 100001,
        },
        {
            "id": "rabbit",
            "name": "Class 1 Rabbit",
            "description": (
                "A fluffy white rabbit with pink inner ears, large dark eyes, short tail, "
                "standing on green grass. Flat educational illustration style, warm palette, "
                "child-safe, accurate rabbit anatomy, no text."
            ),
            "sections": ["s01", "s06", "s09", "s14"],
            "seed": 100002,
        },
        {
            "id": "lion",
            "name": "Class 1 Lion",
            "description": (
                "A friendly-looking male lion with a full golden mane, large brown eyes, "
                "tawny coat, standing on savanna grass. Flat educational illustration style, "
                "warm ochre-and-sky palette, child-safe, accurate lion anatomy, no text."
            ),
            "sections": ["s03", "s07", "s09"],
            "seed": 100003,
        },
        {
            "id": "elephant",
            "name": "Class 1 Elephant",
            "description": (
                "A large grey elephant with big round ears, long curved trunk, small friendly "
                "eyes, standing on golden savanna. Flat educational illustration style, "
                "warm palette, child-safe, accurate elephant anatomy, no text."
            ),
            "sections": ["s03", "s12"],
            "seed": 100004,
        },
        {
            "id": "dog",
            "name": "Class 1 Dog",
            "description": (
                "A golden retriever dog with a wagging tail, floppy ears, brown eyes, "
                "standing in a green garden. Flat educational illustration style, warm "
                "amber-and-green palette, child-safe, accurate dog anatomy, no text."
            ),
            "sections": ["s06", "s11", "s14"],
            "seed": 100005,
        },
        {
            "id": "parrot",
            "name": "Class 1 Parrot",
            "description": (
                "A vivid green-and-red parrot with a curved beak, bright eyes, perched on "
                "a wooden branch or perch. Flat educational illustration style, warm palette, "
                "child-safe, accurate parrot anatomy, no text."
            ),
            "sections": ["s01", "s04", "s06"],
            "seed": 100006,
        },
        {
            "id": "butterfly",
            "name": "Class 1 Butterfly",
            "description": (
                "A yellow-and-black butterfly with symmetrical wings fully spread, six visible "
                "legs, antennae, hovering above a pink flower. Flat educational illustration "
                "style, warm golden palette, child-safe, accurate insect anatomy, no text."
            ),
            "sections": ["s05", "s15"],
            "seed": 100007,
        },
        {
            "id": "bird_generic",
            "name": "Class 1 Bird",
            "description": (
                "A small brown sparrow-like bird with a short beak, round body, two legs, "
                "perched on a branch. Flat educational illustration style, warm palette, "
                "child-safe, accurate bird anatomy, no text."
            ),
            "sections": ["s04", "s08", "s10", "s13"],
            "seed": 100008,
        },
    ],
    "english": [
        {
            "id": "varun",
            "name": "Varun",
            "description": (
                "A young Indian boy aged 6-7, short black hair, wearing a blue t-shirt and "
                "khaki shorts, cheerful expression, at a beach. Flat educational illustration "
                "style, bright palette, child-safe, no text."
            ),
            "sections": ["s01", "s02", "s03", "s04"],
            "seed": 200001,
        },
        {
            "id": "vidya",
            "name": "Vidya",
            "description": (
                "A young Indian girl aged 6-7, black hair in two plaits, wearing a yellow "
                "dress, cheerful expression, at a beach. Flat educational illustration style, "
                "bright palette, child-safe, no text."
            ),
            "sections": ["s01", "s02", "s03", "s04"],
            "seed": 200002,
        },
    ],
    "maths": [
        {
            "id": "sparky",
            "name": "Sparky the Star",
            "description": (
                "A friendly five-pointed yellow star character with simple dot eyes and a "
                "curved smile, no limbs, glowing warm yellow colour with orange outline. "
                "Flat cartoon style, child-safe, no text, simple clean design."
            ),
            "sections": ["s00", "s01", "s02", "s03"],
            "seed": 300001,
        },
    ],
}


def _subject_bible_path(subject: str, project_dir: Path | None = None) -> Path:
    """Return the path to the character bible JSON for a subject."""
    if project_dir is not None:
        return Path(project_dir) / "artifacts" / "character_bible.json"
    from pathlib import Path as P
    root = P(__file__).resolve().parents[2]
    return root / "projects" / subject / "artifacts" / "character_bible.json"


def _subject_ref_dir(subject: str, project_dir: Path | None = None) -> Path:
    """Return the directory where reference images are stored for a subject."""
    if project_dir is not None:
        return Path(project_dir) / "assets" / "characters"
    from pathlib import Path as P
    root = P(__file__).resolve().parents[2]
    return root / "projects" / subject / "assets" / "characters"


_NAME_STOPWORDS = {
    "A", "An", "And", "Answer", "Chapter", "Choose", "Class", "Complete",
    "Brain", "Colour", "Consonants", "Cross", "Different", "Do", "English",
    "Exercise", "Fill", "Find", "For", "From", "GK", "Gym", "Hello",
    "How", "In", "Lesson", "Let", "Maths", "Match", "Name", "Read",
    "Look", "Number", "Plants", "Put", "Recall", "Science", "Some", "The", "They",
    "These", "This", "True", "We", "What", "When", "Where", "Which",
    "Who", "Why", "Write",
}


def discover_recurring_characters(
    sections: list[dict[str, Any]],
    *,
    chapter_title: str,
    visual_style: str,
    max_characters: int = 6,
) -> list[dict[str, Any]]:
    """Build chapter-specific character specs without a subject registry.

    Structured character/entity metadata wins. As a zero-shot fallback, proper
    names that occur in at least two different motion sections are treated as
    recurring story characters. Descriptions contain only source context plus
    the approved chapter style; traits are not invented.
    """
    candidates: dict[str, dict[str, Any]] = {}

    def add(
        name: str,
        section: dict[str, Any],
        description: str = "",
        *,
        structured: bool = False,
        occurrence_count: int = 1,
        non_initial_count: int = 0,
    ) -> None:
        clean_name = " ".join(str(name or "").split()).strip(" .,:;!?()[]{}")
        if (
            not clean_name
            or clean_name in _NAME_STOPWORDS
            or any(part in _NAME_STOPWORDS for part in clean_name.split())
        ):
            return
        key = re.sub(r"[^a-z0-9]+", "-", clean_name.casefold()).strip("-")
        if not key:
            return
        item = candidates.setdefault(key, {
            "id": key,
            "name": clean_name,
            "contexts": [],
            "sections": [],
            "source_blocks": [],
            "occurrence_count": 0,
            "non_initial_count": 0,
            "structured": False,
        })
        sid = str(section.get("section_id") or "")
        if sid and sid not in item["sections"]:
            item["sections"].append(sid)
        source_ids = [
            str(value) for value in section.get("source_block_ids") or []
            if str(value)
        ] or [sid]
        for source_id in source_ids:
            if source_id and source_id not in item["source_blocks"]:
                item["source_blocks"].append(source_id)
        item["occurrence_count"] += max(1, occurrence_count)
        item["non_initial_count"] += max(0, non_initial_count)
        item["structured"] = bool(item["structured"] or structured)
        context = " ".join(
            str(description or section.get("source_text") or section.get("description") or "").split()
        )
        if context and context not in item["contexts"]:
            item["contexts"].append(context[:500])

    processed_source_blocks: set[tuple[str, ...]] = set()
    motion_sections = [
        section for section in sections if section.get("render_mode") == "video_gen"
    ]
    for section in motion_sections:
        structured = (
            section.get("characters")
            or section.get("recurring_entities")
            or section.get("visual_entities")
            or []
        )
        if isinstance(structured, (str, dict)):
            structured = [structured]
        for entity in structured:
            if isinstance(entity, dict):
                add(
                    str(entity.get("name") or entity.get("label") or entity.get("id") or ""),
                    section,
                    str(entity.get("description") or ""),
                    structured=True,
                )
            else:
                add(str(entity), section, structured=True)

        text = str(section.get("source_text") or section.get("description") or "")
        source_key = tuple(
            sorted(str(value) for value in section.get("source_block_ids") or [] if value)
        ) or (str(section.get("section_id") or ""),)
        if source_key in processed_source_blocks:
            continue
        processed_source_blocks.add(source_key)
        matches = list(
            re.finditer(r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?\b", text)
        )
        grouped: dict[str, list[re.Match[str]]] = {}
        for match in matches:
            grouped.setdefault(match.group(0), []).append(match)
        for name, name_matches in grouped.items():
            non_initial = 0
            for match in name_matches:
                prefix = text[:match.start()].rstrip()
                if prefix and not prefix.endswith((".", "?", "!", "\n", "•")):
                    non_initial += 1
            add(
                name,
                section,
                occurrence_count=len(name_matches),
                non_initial_count=non_initial,
            )

    recurring = [
        value for value in candidates.values()
        if value["structured"]
        or len(value["source_blocks"]) >= 2
        or (
            value["occurrence_count"] >= 2
            and value["non_initial_count"] >= 1
        )
    ]
    recurring.sort(key=lambda item: (-len(item["sections"]), item["id"]))
    result: list[dict[str, Any]] = []
    for item in recurring[:max_characters]:
        contexts = " ".join(item.pop("contexts")[:2]).strip()
        for internal_key in (
            "source_blocks", "occurrence_count", "non_initial_count", "structured"
        ):
            item.pop(internal_key, None)
        name_pattern = re.compile(rf"\b{re.escape(item['name'])}\b")
        matched_sections = [
            str(section.get("section_id"))
            for section in motion_sections
            if name_pattern.search(
                str(section.get("source_text") or section.get("description") or "")
            )
        ]
        item["sections"] = list(dict.fromkeys(item["sections"] + matched_sections))
        description = (
            f"Recurring character {item['name']} from {chapter_title}. "
            f"Source context: {contexts}. Style: {visual_style}. "
            "Single full-body character reference, neutral pose, plain background, "
            "polished child-friendly 3D animation, no text, no logo."
        )
        seed_bytes = hashlib.sha256(
            f"{chapter_title}|{item['id']}".encode("utf-8")
        ).digest()
        result.append({
            **item,
            "description": description,
            "seed": int.from_bytes(seed_bytes[:4], "big") & 0x7FFFFFFF,
        })
    return result


# ---------------------------------------------------------------------------
# Character Bible Generator
# ---------------------------------------------------------------------------

class CharacterBible:
    """Generate and persist canonical reference images for all characters in a subject."""

    def generate(
        self,
        subject: str,
        dry_run: bool = False,
        force: bool = False,
        *,
        characters: list[dict[str, Any]] | None = None,
        project_dir: str | Path | None = None,
        image_model_id: str = "flux",
    ) -> dict[str, Any]:
        """Generate reference images for all characters.

        Returns the bible dict {character_id: {"path": ..., "url": ...}}.
        If bible already exists and force=False, loads and returns it.
        """
        project_path = Path(project_dir) if project_dir is not None else None
        bible_path = _subject_bible_path(subject, project_path)
        characters = (
            CHARACTER_REGISTRY.get(subject, [])
            if characters is None
            else list(characters)
        )
        spec_fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "subject": subject,
                    "image_model_id": image_model_id,
                    "characters": characters,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        if bible_path.exists() and not force:
            existing = json.loads(bible_path.read_text(encoding="utf-8"))
            if existing.get("source_fingerprint") == spec_fingerprint:
                references = list((existing.get("characters") or {}).values())
                reusable = all(
                    Path(str(item.get("path") or "")).is_file()
                    and Path(str(item.get("path") or "")).stat().st_size > 0
                    for item in references
                )
                if dry_run or reusable:
                    return existing

        if not characters:
            bible = {
                "subject": subject,
                "source_fingerprint": spec_fingerprint,
                "characters": {},
            }
            bible_path.parent.mkdir(parents=True, exist_ok=True)
            bible_path.write_text(json.dumps(bible, indent=2), encoding="utf-8")
            return bible

        ref_dir = _subject_ref_dir(subject, project_path)
        ref_dir.mkdir(parents=True, exist_ok=True)

        bible: dict[str, Any] = {
            "subject": subject,
            "source_fingerprint": spec_fingerprint,
            "characters": {},
        }

        if dry_run:
            for char in characters:
                cid = char["id"]
                dummy = ref_dir / f"{cid}_ref.png"
                dummy.write_bytes(b"")
                bible["characters"][cid] = {
                    "name":        char["name"],
                    "path":        str(dummy),
                    "url":         "",
                    "description": char["description"],
                    "sections":    char["sections"],
                    "seed":        char["seed"],
                }
            bible_path.parent.mkdir(parents=True, exist_ok=True)
            bible_path.write_text(json.dumps(bible, indent=2), encoding="utf-8")
            return bible

        import requests
        api_key = os.environ.get("MODELSLAB_API_KEY", "")
        if not api_key:
            raise EnvironmentError("MODELSLAB_API_KEY not set")

        for char in characters:
            cid = char["id"]
            out_path = ref_dir / f"{cid}_ref.png"

            print(f"  [character bible] Generating reference for: {cid}...", end=" ", flush=True)

            payload = {
                "key":             api_key,
                "model_id":        image_model_id,
                "prompt":          char["description"],
                "negative_prompt": "text, watermark, logo, blurry, distorted anatomy, extra limbs",
                "width":           768,
                "height":          768,
                "seed":            char["seed"],
                "samples":         1,
            }

            try:
                resp = requests.post(
                    "https://modelslab.com/api/v6/images/text2img",
                    json=payload,
                    timeout=120,
                )
                data = resp.json()
            except Exception as exc:
                print(f"FAIL ({exc})")
                continue

            # Extract image URL
            img_url: str | None = None
            output = data.get("output") or data.get("url")
            if isinstance(output, list) and output:
                img_url = output[0]
            elif isinstance(output, str) and output:
                img_url = output

            # Handle async
            if not img_url and data.get("status") == "processing":
                job_id = data.get("id") or data.get("request_id")
                if job_id:
                    img_url = _poll_image(str(job_id), api_key)

            if not img_url:
                print(f"FAIL (no URL returned)")
                continue

            # Download
            try:
                dl = requests.get(img_url, timeout=60, stream=True)
                dl.raise_for_status()
                with open(out_path, "wb") as f:
                    for chunk in dl.iter_content(8192):
                        f.write(chunk)
                print(f"OK → {out_path.name}")
            except Exception as exc:
                print(f"FAIL (download: {exc})")
                continue

            bible["characters"][cid] = {
                "name":        char["name"],
                "path":        str(out_path),
                "url":         img_url,
                "description": char["description"],
                "sections":    char["sections"],
                "seed":        char["seed"],
            }
            time.sleep(0.5)

        bible_path.parent.mkdir(parents=True, exist_ok=True)
        bible_path.write_text(json.dumps(bible, indent=2), encoding="utf-8")
        print(f"\n  ✓ Character bible written: {bible_path}")
        return bible


def _poll_image(job_id: str, api_key: str, timeout: int = 90) -> str | None:
    """Poll for async image generation result."""
    import requests
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            resp = requests.post(
                "https://modelslab.com/api/v6/images/fetch",
                json={"key": api_key, "request_id": job_id},
                timeout=30,
            )
            data = resp.json()
            if data.get("status") == "success":
                out = data.get("output") or data.get("url")
                if isinstance(out, list) and out:
                    return out[0]
                if isinstance(out, str):
                    return out
            if data.get("status") in ("failed", "error"):
                return None
        except Exception:
            pass
        time.sleep(2)
    return None


# ---------------------------------------------------------------------------
# Character Consistency Manager
# ---------------------------------------------------------------------------

class CharacterConsistencyManager:
    """Wrap video_gen calls with h3-minimax-r2v reference injection.

    h3-minimax-r2v contract:
      - endpoint : POST /api/v6/video/img2video
      - model_id : h3-minimax-r2v
      - init_image: list of reference image URLs  (Image 1, Image 2, …)
      - prompt   : references assets as "Image 1", "Image 2" in text
      - duration : 5-15 seconds
      - max 12 total reference files
    """

    def __init__(self) -> None:
        self._bible_cache: dict[str, dict[str, Any]] = {}

    def _load_bible(self, subject: str) -> dict[str, Any]:
        if subject not in self._bible_cache:
            path = _subject_bible_path(subject)
            if path.exists():
                self._bible_cache[subject] = json.loads(path.read_text(encoding="utf-8"))
            else:
                self._bible_cache[subject] = {"characters": {}}
        return self._bible_cache[subject]

    def _characters_for_section(
        self, subject: str, section_id: str
    ) -> list[dict[str, Any]]:
        """Return all character entries that appear in this section."""
        bible = self._load_bible(subject)
        result = []
        for char_data in bible.get("characters", {}).values():
            if section_id in char_data.get("sections", []):
                result.append(char_data)
        return result

    def _persist_bible_url(self, subject: str, char_id: str, url: str) -> None:
        """Write the uploaded URL back into character_bible.json so it is reused
        on subsequent calls without re-uploading the same image file."""
        try:
            bible_path = _subject_bible_path(subject)
            if not bible_path.exists():
                return
            bible = json.loads(bible_path.read_text(encoding="utf-8"))
            if char_id in bible.get("characters", {}):
                bible["characters"][char_id]["url"] = url
                # Also update in-memory cache
                self._bible_cache[subject] = bible
                bible_path.write_text(json.dumps(bible, indent=2), encoding="utf-8")
        except Exception:
            pass  # Non-fatal — next call will re-upload once more

    def _upload_reference_image(self, path: str, api_key: str) -> str | None:
        """Upload a local image to ModelsLab and return its URL.
        
        Uses the /api/v6/realtime/upload endpoint if available,
        otherwise returns the local path as-is (for dry-run or local server).
        """
        import requests
        p = Path(path)
        if not p.exists() or p.stat().st_size == 0:
            return None
        try:
            with open(p, "rb") as fh:
                resp = requests.post(
                    "https://modelslab.com/api/v6/realtime/upload",
                    data={"key": api_key},
                    files={"file": (p.name, fh, "image/png")},
                    timeout=60,
                )
            data = resp.json()
            url = data.get("url") or data.get("output")
            if isinstance(url, list):
                url = url[0]
            return url if url else None
        except Exception:
            return None

    def build_consistent_prompt(
        self,
        scene_description: str,
        characters: list[dict[str, Any]],
    ) -> str:
        """Build a prompt that references each character by their Image N position."""
        if not characters:
            return (
                f"{scene_description} "
                "Fixed camera, no text, no watermark, child-safe, "
                "flat educational illustration style."
            )

        ref_lines = []
        for i, char in enumerate(characters, 1):
            ref_lines.append(
                f"Image {i} shows {char['name']} — "
                f"keep this character's appearance exactly consistent throughout: "
                f"same face, same colours, same proportions, same style."
            )

        refs = " ".join(ref_lines)
        return (
            f"{refs} "
            f"Scene: {scene_description} "
            "Keep all referenced characters visually identical to their reference images. "
            "Fixed camera, no text, no watermark, no distorted anatomy, child-safe, "
            "flat educational illustration style, warm palette."
        )

    def generate_consistent_clip(
        self,
        subject: str,
        section_id: str,
        scene_description: str,
        output_path: Path,
        duration: int = 5,
        negative_prompt: str = "",
        seed: int | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Generate a video clip with character consistency enforced via h3-minimax-r2v.

        Returns dict: {success, video_path, model_used, cost_usd, error}
        """
        if dry_run:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"")
            return {
                "success":    True,
                "video_path": str(output_path),
                "model_used": "h3-minimax-r2v",
                "cost_usd":   0.0,
                "error":      "",
            }

        api_key = os.environ.get("MODELSLAB_API_KEY", "")
        if not api_key:
            return {"success": False, "video_path": "", "model_used": "",
                    "cost_usd": 0.0, "error": "MODELSLAB_API_KEY not set"}

        import requests

        characters = self._characters_for_section(subject, section_id)

        # Upload reference images (max 4 to stay well within 12-file limit)
        ref_images: list[str] = []
        for char in characters[:4]:
            char_path = char.get("path", "")
            if not char_path:
                continue
            # Use cached URL if already uploaded (stored in bible JSON).
            # Only call _upload_reference_image when URL is absent or empty.
            url = char.get("url", "")
            if not url:
                url = self._upload_reference_image(char_path, api_key)
                if url:
                    # Persist the URL back into the bible so future calls
                    # don't re-upload the same file.
                    char["url"] = url
                    self._persist_bible_url(subject, char.get("id", ""), url)
            if url:
                ref_images.append(url)

        prompt = self.build_consistent_prompt(scene_description, characters[:len(ref_images)])

        neg = negative_prompt or (
            "text, watermark, logo, inconsistent character, different face, "
            "looping, camera movement, zoom, pan, blur, distorted anatomy, "
            "duplicate subjects, morphing style"
        )

        payload: dict[str, Any] = {
            "key":      api_key,
            "model_id": "h3-minimax-r2v",
            "prompt":   prompt,
            "duration": str(min(15, max(5, duration))),
            "negative_prompt": neg,
        }
        if ref_images:
            payload["init_image"] = ref_images
        if seed is not None:
            payload["seed"] = seed

        # If no reference images found, fall back to h3-minimax-t2v via
        # the text2video endpoint (img2video requires at least one init_image).
        if not ref_images:
            payload["model_id"] = "h3-minimax-t2v"
            payload["prompt"]   = scene_description + " Fixed camera, no text, no watermark, child-safe."
            try:
                resp = requests.post(
                    "https://modelslab.com/api/v6/video/text2video",
                    json=payload,
                    timeout=60,
                )
                data = resp.json()
            except Exception as exc:
                return {"success": False, "video_path": "", "model_used": "h3-minimax-t2v",
                        "cost_usd": 0.0, "error": str(exc)}
        else:
            try:
                resp = requests.post(
                    "https://modelslab.com/api/v6/video/img2video",
                    json=payload,
                    timeout=60,
                )
                data = resp.json()
            except Exception as exc:
                return {"success": False, "video_path": "", "model_used": "h3-minimax-r2v",
                        "cost_usd": 0.0, "error": str(exc)}

        # Poll for async completion
        video_url: str | None = None
        status = data.get("status", "")
        if status == "processing":
            job_id = data.get("id") or data.get("request_id")
            if job_id:
                video_url = _poll_video(str(job_id), api_key)
        elif status == "success":
            out = data.get("output") or data.get("url")
            video_url = out[0] if isinstance(out, list) else out

        if not video_url:
            return {"success": False, "video_path": "", "model_used": "h3-minimax-r2v",
                    "cost_usd": 0.0, "error": f"No video URL returned: {str(data)[:200]}"}

        # Download
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            dl = requests.get(video_url, timeout=120, stream=True)
            dl.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in dl.iter_content(8192):
                    f.write(chunk)
        except Exception as exc:
            return {"success": False, "video_path": "", "model_used": "h3-minimax-r2v",
                    "cost_usd": 0.0, "error": f"Download failed: {exc}"}

        model_used = "h3-minimax-r2v" if ref_images else "h3-minimax-t2v"
        return {
            "success":    True,
            "video_path": str(output_path),
            "model_used": model_used,
            "cost_usd":   0.0,
            "error":      "",
        }


def _poll_video(job_id: str, api_key: str, timeout: int = 300) -> str | None:
    """Poll for async video generation result."""
    import requests
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            resp = requests.post(
                "https://modelslab.com/api/v6/video/fetch",
                json={"key": api_key, "request_id": job_id},
                timeout=30,
            )
            data = resp.json()
            if data.get("status") == "success":
                out = data.get("output") or data.get("url")
                if isinstance(out, list) and out:
                    return out[0]
                if isinstance(out, str):
                    return out
            if data.get("status") in ("failed", "error"):
                return None
        except Exception:
            pass
        time.sleep(3)
    return None


# ---------------------------------------------------------------------------
# CLI — generate bible for a subject
# ---------------------------------------------------------------------------

def _cli() -> None:
    import argparse
    import sys as _sys

    ap = argparse.ArgumentParser(description="Generate character reference bible.")
    ap.add_argument("--subject", required=True, choices=["evs", "english", "maths"])
    ap.add_argument("--force",   action="store_true", help="Regenerate even if bible exists")
    ap.add_argument("--dry-run", dest="dry_run", action="store_true")
    args = ap.parse_args()

    bible = CharacterBible().generate(
        subject=args.subject,
        dry_run=args.dry_run,
        force=args.force,
    )
    chars = bible.get("characters", {})
    print(f"\n✓ Character bible for '{args.subject}': {len(chars)} characters")
    for cid, cd in chars.items():
        print(f"  {cid:20s} → {cd.get('path','')}")


if __name__ == "__main__":
    _cli()

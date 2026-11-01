"""
JSON Spec Exporter — build drama-spec.json dari DB records.

Schema mengikuti drama-spec.schema.json (draft-07).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .db import Database


# ============================================================
# FIELD CONSTANTS
# ============================================================
DEFAULT_VIDEO_ENGINE = "omni-1.1-flash"
DEFAULT_RESOLUTION = "360p"
DEFAULT_ASPECT_RATIO = "9:16"
DEFAULT_AUDIO_GENERATE = True
DEFAULT_DURATION_SEC = 10
CREDITS_PER_SEGMENT_360P = 7
CREDITS_PER_SEGMENT_720P = 15
DAILY_FREE_CREDITS = 50


# ============================================================
# HELPERS
# ============================================================
def slugify_name(name: str) -> str:
    """Slugify nama untuk ID — e.g., 'Gajah Mada' → 'gajah_mada'."""
    import re
    import unicodedata

    text = unicodedata.normalize("NFKD", name)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = text.strip("_")
    return text[:50] or "untitled"


def normalize_shot_type(shot: str) -> str:
    if not shot:
        return "medium"
    s = shot.lower()
    if "extreme" in s:
        return "extreme-close-up"
    if "close" in s:
        return "close-up"
    if "wide" in s or "full" in s:
        return "wide"
    return "medium"


def normalize_angle(angle: str) -> str:
    if not angle:
        return "eye-level"
    a = angle.lower()
    if "low" in a:
        return "low-angle"
    if "high" in a:
        return "high-angle"
    if "side" in a:
        return "side"
    return "eye-level"


def normalize_movement(movement: str) -> str:
    if not movement:
        return "fixed"
    m = movement.lower()
    if "push" in m or "dolly" in m:
        return "push-in"
    if "pull" in m:
        return "pull-out"
    if "pan" in m:
        return "pan"
    if "tilt" in m:
        return "tilt"
    if "track" in m:
        return "tracking"
    return "fixed"


def map_bgm_mood(mood: str) -> str:
    if not mood:
        return "epic"
    m = mood.lower()
    if "triumph" in m or "victor" in m:
        return "triumphant"
    if "myster" in m or "mystic" in m:
        return "mysterious"
    if "sad" in m or "melanc" in m or "blue" in m:
        return "melancholic"
    if "tense" in m or "thrill" in m:
        return "tense"
    return "epic"


def infer_era(tags_or_era: str) -> str:
    """Infer era dari string (bisa tags atau era langsung)."""
    if not tags_or_era:
        return "majapahit"
    s = tags_or_era.lower()
    if "mataram_kuno" in s or "sanjaya" in s or "syailendra" in s:
        return "mataram_kuno"
    if "majapahit" in s:
        return "majapahit"
    if "mataram_islam" in s or "sultan_agung" in s or "senopati" in s:
        return "mataram_islam"
    if "sriwijaya" in s:
        return "sriwijaya"
    if "samudera_pasai" in s or "samudra_pasai" in s:
        return "samudera_pasai"
    if "ternate_tidore" in s:
        return "ternate_tidore"
    return "majapahit"


# ============================================================
# EXPORTER
# ============================================================
class SpecExporter:
    """Build drama-spec.json dari SQLite DB per drama."""

    def __init__(self, db_path: Path | str):
        self.db = Database(db_path)

    def export_episode(
        self,
        drama_id: int,
        episode_id: int,
        output_path: Path | str,
        audio_locale: Optional[str] = None,
        resolution: str = DEFAULT_RESOLUTION,
    ) -> dict:
        """
        Export satu episode ke drama-spec.json.

        Returns:
            Spec dict (juga di-write ke output_path)
        """
        with self.db.conn as conn:
            # === Drama meta ===
            cur = conn.execute("SELECT * FROM dramas WHERE id = ?", (drama_id,))
            drama = cur.fetchone()
            if not drama:
                raise ValueError(f"Drama id={drama_id} tidak ditemukan")

            # === Episode ===
            cur = conn.execute("SELECT * FROM episodes WHERE id = ?", (episode_id,))
            episode = cur.fetchone()
            if not episode:
                raise ValueError(f"Episode id={episode_id} tidak ditemukan")

            # === Characters ===
            cur = conn.execute(
                "SELECT * FROM characters WHERE drama_id = ? AND deleted_at IS NULL ORDER BY id",
                (drama_id,),
            )
            characters_raw = cur.fetchall()

            # === Scenes ===
            cur = conn.execute(
                "SELECT * FROM scenes WHERE drama_id = ? AND deleted_at IS NULL ORDER BY id",
                (drama_id,),
            )
            scenes_raw = cur.fetchall()

            # === Props ===
            cur = conn.execute(
                "SELECT * FROM props WHERE drama_id = ? AND deleted_at IS NULL ORDER BY id",
                (drama_id,),
            )
            props_raw = cur.fetchall()

            # === Storyboards ===
            cur = conn.execute(
                """SELECT s.* FROM storyboards s
                   WHERE s.episode_id = ? AND s.deleted_at IS NULL
                   ORDER BY s.storyboard_number""",
                (episode_id,),
            )
            storyboards_raw = cur.fetchall()

            # === Build spec ===
            spec = self._build_spec(
                drama=dict(drama),
                episode=dict(episode),
                characters=[dict(c) for c in characters_raw],
                scenes=[dict(s) for s in scenes_raw],
                props=[dict(p) for p in props_raw],
                storyboards=[dict(s) for s in storyboards_raw],
                audio_locale=audio_locale,
                resolution=resolution,
            )

        # Write to file
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(spec, f, ensure_ascii=False, indent=2)

        return spec

    def _build_spec(
        self,
        drama: dict,
        episode: dict,
        characters: list[dict],
        scenes: list[dict],
        props: list[dict],
        storyboards: list[dict],
        audio_locale: Optional[str],
        resolution: str,
    ) -> dict:
        """Build spec dict sesuai schema."""

        # === Meta ===
        meta = {
            "drama_id": f"drama_{slugify_name(drama['title'])}_{drama['id']:03d}",
            "title": drama["title"],
            "era": infer_era(drama.get("era", "")),
            "language": drama.get("language", "jv"),
            "audio_locale": audio_locale or drama.get("audio_locale", "jv"),
            "style_preset": drama.get("style_preset", "nusantara-epic"),
            "target_platform": drama.get("target_platform", "youtube_shorts"),
            "aspect_ratio": drama.get("aspect_ratio", DEFAULT_ASPECT_RATIO),
            "license": "commercial_safe",
            "video_engine": DEFAULT_VIDEO_ENGINE,
            "description": drama.get("description", ""),
        }

        # === Assets ===
        # Build lookup tables: db_id → spec_id
        char_lookup = {c["id"]: f"char_{slugify_name(c['name'])}_{c['id']:03d}" for c in characters}
        scene_lookup = {s["id"]: f"scene_{slugify_name(s['name'])}_{s['id']:03d}" for s in scenes}
        prop_lookup = {p["id"]: f"prop_{slugify_name(p['name'])}_{p['id']:03d}" for p in props}

        assets = {
            "characters": [
                {
                    "id": char_lookup[c["id"]],
                    "name": c["name"],
                    "role": c.get("role", "supporting"),
                    "appearance": c.get("appearance", ""),
                    "styling": c.get("styling", ""),
                    "image_url": c.get("image_local_path", "") or f"~/drama-nusantara/assets/characters/{slugify_name(c['name'])}_turnaround.png",
                    "image_gen_prompt": c.get("image_gen_prompt", ""),
                }
                for c in characters
            ],
            "scenes": [
                {
                    "id": scene_lookup[s["id"]],
                    "name": s["name"],
                    "location": s.get("location", ""),
                    "time": s.get("time_of_day", ""),
                    "visual_prompt": s.get("visual_prompt", ""),
                    "image_url": s.get("image_local_path", ""),
                }
                for s in scenes
            ],
            "props": [
                {
                    "id": prop_lookup[p["id"]],
                    "name": p["name"],
                    "visual_prompt": p.get("visual_prompt", ""),
                    "image_url": p.get("image_local_path", ""),
                }
                for p in props
            ],
        }

        # === Episodes ===
        with self.db.conn as conn:
            segments = []
            for sb in storyboards:
                # Get character refs
                cur = conn.execute(
                    "SELECT character_id FROM storyboard_characters WHERE storyboard_id = ?",
                    (sb["id"],),
                )
                char_refs = [char_lookup[r[0]] for r in cur.fetchall() if r[0] in char_lookup]

                # Get scene ref (single)
                cur = conn.execute(
                    "SELECT scene_id FROM storyboard_scenes WHERE storyboard_id = ? LIMIT 1",
                    (sb["id"],),
                )
                scene_row = cur.fetchone()
                scene_ref = scene_lookup[scene_row[0]] if scene_row and scene_row[0] in scene_lookup else None

                # Get prop refs
                cur = conn.execute(
                    "SELECT prop_id FROM storyboard_props WHERE storyboard_id = ?",
                    (sb["id"],),
                )
                prop_refs = [prop_lookup[r[0]] for r in cur.fetchall() if r[0] in prop_lookup]

                # Get audio
                cur = conn.execute(
                    "SELECT * FROM segment_audio WHERE storyboard_id = ?",
                    (sb["id"],),
                )
                audio_row = cur.fetchone()
                audio_data = dict(audio_row) if audio_row else {}

                seg = {
                    "segment_id": f"seg_ep{episode['id']:03d}_{sb['storyboard_number']:02d}",
                    "segment_number": sb["storyboard_number"],
                    "omni_prompt": sb.get("omni_prompt", ""),
                    "character_refs": char_refs,
                    "scene_ref": scene_ref,
                    "prop_refs": prop_refs,
                    "camera": {
                        "shot_type": normalize_shot_type(sb.get("shot_type")),
                        "movement": normalize_movement(sb.get("movement")),
                        "angle": normalize_angle(sb.get("angle")),
                    },
                    "audio": {
                        "dialogue": audio_data.get("dialogue_jawa", ""),
                        "dialogue_translation": audio_data.get("dialogue_indonesia", ""),
                        "narration": audio_data.get("narration", ""),
                        "ambient": audio_data.get("ambient_sfx", ""),
                        "bgm_mood": map_bgm_mood(audio_data.get("bgm_mood")),
                        "voice_style": audio_data.get("voice_style", ""),
                    },
                    "transition_out": "hard-cut" if sb["storyboard_number"] == 1 else ("match-cut" if sb["storyboard_number"] < len(storyboards) else "fade-to-black"),
                    "generation_config": {
                        "model": DEFAULT_VIDEO_ENGINE,
                        "duration_sec": DEFAULT_DURATION_SEC,
                        "resolution": resolution,
                        "aspect_ratio": DEFAULT_ASPECT_RATIO,
                        "audio_generate": DEFAULT_AUDIO_GENERATE,
                        "seed": 42 + sb["storyboard_number"],
                    },
                }
                segments.append(seg)

        # Calculate credits
        credits_per_seg = CREDITS_PER_SEGMENT_360P if resolution == "360p" else CREDITS_PER_SEGMENT_720P
        total_credits = len(segments) * credits_per_seg

        episodes_spec = [
            {
                "episode_id": f"ep_{episode['episode_number']:03d}",
                "episode_number": episode["episode_number"],
                "title": episode["title"],
                "duration_sec": sum(s["generation_config"]["duration_sec"] for s in segments),
                "script_id": f"ep_{episode['id']:03d}_script",
                "segments": segments,
                "estimated_credits": total_credits,
            }
        ]

        # === Production plan ===
        eps_per_day = DAILY_FREE_CREDITS / total_credits if total_credits > 0 else 0

        production_plan = {
            "daily_credit_budget": DAILY_FREE_CREDITS,
            "episode_duration_sec": episodes_spec[0]["duration_sec"] if episodes_spec else 30,
            "credits_per_episode": total_credits,
            "episodes_per_day_realistic": round(eps_per_day, 1),
            "episodes_per_month_realistic": int(eps_per_day * 30),
            "total_episodes_target": 1,
            "estimated_days_to_complete": 1,
        }

        # === Final spec ===
        spec = {
            "meta": meta,
            "assets": assets,
            "episodes": episodes_spec,
            "production_plan": production_plan,
            "_generated_at": datetime.now(timezone.utc).isoformat(),
            "_generator": "drama-nusantara-tui v0.1.0",
        }

        return spec

    def close(self) -> None:
        self.db.close()

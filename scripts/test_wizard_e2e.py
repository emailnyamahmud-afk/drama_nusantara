"""
Test script — bypass questionary interactive prompts dengan direct method calls.
Simulasikan full wizard flow: Step 2 → 3 → 4 → 5.
"""
import sys
import os

# Add src to path
sys.path.insert(0, "/home/z/my-project/drama-nusantara-tui/src")

# Setup test env
os.environ["HOME"] = "/tmp/drama-test-home"

from pathlib import Path
import shutil

# Clean slate
test_home = Path("/tmp/drama-test-home")
test_storage = Path("/tmp/drama-storage")
shutil.rmtree(test_home / ".drama-nusantara", ignore_errors=True)
shutil.rmtree(test_storage, ignore_errors=True)
test_home.mkdir(parents=True, exist_ok=True)
test_storage.mkdir(parents=True, exist_ok=True)

# Init config manually
from drama_nusantara_tui.config import ConfigManager, HOME_CONFIG_DIR, DRAMAS_INDEX_DB
from drama_nusantara_tui.db import DramasIndexDB

HOME_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
cm = ConfigManager()
cm.save(cm.load().__class__(
    storage_root=str(test_storage),
    gemini_api_key="test-key-123",
    editor="auto",
    image_viewer="auto",
))

# Init index DB
index_db = DramasIndexDB(DRAMAS_INDEX_DB)
index_db.init_schema()

# Create drama via direct DB call
from drama_nusantara_tui.config import slugify, get_drama_paths
from drama_nusantara_tui.db import Database
from datetime import datetime, timezone

title = "Sumpah Palapa"
slug = slugify(title)
storage_path = test_storage / slug

drama_paths = get_drama_paths(drama_id=0, drama_slug=slug, storage_root=str(test_storage))
drama_paths.ensure_dirs()

# Init drama DB
drama_db = Database(drama_paths.db_path)
drama_db.init_schema()

# Add drama to index
drama_id = index_db.add_drama(
    slug=slug, title=title, era="majapahit", language="jv",
    storage_path=str(storage_path), db_path=str(drama_paths.db_path),
)

# Add drama to drama DB
now = datetime.now(timezone.utc).isoformat()
with drama_db.conn as conn:
    conn.execute(
        """INSERT INTO dramas (slug, title, description, era, language, audio_locale,
                                target_platform, aspect_ratio, storage_path, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (slug, title, "Test drama", "majapahit", "jv", "jv",
         "youtube_shorts", "9:16", str(storage_path), now, now),
    )
drama_db.close()

print(f"✓ Drama created: id={drama_id}")

# === Test wizard with mock AI ===
from drama_nusantara_tui.wizard import ProductionWizard

w = ProductionWizard(drama_id=drama_id, use_mock_ai=True)

# Pastikan episode 1 dibuat
with w.db.conn as conn:
    cur = conn.execute(
        "SELECT id FROM episodes WHERE drama_id = ? AND deleted_at IS NULL ORDER BY episode_number LIMIT 1",
        (drama_id,),
    )
    row = cur.fetchone()
    if row:
        w.current_episode_id = row[0]
    else:
        w._create_episode_1()

print(f"✓ Wizard instantiated, episode_id={w.current_episode_id}")

# Test Step 2 — call AI generate directly
print("\n" + "="*60)
print("STEP 2: Generate Naskah")
print("="*60)

from drama_nusantara_tui.ai import MockAIProvider
mock_ai = MockAIProvider()

draft = mock_ai.generate_naskah(
    format_type="panyandra",
    context="Wisuda prajurit Majapahit",
    characters=["Gajah Mada", "Prajurit Muda"],
    moment="Setelah kemenangan perbatasan",
    era="majapahit",
    language="jv",
)

print(f"✓ Draft generated (quality ~{draft.estimated_quality}%)")
print(f"  Format: {draft.format_type}")
print(f"  Characters: {draft.characters}")
print(f"  Word count: {len(draft.raw_draft.split())}")
print(f"\n--- Preview (first 300 chars) ---")
print(draft.raw_draft[:300])
print("...")

# Save draft directly to DB (skip editor)
now = datetime.now(timezone.utc).isoformat()
with w.db.conn as conn:
    cur = conn.execute(
        """UPDATE episodes
           SET script_content = ?, content = ?, script_source = ?, status = 'scripted', updated_at = ?
           WHERE id = ?""",
        (draft.raw_draft, "Wisuda prajurit Majapahit", "ai_edited", now, w.current_episode_id),
    )
print(f"\n✓ Saved to episode #{w.current_episode_id}")

# === Test Step 3 — extract assets ===
print("\n" + "="*60)
print("STEP 3: Reference Image")
print("="*60)

characters, scenes, props = mock_ai.extract_assets(draft.raw_draft, "majapahit")
print(f"✓ Extracted: {len(characters)} chars, {len(scenes)} scenes, {len(props)} props")

# Save to DB
now = datetime.now(timezone.utc).isoformat()
with w.db.conn as conn:
    # Characters
    for c in characters:
        image_prompt = mock_ai.generate_image_prompt("character", {
            "name": c.name, "appearance": c.appearance, "styling": c.styling
        }, "nusantara-epic")
        cur = conn.execute(
            """INSERT INTO characters
               (drama_id, name, role, appearance, styling, description, voice_style, image_gen_prompt, flow_upload_status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
            (w.drama_id, c.name, c.role, c.appearance, c.styling, c.description, c.voice_style, image_prompt, now, now),
        )
        char_id = cur.lastrowid
        conn.execute(
            "INSERT OR IGNORE INTO episode_characters (episode_id, character_id) VALUES (?, ?)",
            (w.current_episode_id, char_id),
        )
        print(f"  ✓ Char: {c.name} ({c.role})")

    # Scenes
    for s in scenes:
        image_prompt = mock_ai.generate_image_prompt("scene", {
            "name": s.name, "location": s.location,
            "time_of_day": s.time_of_day, "visual_prompt": s.visual_prompt
        }, "nusantara-epic")
        cur = conn.execute(
            """INSERT INTO scenes
               (drama_id, name, location, time_of_day, visual_prompt, lighting, image_gen_prompt, flow_upload_status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
            (w.drama_id, s.name, s.location, s.time_of_day, s.visual_prompt, s.lighting, image_prompt, now, now),
        )
        scene_id = cur.lastrowid
        conn.execute(
            "INSERT OR IGNORE INTO episode_scenes (episode_id, scene_id) VALUES (?, ?)",
            (w.current_episode_id, scene_id),
        )
        print(f"  ✓ Scene: {s.name}")

    # Props
    for p in props:
        image_prompt = mock_ai.generate_image_prompt("prop", {
            "name": p.name, "visual_prompt": p.visual_prompt
        }, "nusantara-epic")
        cur = conn.execute(
            """INSERT INTO props
               (drama_id, name, type, visual_prompt, image_gen_prompt, flow_upload_status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)""",
            (w.drama_id, p.name, p.type, p.visual_prompt, image_prompt, now, now),
        )
        prop_id = cur.lastrowid
        conn.execute(
            "INSERT OR IGNORE INTO episode_props (episode_id, prop_id) VALUES (?, ?)",
            (w.current_episode_id, prop_id),
        )
        print(f"  ✓ Prop: {p.name}")

# === Test Step 4 — storyboard ===
print("\n" + "="*60)
print("STEP 4: Storyboard Segment")
print("="*60)

segments = mock_ai.generate_storyboard(
    naskah=draft.raw_draft,
    characters=characters,
    scenes=scenes,
    props=props,
    target_duration_sec=30,
    era="majapahit",
    language="jv",
)

print(f"✓ Generated {len(segments)} segments (× 10s = {len(segments)*10}s)")

# Save to DB
with w.db.conn as conn:
    # Load character/scene/prop id lookup
    cur = conn.execute("SELECT id, name FROM characters WHERE deleted_at IS NULL")
    char_lookup = {r[1]: r[0] for r in cur.fetchall()}
    cur = conn.execute("SELECT id, name FROM scenes WHERE deleted_at IS NULL")
    scene_lookup = {r[1]: r[0] for r in cur.fetchall()}
    cur = conn.execute("SELECT id, name FROM props WHERE deleted_at IS NULL")
    prop_lookup = {r[1]: r[0] for r in cur.fetchall()}

    for seg in segments:
        cur = conn.execute(
            """INSERT INTO storyboards
               (episode_id, storyboard_number, title, shot_type, angle, movement,
                description, atmosphere, omni_prompt, duration_sec, flow_generation_status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
            (w.current_episode_id, seg.segment_number, seg.title,
             seg.shot_type, seg.angle, seg.movement,
             seg.description, seg.atmosphere, seg.omni_prompt, seg.duration_sec, now, now),
        )
        sb_id = cur.lastrowid

        # Audio
        conn.execute(
            """INSERT INTO segment_audio
               (storyboard_id, dialogue_jawa, dialogue_indonesia, dialogue_source,
                narration, ambient_sfx, bgm_mood, voice_style)
               VALUES (?, ?, ?, 'ai_edited', ?, ?, ?, ?)""",
            (sb_id, seg.dialogue_jawa, seg.dialogue_indonesia,
             "", seg.ambient_sfx, seg.bgm_mood, seg.voice_style),
        )

        # Link
        for cn in seg.character_refs:
            if cn in char_lookup:
                conn.execute(
                    "INSERT OR IGNORE INTO storyboard_characters (storyboard_id, character_id) VALUES (?, ?)",
                    (sb_id, char_lookup[cn]),
                )
        if seg.scene_ref in scene_lookup:
            conn.execute(
                "INSERT OR IGNORE INTO storyboard_scenes (storyboard_id, scene_id) VALUES (?, ?)",
                (sb_id, scene_lookup[seg.scene_ref]),
            )
        for pn in seg.prop_refs:
            if pn in prop_lookup:
                conn.execute(
                    "INSERT OR IGNORE INTO storyboard_props (storyboard_id, prop_id) VALUES (?, ?)",
                    (sb_id, prop_lookup[pn]),
                )

        # Update episode
        conn.execute(
            "UPDATE episodes SET status = 'storyboarded', duration_sec = ?, updated_at = ? WHERE id = ?",
            (len(segments) * 10, now, w.current_episode_id),
        )

        print(f"  ✓ Seg {seg.segment_number}: {seg.title}")
        print(f"    Camera: {seg.shot_type}/{seg.movement}/{seg.angle}")
        print(f"    Dialog Jawa: {seg.dialogue_jawa[:60]}...")

# === Test Step 5 — export JSON ===
print("\n" + "="*60)
print("STEP 5: Export JSON Spec")
print("="*60)

from drama_nusantara_tui.exporter import SpecExporter

output_path = w.drama_paths.exports_dir / "drama_001_ep01_spec.json"
exporter = SpecExporter(w.drama_paths.db_path)

spec = exporter.export_episode(
    drama_id=w.drama_id,
    episode_id=w.current_episode_id,
    output_path=output_path,
    audio_locale="jv",
    resolution="360p",
)
exporter.close()

print(f"✓ JSON spec exported!")
print(f"  File: {output_path}")
print(f"  Size: {output_path.stat().st_size} bytes")
print(f"  Drama: {spec['meta']['title']}")
print(f"  Era: {spec['meta']['era']}")
print(f"  License: {spec['meta']['license']}")
print(f"  Episodes: {len(spec['episodes'])}")
print(f"  Segments per ep: {len(spec['episodes'][0]['segments'])}")
print(f"  Characters: {len(spec['assets']['characters'])}")
print(f"  Scenes: {len(spec['assets']['scenes'])}")
print(f"  Props: {len(spec['assets']['props'])}")
print(f"  Total credits: {spec['episodes'][0]['estimated_credits']}")
print(f"  Episodes/day: {spec['production_plan']['episodes_per_day_realistic']}")
print(f"  Episodes/month: {spec['production_plan']['episodes_per_month_realistic']}")

# Validate JSON
import json
with open(output_path) as f:
    parsed = json.load(f)
print(f"\n✓ JSON parse OK")

# Show sample segment
print("\n--- Sample Segment 1 ---")
seg1 = spec['episodes'][0]['segments'][0]
print(f"  segment_id: {seg1['segment_id']}")
print(f"  omni_prompt: {seg1['omni_prompt'][:80]}...")
print(f"  dialogue: {seg1['audio']['dialogue']}")
print(f"  voice_style: {seg1['audio']['voice_style']}")
print(f"  bgm_mood: {seg1['audio']['bgm_mood']}")

w.db.close()

print("\n" + "="*60)
print("✅ ALL STEPS PASSED")
print("="*60)

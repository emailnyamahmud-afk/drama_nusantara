"""
SQLite schema untuk TUI — terinspirasi struktur huobao-drama, diadaptasi untuk konteks Jawa.

Catatan: Schema ini ditulis ulang dari nol. Tidak ada kode yang di-fork dari huobao-drama.
Struktur tabel mengikuti konvensi umum (dramas, episodes, characters, dst) karena ini pola
yang natural untuk aplikasi manajemen produksi video — bukan karena copy code.

Perbedaan dari huobao-drama:
- Tidak ada frontend Nuxt / desktop Electron (TUI saja)
- Tambah tabel vocabulary_jawa untuk kamus validator (next phase)
- Tambah tabel template_panatacara untuk struktur acara baku (next phase)
- Field audio locale: jv (Jawa) sebagai first-class citizen
- Field image_local_path eksplisit untuk track file di HDD eksternal
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ============================================================
# SCHEMA DDL
# ============================================================
SCHEMA_SQL = """
-- ============================================================
-- DRAMAS — project drama induk
-- ============================================================
CREATE TABLE IF NOT EXISTS dramas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT,
    era TEXT NOT NULL DEFAULT 'majapahit',  -- mataram_kuno | majapahit | mataram_islam | sriwijaya | samudera_pasai | ternate_tidore | custom
    language TEXT NOT NULL DEFAULT 'jv',      -- jv | id | su | min | jv-id-mix
    audio_locale TEXT NOT NULL DEFAULT 'jv',  -- jv | id | jv-id-mix
    style_preset TEXT DEFAULT 'nusantara-epic',
    target_platform TEXT DEFAULT 'youtube_shorts',  -- youtube_shorts | ig_reels | tiktok
    aspect_ratio TEXT DEFAULT '9:16',
    total_episodes INTEGER DEFAULT 1,
    status TEXT DEFAULT 'draft',              -- draft | in_production | completed | published
    tags TEXT,                                 -- comma-separated, mis: "majapahit,sejarah,jawa"
    metadata TEXT,                             -- JSON blob untuk extra metadata
    storage_path TEXT NOT NULL,                -- path absolut ke folder drama di HDD
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT
);

-- ============================================================
-- EPISODES — episode per drama
-- ============================================================
CREATE TABLE IF NOT EXISTS episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    drama_id INTEGER NOT NULL,
    episode_number INTEGER NOT NULL,
    title TEXT NOT NULL,
    content TEXT,                              -- raw input / synopsis dari user
    script_content TEXT,                       -- formatted naskah (post-AI edit)
    script_source TEXT DEFAULT 'user',         -- user | ai_draft | ai_edited
    description TEXT,
    duration_sec INTEGER DEFAULT 30,
    status TEXT DEFAULT 'draft',               -- draft | scripted | storyboarded | generated | exported | published
    video_url TEXT,                            -- path lokal ke MP4 final
    thumbnail TEXT,
    resolution TEXT DEFAULT '360p',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT,
    FOREIGN KEY (drama_id) REFERENCES dramas(id) ON DELETE CASCADE,
    UNIQUE(drama_id, episode_number)
);

-- ============================================================
-- CHARACTERS — karakter per drama (reference image turnaround)
-- ============================================================
CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    drama_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    role TEXT,                                 -- protagonist | antagonist | supporting
    appearance TEXT,                           -- deskripsi fisik
    styling TEXT,                              -- kostum, aksesori
    description TEXT,                          -- background story
    image_local_path TEXT,                     -- path ke turnaround PNG di HDD
    image_gen_prompt TEXT,                     -- prompt untuk Nano Banana Pro
    flow_upload_status TEXT DEFAULT 'pending', -- pending | uploaded | failed
    voice_style TEXT,                          -- custom voice prompt untuk Omni
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT,
    FOREIGN KEY (drama_id) REFERENCES dramas(id) ON DELETE CASCADE
);

-- ============================================================
-- SCENES — lokasi (reference image 1-angle)
-- ============================================================
CREATE TABLE IF NOT EXISTS scenes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    drama_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    location TEXT,                             -- alamat/deskripsi lokasi
    time_of_day TEXT,                          -- pagi | siang | sore | senja | malam
    visual_prompt TEXT,
    lighting TEXT,
    image_local_path TEXT,
    image_gen_prompt TEXT,
    flow_upload_status TEXT DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT,
    FOREIGN KEY (drama_id) REFERENCES dramas(id) ON DELETE CASCADE
);

-- ============================================================
-- PROPS — prop kunci (reference image product shot)
-- ============================================================
CREATE TABLE IF NOT EXISTS props (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    drama_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    type TEXT,                                 -- weapon | clothing | document | jewelry | other
    visual_prompt TEXT,
    image_local_path TEXT,
    image_gen_prompt TEXT,
    flow_upload_status TEXT DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT,
    FOREIGN KEY (drama_id) REFERENCES dramas(id) ON DELETE CASCADE
);

-- ============================================================
-- EPISODE-CHARACTER/SCENE/PROP many-to-many
-- ============================================================
CREATE TABLE IF NOT EXISTS episode_characters (
    episode_id INTEGER NOT NULL,
    character_id INTEGER NOT NULL,
    FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE CASCADE,
    FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE,
    PRIMARY KEY (episode_id, character_id)
);

CREATE TABLE IF NOT EXISTS episode_scenes (
    episode_id INTEGER NOT NULL,
    scene_id INTEGER NOT NULL,
    FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE CASCADE,
    FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE,
    PRIMARY KEY (episode_id, scene_id)
);

CREATE TABLE IF NOT EXISTS episode_props (
    episode_id INTEGER NOT NULL,
    prop_id INTEGER NOT NULL,
    FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE CASCADE,
    FOREIGN KEY (prop_id) REFERENCES props(id) ON DELETE CASCADE,
    PRIMARY KEY (episode_id, prop_id)
);

-- ============================================================
-- STORYBOARDS — segment per episode (1 segment = 1 Omni generation = 10s)
-- ============================================================
CREATE TABLE IF NOT EXISTS storyboards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id INTEGER NOT NULL,
    storyboard_number INTEGER NOT NULL,
    title TEXT,
    shot_type TEXT,                            -- close-up | medium | wide | extreme-close-up
    angle TEXT,                                -- eye-level | low-angle | high-angle | side
    movement TEXT,                             -- fixed | push-in | pull-out | pan | tilt | tracking
    description TEXT,                          -- narasi visual sub-shot
    atmosphere TEXT,
    omni_prompt TEXT,                           -- final prompt untuk Omni 1.1 Flash
    duration_sec INTEGER DEFAULT 10,
    video_local_path TEXT,                      -- path ke MP4 hasil Flow download
    flow_generation_status TEXT DEFAULT 'pending', -- pending | generated | failed
    flow_scene_id TEXT,                         -- ID scene di Flow UI (tracking)
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT,
    FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE CASCADE,
    UNIQUE(episode_id, storyboard_number)
);

CREATE TABLE IF NOT EXISTS storyboard_characters (
    storyboard_id INTEGER NOT NULL,
    character_id INTEGER NOT NULL,
    FOREIGN KEY (storyboard_id) REFERENCES storyboards(id) ON DELETE CASCADE,
    FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE,
    PRIMARY KEY (storyboard_id, character_id)
);

CREATE TABLE IF NOT EXISTS storyboard_scenes (
    storyboard_id INTEGER NOT NULL,
    scene_id INTEGER NOT NULL,
    FOREIGN KEY (storyboard_id) REFERENCES storyboards(id) ON DELETE CASCADE,
    FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE,
    PRIMARY KEY (storyboard_id, scene_id)
);

CREATE TABLE IF NOT EXISTS storyboard_props (
    storyboard_id INTEGER NOT NULL,
    prop_id INTEGER NOT NULL,
    FOREIGN KEY (storyboard_id) REFERENCES storyboards(id) ON DELETE CASCADE,
    FOREIGN KEY (prop_id) REFERENCES props(id) ON DELETE CASCADE,
    PRIMARY KEY (storyboard_id, prop_id)
);

-- ============================================================
-- AUDIO — dialog & voice per segment
-- ============================================================
CREATE TABLE IF NOT EXISTS segment_audio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    storyboard_id INTEGER NOT NULL UNIQUE,
    dialogue_jawa TEXT,                         -- text Jawa Krama (user input/edit)
    dialogue_indonesia TEXT,                    -- terjemahan untuk subtitle
    dialogue_source TEXT DEFAULT 'user',        -- user | ai_draft | ai_edited
    narration TEXT,                             -- voice-over (opsional)
    ambient_sfx TEXT,                           -- "gamelan jauh, langkah armor"
    bgm_mood TEXT,                              -- epic | melancholic | tense | triumphant | mysterious
    voice_style TEXT,                           -- "Deep Javanese male, krama inggil"
    FOREIGN KEY (storyboard_id) REFERENCES storyboards(id) ON DELETE CASCADE
);

-- ============================================================
-- STYLE PRESETS — preset visual Nusantara
-- ============================================================
CREATE TABLE IF NOT EXISTS style_presets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    value TEXT NOT NULL UNIQUE,
    prompt TEXT NOT NULL,
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- ============================================================
-- VOCABULARY JAWA — kamus untuk validator (next phase)
-- ============================================================
CREATE TABLE IF NOT EXISTS vocabulary_jawa (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word TEXT NOT NULL,
    level TEXT NOT NULL,                        -- ngoko | krama | krama_inggil
    meaning_indonesia TEXT,
    meaning_english TEXT,
    context_notes TEXT,
    is_formal INTEGER DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_vocabulary_word ON vocabulary_jawa(word);
CREATE INDEX IF NOT EXISTS idx_vocabulary_level ON vocabulary_jawa(level);

-- ============================================================
-- TEMPLATES — panatacara / panyandra struktur baku (next phase)
-- ============================================================
CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,                         -- panatacara | panyandra | pamedharsabda
    context TEXT NOT NULL,                      -- wedding | graduation | religious | drama_scene | custom
    title TEXT,
    structure TEXT,                             -- JSON: outline paragraf
    sample_text TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- ============================================================
-- SETTINGS — key-value per drama
-- ============================================================
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- ============================================================
-- INDEXES
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_episodes_drama ON episodes(drama_id);
CREATE INDEX IF NOT EXISTS idx_characters_drama ON characters(drama_id);
CREATE INDEX IF NOT EXISTS idx_scenes_drama ON scenes(drama_id);
CREATE INDEX IF NOT EXISTS idx_props_drama ON props(drama_id);
CREATE INDEX IF NOT EXISTS idx_storyboards_episode ON storyboards(episode_id);
"""


# ============================================================
# SEED DATA
# ============================================================
SEED_STYLE_PRESETS_SQL = """
INSERT OR IGNORE INTO style_presets (name, value, prompt, description, sort_order, is_active, created_at, updated_at)
VALUES
('Wayang Nusantara', 'nusantara-wayang',
'Indonesian traditional wayang kulit shadow puppet aesthetic, flat two-dimensional silhouette puppet art with intricate Javanese ornamental perforations, warm golden backlight on a translucent screen, carved buffalo hide puppet texture, deep shadow contrast, classical Javanese character archetypes (ksatria, raksasa, dewata), ornamental batik-patterned frame borders, consistent character design across shots, avoid photorealism, avoid 3D CGI render, avoid modern clothing, avoid western fantasy style, avoid anime cel-shading, avoid plastic look, avoid neon colors',
'Estetika wayang kulit Jawa klasik — bayangan di layar, ornamen tradisional',
10, 1, ?, ?),

('Batik Decorative', 'nusantara-batik',
'Indonesian batik-inspired decorative illustration, rich earth-tone palette with deep soga brown, indigo blue, and natural ochre, traditional batik motifs layered as environmental texture (kawung, parang, lereng, ceplok), crackled wax-resist dye texture on fabric surfaces, semi-realistic character art with batik pattern as clothing and background ornament, warm cinematic lighting with selective pattern highlights, consistent character design across shots, avoid flat solid colors, avoid modern graphic design, avoid photorealism, avoid 3D render, avoid anime style, avoid neon or oversaturated colors, avoid digital airbrush look',
'Ilustrasi dengan lapisan motif batik tradisional sebagai tekstur dekoratif',
11, 1, ?, ?),

('Klasik Nusantara', 'nusantara-classical',
'Indonesian classical realist painting style in tradition of Basuki Abdullah and Sudjojono modern Indonesian art, warm naturalistic oil-painting brushwork with visible canvas texture, earthy palette of sienna, umber, ochre with deep tropical greens, figurative realist character art with expressive faces and detailed anatomy, tropical Southeast Asian landscape and architectural backdrop, soft atmospheric depth with golden-hour lighting, museum-grade Indonesian classical painting quality, consistent character design across shots, avoid anime cel-shading, avoid 3D CGI render, avoid western photorealism, avoid plastic skin, avoid over-smoothed digital airbrush, avoid neon palette',
'Gaya lukisan klasik Indonesia — realis figuratif hangat ala Basuki Abdullah',
12, 1, ?, ?),

('Epik Nusantara', 'nusantara-epic',
'Cinematic historical epic realism with Indonesian Nusantara aesthetic, semi-realistic character art with refined facial features and ethnic accuracy (Javanese, Sundanese, Balinese, Sumatran physiognomy as appropriate), period-accurate traditional costume with batik, ikat, songket, and royal keraton attire, lush tropical Southeast Asian environment with candi temples, keraton architecture, traditional pendopo and gapura, dramatic volumetric lighting with golden-hour warmth and atmospheric haze, rich earth-tone palette with selective jewel-tone accents, professional cinematographer color grading, shallow depth of field with selective focus, consistent character design across shots, avoid anime style, avoid cartoon cel-shading, avoid plastic 3D look, avoid western fantasy armor, avoid modern clothing, avoid neon palette, avoid over-smoothed airbrush skin, avoid generic Asian face',
'Realisme epik sinematik untuk drama sejarah Nusantara — preset default untuk era kerajaan',
13, 1, ?, ?);
"""


# ============================================================
# DB MANAGER
# ============================================================
class Database:
    """Manager untuk SQLite per drama."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                self.db_path,
                isolation_level=None,  # autocommit
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def init_schema(self) -> None:
        """Buat semua tabel + seed data jika belum ada."""
        # Pastikan parent dir ada
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Execute schema DDL
        self.conn.executescript(SCHEMA_SQL)

        # Seed style presets
        now = datetime.now(timezone.utc).isoformat()
        self.conn.executemany(
            SEED_STYLE_PRESETS_SQL.replace("?", "?"),  # placeholder
            [(now, now)] * 0  # dummy, actual seed via execute below
        )
        # Execute seed dengan parameter binding
        self.conn.execute(SEED_STYLE_PRESETS_SQL, (now, now, now, now, now, now, now, now))

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


# ============================================================
# DRAMAS INDEX DB — global, track semua drama user punya
# ============================================================
INDEX_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS dramas_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    era TEXT,
    language TEXT,
    storage_path TEXT NOT NULL,
    db_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class DramasIndexDB:
    """DB global di ~/.drama-nusantara/dramas.sqlite3 untuk track semua drama."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)

    @property
    def conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def init_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.conn as conn:
            conn.executescript(INDEX_SCHEMA_SQL)

    def add_drama(self, slug: str, title: str, era: str, language: str,
                  storage_path: str, db_path: str) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self.conn as conn:
            cur = conn.execute(
                """INSERT INTO dramas_index (slug, title, era, language, storage_path, db_path, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (slug, title, era, language, storage_path, db_path, now, now)
            )
            return cur.lastrowid

    def list_dramas(self) -> list[dict]:
        with self.conn as conn:
            cur = conn.execute(
                "SELECT id, slug, title, era, language, storage_path, created_at FROM dramas_index ORDER BY id"
            )
            return [dict(r) for r in cur.fetchall()]

    def get_drama(self, drama_id: int) -> Optional[dict]:
        with self.conn as conn:
            cur = conn.execute(
                "SELECT * FROM dramas_index WHERE id = ?",
                (drama_id,)
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def delete_drama(self, drama_id: int) -> bool:
        with self.conn as conn:
            cur = conn.execute("DELETE FROM dramas_index WHERE id = ?", (drama_id,))
            return cur.rowcount > 0

"""
Config & storage path management.

Konvensi:
- Code TUI: install via `uv tool install` → ~/.local/share/uv/tools/
- Config user: ~/.drama-nusantara/config.json
- Database & assets: user-configurable, default ~/drama-nusantara/, idealnya di HDD eksternal
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


# ============================================================
# CONSTANTS
# ============================================================
APP_NAME = "drama_nusantara"
APP_VERSION = "0.1.0"

# Lokasi default di home user (untuk config & database index)
# Pakai underscore agar match dengan repo name: drama_nusantara
HOME_CONFIG_DIR = Path.home() / ".drama_nusantara"
CONFIG_FILE = HOME_CONFIG_DIR / "config.json"
DRAMAS_INDEX_DB = HOME_CONFIG_DIR / "dramas.sqlite3"

# Default storage root (bisa di-override user saat init)
# Pakai hyphen agar konsisten dengan konvensi folder visible di storage/HDD
DEFAULT_STORAGE_ROOT = Path.home() / "drama-nusantara"

# Legacy path (untuk migrasi dari v0.1.0 lama yang pakai hyphen)
LEGACY_HOME_CONFIG_DIR = Path.home() / ".drama-nusantara"

# Nama folder per drama
DRAMA_FOLDER_TEMPLATE = "{slug}"  # di-isi slug drama
ASSETS_SUBDIR = "assets"
SEGMENTS_SUBDIR = "segments"
EXPORTS_SUBDIR = "exports"
CHARACTERS_SUBDIR = "characters"
SCENES_SUBDIR = "scenes"
PROPS_SUBDIR = "props"
STORYBOARDS_SUBDIR = "storyboards"


# ============================================================
# CONFIG MODEL
# ============================================================
@dataclass
class UserConfig:
    """Konfigurasi user yang disimpan di ~/.drama-nusantara/config.json"""

    # Path root untuk storage data (assets, video, SQLite per drama)
    storage_root: str = str(DEFAULT_STORAGE_ROOT)

    # Gemini API key (untuk AI draft naskah)
    gemini_api_key: str = ""

    # Provider preference (default: gemini)
    ai_provider: str = "gemini"  # gemini | openai | anthropic

    # Editor preference (default: auto-detect)
    editor: str = "auto"  # auto | vscode | subl | vim | nano | textedit

    # Image viewer preference (default: auto-detect per OS)
    image_viewer: str = "auto"  # auto | vscode | preview | quicklook

    # Default resolution untuk video generation
    default_video_resolution: str = "360p"  # 360p | 720p

    # Default duration per segment (detik)
    default_segment_duration: int = 10  # 4 | 6 | 8 | 10 (Omni max)

    # Default aspect ratio
    default_aspect_ratio: str = "9:16"  # 9:16 | 16:9 | 1:1

    # Bahasa default untuk naskah
    default_language: str = "jv"  # jv | id | su | min

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "UserConfig":
        # Hanya ambil field yang dikenal, ignore unknown
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)


# ============================================================
# CONFIG MANAGER
# ============================================================
class ConfigManager:
    """Manager untuk load/save config user."""

    def __init__(self, config_path: Path = CONFIG_FILE):
        # Migrasi otomatis dari path lama (hyphen) ke path baru (underscore)
        self._migrate_legacy_path()
        self.config_path = config_path
        self._config: Optional[UserConfig] = None

    def _migrate_legacy_path(self) -> None:
        """Migrasi config dari ~/.drama-nusantara/ (lama) ke ~/.drama_nusantara/ (baru)."""
        if not LEGACY_HOME_CONFIG_DIR.exists():
            return
        if HOME_CONFIG_DIR.exists():
            # Path baru sudah ada, skip migrasi (jangan overwrite)
            return
        # Pindahkan folder lama ke path baru
        import shutil
        try:
            HOME_CONFIG_DIR.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(LEGACY_HOME_CONFIG_DIR), str(HOME_CONFIG_DIR))
            print(f"📦 Migrated config: {LEGACY_HOME_CONFIG_DIR} → {HOME_CONFIG_DIR}")
        except (OSError, shutil.Error) as e:
            print(f"⚠️  Migration failed: {e}")
            print(f"   Manual move: mv {LEGACY_HOME_CONFIG_DIR} {HOME_CONFIG_DIR}")

    @property
    def config(self) -> UserConfig:
        if self._config is None:
            self._config = self.load()
        return self._config

    def load(self) -> UserConfig:
        """Load config dari file, atau create default jika tidak ada."""
        if not self.config_path.exists():
            return UserConfig()

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return UserConfig.from_dict(data)
        except (json.JSONDecodeError, OSError) as e:
            print(f"⚠️  Config corrupt di {self.config_path}: {e}")
            print("   Memuat default config.")
            return UserConfig()

    def save(self, config: UserConfig) -> None:
        """Save config ke file."""
        # Pastikan parent directory ada
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)

        self._config = config

    def update(self, **kwargs) -> UserConfig:
        """Update field config dan save."""
        current = self.config
        new_config = UserConfig(**{**current.to_dict(), **kwargs})
        self.save(new_config)
        return new_config

    def is_initialized(self) -> bool:
        """Cek apakah config sudah di-init user."""
        if not self.config_path.exists():
            return False
        cfg = self.config
        # Minimal harus ada storage_root (Gemini API key opsional — bisa pakai mock AI)
        return bool(cfg.storage_root)


# ============================================================
# DRAMA PATH RESOLVER
# ============================================================
def slugify(text: str) -> str:
    """Slugify judul drama jadi nama folder yang aman."""
    import re
    import unicodedata

    # Normalize unicode (NFKD)
    text = unicodedata.normalize("NFKD", text)
    # Hapus karakter non-ASCII
    text = text.encode("ascii", "ignore").decode("ascii")
    # Lowercase
    text = text.lower()
    # Replace non-alphanumeric dengan hyphen
    text = re.sub(r"[^a-z0-9]+", "-", text)
    # Trim hyphen di awal/akhir
    text = text.strip("-")
    # Limit length
    return text[:50] or "untitled"


@dataclass
class DramaPaths:
    """Path resolver untuk satu drama."""

    drama_id: int
    drama_slug: str
    storage_root: Path

    @property
    def drama_dir(self) -> Path:
        return Path(self.storage_root) / self.drama_slug

    @property
    def db_path(self) -> Path:
        return self.drama_dir / "drama.sqlite3"

    @property
    def assets_dir(self) -> Path:
        return self.drama_dir / ASSETS_SUBDIR

    @property
    def characters_dir(self) -> Path:
        return self.assets_dir / CHARACTERS_SUBDIR

    @property
    def scenes_dir(self) -> Path:
        return self.assets_dir / SCENES_SUBDIR

    @property
    def props_dir(self) -> Path:
        return self.assets_dir / PROPS_SUBDIR

    @property
    def storyboards_dir(self) -> Path:
        return self.assets_dir / STORYBOARDS_SUBDIR

    @property
    def segments_dir(self) -> Path:
        return self.drama_dir / SEGMENTS_SUBDIR

    @property
    def exports_dir(self) -> Path:
        return self.drama_dir / EXPORTS_SUBDIR

    def ensure_dirs(self) -> None:
        """Buat semua directory yang dibutuhkan jika belum ada."""
        for p in [
            self.drama_dir,
            self.assets_dir,
            self.characters_dir,
            self.scenes_dir,
            self.props_dir,
            self.storyboards_dir,
            self.segments_dir,
            self.exports_dir,
        ]:
            p.mkdir(parents=True, exist_ok=True)


def get_drama_paths(drama_id: int, drama_slug: str, storage_root: str | Path) -> DramaPaths:
    """Factory untuk DramaPaths."""
    return DramaPaths(
        drama_id=drama_id,
        drama_slug=drama_slug,
        storage_root=Path(storage_root),
    )

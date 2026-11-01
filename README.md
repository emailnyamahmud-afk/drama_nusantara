# Drama Nusantara TUI

> Produksi drama sejarah Nusantara berbahasa Jawa Krama Inggil — dari ide hingga JSON spec siap pakai di Google Flow + Omni 1.1 Flash.

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status: Alpha](https://img.shields.io/badge/Status-Alpha-red.svg)]()

## Apa Ini?

TUI (Terminal User Interface) untuk kreator AI yang ingin memproduksi drama pendek vertical (YouTube Shorts / IG Reels / TikTok) dengan kualitas **premium dan autentik budaya Jawa** — terutama Bahasa Jawa Krama Inggil dan struktur panatacara/panyandra yang baku.

**Moat utama**: Konsistensi visual + Bahasa Jawa Krama naturalis (belum ada kreator AI yang konsisten di niche ini per Nov 2026).

## Arsitektur 3 Lapisan

```
┌─ TUI ini (Python, di home user) ────────────────────┐
│  Brainstorming naskah + storyboard + JSON spec       │
│  Lisensi: MIT                                        │
└──────────────────────────────────────────────────────┘
                          ↓
┌─ Google Flow (Nano Banana Pro + Omni 1.1 Flash) ────┐
│  Generate reference image (free unlimited)            │
│  Generate video 10s per segment (7 kredit/360p)      │
│  Lisensi: Google AI ToS (komersial aman)             │
└──────────────────────────────────────────────────────┘
                          ↓
┌─ Output MP4 (di HDD eksternal user) ────────────────┐
│  FFmpeg merge → episode final 30-50 detik             │
│  Upload ke YouTube Shorts / Reels                     │
└──────────────────────────────────────────────────────┘
```

## Install

### Prasyarat

- macOS (M1/Apple Silicon atau Intel) — atau Linux
- Python 3.10+ (sebaiknya via [uv](https://docs.astral.sh/uv/))
- [uv](https://github.com/astral-sh/uv) — package manager modern
- Akun Google Flow (gratis, 50 kredit/day) di https://flow.google.com
- API key Gemini (gratis tier) di https://aistudio.google.com/apikey

### Install `uv` (jika belum)

```bash
# Mac / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Mac via Homebrew
brew install uv
```

### Install TUI

```bash
# Cara 1: langsung dari PyPI (segera)
uvx drama-nusantara-tui

# Cara 2: clone repo dan install local
git clone https://github.com/drama-nusantara/drama-tui.git
cd drama-tui
uv tool install .

# Jalankan
drama-tui --help
```

## Quick Start

```bash
# Init pertama kali — konfigurasi storage path & API key
drama-tui init

# Buat drama baru
drama-tui new

# Generate naskah (AI draft + user edit)
drama-tui generate-script --drama 1

# List drama
drama-tui list

# Export JSON spec siap pakai di Flow
drama-tui export --drama 1 --episode 1
```

## Penyimpanan Data

| Path | Isi | Lokasi default |
|---|---|---|
| Code TUI | Package Python | `~/.local/share/uv/tools/drama-nusantara-tui/` |
| Database & config | SQLite + settings.json | `~/.drama-nusantara/` |
| Aset (image, video) | Per drama folder | **HDD eksternal** (user pilih saat init) |

Contoh struktur folder:
```
/Volumes/MyHDD/drama-nusantara/
├── sumpah_palapa/
│   ├── drama.sqlite3
│   ├── assets/
│   │   ├── characters/
│   │   │   ├── gajah_mada_turnaround.png
│   │   │   └── hayam_wuruk_turnaround.png
│   │   ├── scenes/
│   │   │   └── pendopo_majapahit.png
│   │   └── props/
│   │       └── keris_naga_sasra.png
│   ├── segments/
│   │   ├── ep01_seg01.mp4
│   │   ├── ep01_seg02.mp4
│   │   └── ep01_seg03.mp4
│   └── exports/
│       └── ep01_spec.json
└── sultan_agung/
    └── ...
```

## Workflow 5 Step

```
Step 1: Buat Drama           — Judul, era, bahasa, target platform
Step 2: Generate Naskah       — AI draft Jawa Krama, user edit di VSCode
Step 3: Reference Image      — TUI generate prompt, user paste ke Flow
Step 4: Storyboard Segment   — 3 segment × 10s, omni_prompt per segment
Step 5: Export JSON Spec     — Siap pakai di Flow + instruksi manual
```

## License

MIT — bebas pakai komersial. Lihat [LICENSE](LICENSE).

## Atribusi & Inspirasi

- Struktur pipeline terinspirasi dari [huobao-drama](https://github.com/chatfire-AI/huobao-drama) by chatfire-AI (CC BY-NC-SA 4.0) — namun kode TUI ini sepenuhnya orisinal, tidak ada kode yang di-fork.
- Engine video: [Google Flow](https://flow.google.com) + Gemini Omni 1.1 Flash
- Engine image: Nano Banana Pro (via Google Flow)

## Status Pengembangan

Saat ini **Alpha** — fitur dasar saja. Roadmap:

- [x] Project skeleton
- [x] SQLite schema (huobao-inspired)
- [x] CLI entry point
- [ ] Wizard 5-step dengan questionary
- [ ] Integrasi Gemini API untuk draft naskah
- [ ] JSON spec exporter sesuai schema
- [ ] Image preview integration (VSCode/Quick Look)
- [ ] Kamus Jawa krama inggil validator
- [ ] FFmpeg merge tool
- [ ] Multi-drama dashboard

Lihat [CHANGELOG.md](CHANGELOG.md) untuk detail rilis.

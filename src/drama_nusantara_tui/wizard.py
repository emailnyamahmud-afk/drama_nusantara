"""
Wizard 5-step production flow.

Step 1: ✓ Drama already created (skip)
Step 2: Generate Naskah (AI draft → user edit)
Step 3: Reference Image (generate prompt untuk Nano Banana Pro)
Step 4: Storyboard Segment (3 × 10s + omni_prompt)
Step 5: Export JSON Spec (siap paste ke Flow)
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .ai import (
    AIProvider,
    MockAIProvider,
    StoryboardSegment,
    get_ai_provider,
)
from .config import ConfigManager, DramaPaths, DRAMAS_INDEX_DB, get_drama_paths, slugify
from .db import Database, DramasIndexDB
from .editor import edit_text
from .exporter import SpecExporter, slugify_name

console = Console()


# ============================================================
# WIZARD
# ============================================================
class ProductionWizard:
    """Wizard 5-step untuk produksi drama."""

    def __init__(self, drama_id: int, use_mock_ai: bool = True):
        self.drama_id = drama_id
        self.use_mock_ai = use_mock_ai

        # Load drama from index DB
        index_db = DramasIndexDB(DRAMAS_INDEX_DB)
        self.drama_meta = index_db.get_drama(drama_id)
        if not self.drama_meta:
            raise ValueError(f"Drama ID {drama_id} tidak ditemukan di index")

        # Config
        cm = ConfigManager()
        self.config = cm.config

        # Drama paths
        self.drama_paths = get_drama_paths(
            drama_id=drama_id,
            drama_slug=self.drama_meta["slug"],
            storage_root=self.config.storage_root,
        )
        self.drama_paths.ensure_dirs()

        # DB connection per drama
        self.db = Database(self.drama_paths.db_path)
        self.db.init_schema()

        # AI provider
        self.ai: AIProvider = get_ai_provider(
            use_mock=use_mock_ai,
            api_key=self.config.gemini_api_key,
        )

        # State — di-populate selama wizard jalan
        self.current_episode_id: Optional[int] = None

    def run(self) -> None:
        """Run full 5-step wizard."""
        console.print(
            Panel(
                f"[bold green]🚀 Wizard Produksi Drama #{self.drama_id}[/]\n"
                f"   Judul: [cyan]{self.drama_meta['title']}[/]\n"
                f"   Era:   [yellow]{self.drama_meta.get('era', '-')}[/]\n"
                f"   Bahasa: [green]{self.drama_meta.get('language', '-')}[/]",
                border_style="green",
            )
        )

        # Cek apakah sudah ada episode
        with self.db.conn as conn:
            cur = conn.execute(
                "SELECT id, episode_number, title FROM episodes WHERE deleted_at IS NULL ORDER BY episode_number LIMIT 1"
            )
            ep_row = cur.fetchone()

        if ep_row:
            self.current_episode_id = ep_row[0]
            console.print(f"[green]✓[/] Episode existing ditemukan: [bold]EP{ep_row[1]} - {ep_row[2]}[/]")
        else:
            # Create episode 1
            self._create_episode_1()

        # Show roadmap
        self._show_roadmap()

        # Run steps 2-5 (step 1 = drama already created)
        while True:
            choice = questionary.select(
                "Pilih step untuk lanjut:",
                choices=[
                    "Step 2: Generate Naskah (AI draft + user edit)",
                    "Step 3: Reference Image (generate prompt untuk Nano Banana Pro)",
                    "Step 4: Storyboard Segment (3 × 10s + omni_prompt)",
                    "Step 5: Export JSON Spec (siap paste ke Flow)",
                    "Lihat ringkasan drama",
                    "Keluar",
                ],
            ).ask()

            if choice is None or choice == "Keluar":
                console.print("[yellow]👋 Keluar wizard. Data sudah tersimpan.[/]")
                break
            elif choice.startswith("Step 2"):
                self.step_2_generate_naskah()
            elif choice.startswith("Step 3"):
                self.step_3_reference_image()
            elif choice.startswith("Step 4"):
                self.step_4_storyboard()
            elif choice.startswith("Step 5"):
                self.step_5_export_json()
            elif choice.startswith("Lihat"):
                self._show_summary()

        self.db.close()

    # ============================================================
    # HELPERS
    # ============================================================
    def _create_episode_1(self) -> None:
        """Create episode 1 default."""
        now = datetime.now(timezone.utc).isoformat()
        with self.db.conn as conn:
            cur = conn.execute(
                """INSERT INTO episodes (drama_id, episode_number, title, duration_sec, status, resolution, created_at, updated_at)
                   VALUES (?, 1, ?, 30, 'draft', '360p', ?, ?)""",
                (self.drama_id, f"{self.drama_meta['title']} — Bagian 1", now, now),
            )
            self.current_episode_id = cur.lastrowid
        console.print(f"[green]✓[/] Episode 1 dibuat (id={self.current_episode_id})")

    def _show_roadmap(self) -> None:
        """Show 5-step roadmap with current status."""
        table = Table(title="📋 Roadmap Wizard 5 Step", show_header=True)
        table.add_column("Step", justify="right", style="cyan", width=6)
        table.add_column("Nama", style="white", width=35)
        table.add_column("Status", style="yellow", width=15)
        table.add_column("Deskripsi", style="dim")

        # Get status from DB
        with self.db.conn as conn:
            cur = conn.execute(
                "SELECT script_content, status FROM episodes WHERE id = ?",
                (self.current_episode_id,),
            )
            ep = cur.fetchone()
            has_script = bool(ep and ep[0])
            ep_status = ep[1] if ep else "draft"

            cur = conn.execute("SELECT COUNT(*) FROM characters WHERE deleted_at IS NULL")
            chars_count = cur.fetchone()[0]

            cur = conn.execute("SELECT COUNT(*) FROM storyboards WHERE episode_id = ? AND deleted_at IS NULL", (self.current_episode_id,))
            sb_count = cur.fetchone()[0]

        status_2 = "[green]✓ Done[/]" if has_script else "[yellow]⏳ Pending[/]"
        status_3 = "[green]✓ Done[/]" if chars_count > 0 else "[yellow]⏳ Pending[/]"
        status_4 = "[green]✓ Done[/]" if sb_count > 0 else "[yellow]⏳ Pending[/]"
        status_5 = "[green]✓ Done[/]" if ep_status in ("exported", "published") else "[yellow]⏳ Pending[/]"

        table.add_row("1", "Buat Drama", "[green]✓ Done[/]", "Sudah dibuat")
        table.add_row("2", "Generate Naskah", status_2, "AI draft Jawa Krama + user edit")
        table.add_row("3", "Reference Image", status_3, "Generate prompt untuk Nano Banana Pro")
        table.add_row("4", "Storyboard Segment", status_4, "3 segment × 10s + omni_prompt")
        table.add_row("5", "Export JSON Spec", status_5, "Siap paste ke Google Flow")
        console.print(table)

    def _show_summary(self) -> None:
        """Show drama summary."""
        with self.db.conn as conn:
            cur = conn.execute("SELECT COUNT(*) FROM episodes WHERE deleted_at IS NULL")
            eps = cur.fetchone()[0]
            cur = conn.execute("SELECT COUNT(*) FROM characters WHERE deleted_at IS NULL")
            chars = cur.fetchone()[0]
            cur = conn.execute("SELECT COUNT(*) FROM scenes WHERE deleted_at IS NULL")
            scenes = cur.fetchone()[0]
            cur = conn.execute("SELECT COUNT(*) FROM props WHERE deleted_at IS NULL")
            props = cur.fetchone()[0]
            cur = conn.execute("SELECT COUNT(*) FROM storyboards WHERE deleted_at IS NULL")
            sbs = cur.fetchone()[0]

        console.print(Panel(
            f"📺 Episode: {eps}\n"
            f"👤 Karakter: {chars}\n"
            f"🏞️  Scene: {scenes}\n"
            f"🎭 Prop: {props}\n"
            f"🎬 Storyboard: {sbs}",
            title="📊 Ringkasan Drama",
            border_style="cyan",
        ))

    # ============================================================
    # STEP 2: GENERATE NASKAH
    # ============================================================
    def step_2_generate_naskah(self) -> None:
        """AI generate draft naskah → user edit via editor."""

        console.print("\n[bold cyan]━━━ Step 2: Generate Naskah ━━━[/]\n")

        # Input dari user
        format_type = questionary.select(
            "Format naskah:",
            choices=[
                questionary.Choice("Panyandra (sambutan pernikahan/acara resmi)", value="panyandra"),
                questionary.Choice("Panatacara (pembawa acara)", value="panatacara"),
                questionary.Choice("Dialog drama (antar tokoh)", value="dialog"),
                questionary.Choice("Voice-over narator", value="narration"),
            ],
        ).ask()

        if format_type is None:
            return

        context = questionary.text(
            "Konteks acara/scene:",
            default="Wisuda prajurit Majapahit",
        ).ask()

        if context is None:
            return

        characters_input = questionary.text(
            "Tokoh utama (comma-separated):",
            default="Gajah Mada, Prajurit Muda",
        ).ask()

        characters = [c.strip() for c in (characters_input or "").split(",") if c.strip()]

        moment = questionary.text(
            "Momen spesifik (apa yang terjadi):",
            default="Setelah kemenangan dari perbatasan",
        ).ask()

        # Generate via AI
        console.print(f"\n[cyan]🤖 Generating draft via {self.ai.provider_name}...[/]")
        era = self.drama_meta.get("era", "majapahit")
        language = self.drama_meta.get("language", "jv")

        draft = self.ai.generate_naskah(
            format_type=format_type,
            context=context,
            characters=characters,
            moment=moment or "",
            era=era,
            language=language,
        )

        console.print(f"[green]✓[/] Draft dibuat (kualitas ~{draft.estimated_quality}%, butuh edit)")
        console.print(f"   Format: {format_type}")
        console.print(f"   Tokoh: {', '.join(draft.characters)}")
        console.print(f"   Context: {draft.context}")

        # Tampilkan preview
        console.print(Panel(
            draft.raw_draft[:500] + ("..." if len(draft.raw_draft) > 500 else ""),
            title="📝 Draft Naskah (preview)",
            border_style="yellow",
        ))

        # Pilihan: edit sekarang atau skip
        action = questionary.select(
            "Mau edit sekarang?",
            choices=[
                "Ya, buka di editor (auto-detected)",
                "Tampilkan di terminal dulu",
                "Skip, simpan draft apa adanya",
            ],
        ).ask()

        if action is None:
            return

        final_naskah = draft.raw_draft

        if action.startswith("Ya, buka"):
            # Spawn editor
            filename = f"naskah_ep01_{format_type}.txt"
            final_naskah = edit_text(
                content=draft.raw_draft,
                filename=filename,
                editor_pref=self.config.editor,
                console=console,
            )
            console.print("[green]✓[/] Naskah final disimpan")
        elif action.startswith("Tampilkan"):
            console.print(Panel(draft.raw_draft, title="📝 Draft Naskah (full)", border_style="cyan"))
            edit_now = questionary.confirm("Edit sekarang di editor?", default=True).ask()
            if edit_now:
                final_naskah = edit_text(
                    content=draft.raw_draft,
                    filename=f"naskah_ep01_{format_type}.txt",
                    editor_pref=self.config.editor,
                    console=console,
                )

        # Save ke DB
        now = datetime.now(timezone.utc).isoformat()
        with self.db.conn as conn:
            conn.execute(
                """UPDATE episodes
                   SET script_content = ?, content = ?, script_source = ?, status = 'scripted', updated_at = ?
                   WHERE id = ?""",
                (final_naskah, context + " | " + (moment or ""), "ai_edited", now, self.current_episode_id),
            )

        console.print(f"\n[green]✓ Naskah disimpan ke episode #{self.current_episode_id}[/]")
        console.print(f"   Status: [yellow]scripted[/]")
        console.print(f"   Word count: [bold]{len(final_naskah.split())}[/] kata")

    # ============================================================
    # STEP 3: REFERENCE IMAGE
    # ============================================================
    def step_3_reference_image(self) -> None:
        """Extract characters/scenes/props dari naskah → generate prompt untuk Nano Banana Pro."""

        console.print("\n[bold cyan]━━━ Step 3: Reference Image ━━━[/]\n")

        # Cek apakah naskah sudah ada
        with self.db.conn as conn:
            cur = conn.execute(
                "SELECT script_content FROM episodes WHERE id = ?",
                (self.current_episode_id,),
            )
            row = cur.fetchone()
            if not row or not row[0]:
                console.print("[red]❌ Naskah belum dibuat. Run Step 2 dulu.[/]")
                return
            naskah = row[0]

        # Cek apakah assets sudah ada
        with self.db.conn as conn:
            cur = conn.execute("SELECT COUNT(*) FROM characters WHERE deleted_at IS NULL")
            existing_chars = cur.fetchone()[0]

        if existing_chars > 0:
            overwrite = questionary.confirm(
                f"Assets sudah ada ({existing_chars} karakter). Re-extract dari naskah?",
                default=False,
            ).ask()
            if not overwrite:
                self._display_assets_prompts()
                return

        # Extract via AI
        console.print(f"\n[cyan]🤖 Extracting characters/scenes/props via {self.ai.provider_name}...[/]")
        era = self.drama_meta.get("era", "majapahit")
        characters, scenes, props = self.ai.extract_assets(naskah, era)

        console.print(f"[green]✓[/] {len(characters)} karakter, {len(scenes)} scene, {len(props)} prop terdeteksi")

        # Generate image prompts untuk masing-masing
        style_preset = "nusantara-epic"  # default dari drama

        now = datetime.now(timezone.utc).isoformat()
        with self.db.conn as conn:
            # Clear existing (soft delete)
            conn.execute("UPDATE characters SET deleted_at = ? WHERE deleted_at IS NULL", (now,))
            conn.execute("UPDATE scenes SET deleted_at = ? WHERE deleted_at IS NULL", (now,))
            conn.execute("UPDATE props SET deleted_at = ? WHERE deleted_at IS NULL", (now,))

            # Insert characters
            for i, c in enumerate(characters):
                # Generate image prompt via AI
                image_prompt = self.ai.generate_image_prompt(
                    "character",
                    {
                        "name": c.name,
                        "appearance": c.appearance,
                        "styling": c.styling,
                    },
                    style_preset,
                )
                cur = conn.execute(
                    """INSERT INTO characters
                       (drama_id, name, role, appearance, styling, description, voice_style, image_gen_prompt, flow_upload_status, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
                    (self.drama_id, c.name, c.role, c.appearance, c.styling, c.description, c.voice_style, image_prompt, now, now),
                )
                char_id = cur.lastrowid
                # Link to episode
                conn.execute(
                    "INSERT OR IGNORE INTO episode_characters (episode_id, character_id) VALUES (?, ?)",
                    (self.current_episode_id, char_id),
                )

            # Insert scenes
            for s in scenes:
                image_prompt = self.ai.generate_image_prompt(
                    "scene",
                    {
                        "name": s.name,
                        "location": s.location,
                        "time_of_day": s.time_of_day,
                        "visual_prompt": s.visual_prompt,
                    },
                    style_preset,
                )
                cur = conn.execute(
                    """INSERT INTO scenes
                       (drama_id, name, location, time_of_day, visual_prompt, lighting, image_gen_prompt, flow_upload_status, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
                    (self.drama_id, s.name, s.location, s.time_of_day, s.visual_prompt, s.lighting, image_prompt, now, now),
                )
                scene_id = cur.lastrowid
                conn.execute(
                    "INSERT OR IGNORE INTO episode_scenes (episode_id, scene_id) VALUES (?, ?)",
                    (self.current_episode_id, scene_id),
                )

            # Insert props
            for p in props:
                image_prompt = self.ai.generate_image_prompt(
                    "prop",
                    {
                        "name": p.name,
                        "visual_prompt": p.visual_prompt,
                    },
                    style_preset,
                )
                cur = conn.execute(
                    """INSERT INTO props
                       (drama_id, name, type, visual_prompt, image_gen_prompt, flow_upload_status, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)""",
                    (self.drama_id, p.name, p.type, p.visual_prompt, image_prompt, now, now),
                )
                prop_id = cur.lastrowid
                conn.execute(
                    "INSERT OR IGNORE INTO episode_props (episode_id, prop_id) VALUES (?, ?)",
                    (self.current_episode_id, prop_id),
                )

        console.print(f"\n[green]✓[/] Assets disimpan ke DB")
        self._display_assets_prompts()

    def _display_assets_prompts(self) -> None:
        """Tampilkan semua image prompts siap copy-paste ke Flow."""
        with self.db.conn as conn:
            cur = conn.execute(
                "SELECT name, role, image_gen_prompt, image_local_path, flow_upload_status FROM characters WHERE deleted_at IS NULL ORDER BY id"
            )
            characters = cur.fetchall()
            cur = conn.execute(
                "SELECT name, image_gen_prompt, image_local_path, flow_upload_status FROM scenes WHERE deleted_at IS NULL ORDER BY id"
            )
            scenes = cur.fetchall()
            cur = conn.execute(
                "SELECT name, image_gen_prompt, image_local_path, flow_upload_status FROM props WHERE deleted_at IS NULL ORDER BY id"
            )
            props = cur.fetchall()

        # Tampilkan table characters
        if characters:
            table = Table(title="👤 Character Reference Images", show_header=True, header_style="bold cyan")
            table.add_column("#", style="cyan", width=3)
            table.add_column("Name", style="white", width=20)
            table.add_column("Role", style="yellow", width=12)
            table.add_column("Status", width=12)
            table.add_column("Local File", style="dim")
            for i, c in enumerate(characters, 1):
                status_emoji = "✅" if c["image_local_path"] else "⏳"
                table.add_row(
                    str(i),
                    c["name"],
                    c["role"],
                    f"{status_emoji} {c['flow_upload_status']}",
                    c["image_local_path"] or "(belum download)",
                )
            console.print(table)

        if scenes:
            table = Table(title="🏞️  Scene Reference Images", show_header=True, header_style="bold cyan")
            table.add_column("#", style="cyan", width=3)
            table.add_column("Name", style="white", width=25)
            table.add_column("Status", width=12)
            table.add_column("Local File", style="dim")
            for i, s in enumerate(scenes, 1):
                status_emoji = "✅" if s["image_local_path"] else "⏳"
                table.add_row(
                    str(i),
                    s["name"],
                    f"{status_emoji} {s['flow_upload_status']}",
                    s["image_local_path"] or "(belum download)",
                )
            console.print(table)

        if props:
            table = Table(title="🎭 Prop Reference Images", show_header=True, header_style="bold cyan")
            table.add_column("#", style="cyan", width=3)
            table.add_column("Name", style="white", width=25)
            table.add_column("Status", width=12)
            for i, p in enumerate(props, 1):
                status_emoji = "✅" if p["image_local_path"] else "⏳"
                table.add_row(
                    str(i),
                    p["name"],
                    f"{status_emoji} {p['flow_upload_status']}",
                )
            console.print(table)

        # Tampilkan prompt untuk Nano Banana Pro
        show_prompts = questionary.confirm(
            "\nTampilkan image generation prompts (untuk copy-paste ke Flow)?",
            default=True,
        ).ask()

        if show_prompts:
            for c in characters:
                console.print(Panel(
                    c["image_gen_prompt"],
                    title=f"👤 {c['name']} — turnaround prompt (Nano Banana Pro)",
                    border_style="cyan",
                ))
            for s in scenes:
                console.print(Panel(
                    s["image_gen_prompt"],
                    title=f"🏞️  {s['name']} — scene prompt (Nano Banana Pro)",
                    border_style="cyan",
                ))
            for p in props:
                console.print(Panel(
                    p["image_gen_prompt"],
                    title=f"🎭 {p['name']} — prop prompt (Nano Banana Pro)",
                    border_style="cyan",
                ))

    # ============================================================
    # STEP 4: STORYBOARD SEGMENT
    # ============================================================
    def step_4_storyboard(self) -> None:
        """Break naskah jadi 3 segment × 10s + omni_prompt per segment."""

        console.print("\n[bold cyan]━━━ Step 4: Storyboard Segment ━━━[/]\n")

        # Cek prerequisites
        with self.db.conn as conn:
            cur = conn.execute("SELECT script_content FROM episodes WHERE id = ?", (self.current_episode_id,))
            row = cur.fetchone()
            if not row or not row[0]:
                console.print("[red]❌ Naskah belum dibuat. Run Step 2 dulu.[/]")
                return
            naskah = row[0]

            cur = conn.execute("SELECT COUNT(*) FROM characters WHERE deleted_at IS NULL")
            if cur.fetchone()[0] == 0:
                console.print("[red]❌ Assets belum di-extract. Run Step 3 dulu.[/]")
                return

        # Input durasi
        target_duration = questionary.select(
            "Target durasi episode:",
            choices=[
                questionary.Choice("30 detik (3 segments × 10s) — recommended", value=30),
                questionary.Choice("20 detik (2 segments × 10s) — short", value=20),
                questionary.Choice("40 detik (4 segments × 10s) — long", value=40),
            ],
        ).ask()

        if target_duration is None:
            return

        # Load assets dari DB
        with self.db.conn as conn:
            cur = conn.execute("SELECT id, name, role, appearance, styling, description, voice_style FROM characters WHERE deleted_at IS NULL ORDER BY id")
            characters_raw = cur.fetchall()

            cur = conn.execute("SELECT id, name, location, time_of_day, visual_prompt, lighting FROM scenes WHERE deleted_at IS NULL ORDER BY id")
            scenes_raw = cur.fetchall()

            cur = conn.execute("SELECT id, name, type, visual_prompt FROM props WHERE deleted_at IS NULL ORDER BY id")
            props_raw = cur.fetchall()

        # Convert ke dataclass (reuse AI types)
        from .ai import CharacterExtraction, SceneExtraction, PropExtraction

        characters = [
            CharacterExtraction(
                name=c["name"], role=c["role"], appearance=c["appearance"],
                styling=c["styling"], description=c["description"], voice_style=c["voice_style"] or ""
            )
            for c in characters_raw
        ]
        scenes = [
            SceneExtraction(
                name=s["name"], location=s["location"], time_of_day=s["time_of_day"],
                visual_prompt=s["visual_prompt"], lighting=s["lighting"]
            )
            for s in scenes_raw
        ]
        props = [
            PropExtraction(name=p["name"], type=p["type"], visual_prompt=p["visual_prompt"])
            for p in props_raw
        ]

        # Generate storyboard via AI
        console.print(f"\n[cyan]🤖 Generating storyboard via {self.ai.provider_name}...[/]")
        era = self.drama_meta.get("era", "majapahit")
        language = self.drama_meta.get("language", "jv")
        segments = self.ai.generate_storyboard(
            naskah=naskah,
            characters=characters,
            scenes=scenes,
            props=props,
            target_duration_sec=target_duration,
            era=era,
            language=language,
        )

        console.print(f"[green]✓[/] {len(segments)} segment dibuat (× 10s = {len(segments) * 10}s total)")

        # Cek existing storyboards
        with self.db.conn as conn:
            cur = conn.execute("SELECT COUNT(*) FROM storyboards WHERE episode_id = ? AND deleted_at IS NULL", (self.current_episode_id,))
            existing = cur.fetchone()[0]

        if existing > 0:
            overwrite = questionary.confirm(
                f"Storyboard sudah ada ({existing} segment). Replace?",
                default=True,
            ).ask()
            if not overwrite:
                self._display_storyboard()
                return

        # Save ke DB
        now = datetime.now(timezone.utc).isoformat()
        with self.db.conn as conn:
            # Hard delete existing storyboards (juga cascade ke segment_audio + junction tables)
            # Pilih hard delete karena UNIQUE(episode_id, storyboard_number) tidak kompatibel dengan soft-delete
            conn.execute(
                "DELETE FROM storyboards WHERE episode_id = ?",
                (self.current_episode_id,),
            )

            # Build lookup: name → db_id
            char_id_lookup = {c["name"]: c["id"] for c in characters_raw}
            scene_id_lookup = {s["name"]: s["id"] for s in scenes_raw}
            prop_id_lookup = {p["name"]: p["id"] for p in props_raw}

            for seg in segments:
                # Insert storyboard
                cur = conn.execute(
                    """INSERT INTO storyboards
                       (episode_id, storyboard_number, title, shot_type, angle, movement,
                        description, atmosphere, omni_prompt, duration_sec, flow_generation_status, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
                    (self.current_episode_id, seg.segment_number, seg.title,
                     seg.shot_type, seg.angle, seg.movement,
                     seg.description, seg.atmosphere, seg.omni_prompt, seg.duration_sec, now, now),
                )
                sb_id = cur.lastrowid

                # Insert audio
                conn.execute(
                    """INSERT INTO segment_audio
                       (storyboard_id, dialogue_jawa, dialogue_indonesia, dialogue_source,
                        narration, ambient_sfx, bgm_mood, voice_style)
                       VALUES (?, ?, ?, 'ai_edited', ?, ?, ?, ?)""",
                    (sb_id, seg.dialogue_jawa, seg.dialogue_indonesia,
                     "", seg.ambient_sfx, seg.bgm_mood, seg.voice_style),
                )

                # Link characters
                for char_name in seg.character_refs:
                    if char_name in char_id_lookup:
                        conn.execute(
                            "INSERT OR IGNORE INTO storyboard_characters (storyboard_id, character_id) VALUES (?, ?)",
                            (sb_id, char_id_lookup[char_name]),
                        )

                # Link scene (single)
                if seg.scene_ref and seg.scene_ref in scene_id_lookup:
                    conn.execute(
                        "INSERT OR IGNORE INTO storyboard_scenes (storyboard_id, scene_id) VALUES (?, ?)",
                        (sb_id, scene_id_lookup[seg.scene_ref]),
                    )

                # Link props
                for prop_name in seg.prop_refs:
                    if prop_name in prop_id_lookup:
                        conn.execute(
                            "INSERT OR IGNORE INTO storyboard_props (storyboard_id, prop_id) VALUES (?, ?)",
                            (sb_id, prop_id_lookup[prop_name]),
                        )

            # Update episode status
            conn.execute(
                "UPDATE episodes SET status = 'storyboarded', duration_sec = ?, updated_at = ? WHERE id = ?",
                (len(segments) * 10, now, self.current_episode_id),
            )

        console.print(f"\n[green]✓[/] {len(segments)} segment disimpan ke DB")
        self._display_storyboard()

    def _display_storyboard(self) -> None:
        """Tampilkan semua segment storyboard."""
        with self.db.conn as conn:
            cur = conn.execute(
                """SELECT s.id, s.storyboard_number, s.title, s.shot_type, s.angle, s.movement,
                          s.description, s.atmosphere, s.omni_prompt, s.duration_sec,
                          s.flow_generation_status, s.video_local_path
                   FROM storyboards s
                   WHERE s.episode_id = ? AND s.deleted_at IS NULL
                   ORDER BY s.storyboard_number""",
                (self.current_episode_id,),
            )
            segments = cur.fetchall()

        if not segments:
            console.print("[yellow]⚠ Belum ada storyboard. Run Step 4 dulu.[/]")
            return

        for seg in segments:
            status_emoji = "✅" if seg["video_local_path"] else "⏳"
            console.print(Panel(
                f"[bold]Title:[/] {seg['title']}\n"
                f"[bold]Camera:[/] {seg['shot_type']} / {seg['movement']} / {seg['angle']}\n"
                f"[bold]Duration:[/] {seg['duration_sec']}s\n"
                f"[bold]Atmosphere:[/] {seg['atmosphere']}\n\n"
                f"[bold]Description:[/]\n{seg['description']}\n\n"
                f"[bold]Omni Prompt:[/]\n[dim]{seg['omni_prompt']}[/]\n\n"
                f"[bold]Status:[/] {status_emoji} {seg['flow_generation_status']}",
                title=f"🎬 Segment {seg['storyboard_number']}",
                border_style="cyan",
            ))

    # ============================================================
    # STEP 5: EXPORT JSON SPEC
    # ============================================================
    def step_5_export_json(self) -> None:
        """Build & export drama-spec.json siap paste ke Flow."""

        console.print("\n[bold cyan]━━━ Step 5: Export JSON Spec ━━━[/]\n")

        # Cek prerequisites
        with self.db.conn as conn:
            cur = conn.execute("SELECT COUNT(*) FROM storyboards WHERE episode_id = ? AND deleted_at IS NULL", (self.current_episode_id,))
            if cur.fetchone()[0] == 0:
                console.print("[red]❌ Storyboard belum dibuat. Run Step 4 dulu.[/]")
                return

        # Output filename
        default_filename = f"drama_{self.drama_id:03d}_ep01_spec.json"
        output_filename = questionary.text(
            "Output filename:",
            default=default_filename,
        ).ask()

        if not output_filename:
            return

        if not output_filename.endswith(".json"):
            output_filename += ".json"

        output_path = self.drama_paths.exports_dir / output_filename

        # Resolution
        resolution = questionary.select(
            "Video resolution:",
            choices=[
                questionary.Choice("360p (7 kredit/segment) — recommended", value="360p"),
                questionary.Choice("720p (15 kredit/segment) — higher quality", value="720p"),
            ],
        ).ask()

        if not resolution:
            return

        # Export
        console.print(f"\n[cyan]📦 Building JSON spec...[/]")
        try:
            exporter = SpecExporter(self.drama_paths.db_path)
            spec = exporter.export_episode(
                drama_id=self.drama_id,
                episode_id=self.current_episode_id,
                output_path=output_path,
                audio_locale=self.drama_meta.get("language", "jv"),
                resolution=resolution,
            )
            exporter.close()
        except Exception as e:
            console.print(f"[red]❌ Export failed: {e}[/]")
            return

        # Stats
        num_segments = len(spec["episodes"][0]["segments"])
        total_credits = spec["episodes"][0]["estimated_credits"]
        num_chars = len(spec["assets"]["characters"])
        num_scenes = len(spec["assets"]["scenes"])
        num_props = len(spec["assets"]["props"])

        console.print(f"\n[green]✓ JSON spec exported![/]")
        console.print(f"   File: [bold]{output_path}[/]")
        console.print(f"   Size: {output_path.stat().st_size} bytes")
        console.print(f"   Segments: {num_segments} × 10s")
        console.print(f"   Characters: {num_chars}")
        console.print(f"   Scenes: {num_scenes}")
        console.print(f"   Props: {num_props}")
        console.print(f"   Est. credits: [bold]{total_credits}[/] ({resolution})")
        console.print(f"   Est. episodes/day: {spec['production_plan']['episodes_per_day_realistic']}")

        # Update episode status
        now = datetime.now(timezone.utc).isoformat()
        with self.db.conn as conn:
            conn.execute(
                "UPDATE episodes SET status = 'exported', updated_at = ? WHERE id = ?",
                (now, self.current_episode_id),
            )

        # Tampilkan manual Flow instructions
        show_instructions = questionary.confirm(
            "\nTampilkan instruksi manual Flow (step-by-step)?",
            default=True,
        ).ask()

        if show_instructions:
            self._display_flow_instructions(spec, output_path)

    def _display_flow_instructions(self, spec: dict, output_path: Path) -> None:
        """Tampilkan step-by-step manual untuk pakai JSON spec di Flow."""

        console.print(Panel(
            f"""[bold]1. Buka:[/] https://flow.google.com
[bold]2. Klik "New Scene"[/]
[bold]3. Setup awal:[/]
   - Mode: Video · Bahan
   - Aspect ratio: 9:16
   - Model: Omni 1.1 Flash
   - Resolution: {spec['episodes'][0]['segments'][0]['generation_config']['resolution']}
   - Duration: 10s
   - Generation count: x1

[bold]4. Untuk setiap segment ({len(spec['episodes'][0]['segments'])} total):[/]
   a. Upload reference images (max 10):
      - Character turnaround PNG (5-angle, white bg)
      - Scene reference PNG
      - Prop reference PNG (jika ada)
   b. Copy-paste omni_prompt ke Flow input box
   c. Klik Generate (7 kredit untuk 360p)
   d. Download MP4 ke folder:
      {self.drama_paths.segments_dir}/
      dengan nama: seg_<N>.mp4 (mis: seg_01.mp4)

[bold]5. Setelah semua segment didownload:[/]
   Run: drama-tui merge --drama {self.drama_id} --episode 1
   (akan FFmpeg concat semua MP4 jadi 1 episode final)

[bold]6. Upload episode final ke YouTube Shorts / IG Reels / TikTok[/]
""",
            title="📖 Manual Flow Step-by-Step",
            border_style="green",
        ))

        # Print omni_prompt per segment untuk copy-paste
        show_prompts = questionary.confirm(
            "Tampilkan omni_prompt per segment (untuk copy-paste)?",
            default=True,
        ).ask()

        if show_prompts:
            for seg in spec["episodes"][0]["segments"]:
                char_refs_str = ", ".join(seg["character_refs"]) if seg["character_refs"] else "(none)"
                console.print(Panel(
                    f"[bold]Camera:[/] {seg['camera']['shot_type']} / {seg['camera']['movement']} / {seg['camera']['angle']}\n"
                    f"[bold]Characters:[/] {char_refs_str}\n"
                    f"[bold]Scene:[/] {seg['scene_ref'] or '(none)'}\n"
                    f"[bold]Dialog Jawa:[/] {seg['audio']['dialogue']}\n"
                    f"[bold]Voice style:[/] {seg['audio']['voice_style']}\n"
                    f"[bold]BGM mood:[/] {seg['audio']['bgm_mood']}\n\n"
                    f"[bold]── Omni Prompt (copy ke Flow) ──[/]\n\n"
                    f"{seg['omni_prompt']}",
                    title=f"🎬 Segment {seg['segment_number']}: {seg.get('title', '')}",
                    border_style="cyan",
                ))

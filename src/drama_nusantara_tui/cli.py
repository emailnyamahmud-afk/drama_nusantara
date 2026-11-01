"""
CLI entry point untuk Drama Nusantara TUI.

Usage:
    drama-tui --help            Show help
    drama-tui --version         Show version
    drama-tui init              Initialize config (first time setup)
    drama-tui new               Create new drama
    drama-tui list              List all dramas
    drama-tui info <id>         Show drama info
    drama-tui delete <id>       Delete a drama
    drama-tui wizard            Run 5-step production wizard
"""
from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import __version__
from .config import (
    APP_NAME,
    ConfigManager,
    DEFAULT_STORAGE_ROOT,
    DRAMAS_INDEX_DB,
    HOME_CONFIG_DIR,
    get_drama_paths,
    slugify,
)
from .db import Database, DramasIndexDB

console = Console()


# ============================================================
# HELPERS
# ============================================================
def print_banner() -> None:
    """Print app banner."""
    banner = f"""
[bold cyan]╭───────────────────────────────────────────────────────────╮[/]
[bold cyan]│[/]  🎬 Drama Nusantara TUI v{__version__:<32}    [bold cyan]│[/]
[bold cyan]│[/]  Produksi drama sejarah Jawa — kualitas premium          [bold cyan]│[/]
[bold cyan]╰───────────────────────────────────────────────────────────╯[/]
"""
    console.print(banner)


def require_init() -> bool:
    """Cek apakah config sudah di-init. Kalau belum, suggest user jalanin `init`."""
    cm = ConfigManager()
    if not cm.is_initialized():
        console.print("[red]❌ TUI belum diinisialisasi.[/]")
        console.print("\nJalankan dulu:")
        console.print("  [bold cyan]drama-tui init[/]")
        return False
    return True


# ============================================================
# CLI COMMANDS
# ============================================================
@click.group(invoke_without_command=True)
@click.version_option(__version__, prog_name="drama-tui")
@click.help_option("-h", "--help")
@click.pass_context
def main(ctx: click.Context) -> None:
    """Drama Nusantara TUI — produksi drama sejarah Nusantara."""
    # Trigger migrasi config dari path lama (~/.drama-nusantara) ke path baru (~/.drama_nusantara)
    # Hanya jalan sekali per install, no-op kalau sudah migrasi
    from .config import ConfigManager
    ConfigManager()

    if ctx.invoked_subcommand is None:
        print_banner()
        console.print("\nPerintah tersedia:\n")
        console.print("  [bold cyan]drama-tui init[/]       Setup awal (first time)")
        console.print("  [bold cyan]drama-tui new[/]        Buat drama baru")
        console.print("  [bold cyan]drama-tui list[/]       Lihat semua drama")
        console.print("  [bold cyan]drama-tui info <id>[/]  Detail satu drama")
        console.print("  [bold cyan]drama-tui wizard[/]     Run 5-step production wizard")
        console.print("  [bold cyan]drama-tui --help[/]     Lihat semua perintah\n")
        console.print("[dim]Mulai dengan: drama-tui init[/]")


@main.command()
def init() -> None:
    """Setup awal — konfigurasi storage path & API key."""
    print_banner()
    console.print("[bold yellow]🚀 Setup Awal Drama Nusantara TUI[/]\n")

    cm = ConfigManager()
    current = cm.config

    # === Storage path ===
    console.print("[bold]1. Lokasi penyimpanan data[/]")
    console.print(f"   Default: [cyan]{DEFAULT_STORAGE_ROOT}[/]")
    console.print("   💡 Untuk file besar (image/video), sebaiknya pakai HDD eksternal.")
    console.print("   Contoh: /Volumes/MyHDD/drama-nusantara\n")

    storage_input = click.prompt(
        "Path storage",
        default=str(current.storage_root or DEFAULT_STORAGE_ROOT),
        type=str,
    )
    storage_path = Path(storage_input).expanduser().resolve()

    # Cek apakah path ada / bisa dibuat
    try:
        storage_path.mkdir(parents=True, exist_ok=True)
        # Test write
        test_file = storage_path / ".drama-tui-test"
        test_file.write_text("ok")
        test_file.unlink()
        console.print(f"   [green]✓[/] Path valid: {storage_path}\n")
    except (OSError, PermissionError) as e:
        console.print(f"   [red]❌ Tidak bisa akses path: {e}[/]")
        if not click.confirm("Lanjut dengan path ini anyway?", default=False):
            return

    # === Gemini API key ===
    console.print("[bold]2. Gemini API Key[/]")
    console.print("   Dapatkan gratis di: https://aistudio.google.com/apikey")
    console.print("   Free tier: 15 request/min, 1500/day (cukup untuk produksi)\n")

    api_key = click.prompt(
        "Gemini API Key (atau kosongkan untuk skip)",
        default=current.gemini_api_key,
        hide_input=False,
        show_default=False,
    )

    # === Editor preference ===
    console.print("\n[bold]3. Editor untuk edit naskah Jawa[/]")
    console.print("   Auto-detect: VSCode > Sublime > nano > TextEdit")
    editor = click.prompt(
        "Editor (auto/vscode/subl/nano/textedit)",
        default=current.editor,
        type=str,
    )

    # === Image viewer ===
    console.print("\n[bold]4. Image viewer untuk preview reference[/]")
    console.print("   Auto-detect: VSCode > Preview > Quick Look (Mac)")
    image_viewer = click.prompt(
        "Image viewer (auto/vscode/preview/quicklook)",
        default=current.image_viewer,
        type=str,
    )

    # === Save config ===
    new_config = cm.update(
        storage_root=str(storage_path),
        gemini_api_key=api_key,
        editor=editor,
        image_viewer=image_viewer,
    )

    # Init index DB
    HOME_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    index_db = DramasIndexDB(DRAMAS_INDEX_DB)
    index_db.init_schema()

    # Print summary
    console.print("\n[bold green]✓ Setup selesai![/]\n")
    console.print(Panel(
        f"[bold]Config tersimpan:[/]\n{cm.config_path}\n\n"
        f"[bold]Storage root:[/]\n{new_config.storage_root}\n\n"
        f"[bold]Index DB:[/]\n{DRAMAS_INDEX_DB}\n\n"
        f"[bold]Gemini API Key:[/]\n{'✓ Set' if new_config.gemini_api_key else '⚠ Tidak set (bisa edit nanti)'}\n\n"
        f"[bold]Editor:[/]\n{new_config.editor}\n\n"
        f"[bold]Image viewer:[/]\n{new_config.image_viewer}",
        title="📋 Ringkasan Setup",
        border_style="cyan",
    ))

    console.print("\n[bold]Langkah selanjutnya:[/]")
    console.print("  [cyan]drama-tui new[/]   Buat drama pertama kamu\n")


@main.command()
@click.option("--title", "-t", prompt="Judul drama", help="Judul drama")
@click.option("--era", "-e", type=click.Choice([
    "mataram_kuno", "majapahit", "mataram_islam", "sriwijaya",
    "samudera_pasai", "ternate_tidore", "custom"
], case_sensitive=False), default="majapahit", help="Era sejarah")
@click.option("--language", "-l", type=click.Choice(["jv", "id", "su", "min"], case_sensitive=False),
              default="jv", help="Bahasa utama naskah")
@click.option("--description", "-d", default="", help="Deskripsi singkat drama")
def new(title: str, era: str, language: str, description: str) -> None:
    """Buat drama baru."""
    print_banner()

    if not require_init():
        return

    cm = ConfigManager()
    config = cm.config

    slug = slugify(title)
    storage_path = Path(config.storage_root) / slug

    # Cek duplikat slug
    if storage_path.exists():
        console.print(f"[red]❌ Drama dengan slug '{slug}' sudah ada di:[/]")
        console.print(f"   {storage_path}")
        if not click.confirm("Override?", default=False):
            return

    # Buat folder & DB
    storage_path.mkdir(parents=True, exist_ok=True)
    drama_paths = get_drama_paths(drama_id=0, drama_slug=slug, storage_root=config.storage_root)
    drama_paths.ensure_dirs()

    # Init DB untuk drama ini
    drama_db = Database(drama_paths.db_path)
    drama_db.init_schema()
    drama_db.close()

    # Insert ke index DB
    index_db = DramasIndexDB(DRAMAS_INDEX_DB)
    index_db.init_schema()
    drama_id = index_db.add_drama(
        slug=slug,
        title=title,
        era=era,
        language=language,
        storage_path=str(storage_path),
        db_path=str(drama_paths.db_path),
    )

    # Insert ke drama DB
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    drama_db = Database(drama_paths.db_path)
    with drama_db.conn as conn:
        conn.execute(
            """INSERT INTO dramas (slug, title, description, era, language, audio_locale,
                                    target_platform, aspect_ratio, storage_path, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (slug, title, description, era.lower(), language.lower(), language.lower(),
             "youtube_shorts", "9:16", str(storage_path), now, now)
        )
    drama_db.close()

    # Success
    console.print(f"\n[bold green]✓ Drama baru dibuat![/]\n")
    console.print(Panel(
        f"[bold]ID:[/]\n{drama_id}\n\n"
        f"[bold]Judul:[/]\n{title}\n\n"
        f"[bold]Era:[/]\n{era}\n\n"
        f"[bold]Bahasa:[/]\n{language}\n\n"
        f"[bold]Folder:[/]\n{storage_path}\n\n"
        f"[bold]Database:[/]\n{drama_paths.db_path}",
        title=f"🎬 Drama #{drama_id}",
        border_style="green",
    ))

    console.print("\n[bold]Langkah selanjutnya:[/]")
    console.print(f"  [cyan]drama-tui info {drama_id}[/]   Lihat detail drama")
    console.print(f"  [cyan]drama-tui wizard {drama_id}[/]  Mulai produksi (5-step wizard)")


@main.command(name="list")
def list_dramas() -> None:
    """List semua drama."""
    print_banner()

    if not DRAMAS_INDEX_DB.exists():
        console.print("[yellow]⚠ Belum ada drama. Jalankan: drama-tui new[/]")
        return

    index_db = DramasIndexDB(DRAMAS_INDEX_DB)
    dramas = index_db.list_dramas()

    if not dramas:
        console.print("[yellow]⚠ Belum ada drama. Jalankan: drama-tui new[/]")
        return

    table = Table(title="📚 Daftar Drama", show_header=True, header_style="bold cyan")
    table.add_column("ID", justify="right", style="cyan", width=4)
    table.add_column("Slug", style="white", width=25)
    table.add_column("Judul", style="white", width=35)
    table.add_column("Era", style="yellow", width=18)
    table.add_column("Bahasa", style="green", width=8)
    table.add_column("Created", style="dim", width=20)

    for d in dramas:
        created = d.get("created_at", "")[:10]
        table.add_row(
            str(d["id"]),
            d["slug"],
            d["title"],
            d.get("era", "-"),
            d.get("language", "-"),
            created,
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(dramas)} drama[/]")


@main.command()
@click.argument("drama_id", type=int)
def info(drama_id: int) -> None:
    """Lihat detail satu drama."""
    print_banner()

    if not DRAMAS_INDEX_DB.exists():
        console.print("[red]❌ Index DB belum di-init. Jalankan: drama-tui init[/]")
        return

    index_db = DramasIndexDB(DRAMAS_INDEX_DB)
    drama = index_db.get_drama(drama_id)

    if not drama:
        console.print(f"[red]❌ Drama ID {drama_id} tidak ditemukan.[/]")
        console.print("Jalankan: [cyan]drama-tui list[/] untuk lihat semua drama.")
        return

    # Load drama DB untuk statistik
    drama_db = Database(drama["db_path"])
    with drama_db.conn as conn:
        # Count episodes
        cur = conn.execute("SELECT COUNT(*) FROM episodes WHERE deleted_at IS NULL")
        episodes_count = cur.fetchone()[0]

        # Count characters
        cur = conn.execute("SELECT COUNT(*) FROM characters WHERE deleted_at IS NULL")
        characters_count = cur.fetchone()[0]

        # Count scenes
        cur = conn.execute("SELECT COUNT(*) FROM scenes WHERE deleted_at IS NULL")
        scenes_count = cur.fetchone()[0]

        # Count storyboards (all episodes)
        cur = conn.execute("""
            SELECT COUNT(*) FROM storyboards s
            JOIN episodes e ON s.episode_id = e.id
            WHERE e.drama_id = (SELECT id FROM dramas LIMIT 1)
            AND s.deleted_at IS NULL
        """)
        storyboards_count = cur.fetchone()[0]
    drama_db.close()

    console.print(Panel(
        f"[bold]ID:[/] {drama['id']}\n"
        f"[bold]Judul:[/] {drama['title']}\n"
        f"[bold]Slug:[/] {drama['slug']}\n"
        f"[bold]Era:[/] {drama.get('era', '-')}\n"
        f"[bold]Bahasa:[/] {drama.get('language', '-')}\n\n"
        f"[bold]Folder:[/]\n{drama['storage_path']}\n\n"
        f"[bold]Database:[/]\n{drama['db_path']}\n\n"
        f"[bold]Dibuat:[/] {drama['created_at']}",
        title=f"🎬 Drama #{drama_id}",
        border_style="cyan",
    ))

    # Stats table
    stats = Table(title="📊 Statistik", show_header=False)
    stats.add_column("Komponen", style="white", width=20)
    stats.add_column("Jumlah", style="cyan", justify="right")
    stats.add_row("📺 Episode", str(episodes_count))
    stats.add_row("👤 Karakter", str(characters_count))
    stats.add_row("🏞️  Scene", str(scenes_count))
    stats.add_row("🎬 Storyboard", str(storyboards_count))
    console.print(stats)


@main.command()
@click.argument("drama_id", type=int)
def delete(drama_id: int) -> None:
    """Hapus drama (DB + folder)."""
    print_banner()

    if not DRAMAS_INDEX_DB.exists():
        console.print("[red]❌ Tidak ada drama untuk dihapus.[/]")
        return

    index_db = DramasIndexDB(DRAMAS_INDEX_DB)
    drama = index_db.get_drama(drama_id)

    if not drama:
        console.print(f"[red]❌ Drama ID {drama_id} tidak ditemukan.[/]")
        return

    console.print(f"\n[bold red]⚠ Konfirmasi Hapus Drama[/]")
    console.print(Panel(
        f"Judul: {drama['title']}\n"
        f"Folder: {drama['storage_path']}\n"
        f"DB: {drama['db_path']}",
        title=f"Hapus Drama #{drama_id}",
        border_style="red",
    ))

    if not click.confirm("\nYakin hapus?", default=False):
        console.print("[yellow]Batal.[/]")
        return

    if click.confirm("Hapus juga folder & file-nya?", default=False):
        import shutil
        storage_path = Path(drama["storage_path"])
        if storage_path.exists():
            shutil.rmtree(storage_path)
            console.print(f"[green]✓ Folder dihapus: {storage_path}[/]")

    # Hapus dari index
    index_db.delete_drama(drama_id)
    console.print(f"[green]✓ Drama #{drama_id} dihapus dari index.[/]")


@main.command()
@click.argument("drama_id", type=int)
@click.option("--mock-ai", is_flag=True, default=True,
              help="Pakai mock AI (tidak call Gemini API). Default untuk Phase 2.")
def wizard(drama_id: int, mock_ai: bool) -> None:
    """Run 5-step production wizard."""
    print_banner()

    if not DRAMAS_INDEX_DB.exists():
        console.print("[red]❌ Belum ada drama. Jalankan: drama-tui new[/]")
        return

    index_db = DramasIndexDB(DRAMAS_INDEX_DB)
    drama = index_db.get_drama(drama_id)

    if not drama:
        console.print(f"[red]❌ Drama ID {drama_id} tidak ditemukan.[/]")
        return

    # Run wizard
    from .wizard import ProductionWizard
    try:
        w = ProductionWizard(drama_id=drama_id, use_mock_ai=mock_ai)
        w.run()
    except ValueError as e:
        console.print(f"[red]❌ {e}[/]")
        return
    except KeyboardInterrupt:
        console.print("\n[yellow]👋 Wizard dihentikan. Data sudah tersimpan.[/]")
        return


# ============================================================
# ENTRY POINT
# ============================================================
def main_entry() -> None:
    """Entry point untuk script."""
    main()


if __name__ == "__main__":
    main_entry()

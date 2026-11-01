"""
Editor integration — auto-detect editor terbaik di Mac/Linux.

Priority:
1. $EDITOR env var (user override)
2. VSCode (code command)
3. Sublime Text (subl command)
4. nano (terminal fallback)
5. TextEdit (Mac GUI fallback via `open -a`)

Untuk edit naskah Jawa panjang, TUI akan:
1. Write draft ke temp file dengan extension .txt
2. Spawn editor (blocking, tunggu user save & close)
3. Read back content dari temp file
4. Cleanup
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from rich.console import Console

console = Console()


# ============================================================
# EDITOR DETECTION
# ============================================================
def detect_editor(preference: str = "auto") -> tuple[str, list[str]]:
    """
    Detect editor terbaik yang tersedia di sistem.

    Returns:
        Tuple (editor_name, command_args) — siap di-spawn dengan file path
    """
    # 1. User preference explicit
    if preference == "vscode":
        if shutil.which("code"):
            return ("VSCode", ["code", "--wait"])
        console.print("[yellow]⚠ VSCode 'code' command tidak ditemukan. Fall back.[/]")
    elif preference == "subl":
        if shutil.which("subl"):
            return ("Sublime Text", ["subl", "--wait"])
        console.print("[yellow]⚠ Sublime Text 'subl' command tidak ditemukan. Fall back.[/]")
    elif preference == "nano":
        if shutil.which("nano"):
            return ("nano", ["nano", "-R"])
    elif preference == "textedit":
        # Mac-only
        if shutil.which("open"):
            return ("TextEdit", ["open", "-a", "TextEdit", "-W"])
        console.print("[yellow]⚠ 'open' command tidak ditemukan.[/]")

    # 2. Auto-detect — priority: VSCode > Sublime > nano > TextEdit
    if shutil.which("code"):
        return ("VSCode", ["code", "--wait"])

    if shutil.which("subl"):
        return ("Sublime Text", ["subl", "--wait"])

    if shutil.which("nano"):
        return ("nano", ["nano", "-R"])

    # 3. Mac fallback — TextEdit via open
    if shutil.which("open"):
        return ("TextEdit (Mac)", ["open", "-a", "TextEdit", "-W"])

    raise RuntimeError("Tidak ada editor yang tersedia. Install VSCode atau nano.")


# ============================================================
# EDIT FLOW
# ============================================================
def edit_text(
    content: str,
    filename: str = "draft.txt",
    editor_pref: str = "auto",
    console: Optional[Console] = None,
) -> str:
    """
    Spawn editor dengan content, tunggu user save & close, return edited content.

    Args:
        content: Text content untuk di-edit
        filename: Nama file temporary (e.g., "naskah_ep01.txt")
        editor_pref: Editor preference ("auto" | "vscode" | "subl" | "nano" | "textedit")
        console: Rich console instance (optional)

    Returns:
        Edited content (string)
    """
    if console is None:
        console = Console()

    # Detect editor
    editor_name, editor_cmd = detect_editor(editor_pref)

    # Create temp file
    tmp_dir = Path(tempfile.gettempdir()) / "drama-tui"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize filename
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
    if not safe_name.endswith(".txt"):
        safe_name += ".txt"

    tmp_file = tmp_dir / safe_name
    tmp_file.write_text(content, encoding="utf-8")

    console.print(f"\n[bold cyan]📝 Membuka editor: {editor_name}[/]")
    console.print(f"   File: [dim]{tmp_file}[/]")
    console.print(f"   [yellow]Edit, save, lalu tutup editor untuk lanjut...[/]\n")

    try:
        # Spawn editor — blocking until user closes
        full_cmd = editor_cmd + [str(tmp_file)]
        result = subprocess.run(full_cmd, check=True)

        # Read back edited content
        edited_content = tmp_file.read_text(encoding="utf-8")

        # Stats
        original_lines = content.count("\n")
        edited_lines = edited_content.count("\n")
        original_words = len(content.split())
        edited_words = len(edited_content.split())

        console.print(f"\n[green]✓ Editor ditutup.[/]")
        console.print(
            f"   [dim]Original: {original_words} kata, {original_lines} baris[/]"
        )
        console.print(
            f"   [dim]Edited:   {edited_words} kata, {edited_lines} baris[/]"
        )

        return edited_content

    except subprocess.CalledProcessError as e:
        console.print(f"\n[red]❌ Editor error: {e}[/]")
        return content
    finally:
        # Cleanup temp file (opsional — bisa keep untuk debug)
        try:
            tmp_file.unlink(missing_ok=True)
        except OSError:
            pass


# ============================================================
# IMAGE VIEWER (Phase 4 — preview reference image)
# ============================================================
def open_image_preview(image_path: Path, viewer_pref: str = "auto") -> None:
    """
    Buka image preview di viewer terbaik.

    Priority:
    - VSCode (jika ada, dan user prefer)
    - Mac Preview (default)
    - Linux: xdg-open
    - Windows: start
    """
    if not image_path.exists():
        console.print(f"[red]❌ Image tidak ditemukan: {image_path}[/]")
        return

    # Mac
    if shutil.which("open"):
        subprocess.run(["open", str(image_path)], check=False)
        return

    # Linux
    if shutil.which("xdg-open"):
        subprocess.run(["xdg-open", str(image_path)], check=False)
        return

    # Fallback — print path
    console.print(f"[yellow]⚠ Tidak ada image viewer. Path: {image_path}[/]")

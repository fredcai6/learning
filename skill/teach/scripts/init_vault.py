#!/usr/bin/env python3
"""Create a learning vault, or repair one: directories, settings, asset link.

Usage: python3 init_vault.py VAULT_DIR --archive-dir DIR

Safe to re-run: existing files are left alone. `assets/base` is linked to
this mechanism repo's `assets/base`, so lessons pick up stylesheet and
widget updates without copying; the link is ignored by the vault's git.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BASE_ASSETS = Path(__file__).resolve().parents[3] / "assets" / "base"


def write_if_missing(path: Path, text: str) -> None:
    if not path.exists():
        path.write_text(text, encoding="utf-8")
        print(f"wrote {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("vault")
    parser.add_argument("--archive-dir", required=True,
                        help="where archived source copies live; outside the vault repo")
    parser.add_argument("--state-db", help="the website's state database; outside the vault repo")
    args = parser.parse_args()

    vault = Path(args.vault).expanduser().resolve()
    archive_dir = Path(args.archive_dir).expanduser().resolve()
    if archive_dir == vault or vault in archive_dir.parents:
        raise SystemExit("archive_dir must be outside the vault: archived copies stay out of git")

    for sub in ("sources", "map", "topics", "learners", "assets"):
        (vault / sub).mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)

    settings = f'archive_dir = "{archive_dir}"\n'
    if args.state_db:
        settings += f'state_db = "{Path(args.state_db).expanduser().resolve()}"\n'
    write_if_missing(vault / "vault.toml", settings)
    write_if_missing(vault / "learners.toml",
                     "# One table per learner. The id is the directory name under learners/.\n"
                     "#\n"
                     "# [learners.alex]\n"
                     '# name = "Alex"\n'
                     '# email = "alex@example.com"        # the address Cloudflare Access passes through\n'
                     "# telegram_chat_id = 123456789      # filled in when the tutor bot first hears from them\n")

    gitignore = vault / ".gitignore"
    lines = gitignore.read_text(encoding="utf-8").splitlines() if gitignore.exists() else []
    for needed in ("/assets/base", ".env", "*.sqlite"):
        if needed not in lines:
            lines.append(needed)
    gitignore.write_text("\n".join(lines) + "\n", encoding="utf-8")

    link = vault / "assets" / "base"
    if link.is_symlink() and link.resolve() != BASE_ASSETS:
        link.unlink()
    if not link.exists():
        link.symlink_to(BASE_ASSETS, target_is_directory=True)
        print(f"linked {link} -> {BASE_ASSETS}")

    print(f"vault ready at {vault}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

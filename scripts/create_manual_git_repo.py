from __future__ import annotations

import argparse
import os
import shutil
import stat
import time
import zlib
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path


DEFAULT_REMOTE = "ssh://git@ssh.github.com:443/dongfanghong656/OMPCP.git"


EXCLUDED_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}


def is_excluded_relative_path(relative_path: Path) -> bool:
    parts = relative_path.parts
    if any(part in EXCLUDED_DIR_NAMES for part in parts):
        return True
    if len(parts) >= 2 and parts[0] == "reports" and parts[1] == "_unit_test_tmp":
        return True
    if any(part.endswith("_unit_test_tmp") for part in parts):
        return True
    return False


def copy_source_tree(source: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for root, dir_names, file_names in os.walk(source):
        root_path = Path(root)
        rel_root = root_path.relative_to(source)
        dir_names[:] = [
            name
            for name in dir_names
            if not is_excluded_relative_path(rel_root / name)
        ]
        if is_excluded_relative_path(rel_root):
            continue
        (output / rel_root).mkdir(parents=True, exist_ok=True)
        for file_name in file_names:
            rel_file = rel_root / file_name
            if is_excluded_relative_path(rel_file):
                continue
            src_file = root_path / file_name
            dst_file = output / rel_file
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)


def write_object(git_dir: Path, object_type: bytes, payload: bytes) -> str:
    header = object_type + b" " + str(len(payload)).encode("ascii") + b"\0"
    raw = header + payload
    digest = sha1(raw).hexdigest()
    object_dir = git_dir / "objects" / digest[:2]
    object_dir.mkdir(parents=True, exist_ok=True)
    object_path = object_dir / digest[2:]
    if not object_path.exists():
        object_path.write_bytes(zlib.compress(raw))
    return digest


@dataclass(frozen=True)
class TreeEntry:
    mode: str
    name: str
    object_id: str
    is_tree: bool


def git_tree_sort_key(entry: TreeEntry) -> bytes:
    # Git sorts trees by byte path; directory names compare as if they had a trailing slash.
    suffix = "/" if entry.is_tree else ""
    return (entry.name + suffix).encode("utf-8")


def build_tree(git_dir: Path, directory: Path) -> str:
    entries: list[TreeEntry] = []
    for child in directory.iterdir():
        if child.name == ".git":
            continue
        if child.is_dir():
            object_id = build_tree(git_dir, child)
            entries.append(TreeEntry("40000", child.name, object_id, True))
        elif child.is_file():
            mode = "100755" if os.access(child, os.X_OK) and os.name != "nt" else "100644"
            object_id = write_object(git_dir, b"blob", child.read_bytes())
            entries.append(TreeEntry(mode, child.name, object_id, False))
    payload = bytearray()
    for entry in sorted(entries, key=git_tree_sort_key):
        payload.extend(f"{entry.mode} {entry.name}".encode("utf-8"))
        payload.append(0)
        payload.extend(bytes.fromhex(entry.object_id))
    return write_object(git_dir, b"tree", bytes(payload))


def build_commit(git_dir: Path, tree_id: str, message: str) -> str:
    now = int(time.time())
    timezone = time.strftime("%z") or "+0000"
    ident = f"Codex <codex@local> {now} {timezone}"
    payload = (
        f"tree {tree_id}\n"
        f"author {ident}\n"
        f"committer {ident}\n"
        "\n"
        f"{message}\n"
    ).encode("utf-8")
    return write_object(git_dir, b"commit", payload)


def write_git_metadata(output: Path, remote_url: str, commit_id: str) -> None:
    git_dir = output / ".git"
    (git_dir / "objects" / "info").mkdir(parents=True, exist_ok=True)
    (git_dir / "objects" / "pack").mkdir(parents=True, exist_ok=True)
    (git_dir / "refs" / "heads").mkdir(parents=True, exist_ok=True)
    (git_dir / "refs" / "tags").mkdir(parents=True, exist_ok=True)
    (git_dir / "refs" / "heads" / "main").write_text(commit_id + "\n", encoding="ascii")
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="ascii")
    (git_dir / "config").write_text(
        "[core]\n"
        "\trepositoryformatversion = 0\n"
        "\tfilemode = false\n"
        "\tbare = false\n"
        "\tlogallrefupdates = true\n"
        "[remote \"origin\"]\n"
        f"\turl = {remote_url}\n"
        "\tfetch = +refs/heads/*:refs/remotes/origin/*\n"
        "[branch \"main\"]\n"
        "\tremote = origin\n"
        "\tmerge = refs/heads/main\n",
        encoding="ascii",
    )
    # Git for Windows is happier if the gitdir files are not read-only after copy2.
    for path in git_dir.rglob("*"):
        try:
            path.chmod(path.stat().st_mode | stat.S_IWRITE)
        except OSError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a Git repository without invoking git-init, for sandboxed publish workspaces."
    )
    parser.add_argument("--source", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--output", required=True)
    parser.add_argument("--remote", default=DEFAULT_REMOTE)
    parser.add_argument("--message", default="Initialize OMPCP OCT Mie PSF diagnostic stack")
    args = parser.parse_args()

    source = Path(args.source).resolve()
    output = Path(args.output).resolve()
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"Output directory already exists and is not empty: {output}")

    copy_source_tree(source, output)
    git_dir = output / ".git"
    git_dir.mkdir(parents=True, exist_ok=True)
    tree_id = build_tree(git_dir, output)
    commit_id = build_commit(git_dir, tree_id, args.message)
    write_git_metadata(output, args.remote, commit_id)
    print(f"created_repo={output}")
    print(f"commit={commit_id}")
    print(f"remote={args.remote}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

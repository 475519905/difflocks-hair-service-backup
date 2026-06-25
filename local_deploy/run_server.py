#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import platform
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER_DIR = ROOT / "server"


def normalize_path(value: str) -> str:
    if not value:
        return value
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return str(path)


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def find_blender() -> str:
    env_value = os.environ.get("BLENDER_PATH", "").strip()
    if env_value:
        return env_value

    candidates: list[Path] = []
    if platform.system().lower() == "windows":
        program_files = [os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")]
        for root in program_files:
            if root:
                candidates.extend(Path(root).glob("Blender Foundation/Blender */blender.exe"))
    else:
        found = shutil.which("blender")
        if found:
            return found
        candidates.extend(Path("/opt").glob("blender*/blender"))

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return ""


def set_defaults() -> None:
    os.environ.setdefault("DIFFLOCKS_PUBLIC", "1")
    os.environ.setdefault("DIFFLOCKS_WEB_PASSWORD", "")
    os.environ.setdefault("HAIRGEN_INVITE_CODE", "")
    os.environ.setdefault("DIFFLOCKS_WEB_DATA", str(ROOT / "runtime_data"))
    os.environ.setdefault("DIFFLOCKS_REPO", str(ROOT / "third_party" / "difflocks"))
    os.environ.setdefault("DIFFLOCKS_PYTHON", sys.executable)
    os.environ.setdefault("DIFFLOCKS_INPROCESS", "1")
    os.environ.setdefault("HAIRGEN_FACE_MODEL_PROVIDER", "off")
    os.environ.setdefault("HAIRGEN_FACE_MODEL_MODE", "cpu")

    for key in ("DIFFLOCKS_WEB_DATA", "DIFFLOCKS_REPO", "DIFFLOCKS_PYTHON", "BLENDER_PATH"):
        if os.environ.get(key):
            os.environ[key] = normalize_path(os.environ[key])
    if not os.environ.get("BLENDER_PATH"):
        os.environ["BLENDER_PATH"] = find_blender()


def preflight() -> None:
    data_dir = Path(os.environ["DIFFLOCKS_WEB_DATA"])
    data_dir.mkdir(parents=True, exist_ok=True)

    checks = [
        ("DiffLocks 代码目录", Path(os.environ["DIFFLOCKS_REPO"])),
        ("DiffLocks Python", Path(os.environ["DIFFLOCKS_PYTHON"])),
        ("Blender 可执行文件", Path(os.environ["BLENDER_PATH"]) if os.environ.get("BLENDER_PATH") else None),
    ]
    for label, path in checks:
        if path is None or not path.exists():
            print(f"[WARN] {label} 未找到: {path or ''}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local DiffLocks hair service.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--env", default=str(ROOT / ".env"))
    args = parser.parse_args()

    load_env(Path(args.env))
    set_defaults()
    preflight()

    os.chdir(SERVER_DIR)
    sys.path.insert(0, str(SERVER_DIR))

    import uvicorn

    uvicorn.run("main:app", host=args.host, port=args.port, workers=1, timeout_keep_alive=30)


if __name__ == "__main__":
    main()


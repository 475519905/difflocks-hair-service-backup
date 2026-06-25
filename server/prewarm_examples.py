#!/usr/bin/env python3
import json
import shutil
import sys
import time
import traceback
import uuid
from pathlib import Path

from PIL import Image, ImageOps

APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR))

import main  # noqa: E402


STATE_PATH = main.EXAMPLE_CACHE_DIR / "prewarm_status.json"
LOG_PATH = main.EXAMPLE_CACHE_DIR / "prewarm.log"


def log(message: str) -> None:
    main.EXAMPLE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}"
    print(line, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def write_state(items: dict[str, dict], current: str = "") -> None:
    done = sum(1 for item in items.values() if item.get("status") in {"ready", "copied"})
    failed = sum(1 for item in items.values() if item.get("status") == "failed")
    main.write_json(
        STATE_PATH,
        {
            "updated_at": time.time(),
            "current": current,
            "total": len(items),
            "ready": done,
            "failed": failed,
            "items": items,
        },
    )


def normalized_params(params: dict) -> dict:
    values = dict(main.DEFAULT_EXAMPLE_PARAMS)
    values.update(params or {})
    return values


def params_match(params: dict) -> bool:
    return normalized_params(params) == dict(main.DEFAULT_EXAMPLE_PARAMS)


def cache_ready(name: str) -> bool:
    root = main.example_cache_dir(name)
    return (root / "result.blend").exists() and (root / "hair.blend").exists() and any((root / "preview").glob("*.png"))


def copy_if_exists(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def copy_job_to_cache(name: str, job_root: Path, source_job_id: str, source: str) -> None:
    dest = main.example_cache_dir(name)
    tmp = dest.with_name(f"{dest.name}.tmp-{uuid.uuid4().hex[:8]}")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)

    copy_if_exists(job_root / "input.png", tmp / "input.png")
    copy_if_exists(job_root / "result.blend", tmp / "result.blend")
    copy_if_exists(job_root / "hair.blend", tmp / "hair.blend")
    copy_if_exists(job_root / "difflocks" / "rgb.png", tmp / "difflocks" / "rgb.png")

    preview_src = job_root / "preview"
    if preview_src.exists():
        shutil.copytree(preview_src, tmp / "preview")

    main.write_json(
        tmp / "cache_status.json",
        {
            "name": name,
            "source": source,
            "source_job_id": source_job_id,
            "params": dict(main.DEFAULT_EXAMPLE_PARAMS),
            "created_at": time.time(),
        },
    )

    if dest.exists():
        shutil.rmtree(dest)
    tmp.replace(dest)


def find_reusable_job(name: str) -> tuple[str, Path] | None:
    candidates = sorted(
        main.JOBS_DIR.glob("*/status.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for status_file in candidates:
        try:
            data = json.loads(status_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("filename") != name or data.get("status") != "done":
            continue
        if not params_match(data.get("params", {})):
            continue
        root = status_file.parent
        if (root / "result.blend").exists() and (root / "hair.blend").exists():
            return root.name, root
    return None


def create_job_for_example(name: str) -> str:
    source = main.example_path(name)
    job_id = "example_" + uuid.uuid4().hex[:12]
    root = main.job_dir(job_id)
    root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, root / "upload.bin")
    with Image.open(source) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        img.save(root / "input.png")

    job = {
        "id": job_id,
        "status": "queued",
        "stage": "queued",
        "created_at": main.now_ts(),
        "updated_at": main.now_ts(),
        "filename": name,
        "params": dict(main.DEFAULT_EXAMPLE_PARAMS),
        "example_cache": True,
    }
    with main.jobs_lock:
        main.jobs[job_id] = job
        main.write_json(main.status_path(job_id), job)
    return job_id


def main_entry() -> int:
    main.DATA_DIR.mkdir(parents=True, exist_ok=True)
    main.JOBS_DIR.mkdir(parents=True, exist_ok=True)
    main.EXAMPLE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    main.load_jobs()

    names = [path.name for path in main.example_files()]
    items = {name: {"status": "pending", "message": ""} for name in names}
    write_state(items)

    for name in names:
        try:
            if cache_ready(name):
                items[name] = {"status": "ready", "message": "cache already exists"}
                write_state(items, name)
                log(f"{name}: cache already exists")
                continue

            reusable = find_reusable_job(name)
            if reusable is not None:
                source_job_id, source_root = reusable
                copy_job_to_cache(name, source_root, source_job_id, "existing_job")
                items[name] = {"status": "copied", "message": f"copied from {source_job_id}"}
                write_state(items, name)
                log(f"{name}: copied from existing job {source_job_id}")
                continue

            items[name] = {"status": "running", "message": "generating"}
            write_state(items, name)
            log(f"{name}: generating")
            job_id = create_job_for_example(name)
            main.run_job(job_id)
            copy_job_to_cache(name, main.job_dir(job_id), job_id, "generated")
            items[name] = {"status": "ready", "message": f"generated from {job_id}"}
            write_state(items, name)
            log(f"{name}: generated from {job_id}")
        except Exception as exc:
            traceback_text = traceback.format_exc()
            items[name] = {"status": "failed", "message": str(exc)}
            write_state(items, name)
            log(f"{name}: failed: {exc}\n{traceback_text}")

    write_state(items)
    return 0 if not any(item.get("status") == "failed" for item in items.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main_entry())

#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
from pathlib import Path

import cv2
import numpy as np
import torch

_ENGINE = None
_ENGINE_REPO: Path | None = None
_IMG2HAIR = None
_ORIGINAL_CROP_FACE = None
_ORIGINAL_SAMPLE_STRANDS = None
_CURRENT_CROP = 3.4
_CURRENT_UPSAMPLE = 4
_CROP_FOREHEAD_WEIGHT = float(os.environ.get("HAIRGEN_CROP_FOREHEAD_WEIGHT", "0.64"))


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--img-path", required=True)
    parser.add_argument("--out-path", required=True)
    parser.add_argument("--seed", type=int, default=5)
    parser.add_argument("--steps", type=int, default=180)
    parser.add_argument("--cfg", type=float, default=1.6)
    parser.add_argument("--crop", type=float, default=3.4)
    parser.add_argument("--upsample", type=int, default=4)
    parser.add_argument("--chunks", type=int, default=20)
    return parser.parse_args()


def configure_torch():
    if torch.cuda.is_available():
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.benchmark = True
        try:
            torch.set_float32_matmul_precision("high")
        except Exception:
            pass


def prepare_repo(repo: Path):
    global _IMG2HAIR
    os.chdir(repo)
    repo_str = str(repo)
    if repo_str not in sys.path:
        sys.path.insert(0, repo_str)

    from inference import img2hair

    install_param_overrides(img2hair)
    _IMG2HAIR = img2hair
    return img2hair


def install_param_overrides(img2hair):
    global _ORIGINAL_CROP_FACE, _ORIGINAL_SAMPLE_STRANDS
    if _ORIGINAL_CROP_FACE is None:
        _ORIGINAL_CROP_FACE = img2hair.crop_face
    if _ORIGINAL_SAMPLE_STRANDS is None:
        _ORIGINAL_SAMPLE_STRANDS = img2hair.sample_strands_from_scalp_with_density

    def crop_face_with_requested_size(image, face_landmarks, output_size, crop_size_multiplier=3.4):
        return crop_face_for_hair_shape(
            image,
            face_landmarks,
            output_size,
            crop_size_multiplier=_CURRENT_CROP,
        )

    def sample_strands_with_requested_density(*sample_args, **sample_kwargs):
        sample_kwargs["upsample_multiplier"] = _CURRENT_UPSAMPLE
        return _ORIGINAL_SAMPLE_STRANDS(*sample_args, **sample_kwargs)

    img2hair.crop_face = crop_face_with_requested_size
    img2hair.sample_strands_from_scalp_with_density = sample_strands_with_requested_density


def crop_face_for_hair_shape(image, face_landmarks, output_size, crop_size_multiplier=3.4):
    img_h, img_w, _ = image.shape
    if face_landmarks is None:
        return cv2.resize(image, (output_size, output_size))

    face_landmarks_px = [(int(lm[0] * img_w), int(lm[1] * img_h)) for lm in face_landmarks]
    if len(face_landmarks_px) <= 454:
        return cv2.resize(image, (output_size, output_size))

    chin = face_landmarks_px[152]
    forehead = face_landmarks_px[10]
    left_cheek = face_landmarks_px[234]
    right_cheek = face_landmarks_px[454]

    face_width = max(1, abs(right_cheek[0] - left_cheek[0]))
    face_height = max(1, abs(chin[1] - forehead[1]))
    crop_size = max(1, int(max(face_width, face_height) * crop_size_multiplier))

    face_center_x = (left_cheek[0] + right_cheek[0]) // 2
    forehead_weight = max(0.4, min(0.75, _CROP_FOREHEAD_WEIGHT))
    face_center_y = int(forehead[1] * forehead_weight + chin[1] * (1.0 - forehead_weight))

    crop_x1 = int(face_center_x - crop_size // 2)
    crop_x2 = crop_x1 + crop_size
    crop_y1 = int(face_center_y - crop_size // 2)
    crop_y2 = crop_y1 + crop_size

    pad_left = max(0, -crop_x1)
    pad_right = max(0, crop_x2 - img_w)
    pad_top = max(0, -crop_y1)
    pad_bottom = max(0, crop_y2 - img_h)

    crop_x1 = max(0, crop_x1)
    crop_y1 = max(0, crop_y1)
    crop_x2 = min(img_w, crop_x2)
    crop_y2 = min(img_h, crop_y2)
    cropped_region = image[crop_y1:crop_y2, crop_x1:crop_x2]
    if cropped_region.size == 0:
        return cv2.resize(image, (output_size, output_size))

    if pad_left or pad_right or pad_top or pad_bottom:
        cropped_region = cv2.copyMakeBorder(
            cropped_region,
            top=pad_top,
            bottom=pad_bottom,
            left=pad_left,
            right=pad_right,
            borderType=cv2.BORDER_REPLICATE,
        )

    h, w = cropped_region.shape[:2]
    interpolation = cv2.INTER_AREA if h > output_size or w > output_size else cv2.INTER_CUBIC
    return cv2.resize(cropped_region, (output_size, output_size), interpolation=interpolation)


def get_engine(repo: Path, chunks: int):
    global _ENGINE, _ENGINE_REPO
    img2hair = prepare_repo(repo)
    if _ENGINE is not None and _ENGINE_REPO == repo:
        return _ENGINE

    _ENGINE = img2hair.DiffLocksInference(
        "./checkpoints/strand_vae/strand_codec.pt",
        "./configs/config_scalp_texture_conditional.json",
        "./checkpoints/difflocks_diffusion/scalp_v9_40k_06730000.pth",
        "./checkpoints/rgb2material/rgb2material.pt",
        cfg_val=1.0,
        nr_iters_denoise=100,
        nr_chunks_decode=chunks,
    )
    _ENGINE_REPO = repo
    return _ENGINE


def run_inference(repo, img_path, out_path, seed=5, steps=180, cfg=1.6, crop=3.4, upsample=4, chunks=20):
    global _CURRENT_CROP, _CURRENT_UPSAMPLE
    repo = Path(repo).resolve()
    img_path = str(Path(img_path).resolve())
    out_path = Path(out_path).resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    configure_torch()
    torch.manual_seed(seed)
    np.random.seed(seed)
    random.seed(seed)
    _CURRENT_CROP = crop
    _CURRENT_UPSAMPLE = upsample

    print(
        json.dumps(
            {
                "event": "start",
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "crop": crop,
                "crop_forehead_weight": _CROP_FOREHEAD_WEIGHT,
                "upsample": upsample,
                "chunks": chunks,
            },
            ensure_ascii=True,
        ),
        flush=True,
    )

    difflocks = get_engine(repo, chunks)
    difflocks.cfg_val = cfg
    difflocks.nr_iters_denoise = steps
    difflocks.nr_chunks_decode_strands = chunks

    strands, material = difflocks.file2hair(img_path, str(out_path))
    if strands is None:
        raise RuntimeError("No face was detected in the input image.")

    npz_path = out_path / "difflocks_output_strands.npz"
    positions = np.load(npz_path)["positions"]
    summary = {
        "event": "done",
        "npz": str(npz_path),
        "strands": int(positions.shape[0]),
        "points_per_strand": int(positions.shape[1]),
        "dtype": str(positions.dtype),
    }
    print(json.dumps(summary, ensure_ascii=True), flush=True)
    return summary


def main():
    args = parse_args()
    run_inference(
        args.repo,
        args.img_path,
        args.out_path,
        seed=args.seed,
        steps=args.steps,
        cfg=args.cfg,
        crop=args.crop,
        upsample=args.upsample,
        chunks=args.chunks,
    )


if __name__ == "__main__":
    main()

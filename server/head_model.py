#!/usr/bin/env python3
import argparse
import os
import sys
from pathlib import Path

import cv2
import numpy as np
import yaml

if not hasattr(np, "int"):
    np.int = int


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument(
        "--tddfa-dir",
        default="/home/c47551/HairStep/external/3DDFA_V2",
        help="Path to 3DDFA_V2 checkout with weights/configs.",
    )
    parser.add_argument("--config", default="configs/mb1_120x120.yml")
    parser.add_argument("--mode", choices=["cpu", "gpu"], default="gpu")
    return parser.parse_args()


def main():
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    tddfa_dir = Path(args.tddfa_dir).resolve()
    sys.path.insert(0, str(tddfa_dir))
    os.chdir(tddfa_dir)

    from FaceBoxes import FaceBoxes
    from TDDFA import TDDFA

    image_bgr = cv2.imread(args.image, cv2.IMREAD_COLOR)
    if image_bgr is None:
        raise RuntimeError(f"Could not read image: {args.image}")
    height, width = image_bgr.shape[:2]

    config_path = tddfa_dir / args.config
    cfg = yaml.load(config_path.read_text(encoding="utf-8"), Loader=yaml.SafeLoader)
    tddfa = TDDFA(gpu_mode=args.mode == "gpu", **cfg)
    face_boxes = FaceBoxes()
    boxes = face_boxes(image_bgr)
    if not boxes:
        raise RuntimeError("3DDFA could not detect a face in the input image.")

    # Use the largest detected face.
    boxes = sorted(boxes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]), reverse=True)
    param_lst, roi_box_lst = tddfa(image_bgr, [boxes[0]])
    ver = tddfa.recon_vers(param_lst, roi_box_lst, dense_flag=True)[0].astype(np.float32)

    x = ver[0]
    y = ver[1]
    z = ver[2]
    vertices = np.stack([x, z, height - y], axis=1).astype(np.float32)
    uvs = np.stack(
        [
            np.clip(x / max(width - 1, 1), 0.0, 1.0),
            np.clip(1.0 - y / max(height - 1, 1), 0.0, 1.0),
        ],
        axis=1,
    ).astype(np.float32)

    faces = tddfa.tri.astype(np.int32)
    texture_path = out_dir / "photo_head_texture.png"
    cv2.imwrite(str(texture_path), image_bgr)

    out_npz = out_dir / "photo_head.npz"
    np.savez(
        out_npz,
        vertices=vertices,
        faces=faces,
        uvs=uvs,
        source="3DDFA_V2_BFM_dense",
        image_width=np.array([width], dtype=np.int32),
        image_height=np.array([height], dtype=np.int32),
    )

    print(f"HEAD_NPZ={out_npz}")
    print(f"HEAD_TEXTURE={texture_path}")
    print("HEAD_SOURCE=3DDFA_V2_BFM_dense")
    print(f"HEAD_VERTICES={vertices.shape[0]}")
    print(f"HEAD_FACES={faces.shape[0]}")


if __name__ == "__main__":
    main()

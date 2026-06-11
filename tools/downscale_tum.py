#!/usr/bin/env python3
import argparse
import shutil
from pathlib import Path

import cv2


def downscale_dir(src_dir: Path, dst_dir: Path, size, interp):
    dst_dir.mkdir(parents=True, exist_ok=True)
    for img_path in sorted(src_dir.glob("*.png")):
        img = cv2.imread(str(img_path), cv2.IMREAD_UNCHANGED)
        if img is None:
            continue
        resized = cv2.resize(img, size, interpolation=interp)
        cv2.imwrite(str(dst_dir / img_path.name), resized)


def main():
    parser = argparse.ArgumentParser(description="Downscale TUM rgb/depth folders.")
    parser.add_argument("src_dir", help="TUM dataset directory with rgb/ depth/")
    parser.add_argument("dst_dir", help="Output directory")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    args = parser.parse_args()

    src = Path(args.src_dir)
    dst = Path(args.dst_dir)
    rgb_src = src / "rgb"
    depth_src = src / "depth"
    if not rgb_src.exists() or not depth_src.exists():
        raise SystemExit("Missing rgb/ or depth/ in source directory.")

    rgb_dst = dst / "rgb"
    depth_dst = dst / "depth"

    size = (args.width, args.height)
    downscale_dir(rgb_src, rgb_dst, size, cv2.INTER_AREA)
    downscale_dir(depth_src, depth_dst, size, cv2.INTER_NEAREST)

    assoc_src = src / "associations.txt"
    if assoc_src.exists():
        shutil.copy2(assoc_src, dst / "associations.txt")

    print("Downscaled:", src)
    print("Output:", dst)
    print("Size:", size)


if __name__ == "__main__":
    main()

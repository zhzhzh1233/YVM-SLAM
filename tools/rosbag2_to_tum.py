#!/usr/bin/env python3
import argparse
import os
from pathlib import Path

import numpy as np
import yaml

try:
    import cv2
except ImportError as exc:
    raise SystemExit("Missing OpenCV (cv2). Install python3-opencv or pip install opencv-python.") from exc

try:
    from rosbags.rosbag2 import Reader
    from rosbags.typesys import Stores, get_typestore
except ImportError as exc:
    raise SystemExit("Missing rosbags. Install with: python3 -m pip install rosbags") from exc


def load_default_topics(bag_dir: Path):
    meta_path = bag_dir / "metadata.yaml"
    if not meta_path.exists():
        return None, None
    data = yaml.safe_load(meta_path.read_text())
    topics = data.get("rosbag2_bagfile_information", {}).get("topics_with_message_count", [])
    color_topic = None
    depth_topic = None
    for t in topics:
        name = t["topic_metadata"]["name"]
        if "color/image" in name and color_topic is None:
            color_topic = name
        if "depth/image" in name and depth_topic is None:
            depth_topic = name
    return color_topic, depth_topic


def stamp_to_sec(stamp):
    return stamp.sec + stamp.nanosec * 1e-9


def decode_image(msg):
    height = msg.height
    width = msg.width
    encoding = msg.encoding
    data = np.frombuffer(msg.data, dtype=np.uint8)
    if encoding in ("rgb8", "bgr8"):
        img = data.reshape((height, width, 3))
        if encoding == "rgb8":
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        return img, "bgr8"
    if encoding in ("mono8",):
        img = data.reshape((height, width))
        return img, "mono8"
    if encoding in ("16UC1", "mono16"):
        img = data.view(np.uint16).reshape((height, width))
        return img, "16UC1"
    if encoding in ("32FC1",):
        img = data.view(np.float32).reshape((height, width))
        return img, "32FC1"
    raise ValueError(f"Unsupported encoding: {encoding}")


def match_streams(rgb_times, depth_times, max_diff):
    matches = []
    j = 0
    for i, t in enumerate(rgb_times):
        while j + 1 < len(depth_times) and abs(depth_times[j + 1] - t) < abs(depth_times[j] - t):
            j += 1
        if abs(depth_times[j] - t) <= max_diff:
            matches.append((i, j))
    return matches


def main():
    parser = argparse.ArgumentParser(description="Convert rosbag2 RGB-D to TUM format.")
    parser.add_argument("bag_dir", help="rosbag2 directory (contains metadata.yaml)")
    parser.add_argument("out_dir", help="output TUM directory")
    parser.add_argument("--color_topic", default="", help="color image topic")
    parser.add_argument("--depth_topic", default="", help="depth image topic")
    parser.add_argument("--max_diff", type=float, default=0.02, help="max timestamp diff for association")
    parser.add_argument("--depth_scale", type=float, default=1000.0, help="scale for 32FC1 depth (m->mm)")
    args = parser.parse_args()

    bag_dir = Path(args.bag_dir)
    out_dir = Path(args.out_dir)
    out_rgb = out_dir / "rgb"
    out_depth = out_dir / "depth"
    out_rgb.mkdir(parents=True, exist_ok=True)
    out_depth.mkdir(parents=True, exist_ok=True)

    color_topic = args.color_topic
    depth_topic = args.depth_topic
    if not color_topic or not depth_topic:
        auto_color, auto_depth = load_default_topics(bag_dir)
        color_topic = color_topic or auto_color
        depth_topic = depth_topic or auto_depth
    if not color_topic or not depth_topic:
        raise SystemExit("Could not determine color/depth topics. Use --color_topic/--depth_topic.")

    typestore = get_typestore(Stores.ROS2_HUMBLE)
    rgb_times = []
    depth_times = []
    rgb_files = []
    depth_files = []

    with Reader(bag_dir) as reader:
        conns = [c for c in reader.connections if c.topic in (color_topic, depth_topic)]
        for conn, ts, raw in reader.messages(connections=conns):
            msg = typestore.deserialize_cdr(raw, conn.msgtype)
            t = stamp_to_sec(msg.header.stamp)
            img, enc = decode_image(msg)
            name = f"{t:.6f}.png"
            if conn.topic == color_topic:
                cv2.imwrite(str(out_rgb / name), img)
                rgb_times.append(t)
                rgb_files.append(name)
            else:
                if enc == "32FC1":
                    img = (img * args.depth_scale).astype(np.uint16)
                cv2.imwrite(str(out_depth / name), img)
                depth_times.append(t)
                depth_files.append(name)

    if not rgb_times or not depth_times:
        raise SystemExit("No rgb/depth images found. Check topics.")

    # Ensure time order
    rgb = sorted(zip(rgb_times, rgb_files), key=lambda x: x[0])
    depth = sorted(zip(depth_times, depth_files), key=lambda x: x[0])
    rgb_times, rgb_files = zip(*rgb)
    depth_times, depth_files = zip(*depth)

    matches = match_streams(rgb_times, depth_times, args.max_diff)
    assoc_path = out_dir / "associations.txt"
    with open(assoc_path, "w", encoding="utf-8") as f:
        for i, j in matches:
            f.write(
                f"{rgb_times[i]:.6f} rgb/{rgb_files[i]} "
                f"{depth_times[j]:.6f} depth/{depth_files[j]}\n"
            )

    print("Converted:", bag_dir)
    print("Color topic:", color_topic)
    print("Depth topic:", depth_topic)
    print("Output:", out_dir)
    print("Associations:", assoc_path)
    print("Pairs:", len(matches))


if __name__ == "__main__":
    main()

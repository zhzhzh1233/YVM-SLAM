#!/usr/bin/env python3
import json
import threading
import time
from typing import List

import cv2
import numpy as np
import rclpy
import torch
from rclpy.node import Node
from sensor_msgs.msg import Image
from vision_msgs.msg import Detection2DArray, Detection2D, ObjectHypothesisWithPose, BoundingBox2D
from std_msgs.msg import String

try:
    from ultralytics import YOLO
except ImportError as exc:
    raise SystemExit(
        "Missing ultralytics. Install it in your ROS environment: "
        "pip install ultralytics"
    ) from exc

try:
    from cv_bridge import CvBridge
except ImportError as exc:
    raise SystemExit(
        "Missing cv_bridge. Install ros-humble-cv-bridge or your ROS distro equivalent."
    ) from exc


DEFAULT_PROMPTS = ["person", "walking man", "car", "truck", "bus"]
EMPTY_PROMPT_TOKEN = "__none__"


class YoloWorldMaskNode(Node):
    def __init__(self) -> None:
        super().__init__("yolo_world_mask_node")
        self.declare_parameter("model_path", "yolov8s-worldv2.pt")
        self.declare_parameter("image_topic", "/color/image")
        self.declare_parameter("mask_topic", "/dynamic_mask")
        self.declare_parameter("detection_topic", "/dynamic_detections")
        self.declare_parameter("clean_image_topic", "/yolo/clean_image")
        self.declare_parameter("prompt_topic", "/yolo_world/prompts")
        self.declare_parameter("vlm_topic", "/vlm/prompts_json")
        self.declare_parameter("active_prompt_topic", "/yolo_world/active_prompts")
        self.declare_parameter("status_topic", "/yolo_world/status")
        self.declare_parameter("conf_thres", 0.25)
        self.declare_parameter("device", "cpu")
        self.declare_parameter("imgsz", 640)
        self.declare_parameter("half", False)
        self.declare_parameter("use_default_prompts", False)

        model_path = self.get_parameter("model_path").get_parameter_value().string_value
        self.conf_thres = float(
            self.get_parameter("conf_thres").get_parameter_value().double_value
        )
        self.device = self.get_parameter("device").get_parameter_value().string_value
        self.imgsz = int(self.get_parameter("imgsz").get_parameter_value().integer_value or 640)
        self.half = bool(self.get_parameter("half").get_parameter_value().bool_value)
        self.use_default_prompts = bool(
            self.get_parameter("use_default_prompts").get_parameter_value().bool_value
        )

        self.bridge = CvBridge()
        self.prompts_lock = threading.Lock()
        self.user_prompts: List[str] = []
        self.dynamic_prompts: List[str] = list(DEFAULT_PROMPTS) if self.use_default_prompts else []
        self.static_prompts: List[str] = []
        self.current_prompts: List[str] = []

        self.model = YOLO(model_path)
        self._set_device_defaults()

        image_topic = self.get_parameter("image_topic").get_parameter_value().string_value
        mask_topic = self.get_parameter("mask_topic").get_parameter_value().string_value
        detection_topic = self.get_parameter("detection_topic").get_parameter_value().string_value
        prompt_topic = self.get_parameter("prompt_topic").get_parameter_value().string_value
        clean_image_topic = (
            self.get_parameter("clean_image_topic").get_parameter_value().string_value
        )
        vlm_topic = self.get_parameter("vlm_topic").get_parameter_value().string_value
        active_prompt_topic = (
            self.get_parameter("active_prompt_topic").get_parameter_value().string_value
        )
        status_topic = self.get_parameter("status_topic").get_parameter_value().string_value

        self.sub_image = self.create_subscription(Image, image_topic, self.on_image, 10)
        self.sub_prompts = self.create_subscription(String, prompt_topic, self.on_prompts, 10)
        self.sub_vlm = self.create_subscription(String, vlm_topic, self.on_vlm_prompts, 10)
        self.pub_mask = self.create_publisher(Image, mask_topic, 10)
        self.pub_detections = self.create_publisher(Detection2DArray, detection_topic, 10)
        self.pub_clean = self.create_publisher(Image, clean_image_topic, 10)
        self.pub_active_prompts = self.create_publisher(String, active_prompt_topic, 10)
        self.pub_status = self.create_publisher(String, status_topic, 10)
        self.prompt_timer = self.create_timer(1.0, self.publish_active_prompts)

        self._apply_prompts()
        self.last_frame_time = 0.0
        self.fps_ema = 0.0

        self.get_logger().info(f"YOLO-World model loaded: {model_path}")
        self.get_logger().info(f"Image topic: {image_topic}")
        self.get_logger().info(f"Mask topic: {mask_topic}")
        self.get_logger().info(f"Detection topic: {detection_topic}")
        self.get_logger().info(f"Clean image topic: {clean_image_topic}")
        self.get_logger().info(f"Prompt topic: {prompt_topic}")
        self.get_logger().info(f"VLM topic: {vlm_topic}")
        self.get_logger().info(f"Active prompt topic: {active_prompt_topic}")
        self.get_logger().info(f"Status topic: {status_topic}")
        self.get_logger().info(f"Device: {self.device}, imgsz: {self.imgsz}, half: {self.half}")

    def _apply_prompts(self) -> None:
        with self.prompts_lock:
            combined = self.dynamic_prompts + self.static_prompts
            if not combined and self.use_default_prompts:
                combined = list(DEFAULT_PROMPTS)
            if not combined and not self.use_default_prompts:
                prompts = [EMPTY_PROMPT_TOKEN]
            else:
                prompts = list(dict.fromkeys(combined))
        if prompts == self.current_prompts:
            return
        self._set_device_defaults()
        self._set_prompt_precision()
        try:
            self.model.set_classes(prompts)
        except Exception as exc:  # pylint: disable=broad-except
            self.get_logger().error(f"Failed to set YOLO-World prompts: {exc}")
            return
        self._restore_precision()
        if prompts == [EMPTY_PROMPT_TOKEN]:
            self.current_prompts = []
            self.get_logger().info("Active prompts: [] (waiting for VLM/user)")
        else:
            self.current_prompts = prompts
            self.get_logger().info(f"Active prompts: {prompts}")
        self.publish_active_prompts()

    def publish_active_prompts(self) -> None:
        msg = String()
        msg.data = json.dumps(self.current_prompts)
        self.pub_active_prompts.publish(msg)

    def _publish_status(self, labels: List[str]) -> None:
        msg = String()
        payload = {
            "fps": round(self.fps_ema, 2),
            "detections": labels,
            "dynamic": self.dynamic_prompts,
            "static_interest": self.static_prompts,
            "active": self.current_prompts,
        }
        msg.data = json.dumps(payload)
        self.pub_status.publish(msg)

    def _update_vlm_lists(self, dynamic_list: List[str], static_list: List[str]) -> None:
        with self.prompts_lock:
            self.dynamic_prompts = dynamic_list
            self.static_prompts = static_list
        self._apply_prompts()

    def on_vlm_prompts(self, msg: String) -> None:
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().warning("Invalid VLM JSON; ignoring.")
            return
        dynamic_list = [str(x).strip() for x in data.get("dynamic", []) if str(x).strip()]
        static_list = [str(x).strip() for x in data.get("static_interest", []) if str(x).strip()]
        self._update_vlm_lists(dynamic_list, static_list)

    def _set_device_defaults(self) -> None:
        if self.device.startswith("cuda"):
            try:
                torch.set_default_device(self.device)
            except Exception:  # pylint: disable=broad-except
                pass
            try:
                self.model.to(self.device)
            except Exception:  # pylint: disable=broad-except
                pass
        else:
            try:
                torch.set_default_device("cpu")
            except Exception:  # pylint: disable=broad-except
                pass

    def _set_prompt_precision(self) -> None:
        if not self.half:
            return
        try:
            self.model.model.float()
        except Exception:  # pylint: disable=broad-except
            pass

    def _restore_precision(self) -> None:
        if not self.half:
            return
        try:
            self.model.model.half()
        except Exception:  # pylint: disable=broad-except
            pass

    def on_prompts(self, msg: String) -> None:
        payload = msg.data.strip()
        if not payload:
            return
        prompts: List[str]
        try:
            data = json.loads(payload)
            if isinstance(data, list):
                prompts = [str(item).strip() for item in data if str(item).strip()]
            else:
                prompts = [payload]
        except json.JSONDecodeError:
            prompts = [p.strip() for p in payload.split(",") if p.strip()]

        with self.prompts_lock:
            self.user_prompts = prompts
        # User prompts are treated as dynamic list additions.
        self._update_vlm_lists(self.user_prompts or self.dynamic_prompts, self.static_prompts)

    def on_image(self, msg: Image) -> None:
        try:
            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except Exception as exc:  # pylint: disable=broad-except
            self.get_logger().error(f"Failed to decode image: {exc}")
            return

        try:
            results = self.model.predict(
                source=frame,
                verbose=False,
                conf=self.conf_thres,
                device=self.device,
                imgsz=self.imgsz,
                half=self.half,
            )
        except RuntimeError as exc:
            # Some Jetson CUDA builds fail when fusing in half precision; retry in float.
            if self.half and "dtype" in str(exc):
                self.get_logger().warning("Half precision failed; retrying in float.")
                self.half = False
                results = self.model.predict(
                    source=frame,
                    verbose=False,
                    conf=self.conf_thres,
                    device=self.device,
                    imgsz=self.imgsz,
                    half=False,
                )
            else:
                raise
        if not results:
            return

        h, w = frame.shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)
        clean = frame.copy()
        boxes = results[0].boxes
        detections_msg = Detection2DArray()
        detections_msg.header = msg.header
        detected_labels: List[str] = []
        if boxes is not None and boxes.xyxy is not None:
            xyxy = boxes.xyxy.cpu().numpy()
            cls = boxes.cls.cpu().numpy() if boxes.cls is not None else None
            conf = boxes.conf.cpu().numpy() if boxes.conf is not None else None
            names = results[0].names
            for i, box in enumerate(xyxy):
                x1, y1, x2, y2 = box[:4].astype(int)
                x1 = max(0, min(w - 1, x1))
                y1 = max(0, min(h - 1, y1))
                x2 = max(0, min(w, x2))
                y2 = max(0, min(h, y2))
                label = "object"
                if cls is not None and int(cls[i]) in names:
                    label = str(names[int(cls[i])])
                detected_labels.append(label)
                if x2 > x1 and y2 > y1:
                    if label in self.dynamic_prompts:
                        mask[y1:y2, x1:x2] = 255
                        clean[y1:y2, x1:x2] = 0
                    elif label in self.static_prompts:
                        cv2.rectangle(clean, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.putText(clean, label, (x1, max(0, y1 - 5)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

                det = Detection2D()
                det.bbox = BoundingBox2D()
                det.bbox.center.position.x = float((x1 + x2) / 2.0)
                det.bbox.center.position.y = float((y1 + y2) / 2.0)
                det.bbox.size_x = float(max(0, x2 - x1))
                det.bbox.size_y = float(max(0, y2 - y1))

                hypothesis = ObjectHypothesisWithPose()
                hypothesis.hypothesis.class_id = label
                hypothesis.hypothesis.score = float(conf[i]) if conf is not None else 0.0
                det.results.append(hypothesis)
                detections_msg.detections.append(det)

        mask_msg = self.bridge.cv2_to_imgmsg(mask, encoding="mono8")
        mask_msg.header = msg.header
        self.pub_mask.publish(mask_msg)
        self.pub_detections.publish(detections_msg)

        clean_msg = self.bridge.cv2_to_imgmsg(clean, encoding="bgr8")
        clean_msg.header = msg.header
        self.pub_clean.publish(clean_msg)

        now = time.time()
        if self.last_frame_time > 0:
            fps = 1.0 / max(1e-6, now - self.last_frame_time)
            if self.fps_ema <= 0:
                self.fps_ema = fps
            else:
                self.fps_ema = (0.9 * self.fps_ema) + (0.1 * fps)
        self.last_frame_time = now
        if detected_labels:
            unique_labels = sorted(set(detected_labels))
        else:
            unique_labels = []
        self._publish_status(unique_labels)


def main() -> None:
    rclpy.init()
    node = YoloWorldMaskNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()

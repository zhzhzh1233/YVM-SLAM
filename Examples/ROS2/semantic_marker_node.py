#!/usr/bin/env python3
import json
from typing import List, Optional

import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
from std_msgs.msg import String
from vision_msgs.msg import Detection2DArray
from visualization_msgs.msg import Marker, MarkerArray
from geometry_msgs.msg import PointStamped
import tf2_ros


class SemanticMarkerNode(Node):
    def __init__(self) -> None:
        super().__init__("semantic_marker_node")
        self.declare_parameter("detection_topic", "/dynamic_detections")
        self.declare_parameter("depth_topic", "/depth/image")
        self.declare_parameter("camera_info_topic", "/color/camera_info")
        self.declare_parameter("status_topic", "/yolo_world/status")
        self.declare_parameter("marker_topic", "/semantic_markers")
        self.declare_parameter("target_frame", "odom")
        self.declare_parameter("max_depth", 5.0)

        self.detection_topic = (
            self.get_parameter("detection_topic").get_parameter_value().string_value
        )
        self.depth_topic = self.get_parameter("depth_topic").get_parameter_value().string_value
        self.camera_info_topic = (
            self.get_parameter("camera_info_topic").get_parameter_value().string_value
        )
        self.status_topic = self.get_parameter("status_topic").get_parameter_value().string_value
        self.marker_topic = self.get_parameter("marker_topic").get_parameter_value().string_value
        self.target_frame = self.get_parameter("target_frame").get_parameter_value().string_value
        self.max_depth = float(
            self.get_parameter("max_depth").get_parameter_value().double_value
        )

        self.sub_det = self.create_subscription(
            Detection2DArray, self.detection_topic, self.on_detections, 10
        )
        self.sub_depth = self.create_subscription(Image, self.depth_topic, self.on_depth, 10)
        self.sub_info = self.create_subscription(
            CameraInfo, self.camera_info_topic, self.on_camera_info, 10
        )
        self.sub_status = self.create_subscription(String, self.status_topic, self.on_status, 10)
        self.pub_markers = self.create_publisher(MarkerArray, self.marker_topic, 10)

        self.depth_image: Optional[np.ndarray] = None
        self.depth_header = None
        self.fx = self.fy = self.cx = self.cy = None
        self.static_labels: List[str] = []

        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

        self.get_logger().info(f"Semantic marker topic: {self.marker_topic}")
        self.get_logger().info(f"Target frame: {self.target_frame}")

    def on_status(self, msg: String) -> None:
        try:
            data = json.loads(msg.data)
        except Exception:
            return
        self.static_labels = data.get("static_interest", []) or []

    def on_camera_info(self, msg: CameraInfo) -> None:
        if msg.k[0] == 0.0:
            return
        self.fx = msg.k[0]
        self.fy = msg.k[4]
        self.cx = msg.k[2]
        self.cy = msg.k[5]

    def on_depth(self, msg: Image) -> None:
        if msg.height == 0 or msg.width == 0:
            return
        depth = np.frombuffer(bytes(msg.data), dtype=np.float32)
        if depth.size != msg.height * msg.width:
            return
        self.depth_image = depth.reshape((msg.height, msg.width))
        self.depth_header = msg.header

    def on_detections(self, msg: Detection2DArray) -> None:
        if self.depth_image is None or self.fx is None:
            return
        markers = MarkerArray()
        if not msg.detections:
            self.pub_markers.publish(markers)
            return

        h, w = self.depth_image.shape
        marker_id = 0
        for det in msg.detections:
            label = ""
            if det.results:
                label = det.results[0].hypothesis.class_id
            if not label or (self.static_labels and label not in self.static_labels):
                continue

            u = int(det.bbox.center.position.x)
            v = int(det.bbox.center.position.y)
            if u < 0 or v < 0 or u >= w or v >= h:
                continue

            z = float(self.depth_image[v, u])
            if not np.isfinite(z) or z <= 0.0:
                z = self._local_depth(u, v)
            if not np.isfinite(z) or z <= 0.0 or z > self.max_depth:
                continue

            x = (u - self.cx) * z / self.fx
            y = (v - self.cy) * z / self.fy

            size_x = max(0.05, float(det.bbox.size_x) * z / self.fx)
            size_y = max(0.05, float(det.bbox.size_y) * z / self.fy)
            size_z = max(0.05, 0.5 * min(size_x, size_y))

            pt = PointStamped()
            pt.header = msg.header
            pt.point.x = x
            pt.point.y = y
            pt.point.z = z

            frame_id = pt.header.frame_id or "base_link"
            target_frame = self.target_frame or frame_id
            if target_frame != frame_id:
                try:
                    pt = self.tf_buffer.transform(pt, target_frame, timeout=rclpy.duration.Duration(seconds=0.05))
                    frame_id = target_frame
                except Exception:
                    frame_id = pt.header.frame_id or frame_id

            cube = Marker()
            cube.header.frame_id = frame_id
            cube.header.stamp = msg.header.stamp
            cube.ns = "semantic_boxes"
            cube.id = marker_id
            cube.type = Marker.CUBE
            cube.action = Marker.ADD
            cube.pose.position = pt.point
            cube.pose.orientation.w = 1.0
            cube.scale.x = size_x
            cube.scale.y = size_y
            cube.scale.z = size_z
            cube.color.r = 0.1
            cube.color.g = 0.8
            cube.color.b = 0.3
            cube.color.a = 0.6
            cube.lifetime.sec = 1
            markers.markers.append(cube)

            text = Marker()
            text.header.frame_id = frame_id
            text.header.stamp = msg.header.stamp
            text.ns = "semantic_labels"
            text.id = marker_id + 1000
            text.type = Marker.TEXT_VIEW_FACING
            text.action = Marker.ADD
            text.pose.position.x = pt.point.x
            text.pose.position.y = pt.point.y
            text.pose.position.z = pt.point.z + size_z * 0.7
            text.pose.orientation.w = 1.0
            text.scale.z = 0.12
            text.color.r = 1.0
            text.color.g = 1.0
            text.color.b = 1.0
            text.color.a = 0.9
            text.text = label
            text.lifetime.sec = 1
            markers.markers.append(text)

            marker_id += 1

        self.pub_markers.publish(markers)

    def _local_depth(self, u: int, v: int) -> float:
        window = self.depth_image[max(0, v - 2): v + 3, max(0, u - 2): u + 3]
        vals = window[np.isfinite(window) & (window > 0)]
        if vals.size == 0:
            return float("nan")
        return float(np.median(vals))


def main() -> None:
    rclpy.init()
    node = SemanticMarkerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import base64
import json
import os
import threading
import time
from typing import Optional

import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String

try:
    from openai import OpenAI
except ImportError as exc:
    raise SystemExit(
        "Missing openai package. Install it in your venv: pip install openai"
    ) from exc

# Static API key fallback (set your key here if you want it hardcoded).
DEFAULT_API_KEY = "sk-1de8b729c6cb4cf1b9496aa2ec498cf4"


class VLMSupervisorNode(Node):
    def __init__(self) -> None:
        super().__init__("vlm_supervisor_node")

        self.declare_parameter("image_topic", "/color/image")
        self.declare_parameter("user_query_topic", "/user_query")
        self.declare_parameter("output_topic", "/vlm/prompts_json")
        self.declare_parameter("override_topic", "/vlm/override")
        self.declare_parameter("process_interval", 5.0)
        self.declare_parameter("auto_analyze", False)
        self.declare_parameter("require_user_query", True)
        self.declare_parameter("model_name", "qwen-vl-max")
        self.declare_parameter("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.declare_parameter("api_key_env", "DASHSCOPE_API_KEY")
        self.declare_parameter("api_key", "")
        self.declare_parameter("jpeg_quality", 50)

        image_topic = self.get_parameter("image_topic").get_parameter_value().string_value
        query_topic = self.get_parameter("user_query_topic").get_parameter_value().string_value
        output_topic = self.get_parameter("output_topic").get_parameter_value().string_value
        override_topic = (
            self.get_parameter("override_topic").get_parameter_value().string_value
        )
        self.process_interval = float(
            self.get_parameter("process_interval").get_parameter_value().double_value
        )
        self.auto_analyze = bool(
            self.get_parameter("auto_analyze").get_parameter_value().bool_value
        )
        self.require_user_query = bool(
            self.get_parameter("require_user_query").get_parameter_value().bool_value
        )
        self.model_name = self.get_parameter("model_name").get_parameter_value().string_value
        self.base_url = self.get_parameter("base_url").get_parameter_value().string_value
        api_env = self.get_parameter("api_key_env").get_parameter_value().string_value
        api_key_param = self.get_parameter("api_key").get_parameter_value().string_value
        self.jpeg_quality = int(
            self.get_parameter("jpeg_quality").get_parameter_value().integer_value or 50
        )

        api_key = api_key_param or os.environ.get(api_env, "") or DEFAULT_API_KEY
        if not api_key or api_key == "sk-REPLACE_ME":
            raise SystemExit(
                "Missing API key. Set param api_key, env DASHSCOPE_API_KEY, "
                "or edit DEFAULT_API_KEY in vlm_supervisor_node.py."
            )

        self.client = OpenAI(api_key=api_key, base_url=self.base_url)
        self.bridge = CvBridge()
        self.latest_image: Optional[Image] = None
        self.last_user_query: str = ""
        self.last_process_time = 0.0
        self.in_flight = False
        self.lock = threading.Lock()
        self.dynamic_memory = []
        self.static_memory = []
        self.last_action = "replace"
        self.last_note = ""

        self.sub_image = self.create_subscription(Image, image_topic, self.image_callback, 10)
        self.sub_query = self.create_subscription(String, query_topic, self.query_callback, 10)
        self.sub_override = self.create_subscription(
            String, override_topic, self.override_callback, 10
        )
        self.pub_json = self.create_publisher(String, output_topic, 10)
        self.pub_last_reply = self.create_publisher(String, "/vlm/last_reply", 10)
        self.timer = self.create_timer(1.0, self.timer_callback)

        self.get_logger().info("VLM Supervisor started.")
        self.get_logger().info(f"Image topic: {image_topic}")
        self.get_logger().info(f"User query topic: {query_topic}")
        self.get_logger().info(f"Output topic: {output_topic}")
        self.get_logger().info(f"Override topic: {override_topic}")
        self.get_logger().info(f"Model: {self.model_name}")
        self.get_logger().info(f"Auto analyze: {self.auto_analyze}")
        self.get_logger().info(f"Require user query: {self.require_user_query}")

    def image_callback(self, msg: Image) -> None:
        self.latest_image = msg

    def query_callback(self, msg: String) -> None:
        self.last_user_query = msg.data.strip()
        self.get_logger().info(f"User query: {self.last_user_query}")
        self.request_process(force=True)

    def override_callback(self, msg: String) -> None:
        try:
            data = json.loads(msg.data)
        except Exception:
            self.get_logger().warning("Invalid override JSON.")
            return
        dynamic = [str(x).strip() for x in data.get("dynamic", []) if str(x).strip()]
        static = [str(x).strip() for x in data.get("static_interest", []) if str(x).strip()]
        self.dynamic_memory = dynamic
        self.static_memory = static
        self.last_action = "manual"
        self.last_note = "Manual override applied."
        self._publish_prompts(self.dynamic_memory, self.static_memory)

    def timer_callback(self) -> None:
        if not self.auto_analyze or self.process_interval <= 0:
            return
        now = time.time()
        if now - self.last_process_time < self.process_interval:
            return
        self.request_process(force=False)

    def request_process(self, force: bool) -> None:
        with self.lock:
            if self.in_flight:
                return
            if self.latest_image is None:
                self._publish_error("no_image", "No image received yet.")
                return
            if self.require_user_query and not self.last_user_query:
                return
            self.in_flight = True
        thread = threading.Thread(target=self.process_vlm, args=(force,), daemon=True)
        thread.start()

    def encode_image_to_base64(self, cv_image) -> str:
        params = [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]
        ok, buffer = cv2.imencode(".jpg", cv_image, params)
        if not ok:
            return ""
        return base64.b64encode(buffer).decode("utf-8")

    def process_vlm(self, force: bool) -> None:
        try:
            if self.latest_image is None:
                self._publish_error("no_image", "No image received yet.")
                return
            cv_img = self.bridge.imgmsg_to_cv2(self.latest_image, "bgr8")
            b64 = self.encode_image_to_base64(cv_img)
            if not b64:
                self.get_logger().warning("Failed to encode image.")
                self._publish_error("encode_failed", "Failed to encode image.")
                return

            user_text = self.last_user_query if force else ""
            self.get_logger().info("Sending VLM request.")
            system_prompt = (
                "You are an agent managing object detection lists for SLAM.\n"
                "Goal: keep dynamic list focused on moving/unstable objects; "
                "keep static_interest list for user-relevant static objects.\n"
                "Return JSON only with keys:\n"
                "  dynamic: list of labels\n"
                "  static_interest: list of labels\n"
                "  action: 'replace' or 'merge' (prefer replace if unsure)\n"
                "  note: short reason for changes\n"
                "Example: {\"dynamic\": [\"person\"], \"static_interest\": [\"red cup\"], "
                "\"action\": \"replace\", \"note\": \"remove irrelevant items\"}"
            )

            user_content = [
                {"type": "text", "text": f"User instruction: {user_text}"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ]

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=200,
                timeout=30,
            )

            result_text = response.choices[0].message.content.strip()
            result_text = result_text.replace("```json", "").replace("```", "").strip()
            data = json.loads(result_text)
            dynamic = [str(x).strip() for x in data.get("dynamic", []) if str(x).strip()]
            static = [
                str(x).strip() for x in data.get("static_interest", []) if str(x).strip()
            ]
            action = str(data.get("action", "replace")).lower()
            note = str(data.get("note", "")).strip()

            if action == "merge":
                self.dynamic_memory = list(dict.fromkeys(self.dynamic_memory + dynamic))
                self.static_memory = list(dict.fromkeys(self.static_memory + static))
            else:
                self.dynamic_memory = dynamic
                self.static_memory = static
                action = "replace"

            self.last_action = action
            self.last_note = note
            self._publish_prompts(self.dynamic_memory, self.static_memory)
            reply = String()
            reply.data = json.dumps(
                {
                    "dynamic": self.dynamic_memory,
                    "static_interest": self.static_memory,
                    "action": self.last_action,
                    "note": self.last_note,
                    "raw": result_text,
                }
            )
            self.pub_last_reply.publish(reply)
            self.get_logger().info("Published VLM prompts JSON.")
            self.last_process_time = time.time()
        except Exception as exc:  # pylint: disable=broad-except
            self.get_logger().error(f"VLM failed: {exc}")
            self._publish_error("api_error", str(exc))
        finally:
            with self.lock:
                self.in_flight = False

    def _publish_prompts(self, dynamic, static) -> None:
        msg = String()
        msg.data = json.dumps({"dynamic": dynamic, "static_interest": static})
        self.pub_json.publish(msg)

    def _publish_error(self, code: str, detail: str) -> None:
        reply = String()
        reply.data = json.dumps(
            {
                "dynamic": self.dynamic_memory,
                "static_interest": self.static_memory,
                "action": "error",
                "note": f"{code}: {detail}",
                "raw": "",
            }
        )
        self.pub_last_reply.publish(reply)


def main() -> None:
    rclpy.init()
    node = VLMSupervisorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()

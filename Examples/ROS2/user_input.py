#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String


def main() -> None:
    rclpy.init()
    node = Node("user_input_node")
    pub = node.create_publisher(String, "/user_query", 10)

    print("=== YVM-SLAM User Input ===")
    print("Enter a query (e.g., 'find the red cup'). Type 'q' to quit.")

    try:
        while True:
            text = input(">> ").strip()
            if text.lower() == "q":
                break
            if not text:
                continue
            msg = String()
            msg.data = text
            pub.publish(msg)
            print(f"Sent: {text}")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()

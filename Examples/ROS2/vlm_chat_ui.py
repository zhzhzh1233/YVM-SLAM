#!/usr/bin/env python3
import json
import queue
import threading
import tkinter as tk
from tkinter import scrolledtext, ttk

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class VLMChatUI(Node):
    def __init__(self) -> None:
        super().__init__("vlm_chat_ui")
        self.pub_query = self.create_publisher(String, "/user_query", 10)
        self.pub_override = self.create_publisher(String, "/vlm/prompts_json", 10)
        self.sub_reply = self.create_subscription(String, "/vlm/last_reply", self.on_reply, 10)
        self.sub_active = self.create_subscription(
            String, "/yolo_world/active_prompts", self.on_active_prompts, 10
        )
        self.sub_status = self.create_subscription(
            String, "/yolo_world/status", self.on_status, 10
        )

        self.root = tk.Tk()
        self.root.title("YVM-SLAM VLM Console")
        self.root.geometry("1100x700")
        self.root.configure(bg="#121212")

        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Header.TLabel", font=("Helvetica", 16, "bold"), foreground="#f5f5f5")
        style.configure("Sub.TLabel", font=("Helvetica", 11), foreground="#cfcfcf")
        style.configure("Card.TLabelframe", background="#1c1c1c", foreground="#f5f5f5")
        style.configure("Card.TLabelframe.Label", foreground="#f5f5f5")

        header = ttk.Label(self.root, text="VLM Control Panel", style="Header.TLabel")
        header.pack(pady=(12, 4))

        self.status = ttk.Label(
            self.root, text="Status: waiting for input", style="Sub.TLabel"
        )
        self.status.pack(pady=(0, 8))

        body = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

        left = ttk.Frame(body)
        right = ttk.Frame(body)
        body.add(left, weight=3)
        body.add(right, weight=2)

        log_frame = ttk.LabelFrame(left, text="Dialog Log", style="Card.TLabelframe")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=(0, 8), pady=(0, 8))
        self.log = scrolledtext.ScrolledText(
            log_frame, state="disabled", wrap=tk.WORD, height=16, bg="#0f0f0f", fg="#d0d0d0"
        )
        self.log.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        entry_frame = ttk.LabelFrame(left, text="User Query", style="Card.TLabelframe")
        entry_frame.pack(fill=tk.X, padx=(0, 8))
        self.entry = tk.Text(entry_frame, height=3, bg="#0f0f0f", fg="#e0e0e0")
        self.entry.pack(fill=tk.X, padx=8, pady=8)

        button_row = ttk.Frame(entry_frame)
        button_row.pack(fill=tk.X, padx=8, pady=(0, 8))
        send_btn = ttk.Button(button_row, text="Send Query", command=self.send_text)
        send_btn.pack(side=tk.LEFT)
        clear_btn = ttk.Button(button_row, text="Clear", command=self.clear_entry)
        clear_btn.pack(side=tk.LEFT, padx=(8, 0))

        reply_frame = ttk.LabelFrame(right, text="Last VLM Reply", style="Card.TLabelframe")
        reply_frame.pack(fill=tk.BOTH, expand=False, pady=(0, 8))
        self.reply_box = scrolledtext.ScrolledText(
            reply_frame, state="disabled", wrap=tk.WORD, height=6, bg="#0f0f0f", fg="#d0d0d0"
        )
        self.reply_box.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        status_frame = ttk.LabelFrame(right, text="Live Status", style="Card.TLabelframe")
        status_frame.pack(fill=tk.X, expand=False, pady=(0, 8))
        self.fps_label = ttk.Label(status_frame, text="FPS: --", style="Sub.TLabel")
        self.fps_label.pack(anchor=tk.W, padx=8, pady=(6, 2))
        self.detected_box = scrolledtext.ScrolledText(
            status_frame, state="disabled", wrap=tk.WORD, height=4, bg="#0f0f0f", fg="#d0d0d0"
        )
        self.detected_box.pack(fill=tk.X, padx=8, pady=(0, 8))

        list_frame = ttk.LabelFrame(right, text="Prompt Lists", style="Card.TLabelframe")
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.dynamic_list = self._build_listbox(list_frame, "Dynamic (mask)")
        self.static_list = self._build_listbox(list_frame, "Static Interest (highlight)")
        self.active_list = self._build_listbox(list_frame, "Active Prompts (YOLO)")

        controls = ttk.Frame(list_frame)
        controls.pack(fill=tk.X, padx=8, pady=(0, 8))
        self.edit_lock = tk.BooleanVar(value=False)
        lock_btn = ttk.Checkbutton(
            controls, text="Lock lists (no auto-update)", variable=self.edit_lock
        )
        lock_btn.pack(side=tk.LEFT)

        self.add_entry = tk.Entry(controls)
        self.add_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        self.add_target = ttk.Combobox(controls, values=["dynamic", "static"], width=8)
        self.add_target.set("dynamic")
        self.add_target.pack(side=tk.LEFT)
        add_btn = ttk.Button(controls, text="Add", command=self.add_prompt)
        add_btn.pack(side=tk.LEFT, padx=(6, 0))
        remove_btn = ttk.Button(controls, text="Remove Selected", command=self.remove_prompt)
        remove_btn.pack(side=tk.LEFT, padx=(6, 0))
        apply_btn = ttk.Button(controls, text="Apply Override", command=self.apply_override)
        apply_btn.pack(side=tk.LEFT, padx=(6, 0))

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self._alive = True
        self.reply_queue: "queue.Queue[tuple]" = queue.Queue()
        self.root.after(200, self.drain_queue)

    def _build_listbox(self, parent, title):
        frame = ttk.LabelFrame(parent, text=title, style="Card.TLabelframe")
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
        listbox = tk.Listbox(frame, height=6, bg="#0f0f0f", fg="#d0d0d0")
        listbox.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
        return listbox

    def send_text(self) -> None:
        text = self.entry.get("1.0", tk.END).strip()
        if not text:
            return
        msg = String()
        msg.data = text
        self.pub_query.publish(msg)
        self.append_log(f">> {text}\n")
        self.clear_entry()
        self.status.configure(text="Status: query sent")

    def clear_entry(self) -> None:
        self.entry.delete("1.0", tk.END)

    def on_reply(self, msg: String) -> None:
        try:
            data = json.loads(msg.data)
            payload = {
                "dynamic": data.get("dynamic", []),
                "static_interest": data.get("static_interest", []),
                "raw": data.get("raw", msg.data),
            }
        except Exception:
            payload = {"dynamic": [], "static_interest": [], "raw": msg.data}
        self.reply_queue.put(("reply", payload))

    def on_active_prompts(self, msg: String) -> None:
        try:
            prompts = json.loads(msg.data)
            if not isinstance(prompts, list):
                prompts = []
        except Exception:
            prompts = []
        self.reply_queue.put(("active", prompts))

    def on_status(self, msg: String) -> None:
        try:
            data = json.loads(msg.data)
        except Exception:
            return
        self.reply_queue.put(("status", data))

    def append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert(tk.END, text)
        self.log.see(tk.END)
        self.log.configure(state="disabled")

    def set_reply(self, text: str) -> None:
        self.reply_box.configure(state="normal")
        self.reply_box.delete("1.0", tk.END)
        self.reply_box.insert(tk.END, text)
        self.reply_box.configure(state="disabled")

    def _update_list(self, listbox, items):
        listbox.delete(0, tk.END)
        for item in items:
            listbox.insert(tk.END, str(item))

    def drain_queue(self) -> None:
        while not self.reply_queue.empty():
            kind, payload = self.reply_queue.get()
            if kind == "reply":
                dynamic = payload.get("dynamic", [])
                static = payload.get("static_interest", [])
                line = f"dynamic: {dynamic}\nstatic_interest: {static}\n"
                self.append_log(line)
                self.set_reply(payload.get("raw", ""))
                self._update_list(self.dynamic_list, dynamic)
                self._update_list(self.static_list, static)
                self.status.configure(text="Status: reply received")
            elif kind == "active":
                self._update_list(self.active_list, payload)
            elif kind == "status":
                fps = payload.get("fps", "--")
                self.fps_label.configure(text=f"FPS: {fps}")
                detections = payload.get("detections", [])
                self.set_detected(detections)
                if not self.edit_lock.get():
                    self._update_list(self.dynamic_list, payload.get("dynamic", []))
                    self._update_list(self.static_list, payload.get("static_interest", []))
                    self._update_list(self.active_list, payload.get("active", []))
        if self._alive:
            self.root.after(200, self.drain_queue)

    def on_close(self) -> None:
        self._alive = False
        self.root.quit()

    def spin_gui(self) -> None:
        while self._alive:
            self.root.update_idletasks()
            self.root.update()

    def set_detected(self, labels) -> None:
        text = ", ".join(labels) if labels else "None"
        self.detected_box.configure(state="normal")
        self.detected_box.delete("1.0", tk.END)
        self.detected_box.insert(tk.END, text)
        self.detected_box.configure(state="disabled")

    def add_prompt(self) -> None:
        text = self.add_entry.get().strip()
        if not text:
            return
        target = self.add_target.get()
        if target == "static":
            self._add_to_listbox(self.static_list, text)
        else:
            self._add_to_listbox(self.dynamic_list, text)
        self.add_entry.delete(0, tk.END)

    def remove_prompt(self) -> None:
        for listbox in (self.dynamic_list, self.static_list):
            selections = list(listbox.curselection())
            for idx in reversed(selections):
                listbox.delete(idx)

    def apply_override(self) -> None:
        dynamic = self._listbox_items(self.dynamic_list)
        static = self._listbox_items(self.static_list)
        msg = String()
        msg.data = json.dumps({"dynamic": dynamic, "static_interest": static})
        self.pub_override.publish(msg)
        self.append_log(">> Applied manual override\n")
        self.status.configure(text="Status: manual override applied")

    def _listbox_items(self, listbox):
        return [listbox.get(i) for i in range(listbox.size())]

    def _add_to_listbox(self, listbox, text):
        existing = self._listbox_items(listbox)
        if text in existing:
            return
        listbox.insert(tk.END, text)


def main() -> None:
    rclpy.init()
    node = VLMChatUI()
    thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    thread.start()
    try:
        node.spin_gui()
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    try:
        rclpy.shutdown()
    except Exception:
        pass


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


HTML_PAGE = """<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>YVM-SLAM VLM Console</title>
  <script src="https://cdn.jsdelivr.net/npm/sortablejs@1.15.2/Sortable.min.js"></script>
  <style>
    body { margin: 0; font-family: "Inter", "SF Pro Text", sans-serif; background: #0f1115; color: #e6e6e6; }
    header { padding: 20px 28px; background: linear-gradient(120deg,#1b1f2a,#2a1f1d); }
    h1 { margin: 0; font-size: 22px; letter-spacing: 0.5px; }
    .grid { display: grid; grid-template-columns: 2fr 1.2fr; gap: 20px; padding: 20px 28px; }
    .card { background: #171a21; border-radius: 14px; padding: 16px; box-shadow: 0 6px 20px rgba(0,0,0,0.25); }
    .card h2 { margin: 0 0 10px; font-size: 16px; color: #c9d1f5; }
    textarea, input { width: 100%; border-radius: 10px; border: 1px solid #2d3242; background: #0c0f16; color: #e6e6e6; padding: 10px; }
    button { background: #3b63ff; color: white; border: none; padding: 10px 16px; border-radius: 10px; cursor: pointer; }
    button.secondary { background: #2b2f3c; }
    .row { display: flex; gap: 10px; }
    .pill { display: inline-block; padding: 6px 12px; border-radius: 999px; background: #242a3a; margin: 4px 6px 4px 0; cursor: grab; }
    .pill.active { background: #3757ff; }
    .list { min-height: 140px; background: #10131b; border: 1px solid #262b3c; border-radius: 10px; padding: 8px; }
    .status { font-size: 13px; color: #9fb1ff; }
  </style>
</head>
<body>
  <header>
    <h1>YVM-SLAM VLM Console</h1>
    <div class="status" id="status">Waiting for data…</div>
  </header>
  <div class="grid">
    <div>
      <div class="card">
        <h2>Dialog Log</h2>
        <div id="log" class="list" style="height:240px; overflow:auto;"></div>
      </div>
      <div class="card" style="margin-top:16px;">
        <h2>User Query</h2>
        <textarea id="query" rows="3" placeholder="e.g. highlight red cup, ignore chair"></textarea>
        <div class="row" style="margin-top:10px;">
          <button onclick="sendQuery()">Send</button>
          <button class="secondary" onclick="clearQuery()">Clear</button>
        </div>
      </div>
      <div class="card" style="margin-top:16px;">
        <h2>Last VLM Reply</h2>
        <pre id="reply" class="list"></pre>
      </div>
    </div>
    <div>
      <div class="card">
        <h2>Live Status</h2>
        <div>FPS: <span id="fps">--</span></div>
        <div style="margin-top:8px;">Detected:</div>
        <div id="detections" class="list"></div>
      </div>
      <div class="card" style="margin-top:16px;">
        <h2>Prompt Lists</h2>
        <div>Dynamic (mask)</div>
        <div id="dyn" class="list"></div>
        <div style="margin-top:8px;">Static Interest (highlight)</div>
        <div id="stat" class="list"></div>
        <div style="margin-top:8px;">Active (YOLO)</div>
        <div id="active" class="list"></div>
        <div class="row" style="margin-top:10px; align-items:center;">
          <input id="item" placeholder="object label"/>
          <select id="target">
            <option value="dynamic">dynamic</option>
            <option value="static_interest">static</option>
          </select>
          <label style="font-size:12px; color:#9aa4c5;">
            <input type="checkbox" id="lock" />
            Lock auto-sync
          </label>
        </div>
        <div class="row" style="margin-top:10px;">
          <button onclick="addItem()">Add</button>
          <button class="secondary" onclick="removeItem()">Remove</button>
          <button onclick="applyOverride()">Apply Override</button>
        </div>
      </div>
    </div>
  </div>
<script>
let state = {dynamic:[], static_interest:[], active:[], detections:[], fps:"--"};
let locked = false;

function renderList(id, items) {
  const el = document.getElementById(id);
  el.innerHTML = items.map(x => `<span class="pill">${x}</span>`).join("");
}

function refresh() {
  fetch("/api/state").then(r => r.json()).then(data => {
    state = data;
    document.getElementById("fps").textContent = data.fps ?? "--";
    renderList("detections", data.detections || []);
    if (!locked) {
      renderList("dyn", data.dynamic || []);
      renderList("stat", data.static_interest || []);
      renderList("active", data.active || []);
    }
    const note = data.last_note ? ("\\nNote: " + data.last_note) : "";
    const action = data.last_action ? ("\\nAction: " + data.last_action) : "";
    document.getElementById("reply").textContent = (data.last_reply_raw || "") + action + note;
    document.getElementById("status").textContent = "Last update: " + new Date().toLocaleTimeString();
  });
}

function sendQuery() {
  const text = document.getElementById("query").value.trim();
  if (!text) return;
  fetch("/api/query", {
    method:"POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({text})
  }).then(() => {
    document.getElementById("status").textContent = "Sent query at " + new Date().toLocaleTimeString();
  });
  const log = document.getElementById("log");
  log.innerHTML += `<div>>> ${text}</div>`;
  log.scrollTop = log.scrollHeight;
}

function clearQuery() { document.getElementById("query").value = ""; }

function addItem() {
  const item = document.getElementById("item").value.trim();
  const target = document.getElementById("target").value;
  if (!item) return;
  if (target === "dynamic") {
    state.dynamic.push(item);
    renderList("dyn", state.dynamic);
  } else {
    state.static_interest.push(item);
    renderList("stat", state.static_interest);
  }
  document.getElementById("item").value = "";
}

function removeItem() {
  const item = document.getElementById("item").value.trim();
  if (!item) return;
  state.dynamic = state.dynamic.filter(x => x !== item);
  state.static_interest = state.static_interest.filter(x => x !== item);
  document.getElementById("item").value = "";
  renderList("dyn", state.dynamic);
  renderList("stat", state.static_interest);
}

function applyOverride() {
  state.dynamic = toArray("dyn");
  state.static_interest = toArray("stat");
  fetch("/api/override", {method:"POST", body: JSON.stringify({
    dynamic: state.dynamic || [],
    static_interest: state.static_interest || []
  })});
}

setInterval(refresh, 800);
refresh();

document.getElementById("lock").addEventListener("change", (e) => {
  locked = e.target.checked;
});

function toArray(containerId) {
  return Array.from(document.getElementById(containerId).children).map(x => x.textContent.trim());
}

new Sortable(document.getElementById("dyn"), {animation: 150});
new Sortable(document.getElementById("stat"), {animation: 150});
new Sortable(document.getElementById("active"), {animation: 150});
</script>
</body>
</html>
"""


class WebBridge(Node):
    def __init__(self) -> None:
        super().__init__("vlm_web_ui")
        self.pub_query = self.create_publisher(String, "/user_query", 10)
        self.pub_override = self.create_publisher(String, "/vlm/override", 10)
        self.sub_reply = self.create_subscription(String, "/vlm/last_reply", self.on_reply, 10)
        self.sub_status = self.create_subscription(String, "/yolo_world/status", self.on_status, 10)

        self.state: Dict[str, Any] = {
            "dynamic": [],
            "static_interest": [],
            "active": [],
            "detections": [],
            "fps": "--",
            "last_reply_raw": "",
        }
        self.lock = threading.Lock()

    def on_reply(self, msg: String) -> None:
        try:
            data = json.loads(msg.data)
        except Exception:
            data = {"raw": msg.data}
        with self.lock:
            self.state["dynamic"] = data.get("dynamic", [])
            self.state["static_interest"] = data.get("static_interest", [])
            self.state["last_reply_raw"] = data.get("raw", msg.data)
            self.state["last_action"] = data.get("action", "")
            self.state["last_note"] = data.get("note", "")

    def on_status(self, msg: String) -> None:
        try:
            data = json.loads(msg.data)
        except Exception:
            return
        with self.lock:
            for key in ("dynamic", "static_interest", "active", "detections", "fps"):
                if key in data:
                    self.state[key] = data[key]

    def snapshot(self) -> Dict[str, Any]:
        with self.lock:
            return dict(self.state)

    def send_query(self, text: str) -> None:
        msg = String()
        msg.data = text
        self.pub_query.publish(msg)

    def override_lists(self, dynamic, static_interest) -> None:
        msg = String()
        msg.data = json.dumps({"dynamic": dynamic, "static_interest": static_interest})
        self.pub_override.publish(msg)


class Handler(BaseHTTPRequestHandler):
    bridge: WebBridge = None  # type: ignore[assignment]

    def _send(self, code, payload, ctype="application/json"):
        body = payload if isinstance(payload, (bytes, bytearray)) else payload.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # pylint: disable=invalid-name
        if self.path == "/" or self.path.startswith("/index"):
            self._send(200, HTML_PAGE, "text/html; charset=utf-8")
            return
        if self.path.startswith("/api/state"):
            payload = json.dumps(self.bridge.snapshot())
            self._send(200, payload)
            return
        self._send(404, "{\"error\":\"not found\"}")

    def do_POST(self):  # pylint: disable=invalid-name
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            data = json.loads(raw)
        except Exception:
            data = {}
        if self.path.startswith("/api/query"):
            text = str(data.get("text", "")).strip()
            if text:
                self.bridge.send_query(text)
            self._send(200, "{\"ok\":true}")
            return
        if self.path.startswith("/api/override"):
            dynamic = data.get("dynamic", [])
            static_interest = data.get("static_interest", [])
            self.bridge.override_lists(dynamic, static_interest)
            self._send(200, "{\"ok\":true}")
            return
        self._send(404, "{\"error\":\"not found\"}")


def main() -> None:
    rclpy.init()
    node = WebBridge()

    port = int(node.declare_parameter("port", 8080).get_parameter_value().integer_value or 8080)
    server = HTTPServer(("0.0.0.0", port), Handler)
    Handler.bridge = node

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    node.get_logger().info(f"Web UI running on http://localhost:{port}")
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    server.shutdown()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()

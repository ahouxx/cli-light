"""
CLI Light — Desktop traffic light indicator for CLI agent status
Green=idle · Orange blinking=task running · Red=needs input

HTTP hook server on localhost:9876 — CLI hooks POST state changes.
Process scanner detects running CLI executables for baseline count.
"""
import json
import os
import socket
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox
import ctypes
from http.server import HTTPServer, BaseHTTPRequestHandler

if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')

user32 = ctypes.windll.user32
HWND_TOPMOST, HWND_NOTOPMOST = -1, -2
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x0001, 0x0002, 0x0010
GWL_EXSTYLE, WS_EX_TOPMOST = -20, 0x00000008

HOUSING  = "#1a1a1a"
LENS_OFF = "#303030"

GREEN  = "#009933"
ORANGE = "#E06000"
RED    = "#CC1111"
BLUE   = "#2266CC"

ORANGE_DIM = "#4A2000"
GREEN_DIM  = "#003312"
RED_DIM    = "#4A0808"
BLUE_DIM   = "#0A1A33"

W, H = 142, 44
LENS_R = 14
SNAP_DIST = 25
HOOK_PORT = 9876

_SCAN_SCRIPT = (
    "$myPid=$PID;"
    "(Get-Process -Name 'claude','opencode','kimi-cli' -ErrorAction SilentlyContinue|"
    "Where-Object{$_.Id -ne $myPid}).Count"
)


class HookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/hook':
            try:
                length = int(self.headers.get('Content-Length', 0))
                body = json.loads(self.rfile.read(length))
                state = body.get('state', '')
                agent = body.get('agent', 'unknown')
                if state in ('running', 'needs_input', 'done'):
                    self.server.app._on_hook(agent, state)
                    self.send_response(200)
                else:
                    self.send_response(400)
            except Exception:
                self.send_response(400)
        else:
            self.send_response(404)
        self.end_headers()

    def log_message(self, fmt, *args):
        pass


class CLILight:
    def __init__(self):
        self._hook_port = self._resolve_port()
        if self._hook_port is None:
            return

        self.root = tk.Tk()
        self.root.title("CLI Light")
        self.root.configure(bg="#000000")
        self.root.overrideredirect(True)

        self._process_count = 0
        self._agents = {}
        self._agents_lock = threading.Lock()
        self.blink_on = True
        self.topmost = True
        self.snapped_edge = None
        self._drag_x = self._drag_y = 0
        self._running = True

        self.lights = {
            "total":       {"cx": 20, "cy": 22, "r": LENS_R, "on": BLUE, "dim": BLUE_DIM},
            "done":        {"cx": 54, "cy": 22, "r": LENS_R, "on": GREEN, "dim": GREEN_DIM},
            "running":     {"cx": 88, "cy": 22, "r": LENS_R, "on": ORANGE, "dim": ORANGE_DIM},
            "needs_input": {"cx": 122, "cy": 22, "r": LENS_R, "on": RED, "dim": RED_DIM},
        }

        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x, y, saved = self._load_state(sw, sh)
        self.topmost = saved.get("topmost", True)
        self.show_dividers = saved.get("dividers", False)
        self.root.geometry(f"{W}x{H}+{x}+{y}")

        self._build_ui()
        self._bind_events()
        self._build_menu()
        self._apply_topmost()

        self._httpd = self._start_http_server()
        threading.Thread(target=self._process_monitor, daemon=True).start()

        self._blink_tick()
        self._update()

    # ── Port / duplicate detection ───────────────────────
    @staticmethod
    def _port_is_free(port):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(('127.0.0.1', port))
            s.close()
            return True
        except OSError:
            s.close()
            return False

    @classmethod
    def _find_free_port(cls, start):
        for port in range(start, start + 100):
            if cls._port_is_free(port):
                return port
        return start

    @classmethod
    def _resolve_port(cls):
        if cls._port_is_free(HOOK_PORT):
            return HOOK_PORT
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        result = messagebox.askyesno(
            "CLI Light",
            "CLI Light 已在运行中。\n\n是否仍要启动新实例？"
        )
        root.destroy()
        if not result:
            return None
        return cls._find_free_port(HOOK_PORT + 1)

    def _start_http_server(self):
        HTTPServer.allow_reuse_address = True
        httpd = HTTPServer(('127.0.0.1', self._hook_port), HookHandler)
        httpd.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        httpd.app = self
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        return httpd

    def _on_hook(self, agent_id, new_state):
        with self._agents_lock:
            self._agents[agent_id] = new_state
        self.root.after(0, self._update)

    # ── UI ──────────────────────────────────────────────
    def _build_ui(self):
        self.canvas = tk.Canvas(self.root, width=W, height=H,
                                bg="#000000", highlightthickness=0)
        self.canvas.pack()
        self._round_rect(0, 0, W, H, 10, fill=HOUSING, outline="#333",
                         width=1, tags="static")

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        return self.canvas.create_polygon(
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2,
            x1 + r, y2, x1, y2, x1, y2 - r,
            x1, y1 + r, x1, y1,
            smooth=True, **kw)

    # ── Events ──────────────────────────────────────────
    def _bind_events(self):
        self.canvas.bind("<Button-1>", self._drag_start)
        self.canvas.bind("<ButtonRelease-1>", self._drag_stop)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self.canvas.bind("<Button-3>", self._show_menu)
        self.canvas.bind("<Double-Button-1>", lambda e: self._quit())

    def _drag_start(self, event):
        self._drag_x, self._drag_y = event.x, event.y
        self.snapped_edge = None

    def _drag_stop(self, event):
        self._drag_x = self._drag_y = 0
        self._snap_to_edge()
        self._save_state()

    def _drag_move(self, event):
        x = self.root.winfo_x() + event.x - self._drag_x
        y = self.root.winfo_y() + event.y - self._drag_y
        self.root.geometry(f"+{x}+{y}")

    def _snap_to_edge(self):
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x, y = self.root.winfo_x(), self.root.winfo_y()
        sx, sy = x, y
        self.snapped_edge = None
        if abs(x) < SNAP_DIST:
            sx = 0; self.snapped_edge = "left"
        elif abs(x + W - sw) < SNAP_DIST:
            sx = sw - W; self.snapped_edge = "right"
        if abs(y) < SNAP_DIST:
            sy = 0
            self.snapped_edge = f"{self.snapped_edge or ''}top".strip()
        elif abs(y + H - sh) < SNAP_DIST:
            sy = sh - H
            self.snapped_edge = f"{self.snapped_edge or ''}bottom".strip()
        if sx != x or sy != y:
            self.root.geometry(f"+{sx}+{sy}")

    # ── Menu ────────────────────────────────────────────
    def _build_menu(self):
        self.menu = tk.Menu(self.root, tearoff=0, bg="#2a2a2a", fg="#fff",
                            activebackground="#444", activeforeground="#fff",
                            font=("Microsoft YaHei", 9))
        self.menu.add_command(label=self._menu_label("置顶显示", self.topmost),
                              command=self._toggle_topmost)
        self.menu.add_command(label=self._menu_label("显示边框", self.show_dividers),
                              command=self._toggle_dividers)
        self.menu.add_separator()
        self.menu.add_command(label="退出", command=self._quit)

    @staticmethod
    def _menu_label(text, on):
        return f"✓ {text}" if on else f"    {text}"

    def _refresh_menu(self):
        self.menu.entryconfigure(0, label=self._menu_label("置顶显示", self.topmost))
        self.menu.entryconfigure(1, label=self._menu_label("显示边框", self.show_dividers))

    def _show_menu(self, event):
        self.menu.post(event.x_root, event.y_root)

    def _toggle_topmost(self):
        self.topmost = not self.topmost
        self._apply_topmost()
        self._refresh_menu()
        self._save_state()

    def _toggle_dividers(self):
        self.show_dividers = not self.show_dividers
        self._refresh_menu()
        self._update()
        self._save_state()

    def _apply_topmost(self):
        hwnd = self.root.winfo_id()
        if self.topmost:
            ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex | WS_EX_TOPMOST)
            user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
        else:
            ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex & ~WS_EX_TOPMOST)
            user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0,
                                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
        self.root.attributes("-topmost", self.topmost)

    # ── Process monitor ─────────────────────────────────
    def _scan_processes(self):
        """Count CLI processes via Get-Process (no temp files, no WMI)."""
        try:
            r = subprocess.run(
                ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                 '-Command', _SCAN_SCRIPT],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return int(r.stdout.strip() or 0)
        except Exception:
            return self._process_count

    def _process_monitor(self):
        while self._running:
            new_count = self._scan_processes()
            with self._agents_lock:
                diff = new_count - self._process_count
                if diff < 0:
                    excess = -diff
                    for state in ('running', 'needs_input', 'done'):
                        if excess <= 0:
                            break
                        to_remove = [aid for aid, st in self._agents.items()
                                     if st == state and aid != "cli-unknown"]
                        for aid in to_remove:
                            if excess <= 0:
                                break
                            del self._agents[aid]
                            excess -= 1
                self._process_count = new_count
            for _ in range(30):
                if not self._running:
                    return
                threading.Event().wait(0.1)

    # ── Rendering ───────────────────────────────────────
    def _draw_lens(self, key, color, number):
        info = self.lights[key]
        cx, cy, r = info["cx"], info["cy"], info["r"]
        tag = f"lens_{key}"
        self.canvas.delete(tag)
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                fill=color, outline="#111", width=1, tags=tag)
        if number > 0:
            self.canvas.create_text(cx, cy, text=str(number),
                                    fill="#fff", font=("Arial", 13, "bold"),
                                    tags=tag)

    def _update(self):
        with self._agents_lock:
            # Count hook-only agents (no standalone process, e.g. Kimi Code
            # in VS Code). They share the "cli-unknown" agent ID.
            hook_only = 1 if "cli-unknown" in self._agents else 0
            total = self._process_count + hook_only
            red_c = sum(1 for s in self._agents.values() if s == 'needs_input')
            orange_c = sum(1 for s in self._agents.values() if s == 'running')
            done_from_hooks = sum(1 for s in self._agents.values() if s == 'done')
            green_c = max(done_from_hooks, total - red_c - orange_c)

        counts = {"total": total, "done": green_c, "running": orange_c,
                  "needs_input": red_c}

        for key, info in self.lights.items():
            count = counts[key]
            if count > 0:
                if key == "running" and not self.blink_on:
                    color = info["dim"]
                else:
                    color = info["on"]
            else:
                color = LENS_OFF
            self._draw_lens(key, color, count)

        self._draw_dividers()

    def _draw_dividers(self):
        tag = "dividers"
        self.canvas.delete(tag)
        if not self.show_dividers:
            return
        s = 17
        for key in ("total", "done", "running", "needs_input"):
            info = self.lights[key]
            cx, cy = info["cx"], info["cy"]
            self._round_rect(cx - s, cy - s, cx + s, cy + s, 4,
                             fill="", outline="#FFF", width=1, tags=tag)

    def _blink_tick(self):
        self.blink_on = not self.blink_on
        self._update()
        self.root.after(500, self._blink_tick)

    # ── Position persistence ────────────────────────────
    @staticmethod
    def _get_state_path():
        d = os.path.join(os.path.expanduser("~"), ".cli-light")
        return os.path.join(d, "state.json")

    @classmethod
    def _load_state(cls, sw, sh):
        dx, dy = sw - W - 20, 20
        try:
            p = cls._get_state_path()
            if os.path.exists(p):
                with open(p, 'r') as f:
                    d = json.load(f)
                x = d.get('x', dx)
                y = d.get('y', dy)
                if x < -W + 30: x = -W + 30
                if y < -H + 30: y = -H + 30
                if x > sw - 30: x = sw - 30
                if y > sh - 30: y = sh - 30
                return x, y, d
        except Exception:
            pass
        return dx, dy, {}

    def _save_state(self):
        try:
            p = self._get_state_path()
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, 'w') as f:
                json.dump({
                    'x': self.root.winfo_x(),
                    'y': self.root.winfo_y(),
                    'topmost': self.topmost,
                    'dividers': self.show_dividers,
                }, f)
        except Exception:
            pass

    # ── Lifecycle ───────────────────────────────────────
    def _quit(self):
        self._save_state()
        self._running = False
        try:
            self._httpd.shutdown()
        except Exception:
            pass
        self.root.destroy()

    def run(self):
        if self._hook_port is not None:
            self.root.mainloop()


if __name__ == "__main__":
    CLILight().run()

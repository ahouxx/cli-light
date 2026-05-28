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
import ctypes
from http.server import HTTPServer, BaseHTTPRequestHandler

# ── pythonw compat ────────────────────────────────────────
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')

# ── Win32 ──────────────────────────────────────────────────
user32 = ctypes.windll.user32
HWND_TOPMOST, HWND_NOTOPMOST = -1, -2
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x0001, 0x0002, 0x0010
GWL_EXSTYLE, WS_EX_TOPMOST = -20, 0x00000008

# ── Colors ─────────────────────────────────────────────────
HOUSING  = "#1a1a1a"
LENS_OFF = "#2a2a2a"

GREEN  = "#009933"
ORANGE = "#E06000"
RED    = "#CC1111"
BLUE   = "#2266CC"

ORANGE_DIM = "#4A2000"
GREEN_DIM  = "#003312"
RED_DIM    = "#4A0808"
BLUE_DIM   = "#0A1A33"

# ── Base design (compact) ──────────────────────────────────
W, H = 155, 44
LENS_R   = 14
LENS_CX  = (20, 54, 88, 122)
LENS_CY  = 22
SNAP_DIST = 25
HOOK_PORT = 9876
MIN_W, MIN_H = 90, 28
MAX_W, MAX_H = 400, 140

# Label mode
_LABEL_KEYS = ("total", "done", "running", "needs_input")
_LABELS     = {"total": "总数", "done": "待命", "running": "任务", "needs_input": "授权"}
_H_LABEL    = 64
_LABEL_Y    = 11
_CY_OFF     = 22

# Resize grip
_GRIP = 14

# PowerShell scan script
_SCAN_SCRIPT = (
    "$myPid=$PID;"
    "(Get-Process -Name 'claude','opencode','kimi-cli' -ErrorAction SilentlyContinue|"
    "Where-Object{$_.Id -ne $myPid}).Count"
)


# ── HTTP hook handler ──────────────────────────────────────
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


# ── Main App ───────────────────────────────────────────────
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
        self.show_labels = False
        self.snapped_edge = None
        self._drag_x = self._drag_y = 0
        self._resizing = False
        self._rs_ox = self._rs_oy = 0
        self._rs_sw = self._rs_sh = 0
        self._running = True

        self._light_colors = {
            "total":       {"on": BLUE, "dim": BLUE_DIM},
            "done":        {"on": GREEN, "dim": GREEN_DIM},
            "running":     {"on": ORANGE, "dim": ORANGE_DIM},
            "needs_input": {"on": RED, "dim": RED_DIM},
        }

        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x, y = self._load_position(sw, sh)
        self.root.geometry(f"{W}x{H}+{x}+{y}")

        self._build_ui()
        self._bind_events()
        self._build_menu()
        self._apply_topmost()

        self._httpd = self._start_http_server()
        threading.Thread(target=self._process_monitor, daemon=True).start()

        self._blink_tick()
        self._update()

    # ── UI ──────────────────────────────────────────────
    def _build_ui(self):
        self.canvas = tk.Canvas(self.root, width=W, height=H,
                                bg="#000000", highlightthickness=0)
        self.canvas.pack()
        self._draw_housing(W, H)

    def _draw_housing(self, cw, ch):
        self.canvas.delete("static")
        s = min(cw / W, ch / self._cur_base_h())
        r = max(4, int(10 * s))
        self._round_rect(0, 0, cw, ch, r, fill=HOUSING, outline="#444",
                         width=1, tags="static")
        # Resize grip (bottom-right)
        g = max(5, int(_GRIP * s))
        m = max(2, int(3 * s))
        x0, y0 = cw - g - 3, ch - g - 3
        for i in range(3):
            x = x0 + i * m
            y = y0 + (2 - i) * m
            self.canvas.create_line(x, y0 + (2 - i) * m + m,
                                    x0 + (2 - i) * m + m, y,
                                    fill="#555", width=1, tags="static")

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        return self.canvas.create_polygon(
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2,
            x1 + r, y2, x1, y2, x1, y2 - r,
            x1, y1 + r, x1, y1,
            smooth=True, **kw)

    # ── Layout ──────────────────────────────────────────
    def _cur_base_h(self):
        return _H_LABEL if self.show_labels else H

    def _cur_scale(self):
        cw = self.canvas.winfo_width() or W
        ch = self.canvas.winfo_height() or H
        return min(cw / W, ch / self._cur_base_h())

    # ── Events ──────────────────────────────────────────
    def _bind_events(self):
        self.canvas.bind("<Button-1>", self._on_down)
        self.canvas.bind("<ButtonRelease-1>", self._on_up)
        self.canvas.bind("<B1-Motion>", self._on_move)
        self.canvas.bind("<Button-3>", self._show_menu)
        self.canvas.bind("<Double-Button-1>", lambda e: self._quit())

    def _in_grip(self, ex, ey):
        cw = self.canvas.winfo_width() or W
        ch = self.canvas.winfo_height() or H
        s = self._cur_scale()
        g = max(5, int(_GRIP * s)) + 4
        return ex >= cw - g and ey >= ch - g

    def _on_down(self, event):
        if self._in_grip(event.x, event.y):
            self._resizing = True
            self._rs_ox = event.x_root
            self._rs_oy = event.y_root
            self._rs_sw = self.root.winfo_width()
            self._rs_sh = self.root.winfo_height()
        else:
            self._resizing = False
            self._drag_x, self._drag_y = event.x, event.y
            self.snapped_edge = None

    def _on_up(self, event):
        if self._resizing:
            self._resizing = False
            self._save_state()
        else:
            self._drag_x = self._drag_y = 0
            self._snap_to_edge()
            self._save_state()

    def _on_move(self, event):
        if self._resizing:
            nw = max(MIN_W, min(MAX_W, self._rs_sw + event.x_root - self._rs_ox))
            nh = max(MIN_H, min(MAX_H, self._rs_sh + event.y_root - self._rs_oy))
            self.root.geometry(f"{nw}x{nh}")
            self.canvas.config(width=nw, height=nh)
            self._draw_housing(nw, nh)
            self._update()
        elif self._drag_x or self._drag_y:
            x = self.root.winfo_x() + event.x - self._drag_x
            y = self.root.winfo_y() + event.y - self._drag_y
            self.root.geometry(f"+{x}+{y}")

    def _snap_to_edge(self):
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        cw = self.root.winfo_width()
        ch = self.root.winfo_height()
        x, y = self.root.winfo_x(), self.root.winfo_y()
        sx, sy = x, y
        self.snapped_edge = None
        if abs(x) < SNAP_DIST:
            sx = 0; self.snapped_edge = "left"
        elif abs(x + cw - sw) < SNAP_DIST:
            sx = sw - cw; self.snapped_edge = "right"
        if abs(y) < SNAP_DIST:
            sy = 0
            self.snapped_edge = f"{self.snapped_edge or ''}top".strip()
        elif abs(y + ch - sh) < SNAP_DIST:
            sy = sh - ch
            self.snapped_edge = f"{self.snapped_edge or ''}bottom".strip()
        if sx != x or sy != y:
            self.root.geometry(f"+{sx}+{sy}")

    # ── Menu ────────────────────────────────────────────
    def _build_menu(self):
        self.menu = tk.Menu(self.root, tearoff=0, bg="#2a2a2a", fg="#fff",
                            activebackground="#444", activeforeground="#fff",
                            font=("Microsoft YaHei", 9))
        self._topmost_var = tk.BooleanVar(value=True)
        self.menu.add_checkbutton(label="置顶显示", variable=self._topmost_var,
                                  command=self._toggle_topmost)
        self._labels_var = tk.BooleanVar(value=False)
        self.menu.add_checkbutton(label="文字说明", variable=self._labels_var,
                                  command=self._toggle_labels)
        self.menu.add_separator()
        self.menu.add_command(label="退出", command=self._quit)

    def _show_menu(self, event):
        self.menu.post(event.x_root, event.y_root)

    def _toggle_topmost(self):
        self.topmost = self._topmost_var.get()
        self._apply_topmost()

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

    def _toggle_labels(self):
        self.show_labels = self._labels_var.get()
        cw = self.root.winfo_width()
        nh = self._cur_base_h()
        x, y = self.root.winfo_x(), self.root.winfo_y()
        self.root.geometry(f"{cw}x{nh}+{x}+{y}")
        self.canvas.config(width=cw, height=nh)
        self._draw_housing(cw, nh)
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
        import tkinter.messagebox as mb
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        result = mb.askyesno(
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

    # ── Hook state ─────────────────────────────────────
    def _on_hook(self, agent_id, new_state):
        with self._agents_lock:
            if new_state == 'done':
                self._agents.pop(agent_id, None)
            else:
                self._agents[agent_id] = new_state
        self.root.after(0, self._update)

    # ── Process monitor ─────────────────────────────────
    def _scan_processes(self):
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
                    for state in ('running', 'needs_input'):
                        if excess <= 0:
                            break
                        to_remove = [aid for aid, st in self._agents.items()
                                     if st == state]
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
    def _draw_lens(self, key, color, number, cx, cy, r, font_sz):
        tag = f"lens_{key}"
        self.canvas.delete(tag)
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                fill=color, outline="#111", width=1, tags=tag)
        if number > 0:
            self.canvas.create_text(cx, cy, text=str(number),
                                    fill="#fff", font=("Arial", font_sz, "bold"),
                                    tags=tag)

    def _draw_labels(self, cx_list, ly, font_sz):
        self.canvas.delete("labels")
        if not self.show_labels:
            return
        for i, key in enumerate(_LABEL_KEYS):
            self.canvas.create_text(cx_list[i], ly, text=_LABELS[key],
                                    fill="#AAA",
                                    font=("Microsoft YaHei", font_sz),
                                    tags="labels")

    def _update(self):
        with self._agents_lock:
            total = self._process_count
            red_c = sum(1 for s in self._agents.values() if s == 'needs_input')
            orange_c = sum(1 for s in self._agents.values() if s == 'running')
            if red_c + orange_c > total:
                excess = red_c + orange_c - total
                for _ in range(excess):
                    for st in ('needs_input', 'running'):
                        for aid, s in list(self._agents.items()):
                            if s == st:
                                del self._agents[aid]
                                break
                        else:
                            continue
                        break
                red_c = sum(1 for s in self._agents.values() if s == 'needs_input')
                orange_c = sum(1 for s in self._agents.values() if s == 'running')
        green_c = max(0, total - red_c - orange_c)
        counts = {"total": total, "done": green_c, "running": orange_c,
                  "needs_input": red_c}

        # Compute scaled layout
        s = self._cur_scale()
        cw = self.canvas.winfo_width() or W
        ch = self.canvas.winfo_height() or H
        scale_x = cw / W if cw > 0 else s

        r = max(4, int(LENS_R * s))
        base_cy = LENS_CY + (_CY_OFF if self.show_labels else 0)
        cy = int(base_cy * s) if self.show_labels else int(ch * (LENS_CY / H) if ch > 0 else LENS_CY)
        if not self.show_labels:
            cy = ch // 2  # center in compact mode
        cx_list = [int(c * scale_x) for c in LENS_CX]
        num_font = max(8, int(13 * s))
        label_font = max(7, int(9 * s))
        label_y = max(4, int(_LABEL_Y * s))

        for i, key in enumerate(_LABEL_KEYS):
            count = counts[key]
            if count > 0:
                if key == "running" and not self.blink_on:
                    color = self._light_colors[key]["dim"]
                else:
                    color = self._light_colors[key]["on"]
            else:
                color = LENS_OFF
            self._draw_lens(key, color, count, cx_list[i], cy, r, num_font)

        self._draw_labels(cx_list, label_y, label_font)

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
    def _load_position(cls, sw, sh):
        dx, dy = sw - W - 20, 20
        try:
            p = cls._get_state_path()
            if os.path.exists(p):
                with open(p, 'r') as f:
                    d = json.load(f)
                x = d.get('x', dx)
                y = d.get('y', dy)
                if x < -MAX_W or x > sw + MAX_W or y < -MAX_H or y > sh + MAX_H:
                    return dx, dy
                if x < -W + 30: x = -W + 30
                if y < -H + 30: y = -H + 30
                if x > sw - 30: x = sw - 30
                if y > sh - 30: y = sh - 30
                return x, y
        except Exception:
            pass
        return dx, dy

    def _save_state(self):
        try:
            p = self._get_state_path()
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, 'w') as f:
                json.dump({'x': self.root.winfo_x(), 'y': self.root.winfo_y()}, f)
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

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

# ── Lens color schemes ──────────────────────────────────────
# Each scheme has 4 lights: total / done / running / needs_input
# with "on" and "dim" (blink-off) colors.
COLOR_SCHEMES = {
    "默认": {
        "total":       {"on": "#2266CC", "dim": "#0A1A33"},
        "done":        {"on": "#009933", "dim": "#003312"},
        "running":     {"on": "#E06000", "dim": "#4A2000"},
        "needs_input": {"on": "#CC1111", "dim": "#4A0808"},
    },
    "海洋": {
        "total":       {"on": "#0077B6", "dim": "#001D33"},
        "done":        {"on": "#00B4D8", "dim": "#002233"},
        "running":     {"on": "#48CAE4", "dim": "#0D2E38"},
        "needs_input": {"on": "#E63946", "dim": "#3D0A0F"},
    },
    "森林": {
        "total":       {"on": "#2D6A4F", "dim": "#0A1A14"},
        "done":        {"on": "#52B788", "dim": "#123321"},
        "running":     {"on": "#D4A373", "dim": "#3D2A14"},
        "needs_input": {"on": "#E76F51", "dim": "#3D1A12"},
    },
    "霓虹": {
        "total":       {"on": "#7C3AED", "dim": "#1E0A3D"},
        "done":        {"on": "#06D6A0", "dim": "#003D28"},
        "running":     {"on": "#FFD166", "dim": "#4A3800"},
        "needs_input": {"on": "#FF6B6B", "dim": "#4A0808"},
    },
    "琥珀": {
        "total":       {"on": "#8B5CF6", "dim": "#1E0A3D"},
        "done":        {"on": "#10B981", "dim": "#003D1E"},
        "running":     {"on": "#F59E0B", "dim": "#4A2E00"},
        "needs_input": {"on": "#EF4444", "dim": "#4A0A0A"},
    },
    "极简": {
        "total":       {"on": "#6B7280", "dim": "#1A1D22"},
        "done":        {"on": "#9CA3AF", "dim": "#222528"},
        "running":     {"on": "#D1D5DB", "dim": "#2D2F33"},
        "needs_input": {"on": "#EF4444", "dim": "#4A0A0A"},
    },
}

_TRANSCOLOR = "#010101"  # color key for transparent background

THEMES = {
    "dark": {
        "housing": "#1A1A1A", "lens_off": "#303030",
        "canvas_bg": "#000000", "lens_outline": "#111",
        "divider": "#FFF", "housing_outline": "#333",
        "menu_bg": "#2A2A2A", "menu_fg": "#FFF",
        "menu_abg": "#444", "menu_afg": "#FFF",
        "num_fg": "#FFF",
    },
    "light": {
        "housing": "#E8E8E8", "lens_off": "#D0D0D0",
        "canvas_bg": "#F0F0F0", "lens_outline": "#CCC",
        "divider": "#999", "housing_outline": "#BBB",
        "menu_bg": "#F0F0F0", "menu_fg": "#222",
        "menu_abg": "#DDD", "menu_afg": "#000",
        "num_fg": "#FFF",
    },
    "transparent": {
        "housing": _TRANSCOLOR, "lens_off": "#303030",
        "canvas_bg": _TRANSCOLOR, "lens_outline": "#111",
        "divider": "#FFF", "housing_outline": "#666",
        "menu_bg": "#2A2A2A", "menu_fg": "#FFF",
        "menu_abg": "#444", "menu_afg": "#FFF",
        "num_fg": "#FFF",
    },
}

def _detect_system_theme():
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        v, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return "light" if v else "dark"
    except Exception:
        return "dark"

W, H = 142, 40
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
            "total":       {"cx": 20, "cy": 20, "r": LENS_R},
            "done":        {"cx": 54, "cy": 20, "r": LENS_R},
            "running":     {"cx": 88, "cy": 20, "r": LENS_R},
            "needs_input": {"cx": 122, "cy": 20, "r": LENS_R},
        }

        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x, y, saved = self._load_state(sw, sh)
        self.topmost = saved.get("topmost", True)
        self.show_dividers = saved.get("dividers", False)
        self.theme = saved.get("theme", "dark")
        self.color_scheme = saved.get("color_scheme", "默认")
        self.scale = saved.get("scale", 1.0)
        w, h = self._scaled_wh()
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self._apply_transparent_mode()

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
        w, h = self._scaled_wh()
        self.canvas = tk.Canvas(self.root, width=w, height=h,
                                bg="#000000", highlightthickness=0)
        self.canvas.pack()
        self._draw_housing()

    def _draw_housing(self):
        tc = self._theme_colors()
        self.canvas.delete("static")
        self.canvas.config(bg=tc["canvas_bg"])
        w, h = self._scaled_wh()
        r = self._scaled(10)[0]
        fill = tc["housing"]
        outline = "" if self.theme == "transparent" else tc["housing_outline"]
        self._round_rect(0, 0, w, h, r, fill=fill,
                         outline=outline, width=1, tags="static")

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
        elif abs(x + cur_w - sw) < SNAP_DIST:
            sx = sw - cur_w; self.snapped_edge = "right"
        if abs(y) < SNAP_DIST:
            sy = 0
            self.snapped_edge = f"{self.snapped_edge or ''}top".strip()
        elif abs(y + H - sh) < SNAP_DIST:
            sy = sh - H
            self.snapped_edge = f"{self.snapped_edge or ''}bottom".strip()
        if sx != x or sy != y:
            self.root.geometry(f"+{sx}+{sy}")

    # ── Menu ────────────────────────────────────────────
    def _scaled(self, *vals):
        return tuple(max(1, int(v * self.scale)) for v in vals)

    def _scaled_wh(self):
        return self._scaled(W, H)

    def _lens_color(self, key, on):
        cs = COLOR_SCHEMES[self.color_scheme][key]
        return cs["on"] if on else cs["dim"]

    def _resolve_theme(self):
        if self.theme == "system":
            return _detect_system_theme()
        return self.theme

    def _theme_colors(self):
        return THEMES[self._resolve_theme()]

    def _build_menu(self):
        tc = self._theme_colors()
        self.menu = tk.Menu(self.root, tearoff=0, bg=tc["menu_bg"], fg=tc["menu_fg"],
                            activebackground=tc["menu_abg"], activeforeground=tc["menu_afg"],
                            font=("Microsoft YaHei", 9))
        self.menu.add_command(label=self._menu_label("置顶显示", self.topmost),
                              command=self._toggle_topmost)
        self.menu.add_command(label=self._menu_label("显示边框", self.show_dividers),
                              command=self._toggle_dividers)
        self.menu.add_separator()
        # Theme submenu
        self._theme_menu = tk.Menu(self.menu, tearoff=0, bg=tc["menu_bg"], fg=tc["menu_fg"],
                                   activebackground=tc["menu_abg"], activeforeground=tc["menu_afg"],
                                   font=("Microsoft YaHei", 9))
        for key, label in [("dark", "深色"), ("transparent", "透明")]:
            self._theme_menu.add_command(
                label=self._menu_label(label, self.theme == key),
                command=lambda k=key: self._set_theme(k))
        self.menu.add_cascade(label="主题", menu=self._theme_menu)
        # Scale submenu
        self._scale_menu = tk.Menu(self.menu, tearoff=0, bg=tc["menu_bg"], fg=tc["menu_fg"],
                                   activebackground=tc["menu_abg"], activeforeground=tc["menu_afg"],
                                   font=("Microsoft YaHei", 9))
        for factor, label in [(0.75, "75%"), (1.00, "100%"), (1.25, "125%"), (1.50, "150%")]:
            self._scale_menu.add_command(
                label=self._menu_label(label, abs(self.scale - factor) < 0.01),
                command=lambda f=factor: self._set_scale(f))
        self.menu.add_cascade(label="缩放", menu=self._scale_menu)
        # Color scheme submenu
        self._cs_menu = tk.Menu(self.menu, tearoff=0, bg=tc["menu_bg"], fg=tc["menu_fg"],
                                activebackground=tc["menu_abg"], activeforeground=tc["menu_afg"],
                                font=("Microsoft YaHei", 9))
        for name in COLOR_SCHEMES:
            self._cs_menu.add_command(
                label=self._menu_label(name, self.color_scheme == name),
                command=lambda n=name: self._set_color_scheme(n))
        self.menu.add_cascade(label="配色", menu=self._cs_menu)
        self.menu.add_separator()
        self.menu.add_command(label="退出", command=self._quit)

    @staticmethod
    def _menu_label(text, on):
        return f"✓ {text}" if on else f"    {text}"

    def _refresh_menu(self):
        self.menu.entryconfigure(0, label=self._menu_label("置顶显示", self.topmost))
        self.menu.entryconfigure(1, label=self._menu_label("显示边框", self.show_dividers))
        tc = self._theme_colors()
        self._theme_menu.config(bg=tc["menu_bg"], fg=tc["menu_fg"],
                                activebackground=tc["menu_abg"], activeforeground=tc["menu_afg"])
        for i, key in enumerate(["dark", "transparent"]):
            self._theme_menu.entryconfigure(i, label=self._menu_label(
                {"dark": "深色", "transparent": "透明"}[key], self.theme == key))
        for i, (factor, label) in enumerate([(0.75, "75%"), (1.00, "100%"), (1.25, "125%"), (1.50, "150%")]):
            self._scale_menu.entryconfigure(i, label=self._menu_label(label, abs(self.scale - factor) < 0.01))
        for i, name in enumerate(COLOR_SCHEMES):
            self._cs_menu.entryconfigure(i, label=self._menu_label(name, self.color_scheme == name))

    def _set_theme(self, theme):
        self.theme = theme
        self._apply_transparent_mode()
        self._refresh_menu()
        self._rebuild_ui()
        self._save_state()

    def _apply_transparent_mode(self):
        if self.theme == "transparent":
            self.root.attributes("-transparentcolor", _TRANSCOLOR)
            self.root.configure(bg=_TRANSCOLOR)
        else:
            self.root.attributes("-transparentcolor", "")
            self.root.configure(bg="#000000")

    def _rebuild_ui(self):
        tc = self._theme_colors()
        self.canvas.config(bg=tc["canvas_bg"])
        self._draw_housing()
        self._update()

    def _show_menu(self, event):
        self.menu.post(event.x_root, event.y_root)

    def _toggle_topmost(self):
        self.topmost = not self.topmost
        self._apply_topmost()
        self._refresh_menu()
        self._save_state()

    def _set_scale(self, factor):
        self.scale = factor
        w, h = self._scaled_wh()
        x, y = self.root.winfo_x(), self.root.winfo_y()
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.canvas.config(width=w, height=h)
        self._draw_housing()
        self._refresh_menu()
        self._update()
        self._save_state()

    def _set_color_scheme(self, name):
        self.color_scheme = name
        self._refresh_menu()
        self._update()
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
        cx, cy = self._scaled(info["cx"], info["cy"])
        r = self._scaled(info["r"])[0]
        tag = f"lens_{key}"
        self.canvas.delete(tag)
        tc = self._theme_colors()
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                fill=color, outline=tc["lens_outline"], width=1, tags=tag)
        if number > 0:
            font_sz = max(8, self._scaled(13)[0])
            self.canvas.create_text(cx, cy, text=str(number),
                                    fill=tc["num_fg"], font=("Arial", font_sz, "bold"),
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
                is_dim = (key == "running" and not self.blink_on)
                color = self._lens_color(key, not is_dim)
            else:
                color = self._theme_colors()["lens_off"]
            self._draw_lens(key, color, count)

        self._draw_dividers()

    def _draw_dividers(self):
        tag = "dividers"
        self.canvas.delete(tag)
        if not self.show_dividers:
            return
        s = self._scaled(17)[0]
        cr = self._scaled(4)[0]
        for key in ("total", "done", "running", "needs_input"):
            info = self.lights[key]
            cx, cy = self._scaled(info["cx"], info["cy"])
            self._round_rect(cx - s, cy - s, cx + s, cy + s, cr,
                             fill="", outline=self._theme_colors()["divider"],
                             width=1, tags=tag)

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
        s = 1.0
        try:
            p = cls._get_state_path()
            if os.path.exists(p):
                with open(p, 'r') as f:
                    d = json.load(f)
                s = d.get("scale", 1.0)
        except Exception:
            pass
        w = max(1, int(W * s))
        h = max(1, int(H * s))
        dx, dy = sw - w - 20, 20
        try:
            p = cls._get_state_path()
            if os.path.exists(p):
                with open(p, 'r') as f:
                    d = json.load(f)
                x = d.get('x', dx)
                y = d.get('y', dy)
                if x < -w + 30: x = -w + 30
                if y < -h + 30: y = -h + 30
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
                    'theme': self.theme,
                    'scale': self.scale,
                    'color_scheme': self.color_scheme,
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

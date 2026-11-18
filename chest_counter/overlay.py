"""Desktop-Overlay: rahmenloses, transparentes, immer oben liegendes und klick-durchlässiges Fenster.

Aufbau (bei scale = 1.0):

    ╭──────────────────────────────╮
    │ ▌ [Truhe]   TRUHEN  ●        │
    │ ▌           1.234   +1       │
    │ ▌ ⏸ Auto-Erkennung pausiert  │   ← nur bei Hinweisen/Meldungen
    ╰──────────────────────────────╯

Größe: Strg+Bild↑/↓, oder im Verschiebe-Modus (F10) per Mausrad bzw. am Griff unten rechts ziehen.
"""
from __future__ import annotations

import sys
import tkinter as tk
import tkinter.font as tkfont
from typing import Callable

from .config import clamp_scale, format_number

TRANSPARENT = "#010101"  # Farbe, die Windows als "durchsichtig" behandelt

# Win32-Konstanten für Klick-Durchlass
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080  # nicht in der Taskleiste / Alt-Tab
WS_EX_NOACTIVATE = 0x08000000  # stiehlt Fortnite nicht den Fokus

STATUS_COLORS = {"ok": "#4ADE80", "paused": "#FBBF24", "warn": "#F87171"}


def rounded_rect(canvas: tk.Canvas, x0, y0, x1, y1, r, **kwargs):
    r = max(1, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
    # Doppelte Punkte an den Geraden halten die Kanten gerade, nur die Ecken werden gerundet
    points = [
        x0 + r, y0, x0 + r, y0, x1 - r, y0, x1 - r, y0, x1, y0,
        x1, y0 + r, x1, y0 + r, x1, y1 - r, x1, y1 - r, x1, y1,
        x1 - r, y1, x1 - r, y1, x0 + r, y1, x0 + r, y1, x0, y1,
        x0, y1 - r, x0, y1 - r, x0, y0 + r, x0, y0 + r, x0, y0,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


class Overlay:
    def __init__(self, config: dict, on_settings_changed: Callable[[dict], None]):
        self.cfg = config["overlay"]
        self._on_settings_changed = on_settings_changed
        self.scale = clamp_scale(float(self.cfg.get("scale", 1.0)))
        self._move_mode = False
        self._drag_offset = (0, 0)
        self._resize_start: tuple[int, float, int] | None = None
        self._flash_job: str | None = None
        self._toast_job: str | None = None
        self._save_job: str | None = None

        self._total = 0
        self._flashing = False
        self._status = ("ok", "")
        self._toast_text = ""

        self.root = tk.Tk()
        self.root.title("Fortnite Chest Counter")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=TRANSPARENT)
        if sys.platform == "win32":
            self.root.attributes("-transparentcolor", TRANSPARENT)
        try:
            self.root.attributes("-alpha", min(1.0, max(0.3, float(self.cfg.get("opacity", 0.92)))))
        except tk.TclError:
            pass
        self.root.geometry(f"+{int(self.cfg['x'])}+{int(self.cfg['y'])}")

        family = self.cfg["font_family"]
        self._f_number = tkfont.Font(root=self.root, family=family, weight="bold")
        self._f_label = tkfont.Font(root=self.root, family=family, weight="bold")
        self._f_small = tkfont.Font(root=self.root, family=family, weight="bold")
        self._apply_font_sizes()

        self.canvas = tk.Canvas(self.root, bg=TRANSPARENT, highlightthickness=0, bd=0)
        self.canvas.pack()

        for widget in (self.root, self.canvas):
            widget.bind("<ButtonPress-1>", self._on_press)
            widget.bind("<B1-Motion>", self._on_motion)
            widget.bind("<ButtonRelease-1>", self._on_release)
            widget.bind("<MouseWheel>", self._on_wheel)          # Windows
            widget.bind("<Button-4>", lambda e: self.change_scale(+0.1))  # Linux
            widget.bind("<Button-5>", lambda e: self.change_scale(-0.1))

        self._size = (100, 40)
        self.root.update_idletasks()
        self._set_click_through(True)
        self._keep_on_top()

    # ---------- Größe ----------
    def _px(self, value: float) -> int:
        return max(1, round(value * self.scale))

    def _apply_font_sizes(self) -> None:
        base = float(self.cfg["font_size"]) * self.scale
        # negative Größen = Pixel → Layout skaliert unabhängig von der Windows-DPI gleichmäßig
        self._f_number.configure(size=-max(8, round(base * 1.25)))
        self._f_label.configure(size=-max(6, round(base * 0.46)))
        self._f_small.configure(size=-max(6, round(base * 0.44)))

    def change_scale(self, delta: float) -> None:
        self.set_scale(self.scale + delta)

    def set_scale(self, value: float, announce: bool = True) -> None:
        value = clamp_scale(value)
        if value == self.scale:
            return
        self.scale = value
        self._apply_font_sizes()
        self._redraw()
        if announce:
            self.toast(f"Größe: {round(self.scale * 100)} %", 1500)
        self._schedule_save()

    # ---------- Zeichnen ----------
    def _draw_chest(self, x: float, y: float, w: float, h: float, open_: bool) -> None:
        c = self.canvas
        wood, wood_dark, outline = "#B8742A", "#7A4A1A", "#3B2410"
        gold = self.cfg["color"]
        lw = max(1, round(1.6 * self.scale))
        seam = y + h * 0.45
        lift = h * 0.30 if open_ else 0

        if open_:  # Lichtstrahlen + Leuchten aus der offenen Truhe
            cx = x + w / 2
            for dx in (-0.42, -0.2, 0.0, 0.2, 0.42):
                c.create_line(cx + w * dx * 0.5, seam, cx + w * dx * 1.15, seam - h * 0.62,
                              fill="#FFE27A", width=max(1, round(2.2 * self.scale)), capstyle="round")
            c.create_oval(x + w * 0.08, seam - h * 0.30, x + w * 0.92, seam + h * 0.10, fill="#FFE27A", outline="")
            c.create_oval(x + w * 0.24, seam - h * 0.20, x + w * 0.76, seam + h * 0.04, fill="#FFF8D6", outline="")

        # Korpus
        mid = seam + (y + h - seam) * 0.5
        c.create_rectangle(x, seam, x + w, y + h, fill=wood, outline=outline, width=lw)
        c.create_line(x + lw, mid, x + w - lw, mid, fill=wood_dark, width=lw)

        # Deckel (gewölbt), beim Öffnen angehoben
        top, bottom = y + h * 0.04 - lift, seam - lift
        rounded_rect(c, x, top, x + w, bottom, h * 0.2, fill=wood, outline=outline, width=lw)
        c.create_rectangle(x, (top + bottom) / 2, x + w, bottom, fill=wood, outline="")
        c.create_line(x, (top + bottom) / 2, x, bottom, x + w, bottom, x + w, (top + bottom) / 2,
                      fill=outline, width=lw)

        # Goldbeschläge
        band = w * 0.12
        for bx in (x + w * 0.14, x + w * 0.86 - band):
            c.create_rectangle(bx, seam, bx + band, y + h, fill=gold, outline=outline, width=lw)
            c.create_rectangle(bx, top + h * 0.06, bx + band, bottom, fill=gold, outline=outline, width=lw)

        # Schloss (bleibt am Korpus)
        lx, lwid = x + w * 0.5, w * 0.2
        c.create_rectangle(lx - lwid / 2, seam - (0 if open_ else h * 0.06), lx + lwid / 2, seam + h * 0.2,
                           fill=gold, outline=outline, width=lw)
        c.create_rectangle(lx - w * 0.025, seam + h * 0.04, lx + w * 0.025, seam + h * 0.14,
                           fill=outline, outline="")

    def _pill(self, x: float, y: float, text: str, font, bg: str, fg: str) -> None:
        tw, th = font.measure(text), font.metrics("linespace")
        px, py = self._px(7), self._px(1)
        rounded_rect(self.canvas, x, y, x + tw + 2 * px, y + th + 2 * py, (th + 2 * py) / 2, fill=bg, outline="")
        self.canvas.create_text(x + px, y + py, text=text, font=font, fill=fg, anchor="nw")

    def _shadow_text(self, x, y, text, font, color, anchor="nw") -> None:
        off = max(1, round(2 * self.scale))
        for dx, dy in ((off, off), (-1, -1), (1, -1), (-1, 1)):
            self.canvas.create_text(x + dx, y + dy, text=text, font=font, fill=self.cfg["shadow_color"], anchor=anchor)
        self.canvas.create_text(x, y, text=text, font=font, fill=color, anchor=anchor)

    def _text(self, x, y, text, font, color, anchor="nw") -> None:
        if self.cfg.get("background", True):
            self.canvas.create_text(x, y, text=text, font=font, fill=color, anchor=anchor)
        else:
            self._shadow_text(x, y, text, font, color, anchor)

    def _redraw(self) -> None:
        c = self.canvas
        c.delete("all")
        cfg = self.cfg
        with_panel = bool(cfg.get("background", True))

        pad = self._px(14)
        gap = self._px(12)
        accent_w = self._px(4) if with_panel else 0
        icon_w, icon_h = self._px(46), self._px(40)

        label = str(cfg["label"]).upper()
        number = format_number(self._total)
        plus = "+1"

        label_h = self._f_label.metrics("linespace")
        number_h = self._f_number.metrics("linespace")
        small_h = self._f_small.metrics("linespace")
        dot = max(4, round(label_h * 0.42))

        text_w = max(
            self._f_label.measure(label) + gap // 2 + dot,
            self._f_number.measure(number) + gap // 2 + self._f_label.measure(plus) + self._px(16),
        )
        head_h = max(icon_h, label_h + round(number_h * 0.88))

        lines: list[tuple[str, str]] = []
        kind, status = self._status
        if status and kind != "ok":
            lines.append((kind, status))
        if self._toast_text:
            lines.append(("toast", self._toast_text))
        lines_h = sum(small_h + self._px(4) for _ in lines)
        lines_w = max([self._f_small.measure(t) + dot + gap // 2 for _, t in lines] or [0])

        content_x = pad + accent_w + (gap if with_panel else 0)
        width = content_x + max(icon_w + gap + text_w, lines_w) + pad
        height = pad + head_h + (self._px(8) + lines_h if lines else 0) + pad

        # Panel
        if with_panel:
            radius = self._px(18)
            rounded_rect(c, 0, 0, width, height, radius, fill=cfg["panel_color"],
                         outline=cfg["border_color"], width=max(1, self._px(1.5)))
            rounded_rect(c, pad * 0.6, pad, pad * 0.6 + accent_w, height - pad, accent_w / 2,
                         fill=cfg["color"], outline="")

        # Kopfzeile: Truhe + Label + Zahl
        x = content_x
        icon_y = pad + (head_h - icon_h) / 2
        self._draw_chest(x, icon_y, icon_w, icon_h, open_=self._flashing)

        tx = x + icon_w + gap
        ty = pad + (head_h - (label_h + round(number_h * 0.88))) / 2
        self._text(tx, ty, label, self._f_label, cfg["color"])
        dot_color = STATUS_COLORS.get(kind, STATUS_COLORS["ok"])
        dx = tx + self._f_label.measure(label) + gap // 2
        dy = ty + (label_h - dot) / 2
        c.create_oval(dx, dy, dx + dot, dy + dot, fill=dot_color, outline="")

        ny = ty + label_h - round(number_h * 0.12)
        number_color = cfg["flash_color"] if self._flashing else cfg["number_color"]
        self._text(tx, ny, number, self._f_number, number_color)
        if self._flashing:
            px = tx + self._f_number.measure(number) + gap // 2
            py = ny + (number_h - self._f_label.metrics("linespace")) / 2
            self._pill(px, py, plus, self._f_label, cfg["flash_color"], "#062B12")

        # Zusatzzeilen (Status-Hinweise, Meldungen)
        ly = pad + head_h + self._px(8)
        lx = content_x
        for line_kind, text in lines:
            color = cfg["muted_color"] if line_kind == "toast" else STATUS_COLORS.get(line_kind, cfg["muted_color"])
            if line_kind != "toast":
                oy = ly + (small_h - dot) / 2
                c.create_oval(lx, oy, lx + dot, oy + dot, fill=color, outline="")
                self._text(lx + dot + gap // 2, ly, text, self._f_small, color)
            else:
                self._text(lx, ly, text, self._f_small, color)
            ly += small_h + self._px(4)

        # Verschiebe-/Größen-Modus
        if self._move_mode:
            c.create_rectangle(1, 1, width - 2, height - 2, outline="#FFFFFF", dash=(5, 3), width=2)
            g = self._px(16)
            c.create_polygon(width - 3, height - g, width - 3, height - 3, width - g, height - 3,
                             fill="#FFFFFF", outline="")

        c.configure(width=width, height=height)
        self._size = (width, height)

    # ---------- öffentliche API ----------
    def set_total(self, total: int, flash: bool = False) -> None:
        self._total = total
        if flash:
            self._flashing = True
            if self._flash_job:
                self.root.after_cancel(self._flash_job)
            self._flash_job = self.root.after(900, self._end_flash)
        self._redraw()

    def _end_flash(self) -> None:
        self._flash_job = None
        self._flashing = False
        self._redraw()

    def set_status(self, kind: str, text: str) -> None:
        """kind: 'ok' (nur grüner Punkt), 'paused' oder 'warn' (mit Textzeile)."""
        self._status = (kind, text)
        self._redraw()

    def toast(self, text: str, duration_ms: int = 3000) -> None:
        self._toast_text = text
        if self._toast_job:
            self.root.after_cancel(self._toast_job)
        self._toast_job = self.root.after(duration_ms, self._clear_toast)
        self._redraw()

    def _clear_toast(self) -> None:
        self._toast_job = None
        self._toast_text = ""
        self._redraw()

    # ---------- Fensterverhalten ----------
    def _hwnd(self) -> int:
        import ctypes

        return ctypes.windll.user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()

    def _set_click_through(self, enabled: bool) -> None:
        if sys.platform != "win32":
            return
        import ctypes

        user32 = ctypes.windll.user32
        hwnd = self._hwnd()
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style |= WS_EX_LAYERED | WS_EX_TOOLWINDOW
        if enabled:
            style |= WS_EX_TRANSPARENT | WS_EX_NOACTIVATE
        else:
            style &= ~(WS_EX_TRANSPARENT | WS_EX_NOACTIVATE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

    def _keep_on_top(self) -> None:
        # Fortnite holt sich beim Fokuswechsel manchmal den Vordergrund zurück
        self.root.attributes("-topmost", True)
        self.root.lift()
        self.root.after(2000, self._keep_on_top)

    def _schedule_save(self) -> None:
        if self._save_job:
            self.root.after_cancel(self._save_job)
        self._save_job = self.root.after(600, self._save_settings)

    def _save_settings(self) -> None:
        self._save_job = None
        self._on_settings_changed({"x": self.root.winfo_x(), "y": self.root.winfo_y(), "scale": self.scale})

    def toggle_move_mode(self) -> bool:
        self._move_mode = not self._move_mode
        self._set_click_through(not self._move_mode)
        if not self._move_mode:
            self._save_settings()
        self._redraw()
        return self._move_mode

    def _on_grip(self, event) -> bool:
        width, height = self._size
        g = self._px(22)
        return event.x >= width - g and event.y >= height - g

    def _on_press(self, event) -> None:
        if not self._move_mode:
            return
        if self._on_grip(event):
            self._resize_start = (event.x_root, self.scale, self._size[0])
        else:
            self._drag_offset = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def _on_motion(self, event) -> None:
        if not self._move_mode:
            return
        if self._resize_start:
            start_x, start_scale, start_w = self._resize_start
            self.set_scale(start_scale * (start_w + event.x_root - start_x) / start_w, announce=False)
        else:
            dx, dy = self._drag_offset
            self.root.geometry(f"+{event.x_root - dx}+{event.y_root - dy}")

    def _on_release(self, _event) -> None:
        if self._resize_start:
            self._resize_start = None
            self.toast(f"Größe: {round(self.scale * 100)} %", 1500)

    def _on_wheel(self, event) -> None:
        if self._move_mode:
            self.change_scale(0.1 if event.delta > 0 else -0.1)

    # ---------- Startwert-Dialog ----------
    def ask_value(self, title: str, prompt: str, initial: int, on_result: Callable[[int | None], None]) -> None:
        """Eingabefenster im Overlay-Stil (immer oben), um den Zählerstand manuell zu setzen."""
        cfg = self.cfg
        bg, fg, accent, muted = cfg["panel_color"], cfg["number_color"], cfg["color"], cfg["muted_color"]
        family = cfg["font_family"]

        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.attributes("-topmost", True)
        dialog.resizable(False, False)
        dialog.configure(bg=bg, padx=22, pady=18, highlightthickness=2, highlightbackground=accent)

        tk.Label(dialog, text="🧰  " + title, bg=bg, fg=accent, font=(family, 13, "bold")).pack(anchor="w")
        tk.Label(dialog, text=prompt, justify="left", bg=bg, fg=muted, font=(family, 10)).pack(anchor="w", pady=(6, 0))
        var = tk.StringVar(value=str(initial))
        entry = tk.Entry(dialog, textvariable=var, width=12, font=(family, 22, "bold"), justify="center",
                         bg="#0C0E15", fg=fg, insertbackground=fg, relief="flat",
                         highlightthickness=2, highlightbackground=cfg["border_color"], highlightcolor=accent,
                         selectbackground=accent, selectforeground="#1A1300")
        entry.pack(fill="x", pady=12, ipady=4)
        error = tk.Label(dialog, text="", bg=bg, fg=STATUS_COLORS["warn"], font=(family, 9))
        error.pack(anchor="w")

        done = {"value": False}

        def finish(value: int | None) -> None:
            if done["value"]:
                return
            done["value"] = True
            dialog.destroy()
            on_result(value)

        def submit(_event=None) -> None:
            text = var.get().strip().replace(".", "").replace(" ", "")
            if not text.isdigit():
                error.configure(text="Bitte eine ganze Zahl ≥ 0 eingeben.")
                return
            finish(int(text))

        buttons = tk.Frame(dialog, bg=bg)
        buttons.pack(fill="x", pady=(4, 0))
        style = dict(font=(family, 10, "bold"), relief="flat", bd=0, padx=14, pady=6, cursor="hand2")
        tk.Button(buttons, text="Übernehmen", command=submit, bg=accent, fg="#1A1300",
                  activebackground="#FFE58A", **style).pack(side="right")
        tk.Button(buttons, text="Abbrechen", command=lambda: finish(None), bg="#262B3B", fg=fg,
                  activebackground="#323850", activeforeground=fg, **style).pack(side="right", padx=(0, 8))

        dialog.bind("<Return>", submit)
        dialog.bind("<Escape>", lambda _e: finish(None))
        dialog.protocol("WM_DELETE_WINDOW", lambda: finish(None))

        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - dialog.winfo_reqwidth()) // 2
        y = (dialog.winfo_screenheight() - dialog.winfo_reqheight()) // 3
        dialog.geometry(f"+{x}+{y}")
        dialog.lift()
        dialog.focus_force()
        entry.focus_set()
        entry.select_range(0, "end")

    # ---------- Ereignisschleife ----------
    def poll(self, callback: Callable[[], None], interval_ms: int = 50) -> None:
        def tick() -> None:
            callback()
            self.root.after(interval_ms, tick)

        self.root.after(interval_ms, tick)

    def run(self) -> None:
        self.root.mainloop()

    def close(self) -> None:
        self.root.destroy()

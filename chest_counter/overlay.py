"""Desktop-Overlay: rahmenloses, transparentes, immer oben liegendes und klick-durchlässiges Fenster."""
from __future__ import annotations

import sys
import tkinter as tk
from typing import Callable

TRANSPARENT = "#010101"  # Farbe, die Windows als "durchsichtig" behandelt

# Win32-Konstanten für Klick-Durchlass
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080  # nicht in der Taskleiste / Alt-Tab
WS_EX_NOACTIVATE = 0x08000000  # stiehlt Fortnite nicht den Fokus


def _format_number(value: int) -> str:
    return f"{value:,}".replace(",", ".")


class Overlay:
    def __init__(self, config: dict, on_position_changed: Callable[[int, int], None]):
        self.cfg = config["overlay"]
        self._on_position_changed = on_position_changed
        self._move_mode = False
        self._drag_offset = (0, 0)
        self._flash_job: str | None = None
        self._toast_job: str | None = None

        self.root = tk.Tk()
        self.root.title("Fortnite Chest Counter")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=TRANSPARENT)
        if sys.platform == "win32":
            self.root.attributes("-transparentcolor", TRANSPARENT)
        self.root.geometry(f"+{int(self.cfg['x'])}+{int(self.cfg['y'])}")

        size = int(self.cfg["font_size"])
        family = self.cfg["font_family"]
        self._main_font = (family, size, "bold")
        self._small_font = (family, max(9, size // 3), "bold")

        self.canvas = tk.Canvas(self.root, bg=TRANSPARENT, highlightthickness=0, bd=0)
        self.canvas.pack()
        self._main_text = ""
        self._status_text = ""
        self._toast_text = ""
        self._main_color = self.cfg["color"]

        for widget in (self.root, self.canvas):
            widget.bind("<ButtonPress-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._drag)

        self.root.update_idletasks()
        self._set_click_through(True)
        self._keep_on_top()

    # ---------- Darstellung ----------
    def _draw_text(self, x: int, y: int, text: str, font, color: str) -> int:
        """Zeichnet Text mit Schatten und gibt die Unterkante zurück."""
        shadow = self.cfg["shadow_color"]
        for dx, dy in ((2, 2), (-1, -1), (1, -1), (-1, 1)):
            self.canvas.create_text(x + dx, y + dy, text=text, font=font, fill=shadow, anchor="nw")
        item = self.canvas.create_text(x, y, text=text, font=font, fill=color, anchor="nw")
        return self.canvas.bbox(item)[3]

    def _redraw(self) -> None:
        self.canvas.delete("all")
        y = self._draw_text(6, 2, self._main_text, self._main_font, self._main_color)
        for line in (self._status_text, self._toast_text):
            if line:
                y = self._draw_text(8, y + 2, line, self._small_font, "#FFFFFF")
        bbox = self.canvas.bbox("all") or (0, 0, 100, 40)
        width, height = bbox[2] + 8, bbox[3] + 6
        if self._move_mode:
            self.canvas.create_rectangle(1, 1, width - 2, height - 2, outline="#FFFFFF", dash=(4, 2), width=2)
        self.canvas.configure(width=width, height=height)

    def set_total(self, total: int, flash: bool = False) -> None:
        self._main_text = f"🧰 {self.cfg['label']}: {_format_number(total)}"
        if flash:
            self._main_color = self.cfg["flash_color"]
            if self._flash_job:
                self.root.after_cancel(self._flash_job)
            self._flash_job = self.root.after(600, self._end_flash)
        self._redraw()

    def _end_flash(self) -> None:
        self._flash_job = None
        self._main_color = self.cfg["color"]
        self._redraw()

    def set_status(self, text: str) -> None:
        self._status_text = text
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
        style |= WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        if enabled:
            style |= WS_EX_TRANSPARENT
        else:
            style &= ~WS_EX_TRANSPARENT
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

    def _keep_on_top(self) -> None:
        # Fortnite holt sich beim Fokuswechsel manchmal den Vordergrund zurück
        self.root.attributes("-topmost", True)
        self.root.lift()
        self.root.after(2000, self._keep_on_top)

    def toggle_move_mode(self) -> bool:
        self._move_mode = not self._move_mode
        self._set_click_through(not self._move_mode)
        if not self._move_mode:
            self._on_position_changed(self.root.winfo_x(), self.root.winfo_y())
        self._redraw()
        return self._move_mode

    def _start_drag(self, event) -> None:
        if self._move_mode:
            self._drag_offset = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def _drag(self, event) -> None:
        if self._move_mode:
            dx, dy = self._drag_offset
            self.root.geometry(f"+{event.x_root - dx}+{event.y_root - dy}")

    # ---------- Startwert-Dialog ----------
    def ask_value(self, title: str, prompt: str, initial: int, on_result: Callable[[int | None], None]) -> None:
        """Kleines Eingabefenster (immer oben), um den Zählerstand manuell zu setzen."""
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.attributes("-topmost", True)
        dialog.resizable(False, False)
        dialog.configure(padx=16, pady=12)

        tk.Label(dialog, text=prompt, justify="left").pack(anchor="w")
        var = tk.StringVar(value=str(initial))
        entry = tk.Entry(dialog, textvariable=var, width=14, font=("Segoe UI", 14))
        entry.pack(fill="x", pady=8)
        error = tk.Label(dialog, text="", fg="#C0392B")
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

        buttons = tk.Frame(dialog)
        buttons.pack(fill="x")
        tk.Button(buttons, text="Übernehmen", command=submit, width=12).pack(side="left")
        tk.Button(buttons, text="Abbrechen", command=lambda: finish(None), width=12).pack(side="right")

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

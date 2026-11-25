"""Work Counter: a tiny always-on-top widget that counts up today's pay.

Drag it anywhere. Right-click for options.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import tkinter as tk
from tkinter import messagebox

import paylogic as p

APP = "WorkCounter"
IS_WIN = sys.platform == "win32"

BG = "#15171c"
FG = "#f2f3f5"
MUTED = "#8a8f98"
DIM = "#4b5059"
ACCENT = "#4ade80"
PANEL = "#1d2027"

if IS_WIN:
    BIG = ("Segoe UI Semibold", 26)
    SMALL = ("Segoe UI", 10)
    UI = ("Segoe UI", 10)
else:
    BIG = ("DejaVu Sans", 24, "bold")
    SMALL = ("DejaVu Sans", 9)
    UI = ("DejaVu Sans", 10)

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


# --------------------------------------------------------------------------- config

def config_path() -> Path:
    if IS_WIN:
        base = Path(os.environ.get("APPDATA") or Path.home())
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / APP / "config.json"


def recent_wednesday(today: date) -> date:
    """Today if it's Wednesday, otherwise the most recent Wednesday."""
    return today - timedelta(days=(today.weekday() - 2) % 7)


def default_config() -> dict:
    return {
        "rate": 34.0,
        "hours": 7.5,
        "start": "09:00",
        "break_start": "12:30",
        "break_minutes": 0,
        "workdays": [0, 1, 2, 3, 4],
        "payday": recent_wednesday(date.today()).isoformat(),
        "overrides": {},
        "topmost": True,
        "x": None,
        "y": None,
        "setup_done": False,
    }


def load_config() -> dict:
    cfg = default_config()
    try:
        cfg.update(json.loads(config_path().read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return cfg


def save_config(cfg: dict) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def money(v: float) -> str:
    return f"{v:,.2f}"


# --------------------------------------------------------------------------- windows bits

def win_dpi_aware() -> None:
    if not IS_WIN:
        return
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def win_single_instance() -> bool:
    """False if another copy is already running."""
    if not IS_WIN:
        return True
    import ctypes
    ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\WorkCounterWidget")
    return ctypes.windll.kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS


def win_round_corners(root: tk.Tk) -> None:
    if not IS_WIN:
        return
    import ctypes
    try:
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        pref = ctypes.c_int(2)  # DWMWCP_ROUND (Windows 11)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
    except Exception:
        pass


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def launch_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")
    return f'"{pyw if pyw.exists() else exe}" "{Path(__file__).resolve()}"'


def autostart_enabled() -> bool:
    if not IS_WIN:
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP)
        return True
    except OSError:
        return False


def set_autostart(on: bool) -> None:
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, APP, 0, winreg.REG_SZ, launch_command())
        else:
            try:
                winreg.DeleteValue(k, APP)
            except OSError:
                pass


# --------------------------------------------------------------------------- widget

class Widget:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.cfg = load_config()
        self.days_win: DaysDialog | None = None
        self.settings_win: SettingsDialog | None = None

        root.title("Work Counter")
        root.overrideredirect(True)
        root.configure(bg=BG)
        root.attributes("-alpha", 0.95)
        root.attributes("-topmost", bool(self.cfg["topmost"]))

        box = tk.Frame(root, bg=BG, padx=18, pady=10)
        box.pack()
        row = tk.Frame(box, bg=BG)
        row.pack(anchor="w")
        self.dollar = tk.Label(row, text="$", font=BIG, fg=ACCENT, bg=BG)
        self.dollar.pack(side="left")
        self.amount = tk.Label(row, text="0.00", font=BIG, fg=FG, bg=BG)
        self.amount.pack(side="left")
        self.sub = tk.Label(box, text="", font=SMALL, fg=MUTED, bg=BG)
        self.sub.pack(anchor="w", pady=(0, 2))

        self.menu = tk.Menu(root, tearoff=0)
        for w in (root, box, row, self.dollar, self.amount, self.sub):
            w.bind("<ButtonPress-1>", self._press)
            w.bind("<B1-Motion>", self._drag)
            w.bind("<ButtonRelease-1>", self._release)
            w.bind("<Button-3>", self._popup)
            if sys.platform == "darwin":
                w.bind("<Button-2>", self._popup)

        self.tick()
        root.update_idletasks()
        self._place()
        win_round_corners(root)

        if not self.cfg.get("setup_done"):
            root.after(300, lambda: self.open_settings(first_run=True))

    # -- position / dragging
    def _place(self):
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w, h = self.root.winfo_reqwidth(), self.root.winfo_reqheight()
        x, y = self.cfg.get("x"), self.cfg.get("y")
        if x is None or y is None or not (0 <= x <= sw - 40 and 0 <= y <= sh - 40):
            x, y = sw - w - 40, 40
        self.root.geometry(f"+{x}+{y}")

    def _press(self, e):
        self._off = (e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y())

    def _drag(self, e):
        dx, dy = self._off
        self.root.geometry(f"+{e.x_root - dx}+{e.y_root - dy}")

    def _release(self, _e):
        self.cfg["x"], self.cfg["y"] = self.root.winfo_x(), self.root.winfo_y()
        self.save()

    # -- state
    def save(self):
        try:
            save_config(self.cfg)
        except OSError:
            pass

    def refresh(self):
        self.tick(reschedule=False)
        if self.days_win is not None:
            self.days_win.render()

    def tick(self, reschedule: bool = True):
        now = datetime.now()
        today = now.date()
        earned = p.day_earnings(today, now, self.cfg)
        period = p.period_earnings(now, self.cfg)

        counted = p.is_counted(today, self.cfg)
        if counted:
            note = ""
        elif p.is_default_workday(today, self.cfg):
            note = "voided · "
        else:
            note = "day off · "

        self.amount.config(text=money(earned), fg=FG if counted else DIM)
        self.dollar.config(fg=ACCENT if counted else DIM)
        self.sub.config(text=f"{note}this fortnight ${money(period)}")
        if reschedule:
            self.root.after(1000, self.tick)

    def set_counted(self, day: date, counted: bool):
        key = day.isoformat()
        ov = self.cfg.setdefault("overrides", {})
        if counted == p.is_default_workday(day, self.cfg):
            ov.pop(key, None)
        else:
            ov[key] = counted
        # forget overrides from old pay periods
        cutoff = (p.period_start(date.today(), self.cfg) - timedelta(days=p.PERIOD_DAYS)).isoformat()
        for k in [k for k in ov if k < cutoff]:
            del ov[k]
        self.save()
        self.refresh()

    # -- menu
    def _popup(self, e):
        m = self.menu
        m.delete(0, "end")
        today = date.today()
        if p.is_counted(today, self.cfg):
            m.add_command(label="Void today", command=lambda: self.set_counted(today, False))
        else:
            m.add_command(label="Count today as worked", command=lambda: self.set_counted(today, True))
        m.add_command(label="Days this fortnight…", command=self.open_days)
        m.add_command(label="Settings…", command=self.open_settings)
        m.add_separator()
        self._top = tk.BooleanVar(value=bool(self.cfg["topmost"]))
        m.add_checkbutton(label="Always on top", variable=self._top, command=self.toggle_topmost)
        if IS_WIN:
            self._auto = tk.BooleanVar(value=autostart_enabled())
            m.add_checkbutton(label="Start with Windows", variable=self._auto, command=self.toggle_autostart)
        m.add_separator()
        m.add_command(label="Quit", command=self.root.destroy)
        m.tk_popup(e.x_root, e.y_root)

    def toggle_topmost(self):
        self.cfg["topmost"] = self._top.get()
        self.root.attributes("-topmost", self.cfg["topmost"])
        self.save()

    def toggle_autostart(self):
        try:
            set_autostart(self._auto.get())
        except OSError as err:
            messagebox.showerror("Work Counter", f"Couldn't change startup setting:\n{err}")

    def open_days(self):
        if self.days_win is not None and self.days_win.winfo_exists():
            self.days_win.lift()
            return
        self.days_win = DaysDialog(self)

    def open_settings(self, first_run: bool = False):
        if self.settings_win is not None and self.settings_win.winfo_exists():
            self.settings_win.lift()
            return
        self.settings_win = SettingsDialog(self, first_run)


# --------------------------------------------------------------------------- dialogs

class Dialog(tk.Toplevel):
    def __init__(self, app: Widget, title: str):
        super().__init__(app.root)
        self.app = app
        self.title(title)
        self.configure(bg=BG, padx=18, pady=14)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.bind("<Escape>", lambda _e: self.destroy())

    def label(self, parent, text, fg=FG, font=UI, **kw):
        return tk.Label(parent, text=text, fg=fg, bg=BG, font=font, **kw)

    def check(self, parent, text, var, command=None):
        return tk.Checkbutton(
            parent, text=text, variable=var, command=command, font=UI,
            fg=FG, bg=BG, activebackground=BG, activeforeground=FG,
            selectcolor=PANEL, highlightthickness=0, bd=0, anchor="w",
        )

    def button(self, parent, text, command):
        return tk.Button(
            parent, text=text, command=command, font=UI, fg=FG, bg=PANEL,
            activebackground="#2a2e37", activeforeground=FG, relief="flat",
            bd=0, padx=12, pady=4, highlightthickness=0, cursor="hand2",
        )

    def centre_on_screen(self):
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 3
        self.geometry(f"+{x}+{y}")


class DaysDialog(Dialog):
    """Tick off which days of a fortnight count. Untick to void a day."""

    def __init__(self, app: Widget):
        super().__init__(app, "Days")
        self.start = p.period_start(date.today(), app.cfg)
        self.body = tk.Frame(self, bg=BG)
        self.body.pack()
        self.render()
        self.centre_on_screen()

    def shift(self, periods: int):
        self.start += timedelta(days=p.PERIOD_DAYS * periods)
        self.render()

    def render(self):
        for w in self.body.winfo_children():
            w.destroy()
        cfg = self.app.cfg
        now = datetime.now()
        days = p.period_days(self.start)
        end = days[-1]

        head = tk.Frame(self.body, bg=BG)
        head.pack(fill="x", pady=(0, 8))
        self.button(head, "‹", lambda: self.shift(-1)).pack(side="left")
        self.label(head, f"{self.start:%a %d %b} – {end:%a %d %b}").pack(side="left", expand=True)
        self.button(head, "›", lambda: self.shift(1)).pack(side="right")

        grid = tk.Frame(self.body, bg=BG)
        grid.pack(fill="x")
        for i, d in enumerate(days):
            var = tk.BooleanVar(value=p.is_counted(d, cfg))
            text = f"{d:%a %d %b}" + ("  · today" if d == now.date() else "")
            cb = self.check(grid, text, var, command=lambda d=d, v=var: self.app.set_counted(d, v.get()))
            cb.grid(row=i, column=0, sticky="w")
            amt = p.day_earnings(d, now, cfg) if d <= now.date() else 0.0
            if p.is_counted(d, cfg) and d > now.date():
                txt, colour = f"${money(p.day_pay(cfg))}", DIM
            elif p.is_counted(d, cfg):
                txt, colour = f"${money(amt)}", FG
            else:
                txt, colour = "—", DIM
            self.label(grid, txt, fg=colour).grid(row=i, column=1, sticky="e", padx=(24, 0))

        counted = sum(p.is_counted(d, cfg) for d in days)
        earned = sum(p.day_earnings(d, now, cfg) for d in days if d <= now.date())
        full = counted * p.day_pay(cfg)
        foot = tk.Frame(self.body, bg=BG)
        foot.pack(fill="x", pady=(10, 0))
        self.label(foot, f"Earned so far  ${money(earned)}", fg=MUTED, font=SMALL).pack(anchor="w")
        self.label(foot, f"Fortnight total  ${money(full)}  ({counted} shifts)", fg=MUTED, font=SMALL).pack(anchor="w")
        self.label(foot, f"Paid {end + timedelta(days=1):%a %d %b}", fg=MUTED, font=SMALL).pack(anchor="w")


class SettingsDialog(Dialog):
    def __init__(self, app: Widget, first_run: bool):
        super().__init__(app, "Work Counter settings")
        cfg = app.cfg
        self.protocol("WM_DELETE_WINDOW", self.cancel)

        if first_run:
            self.label(
                self, "Quick check before you start:", fg=ACCENT, font=UI,
            ).pack(anchor="w", pady=(0, 8))

        form = tk.Frame(self, bg=BG)
        form.pack(fill="x")
        self.vars = {}

        def field(row, label, key, value, hint=""):
            self.label(form, label, fg=MUTED).grid(row=row, column=0, sticky="w", pady=3)
            v = tk.StringVar(value=value)
            e = tk.Entry(
                form, textvariable=v, width=8, font=UI, fg=FG, bg=PANEL, insertbackground=FG,
                relief="flat", highlightthickness=1, highlightbackground=PANEL, highlightcolor=ACCENT,
            )
            e.grid(row=row, column=1, sticky="w", padx=(12, 6))
            if hint:
                self.label(form, hint, fg=DIM, font=SMALL).grid(row=row, column=2, sticky="w")
            self.vars[key] = v

        def num(x):
            return f"{x:g}"

        field(0, "Hourly rate ($)", "rate", num(cfg["rate"]))
        field(1, "Paid hours / shift", "hours", num(cfg["hours"]))
        field(2, "Shift starts", "start", cfg["start"], "24h, e.g. 08:30")
        field(3, "Unpaid break (min)", "break_minutes", str(cfg["break_minutes"]), "0 = none")
        field(4, "Break starts", "break_start", cfg["break_start"], "counter pauses")

        self.label(self, "Work days", fg=MUTED).pack(anchor="w", pady=(10, 2))
        days = tk.Frame(self, bg=BG)
        days.pack(anchor="w")
        self.day_vars = []
        for i, name in enumerate(DAY_NAMES):
            v = tk.BooleanVar(value=i in cfg["workdays"])
            self.check(days, name, v).pack(side="left", padx=(0, 6))
            self.day_vars.append(v)

        # Paid fortnightly on Wednesday: exactly one of the last two Wednesdays was payday.
        self.label(self, "Last payday was", fg=MUTED).pack(anchor="w", pady=(10, 2))
        w0 = recent_wednesday(date.today())
        w1 = w0 - timedelta(days=7)
        current = p.period_start(date.today(), cfg)
        self.payday = tk.StringVar(value=(w0 if current == w0 else w1).isoformat())
        pd = tk.Frame(self, bg=BG)
        pd.pack(anchor="w")
        for d in (w0, w1):
            label = f"{d:%a %d %b}" + (" (today)" if d == date.today() else "")
            tk.Radiobutton(
                pd, text=label, value=d.isoformat(), variable=self.payday, font=UI,
                fg=FG, bg=BG, activebackground=BG, activeforeground=FG,
                selectcolor=PANEL, highlightthickness=0, bd=0,
            ).pack(side="left", padx=(0, 10))

        btns = tk.Frame(self, bg=BG)
        btns.pack(fill="x", pady=(14, 0))
        self.button(btns, "Save", self.save).pack(side="right")
        self.button(btns, "Cancel", self.cancel).pack(side="right", padx=(0, 8))
        self.bind("<Return>", lambda _e: self.save())
        self.centre_on_screen()

    def cancel(self):
        if not self.app.cfg.get("setup_done"):
            # first run: accept defaults rather than nagging every launch
            self.app.cfg["setup_done"] = True
            self.app.save()
        self.destroy()

    def save(self):
        v = {k: s.get().strip() for k, s in self.vars.items()}
        try:
            rate = float(v["rate"].lstrip("$"))
            hours = float(v["hours"])
            brk = int(v["break_minutes"] or 0)
            start = self._hhmm(v["start"])
            bstart = self._hhmm(v["break_start"])
            if rate <= 0 or not 0 < hours <= 24 or brk < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Work Counter", "Check the numbers and times (HH:MM).", parent=self)
            return
        workdays = [i for i, d in enumerate(self.day_vars) if d.get()]
        self.app.cfg.update(
            rate=rate, hours=hours, start=start, break_minutes=brk, break_start=bstart,
            workdays=workdays, payday=self.payday.get(), setup_done=True,
        )
        self.app.save()
        self.app.refresh()
        self.destroy()

    @staticmethod
    def _hhmm(text: str) -> str:
        text = text.replace(".", ":")
        h, m = (text.split(":") + ["0"])[:2]
        h, m = int(h), int(m)
        if not (0 <= h < 24 and 0 <= m < 60):
            raise ValueError
        return f"{h:02d}:{m:02d}"


# --------------------------------------------------------------------------- main

def main():
    win_dpi_aware()
    if not win_single_instance():
        return
    root = tk.Tk()
    Widget(root)
    root.mainloop()


if __name__ == "__main__":
    main()

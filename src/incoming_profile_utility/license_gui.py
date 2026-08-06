"""The license screen — shown before the main window.

Two states, one window:
  * a valid license was found  -> holder + time remaining, Continue, and a Renew option;
  * nothing valid was found    -> the reason, this machine's hardware signature to send
                                  to the vendor, and a file picker for the license.

The activation panel (signature + picker) is the same in both states; it just starts
hidden when the license is already good.
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path

import customtkinter as ctk

from . import APP_NAME, short_version, version_string
from . import licensing
from .theme import (AMBER, BLUE_L, GREEN, GREEN_D, GREEN_INK, MUT, NAVY, NAVY_700,
                    NAVY_800, NAVY_900, ON, RED, SOFT, brand_logo)


class LicenseGate(ctk.CTkToplevel):
    """Modal license screen. `run()` returns True when the user may enter the app."""

    def __init__(self, master, status=None):
        super().__init__(master)
        self.configure(fg_color=NAVY)
        self.title(f"{APP_NAME} — License")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._quit)

        self.uf = ctk.CTkFont(family="Inter", size=13)
        self.ub = ctk.CTkFont(family="Inter", size=14, weight="bold")
        self.hf = ctk.CTkFont(family="Inter", size=22, weight="bold")
        self.sf = ctk.CTkFont(family="Inter", size=17, weight="bold")
        self.eb = ctk.CTkFont(family="JetBrains Mono", size=11)
        self.mono = ctk.CTkFont(family="JetBrains Mono", size=12)

        self._admitted = False
        self._panel_open = False
        self.status = status if status is not None else licensing.find_license()

        self.grid_columnconfigure(0, weight=1)
        self._header()
        self._status_card()
        self._activation_panel()
        self._buttons()
        self._render_status()
        if not self.status.ok:
            self._toggle_panel(True)                        # nothing to continue with: show it now
        self.after(10, self._center)

    # ---- layout ----
    def _header(self):
        h = ctk.CTkFrame(self, fg_color=NAVY_900, corner_radius=0, height=54)
        h.grid(row=0, column=0, sticky="ew")
        h.grid_propagate(False)
        h.grid_columnconfigure(0, weight=1)
        b = ctk.CTkFrame(h, fg_color="transparent")
        b.grid(row=0, column=0, sticky="w", padx=22, pady=8)
        logo = brand_logo(30)
        if logo is not None:
            self._logo_img = ctk.CTkImage(light_image=logo, dark_image=logo, size=logo.size)
            ctk.CTkLabel(b, image=self._logo_img, text="").pack(side="left", padx=(0, 14))
        ctk.CTkLabel(b, text=APP_NAME, font=self.hf, text_color=ON).pack(side="left")
        ctk.CTkLabel(h, text=short_version(), font=self.mono, text_color=MUT).grid(
            row=0, column=1, sticky="e", padx=22)

    def _card(self, row, pady=(18, 0)):
        c = ctk.CTkFrame(self, fg_color=NAVY_800, corner_radius=12,
                         border_width=1, border_color=NAVY_700)
        c.grid(row=row, column=0, sticky="ew", padx=22, pady=pady)
        c.grid_columnconfigure(0, weight=1)
        return c

    def _status_card(self):
        c = self._card(1)
        self.state_lbl = ctk.CTkLabel(c, text="", font=self.sf, text_color=ON, anchor="w")
        self.state_lbl.grid(row=0, column=0, sticky="w", padx=18, pady=(16, 2))
        self.holder_lbl = ctk.CTkLabel(c, text="", font=self.uf, text_color=SOFT, anchor="w",
                                       justify="left", wraplength=520)
        self.holder_lbl.grid(row=1, column=0, sticky="w", padx=18, pady=(0, 2))
        self.expiry_lbl = ctk.CTkLabel(c, text="", font=self.ub, text_color=SOFT, anchor="w")
        self.expiry_lbl.grid(row=2, column=0, sticky="w", padx=18, pady=(0, 2))
        self.path_lbl = ctk.CTkLabel(c, text="", font=self.eb, text_color=MUT, anchor="w",
                                     justify="left", wraplength=520)
        self.path_lbl.grid(row=3, column=0, sticky="w", padx=18, pady=(6, 16))

    def _activation_panel(self):
        self.panel = ctk.CTkFrame(self, fg_color=NAVY_800, corner_radius=12,
                                  border_width=1, border_color=NAVY_700)
        self.panel.grid_columnconfigure(0, weight=1)
        p = self.panel

        ctk.CTkLabel(p, text="Request a license", font=self.ub, text_color=ON, anchor="w"
                     ).grid(row=0, column=0, sticky="w", padx=18, pady=(14, 2))
        ctk.CTkLabel(p, text="Send this machine's hardware signature to your software vendor. "
                     "They return a license file that is valid on this computer only.",
                     font=self.eb, text_color=MUT, anchor="w", justify="left", wraplength=520
                     ).grid(row=1, column=0, sticky="w", padx=18, pady=(0, 8))

        sig = ctk.CTkFrame(p, fg_color="transparent")
        sig.grid(row=2, column=0, sticky="ew", padx=18)
        sig.grid_columnconfigure(0, weight=1)
        self.sig_entry = ctk.CTkEntry(sig, font=self.mono, fg_color=NAVY_900, border_color=NAVY_700,
                                      text_color=ON, height=32)
        self.sig_entry.grid(row=0, column=0, sticky="ew")
        signature = licensing.machine_signature()
        self.sig_entry.insert(0, signature or "unavailable on this machine")
        self.sig_entry.configure(state="readonly")          # selectable, not editable
        self._ghost(sig, "Copy", self._copy_signature, w=64).grid(row=0, column=1, padx=(8, 0))
        self._ghost(sig, "Save…", self._save_signature, w=64).grid(row=0, column=2, padx=(6, 0))
        self.sig_hint = ctk.CTkLabel(p, text="", font=self.eb, text_color=GREEN, anchor="w")
        self.sig_hint.grid(row=3, column=0, sticky="w", padx=18, pady=(4, 0))

        ctk.CTkFrame(p, height=1, fg_color=NAVY_700).grid(
            row=4, column=0, sticky="ew", padx=18, pady=(12, 12))

        ctk.CTkLabel(p, text="Already have a license file?", font=self.ub, text_color=ON, anchor="w"
                     ).grid(row=5, column=0, sticky="w", padx=18, pady=(0, 2))
        ctk.CTkLabel(p, text=f"It is normally called “{licensing.LICENSE_FILENAME}” and sits next to "
                     f"the program. Pick it here and it will be installed for you.",
                     font=self.eb, text_color=MUT, anchor="w", justify="left", wraplength=520
                     ).grid(row=6, column=0, sticky="w", padx=18, pady=(0, 8))
        row = ctk.CTkFrame(p, fg_color="transparent")
        row.grid(row=7, column=0, sticky="w", padx=18, pady=(0, 16))
        ctk.CTkButton(row, text="Select license file…", command=self._pick_license, font=self.ub,
                      width=170, fg_color=GREEN, hover_color=GREEN_D, text_color=GREEN_INK).pack(side="left")
        self.pick_hint = ctk.CTkLabel(row, text="", font=self.eb,
                                      text_color=RED, justify="left", wraplength=330)
        self.pick_hint.pack(side="left", padx=(12, 0))

    def _buttons(self):
        b = ctk.CTkFrame(self, fg_color="transparent")
        b.grid(row=3, column=0, sticky="ew", padx=22, pady=(16, 16))
        self.continue_btn = ctk.CTkButton(b, text="Continue →", command=self._admit, font=self.ub, width=130,
                                          height=36, fg_color=GREEN, hover_color=GREEN_D, text_color=GREEN_INK)
        self.continue_btn.pack(side="right")
        self.renew_btn = self._ghost(
            b, "Renew license…", lambda: self._toggle_panel(not self._panel_open), w=140)
        self.renew_btn.pack(side="right", padx=(0, 8))
        self._ghost(b, "Quit", self._quit, w=80).pack(side="left")
        ctk.CTkLabel(b, text=version_string(), font=self.eb,
                     text_color=MUT).pack(side="left", padx=(12, 0))

    def _ghost(self, parent, text, cmd, w=90):
        return ctk.CTkButton(parent, text=text, command=cmd, font=self.uf, width=w, height=32,
                             fg_color="transparent", border_width=1, border_color=BLUE_L,
                             text_color=ON, hover_color=NAVY_700)

    # ---- state ----
    def _render_status(self):
        s = self.status
        if s.ok and s.dev_mode:
            self.state_lbl.configure(text="Development build", text_color=AMBER)
            self.holder_lbl.configure(text="Running from source without the license component — "
                                           "the check is skipped. Frozen builds always require a license.")
            self.expiry_lbl.configure(text="")
            self.path_lbl.configure(text="")
        elif s.ok:
            self.state_lbl.configure(text="License valid", text_color=GREEN)
            self.holder_lbl.configure(text=f"Licensed to {s.holder}" if s.holder else "")
            self.expiry_lbl.configure(text=s.expiry_text,
                                      text_color=(AMBER if s.expires_soon else SOFT))
            self.path_lbl.configure(text=f"License file: {s.path}")
        else:
            self.state_lbl.configure(text="No valid license", text_color=RED)
            self.holder_lbl.configure(text=s.reason)
            self.expiry_lbl.configure(text="")
            where = s.path or licensing.default_license_path()
            self.path_lbl.configure(text=f"Looked for: {where}"
                                    + (f"    ·    {s.code}" if s.code else ""))
        self.continue_btn.configure(state=("normal" if s.ok else "disabled"))
        self.renew_btn.configure(text=("Renew license…" if s.ok else "Activation options"))
        self._resize()

    def _toggle_panel(self, show):
        self._panel_open = show
        if show:
            self.panel.grid(row=2, column=0, sticky="ew", padx=22, pady=(14, 0))
        else:
            self.panel.grid_remove()
        self._resize()

    def _resize(self):
        self.update_idletasks()
        self.geometry(f"600x{self.winfo_reqheight()}")

    def _center(self):
        self.update_idletasks()
        w = self.winfo_width() or 600
        h = self.winfo_height() or 460
        x = (self.winfo_screenwidth() - w) // 2
        y = max(0, (self.winfo_screenheight() - h) // 3)
        self.geometry(f"+{x}+{y}")

    # ---- actions ----
    def _copy_signature(self):
        sig = licensing.machine_signature()
        if not sig:
            self._flash(self.sig_hint, "No hardware signature available on this machine.", RED)
            return
        self.clipboard_clear()
        self.clipboard_append(sig)
        self._flash(self.sig_hint, "Hardware signature copied to the clipboard.", GREEN)

    def _save_signature(self):
        from tkinter import filedialog
        sig = licensing.machine_signature()
        if not sig:
            self._flash(self.sig_hint, "No hardware signature available on this machine.", RED)
            return
        path = filedialog.asksaveasfilename(parent=self, title="Save hardware signature",
                                            defaultextension=".txt", initialfile="hardware_signature.txt",
                                            filetypes=[("Text file", "*.txt"), ("All files", "*.*")])
        if not path:
            return
        try:
            Path(path).write_text(f"{APP_NAME} {short_version()}\nHardware signature: {sig}\n",
                                  encoding="utf-8")
        except OSError as exc:
            self._flash(self.sig_hint, f"Could not write that file: {exc.strerror or exc}", RED)
            return
        self._flash(self.sig_hint, f"Saved to {Path(path).name}.", GREEN)

    def _pick_license(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(parent=self, title="Select license file",
                                          initialdir=str(licensing.app_dir()),
                                          filetypes=[("License file", "*.lic"), ("All files", "*.*")])
        if not path:
            return
        status = licensing.check(path)
        if not status.ok:
            self.pick_hint.configure(text=status.reason, text_color=RED)
            return
        installed, copied = licensing.install(path)
        self.status = licensing.check(installed)
        self.pick_hint.configure(
            text=("License installed." if copied else "License accepted — this file will be used "
                  "from where it is (the program folder is not writable)."),
            text_color=GREEN)
        self._render_status()

    def _flash(self, label, text, color):
        label.configure(text=text, text_color=color)
        self.after(4000, lambda: label.configure(text=""))

    def _admit(self):
        if not self.status.ok:
            return
        self._admitted = True
        self.destroy()

    def _quit(self):
        self._admitted = False
        self.destroy()

    # ---- modal ----
    def run(self) -> bool:
        # Only tie to the parent when it is actually on screen: a transient window gets no
        # taskbar button of its own, and the main window is hidden while this gate is up.
        if self.master is not None and self.master.winfo_viewable():
            self.transient(self.master)
        self.grab_set()
        self.lift()
        self.focus_force()
        self.bind("<Escape>", lambda _e: self._quit())
        self.bind("<Return>", lambda _e: self._admit())
        self.wait_window(self)
        return self._admitted


def require_license(master) -> bool:
    """Show the license screen over `master` (kept hidden). True = start the app."""
    status = licensing.find_license()
    if status.ok and status.dev_mode:
        # Source checkout without the license component: nothing to show and nothing to
        # renew, so don't put a screen in a developer's way — just say so on the console.
        print("[license] license_usher not installed — running unlicensed from source.")
        return True
    try:
        return LicenseGate(master, status).run()
    except tk.TclError:                                     # window torn down mid-check
        return False

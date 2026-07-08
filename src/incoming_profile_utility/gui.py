"""Incoming Profile Utility — GUI (customtkinter), themed with SandBox brand colors.

Meets the v1 minimum requirements (docs/00): input via GUI, load a CSV trace,
parametric input (pitch / thicknesses / curvature), symmetric output, and Save .bmp.
Profiles are composed as material/vacuum regions (default: a vacuum feature carved
into surrounding material) using the central palette (materials.py).

Run:  python -m incoming_profile_utility.main   (or profile-utility)
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import customtkinter as ctk
from PIL import Image

from .materials import load_palette
from .parametric import build_profile
from .profiles import render_trace_csv
from . import renderer as rnd

# --- SandBox brand tokens (from the design system) ---
NAVY = "#0E1B2E"; NAVY_900 = "#0B1626"; NAVY_800 = "#132540"; NAVY_700 = "#1C2C46"
BLUE = "#283D5D"; BLUE_L = "#6E90C6"
GREEN = "#4FD093"; GREEN_D = "#0E7A49"; GREEN_INK = "#07271A"
ON_DARK = "#FFFFFF"; ON_DARK_SOFT = "#AEB9C8"; ON_DARK_MUTED = "#8B99AC"

FIELDS = [
    ("pitch", "Pitch (nm)", "90"),
    ("space", "Space (nm)", ""),
    ("feature_height", "Feature height (nm)", "200"),
    ("top_width", "Top width (nm)", "45"),
    ("bottom_width", "Bottom width (nm)", "20"),
    ("bow", "Bow · max CD (nm)", ""),
    ("bow_height", "Bow height (nm)", ""),
    ("mask_height", "Mask height (nm)", "30"),
]


class ProfileStudio(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.title("Incoming Profile Utility")
        self.geometry("1040x700")
        self.configure(fg_color=NAVY)

        self.palette = load_palette()
        self.csv_path = None
        self.mode = "Parametric"

        self.ui_font = ctk.CTkFont(family="Inter", size=13)
        self.ui_bold = ctk.CTkFont(family="Inter", size=14, weight="bold")
        self.title_font = ctk.CTkFont(family="Inter", size=20, weight="bold")
        self.mono = ctk.CTkFont(family="JetBrains Mono", size=12)
        self.eyebrow = ctk.CTkFont(family="JetBrains Mono", size=11)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._header()
        self._body()
        self._footer()
        self.after(120, self.render_preview)

    def _header(self):
        h = ctk.CTkFrame(self, fg_color=NAVY_900, corner_radius=0, height=66)
        h.grid(row=0, column=0, sticky="ew")
        h.grid_propagate(False)
        h.grid_columnconfigure(0, weight=1)
        box = ctk.CTkFrame(h, fg_color="transparent")
        box.grid(row=0, column=0, sticky="w", padx=22, pady=12)
        ctk.CTkLabel(box, text="SANDBOX · PROFILE STUDIO", font=self.eyebrow,
                     text_color=BLUE_L).pack(anchor="w")
        ctk.CTkLabel(box, text="Incoming Profile Utility", font=self.title_font,
                     text_color=ON_DARK).pack(anchor="w")
        pill = ctk.CTkFrame(h, fg_color=GREEN, corner_radius=999)
        pill.grid(row=0, column=1, sticky="e", padx=22)
        ctk.CTkLabel(pill, text="v1", font=self.mono, text_color=GREEN_INK).pack(padx=12, pady=3)

    def _body(self):
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=18, pady=16)
        body.grid_columnconfigure(0, weight=0, minsize=430)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)
        self._inputs(body)
        self._preview(body)

    def _card(self, parent, title):
        card = ctk.CTkFrame(parent, fg_color=NAVY_800, corner_radius=12,
                            border_width=1, border_color=NAVY_700)
        ctk.CTkLabel(card, text=title, font=self.ui_bold, text_color=ON_DARK).pack(
            anchor="w", padx=18, pady=(14, 6))
        return card

    def _inputs(self, parent):
        card = self._card(parent, "Inputs")
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        seg = ctk.CTkSegmentedButton(
            card, values=["Parametric", "CSV trace"], command=self._set_mode,
            font=self.ui_font, fg_color=NAVY_900, selected_color=BLUE,
            selected_hover_color=BLUE_L, unselected_color=NAVY_900,
            text_color=ON_DARK_SOFT)
        seg.set("Parametric"); seg.pack(fill="x", padx=18, pady=(0, 10))

        scroll = ctk.CTkScrollableFrame(card, fg_color="transparent", height=430)
        scroll.pack(fill="both", expand=True, padx=10)
        scroll.grid_columnconfigure(1, weight=1)

        self.entries = {}
        for i, (key, label, default) in enumerate(FIELDS):
            ctk.CTkLabel(scroll, text=label, font=self.ui_font,
                         text_color=ON_DARK_SOFT).grid(row=i, column=0, sticky="w",
                                                       padx=(8, 10), pady=5)
            e = ctk.CTkEntry(scroll, font=self.mono, fg_color=NAVY_900,
                             border_color=NAVY_700, text_color=ON_DARK, width=120)
            e.insert(0, default)
            e.grid(row=i, column=1, sticky="ew", padx=(0, 8), pady=5)
            self.entries[key] = e

        r0 = len(FIELDS)
        ctk.CTkLabel(scroll, text="REGIONS", font=self.eyebrow, text_color=BLUE_L).grid(
            row=r0, column=0, columnspan=2, sticky="w", padx=8, pady=(12, 2))
        mats = self.palette.names()
        self.opt = {}
        for j, (key, label, default) in enumerate([
                ("surround_material", "Surround", "silicon"),
                ("feature_material", "Feature", "vacuum"),
                ("mask_material", "Mask", "hardmask")]):
            ctk.CTkLabel(scroll, text=label, font=self.ui_font,
                         text_color=ON_DARK_SOFT).grid(row=r0 + 1 + j, column=0,
                                                       sticky="w", padx=(8, 10), pady=5)
            om = ctk.CTkOptionMenu(scroll, values=mats, font=self.ui_font,
                                   fg_color=NAVY_900, button_color=BLUE,
                                   button_hover_color=BLUE_L, text_color=ON_DARK)
            om.set(default)
            om.grid(row=r0 + 1 + j, column=1, sticky="ew", padx=(0, 8), pady=5)
            self.opt[key] = om

        r1 = r0 + 5
        ctk.CTkLabel(scroll, text="Scale (nm/px)", font=self.ui_font,
                     text_color=ON_DARK_SOFT).grid(row=r1, column=0, sticky="w",
                                                   padx=(8, 10), pady=5)
        self.scale_entry = ctk.CTkEntry(scroll, font=self.mono, fg_color=NAVY_900,
                                        border_color=NAVY_700, text_color=ON_DARK, width=120)
        self.scale_entry.insert(0, "0.4")
        self.scale_entry.grid(row=r1, column=1, sticky="ew", padx=(0, 8), pady=5)

        self.csv_btn = ctk.CTkButton(scroll, text="Load CSV…", command=self._load_csv,
                                     font=self.ui_font, fg_color="transparent",
                                     border_width=1, border_color=BLUE_L,
                                     text_color=ON_DARK, hover_color=NAVY_700)
        self.csv_label = ctk.CTkLabel(scroll, text="no file", font=self.mono,
                                      text_color=ON_DARK_MUTED)

    def _preview(self, parent):
        card = self._card(parent, "Preview")
        card.grid(row=0, column=1, sticky="nsew")

        frame = ctk.CTkFrame(card, fg_color=NAVY_900, corner_radius=10)
        frame.pack(expand=True, fill="both", padx=18, pady=6)
        self.preview = ctk.CTkLabel(frame, text="", fg_color=NAVY_900)
        self.preview.pack(expand=True, fill="both", padx=10, pady=10)

        bar = ctk.CTkFrame(card, fg_color="transparent")
        bar.pack(fill="x", padx=18, pady=(6, 16))
        bar.grid_columnconfigure(0, weight=1)
        self.out_entry = ctk.CTkEntry(bar, font=self.mono, fg_color=NAVY_900,
                                      border_color=NAVY_700, text_color=ON_DARK)
        self.out_entry.insert(0, "outputs/profile.bmp")
        self.out_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        ctk.CTkButton(bar, text="Render", command=self.render_preview, font=self.ui_font,
                      width=90, fg_color="transparent", border_width=1,
                      border_color=BLUE_L, text_color=ON_DARK,
                      hover_color=NAVY_700).grid(row=0, column=1, padx=(0, 8))
        ctk.CTkButton(bar, text="Save .bmp", command=self.save_bmp, font=self.ui_bold,
                      width=120, fg_color=GREEN, hover_color=GREEN_D,
                      text_color=GREEN_INK).grid(row=0, column=2)

    def _footer(self):
        ctk.CTkLabel(self, text="Symmetric · 24-bit BMP · material/vacuum composition",
                     font=self.eyebrow, text_color=ON_DARK_MUTED).grid(
            row=2, column=0, sticky="w", padx=22, pady=(0, 10))

    def _set_mode(self, value):
        self.mode = value
        if value == "CSV trace":
            self.csv_btn.grid(row=99, column=0, columnspan=2, sticky="ew", padx=8, pady=(10, 2))
            self.csv_label.grid(row=100, column=0, columnspan=2, sticky="w", padx=8)
        else:
            self.csv_btn.grid_forget(); self.csv_label.grid_forget()

    def _load_csv(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if path:
            self.csv_path = Path(path)
            self.csv_label.configure(text=self.csv_path.name)
            self.render_preview()

    def _params(self):
        p = {}
        for key, e in self.entries.items():
            v = e.get().strip()
            if v:
                p[key] = float(v)
        for key, om in self.opt.items():
            p[key] = om.get()
        return p

    def _scale(self):
        try:
            return float(self.scale_entry.get())
        except ValueError:
            return 0.4

    def _render_to(self, out_path):
        npp = self._scale()
        if self.mode == "CSV trace" and self.csv_path:
            render_trace_csv(self.csv_path, out_path, npp)
        else:
            layers, dims = build_profile(self._params(), self.palette, npp)
            rnd.render_layers(layers, dims, out_path)

    def render_preview(self):
        try:
            tmp = Path(tempfile.gettempdir()) / "_ipu_preview.bmp"
            self._render_to(tmp)
            img = Image.open(tmp).convert("RGB")
            w, h = img.size
            scale = min(4.0, 520 / h)
            disp = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.NEAREST)
            self.preview.configure(image=ctk.CTkImage(light_image=disp, dark_image=disp,
                                                      size=disp.size), text="")
        except Exception as exc:
            self.preview.configure(image=None, text=f"⚠ {exc}", text_color=ON_DARK_MUTED)

    def save_bmp(self):
        out = Path(self.out_entry.get().strip() or "outputs/profile.bmp")
        out.parent.mkdir(parents=True, exist_ok=True)
        self._render_to(out)
        self.title(f"Incoming Profile Utility — saved {out.name}")


def launch() -> None:
    ProfileStudio().mainloop()

"""Incoming Profile Utility — GUI (customtkinter), themed with SandBox brand colors.

Meets the v1 minimum requirements (docs/00) and adds: per-field info tooltips, an
nm grid on the preview, a material legend, user-defined materials (name + color),
CSV auto-populate of parametric fields, and mode-specific input panels.
"""
from __future__ import annotations

import math
import tempfile
from pathlib import Path

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont

from .materials import load_palette, _DEFAULT_CONFIG
from .parametric import build_profile
from .profiles import render_trace_csv
from .io_csv import load_trace, trace_to_parametric
from . import renderer as rnd

# --- SandBox brand tokens ---
NAVY = "#0E1B2E"; NAVY_900 = "#0B1626"; NAVY_800 = "#132540"; NAVY_700 = "#1C2C46"
BLUE = "#283D5D"; BLUE_L = "#6E90C6"
GREEN = "#4FD093"; GREEN_D = "#0E7A49"; GREEN_INK = "#07271A"
ON_DARK = "#FFFFFF"; ON_DARK_SOFT = "#AEB9C8"; ON_DARK_MUTED = "#8B99AC"

# (key, label, default, info)
FIELDS = [
    ("pitch", "Pitch (nm)", "90", "Width of one repeating unit cell (one line + one space)."),
    ("space", "Space (nm)", "", "Gap width. pitch = linewidth + space. Provide pitch, or space + a width."),
    ("feature_height", "Feature height (nm)", "200", "Vertical extent of the feature, base (0) to top."),
    ("top_width", "Top width (nm)", "45", "Full CD at the top of the feature."),
    ("mid_width", "Mid width (nm)", "", "Optional CD at mid-height for a gentle curve (ignored if Bow is set)."),
    ("bottom_width", "Bottom width (nm)", "20", "Full CD at the base of the feature."),
    ("bow", "Bow · max CD (nm)", "", "The MAXIMUM CD — the widest full width on the wall. Must be >= top and bottom."),
    ("bow_height", "Bow height (nm)", "", "Height at which the bow (max CD) occurs. Default: mid-height."),
    ("mask_height", "Mask height (nm)", "30", "Height of the mask on top (0 = none)."),
]
MAT_INFO = {
    "surround_material": "Surround: the bulk material that fills the cell and that the feature sits in or is carved from.",
    "feature_material": "Feature: the CD-curve region. 'vacuum' = open space -> the default trench-in-material (inverted) case.",
    "mask_material": "Mask: the material on top — a band with the feature opening (inverted) or a block over a solid feature.",
}


class Tooltip:
    def __init__(self, widget, text):
        self.widget, self.text, self.tip = widget, text, None
        widget.bind("<Enter>", self._show); widget.bind("<Leave>", self._hide)

    def _show(self, _=None):
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 18; y = self.widget.winfo_rooty() + 18
        self.tip = tw = ctk.CTkToplevel(self.widget)
        tw.wm_overrideredirect(True); tw.wm_geometry(f"+{x}+{y}")
        tw.configure(fg_color=NAVY_700)
        ctk.CTkLabel(tw, text=self.text, justify="left", wraplength=260,
                     text_color=ON_DARK, fg_color=NAVY_700,
                     font=ctk.CTkFont(size=11)).pack(padx=8, pady=6)

    def _hide(self, _=None):
        if self.tip:
            self.tip.destroy(); self.tip = None


def _nice_step(extent: float) -> float:
    if extent <= 0:
        return 10.0
    raw = extent / 5.0
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag


def compose_preview(bmp_path, nm_per_px: float, target_h: int = 470) -> Image.Image:
    """Scale the rendered profile and overlay an nm grid with axis labels."""
    img = Image.open(bmp_path).convert("RGB")
    w, h = img.size
    disp = min(6.0, target_h / h)
    dw, dh = max(1, int(w * disp)), max(1, int(h * disp))
    prof = img.resize((dw, dh), Image.NEAREST)

    ML, MB, MT, MR = 48, 30, 12, 14
    canvas = Image.new("RGB", (ML + dw + MR, MT + dh + MB), (11, 22, 38))
    canvas.paste(prof, (ML, MT))

    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    font = ImageFont.load_default()
    ppn = disp / nm_per_px
    width_nm, height_nm = w * nm_per_px, h * nm_per_px
    stepx, stepy = _nice_step(width_nm), _nice_step(height_nm)
    grid = (110, 144, 198, 70); tick = (110, 144, 198, 255)

    for k in range(int(width_nm // stepx) + 1):
        xnm = k * stepx; x = ML + xnm * ppn
        d.line([(x, MT), (x, MT + dh)], fill=grid)
        d.text((x - 5, MT + dh + 5), f"{int(xnm)}", fill=tick, font=font)
    for k in range(int(height_nm // stepy) + 1):
        ynm = k * stepy; y = MT + dh - ynm * ppn
        d.line([(ML, y), (ML + dw, y)], fill=grid)
        d.text((6, y - 4), f"{int(ynm)}", fill=tick, font=font)
    d.text((ML, MT + dh + 16), "width nm  /  height nm ↑", fill=tick, font=font)

    return Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")


class ProfileStudio(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.title("Incoming Profile Utility")
        self.geometry("1120x760")
        self.configure(fg_color=NAVY)

        self.palette = load_palette()
        self.csv_path = None
        self.mode = "Parametric"
        self.material_menus = []

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
        self._set_mode("Parametric")
        self.after(150, self.render_preview)

    # ---------- info-row helper ----------
    def _row(self, parent, r, label, info, widget):
        ctk.CTkLabel(parent, text=label, font=self.ui_font,
                     text_color=ON_DARK_SOFT).grid(row=r, column=0, sticky="w",
                                                   padx=(8, 6), pady=5)
        ic = ctk.CTkLabel(parent, text="ⓘ", font=self.ui_font, text_color=BLUE_L,
                          cursor="hand2")
        ic.grid(row=r, column=1, sticky="w", padx=(0, 8)); Tooltip(ic, info)
        widget.grid(row=r, column=2, sticky="ew", padx=(0, 8), pady=5)

    # ---------- layout ----------
    def _header(self):
        h = ctk.CTkFrame(self, fg_color=NAVY_900, corner_radius=0, height=66)
        h.grid(row=0, column=0, sticky="ew"); h.grid_propagate(False)
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
        body.grid_columnconfigure(0, weight=0, minsize=470)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)
        self._inputs(body)
        self._preview_card(body)

    def _card(self, parent, title):
        card = ctk.CTkFrame(parent, fg_color=NAVY_800, corner_radius=12,
                            border_width=1, border_color=NAVY_700)
        ctk.CTkLabel(card, text=title, font=self.ui_bold, text_color=ON_DARK).pack(
            anchor="w", padx=18, pady=(14, 6))
        return card

    def _mat_menu(self, parent, default):
        om = ctk.CTkOptionMenu(parent, values=self.palette.names(), font=self.ui_font,
                               fg_color=NAVY_900, button_color=BLUE,
                               button_hover_color=BLUE_L, text_color=ON_DARK,
                               command=lambda _v: self.render_preview())
        om.set(default); self.material_menus.append(om)
        return om

    def _inputs(self, parent):
        card = self._card(parent, "Inputs")
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        seg = ctk.CTkSegmentedButton(card, values=["Parametric", "CSV trace"],
                                     command=self._set_mode, font=self.ui_font,
                                     fg_color=NAVY_900, selected_color=BLUE,
                                     selected_hover_color=BLUE_L, unselected_color=NAVY_900,
                                     text_color=ON_DARK_SOFT)
        seg.set("Parametric"); seg.pack(fill="x", padx=18, pady=(0, 10))

        # ----- Parametric page -----
        self.param_page = ctk.CTkScrollableFrame(card, fg_color="transparent", height=470)
        self.param_page.grid_columnconfigure(2, weight=1)
        self.entries = {}
        for i, (key, label, default, info) in enumerate(FIELDS):
            e = ctk.CTkEntry(self.param_page, font=self.mono, fg_color=NAVY_900,
                             border_color=NAVY_700, text_color=ON_DARK, width=120)
            e.insert(0, default)
            e.bind("<KeyRelease>", self._schedule_render)
            self._row(self.param_page, i, label, info, e)
            self.entries[key] = e

        r0 = len(FIELDS)
        ctk.CTkLabel(self.param_page, text="MATERIALS", font=self.eyebrow,
                     text_color=BLUE_L).grid(row=r0, column=0, columnspan=3,
                                             sticky="w", padx=8, pady=(12, 2))
        self.opt = {}
        for j, (key, label, default) in enumerate([
                ("surround_material", "Surround", "silicon"),
                ("feature_material", "Feature", "vacuum"),
                ("mask_material", "Mask", "hardmask")]):
            om = self._mat_menu(self.param_page, default)
            self._row(self.param_page, r0 + 1 + j, label, MAT_INFO[key], om)
            self.opt[key] = om
        ctk.CTkButton(self.param_page, text="＋ Add material", command=self._add_material,
                      font=self.ui_font, fg_color="transparent", border_width=1,
                      border_color=BLUE_L, text_color=ON_DARK, hover_color=NAVY_700
                      ).grid(row=r0 + 5, column=0, columnspan=3, sticky="ew", padx=8, pady=(8, 4))

        # ----- CSV page -----
        self.csv_page = ctk.CTkScrollableFrame(card, fg_color="transparent", height=470)
        self.csv_page.grid_columnconfigure(2, weight=1)
        ctk.CTkButton(self.csv_page, text="Load CSV…", command=self._load_csv,
                      font=self.ui_font, fg_color="transparent", border_width=1,
                      border_color=BLUE_L, text_color=ON_DARK, hover_color=NAVY_700
                      ).grid(row=0, column=0, columnspan=3, sticky="ew", padx=8, pady=(6, 4))
        self.csv_label = ctk.CTkLabel(self.csv_page, text="no file loaded", font=self.mono,
                                      text_color=ON_DARK_MUTED)
        self.csv_label.grid(row=1, column=0, columnspan=3, sticky="w", padx=8)
        self.csv_note = ctk.CTkLabel(self.csv_page, text="", font=self.eyebrow,
                                     text_color=GREEN, wraplength=380, justify="left")
        self.csv_note.grid(row=2, column=0, columnspan=3, sticky="w", padx=8, pady=(4, 8))
        self.csv_fill = self._mat_menu(self.csv_page, "silicon")
        self._row(self.csv_page, 3, "Fill material",
                  "Color used to fill the trace feature.", self.csv_fill)

        # ----- common: scale -----
        common = ctk.CTkFrame(card, fg_color="transparent")
        common.pack(fill="x", padx=10, pady=(2, 8)); common.grid_columnconfigure(2, weight=1)
        self.scale_entry = ctk.CTkEntry(common, font=self.mono, fg_color=NAVY_900,
                                        border_color=NAVY_700, text_color=ON_DARK, width=120)
        self.scale_entry.insert(0, "0.4")
        self.scale_entry.bind("<KeyRelease>", self._schedule_render)
        self._row(common, 0, "Scale (nm/px)",
                  "Nanometers per pixel. Smaller = higher resolution / larger image.",
                  self.scale_entry)

    def _preview_card(self, parent):
        card = self._card(parent, "Preview")
        card.grid(row=0, column=1, sticky="nsew")
        frame = ctk.CTkFrame(card, fg_color=NAVY_900, corner_radius=10)
        frame.pack(expand=True, fill="both", padx=18, pady=6)
        self.preview = ctk.CTkLabel(frame, text="", fg_color=NAVY_900)
        self.preview.pack(expand=True, fill="both", padx=10, pady=10)

        self.legend = ctk.CTkFrame(card, fg_color="transparent")
        self.legend.pack(fill="x", padx=18, pady=(0, 4))

        bar = ctk.CTkFrame(card, fg_color="transparent")
        bar.pack(fill="x", padx=18, pady=(4, 16)); bar.grid_columnconfigure(0, weight=1)
        self.out_entry = ctk.CTkEntry(bar, font=self.mono, fg_color=NAVY_900,
                                      border_color=NAVY_700, text_color=ON_DARK)
        self.out_entry.insert(0, "outputs/profile.bmp")
        self.out_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        ctk.CTkButton(bar, text="Render", command=self.render_preview, font=self.ui_font,
                      width=90, fg_color="transparent", border_width=1,
                      border_color=BLUE_L, text_color=ON_DARK, hover_color=NAVY_700
                      ).grid(row=0, column=1, padx=(0, 8))
        ctk.CTkButton(bar, text="Save .bmp", command=self.save_bmp, font=self.ui_bold,
                      width=120, fg_color=GREEN, hover_color=GREEN_D,
                      text_color=GREEN_INK).grid(row=0, column=2)

    def _footer(self):
        ctk.CTkLabel(self, text="Symmetric · 24-bit BMP · material/vacuum composition",
                     font=self.eyebrow, text_color=ON_DARK_MUTED).grid(
            row=2, column=0, sticky="w", padx=22, pady=(0, 10))

    # ---------- behavior ----------
    def _set_mode(self, value):
        self.mode = value
        self.param_page.pack_forget(); self.csv_page.pack_forget()
        (self.param_page if value == "Parametric" else self.csv_page).pack(
            fill="both", expand=True, padx=10)
        self.render_preview()

    def _update_menus(self):
        names = self.palette.names()
        for om in self.material_menus:
            cur = om.get(); om.configure(values=names); om.set(cur)

    def _add_material(self):
        from tkinter.colorchooser import askcolor
        dlg = ctk.CTkToplevel(self); dlg.title("Add material")
        dlg.geometry("340x220"); dlg.configure(fg_color=NAVY_800); dlg.transient(self)
        ctk.CTkLabel(dlg, text="New material", font=self.ui_bold, text_color=ON_DARK).pack(
            anchor="w", padx=16, pady=(14, 6))
        name_e = ctk.CTkEntry(dlg, placeholder_text="name (e.g. tungsten)", font=self.ui_font,
                              fg_color=NAVY_900, border_color=NAVY_700, text_color=ON_DARK)
        name_e.pack(fill="x", padx=16, pady=6)
        chosen = {"rgb": (79, 208, 147)}
        swatch = ctk.CTkFrame(dlg, fg_color="#4FD093", width=40, height=24, corner_radius=6)
        swatch.pack(side="left", padx=(16, 8), pady=10)

        def pick():
            rgb, _hex = askcolor(parent=dlg, title="Pick material color")
            if rgb:
                chosen["rgb"] = tuple(int(c) for c in rgb)
                swatch.configure(fg_color=f"#{chosen['rgb'][0]:02X}{chosen['rgb'][1]:02X}{chosen['rgb'][2]:02X}")

        ctk.CTkButton(dlg, text="Pick color…", command=pick, font=self.ui_font,
                      fg_color="transparent", border_width=1, border_color=BLUE_L,
                      text_color=ON_DARK, hover_color=NAVY_700).pack(side="left", pady=10)

        def commit():
            name = name_e.get().strip().lower().replace(" ", "_")
            if name:
                self.palette.add(name, chosen["rgb"], label=name_e.get().strip())
                try:
                    self.palette.save(_DEFAULT_CONFIG)
                except OSError:
                    pass
                self._update_menus()
            dlg.destroy()

        ctk.CTkButton(dlg, text="Add", command=commit, font=self.ui_bold, width=90,
                      fg_color=GREEN, hover_color=GREEN_D, text_color=GREEN_INK
                      ).pack(side="right", padx=16, pady=10)

    def _load_csv(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if not path:
            return
        self.csv_path = Path(path)
        self.csv_label.configure(text=self.csv_path.name)
        try:
            fitted = trace_to_parametric(load_trace(self.csv_path))
            for k in ("bow", "bow_height", "mid_width"):
                self.entries[k].delete(0, "end")
            for k, v in fitted.items():
                if k in self.entries:
                    self.entries[k].delete(0, "end"); self.entries[k].insert(0, str(v))
            self.csv_note.configure(
                text="✓ Parametric fields populated from CSV (approx.). "
                     "Switch to Parametric to edit. Pitch/mask not in CSV — set manually.")
        except Exception as exc:
            self.csv_note.configure(text=f"Could not fit parametric fields: {exc}")
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
            fill = self.csv_fill.get()
            fill_bgr = None if fill == "vacuum" else self.palette.bgr(fill)
            render_trace_csv(self.csv_path, out_path, npp, fill_bgr=fill_bgr)
        else:
            layers, dims = build_profile(self._params(), self.palette, npp)
            rnd.render_layers(layers, dims, out_path)

    def _update_legend(self):
        for w in self.legend.winfo_children():
            w.destroy()
        if self.mode == "CSV trace":
            items = [("Fill", self.csv_fill.get())]
        else:
            items = [("Surround", self.opt["surround_material"].get()),
                     ("Feature", self.opt["feature_material"].get()),
                     ("Mask", self.opt["mask_material"].get())]
        for label, mat in items:
            chip = ctk.CTkFrame(self.legend, fg_color="transparent")
            chip.pack(side="left", padx=(0, 14))
            sw = ctk.CTkFrame(chip, width=14, height=14, corner_radius=3,
                              fg_color=self.palette.hex(mat), border_width=1,
                              border_color=NAVY_700)
            sw.pack(side="left", padx=(0, 5)); sw.pack_propagate(False)
            ctk.CTkLabel(chip, text=f"{label}: {mat}", font=self.eyebrow,
                         text_color=ON_DARK_SOFT).pack(side="left")

    def _schedule_render(self, _evt=None):
        """Debounced live re-render (used by keystroke bindings)."""
        if getattr(self, "_render_job", None):
            self.after_cancel(self._render_job)
        self._render_job = self.after(120, self.render_preview)

    def render_preview(self):
        self._render_job = None
        try:
            tmp = Path(tempfile.gettempdir()) / "_ipu_preview.bmp"
            self._render_to(tmp)
            disp = compose_preview(tmp, self._scale(), target_h=470)
            self.preview.configure(image=ctk.CTkImage(light_image=disp, dark_image=disp,
                                                      size=disp.size), text="")
            self._update_legend()
        except Exception as exc:
            self.preview.configure(image=None, text=f"⚠ {exc}", text_color=ON_DARK_MUTED)

    def save_bmp(self):
        out = Path(self.out_entry.get().strip() or "outputs/profile.bmp")
        out.parent.mkdir(parents=True, exist_ok=True)
        self._render_to(out)
        self.title(f"Incoming Profile Utility — saved {out.name}")


def launch() -> None:
    ProfileStudio().mainloop()

"""Incoming Profile Utility — GUI (customtkinter), SandBox brand theme."""
from __future__ import annotations

import math
import tempfile
import tkinter as tk
from pathlib import Path

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont

from .materials import load_palette
from .io_csv import load_trace
from . import process as proc

NAVY="#0E1B2E"; NAVY_900="#0B1626"; NAVY_800="#132540"; NAVY_700="#1C2C46"
BLUE="#283D5D"; BLUE_L="#6E90C6"; GREEN="#4FD093"; GREEN_D="#0E7A49"; GREEN_INK="#07271A"
ON="#FFFFFF"; SOFT="#AEB9C8"; MUT="#8B99AC"

FIELDS = [
    ("pitch","Pitch (nm)","120","Width of one repeating unit cell = line + opening."),
    ("space","Space · opening (nm)","50","Width of the centered opening. line width = pitch − space."),
    ("opening_depth","Opening depth (nm)","","How far down the opening is cut, measured from the top of the TOPMOST MATERIAL (row ① in the stack) — NOT from the top of the image. The top-vacuum headroom above the stack does not count. Blank = cut all the way through every material."),
    ("opening_bottom_radius","Opening bottom round (nm)","","Round the BOTTOM of the opening into a U. 0 = flat; ≈ half the Space = full semicircle."),
    ("top_vacuum","Top vacuum (nm)","20","Empty headroom drawn ABOVE the topmost material (room to deposit on top). This sits above the stack and does not affect Opening depth."),
]
OP_LABELS = ["Deposit · conformal","Deposit · planar","Fill","Etch · isotropic","Etch · anisotropic","Planarize"]
OP_PRESETS = {"deposit":("Deposit · conformal","oxide",8),"fill":("Fill","tungsten",0),
              "etch":("Etch · anisotropic","(any)",5),"planarize":("Planarize","oxide",240)}
OP_INFO = ("Deposit · conformal: uniform film of the set thickness on all exposed surfaces.\n"
           "Deposit · planar: flat slab of the set thickness on top.\n"
           "Fill: gap-fills the opening flush with the surface. The number is OVERFILL — extra\n"
           "  nm of blanket material above the surface (0 = flush). Deposit/Fill can use ANY\n"
           "  material in the palette; you don't need to add it to the stack first.\n"
           "Etch: removes to the set depth. Pick a material to etch just that one (stops on "
           "others), or (any) to etch everything exposed. Anisotropy 1 = vertical, 0 = isotropic undercut.\n"
           "Planarize: cut everything above the given height (CMP).")


def _op_to_row(op):
    o=op.get("op")
    if o=="conformal_deposit": return ("Deposit · conformal", op.get("material","oxide"), op.get("thickness",0), 1.0)
    if o=="planar_deposit":    return ("Deposit · planar", op.get("material","oxide"), op.get("thickness",0), 1.0)
    if o=="fill":              return ("Fill", op.get("material","tungsten"), op.get("overfill",0), 1.0)
    if o=="etch":
        a=op.get("anisotropy",1.0); mat=op.get("material") or "(any)"
        return (("Etch · isotropic" if a<=0 else "Etch · anisotropic"), mat, op.get("depth",0), a)
    if o=="planarize":         return ("Planarize", "oxide", op.get("at_height",0), 1.0)
    return ("Deposit · conformal","oxide",0,1.0)


def _nice_step(extent):
    if extent<=0: return 10.0
    raw=extent/5.0; mag=10**math.floor(math.log10(raw))
    for m in (1,2,5,10):
        if raw<=m*mag: return m*mag
    return 10*mag

def compose_preview(bmp_path, nm_per_px, box_w=760, box_h=460, origin=(0.0,0.0), return_scale=False):
    """Render the profile into a FIXED-size plot box (box_w x box_h). The profile is scaled
    to fit inside the data area preserving aspect (letterboxed, centered) so the grid panel
    keeps a constant size as the profile changes — only the axis labels update. Returns the
    composed image and, optionally, the fit scale (composed px per profile px).
    bmp_path may be a path or an already-open PIL image (avoids a disk round-trip)."""
    img=bmp_path if isinstance(bmp_path,Image.Image) else Image.open(bmp_path)
    img=img.convert("RGB"); w,h=img.size
    ML,MB,MT,MR=48,30,12,14
    box_w=max(ML+MR+80,int(box_w)); box_h=max(MT+MB+80,int(box_h))
    data_w=box_w-ML-MR; data_h=box_h-MT-MB
    fit=min(data_w/w, data_h/h, 6.0)                  # letterbox, preserve aspect, don't over-zoom
    pw2,ph2=max(1,int(w*fit)),max(1,int(h*fit))
    prof=img.resize((pw2,ph2), Image.NEAREST)
    px=ML+(data_w-pw2)//2; py=MT+(data_h-ph2)//2      # centre the profile in the fixed data area
    canvas=Image.new("RGB",(box_w,box_h),(11,22,38)); canvas.paste(prof,(px,py))
    ov=Image.new("RGBA",canvas.size,(0,0,0,0)); d=ImageDraw.Draw(ov); font=ImageFont.load_default()
    ppn=fit/nm_per_px; wnm,hnm=w*nm_per_px,h*nm_per_px; sx,sy=_nice_step(wnm),_nice_step(hnm)
    x0,y0=origin
    grid=(110,144,198,70); tick=(110,144,198,255); frame=(70,96,140,255)
    d.rectangle([ML,MT,ML+data_w,MT+data_h],outline=frame,width=1)   # stable plot frame
    nx=math.ceil(x0/sx)*sx
    while nx<=x0+wnm+1e-6:
        xx=px+(nx-x0)*ppn
        if ML<=xx<=ML+data_w:
            d.line([(xx,MT),(xx,MT+data_h)],fill=grid); d.text((xx-5,MT+data_h+5),f"{int(round(nx))}",fill=tick,font=font)
        nx+=sx
    ny=math.ceil(y0/sy)*sy
    while ny<=y0+hnm+1e-6:
        yy=py+ph2-(ny-y0)*ppn
        if MT<=yy<=MT+data_h:
            d.line([(ML,yy),(ML+data_w,yy)],fill=grid); d.text((6,yy-4),f"{int(round(ny))}",fill=tick,font=font)
        ny+=sy
    d.text((ML,MT+data_h+16),"width nm  /  height nm ↑",fill=tick,font=font)
    out=Image.alpha_composite(canvas.convert("RGBA"),ov).convert("RGB")
    return (out, fit) if return_scale else out


class Tooltip:
    _active=None
    def __init__(self,widget,text):
        self.w=widget; self.t=text; self.tip=None; self._show_job=None; self._hide_job=None
        widget.bind("<Enter>", self._enter, add="+"); widget.bind("<Leave>", self._leave, add="+")
        widget.bind("<Button-1>", self._leave, add="+"); widget.bind("<Destroy>", self._leave, add="+")
    def _enter(self,_=None):
        self._cancel(); self._show_job=self.w.after(300, self._show)
    def _show(self):
        if self.tip or not self.t: return
        if Tooltip._active is not None:
            try: Tooltip._active.destroy()
            except Exception: pass
            Tooltip._active=None
        x=self.w.winfo_rootx()+20; y=self.w.winfo_rooty()+22
        self.tip=tk.Toplevel(self.w); self.tip.wm_overrideredirect(True); self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip,text=self.t,justify="left",wraplength=260,bg=NAVY_700,fg=ON,font=("",9),padx=8,pady=6,bd=0).pack()
        Tooltip._active=self.tip; self._hide_job=self.w.after(6000,self._leave)
    def _cancel(self):
        for j in (self._show_job,self._hide_job):
            if j:
                try: self.w.after_cancel(j)
                except Exception: pass
        self._show_job=self._hide_job=None
    def _leave(self,_=None):
        self._cancel()
        if self.tip:
            try: self.tip.destroy()
            except Exception: pass
            if Tooltip._active is self.tip: Tooltip._active=None
            self.tip=None


class MaterialLayerRow:
    def __init__(self, app, material, thickness, shape=None):
        self.app=app; self.shape=list(shape) if shape else []
        self.frame=ctk.CTkFrame(app.matstack_container, fg_color=NAVY_900, corner_radius=8, border_width=1, border_color=NAVY_700)
        self.grip=ctk.CTkLabel(self.frame, text="⠿", font=app.ub, text_color=MUT, cursor="fleur", width=16)
        self.grip.pack(side="left", padx=(8,2))
        self.grip.bind("<ButtonPress-1>", lambda e: app._drag_start(self))
        self.grip.bind("<ButtonRelease-1>", lambda e: app._drag_drop(self))
        self.badge=ctk.CTkFrame(self.frame, fg_color=BLUE, corner_radius=999, width=20, height=20); self.badge.pack(side="left", padx=(2,6), pady=7); self.badge.pack_propagate(False)
        self.badge_lbl=ctk.CTkLabel(self.badge, text="1", font=app.eb, text_color=ON); self.badge_lbl.pack(expand=True)
        self.sw=ctk.CTkFrame(self.frame, width=16, height=16, corner_radius=3, fg_color=app.palette.hex(material), border_width=1, border_color=NAVY_700)
        self.sw.pack(side="left", padx=(0,6)); self.sw.pack_propagate(False)
        self.mat=ctk.CTkOptionMenu(self.frame, values=app.palette.names(), width=132, font=app.uf, fg_color=NAVY_800,
                     button_color=BLUE, button_hover_color=BLUE_L, text_color=ON, command=self._on_mat)
        self.mat.set(material); self.mat.pack(side="left", padx=(0,6), pady=7)
        self.th=ctk.CTkEntry(self.frame, width=50, font=app.mono, fg_color=NAVY_800, border_color=NAVY_700, text_color=ON)
        self.th.insert(0,str(thickness)); self.th.bind("<KeyRelease>", app._schedule_render); self.th.pack(side="left", padx=(0,2))
        ctk.CTkLabel(self.frame, text="nm", font=app.eb, text_color=MUT).pack(side="left")
        for sym,cmd in (("✕",lambda:app._remove_matlayer(self)),("↓",lambda:app._move_matlayer(self,1)),("↑",lambda:app._move_matlayer(self,-1))):
            ctk.CTkButton(self.frame, text=sym, width=24, font=app.uf, fg_color="transparent", border_width=1,
                          border_color=NAVY_700, text_color=SOFT, hover_color=NAVY_700, command=cmd).pack(side="right", padx=1)
        self.shape_btn=ctk.CTkButton(self.frame, text="◐ shape", width=64, font=app.eb, fg_color="transparent", border_width=1,
                     border_color=BLUE_L, text_color=SOFT, hover_color=NAVY_700, command=lambda: app._edit_shape(self))
        self.shape_btn.pack(side="right", padx=(4,2)); self._refresh_shape_btn()
        Tooltip(self.shape_btn, "Shape this layer's opening. Add one or MORE treatments (they stack): round / "
                                "chamfer / facet the top corners, and/or taper the sidewall (taper angle = "
                                "sidewall angle from the horizontal base, 90° = vertical).")
    def _refresh_shape_btn(self):
        self.shape_btn.configure(text=f"◐ shape ({len(self.shape)})" if self.shape else "◐ shape",
                                 text_color=(GREEN if self.shape else SOFT))
    def _on_mat(self,_v):
        self.sw.configure(fg_color=self.app.palette.hex(self.mat.get())); self.app._refresh_op_materials(); self.app.render_preview()
    def to_layer(self):
        try: t=float(self.th.get())
        except ValueError: t=0.0
        d=dict(material=self.mat.get(), thickness=t)
        if self.shape: d["shape"]=self.shape
        return d


class OpRow:
    NEEDS_MAT = ("Deposit · conformal", "Deposit · planar", "Fill")
    def __init__(self, host, op_label, material, num, aniso=1.0):
        self.host=host; app=host.app
        self.frame=ctk.CTkFrame(host.container, fg_color=NAVY_900, corner_radius=8, border_width=1, border_color=NAVY_700)
        for sym,cmd in (("✕",lambda:host.remove(self)),("↓",lambda:host.move(self,1)),("↑",lambda:host.move(self,-1))):
            ctk.CTkButton(self.frame, text=sym, width=24, font=app.uf, fg_color="transparent", border_width=1,
                          border_color=NAVY_700, text_color=SOFT, hover_color=NAVY_700, command=cmd).pack(side="right", padx=1)
        self.badge=ctk.CTkFrame(self.frame, fg_color=BLUE, corner_radius=999, width=20, height=20); self.badge.pack(side="left", padx=(10,6), pady=8); self.badge.pack_propagate(False)
        self.badge_lbl=ctk.CTkLabel(self.badge, text="1", font=app.eb, text_color=ON); self.badge_lbl.pack(expand=True)
        info=ctk.CTkLabel(self.frame, text="ⓘ", font=app.uf, text_color=BLUE_L, cursor="hand2"); info.pack(side="left", padx=(0,4)); Tooltip(info, OP_INFO)
        self.optype=ctk.CTkOptionMenu(self.frame, values=OP_LABELS, width=142, font=app.uf, fg_color=NAVY_800,
                     button_color=BLUE, button_hover_color=BLUE_L, text_color=ON, command=self._on_type)
        self.optype.set(op_label); self.optype.pack(side="left", padx=4, pady=8)
        self.mat=ctk.CTkOptionMenu(self.frame, values=app.palette.names(), width=100, font=app.uf, fg_color=NAVY_800,
                     button_color=BLUE, button_hover_color=BLUE_L, text_color=ON, command=lambda _v: app._schedule_render())
        self.mat.set(material); self.mat.pack(side="left", padx=2, pady=8)
        self.num=ctk.CTkEntry(self.frame, width=44, font=app.mono, fg_color=NAVY_800, border_color=NAVY_700, text_color=ON)
        self.num.insert(0,str(num)); self.num.bind("<KeyRelease>", app._schedule_render); self.num.pack(side="left", padx=(6,2))
        ctk.CTkLabel(self.frame, text="nm", font=app.eb, text_color=MUT).pack(side="left")
        self.aniso_lbl=ctk.CTkLabel(self.frame, text="aniso", font=app.eb, text_color=MUT)
        self.aniso=ctk.CTkEntry(self.frame, width=40, font=app.mono, fg_color=NAVY_800, border_color=NAVY_700, text_color=ON)
        self.aniso.insert(0,str(aniso)); self.aniso.bind("<KeyRelease>", app._schedule_render)
        self._sync()
    def _on_type(self,_v): self._sync(); self.host.app._schedule_render()
    def _sync(self):
        lbl=self.optype.get(); names=self.host.app._op_material_choices()
        if lbl=="Planarize":
            self.mat.pack_forget()
        else:
            self.mat.pack(side="left", padx=2, pady=8, before=self.num)
            if lbl in ("Etch · isotropic","Etch · anisotropic"):
                vals=["(any)"]+names   # etch acts on materials already present
                self.mat.configure(state="normal", values=vals)
                if self.mat.get() not in vals: self.mat.set("(any)")
            else:                       # Deposit / Fill introduce NEW material -> whole palette
                vals=self.host.app.palette.names()
                self.mat.configure(state="normal", values=vals)
                if self.mat.get() not in vals and vals: self.mat.set(vals[0])
        if lbl=="Etch · anisotropic": self.aniso_lbl.pack(side="left",padx=(6,1)); self.aniso.pack(side="left")
        else: self.aniso_lbl.pack_forget(); self.aniso.pack_forget()
    def to_op(self):
        lbl=self.optype.get(); mat=self.mat.get()
        try: n=float(self.num.get())
        except ValueError: n=0.0
        tgt=None if mat=="(any)" else mat
        if lbl=="Deposit · conformal": return dict(op="conformal_deposit", material=mat, thickness=n)
        if lbl=="Deposit · planar":    return dict(op="planar_deposit", material=mat, thickness=n)
        if lbl=="Fill":                return dict(op="fill", material=mat, overfill=n)
        if lbl=="Etch · isotropic":    return dict(op="etch", depth=n, anisotropy=0.0, material=tgt)
        if lbl=="Etch · anisotropic":
            try: a=float(self.aniso.get())
            except ValueError: a=1.0
            return dict(op="etch", depth=n, anisotropy=a, material=tgt)
        if lbl=="Planarize":           return dict(op="planarize", at_height=n)
        return dict(op="conformal_deposit", material=mat, thickness=n)


class RepeatRow:
    def __init__(self, host):
        self.host=host; app=host.app
        self.frame=ctk.CTkFrame(host.container, fg_color=NAVY_800, corner_radius=8, border_width=1, border_color=GREEN_D)
        head=ctk.CTkFrame(self.frame, fg_color="transparent"); head.pack(fill="x", padx=8, pady=(8,2))
        self.badge=ctk.CTkFrame(head, fg_color=GREEN_D, corner_radius=999, width=20, height=20); self.badge.pack(side="left", padx=(2,8)); self.badge.pack_propagate(False)
        self.badge_lbl=ctk.CTkLabel(self.badge, text="1", font=app.eb, text_color=ON); self.badge_lbl.pack(expand=True)
        ctk.CTkLabel(head, text="⟳ Repeat ×", font=app.ub, text_color=GREEN).pack(side="left")
        self.times=ctk.CTkEntry(head, width=44, font=app.mono, fg_color=NAVY_900, border_color=NAVY_700, text_color=ON)
        self.times.insert(0,"10"); self.times.bind("<KeyRelease>", app._schedule_render); self.times.pack(side="left", padx=6)
        for sym,cmd in (("✕",lambda:host.remove(self)),("↓",lambda:host.move(self,1)),("↑",lambda:host.move(self,-1))):
            ctk.CTkButton(head, text=sym, width=24, font=app.uf, fg_color="transparent", border_width=1,
                          border_color=NAVY_700, text_color=SOFT, hover_color=NAVY_700, command=cmd).pack(side="right", padx=1)
        addbar=ctk.CTkFrame(self.frame, fg_color="transparent"); addbar.pack(fill="x", padx=8, pady=(0,2))
        for text,kind in [("＋ Deposit","deposit"),("＋ Fill","fill"),("＋ Etch","etch"),("＋ Planarize","planarize")]:
            ctk.CTkButton(addbar,text=text,command=lambda k=kind:self.sub.add_op(k),font=ctk.CTkFont(size=11),fg_color=NAVY_900,
                          border_width=1,border_color=BLUE_L,text_color=ON,hover_color=NAVY_700,width=10,height=24).pack(side="left",expand=True,fill="x",padx=2)
        self.subcont=ctk.CTkFrame(self.frame, fg_color="transparent"); self.subcont.pack(fill="x", padx=(14,6), pady=(2,8))
        self.sub=OpList(app, self.subcont)
    def to_op(self):
        try: n=int(float(self.times.get()))
        except ValueError: n=1
        return dict(op="repeat", times=max(1,n), steps=self.sub.to_ops())


class OpList:
    def __init__(self, app, container, empty_hint=None):
        self.app=app; self.container=container; self.rows=[]; self.empty_hint=empty_hint
    def add_op(self, kind="deposit"):
        self.app._capture(); lbl,mat,num=OP_PRESETS.get(kind,OP_PRESETS["deposit"])
        self.rows.append(OpRow(self,lbl,mat,num)); self.relayout(); self.app.render_preview()
    def add_repeat(self):
        self.app._capture(); r=RepeatRow(self); self.rows.append(r); r.sub.add_op("deposit"); self.relayout(); self.app.render_preview()
    def remove(self,row):
        self.app._capture(); row.frame.destroy(); self.rows.remove(row); self.relayout(); self.app.render_preview()
    def move(self,row,delta):
        i=self.rows.index(row); j=i+delta
        if 0<=j<len(self.rows):
            self.app._capture(); self.rows[i],self.rows[j]=self.rows[j],self.rows[i]; self.relayout(); self.app.render_preview()
    def relayout(self):
        for n,row in enumerate(self.rows,1):
            row.frame.pack_forget(); row.frame.pack(fill="x",padx=6,pady=4); row.badge_lbl.configure(text=str(n))
        if self.empty_hint is not None:
            self.empty_hint.pack_forget()
            if not self.rows: self.empty_hint.pack(anchor="w",padx=6)
    def clear(self):
        for r in list(self.rows): r.frame.destroy()
        self.rows=[]; self.relayout()
    def to_ops(self): return [r.to_op() for r in self.rows]


class ProfileStudio(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark"); self.configure(fg_color=NAVY)
        self.title("Incoming Profile Utility"); self.geometry("1360x900")
        self._set_app_icon()
        self.palette=load_palette(); self.opening_trace=None
        self.material_menus=[]; self.matlayer_rows=[]; self._last_state=None
        self._undo=[]; self._redo=[]; self._loading=False; self._drag=None; self._last_npp=0.4; self.smooth_level=ctk.StringVar(value="Off")
        self._zoom=1.0; self._cx=0.5; self._cy=0.5; self._pv=None; self._pan=None   # zoom/pan view state
        self._tool="move"; self._measure=False; self._prof_wh=None; self._hint_job=None
        self._full_img=None; self._pan_rendering=False; self._pan_pending=False
        self.uf=ctk.CTkFont(family="Inter",size=13); self.ub=ctk.CTkFont(family="Inter",size=14,weight="bold")
        self.tf=ctk.CTkFont(family="Inter",size=20,weight="bold"); self.mono=ctk.CTkFont(family="JetBrains Mono",size=12)
        self.eb=ctk.CTkFont(family="JetBrains Mono",size=11)
        self.hf=ctk.CTkFont(family="Inter",size=22,weight="bold")   # header title
        self.grid_columnconfigure(0,weight=1); self.grid_rowconfigure(2,weight=1)
        self._header(); self._toolbar(); self._body(); self._footer()
        self.after(60, self._fit_to_screen)
        self.bind_class("Entry","<FocusIn>", lambda e: self._capture())   # one undo step per field edit
        self.after(160, self.render_preview)

    def _row(self,parent,r,label,info,widget):
        ctk.CTkLabel(parent,text=label,font=self.uf,text_color=SOFT).grid(row=r,column=0,sticky="w",padx=(8,6),pady=5)
        ic=ctk.CTkLabel(parent,text="ⓘ",font=self.uf,text_color=BLUE_L,cursor="hand2"); ic.grid(row=r,column=1,sticky="w",padx=(0,8)); Tooltip(ic,info)
        widget.grid(row=r,column=2,sticky="ew",padx=(0,8),pady=5)

    def _header(self):
        h=ctk.CTkFrame(self,fg_color=NAVY_900,corner_radius=0,height=54); h.grid(row=0,column=0,sticky="ew"); h.grid_propagate(False); h.grid_columnconfigure(0,weight=1)
        b=ctk.CTkFrame(h,fg_color="transparent"); b.grid(row=0,column=0,sticky="w",padx=22,pady=10)
        ctk.CTkLabel(b,text="SANDBOX · PROFILE STUDIO",font=self.hf,text_color=ON).pack(anchor="w")
        pill=ctk.CTkFrame(h,fg_color=GREEN,corner_radius=999); pill.grid(row=0,column=1,sticky="e",padx=22)
        ctk.CTkLabel(pill,text="v1",font=self.mono,text_color=GREEN_INK).pack(padx=12,pady=3)

    def _card(self,parent,title):
        c=ctk.CTkFrame(parent,fg_color=NAVY_800,corner_radius=12,border_width=1,border_color=NAVY_700)
        ctk.CTkLabel(c,text=title,font=self.ub,text_color=ON).pack(anchor="w",padx=18,pady=(14,6)); return c

    def _mat_menu(self,parent,default,width=150):
        m=ctk.CTkOptionMenu(parent,values=self.palette.names(),font=self.uf,fg_color=NAVY_900,button_color=BLUE,
                            button_hover_color=BLUE_L,text_color=ON,width=width,command=lambda _v:self.render_preview())
        m.set(default); self.material_menus.append(m); return m

    def _toolbar(self):
        tb=ctk.CTkFrame(self,fg_color=NAVY_800,corner_radius=0,height=36); tb.grid(row=1,column=0,sticky="ew")
        tb.pack_propagate(False)                       # children are packed; keep the strip slim
        inner=ctk.CTkFrame(tb,fg_color="transparent"); inner.pack(side="left",padx=10,pady=4)
        def tbtn(text,cmd,tip,accent=False,w=48):
            btn=ctk.CTkButton(inner,text=text,command=cmd,font=self.uf,width=w,height=26,corner_radius=5,
                fg_color=(GREEN if accent else "transparent"),text_color=(GREEN_INK if accent else ON),
                border_width=0,hover_color=(GREEN_D if accent else NAVY_700))
            btn.pack(side="left",padx=1); Tooltip(btn,tip)
        def sep():
            ctk.CTkFrame(inner,width=1,height=20,fg_color=NAVY_700).pack(side="left",padx=6)
        tbtn("New",self._new_project,"Start a new, blank project")
        tbtn("Open",self._open_project,"Open a saved project (.json)")
        tbtn("Save",self._save_project,"Save the whole project — materials, base feature, process stack — to a .json file",accent=True)
        sep()
        tbtn("↶ Undo",self._undo_action,"Undo the last change",w=68)
        tbtn("↷ Redo",self._redo_action,"Redo",w=66)
        sep()
        tbtn("↺ Reset",self._reset,"Reset everything to a blank canvas",w=70)

    def _set_app_icon(self):
        """Title-bar / taskbar icon. Works from source and from the frozen .exe."""
        from .materials import _base_dir
        assets=_base_dir()/"assets"
        try:                                   # Windows: .ico gives the crisp taskbar icon
            ico=assets/"icon.ico"
            if ico.exists(): self.iconbitmap(default=str(ico))
        except Exception: pass
        try:                                   # cross-platform fallback / Linux
            png=assets/"icon.png"
            if png.exists():
                from PIL import ImageTk
                self._icon_img=ImageTk.PhotoImage(Image.open(png))
                self.iconphoto(True, self._icon_img)
        except Exception: pass

    def _fit_to_screen(self):
        """Keep the window within the physical screen at ANY Windows display scaling,
        so no panel (e.g. the process stack) ends up off-screen."""
        try:
            sw=self.winfo_screenwidth(); sh=self.winfo_screenheight()
            try: wsf=ctk.ScalingTracker.get_window_scaling(self)
            except Exception: wsf=1.0
            max_w=int(sw/wsf)-40; max_h=int(sh/wsf)-90
            w=min(1360,max_w); h=min(900,max_h)
            self.geometry(f"{w}x{h}")
            self.minsize(min(900,w), min(560,h))
        except Exception:
            pass

    def _body(self):
        body=ctk.CTkFrame(self,fg_color="transparent"); body.grid(row=2,column=0,sticky="nsew",padx=18,pady=16)
        body.grid_columnconfigure(0,weight=0,minsize=580); body.grid_columnconfigure(1,weight=1); body.grid_rowconfigure(0,weight=1)
        self._inputs(body); self._preview_card(body)

    def _inputs(self,parent):
        card=self._card(parent,"Inputs"); card.grid(row=0,column=0,sticky="nsew",padx=(0,12))
        self.param_page=ctk.CTkScrollableFrame(card,fg_color="transparent",height=440)
        self.param_page.pack(fill="both",expand=True,padx=10)
        self.entries={}

        matf=ctk.CTkFrame(self.param_page,fg_color="transparent"); matf.pack(fill="x",pady=(0,6))
        ctk.CTkLabel(matf,text="MATERIAL STACK  (row ① = top)",font=self.eb,text_color=BLUE_L).pack(anchor="w",padx=6)
        ctk.CTkLabel(matf,text="The incoming film stack, top → bottom. Each layer is a material + thickness (nm). Drag ⠿ to reorder; use ◐ shape for rounded corners or a tapered sidewall.",
                     font=ctk.CTkFont(size=11),text_color=MUT,wraplength=520,justify="left").pack(anchor="w",padx=6,pady=(0,4))
        self.matstack_container=ctk.CTkFrame(matf,fg_color="transparent"); self.matstack_container.pack(fill="x")
        self.matstack_hint=ctk.CTkLabel(matf,text="No layers yet — add one to start the stack.",font=ctk.CTkFont(size=11),text_color=MUT); self.matstack_hint.pack(anchor="w",padx=6)
        addrow=ctk.CTkFrame(matf,fg_color="transparent"); addrow.pack(fill="x",padx=4,pady=(4,0))
        ctk.CTkButton(addrow,text="＋ Add material layer",command=lambda:self._add_matlayer(),font=self.uf,fg_color=NAVY_900,
                      border_width=1,border_color=BLUE_L,text_color=ON,hover_color=NAVY_700).pack(side="left",expand=True,fill="x",padx=2)
        ctk.CTkButton(addrow,text="＋ New material (color)",command=self._add_material,font=self.uf,fg_color="transparent",
                      border_width=1,border_color=NAVY_700,text_color=SOFT,hover_color=NAVY_700).pack(side="left",expand=True,fill="x",padx=2)

        # CSV lives with the stack — it defines the whole opening profile (overrides Space).
        csvf=ctk.CTkFrame(self.param_page,fg_color="transparent"); csvf.pack(fill="x",pady=(8,2)); csvf.grid_columnconfigure(2,weight=1)
        ctk.CTkLabel(csvf,text="OPENING FROM CSV  (optional — defines the profile, overrides Space)",font=self.eb,text_color=BLUE_L).grid(row=0,column=0,columnspan=3,sticky="w",padx=6,pady=(2,2))
        ocsv=ctk.CTkFrame(csvf,fg_color="transparent"); ocsv.grid(row=1,column=0,columnspan=3,sticky="ew",padx=6)
        ctk.CTkButton(ocsv,text="Load CSV…",command=self._load_csv,font=self.uf,fg_color=NAVY_900,border_width=1,
                      border_color=BLUE_L,text_color=ON,hover_color=NAVY_700).pack(side="left",expand=True,fill="x",padx=2)
        ctk.CTkButton(ocsv,text="Clear",command=self._clear_csv,font=self.uf,fg_color="transparent",border_width=1,
                      border_color=NAVY_700,text_color=SOFT,hover_color=NAVY_700,width=70).pack(side="left",padx=2)
        self.csv_label=ctk.CTkLabel(csvf,text="No CSV loaded — the opening is rectangular (from Space below).",
                                    font=self.eb,text_color=MUT,wraplength=520,justify="left")
        self.csv_label.grid(row=2,column=0,columnspan=3,sticky="w",padx=8,pady=(2,2))
        self.csv_ref_entry=ctk.CTkEntry(csvf,font=self.mono,fg_color=NAVY_900,border_color=NAVY_700,text_color=ON,width=120,placeholder_text="top")
        self.csv_ref_entry.bind("<KeyRelease>",self._schedule_render)
        self._row(csvf,3,"CSV height=0 at (nm)",
                  "Where the CSV's height=0 line sits, measured in nm from the stack bottom. Blank = top-align (trace top at the stack top). Points with negative height sit below this line.",
                  self.csv_ref_entry)

        bs=ctk.CTkFrame(self.param_page,fg_color="transparent"); bs.pack(fill="x",pady=(8,4)); bs.grid_columnconfigure(2,weight=1)
        ctk.CTkLabel(bs,text="BASE FEATURE",font=self.eb,text_color=BLUE_L).grid(row=0,column=0,columnspan=3,sticky="w",padx=8,pady=(4,2))
        for i,(k,label,default,info) in enumerate(FIELDS,1):
            e=ctk.CTkEntry(bs,font=self.mono,fg_color=NAVY_900,border_color=NAVY_700,text_color=ON,width=120)
            e.insert(0,default); e.bind("<KeyRelease>",self._schedule_render); self._row(bs,i,label,info,e); self.entries[k]=e

        ps=ctk.CTkFrame(self.param_page,fg_color="transparent"); ps.pack(fill="x",pady=(8,8))
        ctk.CTkLabel(ps,text="PROCESS STACK",font=self.eb,text_color=BLUE_L).pack(anchor="w",padx=6)
        ctk.CTkLabel(ps,text="Steps run in order: ① first, then ②, ③ … each acts on the result above it. A Repeat block runs its steps ×N.",
                     font=ctk.CTkFont(size=11),text_color=MUT,wraplength=520,justify="left").pack(anchor="w",padx=6,pady=(0,6))
        addbar=ctk.CTkFrame(ps,fg_color="transparent"); addbar.pack(fill="x",padx=4)
        for text,kind in [("＋ Deposit","deposit"),("＋ Fill","fill"),("＋ Etch","etch"),("＋ Planarize","planarize")]:
            ctk.CTkButton(addbar,text=text,command=lambda k=kind:self.stack.add_op(k),font=self.uf,fg_color=NAVY_900,
                          border_width=1,border_color=BLUE_L,text_color=ON,hover_color=NAVY_700,width=10).pack(side="left",expand=True,fill="x",padx=2)
        ctk.CTkButton(ps,text="⟳ Add Repeat block  (multilayer / superlattice)",command=lambda:self.stack.add_repeat(),
                      font=self.uf,fg_color=NAVY_900,border_width=1,border_color=GREEN,text_color=GREEN,hover_color=NAVY_700).pack(fill="x",padx=4,pady=(4,0))
        self.op_container=ctk.CTkFrame(ps,fg_color="transparent"); self.op_container.pack(fill="x",pady=4)
        self.empty_hint=ctk.CTkLabel(ps,text="No steps yet.",font=ctk.CTkFont(size=11),text_color=MUT)
        self.stack=OpList(self, self.op_container, empty_hint=self.empty_hint); self.empty_hint.pack(anchor="w",padx=6)

        common=ctk.CTkFrame(card,fg_color="transparent"); common.pack(fill="x",padx=10,pady=(2,8)); common.grid_columnconfigure(2,weight=1)
        self.scale_entry=ctk.CTkEntry(common,font=self.mono,fg_color=NAVY_900,border_color=NAVY_700,text_color=ON,width=120,placeholder_text="auto")
        self.scale_entry.bind("<KeyRelease>",self._schedule_render)
        self._row(common,0,"Resolution (nm/px)","Blank = auto-fit (~1000 px tall). Set a value to fix the nm-per-pixel calibration (smaller = higher resolution / bigger image).",self.scale_entry)

    def _preview_card(self,parent):
        card=self._card(parent,"Preview"); card.grid(row=0,column=1,sticky="nsew")
        bottom=ctk.CTkFrame(card,fg_color="transparent"); bottom.pack(side="bottom",fill="x")   # controls stay visible
        fr=ctk.CTkFrame(card,fg_color=NAVY_900,corner_radius=10); fr.pack(side="top",expand=True,fill="both",padx=18,pady=6)
        self.preview=ctk.CTkLabel(fr,text="",fg_color=NAVY_900); self.preview.pack(expand=True,fill="both",padx=10,pady=10)
        self._pv_target=getattr(self.preview,"_label",self.preview)   # inner widget that shows the image
        for ev,cb in (("<ButtonPress-1>",self._pan_start),("<B1-Motion>",self._pan_move),
                      ("<ButtonRelease-1>",self._pan_release),
                      ("<Double-Button-1>",lambda e:self._reset_zoom()),
                      ("<MouseWheel>",self._wheel_zoom),("<Button-4>",self._wheel_zoom),("<Button-5>",self._wheel_zoom)):
            self._pv_target.bind(ev,cb,add="+")
        for key,(dx,dy) in {"<Up>":(0,1),"<Down>":(0,-1),"<Left>":(-1,0),"<Right>":(1,0)}.items():
            self.bind(key, lambda e,dx=dx,dy=dy:self._nudge_pan(dx,dy), add="+")
        self.legend=ctk.CTkFrame(bottom,fg_color="transparent"); self.legend.pack(fill="x",padx=18,pady=(0,4))
        bar=ctk.CTkFrame(bottom,fg_color="transparent"); bar.pack(fill="x",padx=18,pady=(4,8)); bar.grid_columnconfigure(0,weight=1)
        sm=ctk.CTkFrame(bar,fg_color="transparent"); sm.grid(row=0,column=0,sticky="w")
        ctk.CTkLabel(sm,text="Smoothing",font=self.eb,text_color=SOFT).pack(side="left",padx=(0,6))
        ctk.CTkOptionMenu(sm,values=["Off","2×","4×","8×"],variable=self.smooth_level,command=lambda _v:self.render_preview(),
                          width=76,font=self.uf,fg_color=NAVY_900,button_color=BLUE,button_hover_color=BLUE_L,text_color=ON).pack(side="left")
        self.preview_note=ctk.CTkLabel(bar,text="preview updates as you edit",font=self.eb,text_color=MUT); self.preview_note.grid(row=0,column=1,padx=(0,10))
        poly_btn=ctk.CTkButton(bar,text="⬡ Polygons…",command=self.export_polygons,font=self.uf,width=104,fg_color="transparent",
                      border_width=1,border_color=BLUE_L,text_color=ON,hover_color=NAVY_700); poly_btn.grid(row=0,column=2,padx=(0,6))
        Tooltip(poly_btn,"Export the built profile as editable polygons: an SVG (open in Inkscape/Illustrator to nudge vertices) plus a JSON of exact nm coordinates.")
        ctk.CTkButton(bar,text="Save .bmp…",command=self.save_bmp,font=self.ub,width=110,fg_color=GREEN,hover_color=GREEN_D,text_color=GREEN_INK).grid(row=0,column=3)
        # zoom bar (row 1): drag the preview to pan, scroll to zoom, double-click to reset
        zb=ctk.CTkFrame(bar,fg_color="transparent"); zb.grid(row=1,column=0,columnspan=3,sticky="ew",pady=(6,2)); zb.grid_columnconfigure(1,weight=1)
        ctk.CTkLabel(zb,text="Zoom",font=self.eb,text_color=SOFT).grid(row=0,column=0,padx=(0,8))
        self.zoom_var=ctk.DoubleVar(value=1.0)
        self.zoom_slider=ctk.CTkSlider(zb,from_=1.0,to=8.0,number_of_steps=70,variable=self.zoom_var,
                                       command=self._on_zoom_slider,button_color=BLUE,button_hover_color=BLUE_L,progress_color=BLUE)
        self.zoom_slider.grid(row=0,column=1,sticky="ew",padx=6)
        ctk.CTkButton(zb,text="Reset",command=self._reset_zoom,font=self.uf,width=60,fg_color="transparent",border_width=1,
                      border_color=NAVY_700,text_color=SOFT,hover_color=NAVY_700).grid(row=0,column=2,padx=(6,0))
        self.move_btn=ctk.CTkButton(zb,text="✥ Move",command=lambda:self._select_tool("move"),font=self.uf,width=84,
                      fg_color="transparent",border_width=1,border_color=BLUE_L,text_color=ON,hover_color=NAVY_700)
        self.move_btn.grid(row=0,column=3,padx=(6,0))
        Tooltip(self.move_btn,"Move: drag (or use the arrow keys) to pan around the preview when zoomed in.")
        self.measure_btn=ctk.CTkButton(zb,text="📏 Measure",command=lambda:self._select_tool("measure"),font=self.uf,width=96,fg_color="transparent",
                      border_width=1,border_color=BLUE_L,text_color=ON,hover_color=NAVY_700)
        self.measure_btn.grid(row=0,column=4,padx=(6,0))
        Tooltip(self.measure_btn,"Measure: drag a line on the preview to read its length in nm. Works at any zoom.")
        self.move_btn.configure(fg_color=GREEN,text_color=GREEN_INK,border_color=GREEN)   # Move active by default
        Tooltip(self.zoom_slider,"Zoom the preview. You can also scroll the wheel over the preview to zoom, drag to pan, and double-click to reset.")

    def _on_zoom_slider(self,_v=None):
        self._zoom=max(1.0,float(self.zoom_var.get()))
        if self._zoom<=1.0: self._cx=self._cy=0.5
        self._update_cursor(); self.render_preview()
    def _reset_zoom(self):
        self._zoom=1.0; self._cx=self._cy=0.5
        if hasattr(self,"zoom_var"): self.zoom_var.set(1.0)
        self._update_cursor(); self.render_preview()
    def _wheel_zoom(self,e):
        step=1.2 if getattr(e,"delta",0)>0 or getattr(e,"num",0)==4 else (1/1.2)
        self._zoom=min(8.0,max(1.0,self._zoom*step))
        if self._zoom<=1.0: self._cx=self._cy=0.5
        if hasattr(self,"zoom_var"): self.zoom_var.set(self._zoom)
        self._update_cursor(); self.render_preview()
    def _pan_start(self,e):
        if getattr(self,"_measure",False): return self._meas_start_cb(e)
        if self._zoom<=1.0:
            self._flash_hint("Zoom in to move — scroll over the preview or use the Zoom slider, then drag.")
            return
        self._pan=(e.x,e.y,self._cx,self._cy)
        try: self._pv_target.configure(cursor="fleur")
        except Exception: pass
    def _pan_release(self,e):
        if self._pan is not None:
            self._pan=None
            self._update_cursor()
            self.render_preview()          # one crisp, full-quality render after the drag
    def _flash_hint(self,msg):
        try:
            self.preview_note.configure(text=msg,text_color=BLUE_L)
            if getattr(self,"_hint_job",None): self.after_cancel(self._hint_job)
            self._hint_job=self.after(2400,self.render_preview)     # restore the normal note
        except Exception: pass
    def _pan_move(self,e):
        if getattr(self,"_measure",False): return self._meas_move_cb(e)
        if not self._pan or self._zoom<=1.0 or not self._pv: return
        x0,y0,cx0,cy0=self._pan; z=self._pv[2]
        pw2,ph2=getattr(self,"_prof_wh",(self._pv[0],self._pv[1]))   # profile's on-screen extent
        # drag content with the cursor: one full profile-width of drag == one view (1/z of image)
        self._cx=cx0-(e.x-x0)/max(1,pw2)/z
        self._cy=cy0+(e.y-y0)/max(1,ph2)/z
        self._request_pan_render()
    def _request_pan_render(self):
        """Coalesce rapid drag events: render at most one frame at a time so motion events
        can't queue up behind slow renders (that queue is what feels like lag)."""
        if getattr(self,"_pan_rendering",False):
            self._pan_pending=True; return
        self._pan_rendering=True; self._pan_pending=False
        try:
            self.render_preview(view_only=True)
        finally:
            self._pan_rendering=False
        if self._pan_pending:                       # coordinates moved on during the render
            self._pan_pending=False
            self.after_idle(self._request_pan_render)
    def _nudge_pan(self,dx,dy):
        """Arrow-key panning when zoomed (ignored while typing in a field)."""
        if self._zoom<=1.0: return
        import tkinter as _tk
        f=self.focus_get()
        if isinstance(f,(_tk.Entry,_tk.Text)): return          # don't hijack text editing
        self._cx+=dx*0.12/self._zoom; self._cy+=dy*0.12/self._zoom
        self.render_preview(view_only=True)

    # ---- measure tool: drag a line, read its length in nm ----
    def _select_tool(self, tool):
        """Mutually-exclusive preview tools: 'move' (pan) or 'measure'."""
        self._tool=tool
        self._measure=(tool=="measure")
        for btn,name in ((self.move_btn,"move"),(self.measure_btn,"measure")):
            active=(name==tool)
            btn.configure(fg_color=GREEN if active else "transparent",
                          text_color=GREEN_INK if active else ON, border_color=GREEN if active else BLUE_L)
        self._meas_start=None
        self._update_cursor()
        if tool!="measure": self.render_preview()      # clear any measure line
    def _update_cursor(self):
        """Show a move cursor over the grid so it's clear you can pan (when zoomed)."""
        if getattr(self,"_measure",False):
            cur="crosshair"
        elif getattr(self,"_zoom",1.0)>1.0:
            cur="fleur"                                 # 4-way move arrows
        else:
            cur=""
        for w in (getattr(self,"preview",None), getattr(self,"_pv_target",None)):
            try:
                if w is not None: w.configure(cursor=cur)
            except Exception: pass
    def _to_disp(self,e):
        pw,ph,_=self._pv
        try: s=ctk.ScalingTracker.get_widget_scaling(self)
        except Exception: s=1.0
        tgt=getattr(self,"_pv_target",self.preview)
        lw=tgt.winfo_width(); lh=tgt.winfo_height()            # inner label that holds the image
        dispw,disph=pw*s,ph*s                                  # CTkImage renders at size*scaling
        ox=max(0,(lw-dispw)/2); oy=max(0,(lh-disph)/2)
        x=(e.x-ox)/s; y=(e.y-oy)/s                             # -> composed (unscaled) coords
        return (min(max(x,0),pw), min(max(y,0),ph))
    def _meas_start_cb(self,e):
        if self._pv: self._meas_start=self._to_disp(e)
    def _meas_move_cb(self,e):
        if not self._meas_start or getattr(self,"_base_disp",None) is None or not self._pv: return
        p0=self._meas_start; p1=self._to_disp(e)
        im=self._base_disp.copy(); d=ImageDraw.Draw(im)
        d.line([p0,p1],fill=(79,208,147),width=2)
        for p in (p0,p1): d.ellipse([p[0]-3,p[1]-3,p[0]+3,p[1]+3],fill=(79,208,147))
        dist=((p1[0]-p0[0])**2+(p1[1]-p0[1])**2)**0.5*self._nmpp_disp
        d.text((min(p0[0],p1[0])+6, min(p0[1],p1[1])-12), f"{dist:.1f} nm",
               fill=(230,240,255), font=ImageFont.load_default())
        self.preview.configure(image=ctk.CTkImage(light_image=im,dark_image=im,size=im.size))

    def _footer(self):
        ctk.CTkLabel(self,text="Symmetric · 24-bit BMP · 2D-polygon process model",font=self.eb,text_color=MUT).grid(row=3,column=0,sticky="w",padx=22,pady=(0,10))

    # ---- material stack ----
    def _add_matlayer(self, material="silicon", thickness=20, capture=True):
        if capture: self._capture()
        self.matlayer_rows.append(MaterialLayerRow(self, material, thickness)); self._relayout_matstack(); self.render_preview()
    def _remove_matlayer(self,row):
        self._capture(); row.frame.destroy(); self.matlayer_rows.remove(row); self._relayout_matstack(); self.render_preview()
    def _move_matlayer(self,row,delta):
        i=self.matlayer_rows.index(row); j=i+delta
        if 0<=j<len(self.matlayer_rows):
            self._capture(); self.matlayer_rows[i],self.matlayer_rows[j]=self.matlayer_rows[j],self.matlayer_rows[i]; self._relayout_matstack(); self.render_preview()
    def _op_material_choices(self):
        mats=[]
        for r in self.matlayer_rows:
            m=r.mat.get()
            if m and m not in mats: mats.append(m)
        return mats or self.palette.names()     # fall back to palette when stack is empty

    def _refresh_op_materials(self):
        def walk(lst):
            for r in lst.rows:
                if isinstance(r,OpRow): r._sync()
                elif isinstance(r,RepeatRow): walk(r.sub)
        if hasattr(self,"stack"): walk(self.stack)

    def _relayout_matstack(self):
        for n,row in enumerate(self.matlayer_rows,1):
            row.frame.pack_forget(); row.frame.pack(fill="x",padx=6,pady=3); row.badge_lbl.configure(text=str(n))
        self.matstack_hint.pack_forget()
        if not self.matlayer_rows: self.matstack_hint.pack(anchor="w",padx=6)
        self._refresh_op_materials()
    def _drag_start(self,row): self._drag=row
    def _drag_drop(self,row):
        if self._drag is None: return
        y=self.winfo_pointery(); target=len(self.matlayer_rows)-1
        for i,r in enumerate(self.matlayer_rows):
            if y < r.frame.winfo_rooty()+r.frame.winfo_height()/2: target=i; break
        if self.matlayer_rows.index(self._drag)!=target:
            self._capture(); self.matlayer_rows.remove(self._drag); self.matlayer_rows.insert(target,self._drag)
            self._relayout_matstack(); self.render_preview()
        self._drag=None

    # ---- undo ----
    def _snapshot(self):
        return dict(materials=[{"material":r.mat.get(),"thickness":r.th.get(),"shape":list(r.shape)} for r in self.matlayer_rows],
                    ops=self.stack.to_ops(),
                    fields={k:self.entries[k].get() for k in self.entries},
                    scale=self.scale_entry.get(),
                    trace=self.opening_trace,
                    csv_ref=self.csv_ref_entry.get())
    def _capture(self):
        if self._loading: return
        snap=self._snapshot()
        if self._undo and self._undo[-1]==snap: return      # skip no-op duplicates
        self._undo.append(snap); self._redo.clear()
        if len(self._undo)>50: self._undo.pop(0)
    def _undo_action(self):
        if not self._undo: return
        self._redo.append(self._snapshot()); self._load_state(self._undo.pop())
    def _redo_action(self):
        if not self._redo: return
        self._undo.append(self._snapshot()); self._load_state(self._redo.pop())

    def _save_project(self):
        from tkinter import filedialog
        import json
        path=filedialog.asksaveasfilename(parent=self, defaultextension=".json",
              filetypes=[("Profile project","*.json")], initialfile="profile.json")
        if not path: return
        with open(path,"w") as f: json.dump(self._snapshot(), f, indent=2)
        self.title(f"Incoming Profile Utility — saved {Path(path).name}")
    def _open_project(self):
        from tkinter import filedialog
        import json
        path=filedialog.askopenfilename(parent=self, filetypes=[("Profile project","*.json")])
        if not path: return
        try:
            with open(path) as f: snap=json.load(f)
            self._load_state(snap)
            self._undo.clear(); self._redo.clear()      # opened state is the baseline; nothing to undo into
            self.title(f"Incoming Profile Utility — {Path(path).name}")
        except Exception as exc:
            self.title(f"Incoming Profile Utility — ⚠ open failed: {exc}")
    def _new_project(self):
        self._reset(capture=False)                       # blank canvas
        self._undo.clear(); self._redo.clear()           # fresh project: no history
        self.title("Incoming Profile Utility")
    def _load_ops(self, oplist, ops):
        oplist.clear()
        for op in ops:
            if op.get("op")=="repeat":
                r=RepeatRow(oplist); oplist.rows.append(r)
                self._load_ops(r.sub, op.get("steps",[]))
                r.times.delete(0,"end"); r.times.insert(0,str(op.get("times",1)))
            else:
                lbl,mat,num,aniso=_op_to_row(op)
                r=OpRow(oplist,lbl,mat,num,aniso); oplist.rows.append(r)
        oplist.relayout()
    def _load_state(self, snap):
        self._loading=True
        try:
            for r in list(self.matlayer_rows): r.frame.destroy()
            self.matlayer_rows=[]
            for m in snap["materials"]:
                self.matlayer_rows.append(MaterialLayerRow(self, m["material"], m["thickness"], m.get("shape")))
            self._relayout_matstack()
            self._load_ops(self.stack, snap["ops"])
            for k,v in snap["fields"].items():
                if k in self.entries: self.entries[k].delete(0,"end"); self.entries[k].insert(0,v)
            self.scale_entry.delete(0,"end"); self.scale_entry.insert(0,snap["scale"])
            self.csv_ref_entry.delete(0,"end"); self.csv_ref_entry.insert(0,snap.get("csv_ref",""))
            self.opening_trace=snap.get("trace")
            self.csv_label.configure(
                text=(f"✓ CSV loaded ({len(self.opening_trace)} pts)." if self.opening_trace
                      else "Opening: rectangular (from Space). Load a CSV to use a trace profile instead."),
                text_color=(GREEN if self.opening_trace else MUT))
        finally:
            self._loading=False
        self.render_preview()

    def _update_menus(self):
        names=self.palette.names()
        for om in self.material_menus+[r.mat for r in self.matlayer_rows]:
            cur=om.get(); om.configure(values=names); om.set(cur)
        self._refresh_op_materials()

    def _edit_shape(self, row):
        dlg=ctk.CTkToplevel(self); dlg.title("Top-corner shape"); dlg.geometry("440x380"); dlg.configure(fg_color=NAVY_800); dlg.transient(self)
        ctk.CTkLabel(dlg,text=f"Top-corner shape · {row.mat.get()}",font=self.ub,text_color=ON).pack(anchor="w",padx=16,pady=(12,2))
        ctk.CTkLabel(dlg,text="Stack MULTIPLE treatments here — e.g. Round + Taper. They combine (order-independent) and apply symmetrically to both corners.",
                     font=self.eb,text_color=MUT,wraplength=400,justify="left").pack(anchor="w",padx=16,pady=(0,6))
        cont=ctk.CTkScrollableFrame(dlg,fg_color="transparent",height=210); cont.pack(fill="both",expand=True,padx=10)
        trows=[]
        def to_dicts():
            out=[]
            for rec in trows:
                k=rec["kind"].get()
                def fv(e,d):
                    try: return float(e.get())
                    except ValueError: return d
                if k=="round": out.append({"kind":"round","r":fv(rec["p1"],0)})
                elif k=="chamfer": out.append({"kind":"chamfer","s":fv(rec["p1"],0)})
                elif k=="taper": out.append({"kind":"taper","angle":fv(rec["p1"],80)})
                else: out.append({"kind":"facet","angle":fv(rec["p1"],45),"depth":fv(rec["p2"],0)})
            return out
        def commit():
            row.shape=to_dicts(); row._refresh_shape_btn(); self.render_preview()
        def add_tr(t=None):
            t=t or {"kind":"round","r":10}
            fr=ctk.CTkFrame(cont,fg_color=NAVY_900,corner_radius=8); fr.pack(fill="x",pady=3)
            kind=ctk.CTkOptionMenu(fr,values=["round","chamfer","facet","taper"],width=90,font=self.uf,fg_color=NAVY_800,
                   button_color=BLUE,button_hover_color=BLUE_L,text_color=ON); kind.set(t.get("kind","round"))
            kind.pack(side="left",padx=(8,4),pady=7)
            ic=ctk.CTkLabel(fr,text="ⓘ",font=self.uf,text_color=BLUE_L,cursor="hand2"); ic.pack(side="left",padx=(0,6))
            Tooltip(ic,"round: fillet the top corner (radius).\nchamfer: straight 45° cut of the top corner (size).\n"
                       "facet: short angled cut of the top corner (angle from horizontal + depth).\n"
                       "taper: slope the WHOLE layer wall. angle = sidewall angle from the horizontal base "
                       "(90 = vertical, smaller = more sloped, opening wider at the top).")
            l1=ctk.CTkLabel(fr,text="",font=self.eb,text_color=MUT,width=44); l1.pack(side="left")
            p1=ctk.CTkEntry(fr,width=52,font=self.mono,fg_color=NAVY_800,border_color=NAVY_700,text_color=ON); p1.pack(side="left",padx=2)
            l2=ctk.CTkLabel(fr,text="",font=self.eb,text_color=MUT,width=44)
            p2=ctk.CTkEntry(fr,width=52,font=self.mono,fg_color=NAVY_800,border_color=NAVY_700,text_color=ON)
            rec={"frame":fr,"kind":kind,"p1":p1,"p2":p2}
            def sync(_=None):
                k=kind.get()
                if k=="facet":
                    l1.configure(text="angle°"); l2.configure(text="depth")
                    l2.pack(side="left"); p2.pack(side="left",padx=2)
                    if not p1.get().strip(): p1.insert(0,"45")
                    if not p2.get().strip(): p2.insert(0,"10")
                else:
                    l1.configure(text={"round":"radius","chamfer":"size","taper":"angle°"}[k])
                    p2.pack_forget(); l2.pack_forget()
                    if k=="taper" and not p1.get().strip(): p1.insert(0,"80")
            kind.configure(command=lambda _v:(sync(),commit()))
            p1.bind("<KeyRelease>",lambda e:commit()); p2.bind("<KeyRelease>",lambda e:commit())
            def rm(): fr.destroy(); trows.remove(rec); commit()
            ctk.CTkButton(fr,text="✕",width=24,font=self.uf,fg_color="transparent",border_width=1,border_color=NAVY_700,
                          text_color=SOFT,hover_color=NAVY_700,command=rm).pack(side="right",padx=6)
            if t.get("kind")=="facet": p1.insert(0,str(t.get("angle",45))); p2.insert(0,str(t.get("depth",10)))
            elif t.get("kind")=="chamfer": p1.insert(0,str(t.get("s",0)))
            elif t.get("kind")=="taper": p1.insert(0,str(t.get("angle",80)))
            else: p1.insert(0,str(t.get("r",0)))
            trows.append(rec); sync()
        for t in row.shape: add_tr(t)
        if not row.shape: add_tr()          # start with one visible row so the pattern is obvious
        bar=ctk.CTkFrame(dlg,fg_color="transparent"); bar.pack(fill="x",padx=12,pady=8)
        ctk.CTkButton(bar,text="＋ Add another treatment",command=lambda:(add_tr(),commit()),font=self.ub,fg_color="transparent",
                      border_width=1,border_color=GREEN,text_color=GREEN,hover_color=NAVY_700).pack(side="left",expand=True,fill="x",padx=2)
        ctk.CTkButton(bar,text="Done",command=dlg.destroy,font=self.ub,width=90,fg_color=GREEN,hover_color=GREEN_D,text_color=GREEN_INK).pack(side="left",padx=2)

    def _add_material(self):
        from tkinter.colorchooser import askcolor
        dlg=ctk.CTkToplevel(self); dlg.title("Add material"); dlg.geometry("340x210"); dlg.configure(fg_color=NAVY_800); dlg.transient(self)
        ctk.CTkLabel(dlg,text="New material",font=self.ub,text_color=ON).pack(anchor="w",padx=16,pady=(14,6))
        name_e=ctk.CTkEntry(dlg,placeholder_text="name (e.g. tungsten)",font=self.uf,fg_color=NAVY_900,border_color=NAVY_700,text_color=ON); name_e.pack(fill="x",padx=16,pady=6)
        chosen={"rgb":(79,208,147)}; sw=ctk.CTkFrame(dlg,fg_color="#4FD093",width=40,height=24,corner_radius=6); sw.pack(side="left",padx=(16,8),pady=10)
        def pick():
            rgb,_=askcolor(parent=dlg,title="Pick color")
            if rgb: chosen["rgb"]=tuple(int(c) for c in rgb); sw.configure(fg_color=f"#{chosen['rgb'][0]:02X}{chosen['rgb'][1]:02X}{chosen['rgb'][2]:02X}")
        ctk.CTkButton(dlg,text="Pick color…",command=pick,font=self.uf,fg_color="transparent",border_width=1,border_color=BLUE_L,text_color=ON,hover_color=NAVY_700).pack(side="left",pady=10)
        def commit():
            nm=name_e.get().strip().lower().replace(" ","_")
            if nm:
                self.palette.add(nm,chosen["rgb"],label=name_e.get().strip())
                try: self.palette.save()
                except OSError: pass
                self._update_menus()
            dlg.destroy()
        ctk.CTkButton(dlg,text="Add",command=commit,font=self.ub,width=90,fg_color=GREEN,hover_color=GREEN_D,text_color=GREEN_INK).pack(side="right",padx=16,pady=10)

    def _load_csv(self):
        from tkinter import filedialog
        path=filedialog.askopenfilename(parent=self, filetypes=[("CSV","*.csv")])
        if not path: return
        try:
            df=load_trace(path, normalize=False)
        except Exception as exc:
            self.csv_label.configure(text=f"⚠ {exc}", text_color="#E58B8B"); return
        self._capture()
        self.opening_trace=[(float(w),float(h)) for w,h in zip(df["width"],df["height"])]
        hspan=float(df["height"].max()-df["height"].min())
        if not self.matlayer_rows and hspan>0:      # give the opening something to cut, so it's visible
            self.matlayer_rows.append(MaterialLayerRow(self,"silicon",round(hspan,1))); self._relayout_matstack()
        self.csv_label.configure(text=f"✓ CSV loaded from {Path(path).name} ({len(df)} pts) — aligned to the TOP of the stack, cut downward. Set 'CSV height=0 at' to reposition; Space is ignored.", text_color=GREEN)
        self.render_preview()

    def _clear_csv(self):
        if self.opening_trace is not None:
            self._capture(); self.opening_trace=None
            self.csv_label.configure(text="Opening: rectangular (from Space). Load a CSV to use a trace profile instead.", text_color=MUT)
            self.render_preview()

    def _params(self):
        p={}
        for k,e in self.entries.items():
            v=e.get().strip()
            if v:
                try: p[k]=float(v)
                except ValueError: pass
        p["material_layers"]=[r.to_layer() for r in self.matlayer_rows]
        if self.opening_trace:
            p["opening_trace"]=self.opening_trace
            ref=self._csv_ref()
            if ref is not None: p["opening_ref"]=ref
        return p

    def _csv_ref(self):
        v=self.csv_ref_entry.get().strip()
        if not v: return None
        try: return float(v)
        except ValueError: return None

    def _scale(self):
        v=self.scale_entry.get().strip()
        if not v or v.lower()=="auto": return None
        try: return float(v)
        except ValueError: return None

    def _resolve_npp(self, st, cap=1600, target_px=1000):
        minx,miny,maxx,maxy=st.cell.bounds
        W=max(maxx-minx,1.0); H=max(maxy-miny,1.0)
        manual=self._scale()
        npp = manual if (manual and manual>0) else H/target_px  # manual value, else ~target_px px tall
        npp = max(npp, W/cap, H/cap, 0.005)                     # clamp so neither side exceeds `cap` px
        return npp

    def _render_to(self,out_path,for_save=False):
        base=proc.build_base(self._params()); st=proc.evaluate(base,self.stack.to_ops()); self._last_state=st
        z=max(1.0, getattr(self,"_zoom",1.0))
        if for_save:
            npp=self._resolve_npp(st, cap=12000)
        else:
            npp=self._resolve_npp(st, cap=min(6000,int(1600*z)), target_px=min(4000,int(1000*z)))
        self._last_npp=npp
        ss={"Off":1,"2×":2,"4×":4,"8×":8}.get(self.smooth_level.get(),1)
        # bound the internal supersample so a big profile can't freeze
        minx,miny,maxx,maxy=st.cell.bounds; maxdim=max(maxx-minx,maxy-miny)
        HI_CAP=8000 if for_save else 4000
        while ss>1 and maxdim*ss/npp>HI_CAP: ss//=2
        proc.render_regions(st,self.palette,out_path,npp,oversample=ss)  # majority-vote AA, exact colors

    def _reset(self, capture=True):
        if capture: self._capture()
        self._zoom=1.0; self._cx=self._cy=0.5
        if hasattr(self,"zoom_var"): self.zoom_var.set(1.0)
        self.stack.clear()
        for r in list(self.matlayer_rows): r.frame.destroy()
        self.matlayer_rows=[]; self._relayout_matstack()
        self.opening_trace=None
        self.csv_ref_entry.delete(0,"end")
        self.csv_label.configure(text="Opening: rectangular (from Space). Load a CSV to use a trace profile instead.", text_color=MUT)
        for k,label,default,info in FIELDS:
            self.entries[k].delete(0,"end"); self.entries[k].insert(0,default)
        self.scale_entry.delete(0,"end")  # blank = auto
        self.render_preview()

    def _update_legend(self):
        for w in self.legend.winfo_children(): w.destroy()
        mats=[]
        if self._last_state is not None:
            for m,_ in self._last_state.regions:
                if m not in mats: mats.append(m)
        for mat in mats:
            chip=ctk.CTkFrame(self.legend,fg_color="transparent"); chip.pack(side="left",padx=(0,12))
            sw=ctk.CTkFrame(chip,width=14,height=14,corner_radius=3,fg_color=self.palette.hex(mat),border_width=1,border_color=NAVY_700); sw.pack(side="left",padx=(0,5)); sw.pack_propagate(False)
            ctk.CTkLabel(chip,text=mat,font=self.eb,text_color=SOFT).pack(side="left")

    def _schedule_render(self,_e=None):
        if getattr(self,"_job",None): self.after_cancel(self._job)
        self._job=self.after(120,self.render_preview)

    def _field(self,key):
        try: return float(self.entries[key].get())
        except (ValueError, KeyError): return None

    def _update_shape_availability(self):
        rows=self.matlayer_rows
        total=0.0
        for r in rows:
            try: total+=float(r.th.get())
            except ValueError: pass
        space=self._field("space"); depth=self._field("opening_depth"); trace=self.opening_trace is not None
        open_bottom = 0.0 if (depth is None or depth<=0 or (total and depth>=total)) else (total-depth)
        y=0.0; topmap={}
        for r in reversed(rows):
            try: y+=float(r.th.get())
            except ValueError: pass
            topmap[id(r)]=y
        for r in rows:
            reach=(not trace) and (space is not None and space>0) and (topmap.get(id(r),0)>open_bottom+1e-9)
            r.shape_btn.configure(state="normal" if reach else "disabled")

    def _update_csv_field_state(self):
        # Space / Opening depth / bottom-round are ignored while a CSV drives the opening.
        disabled = self.opening_trace is not None
        for k in ("space","opening_depth","opening_bottom_radius"):
            e=self.entries.get(k)
            if e is not None:
                try: e.configure(state="disabled" if disabled else "normal")
                except Exception: pass

    def render_preview(self, view_only=False):
        """view_only=True: the profile hasn't changed (panning/zooming) — reuse the cached
        render and just re-crop/recompose, which is far cheaper than rebuilding geometry."""
        self._job=None
        if self._loading: return
        try:
            tmp=Path(tempfile.gettempdir())/"_ipu_preview.bmp"
            cached=getattr(self,"_full_img",None)
            if view_only and cached is not None:
                im_full=cached                              # skip engine + raster entirely
            else:
                self._update_shape_availability()
                self._update_csv_field_state()
                self._render_to(tmp)
                im_full=Image.open(tmp).convert("RGB"); im_full.load()
                self._full_img=im_full                      # cache for subsequent pans/zooms
            src_img=im_full; origin=(0.0,0.0); z=self._zoom
            if z>1.0:
                W,H=im_full.size; half=0.5/z
                cx=min(max(self._cx,half),1-half); cy=min(max(self._cy,half),1-half); self._cx,self._cy=cx,cy
                fx0,fx1=cx-half,cx+half; fy0,fy1=cy-half,cy+half
                px0=int(fx0*W); px1=max(px0+1,int(round(fx1*W)))
                py0=int((1-fy1)*H); py1=max(py0+1,int(round((1-fy0)*H)))   # image y is top-origin
                src_img=im_full.crop((px0,py0,px1,py1))
                origin=(fx0*W*self._last_npp, fy0*H*self._last_npp)
            self.preview.update_idletasks()
            _tgt=getattr(self,"_pv_target",self.preview)
            try: _s=ctk.ScalingTracker.get_widget_scaling(self)
            except Exception: _s=1.0
            box_w=_tgt.winfo_width()/_s; box_h=_tgt.winfo_height()/_s
            if box_w<120 or box_h<120: box_w,box_h=760,460          # before first layout
            disp,fit=compose_preview(src_img,self._last_npp,box_w=box_w,box_h=box_h,origin=origin,return_scale=True)
            self._nmpp_disp=self._last_npp/fit                 # real nm per on-screen (composed) pixel
            srcW,srcH=src_img.size
            self._prof_wh=(max(1,int(srcW*fit)),max(1,int(srcH*fit)))   # profile's on-screen size (for panning)
            self._base_disp=disp                               # clean image (for the measure overlay)
            self.preview.configure(image=ctk.CTkImage(light_image=disp,dark_image=disp,size=disp.size),text="")
            self._pv=(disp.size[0],disp.size[1],z)                        # for pan / measure mapping
            if not view_only: self._update_legend()   # materials can't change while panning
            if not view_only:
                mode="" if self._scale() else " (auto)"
                if z>1.0:
                    tail=f" · {z:.1f}× · drag or arrow keys to move"
                elif getattr(self,"_tool","move")=="move":
                    tail=" · scroll over the preview to zoom, then drag to move"
                else:
                    tail=""
                self.preview_note.configure(text=f"{self._last_npp:.3g} nm/px{mode} · updates live{tail}",text_color=MUT)
        except Exception as exc:
            self.preview.configure(image=None,text=f"⚠ {exc}",text_color=MUT)

    def save_bmp(self):
        from tkinter import filedialog
        path=filedialog.asksaveasfilename(defaultextension=".bmp",filetypes=[("Bitmap","*.bmp")],initialfile="profile.bmp")
        if not path: return
        self._render_to(path, for_save=True)   # full-resolution, no anti-aliasing
        self.title(f"Incoming Profile Utility — saved {Path(path).name}")

    def export_polygons(self):
        from tkinter import filedialog, messagebox
        path=filedialog.asksaveasfilename(defaultextension=".svg",initialfile="profile.svg",
             filetypes=[("SVG vector","*.svg"),("JSON coordinates","*.json")],title="Export polygons")
        if not path: return
        low=path.lower(); stem=path[:-4] if (low.endswith(".svg") or low.endswith(".json")) else path
        try:
            base=proc.build_base(self._params()); st=proc.evaluate(base,self.stack.to_ops())
            proc.export_polygons(st,self.palette,svg_path=stem+".svg",json_path=stem+".json")
        except Exception as exc:
            messagebox.showerror("Export failed",str(exc)); return
        messagebox.showinfo("Polygons exported",
            f"{Path(stem).name}.svg — editable vertices (Inkscape / Illustrator)\n"
            f"{Path(stem).name}.json — exact nm coordinates per material")
        self.title(f"Incoming Profile Utility — exported {Path(stem).name}.svg")


def launch():
    ProfileStudio().mainloop()

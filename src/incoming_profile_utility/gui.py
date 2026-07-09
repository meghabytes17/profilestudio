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
    ("opening_depth","Opening depth (nm)","","How far down the opening is cut, measured from the TOP of the whole stack (not per-layer). Blank = cut all the way through every material."),
    ("opening_bottom_radius","Opening bottom round (nm)","","Round the BOTTOM of the opening into a U. 0 = flat; ≈ half the Space = full semicircle."),
    ("top_vacuum","Top vacuum (nm)","20","Empty space above the stack (room to deposit on top)."),
]
OP_LABELS = ["Deposit · conformal","Deposit · planar","Fill","Etch · isotropic","Etch · anisotropic","Planarize"]
OP_PRESETS = {"deposit":("Deposit · conformal","oxide",8),"fill":("Fill","tungsten",0),
              "etch":("Etch · anisotropic","(any)",5),"planarize":("Planarize","oxide",240)}
OP_INFO = ("Deposit · conformal: uniform film of the set thickness on all exposed surfaces.\n"
           "Deposit · planar: flat slab of the set thickness on top.\n"
           "Fill: fills the opening with the chosen material.\n"
           "Etch: removes to the set depth. Pick a material to etch just that one (stops on "
           "others), or (any) to etch everything exposed. Anisotropy 1 = vertical, 0 = isotropic undercut.\n"
           "Planarize: cut everything above the given height (CMP).")


def _op_to_row(op):
    o=op.get("op")
    if o=="conformal_deposit": return ("Deposit · conformal", op.get("material","oxide"), op.get("thickness",0), 1.0)
    if o=="planar_deposit":    return ("Deposit · planar", op.get("material","oxide"), op.get("thickness",0), 1.0)
    if o=="fill":              return ("Fill", op.get("material","tungsten"), 0, 1.0)
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

def compose_preview(bmp_path, nm_per_px, target_h=440):
    img=Image.open(bmp_path).convert("RGB"); w,h=img.size
    disp=min(6.0, target_h/h); dw,dh=max(1,int(w*disp)),max(1,int(h*disp))
    prof=img.resize((dw,dh), Image.NEAREST)
    ML,MB,MT,MR=48,30,12,14
    canvas=Image.new("RGB",(ML+dw+MR, MT+dh+MB),(11,22,38)); canvas.paste(prof,(ML,MT))
    ov=Image.new("RGBA",canvas.size,(0,0,0,0)); d=ImageDraw.Draw(ov); font=ImageFont.load_default()
    ppn=disp/nm_per_px; wnm,hnm=w*nm_per_px,h*nm_per_px; sx,sy=_nice_step(wnm),_nice_step(hnm)
    grid=(110,144,198,70); tick=(110,144,198,255)
    for k in range(int(wnm//sx)+1):
        xx=ML+k*sx*ppn; d.line([(xx,MT),(xx,MT+dh)],fill=grid); d.text((xx-5,MT+dh+5),f"{int(k*sx)}",fill=tick,font=font)
    for k in range(int(hnm//sy)+1):
        yy=MT+dh-k*sy*ppn; d.line([(ML,yy),(ML+dw,yy)],fill=grid); d.text((6,yy-4),f"{int(k*sy)}",fill=tick,font=font)
    d.text((ML,MT+dh+16),"width nm  /  height nm ↑",fill=tick,font=font)
    return Image.alpha_composite(canvas.convert("RGBA"),ov).convert("RGB")


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
        Tooltip(self.shape_btn, "Shape this layer's opening: round / chamfer / facet the top corners, "
                                "or taper the sidewall (taper angle = sidewall angle from the horizontal base, 90° = vertical).")
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
                vals=["(any)"]+names; self.mat.configure(state="normal", values=vals)
                if self.mat.get() not in vals: self.mat.set("(any)")
            else:
                self.mat.configure(state="normal", values=names)
                if self.mat.get() not in names and names: self.mat.set(names[0])
        if lbl=="Etch · anisotropic": self.aniso_lbl.pack(side="left",padx=(6,1)); self.aniso.pack(side="left")
        else: self.aniso_lbl.pack_forget(); self.aniso.pack_forget()
    def to_op(self):
        lbl=self.optype.get(); mat=self.mat.get()
        try: n=float(self.num.get())
        except ValueError: n=0.0
        tgt=None if mat=="(any)" else mat
        if lbl=="Deposit · conformal": return dict(op="conformal_deposit", material=mat, thickness=n)
        if lbl=="Deposit · planar":    return dict(op="planar_deposit", material=mat, thickness=n)
        if lbl=="Fill":                return dict(op="fill", material=mat)
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
        self.title("Incoming Profile Utility"); self.geometry("1180x820")
        self.palette=load_palette(); self.opening_trace=None
        self.material_menus=[]; self.matlayer_rows=[]; self._last_state=None
        self._undo=[]; self._redo=[]; self._loading=False; self._drag=None; self._last_npp=0.4; self.smooth_level=ctk.StringVar(value="Off")
        self.uf=ctk.CTkFont(family="Inter",size=13); self.ub=ctk.CTkFont(family="Inter",size=14,weight="bold")
        self.tf=ctk.CTkFont(family="Inter",size=20,weight="bold"); self.mono=ctk.CTkFont(family="JetBrains Mono",size=12)
        self.eb=ctk.CTkFont(family="JetBrains Mono",size=11)
        self.hf=ctk.CTkFont(family="Inter",size=22,weight="bold")   # header title
        self.grid_columnconfigure(0,weight=1); self.grid_rowconfigure(2,weight=1)
        self._header(); self._toolbar(); self._body(); self._footer()
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

    def _body(self):
        body=ctk.CTkFrame(self,fg_color="transparent"); body.grid(row=2,column=0,sticky="nsew",padx=18,pady=16)
        body.grid_columnconfigure(0,weight=0,minsize=580); body.grid_columnconfigure(1,weight=1); body.grid_rowconfigure(0,weight=1)
        self._inputs(body); self._preview_card(body)

    def _inputs(self,parent):
        card=self._card(parent,"Inputs"); card.grid(row=0,column=0,sticky="nsew",padx=(0,12))
        self.param_page=ctk.CTkScrollableFrame(card,fg_color="transparent",height=540)
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

        bs=ctk.CTkFrame(self.param_page,fg_color="transparent"); bs.pack(fill="x",pady=(8,4)); bs.grid_columnconfigure(2,weight=1)
        ctk.CTkLabel(bs,text="BASE FEATURE",font=self.eb,text_color=BLUE_L).grid(row=0,column=0,columnspan=3,sticky="w",padx=8,pady=(4,2))
        for i,(k,label,default,info) in enumerate(FIELDS,1):
            e=ctk.CTkEntry(bs,font=self.mono,fg_color=NAVY_900,border_color=NAVY_700,text_color=ON,width=120)
            e.insert(0,default); e.bind("<KeyRelease>",self._schedule_render); self._row(bs,i,label,info,e); self.entries[k]=e
        ocsv=ctk.CTkFrame(bs,fg_color="transparent"); ocsv.grid(row=len(FIELDS)+1,column=0,columnspan=3,sticky="ew",padx=6,pady=(6,0))
        ctk.CTkButton(ocsv,text="Load CSV…",command=self._load_csv,font=self.uf,fg_color=NAVY_900,border_width=1,
                      border_color=BLUE_L,text_color=ON,hover_color=NAVY_700).pack(side="left",expand=True,fill="x",padx=2)
        ctk.CTkButton(ocsv,text="Clear",command=self._clear_csv,font=self.uf,fg_color="transparent",border_width=1,
                      border_color=NAVY_700,text_color=SOFT,hover_color=NAVY_700,width=70).pack(side="left",padx=2)
        self.csv_label=ctk.CTkLabel(bs,text="Opening: rectangular (from Space). Load a CSV to use a trace profile instead.",
                                    font=self.eb,text_color=MUT,wraplength=520,justify="left")
        self.csv_label.grid(row=len(FIELDS)+2,column=0,columnspan=3,sticky="w",padx=8,pady=(2,2))
        self.csv_ref_entry=ctk.CTkEntry(bs,font=self.mono,fg_color=NAVY_900,border_color=NAVY_700,text_color=ON,width=120,placeholder_text="top")
        self.csv_ref_entry.bind("<KeyRelease>",self._schedule_render)
        self._row(bs,len(FIELDS)+3,"CSV height=0 at (nm)",
                  "Where the CSV's height=0 line sits, measured in nm from the stack bottom. Blank = top-align (trace top at the stack top). Points with negative height sit below this line.",
                  self.csv_ref_entry)

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
        fr=ctk.CTkFrame(card,fg_color=NAVY_900,corner_radius=10); fr.pack(expand=True,fill="both",padx=18,pady=6)
        self.preview=ctk.CTkLabel(fr,text="",fg_color=NAVY_900); self.preview.pack(expand=True,fill="both",padx=10,pady=10)
        self.legend=ctk.CTkFrame(card,fg_color="transparent"); self.legend.pack(fill="x",padx=18,pady=(0,4))
        bar=ctk.CTkFrame(card,fg_color="transparent"); bar.pack(fill="x",padx=18,pady=(4,16)); bar.grid_columnconfigure(0,weight=1)
        sm=ctk.CTkFrame(bar,fg_color="transparent"); sm.grid(row=0,column=0,sticky="w")
        ctk.CTkLabel(sm,text="Smoothing",font=self.eb,text_color=SOFT).pack(side="left",padx=(0,6))
        ctk.CTkOptionMenu(sm,values=["Off","2×","4×","8×"],variable=self.smooth_level,command=lambda _v:self.render_preview(),
                          width=76,font=self.uf,fg_color=NAVY_900,button_color=BLUE,button_hover_color=BLUE_L,text_color=ON).pack(side="left")
        ctk.CTkLabel(bar,text="preview updates as you edit",font=self.eb,text_color=MUT).grid(row=0,column=1,padx=(0,10))
        ctk.CTkButton(bar,text="Save .bmp…",command=self.save_bmp,font=self.ub,width=120,fg_color=GREEN,hover_color=GREEN_D,text_color=GREEN_INK).grid(row=0,column=2)

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
        ctk.CTkLabel(dlg,text="Treatments stack (combine), applied to both top corners (symmetric).",
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
        bar=ctk.CTkFrame(dlg,fg_color="transparent"); bar.pack(fill="x",padx=12,pady=8)
        ctk.CTkButton(bar,text="＋ Add treatment",command=lambda:(add_tr(),commit()),font=self.uf,fg_color=NAVY_900,
                      border_width=1,border_color=BLUE_L,text_color=ON,hover_color=NAVY_700).pack(side="left",expand=True,fill="x",padx=2)
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

    def _resolve_npp(self, st):
        manual=self._scale()
        if manual and manual>0: return manual
        minx,miny,maxx,maxy=st.cell.bounds
        W=max(maxx-minx,1.0); H=max(maxy-miny,1.0)
        npp=H/1000.0                          # target ~1000 px tall
        CAP=2400                              # but never exceed this many px on either side
        if W/npp>CAP: npp=W/CAP
        if H/npp>CAP: npp=H/CAP
        return max(npp,0.005)

    def _render_to(self,out_path):
        base=proc.build_base(self._params()); st=proc.evaluate(base,self.stack.to_ops()); self._last_state=st
        npp=self._resolve_npp(st); self._last_npp=npp
        ss={"Off":1,"2×":2,"4×":4,"8×":8}.get(self.smooth_level.get(),1)
        if ss==1:
            proc.render_regions(st,self.palette,out_path,npp)     # hard pixels, no AA
        else:
            import cv2
            minx,miny,maxx,maxy=st.cell.bounds
            Wnm=maxx-minx; Hnm=maxy-miny
            HI_CAP=4000                                           # keep the supersample bounded (no freeze)
            hi_npp=max(npp/ss, Wnm/HI_CAP, Hnm/HI_CAP)
            hi=Path(tempfile.gettempdir())/"_ipu_hi.bmp"
            proc.render_regions(st,self.palette,hi,hi_npp)        # supersample (capped)
            W=max(1,round(Wnm/npp)); H=max(1,round(Hnm/npp))
            img=cv2.resize(cv2.imread(str(hi)),(W,H),interpolation=cv2.INTER_AREA)
            cv2.imwrite(str(out_path),img)

    def _reset(self, capture=True):
        if capture: self._capture()
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

    def render_preview(self):
        self._job=None
        if self._loading: return
        self._update_shape_availability()
        try:
            tmp=Path(tempfile.gettempdir())/"_ipu_preview.bmp"; self._render_to(tmp)
            disp=compose_preview(tmp,self._last_npp,target_h=440)
            self.preview.configure(image=ctk.CTkImage(light_image=disp,dark_image=disp,size=disp.size),text="")
            self._update_legend()
        except Exception as exc:
            self.preview.configure(image=None,text=f"⚠ {exc}",text_color=MUT)

    def save_bmp(self):
        from tkinter import filedialog
        path=filedialog.asksaveasfilename(defaultextension=".bmp",filetypes=[("Bitmap","*.bmp")],initialfile="profile.bmp")
        if not path: return
        self._render_to(path)   # full-resolution, no anti-aliasing
        self.title(f"Incoming Profile Utility — saved {Path(path).name}")


def launch():
    ProfileStudio().mainloop()

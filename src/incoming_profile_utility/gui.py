"""Incoming Profile Utility — GUI (customtkinter), SandBox brand theme.

Parametric mode drives the process-op engine (process.py): a selectable base
(Blank / Substrate / Trench / Line) plus an ordered process stack of operations —
including Repeat blocks for multilayer/superlattice stacks — with a live preview,
nm grid, and material legend. CSV mode renders a width/height trace.
"""
from __future__ import annotations

import math
import tempfile
from pathlib import Path

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont

from .materials import load_palette, _DEFAULT_CONFIG
from .profiles import render_trace_csv
from .io_csv import load_trace, trace_to_parametric
from . import process as proc

NAVY="#0E1B2E"; NAVY_900="#0B1626"; NAVY_800="#132540"; NAVY_700="#1C2C46"
BLUE="#283D5D"; BLUE_L="#6E90C6"; GREEN="#4FD093"; GREEN_D="#0E7A49"; GREEN_INK="#07271A"
ON="#FFFFFF"; SOFT="#AEB9C8"; MUT="#8B99AC"

FIELDS = [
    ("pitch","Pitch (nm)","120","Width of one repeating unit cell."),
    ("space","Space (nm)","","Gap width. pitch = linewidth + space."),
    ("feature_height","Feature height (nm)","220","Base (0) to top of the trench/feature."),
    ("top_width","Top width (nm)","50","Full CD at the top (equal top & bottom = straight walls)."),
    ("mid_width","Mid width (nm)","","Optional mid CD for a gentle curve (ignored if Bow set)."),
    ("bottom_width","Bottom width (nm)","50","Full CD at the base."),
    ("bow","Bow · max CD (nm)","","Maximum CD; must be >= top and bottom."),
    ("bow_height","Bow height (nm)","","Height of the max CD (default mid)."),
]
OP_LABELS = ["Deposit · conformal","Deposit · planar","Fill","Etch · isotropic","Etch · anisotropic","Planarize"]
OP_PRESETS = {"deposit":("Deposit · conformal","oxide",8),"fill":("Fill","tungsten",0),
              "etch":("Etch · isotropic","oxide",5),"planarize":("Planarize","oxide",240)}


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
    def __init__(self,widget,text): self.w,self.t,self.tip=widget,text,None; widget.bind("<Enter>",self._s); widget.bind("<Leave>",self._h)
    def _s(self,_=None):
        if self.tip or not self.t: return
        x=self.w.winfo_rootx()+18; y=self.w.winfo_rooty()+18
        self.tip=tw=ctk.CTkToplevel(self.w); tw.wm_overrideredirect(True); tw.wm_geometry(f"+{x}+{y}"); tw.configure(fg_color=NAVY_700)
        ctk.CTkLabel(tw,text=self.t,justify="left",wraplength=260,text_color=ON,fg_color=NAVY_700,font=ctk.CTkFont(size=11)).pack(padx=8,pady=6)
    def _h(self,_=None):
        if self.tip: self.tip.destroy(); self.tip=None


class MaskLayerRow:
    """One layer of the mask stack: a material + a height (bands, bottom -> top)."""
    def __init__(self, app, material, height):
        self.app=app
        self.frame=ctk.CTkFrame(app.mask_container, fg_color=NAVY_900, corner_radius=8, border_width=1, border_color=NAVY_700)
        self.mat=ctk.CTkOptionMenu(self.frame, values=app.palette.names(), width=130, font=app.uf, fg_color=NAVY_800,
                     button_color=BLUE, button_hover_color=BLUE_L, text_color=ON, command=lambda _v: app.render_preview())
        self.mat.set(material); self.mat.pack(side="left", padx=(10,6), pady=7)
        self.h=ctk.CTkEntry(self.frame, width=52, font=app.mono, fg_color=NAVY_800, border_color=NAVY_700, text_color=ON)
        self.h.insert(0,str(height)); self.h.bind("<KeyRelease>", app._schedule_render); self.h.pack(side="left", padx=(4,2))
        ctk.CTkLabel(self.frame, text="nm tall", font=app.eb, text_color=MUT).pack(side="left")
        ctk.CTkButton(self.frame, text="✕", width=24, font=app.uf, fg_color="transparent", border_width=1,
                      border_color=NAVY_700, text_color=SOFT, hover_color=NAVY_700,
                      command=lambda: app._remove_mask_layer(self)).pack(side="right", padx=6)
    def to_layer(self):
        try: hh=float(self.h.get())
        except ValueError: hh=0.0
        return dict(material=self.mat.get(), height=hh)


class OpRow:
    NEEDS_MAT = ("Deposit · conformal", "Deposit · planar", "Fill")
    def __init__(self, host, op_label, material, num):
        self.host=host; app=host.app
        self.frame=ctk.CTkFrame(host.container, fg_color=NAVY_900, corner_radius=8, border_width=1, border_color=NAVY_700)
        self.badge=ctk.CTkFrame(self.frame, fg_color=BLUE, corner_radius=999, width=22, height=22)
        self.badge.pack(side="left", padx=(10,8), pady=8); self.badge.pack_propagate(False)
        self.badge_lbl=ctk.CTkLabel(self.badge, text="1", font=app.eb, text_color=ON); self.badge_lbl.pack(expand=True)
        self.optype=ctk.CTkOptionMenu(self.frame, values=OP_LABELS, width=146, font=app.uf, fg_color=NAVY_800,
                     button_color=BLUE, button_hover_color=BLUE_L, text_color=ON, command=self._on_type)
        self.optype.set(op_label); self.optype.pack(side="left", padx=4, pady=8)
        self.mat=ctk.CTkOptionMenu(self.frame, values=app.palette.names(), width=104, font=app.uf, fg_color=NAVY_800,
                     button_color=BLUE, button_hover_color=BLUE_L, text_color=ON, command=lambda _v: app._schedule_render())
        self.mat.set(material); self.mat.pack(side="left", padx=2, pady=8)
        self.num=ctk.CTkEntry(self.frame, width=46, font=app.mono, fg_color=NAVY_800, border_color=NAVY_700, text_color=ON)
        self.num.insert(0,str(num)); self.num.bind("<KeyRelease>", app._schedule_render); self.num.pack(side="left", padx=(6,2))
        ctk.CTkLabel(self.frame, text="nm", font=app.eb, text_color=MUT).pack(side="left")
        for sym,cmd in (("↑",lambda:host.move(self,-1)),("↓",lambda:host.move(self,1)),("✕",lambda:host.remove(self))):
            ctk.CTkButton(self.frame, text=sym, width=24, font=app.uf, fg_color="transparent", border_width=1,
                          border_color=NAVY_700, text_color=SOFT, hover_color=NAVY_700, command=cmd).pack(side="left", padx=1)
        self._sync()
    def _on_type(self,_v): self._sync(); self.host.app._schedule_render()
    def _sync(self):
        self.mat.configure(state="normal" if self.optype.get() in self.NEEDS_MAT else "disabled")
    def to_op(self):
        lbl=self.optype.get(); mat=self.mat.get()
        try: n=float(self.num.get())
        except ValueError: n=0.0
        if lbl=="Deposit · conformal": return dict(op="conformal_deposit", material=mat, thickness=n)
        if lbl=="Deposit · planar":    return dict(op="planar_deposit", material=mat, thickness=n)
        if lbl=="Fill":                return dict(op="fill", material=mat)
        if lbl=="Etch · isotropic":    return dict(op="etch", depth=n, mode="isotropic")
        if lbl=="Etch · anisotropic":  return dict(op="etch", depth=n, mode="anisotropic")
        if lbl=="Planarize":           return dict(op="planarize", at_height=n)
        return dict(op="conformal_deposit", material=mat, thickness=n)


class RepeatRow:
    """A repeat block: its sub-steps run `times` times in order. Used for superlattices."""
    def __init__(self, host):
        self.host=host; app=host.app
        self.frame=ctk.CTkFrame(host.container, fg_color=NAVY_800, corner_radius=8, border_width=1, border_color=GREEN_D)
        head=ctk.CTkFrame(self.frame, fg_color="transparent"); head.pack(fill="x", padx=8, pady=(8,2))
        self.badge=ctk.CTkFrame(head, fg_color=GREEN_D, corner_radius=999, width=22, height=22)
        self.badge.pack(side="left", padx=(2,8)); self.badge.pack_propagate(False)
        self.badge_lbl=ctk.CTkLabel(self.badge, text="1", font=app.eb, text_color=ON); self.badge_lbl.pack(expand=True)
        ctk.CTkLabel(head, text="⟳ Repeat block  ×", font=app.ub, text_color=GREEN).pack(side="left")
        self.times=ctk.CTkEntry(head, width=48, font=app.mono, fg_color=NAVY_900, border_color=NAVY_700, text_color=ON)
        self.times.insert(0,"10"); self.times.bind("<KeyRelease>", app._schedule_render); self.times.pack(side="left", padx=6)
        for sym,cmd in (("↑",lambda:host.move(self,-1)),("↓",lambda:host.move(self,1)),("✕",lambda:host.remove(self))):
            ctk.CTkButton(head, text=sym, width=24, font=app.uf, fg_color="transparent", border_width=1,
                          border_color=NAVY_700, text_color=SOFT, hover_color=NAVY_700, command=cmd).pack(side="right", padx=1)
        addbar=ctk.CTkFrame(self.frame, fg_color="transparent"); addbar.pack(fill="x", padx=8, pady=(0,2))
        for text,kind in [("＋ Deposit","deposit"),("＋ Fill","fill"),("＋ Etch","etch"),("＋ Planarize","planarize")]:
            ctk.CTkButton(addbar,text=text,command=lambda k=kind:self.sub.add_op(k),font=ctk.CTkFont(size=11),fg_color=NAVY_900,
                          border_width=1,border_color=BLUE_L,text_color=ON,hover_color=NAVY_700,width=10,height=24).pack(side="left",expand=True,fill="x",padx=2)
        self.subcont=ctk.CTkFrame(self.frame, fg_color="transparent"); self.subcont.pack(fill="x", padx=(14,6), pady=(2,8))
        self.sub=OpList(app, self.subcont)
        self.sub.add_op("deposit")  # seed one so the block isn't empty
    def to_op(self):
        try: n=int(float(self.times.get()))
        except ValueError: n=1
        return dict(op="repeat", times=max(1,n), steps=self.sub.to_ops())


class OpList:
    """Manages an ordered container of OpRow / RepeatRow widgets."""
    def __init__(self, app, container, empty_hint=None):
        self.app=app; self.container=container; self.rows=[]; self.empty_hint=empty_hint
    def add_op(self, kind="deposit"):
        lbl,mat,num=OP_PRESETS.get(kind,OP_PRESETS["deposit"]); self.rows.append(OpRow(self,lbl,mat,num)); self.relayout(); self.app.render_preview()
    def add_repeat(self):
        self.rows.append(RepeatRow(self)); self.relayout(); self.app.render_preview()
    def remove(self,row): row.frame.destroy(); self.rows.remove(row); self.relayout(); self.app.render_preview()
    def move(self,row,delta):
        i=self.rows.index(row); j=i+delta
        if 0<=j<len(self.rows):
            self.rows[i],self.rows[j]=self.rows[j],self.rows[i]; self.relayout(); self.app.render_preview()
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
        self.palette=load_palette(); self.csv_path=None; self.mode="Parametric"
        self.material_menus=[]; self._last_state=None
        self.uf=ctk.CTkFont(family="Inter",size=13); self.ub=ctk.CTkFont(family="Inter",size=14,weight="bold")
        self.tf=ctk.CTkFont(family="Inter",size=20,weight="bold"); self.mono=ctk.CTkFont(family="JetBrains Mono",size=12)
        self.eb=ctk.CTkFont(family="JetBrains Mono",size=11)
        self.grid_columnconfigure(0,weight=1); self.grid_rowconfigure(1,weight=1)
        self._header(); self._body(); self._footer()
        self._set_mode("Parametric")
        self.after(160, self.render_preview)

    def _row(self,parent,r,label,info,widget):
        ctk.CTkLabel(parent,text=label,font=self.uf,text_color=SOFT).grid(row=r,column=0,sticky="w",padx=(8,6),pady=5)
        ic=ctk.CTkLabel(parent,text="ⓘ",font=self.uf,text_color=BLUE_L,cursor="hand2"); ic.grid(row=r,column=1,sticky="w",padx=(0,8)); Tooltip(ic,info)
        widget.grid(row=r,column=2,sticky="ew",padx=(0,8),pady=5)

    def _header(self):
        h=ctk.CTkFrame(self,fg_color=NAVY_900,corner_radius=0,height=66); h.grid(row=0,column=0,sticky="ew"); h.grid_propagate(False); h.grid_columnconfigure(0,weight=1)
        b=ctk.CTkFrame(h,fg_color="transparent"); b.grid(row=0,column=0,sticky="w",padx=22,pady=12)
        ctk.CTkLabel(b,text="SANDBOX · PROFILE STUDIO",font=self.eb,text_color=BLUE_L).pack(anchor="w")
        ctk.CTkLabel(b,text="Incoming Profile Utility",font=self.tf,text_color=ON).pack(anchor="w")
        pill=ctk.CTkFrame(h,fg_color=GREEN,corner_radius=999); pill.grid(row=0,column=1,sticky="e",padx=22)
        ctk.CTkLabel(pill,text="v1",font=self.mono,text_color=GREEN_INK).pack(padx=12,pady=3)

    def _card(self,parent,title):
        c=ctk.CTkFrame(parent,fg_color=NAVY_800,corner_radius=12,border_width=1,border_color=NAVY_700)
        ctk.CTkLabel(c,text=title,font=self.ub,text_color=ON).pack(anchor="w",padx=18,pady=(14,6)); return c

    def _mat_menu(self,parent,default,width=150):
        m=ctk.CTkOptionMenu(parent,values=self.palette.names(),font=self.uf,fg_color=NAVY_900,button_color=BLUE,
                            button_hover_color=BLUE_L,text_color=ON,width=width,command=lambda _v:self.render_preview())
        m.set(default); self.material_menus.append(m); return m

    def _body(self):
        body=ctk.CTkFrame(self,fg_color="transparent"); body.grid(row=1,column=0,sticky="nsew",padx=18,pady=16)
        body.grid_columnconfigure(0,weight=0,minsize=560); body.grid_columnconfigure(1,weight=1); body.grid_rowconfigure(0,weight=1)
        self._inputs(body); self._preview_card(body)

    def _inputs(self,parent):
        card=self._card(parent,"Inputs"); card.grid(row=0,column=0,sticky="nsew",padx=(0,12))
        seg=ctk.CTkSegmentedButton(card,values=["Parametric","CSV trace"],command=self._set_mode,font=self.uf,fg_color=NAVY_900,
             selected_color=BLUE,selected_hover_color=BLUE_L,unselected_color=NAVY_900,text_color=SOFT)
        seg.set("Parametric"); seg.pack(fill="x",padx=18,pady=(0,10))

        self.param_page=ctk.CTkScrollableFrame(card,fg_color="transparent",height=520)
        self.entries={}; self.opt={}

        # 1) BASE FEATURE (the starting point the steps act on — defined first)
        bs=ctk.CTkFrame(self.param_page,fg_color="transparent"); bs.pack(fill="x",pady=(0,4)); bs.grid_columnconfigure(2,weight=1)
        ctk.CTkLabel(bs,text="BASE FEATURE  (the starting point the steps act on)",font=self.eb,text_color=BLUE_L).grid(row=0,column=0,columnspan=3,sticky="w",padx=8,pady=(4,2))
        self.base_shape=ctk.CTkSegmentedButton(bs,values=["Blank","Substrate","Trench"],command=lambda _v:self.render_preview(),font=self.uf,
                        fg_color=NAVY_900,selected_color=BLUE,selected_hover_color=BLUE_L,unselected_color=NAVY_900,text_color=SOFT)
        self.base_shape.set("Blank"); self._row(bs,1,"Base",
            "Blank = empty canvas (build up with deposits). Substrate = flat slab. Trench = rectangular trench in surround + mask.",self.base_shape)
        for i,(k,label,default,info) in enumerate(FIELDS,2):
            e=ctk.CTkEntry(bs,font=self.mono,fg_color=NAVY_900,border_color=NAVY_700,text_color=ON,width=120)
            e.insert(0,default); e.bind("<KeyRelease>",self._schedule_render); self._row(bs,i,label,info,e); self.entries[k]=e

        # 2) MATERIALS & MASK
        ms=ctk.CTkFrame(self.param_page,fg_color="transparent"); ms.pack(fill="x",pady=(4,4)); ms.grid_columnconfigure(2,weight=1)
        ctk.CTkLabel(ms,text="MATERIALS & MASK",font=self.eb,text_color=BLUE_L).grid(row=0,column=0,columnspan=3,sticky="w",padx=8,pady=(4,2))
        self.opt["surround_material"]=self._mat_menu(ms,"silicon"); self._row(ms,1,"Surround","Bulk material of the trench/substrate.",self.opt["surround_material"])
        ctk.CTkLabel(ms,text="MASK STACK  (bottom → top; each a band with the opening)",font=ctk.CTkFont(family="JetBrains Mono",size=11),text_color=BLUE_L).grid(row=2,column=0,columnspan=3,sticky="w",padx=8,pady=(8,2))
        self.mask_container=ctk.CTkFrame(ms,fg_color="transparent"); self.mask_container.grid(row=3,column=0,columnspan=3,sticky="ew",padx=2)
        self.mask_rows=[]
        for mat,ht in [("hardmask",20),("photoresist",30)]:
            self.mask_rows.append(MaskLayerRow(self,mat,ht))
        self._relayout_mask()
        ctk.CTkButton(ms,text="＋ Add mask layer",command=self._add_mask_layer,font=self.uf,fg_color="transparent",border_width=1,
                      border_color=BLUE_L,text_color=ON,hover_color=NAVY_700).grid(row=4,column=0,columnspan=3,sticky="ew",padx=8,pady=(2,6))
        self.mask_shape=ctk.CTkSegmentedButton(ms,values=["Square","Facet","Round"],command=lambda _v:self.render_preview(),font=self.uf,
                        fg_color=NAVY_900,selected_color=BLUE,selected_hover_color=BLUE_L,unselected_color=NAVY_900,text_color=SOFT)
        self.mask_shape.set("Square"); self._row(ms,5,"Top-mask shape","Corner style of the topmost mask layer (symmetric).",self.mask_shape)
        self.entries["mask_facet_angle"]=ctk.CTkEntry(ms,font=self.mono,fg_color=NAVY_900,border_color=NAVY_700,text_color=ON,width=120)
        self.entries["mask_facet_angle"].insert(0,"60"); self.entries["mask_facet_angle"].bind("<KeyRelease>",self._schedule_render)
        self._row(ms,6,"Facet angle (°)","Facet sidewall angle from horizontal; 90 = square.",self.entries["mask_facet_angle"])
        self.entries["mask_radius"]=ctk.CTkEntry(ms,font=self.mono,fg_color=NAVY_900,border_color=NAVY_700,text_color=ON,width=120)
        self.entries["mask_radius"].insert(0,"12"); self.entries["mask_radius"].bind("<KeyRelease>",self._schedule_render)
        self._row(ms,7,"Round radius (nm)","Corner radius when shape = Round.",self.entries["mask_radius"])
        ctk.CTkButton(ms,text="＋ Add material",command=self._add_material,font=self.uf,fg_color="transparent",border_width=1,
                      border_color=BLUE_L,text_color=ON,hover_color=NAVY_700).grid(row=8,column=0,columnspan=3,sticky="ew",padx=8,pady=(8,4))

        # 3) PROCESS STACK
        ps=ctk.CTkFrame(self.param_page,fg_color="transparent"); ps.pack(fill="x",pady=(4,8))
        ctk.CTkLabel(ps,text="PROCESS STACK",font=self.eb,text_color=BLUE_L).pack(anchor="w",padx=6)
        ctk.CTkLabel(ps,text="Steps run in order: ① at the top happens first, then ②, ③ … each acts on the result of the steps above it. A Repeat block runs its steps ×N (for multilayer stacks).",
                     font=ctk.CTkFont(size=11),text_color=MUT,wraplength=500,justify="left").pack(anchor="w",padx=6,pady=(0,6))
        addbar=ctk.CTkFrame(ps,fg_color="transparent"); addbar.pack(fill="x",padx=4)
        for text,kind in [("＋ Deposit","deposit"),("＋ Fill","fill"),("＋ Etch","etch"),("＋ Planarize","planarize")]:
            ctk.CTkButton(addbar,text=text,command=lambda k=kind:self.stack.add_op(k),font=self.uf,fg_color=NAVY_900,
                          border_width=1,border_color=BLUE_L,text_color=ON,hover_color=NAVY_700,width=10).pack(side="left",expand=True,fill="x",padx=2)
        ctk.CTkButton(ps,text="⟳ Add Repeat block  (for multilayer / superlattice stacks)",command=lambda:self.stack.add_repeat(),
                      font=self.uf,fg_color=NAVY_900,border_width=1,border_color=GREEN,text_color=GREEN,hover_color=NAVY_700).pack(fill="x",padx=4,pady=(4,0))
        self.op_container=ctk.CTkFrame(ps,fg_color="transparent"); self.op_container.pack(fill="x",pady=4)
        self.empty_hint=ctk.CTkLabel(ps,text="No steps yet — add one above to start building.",font=ctk.CTkFont(size=11),text_color=MUT)
        self.stack=OpList(self, self.op_container, empty_hint=self.empty_hint); self.empty_hint.pack(anchor="w",padx=6)
        ctk.CTkButton(ps,text="↺ Reset  (clear everything → blank canvas)",command=self._reset,font=self.uf,fg_color="transparent",
                      border_width=1,border_color=NAVY_700,text_color=SOFT,hover_color=NAVY_700).pack(fill="x",padx=4,pady=(6,0))

        # ---- csv page ----
        self.csv_page=ctk.CTkScrollableFrame(card,fg_color="transparent",height=520); self.csv_page.grid_columnconfigure(2,weight=1)
        ctk.CTkButton(self.csv_page,text="Load CSV…",command=self._load_csv,font=self.uf,fg_color="transparent",border_width=1,
                      border_color=BLUE_L,text_color=ON,hover_color=NAVY_700).grid(row=0,column=0,columnspan=3,sticky="ew",padx=8,pady=(6,4))
        self.csv_label=ctk.CTkLabel(self.csv_page,text="no file loaded",font=self.mono,text_color=MUT); self.csv_label.grid(row=1,column=0,columnspan=3,sticky="w",padx=8)
        self.csv_note=ctk.CTkLabel(self.csv_page,text="",font=self.eb,text_color=GREEN,wraplength=380,justify="left"); self.csv_note.grid(row=2,column=0,columnspan=3,sticky="w",padx=8,pady=(4,8))
        self.csv_fill=self._mat_menu(self.csv_page,"silicon"); self._row(self.csv_page,3,"Fill material","Color used to fill the trace feature.",self.csv_fill)

        common=ctk.CTkFrame(card,fg_color="transparent"); common.pack(fill="x",padx=10,pady=(2,8)); common.grid_columnconfigure(2,weight=1)
        self.scale_entry=ctk.CTkEntry(common,font=self.mono,fg_color=NAVY_900,border_color=NAVY_700,text_color=ON,width=120)
        self.scale_entry.insert(0,"0.4"); self.scale_entry.bind("<KeyRelease>",self._schedule_render)
        self._row(common,0,"Scale (nm/px)","Nanometers per pixel.",self.scale_entry)

    def _preview_card(self,parent):
        card=self._card(parent,"Preview"); card.grid(row=0,column=1,sticky="nsew")
        fr=ctk.CTkFrame(card,fg_color=NAVY_900,corner_radius=10); fr.pack(expand=True,fill="both",padx=18,pady=6)
        self.preview=ctk.CTkLabel(fr,text="",fg_color=NAVY_900); self.preview.pack(expand=True,fill="both",padx=10,pady=10)
        self.legend=ctk.CTkFrame(card,fg_color="transparent"); self.legend.pack(fill="x",padx=18,pady=(0,4))
        bar=ctk.CTkFrame(card,fg_color="transparent"); bar.pack(fill="x",padx=18,pady=(4,16)); bar.grid_columnconfigure(0,weight=1)
        self.out_entry=ctk.CTkEntry(bar,font=self.mono,fg_color=NAVY_900,border_color=NAVY_700,text_color=ON); self.out_entry.insert(0,"outputs/profile.bmp"); self.out_entry.grid(row=0,column=0,sticky="ew",padx=(0,10))
        ctk.CTkButton(bar,text="Render",command=self.render_preview,font=self.uf,width=90,fg_color="transparent",border_width=1,border_color=BLUE_L,text_color=ON,hover_color=NAVY_700).grid(row=0,column=1,padx=(0,8))
        ctk.CTkButton(bar,text="Save .bmp",command=self.save_bmp,font=self.ub,width=120,fg_color=GREEN,hover_color=GREEN_D,text_color=GREEN_INK).grid(row=0,column=2)

    def _footer(self):
        ctk.CTkLabel(self,text="Symmetric · 24-bit BMP · 2D-polygon process model",font=self.eb,text_color=MUT).grid(row=2,column=0,sticky="w",padx=22,pady=(0,10))

    def _set_mode(self,value):
        self.mode=value; self.param_page.pack_forget(); self.csv_page.pack_forget()
        (self.param_page if value=="Parametric" else self.csv_page).pack(fill="both",expand=True,padx=10); self.render_preview()

    def _update_menus(self):
        names=self.palette.names()
        def rows(lst):
            out=[]
            for r in lst.rows:
                if isinstance(r,OpRow): out.append(r.mat)
                elif isinstance(r,RepeatRow): out+=rows(r.sub)
            return out
        for om in self.material_menus+rows(self.stack)+[r.mat for r in self.mask_rows]:
            cur=om.get(); om.configure(values=names); om.set(cur)

    def _add_mask_layer(self, material="oxide", height=12):
        self.mask_rows.append(MaskLayerRow(self, material, height)); self._relayout_mask(); self.render_preview()
    def _remove_mask_layer(self,row):
        row.frame.destroy(); self.mask_rows.remove(row); self._relayout_mask(); self.render_preview()
    def _relayout_mask(self):
        for r in self.mask_rows:
            r.frame.pack_forget(); r.frame.pack(fill="x",padx=4,pady=3)

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
                try: self.palette.save(_DEFAULT_CONFIG)
                except OSError: pass
                self._update_menus()
            dlg.destroy()
        ctk.CTkButton(dlg,text="Add",command=commit,font=self.ub,width=90,fg_color=GREEN,hover_color=GREEN_D,text_color=GREEN_INK).pack(side="right",padx=16,pady=10)

    def _load_csv(self):
        from tkinter import filedialog
        path=filedialog.askopenfilename(filetypes=[("CSV","*.csv")])
        if not path: return
        self.csv_path=Path(path); self.csv_label.configure(text=self.csv_path.name)
        try:
            fitted=trace_to_parametric(load_trace(self.csv_path))
            for k in ("bow","bow_height","mid_width"): self.entries[k].delete(0,"end")
            for k,v in fitted.items():
                if k in self.entries: self.entries[k].delete(0,"end"); self.entries[k].insert(0,str(v))
            self.csv_note.configure(text="✓ Parametric fields populated from CSV (approx). Pitch/mask not in CSV — set manually.")
        except Exception as exc:
            self.csv_note.configure(text=f"Could not fit: {exc}")
        self.render_preview()

    def _mask_corner(self):
        return {"Square":"square","Facet":"facet","Round":"round"}[self.mask_shape.get()]

    def _params(self):
        p={}
        for k,e in self.entries.items():
            v=e.get().strip()
            if v:
                try: p[k]=float(v)
                except ValueError: pass
        p["surround_material"]=self.opt["surround_material"].get()
        p["mask_layers"]=[r.to_layer() for r in self.mask_rows]
        p["mask_corner"]=self._mask_corner()
        p["base_type"]={"Blank":"blank","Substrate":"substrate","Trench":"trench"}[self.base_shape.get()]
        return p

    def _scale(self):
        try: return float(self.scale_entry.get())
        except ValueError: return 0.4

    def _render_to(self,out_path):
        npp=self._scale()
        if self.mode=="CSV trace" and self.csv_path:
            fill=self.csv_fill.get(); fb=None if fill=="vacuum" else self.palette.bgr(fill)
            render_trace_csv(self.csv_path,out_path,npp,fill_bgr=fb); self._last_state=None
        else:
            base=proc.build_base(self._params()); st=proc.evaluate(base,self.stack.to_ops())
            proc.render_regions(st,self.palette,out_path,npp); self._last_state=st

    def _reset(self):
        self.stack.clear()
        for k,label,default,info in FIELDS:
            self.entries[k].delete(0,"end"); self.entries[k].insert(0,default)
        self.entries["mask_facet_angle"].delete(0,"end"); self.entries["mask_facet_angle"].insert(0,"60")
        self.entries["mask_radius"].delete(0,"end"); self.entries["mask_radius"].insert(0,"12")
        self.opt["surround_material"].set("silicon")
        for r in list(self.mask_rows): r.frame.destroy()
        self.mask_rows=[]
        for mat,ht in [("hardmask",20),("photoresist",30)]:
            self.mask_rows.append(MaskLayerRow(self,mat,ht))
        self._relayout_mask()
        self.mask_shape.set("Square"); self.base_shape.set("Blank")
        self.scale_entry.delete(0,"end"); self.scale_entry.insert(0,"0.4")
        self.render_preview()

    def _update_legend(self):
        for w in self.legend.winfo_children(): w.destroy()
        if self.mode=="CSV trace": mats=[self.csv_fill.get()]
        elif self._last_state is not None:
            mats=[]; 
            for m,_ in self._last_state.regions:
                if m not in mats: mats.append(m)
        else: mats=[]
        for mat in mats:
            chip=ctk.CTkFrame(self.legend,fg_color="transparent"); chip.pack(side="left",padx=(0,12))
            sw=ctk.CTkFrame(chip,width=14,height=14,corner_radius=3,fg_color=self.palette.hex(mat),border_width=1,border_color=NAVY_700); sw.pack(side="left",padx=(0,5)); sw.pack_propagate(False)
            ctk.CTkLabel(chip,text=mat,font=self.eb,text_color=SOFT).pack(side="left")

    def _schedule_render(self,_e=None):
        if getattr(self,"_job",None): self.after_cancel(self._job)
        self._job=self.after(120,self.render_preview)

    def render_preview(self):
        self._job=None
        try:
            tmp=Path(tempfile.gettempdir())/"_ipu_preview.bmp"; self._render_to(tmp)
            disp=compose_preview(tmp,self._scale(),target_h=440)
            self.preview.configure(image=ctk.CTkImage(light_image=disp,dark_image=disp,size=disp.size),text="")
            self._update_legend()
        except Exception as exc:
            self.preview.configure(image=None,text=f"⚠ {exc}",text_color=MUT)

    def save_bmp(self):
        out=Path(self.out_entry.get().strip() or "outputs/profile.bmp"); out.parent.mkdir(parents=True,exist_ok=True)
        self._render_to(out); self.title(f"Incoming Profile Utility — saved {out.name}")


def launch():
    ProfileStudio().mainloop()

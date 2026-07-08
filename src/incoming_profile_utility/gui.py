"""Incoming Profile Utility — GUI (customtkinter), SandBox brand theme.

Parametric mode builds an incoming structure from a **material stack** (ordered
material layers, defined first) plus a base feature (pitch + a centered opening of
width = space), then runs an ordered **process stack** of operations on it. Live
preview, nm grid, material legend. CSV mode renders a width/height trace.
"""
from __future__ import annotations

import math
import tempfile
import tkinter as tk
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
    ("pitch","Pitch (nm)","120","Width of one repeating unit cell = line + opening."),
    ("space","Space · opening (nm)","50","Width of the centered opening cut through the stack. line width = pitch − space."),
    ("opening_depth","Opening depth (nm)","","How far down from the TOP of the stack the opening is cut. Blank = all the way through."),
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
    """Lightweight hover tooltip that reliably hides on leave (tk.Toplevel + auto-hide)."""
    _active=None
    def __init__(self,widget,text):
        self.w=widget; self.t=text; self.tip=None; self._show_job=None; self._hide_job=None
        widget.bind("<Enter>", self._enter, add="+")
        widget.bind("<Leave>", self._leave, add="+")
        widget.bind("<Button-1>", self._leave, add="+")
        widget.bind("<Destroy>", self._leave, add="+")
    def _enter(self,_=None):
        self._cancel_jobs(); self._show_job=self.w.after(300, self._show)
    def _show(self):
        if self.tip or not self.t: return
        if Tooltip._active is not None:
            try: Tooltip._active.destroy()
            except Exception: pass
            Tooltip._active=None
        x=self.w.winfo_rootx()+20; y=self.w.winfo_rooty()+22
        self.tip=tk.Toplevel(self.w); self.tip.wm_overrideredirect(True); self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip,text=self.t,justify="left",wraplength=260,bg=NAVY_700,fg=ON,
                 font=("",9),padx=8,pady=6,bd=0).pack()
        Tooltip._active=self.tip
        self._hide_job=self.w.after(6000, self._leave)   # safety auto-hide
    def _cancel_jobs(self):
        for j in (self._show_job,self._hide_job):
            if j:
                try: self.w.after_cancel(j)
                except Exception: pass
        self._show_job=self._hide_job=None
    def _leave(self,_=None):
        self._cancel_jobs()
        if self.tip:
            try: self.tip.destroy()
            except Exception: pass
            if Tooltip._active is self.tip: Tooltip._active=None
            self.tip=None


class MaterialLayerRow:
    """One layer of the material stack: material + thickness (bottom -> top)."""
    def __init__(self, app, material, thickness):
        self.app=app
        self.frame=ctk.CTkFrame(app.matstack_container, fg_color=NAVY_900, corner_radius=8, border_width=1, border_color=NAVY_700)
        self.badge=ctk.CTkFrame(self.frame, fg_color=BLUE, corner_radius=999, width=22, height=22)
        self.badge.pack(side="left", padx=(10,8), pady=7); self.badge.pack_propagate(False)
        self.badge_lbl=ctk.CTkLabel(self.badge, text="1", font=app.eb, text_color=ON); self.badge_lbl.pack(expand=True)
        self.mat=ctk.CTkOptionMenu(self.frame, values=app.palette.names(), width=150, font=app.uf, fg_color=NAVY_800,
                     button_color=BLUE, button_hover_color=BLUE_L, text_color=ON, command=lambda _v: app.render_preview())
        self.mat.set(material); self.mat.pack(side="left", padx=(2,6), pady=7)
        self.th=ctk.CTkEntry(self.frame, width=54, font=app.mono, fg_color=NAVY_800, border_color=NAVY_700, text_color=ON)
        self.th.insert(0,str(thickness)); self.th.bind("<KeyRelease>", app._schedule_render); self.th.pack(side="left", padx=(2,2))
        ctk.CTkLabel(self.frame, text="nm thick", font=app.eb, text_color=MUT).pack(side="left")
        for sym,cmd in (("↑",lambda:app._move_matlayer(self,-1)),("↓",lambda:app._move_matlayer(self,1)),("✕",lambda:app._remove_matlayer(self))):
            ctk.CTkButton(self.frame, text=sym, width=24, font=app.uf, fg_color="transparent", border_width=1,
                          border_color=NAVY_700, text_color=SOFT, hover_color=NAVY_700, command=cmd).pack(side="left", padx=1)
    def to_layer(self):
        try: t=float(self.th.get())
        except ValueError: t=0.0
        return dict(material=self.mat.get(), thickness=t)


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
        self.sub=OpList(app, self.subcont); self.sub.add_op("deposit")
    def to_op(self):
        try: n=int(float(self.times.get()))
        except ValueError: n=1
        return dict(op="repeat", times=max(1,n), steps=self.sub.to_ops())


class OpList:
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
        self.material_menus=[]; self.matlayer_rows=[]; self._last_state=None
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
        self.entries={}

        # 1) MATERIAL STACK (defined first)
        matf=ctk.CTkFrame(self.param_page,fg_color="transparent"); matf.pack(fill="x",pady=(0,6))
        ctk.CTkLabel(matf,text="MATERIAL STACK  (bottom → top)",font=self.eb,text_color=BLUE_L).pack(anchor="w",padx=6)
        ctk.CTkLabel(matf,text="The incoming film stack: each layer is a material + thickness (nm). Stack height = sum of thicknesses.",
                     font=ctk.CTkFont(size=11),text_color=MUT,wraplength=500,justify="left").pack(anchor="w",padx=6,pady=(0,4))
        self.matstack_container=ctk.CTkFrame(matf,fg_color="transparent"); self.matstack_container.pack(fill="x")
        self.matstack_hint=ctk.CTkLabel(matf,text="No layers yet — add one to start the stack.",font=ctk.CTkFont(size=11),text_color=MUT)
        self.matstack_hint.pack(anchor="w",padx=6)
        addrow=ctk.CTkFrame(matf,fg_color="transparent"); addrow.pack(fill="x",padx=4,pady=(4,0))
        ctk.CTkButton(addrow,text="＋ Add material layer",command=lambda:self._add_matlayer(),font=self.uf,fg_color=NAVY_900,
                      border_width=1,border_color=BLUE_L,text_color=ON,hover_color=NAVY_700).pack(side="left",expand=True,fill="x",padx=2)
        ctk.CTkButton(addrow,text="＋ New material (color)",command=self._add_material,font=self.uf,fg_color="transparent",
                      border_width=1,border_color=NAVY_700,text_color=SOFT,hover_color=NAVY_700).pack(side="left",expand=True,fill="x",padx=2)

        # 2) BASE FEATURE (pitch + opening)
        bs=ctk.CTkFrame(self.param_page,fg_color="transparent"); bs.pack(fill="x",pady=(8,4)); bs.grid_columnconfigure(2,weight=1)
        ctk.CTkLabel(bs,text="BASE FEATURE",font=self.eb,text_color=BLUE_L).grid(row=0,column=0,columnspan=3,sticky="w",padx=8,pady=(4,2))
        for i,(k,label,default,info) in enumerate(FIELDS,1):
            e=ctk.CTkEntry(bs,font=self.mono,fg_color=NAVY_900,border_color=NAVY_700,text_color=ON,width=120)
            e.insert(0,default); e.bind("<KeyRelease>",self._schedule_render); self._row(bs,i,label,info,e); self.entries[k]=e

        # 3) PROCESS STACK
        ps=ctk.CTkFrame(self.param_page,fg_color="transparent"); ps.pack(fill="x",pady=(8,8))
        ctk.CTkLabel(ps,text="PROCESS STACK",font=self.eb,text_color=BLUE_L).pack(anchor="w",padx=6)
        ctk.CTkLabel(ps,text="Steps run in order: ① at the top happens first, then ②, ③ … each acts on the result above it. A Repeat block runs its steps ×N.",
                     font=ctk.CTkFont(size=11),text_color=MUT,wraplength=500,justify="left").pack(anchor="w",padx=6,pady=(0,6))
        addbar=ctk.CTkFrame(ps,fg_color="transparent"); addbar.pack(fill="x",padx=4)
        for text,kind in [("＋ Deposit","deposit"),("＋ Fill","fill"),("＋ Etch","etch"),("＋ Planarize","planarize")]:
            ctk.CTkButton(addbar,text=text,command=lambda k=kind:self.stack.add_op(k),font=self.uf,fg_color=NAVY_900,
                          border_width=1,border_color=BLUE_L,text_color=ON,hover_color=NAVY_700,width=10).pack(side="left",expand=True,fill="x",padx=2)
        ctk.CTkButton(ps,text="⟳ Add Repeat block  (multilayer / superlattice)",command=lambda:self.stack.add_repeat(),
                      font=self.uf,fg_color=NAVY_900,border_width=1,border_color=GREEN,text_color=GREEN,hover_color=NAVY_700).pack(fill="x",padx=4,pady=(4,0))
        self.op_container=ctk.CTkFrame(ps,fg_color="transparent"); self.op_container.pack(fill="x",pady=4)
        self.empty_hint=ctk.CTkLabel(ps,text="No steps yet.",font=ctk.CTkFont(size=11),text_color=MUT)
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

    # ---- material stack management ----
    def _add_matlayer(self, material="silicon", thickness=20):
        self.matlayer_rows.append(MaterialLayerRow(self, material, thickness)); self._relayout_matstack(); self.render_preview()
    def _remove_matlayer(self,row):
        row.frame.destroy(); self.matlayer_rows.remove(row); self._relayout_matstack(); self.render_preview()
    def _move_matlayer(self,row,delta):
        i=self.matlayer_rows.index(row); j=i+delta
        if 0<=j<len(self.matlayer_rows):
            self.matlayer_rows[i],self.matlayer_rows[j]=self.matlayer_rows[j],self.matlayer_rows[i]; self._relayout_matstack(); self.render_preview()
    def _relayout_matstack(self):
        for n,row in enumerate(self.matlayer_rows,1):
            row.frame.pack_forget(); row.frame.pack(fill="x",padx=6,pady=3); row.badge_lbl.configure(text=str(n))
        self.matstack_hint.pack_forget()
        if not self.matlayer_rows: self.matstack_hint.pack(anchor="w",padx=6)

    def _update_menus(self):
        names=self.palette.names()
        def orows(lst):
            out=[]
            for r in lst.rows:
                if isinstance(r,OpRow): out.append(r.mat)
                elif isinstance(r,RepeatRow): out+=orows(r.sub)
            return out
        for om in self.material_menus+orows(self.stack)+[r.mat for r in self.matlayer_rows]:
            cur=om.get(); om.configure(values=names); om.set(cur)

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
        self.csv_note.configure(text="✓ Loaded. The CSV trace renders directly (symmetric width/height profile).")
        self.render_preview()

    def _params(self):
        p={}
        for k,e in self.entries.items():
            v=e.get().strip()
            if v:
                try: p[k]=float(v)
                except ValueError: pass
        p["material_layers"]=[r.to_layer() for r in self.matlayer_rows]
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
        for r in list(self.matlayer_rows): r.frame.destroy()
        self.matlayer_rows=[]; self._relayout_matstack()
        for k,label,default,info in FIELDS:
            self.entries[k].delete(0,"end"); self.entries[k].insert(0,default)
        self.scale_entry.delete(0,"end"); self.scale_entry.insert(0,"0.4")
        self.render_preview()

    def _update_legend(self):
        for w in self.legend.winfo_children(): w.destroy()
        if self.mode=="CSV trace": mats=[self.csv_fill.get()]
        elif self._last_state is not None:
            mats=[]
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

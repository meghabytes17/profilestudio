"""Incoming Profile Utility — GUI (customtkinter), SandBox brand theme."""
from __future__ import annotations

import math
import tempfile
import tkinter as tk
from pathlib import Path

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont

from .materials import load_palette, _DEFAULT_CONFIG
from .io_csv import load_trace
from . import process as proc

NAVY="#0E1B2E"; NAVY_900="#0B1626"; NAVY_800="#132540"; NAVY_700="#1C2C46"
BLUE="#283D5D"; BLUE_L="#6E90C6"; GREEN="#4FD093"; GREEN_D="#0E7A49"; GREEN_INK="#07271A"
ON="#FFFFFF"; SOFT="#AEB9C8"; MUT="#8B99AC"

FIELDS = [
    ("pitch","Pitch (nm)","120","Width of one repeating unit cell = line + opening."),
    ("space","Space · opening (nm)","50","Width of the centered opening. line width = pitch − space."),
    ("opening_depth","Opening depth (nm)","","How far down from the TOP the opening is cut. Blank = all the way through."),
    ("top_vacuum","Top vacuum (nm)","20","Empty space above the stack (room to deposit on top)."),
]
OP_LABELS = ["Deposit · conformal","Deposit · planar","Fill","Etch","Planarize"]
OP_PRESETS = {"deposit":("Deposit · conformal","oxide",8),"fill":("Fill","tungsten",0),
              "etch":("Etch","oxide",5),"planarize":("Planarize","oxide",240)}


def _op_to_row(op):
    o=op.get("op")
    if o=="conformal_deposit": return ("Deposit · conformal", op.get("material","oxide"), op.get("thickness",0), 1.0)
    if o=="planar_deposit":    return ("Deposit · planar", op.get("material","oxide"), op.get("thickness",0), 1.0)
    if o=="fill":              return ("Fill", op.get("material","tungsten"), 0, 1.0)
    if o=="etch":              return ("Etch", "oxide", op.get("depth",0), op.get("anisotropy",1.0))
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
    def __init__(self, app, material, thickness):
        self.app=app
        self.frame=ctk.CTkFrame(app.matstack_container, fg_color=NAVY_900, corner_radius=8, border_width=1, border_color=NAVY_700)
        self.grip=ctk.CTkLabel(self.frame, text="⠿", font=app.ub, text_color=MUT, cursor="fleur", width=16)
        self.grip.pack(side="left", padx=(8,2))
        self.grip.bind("<ButtonPress-1>", lambda e: app._drag_start(self))
        self.grip.bind("<ButtonRelease-1>", lambda e: app._drag_drop(self))
        self.badge=ctk.CTkFrame(self.frame, fg_color=BLUE, corner_radius=999, width=20, height=20); self.badge.pack(side="left", padx=(2,6), pady=7); self.badge.pack_propagate(False)
        self.badge_lbl=ctk.CTkLabel(self.badge, text="1", font=app.eb, text_color=ON); self.badge_lbl.pack(expand=True)
        self.sw=ctk.CTkFrame(self.frame, width=16, height=16, corner_radius=3, fg_color=app.palette.hex(material), border_width=1, border_color=NAVY_700)
        self.sw.pack(side="left", padx=(0,6)); self.sw.pack_propagate(False)
        self.mat=ctk.CTkOptionMenu(self.frame, values=app.palette.names(), width=140, font=app.uf, fg_color=NAVY_800,
                     button_color=BLUE, button_hover_color=BLUE_L, text_color=ON, command=self._on_mat)
        self.mat.set(material); self.mat.pack(side="left", padx=(0,6), pady=7)
        self.th=ctk.CTkEntry(self.frame, width=52, font=app.mono, fg_color=NAVY_800, border_color=NAVY_700, text_color=ON)
        self.th.insert(0,str(thickness)); self.th.bind("<KeyRelease>", app._schedule_render); self.th.pack(side="left", padx=(0,2))
        ctk.CTkLabel(self.frame, text="nm", font=app.eb, text_color=MUT).pack(side="left")
        for sym,cmd in (("✕",lambda:app._remove_matlayer(self)),("↓",lambda:app._move_matlayer(self,1)),("↑",lambda:app._move_matlayer(self,-1))):
            ctk.CTkButton(self.frame, text=sym, width=24, font=app.uf, fg_color="transparent", border_width=1,
                          border_color=NAVY_700, text_color=SOFT, hover_color=NAVY_700, command=cmd).pack(side="right", padx=1)
    def _on_mat(self,_v):
        self.sw.configure(fg_color=self.app.palette.hex(self.mat.get())); self.app.render_preview()
    def to_layer(self):
        try: t=float(self.th.get())
        except ValueError: t=0.0
        return dict(material=self.mat.get(), thickness=t)


class OpRow:
    NEEDS_MAT = ("Deposit · conformal", "Deposit · planar", "Fill")
    def __init__(self, host, op_label, material, num, aniso=1.0):
        self.host=host; app=host.app
        self.frame=ctk.CTkFrame(host.container, fg_color=NAVY_900, corner_radius=8, border_width=1, border_color=NAVY_700)
        for sym,cmd in (("✕",lambda:host.remove(self)),("↓",lambda:host.move(self,1)),("↑",lambda:host.move(self,-1))):
            ctk.CTkButton(self.frame, text=sym, width=24, font=app.uf, fg_color="transparent", border_width=1,
                          border_color=NAVY_700, text_color=SOFT, hover_color=NAVY_700, command=cmd).pack(side="right", padx=1)
        self.badge=ctk.CTkFrame(self.frame, fg_color=BLUE, corner_radius=999, width=20, height=20); self.badge.pack(side="left", padx=(10,8), pady=8); self.badge.pack_propagate(False)
        self.badge_lbl=ctk.CTkLabel(self.badge, text="1", font=app.eb, text_color=ON); self.badge_lbl.pack(expand=True)
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
        et = self.optype.get()=="Etch"
        self.mat.configure(state="normal" if self.optype.get() in self.NEEDS_MAT else "disabled")
        if et: self.aniso_lbl.pack(side="left",padx=(6,1)); self.aniso.pack(side="left")
        else: self.aniso_lbl.pack_forget(); self.aniso.pack_forget()
    def to_op(self):
        lbl=self.optype.get(); mat=self.mat.get()
        try: n=float(self.num.get())
        except ValueError: n=0.0
        if lbl=="Deposit · conformal": return dict(op="conformal_deposit", material=mat, thickness=n)
        if lbl=="Deposit · planar":    return dict(op="planar_deposit", material=mat, thickness=n)
        if lbl=="Fill":                return dict(op="fill", material=mat)
        if lbl=="Etch":
            try: a=float(self.aniso.get())
            except ValueError: a=1.0
            return dict(op="etch", depth=n, anisotropy=a)
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
        self._undo=[]; self._loading=False; self._drag=None; self._last_npp=0.4; self.smooth_var=ctk.BooleanVar(value=False)
        self.uf=ctk.CTkFont(family="Inter",size=13); self.ub=ctk.CTkFont(family="Inter",size=14,weight="bold")
        self.tf=ctk.CTkFont(family="Inter",size=20,weight="bold"); self.mono=ctk.CTkFont(family="JetBrains Mono",size=12)
        self.eb=ctk.CTkFont(family="JetBrains Mono",size=11)
        self.grid_columnconfigure(0,weight=1); self.grid_rowconfigure(1,weight=1)
        self._header(); self._body(); self._footer()
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
        body.grid_columnconfigure(0,weight=0,minsize=580); body.grid_columnconfigure(1,weight=1); body.grid_rowconfigure(0,weight=1)
        self._inputs(body); self._preview_card(body)

    def _inputs(self,parent):
        card=self._card(parent,"Inputs"); card.grid(row=0,column=0,sticky="nsew",padx=(0,12))
        self.param_page=ctk.CTkScrollableFrame(card,fg_color="transparent",height=540)
        self.param_page.pack(fill="both",expand=True,padx=10)
        self.entries={}

        matf=ctk.CTkFrame(self.param_page,fg_color="transparent"); matf.pack(fill="x",pady=(0,6))
        ctk.CTkLabel(matf,text="MATERIAL STACK  (row ① = top)",font=self.eb,text_color=BLUE_L).pack(anchor="w",padx=6)
        ctk.CTkLabel(matf,text="The incoming film stack, top → bottom. Each layer is a material + thickness (nm). Drag ⠿ to reorder.",
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
        ctk.CTkButton(ocsv,text="Load CSV opening…",command=self._load_csv,font=self.uf,fg_color=NAVY_900,border_width=1,
                      border_color=BLUE_L,text_color=ON,hover_color=NAVY_700).pack(side="left",expand=True,fill="x",padx=2)
        ctk.CTkButton(ocsv,text="Clear",command=self._clear_csv,font=self.uf,fg_color="transparent",border_width=1,
                      border_color=NAVY_700,text_color=SOFT,hover_color=NAVY_700,width=70).pack(side="left",padx=2)
        self.csv_label=ctk.CTkLabel(bs,text="Opening: rectangular (from Space). Load a CSV to use a trace shape instead.",
                                    font=self.eb,text_color=MUT,wraplength=520,justify="left")
        self.csv_label.grid(row=len(FIELDS)+2,column=0,columnspan=3,sticky="w",padx=8,pady=(2,2))

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
        btns=ctk.CTkFrame(ps,fg_color="transparent"); btns.pack(fill="x",padx=4,pady=(6,0))
        ctk.CTkButton(btns,text="↶ Undo",command=self._undo_action,font=self.uf,fg_color="transparent",border_width=1,
                      border_color=BLUE_L,text_color=ON,hover_color=NAVY_700).pack(side="left",expand=True,fill="x",padx=2)
        ctk.CTkButton(btns,text="↺ Reset",command=self._reset,font=self.uf,fg_color="transparent",border_width=1,
                      border_color=NAVY_700,text_color=SOFT,hover_color=NAVY_700).pack(side="left",expand=True,fill="x",padx=2)

        common=ctk.CTkFrame(card,fg_color="transparent"); common.pack(fill="x",padx=10,pady=(2,8)); common.grid_columnconfigure(2,weight=1)
        self.scale_entry=ctk.CTkEntry(common,font=self.mono,fg_color=NAVY_900,border_color=NAVY_700,text_color=ON,width=120,placeholder_text="auto")
        self.scale_entry.bind("<KeyRelease>",self._schedule_render)
        self._row(common,0,"Resolution (nm/px)","Blank = auto-fit (~900 px on the long side). Set a value to fix the nm-per-pixel calibration (smaller = higher resolution / bigger image).",self.scale_entry)

    def _preview_card(self,parent):
        card=self._card(parent,"Preview"); card.grid(row=0,column=1,sticky="nsew")
        fr=ctk.CTkFrame(card,fg_color=NAVY_900,corner_radius=10); fr.pack(expand=True,fill="both",padx=18,pady=6)
        self.preview=ctk.CTkLabel(fr,text="",fg_color=NAVY_900); self.preview.pack(expand=True,fill="both",padx=10,pady=10)
        self.legend=ctk.CTkFrame(card,fg_color="transparent"); self.legend.pack(fill="x",padx=18,pady=(0,4))
        bar=ctk.CTkFrame(card,fg_color="transparent"); bar.pack(fill="x",padx=18,pady=(4,16)); bar.grid_columnconfigure(0,weight=1)
        ctk.CTkCheckBox(bar,text="Smooth (anti-alias)",variable=self.smooth_var,command=self.render_preview,
                        font=self.eb,text_color=SOFT,fg_color=GREEN,hover_color=GREEN_D,checkbox_width=18,checkbox_height=18).grid(row=0,column=0,sticky="w")
        ctk.CTkButton(bar,text="Render",command=self.render_preview,font=self.uf,width=90,fg_color="transparent",border_width=1,border_color=BLUE_L,text_color=ON,hover_color=NAVY_700).grid(row=0,column=1,padx=(0,8))
        ctk.CTkButton(bar,text="Save .bmp…",command=self.save_bmp,font=self.ub,width=120,fg_color=GREEN,hover_color=GREEN_D,text_color=GREEN_INK).grid(row=0,column=2)

    def _footer(self):
        ctk.CTkLabel(self,text="Symmetric · 24-bit BMP · 2D-polygon process model",font=self.eb,text_color=MUT).grid(row=2,column=0,sticky="w",padx=22,pady=(0,10))

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
    def _relayout_matstack(self):
        for n,row in enumerate(self.matlayer_rows,1):
            row.frame.pack_forget(); row.frame.pack(fill="x",padx=6,pady=3); row.badge_lbl.configure(text=str(n))
        self.matstack_hint.pack_forget()
        if not self.matlayer_rows: self.matstack_hint.pack(anchor="w",padx=6)
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
        return dict(materials=[(r.mat.get(), r.th.get()) for r in self.matlayer_rows],
                    ops=self.stack.to_ops(),
                    fields={k:self.entries[k].get() for k in self.entries},
                    scale=self.scale_entry.get(),
                    trace=self.opening_trace)
    def _capture(self):
        if self._loading: return
        self._undo.append(self._snapshot())
        if len(self._undo)>50: self._undo.pop(0)
    def _undo_action(self):
        if not self._undo: return
        self._load_state(self._undo.pop())
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
            for mat,th in snap["materials"]:
                self.matlayer_rows.append(MaterialLayerRow(self, mat, th))
            self._relayout_matstack()
            self._load_ops(self.stack, snap["ops"])
            for k,v in snap["fields"].items():
                if k in self.entries: self.entries[k].delete(0,"end"); self.entries[k].insert(0,v)
            self.scale_entry.delete(0,"end"); self.scale_entry.insert(0,snap["scale"])
            self.opening_trace=snap.get("trace")
            self.csv_label.configure(
                text=(f"✓ CSV opening loaded ({len(self.opening_trace)} pts)." if self.opening_trace
                      else "Opening: rectangular (from Space). Load a CSV to use a trace shape instead."),
                text_color=(GREEN if self.opening_trace else MUT))
        finally:
            self._loading=False
        self.render_preview()

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
        try:
            df=load_trace(path)
        except Exception as exc:
            self.csv_label.configure(text=f"⚠ {exc}", text_color="#E58B8B"); return
        self._capture()
        self.opening_trace=[(float(w),float(h)) for w,h in zip(df["width"],df["height"])]
        self.csv_label.configure(text=f"✓ Opening from {Path(path).name} ({len(df)} pts). Space & opening-depth ignored while a CSV opening is loaded.", text_color=GREEN)
        self.render_preview()

    def _clear_csv(self):
        if self.opening_trace is not None:
            self._capture(); self.opening_trace=None
            self.csv_label.configure(text="Opening: rectangular (from Space). Load a CSV to use a trace shape instead.", text_color=MUT)
            self.render_preview()

    def _params(self):
        p={}
        for k,e in self.entries.items():
            v=e.get().strip()
            if v:
                try: p[k]=float(v)
                except ValueError: pass
        p["material_layers"]=[r.to_layer() for r in self.matlayer_rows]
        if self.opening_trace: p["opening_trace"]=self.opening_trace
        return p

    def _scale(self):
        v=self.scale_entry.get().strip()
        if not v or v.lower()=="auto": return None
        try: return float(v)
        except ValueError: return None

    def _resolve_npp(self, st):
        manual=self._scale()
        if manual and manual>0: return manual
        minx,miny,maxx,maxy=st.cell.bounds
        dim=max(maxx-minx, maxy-miny, 1.0)
        return max(dim/900.0, 0.02)   # auto: ~900 px on the long side

    def _render_to(self,out_path):
        base=proc.build_base(self._params()); st=proc.evaluate(base,self.stack.to_ops()); self._last_state=st
        npp=self._resolve_npp(st); self._last_npp=npp
        ss = 3 if self.smooth_var.get() else 1
        if ss==1:
            proc.render_regions(st,self.palette,out_path,npp)     # hard pixels, no AA
        else:
            import cv2
            hi=Path(tempfile.gettempdir())/"_ipu_hi.bmp"
            proc.render_regions(st,self.palette,hi,npp/ss)        # supersample
            minx,miny,maxx,maxy=st.cell.bounds
            W=max(1,round((maxx-minx)/npp)); H=max(1,round((maxy-miny)/npp))
            img=cv2.resize(cv2.imread(str(hi)),(W,H),interpolation=cv2.INTER_AREA)
            cv2.imwrite(str(out_path),img)

    def _reset(self):
        self._capture()
        self.stack.clear()
        for r in list(self.matlayer_rows): r.frame.destroy()
        self.matlayer_rows=[]; self._relayout_matstack()
        self.opening_trace=None
        self.csv_label.configure(text="Opening: rectangular (from Space). Load a CSV to use a trace shape instead.", text_color=MUT)
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

    def render_preview(self):
        self._job=None
        if self._loading: return
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

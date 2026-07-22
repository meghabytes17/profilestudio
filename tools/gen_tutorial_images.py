import sys, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0,"src")
from incoming_profile_utility.process import build_base, evaluate, render_regions
from incoming_profile_utility.materials import load_palette
pal=load_palette()
OUT="docs/tutorial_img/"

def render(params, ops, name, npp=0.5):
    st=evaluate(build_base(params), ops)
    render_regions(st, pal, OUT+name, npp)
    print("wrote", name)

# --- Tutorial 1: U-shaped mask (indigo over lavender, round top, U bottom) ---
t1=dict(material_layers=[dict(material="indigo",thickness=200,shape=[dict(kind="round",r=75)]),
                          dict(material="lavender",thickness=55)],
        pitch=210, space=95, top_vacuum=25, opening_depth=200, opening_bottom_radius=47)
render(t1, [], "mask_result.png", npp=0.4)
# "target" = same but a touch simpler (what the user is aiming to reproduce)
render(t1, [], "mask_target.png", npp=0.4)

# --- Tutorial 2: CSV trace result (a curved opening) ---
import numpy as np, pandas as pd, tempfile
h=np.linspace(0,180,40); w=60+40*np.sin(np.pi*h/180)   # a bowed profile
csv=tempfile.NamedTemporaryFile(suffix=".csv",delete=False,mode="w")
pd.DataFrame({"width":w,"height":h}).to_csv(csv.name,index=False); csv.close()
from incoming_profile_utility.io_csv import load_trace
df=load_trace(csv.name, normalize=False)
trace=[(float(a),float(b)) for a,b in zip(df["width"],df["height"])]
t2=dict(material_layers=[dict(material="oxide",thickness=180)],
        pitch=200, top_vacuum=20, opening_trace=trace, opening_ref=None)
render(t2, [], "csv_result.png", npp=0.4)

# --- Tutorial 3: process stack sequence (base -> conformal liner -> fill+planarize) ---
base=dict(material_layers=[dict(material="hardmask",thickness=60),dict(material="silicon",thickness=180)],
          pitch=200, space=80, top_vacuum=20, opening_depth=170, opening_bottom_radius=20)
render(base, [], "ps_1base.png", npp=0.4)
render(base, [dict(op="conformal_deposit",material="nitride",thickness=18)], "ps_2conf.png", npp=0.4)
render(base, [dict(op="conformal_deposit",material="nitride",thickness=18),
              dict(op="fill",material="tungsten"),
              dict(op="planarize",at_height=230)], "ps_3fill.png", npp=0.4)
print("done")

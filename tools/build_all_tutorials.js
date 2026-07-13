const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell,
  WidthType, AlignmentType, BorderStyle, ShadingType, VerticalAlign,
} = require("docx");

// ---- palette / type ----------------------------------------------------------
const NAVY="12233B", BLUE="3E5C86", GREEN="2E9E77", INK="1F2A38", MUT="6B7A8D",
      LINE="CBD6E4", PANEL="F6F9FD", GREENBG="EAF6F0";
const F="Arial";
const img=(p,w,h)=>new ImageRun({type:"png",data:fs.readFileSync(p),transformation:{width:w,height:h}});
const T=(t,o={})=>new TextRun({text:t,size:20,font:F,color:INK,...o});
const B=t=>T(t,{bold:true});
const boxAll=(c,s=4)=>["top","bottom","left","right"].reduce((a,k)=>(a[k]={style:BorderStyle.SINGLE,size:s,color:c},a),{});
const noBorder=()=>["top","bottom","left","right","insideHorizontal","insideVertical"]
  .reduce((a,k)=>(a[k]={style:BorderStyle.NONE,size:0,color:"FFFFFF"},a),{});

const eyebrow=t=>new Paragraph({spacing:{after:30},children:[new TextRun({text:t,color:BLUE,size:16,font:F,bold:true,characterSpacing:20})]});
const title=t=>new Paragraph({spacing:{after:60},children:[new TextRun({text:t,color:NAVY,size:38,font:F,bold:true})]});
const sub=t=>new Paragraph({spacing:{after:60},children:[new TextRun({text:t,color:MUT,size:20,font:F})]});
const rule=()=>new Paragraph({spacing:{after:150},border:{bottom:{style:BorderStyle.SINGLE,size:6,color:LINE,space:8}},children:[new TextRun({text:"",size:2})]});
const sect=t=>new Paragraph({spacing:{before:170,after:70},children:[
  new TextRun({text:"▍",color:GREEN,size:22,font:F}),
  new TextRun({text:" "+t,color:NAVY,size:23,font:F,bold:true})]});
const body=runs=>new Paragraph({spacing:{after:70},children:runs});
const bullet=runs=>new Paragraph({spacing:{after:60},indent:{left:120},children:[new TextRun({text:"•  ",color:GREEN,size:20,font:F,bold:true}),...runs]});
const step=(n,runs)=>new Paragraph({spacing:{after:80},indent:{left:120},children:[new TextRun({text:n+".  ",bold:true,color:GREEN,size:20,font:F}),...runs]});
const caption=t=>new Paragraph({alignment:AlignmentType.CENTER,spacing:{before:60},children:[new TextRun({text:t,italics:true,color:MUT,size:16,font:F})]});
const gap=()=>new Paragraph({spacing:{after:60},children:[new TextRun({text:"",size:2})]});

// framed image panel (used in rows)
function panel(colW,path,iw,ih,cap){
  return new TableCell({width:{size:colW,type:WidthType.DXA},verticalAlign:VerticalAlign.CENTER,
    margins:{top:90,bottom:70,left:90,right:90},shading:{type:ShadingType.CLEAR,fill:PANEL},borders:boxAll(LINE),
    children:[new Paragraph({alignment:AlignmentType.CENTER,children:[img(path,iw,ih)]}),caption(cap)]});
}
function spacer(w){return new TableCell({width:{size:w,type:WidthType.DXA},borders:noBorder(),children:[new Paragraph({children:[new TextRun({text:"",size:2})]})]});}
function panelRow(cols){ // cols: [{path,iw,ih,cap}]
  const W=10040, g=260, colW=Math.floor((W-g*(cols.length-1))/cols.length);
  const widths=[]; const cells=[];
  cols.forEach((c,i)=>{ if(i){widths.push(g);cells.push(spacer(g));} widths.push(colW); cells.push(panel(colW,c.path,c.iw,c.ih,c.cap)); });
  return new Table({width:{size:W,type:WidthType.DXA},columnWidths:widths,borders:noBorder(),rows:[new TableRow({children:cells})]});
}
function tipsBox(lines){
  const kids=[new Paragraph({spacing:{after:30},children:[new TextRun({text:"Tips",bold:true,color:NAVY,size:19,font:F})]})];
  for(const l of lines) kids.push(new Paragraph({spacing:{before:24},indent:{left:80},children:[new TextRun({text:"•  "+l,color:INK,size:18,font:F})]}));
  return new Table({width:{size:10040,type:WidthType.DXA},columnWidths:[10040],borders:boxAll(GREEN,4),
    rows:[new TableRow({children:[new TableCell({width:{size:10040,type:WidthType.DXA},shading:{type:ShadingType.CLEAR,fill:GREENBG},
      margins:{top:110,bottom:110,left:150,right:150},children:kids})]})]});
}
const PAGE={size:{width:12240,height:15840},margin:{top:1000,bottom:800,left:1100,right:1100}};
const D=(children)=>new Document({sections:[{properties:{page:PAGE},children}]});
const IMG="/home/claude/tut/";

// ---- Tutorial 1 --------------------------------------------------------------
const doc1=D([
  eyebrow("SANDBOX · PROFILE STUDIO — TUTORIAL 1"),
  title("Building a U-shaped mask profile"),
  sub("Reproduce a flared mask with a rounded (U) opening bottom using the material stack and per-layer shape treatments."),
  rule(),
  panelRow([
    {path:IMG+"mask_target.png",iw:214,ih:168,cap:"Target — your image"},
    {path:IMG+"mask_result.png",iw:132,ih:168,cap:"Result in Profile Studio"},
  ]),
  sect("Steps"),
  step("1",[B("Material stack"),T(" (row 1 = top). Add "),B("indigo"),T(" 200 nm, then "),B("lavender"),T(" 55 nm.")]),
  step("2",[B("Base feature."),T(" Pitch "),B("210"),T(", Space "),B("95"),T(", Opening depth "),B("200"),T(", Top vacuum "),B("25"),T(".")]),
  step("3",[B("Opening bottom round: 47"),T(" nm (about half of Space) — this makes the U-shaped bottom.")]),
  step("4",[B("Shape the mask."),T(" On the indigo layer press its "),B("shape"),T(" button and add "),B("Round"),T(" radius "),B("75"),T(" for the flared top.")]),
  step("5",[T("The preview updates live as you edit — click "),B("Save .bmp…"),T(" to export the image.")]),
  sect("How the shape treatments work"),
  bullet([B("Round"),T(" softens the top corner, "),B("Taper"),T(" slopes the whole wall, and "),B("Opening bottom round"),T(" curves the base — each shapes a different part.")]),
  bullet([B("Taper"),T(" angle is the sidewall angle from the horizontal base: "),B("90° = vertical"),T(", smaller = more sloped. (Not needed for this mask.)")]),
  bullet([T("You can "),B("stack several treatments"),T(" on one layer — e.g. "),B("Round + Taper"),T(". Use "),B("＋ Add another treatment"),T(" in the shape dialog. They combine and are order-independent.")]),
  sect("Working in the preview"),
  bullet([B("Zoom"),T(" — scroll the wheel over the preview (or use the Zoom slider). Double-click or "),B("Reset"),T(" returns to the full view.")]),
  bullet([B("Move"),T(" — once zoomed in, the cursor becomes a move cursor: drag, or use the arrow keys, to reposition. (At 1x there is nothing to move — the whole profile is already in view.)")]),
  bullet([B("Measure"),T(" — switch to the Measure tool and drag a line across any feature to read its length in nm. Switch back to "),B("Move"),T(" to pan again.")]),
  bullet([B("Smoothing"),T(" (Off / 2x / 4x / 8x) de-jags curved walls. It never blends colours: the .bmp always contains exactly one colour per material.")]),
  bullet([B("Save .bmp…"),T(" exports the picture; "),B("Polygons…"),T(" exports the profile as editable vector shapes (SVG) plus exact nm coordinates (JSON).")]),
  gap(),
  tipsBox([
    "The plot grid keeps a fixed size — only the axis numbers change as you edit.",
    "The shape button on a layer row is enabled only for layers the opening actually reaches.",
    "Toolbar Save stores the whole project; Save .bmp exports just the picture.",
    "Add your own colors with the “＋ New material (color)” button.",
  ]),
]);

// ---- Tutorial 2 --------------------------------------------------------------
function csvTable(){
  const rows=[["width","height"],["0","0"],["22","6"],["36","16"],["48","40"],["56","80"],
    ["62","130"],["64","180"],["62","220"],["58","248"],["60","262"]];
  return new Table({width:{size:2400,type:WidthType.DXA},columnWidths:[1200,1200],borders:boxAll(LINE,2),
    rows:rows.map((r,i)=>new TableRow({children:r.map(c=>new TableCell({width:{size:1200,type:WidthType.DXA},
      shading:i===0?{type:ShadingType.CLEAR,fill:NAVY}:(i%2?{type:ShadingType.CLEAR,fill:PANEL}:undefined),
      margins:{top:26,bottom:26,left:70,right:70},
      children:[new Paragraph({alignment:AlignmentType.CENTER,children:[new TextRun({text:c,size:18,font:"Consolas",bold:i===0,color:i===0?"FFFFFF":INK})]})]}))}))});
}
const doc2=D([
  eyebrow("SANDBOX · PROFILE STUDIO — TUTORIAL 2"),
  title("Using a CSV"),
  sub("Define an arbitrary, curved profile from a width/height trace instead of the rectangular Space opening. A CSV can describe a whole etched profile, not just a simple opening."),
  rule(),
  new Table({width:{size:10040,type:WidthType.DXA},columnWidths:[5540,300,4200],borders:noBorder(),rows:[new TableRow({children:[
    new TableCell({width:{size:5540,type:WidthType.DXA},borders:noBorder(),verticalAlign:VerticalAlign.TOP,children:[
      new Paragraph({spacing:{after:70},children:[new TextRun({text:"The CSV format",bold:true,color:NAVY,size:22,font:F})]}),
      body([T("Two columns, one row per point:")]),
      bullet([B("width"),T(" — the full opening width (CD) at that height. A size, always ≥ 0.")]),
      bullet([B("height"),T(" — the vertical position in nm. May be negative (it's a position).")]),
      bullet([T("The profile is drawn "),B("symmetric"),T(" about the centerline (±width/2).")]),
      gap(), csvTable(), caption("example_profile.csv — a realistic etched trench"),
    ]}),
    spacer(300),
    new TableCell({width:{size:4200,type:WidthType.DXA},borders:boxAll(LINE),shading:{type:ShadingType.CLEAR,fill:PANEL},
      margins:{top:110,bottom:90,left:90,right:90},verticalAlign:VerticalAlign.CENTER,children:[
      new Paragraph({alignment:AlignmentType.CENTER,children:[img(IMG+"csv_result.png",150,220)]}),
      caption("The trace loaded as the profile"),
    ]}),
  ]})]}),
  sect("Steps"),
  step("1",[T("Prepare a CSV with columns "),B("width,height"),T(" (see example). Save it anywhere.")]),
  step("2",[T("In the "),B("OPENING FROM CSV"),T(" section, click "),B("“Load CSV…”"),T(" and choose your file.")]),
  step("3",[B("Placement."),T(" By default the trace is "),B("top-aligned"),T(" (its top sits at the stack top, cutting downward). To pin it elsewhere, set "),B("“CSV height=0 at (nm)”"),T(" — the row where height = 0 lands that many nm from the stack bottom; negative heights sit below that line.")]),
  step("4",[T("While a CSV is active, "),B("Space"),T(" and "),B("Opening depth"),T(" are ignored (they gray out); "),B("Top vacuum"),T(" still applies.")]),
  step("5",[T("If the curved walls look jagged, raise "),B("Smoothing"),T(" (Off / 2× / 4× / 8×) — it de-jags the edges without ever blending colours. Zoom and drag to inspect, use "),B("Measure"),T(" to check a CD, then "),B("Save .bmp…"),T(" to export.")]),
  gap(),
  tipsBox([
    "If the material stack is empty, a silicon base is added automatically so the profile is visible.",
    "Negative width is rejected; ragged rows or blanks are rejected with a clear message.",
    "Points don't need to be pre-sorted — they're ordered by height internally.",
  ]),
]);

// ---- Tutorial 3 --------------------------------------------------------------
const doc3=D([
  eyebrow("SANDBOX · PROFILE STUDIO — TUTORIAL 3"),
  title("The process stack"),
  sub("After the material stack and opening are built, the process stack transforms the profile step by step — the same idea as real fab steps (deposit, fill, etch, polish)."),
  rule(),
  sect("How it works"),
  body([T("Steps run "),B("in order, top to bottom"),T(" (①, then ②, ③ …). Each step acts on the result of the one above it. A "),B("Repeat"),T(" block runs its steps ×N — handy for multilayers / superlattices.")]),
  sect("The step types"),
  bullet([B("Deposit · conformal"),T(" — coats every surface (walls, bottom, top) with a uniform layer that follows the profile. Use it for liners and spacers.")]),
  bullet([B("Deposit · planar"),T(" — adds a flat layer on top only (no sidewall coverage).")]),
  bullet([B("Fill"),T(" — gap-fills the opening flush with the surface. The number is "),B("overfill"),T(" (extra nm of blanket above the surface; 0 = flush).")]),
  bullet([B("Etch · isotropic"),T(" — removes material equally in all directions; rounds corners and undercuts.")]),
  bullet([B("Etch · anisotropic"),T(" — removes material vertically. Anisotropy 1 = fully vertical, 0 = isotropic, in between = a rounded undercut. Pick a material to etch only that one, or “(any)”.")]),
  bullet([B("Planarize"),T(" — cuts everything flat at a height, like chemical-mechanical polish (CMP).")]),
  sect("Worked example — liner + fill + polish"),
  panelRow([
    {path:IMG+"ps_1base.png",iw:114,ih:160,cap:"① bare trench (stack + opening)"},
    {path:IMG+"ps_2conf.png",iw:114,ih:160,cap:"② ＋ Deposit·conformal (nitride liner)"},
    {path:IMG+"ps_3fill.png",iw:114,ih:160,cap:"③ ＋ Fill (tungsten) ＋ Planarize"},
  ]),
  gap(),
  tipsBox([
    "Deposit / Fill can use ANY material in the palette — you don\u2019t need to add liner/fill materials to the stack first. Etch lists the materials present (plus “(any)”).",
    "Etch with a material selected removes only that material; “(any)” removes whatever it reaches.",
    "Build a superlattice with a Repeat block: e.g. deposit A, deposit B, repeated ×10.",
  ]),
]);

(async()=>{
  const out="/mnt/user-data/outputs/";
  fs.writeFileSync(out+"Tutorial-1-mask-profile.docx", await Packer.toBuffer(doc1));
  fs.writeFileSync(out+"Tutorial-2-csv.docx", await Packer.toBuffer(doc2));
  fs.writeFileSync(out+"Tutorial-3-process-stack.docx", await Packer.toBuffer(doc3));
  console.log("all three tutorials written");
})();

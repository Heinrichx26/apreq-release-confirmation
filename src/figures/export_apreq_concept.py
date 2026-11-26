"""Export the APREQ coordination and pushback illustration without running experiments."""
from pathlib import Path
import html
import shutil
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/figures"
OUT.mkdir(parents=True, exist_ok=True)
NAME = "conceptual_information_release"
W, H = 1200, 426
COLORS = {"ink": "#24313b", "muted": "#4a5966", "edge": "#6c7b88"}
# Diagram content is shared by SVG and diagrams.net editable sources.
boxes = [
    ("initial", 245, 110, 210, 66, "Ready group", "agreed pushback order", "#e8f2f8"),
    ("check", 475, 110, 210, 66, "Call center TMC", "ask for one interval", "#fff5e9"),
    ("answer", 705, 110, 210, 66, "Center answers", "delayed, may differ", "#e9f6f1"),
    ("observe", 935, 110, 220, 66, "Observe takeoffs", "update later intervals", "#f1f3f5"),
    ("start", 245, 235, 210, 66, "Push back minimum", "set by deadlines", "#e8f2f8"),
    ("pending", 475, 235, 210, 66, "Hold at gates", "answer still pending", "#fff5e9"),
    ("revise", 705, 235, 210, 66, "Revise pushbacks", "use confirmed count", "#e9f6f1"),
    ("continue", 935, 235, 220, 66, "Take off on time", "−2 to +1 min window", "#f1f3f5"),
]
edges = [("initial", "check"), ("check", "answer"), ("answer", "observe"),
         ("start", "pending"), ("pending", "revise"), ("revise", "continue")]
labels = [
    ("title", 35, 31, "APREQ coordination and pushback decisions", "title"),
    ("information", 30, 137, "Coordination", "lane"),
    ("decision", 30, 262, "Pushback", "lane"),
    ("result", 30, 377, "Result", "lane"),
    ("t0", 245, 76, "Current interval", "small"),
    ("t1", 475, 76, "Answer pending", "small"),
    ("t2", 705, 76, "Answer available", "small"),
    ("t3", 935, 76, "Later intervals", "small"),
]
parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
         '<defs><marker id="arrow" markerWidth="5" markerHeight="5" refX="4.7" refY="2.5" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,5 L5,2.5 z" fill="#526575"/></marker>',
         '<style>.title{font:700 23px Arial,sans-serif;fill:#1e2d3a}.lane{font:700 20px Arial,sans-serif;fill:#1e2d3a}.label{font:22px Arial,sans-serif;fill:#24313b}.small{font:18px Arial,sans-serif;fill:#4a5966}</style></defs>',
         f'<rect width="{W}" height="{H}" fill="#ffffff"/>']
for _, x, y, value, cls in labels:
    parts.append(f'<text x="{x}" y="{y}" class="{cls}">{html.escape(value)}</text>')
parts.append('<path d="M245 88 H1155" stroke="#a5b1bb" stroke-width="1.2"/>')
for x in [245,475,705,935,1155]:
    parts.append(f'<path d="M{x} 88 V320" stroke="#e1e6eb" stroke-width="1"/>')
by_id={b[0]:b for b in boxes}
for idv,x,y,w,h,title,sub,fill in boxes:
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="{fill}" stroke="#6c7b88" stroke-width="1.3"/>')
    parts.append(f'<text x="{x+w/2}" y="{y+27}" text-anchor="middle" class="label">{html.escape(title)}</text>')
    parts.append(f'<text x="{x+w/2}" y="{y+52}" text-anchor="middle" class="small">{html.escape(sub)}</text>')
for src,tgt in edges:
    a,b=by_id[src],by_id[tgt]
    parts.append(f'<path d="M{a[1]+a[3]} {a[2]+a[4]/2} H{b[1]-3}" fill="none" stroke="#526575" stroke-width="1.5" marker-end="url(#arrow)"/>')
for src,tgt in [('initial','start'),('answer','revise'),('observe','continue')]:
    a,b=by_id[src],by_id[tgt]
    parts.append(f'<path d="M{a[1]+a[3]/2} {a[2]+a[4]} V{b[2]-4}" stroke="#8ca0af" stroke-width="1.4" marker-end="url(#arrow)"/>')
parts.append('<rect x="245" y="346" width="910" height="51" rx="9" fill="#eef7f2" stroke="#8ab59c" stroke-width="1.3"/>')
parts.append('<text x="700" y="377" text-anchor="middle" class="label">More time at gates with the same takeoff times</text>')
for x in [350,810,1045]:
    parts.append(f'<path d="M{x} 301 V342" stroke="#6f9685" stroke-width="1.4" marker-end="url(#arrow)"/>')
parts.append('</svg>')
svg=OUT/(NAME+'.svg')
svg.write_text(''.join(parts),encoding='utf-8')

mx=ET.Element('mxfile',host='app.diagrams.net',modified='2026-10-31T00:00:00.000Z',version='24.7.17',type='device')
dia=ET.SubElement(mx,'diagram',id=NAME,name='APREQ coordination and pushback')
model=ET.SubElement(dia,'mxGraphModel',dx=str(W),dy=str(H),grid='1',gridSize='10',page='1',pageScale='1',pageWidth=str(W),pageHeight=str(H))
root=ET.SubElement(model,'root')
ET.SubElement(root,'mxCell',id='0')
ET.SubElement(root,'mxCell',id='1',parent='0')
def cell(idv,value,x,y,w,h,style):
    node=ET.SubElement(root,'mxCell',id=idv,value=value,style=style,vertex='1',parent='1')
    ET.SubElement(node,'mxGeometry',x=str(x),y=str(y),width=str(w),height=str(h),attrib={'as':'geometry'})
for idv,x,y,w,h,title,sub,fill in boxes:
    cell(idv,title+'<br><font style="font-size:18px" color="#4a5966">'+sub+'</font>',x,y,w,h,
         f'rounded=1;arcSize=12;whiteSpace=wrap;html=1;fontFamily=Arial;fontSize=22;fontColor=#24313b;fillColor={fill};strokeColor=#6c7b88;strokeWidth=1.3;')
for idv,x,y,value,cls in labels:
    size=23 if cls=='title' else 20 if cls=='lane' else 18
    width=1120 if cls=='title' else 210
    cell(idv,value,x,y-size,width,size+8,f'text;html=1;strokeColor=none;fillColor=none;align=left;fontFamily=Arial;fontSize={size};fontColor=#24313b;fontStyle={1 if cls in ("title","lane") else 0};')
cell('objective','More time at gates with the same takeoff times',245,346,910,51,'rounded=1;html=1;fontFamily=Arial;fontSize=22;fillColor=#eef7f2;strokeColor=#8ab59c;')
all_edges=edges+[('initial','start'),('answer','revise'),('observe','continue'),('start','objective'),('revise','objective'),('continue','objective')]
for i,(src,tgt) in enumerate(all_edges):
    n=ET.SubElement(root,'mxCell',id=f'edge{i}',edge='1',parent='1',source=src,target=tgt,style='edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;endSize=5;strokeColor=#526575;strokeWidth=1.4;')
    ET.SubElement(n,'mxGeometry',relative='1',attrib={'as':'geometry'})
ET.ElementTree(mx).write(OUT/(NAME+'.drawio'),encoding='utf-8',xml_declaration=True)

inkscape=shutil.which('inkscape') or r'C:/Program Files/Inkscape/bin/inkscape.com'
assert Path(inkscape).is_file(),inkscape
# Native PDF retains searchable text. The alternate pair supports editable LaTeX text.
for suffix,options in [('.pdf',[]),('.background.pdf',['--export-latex'])]:
    subprocess.run([inkscape,str(svg),'--export-type=pdf','--export-area-page',
                    '--export-filename='+str(OUT/(NAME+suffix)),*options],check=True,capture_output=True)
(OUT/(NAME+'.pdf_tex')).write_text('% Inkscape text and vector background.'+chr(10)+chr(92)+'input{figures/conceptual_information_release.background.pdf_tex}'+chr(10),encoding='utf-8')
print('Exported editable diagrams.net and SVG sources, searchable PDF and Inkscape PDF_TEX.')




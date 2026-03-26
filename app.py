import streamlit as st
from PIL import Image, ImageDraw, ImageOps
import io, math, json, datetime
import fitz # PyMuPDF

# Settings
ROLL_WIDTH_IN, MARGIN_IN, DPI = 22, 0.375, 300

# State
if 'inventory' not in st.session_state: st.session_state.inventory = []
if 'uploader_key' not in st.session_state: st.session_state.uploader_key = 0
if 'history' not in st.session_state: st.session_state.history = []

def clear_all_data():
    for k in list(st.session_state.keys()):
        if k != 'history': del st.session_state[k]
    st.session_state.inventory, st.session_state.uploader_key = [], st.session_state.get('uploader_key', 0) + 1

def rasterize_vector(f_bytes, ext):
    try:
        doc = fitz.open(stream=f_bytes, filetype=ext)
        pix = doc.load_page(0).get_pixmap(matrix=fitz.Matrix(DPI/72, DPI/72), alpha=True)
        img = Image.frombytes("RGBA", [pix.width, pix.height], pix.samples)
        doc.close()
        return img
    except: return None

def optimize_layout_distributed(artworks, roll_w):
    if not artworks: return [], 0
    proc = []
    for a in artworks:
        w, h, img = a['print_w'], a['print_h'], a['image']
        if (h + 0.75 <= roll_w) and (h < w or w + 0.75 > roll_w):
            w, h, img = h, w, img.rotate(90, expand=True)
        proc.append({'id': a['id'], 'image': img, 'w': w, 'h': h})
    sorted_art = sorted(proc, key=lambda x: x['h'], reverse=True)
    rows, row, rw = [], [], 0
    for a in sorted_art:
        if rw + a['w'] + 0.75 > roll_w and row:
            rows.append(row); row, rw = [], 0
        row.append(a); rw += a['w'] + 0.75
    if row: rows.append(row)
    placed, cur_y = [], 0.375
    for r in rows:
        rh = max(i['h'] for i in r)
        rem = roll_w - 0.75 - sum(i['w'] for i in r)
        gap, cx = (rem / (len(r)-1)) if len(r)>1 else 0, 0.375
        if len(r)==1: cx += rem/2
        for i in r:
            placed.append({**i, 'x': cx, 'y': cur_y + (rh-i['h'])/2})
            cx += i['w'] + gap
        cur_y += rh + 0.375
    return placed, cur_y

def generate_png(placed, rw, rh, mir):
    canv = Image.new('RGBA', (int(rw*DPI), int(rh*DPI)), (0,0,0,0))
    for a in placed:
        res = a['image'].resize((int(a['w']*DPI), int(a['h']*DPI)), Image.Resampling.LANCZOS)
        canv.alpha_composite(res, (int(a['x']*DPI), int(a['y']*DPI)))
    if mir: canv = ImageOps.mirror(canv)
    buf = io.BytesIO(); canv.save(buf, format="PNG", dpi=(DPI, DPI)); buf.seek(0)
    return buf

st.set_page_config(page_title="DTF Pro Builder", layout="wide")
st.title('🖨️ DTF Universal Workspace')

with st.sidebar:
    if st.button("🗑️ CLEAR JOB", type="primary", use_container_width=True): 
        clear_all_data(); st.rerun()
    cust, order = st.text_input("Customer", "Client"), st.text_input("Order #", "1001")
    price, mirror = st.number_input("Price/ft", 15.0), st.checkbox("Mirror Print")
    file = st.file_uploader("Upload Art", type=['png','pdf','ai','eps','webp','tiff'], key=f"u_{st.session_state.uploader_key}")
    if file:
        ext = file.name.split('.')[-1].lower()
        raw = rasterize_vector(file.read(), ext) if ext in ['pdf','ai','eps'] else Image.open(file).convert("RGBA")
        if raw:
            box = raw.getbbox(); img = raw.crop(box) if box else raw
            dpi_v = img.info.get('dpi', (DPI, DPI))[0]
            aw, ah = round(img.width/dpi_v, 2), round(img.height/dpi_v, 2)
            if aw > 22: st.error("Width > 22\""); st.stop()
            with st.form("add"):
                c1, c2 = st.columns(2)
                win, hin = c1.number_input("W", 0.1, 22.0, float(aw)), c2.number_input("H", 0.1, 120.0, float(ah))
                qty = st.number_input("Qty", 1, 100, 1)
                if st.form_submit_button("Add to Roll"):
                    for _ in range(qty): st.session_state.inventory.append({'id': file.name, 'image': img, 'print_w': win, 'print_h': hin})
                    st.rerun()

if st.session_state.inventory:
    u_ids = []; u_items = []
    for it in st.session_state.inventory:
        if it['id'] not in u_ids: u_ids.append(it['id']); u_items.append(it)
    grid = st.columns(4)
    for i, item in enumerate(u_items):
        with grid[i%4]:
            st.image(item['image'], width=80)
            if st.button(f"Remove", key=f"r_{i}"):
                st.session_state.inventory = [x for x in st.session_state.inventory if x['id'] != item['id']]; st.rerun()
    placed, ah = optimize_layout_distributed(st.session_state.inventory, 22)
    bill = math.ceil(ah/12)*12
    m1, m2, m3 = st.columns(3)
    m1.metric("Length", f"{bill}\"")
    m2.metric("Cost", f"${(bill/12)*price:.2f}")
    m3.metric("Items", len(st.session_state.inventory))
    bg = st.radio("BG:", ["Charcoal", "Gray", "Blue"], horizontal=True)
    mask = st.checkbox("Underbase Mask")
    b_map = {"Gray": (240,240,240,255), "Charcoal": (30,30,30,255), "Blue": (0,100,255,255)}
    viz = Image.new('RGBA', (int(22*20), int(bill*20)), b_map[bg])
    for a in placed:
        t = a['image'].copy(); t.thumbnail((int(a['w']*20), int(a['h']*20)))
        if mask:
            viz.paste(Image.new("RGBA", t.size, (0,0,0,255)), (int(a['x']*20), int(a['y']*20)), t.getchannel('A'))
        else:
            viz.paste(t, (int(a['x']*20), int(a['y']*20)), t)
    st.image(viz if not mirror else ImageOps.mirror(viz), use_container_width=True)
    op = st.text_input("Operator", "Staff")
    if st.download_button("Download PNG", generate_png(placed, 22, bill, mirror), f"{cust}_{order}.png"):
        st.session_state.history.append({'t': datetime.datetime.now().strftime("%H:%M"), 'j': f"{cust}_{order}", 'op': op})
        st.rerun()

if st.session_state.history:
    st.divider()
    for h in st.session_state.history[::-1]: st.write(f"✅ {h['t']} | {h['j']} | Op: {h['op']}")

st.caption(f"v2.7 | {datetime.datetime.now().strftime('%Y-%m-%d')}")

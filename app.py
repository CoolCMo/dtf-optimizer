import streamlit as st
from PIL import Image, ImageDraw, ImageOps
import io
import math
import fitz  # PyMuPDF
import json
import datetime

# --- 1. Configuration ---
ROLL_WIDTH_IN = 22
MARGIN_IN = 0.375 
DPI = 300

# --- 2. Session State ---
if 'inventory' not in st.session_state:
    st.session_state.inventory = []
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0
if 'history' not in st.session_state:
    st.session_state.history = []

# --- 3. Functions ---
def clear_all_data():
    for key in list(st.session_state.keys()):
        if key != 'history': del st.session_state[key]
    st.session_state.inventory = []
    st.session_state.uploader_key = st.session_state.get('uploader_key', 0) + 1

def rasterize_vector(file_bytes, extension):
    try:
        doc = fitz.open(stream=file_bytes, filetype=extension)
        page = doc.load_page(0)
        zoom = DPI / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=True)
        img = Image.frombytes("RGBA", [pix.width, pix.height], pix.samples)
        doc.close()
        return img
    except Exception as e:
        st.error(f"Vector Error: {e}")
        return None

def optimize_layout_distributed(artworks, roll_width_in):
    if not artworks: return [], 0
    processed = []
    for art in artworks:
        w_orig, h_orig = art['print_w'], art['print_h']
        img = art['image']
        can_fit_n = (w_orig + (2 * MARGIN_IN)) <= roll_width_in
        can_fit_r = (h_orig + (2 * MARGIN_IN)) <= roll_width_in
        w, h = w_orig, h_orig
        if can_fit_r and (h_orig < w_orig or not can_fit_n):
            w, h = h_orig, w_orig
            img = img.rotate(90, expand=True)
        processed.append({'id': art['id'], 'image': img, 'w': w, 'h': h})

    sorted_art = sorted(processed, key=lambda x: x['h'], reverse=True)
    rows, current_row, current_row_w = [], [], 0
    for art in sorted_art:
        needed = art['w'] + (MARGIN_IN * 2)
        if current_row_w + needed > roll_width_in and current_row:
            rows.append(current_row)
            current_row, current_row_w = [], 0
        current_row.append(art)
        current_row_w += needed
    if current_row: rows.append(current_row)

    placed, curr_y = [], MARGIN_IN 
    for row in rows:
        row_h = max(item['h'] for item in row)
        rem_w = roll_width_in - (MARGIN_IN * 2) - sum(i['w'] for i in row)
        h_gap, curr_x = (rem_w / (len(row) - 1)) if len(row) > 1 else 0, MARGIN_IN
        if len(row) == 1: curr_x += rem_w / 2
        for item in row:
            v_off = (row_h - item['h']) / 2
            placed.append({**item, 'x': curr_x, 'y': curr_y + v_off})
            curr_x += item['w'] + h_gap
        curr_y += row_h + MARGIN_IN 
    return placed, curr_y

def generate_png_file(placed, roll_w, roll_h, mirror=False):
    canvas = Image.new('RGBA', (int(roll_w * DPI), int(roll_h * DPI)), (0, 0, 0, 0))
    for art in placed:
        tw, th = int(art['w'] * DPI), int(art['h'] * DPI)
        res = art['image'].resize((tw, th), Image.Resampling.LANCZOS)
        canvas.alpha_composite(res, (int(art['x'] * DPI), int(art['y'] * DPI)))
    if mirror: canvas = ImageOps.mirror(canvas)
    buf = io.BytesIO()
    canvas.save(buf, format="PNG", dpi=(DPI, DPI))
    buf.seek(0)
    return buf

# --- 4. Main App UI ---
st.set_page_config(page_title="DTF Pro Builder", layout="wide")
st.title('🖨️ DTF Universal Workspace')

with st.sidebar:
    st.header("1. Project Actions")
    if st.button("🗑️ CLEAR CURRENT JOB", type="primary", use_container_width=True): 
        clear_all_data()
        st.rerun()

    st.divider()
    st.header("2. Job Setup")
    cust = st.text_input("Customer", value="Client")
    order = st.text_input("Order #", value="1001")
    price = st.number_input("Price/ft", value=15.0)
    mirror = st.checkbox("Mirror Print", value=False)

    st.divider()
    st.header("3. Add Artwork")
    file = st.file_uploader("Upload Art", type=['png', 'pdf', 'ai', 'eps', 'webp', 'tiff'], key=f"u_{st.session_state.uploader_key}")
    
    if file:
        ext = file.name.split('.')[-1].lower()
        if ext in ['pdf', 'ai', 'eps']:
            raw_img = rasterize_vector(file.read(), ext)
        else:
            raw_img = Image.open(file).convert("RGBA")
        
        if raw_img:
            bbox = raw_img.getbbox()
            img_data = raw_img.crop(bbox) if bbox else raw_img
            dpi_v = img_data.info.get('dpi', (DPI, DPI))[0]
            aw, ah = round(img_data.width/dpi_v, 2), round(img_data.height/dpi_v, 2)

            if aw > ROLL_WIDTH_IN:
                st.error(f"❌ Width {aw}\" > {ROLL_WIDTH_IN}\""); st.stop()

            # Scan for semi-transparency
            pix_data = list(img_data.getdata())
            alpha = [p[3] for p in pix_data if p[3] > 0]
            semi_pct = (len([a for a in alpha if a < 255]) / len(alpha) * 100) if alpha else 0

            with st.form("add_form"):
                c1, c2 = st.columns(2)
                win = c1.number_input("Width (in)", 0.1, 22.0, float(aw))
                hin = c2.number_input("Height (in)", 0.1, 120.0, float(ah))
                eff_dpi = int(img_data.width / win)
                if eff_dpi < 200: st.error(f"Low Res: {eff_dpi} DPI")
                if semi_pct > 5: st.warning(f"Soft Edges: {semi_pct:.1f}%")
                qty = st.number_input("Quantity", 1, 100, 1)
                if st.form_submit_button("Add to Roll", use_container_width=True):
                    for _ in range(qty): 
                        st.session_state.inventory.append({'id': file.name, 'image': img_data, 'print_w': win, 'print_h': hin})
                    st.rerun()

# --- 5. Workspace ---
if st.session_state.inventory:
    st.subheader("📦 Inventory Management")
    u_items = []
    u_ids = []
    for it in st.session_state.inventory:
        if it['id'] not in u_ids:
            u_ids.append(it['id']); u_items.append(it)
    
    grid = st.columns(4)
    for idx, item in enumerate(u_items):
        with grid[idx % 4]:
            st.image(item['image'], width=100)
            if st.button(f"Remove {item['id'][:10]}", key=f"r_{idx}", use_container_width=True):
                st.session_state.inventory = [x for x in st.session_state.inventory if x['id'] != item['id']]
                st.rerun()

    st.divider()
    placed, actual_h = optimize_layout_distributed(st.session_state.inventory, ROLL_WIDTH_IN)
    billable = math.ceil(actual_h / 12) * 12
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Roll Length", f"{billable}\"")
    m2.metric("

import streamlit as st
from PIL import Image, ImageDraw, ImageOps
import io
import math
import fitz  # PyMuPDF (Required for PDF/AI/EPS support)
import json
import datetime

# --- 1. Configuration & Constants ---
ROLL_WIDTH_IN = 22
MARGIN_IN = 0.375 
DPI = 300

# --- 2. Session State Initialization ---
if 'inventory' not in st.session_state:
    st.session_state.inventory = []
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0
if 'history' not in st.session_state:
    st.session_state.history = []

# --- 3. Helper Functions ---
def clear_all_data():
    for key in list(st.session_state.keys()):
        if key != 'history': 
            del st.session_state[key]
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
        st.error(f"Error processing vector: {e}")
        return None

def optimize_layout_distributed(artworks, roll_width_in):
    if not artworks: return [], 0
    processed_art = []
    for art in artworks:
        w_orig, h_orig = art['print_w'], art['print_h']
        img = art['image']
        # Rotation Logic for best fit
        can_fit_n = (w_orig + (2 * MARGIN_IN)) <= roll_width_in
        can_fit_r = (h_orig + (2 * MARGIN_IN)) <= roll_width_in
        w, h = w_orig, h_orig
        if can_fit_r and (h_orig < w_orig or not can_fit_n):
            w, h = h_orig, w_orig
            img = img.rotate(90, expand=True)
        processed_art.append({'id': art['id'], 'image': img, 'w': w, 'h': h})

    # Sort by height for tightest packing (Reoptimization)
    sorted_art = sorted(processed_art, key=lambda x: x['h'], reverse=True)
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

# --- 4. Sidebar: Job Setup & Upload ---
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
    file = st.file_uploader("Upload Art (PNG, PDF, AI, EPS)", type=['png', 'pdf', 'ai', 'eps', 'webp', 'tiff'], key=f"u_{st.session_state.uploader_key}")
    
    if file:
        ext = file.name.split('.')[-1].lower()
        # Rasterize or Open
        if ext in ['pdf', 'ai', 'eps']:
            raw_img =
        st.info(f"✅ **{entry['timestamp']}** | **Job:** {entry['name']} | **Op:** {entry['operator']} | **Settings:** {entry['specs']} | **Notes:** {entry['notes']}")

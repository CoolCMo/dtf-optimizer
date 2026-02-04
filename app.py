import streamlit as st
from PIL import Image, ImageDraw, ImageOps
import io
import math
import fitz  # PyMuPDF for PDF, AI, and EPS support

# --- Configuration ---
ROLL_WIDTH_IN = 22
MARGIN_IN = 0.375 
DPI = 300

def clear_all_data():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state.inventory = []
    if 'uploader_key' not in st.session_state:
        st.session_state.uploader_key = 0
    st.session_state.uploader_key += 1

def reset_uploader():
    if 'uploader_key' not in st.session_state:
        st.session_state.uploader_key = 0
    st.session_state.uploader_key += 1
    st.rerun()

def rasterize_vector(file_bytes, extension):
    """Converts PDF, AI, or EPS to a transparent PIL Image at 300 DPI."""
    try:
        doc = fitz.open(stream=file_bytes, filetype=extension)
        page = doc.load_page(0)  # Load first page
        # Calculate scaling to reach 300 DPI (standard PDF is 72 DPI)
        zoom = DPI / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=True)
        img = Image.frombytes("RGBA", [pix.width, pix.height], pix.samples)
        doc.close()
        return img
    except Exception as e:
        st.error(f"Error processing vector file: {e}")
        return None

def optimize_layout_distributed(artworks, roll_width_in):
    processed_art = []
    for art in artworks:
        w_orig, h_orig = art['print_w'], art['print_h']
        img = art['image']
        
        can_fit_normal = (w_orig + (2 * MARGIN_IN)) <= roll_width_in
        can_fit_rotated = (h_orig + (2 * MARGIN_IN)) <= roll_width_in
        
        rotated = False
        w, h = w_orig, h_orig
        if can_fit_rotated:
            if h_orig < w_orig or not can_fit_normal:
                w, h = h_orig, w_orig
                img = img.rotate(90, expand=True)
                rotated = True
        
        processed_art.append({'id': art['id'], 'image': img, 'w': w, 'h': h})

    sorted_art = sorted(processed_art, key=lambda x: x['h'], reverse=True)
    rows, current_row, current_row_w = [], [], 0
    
    for art in sorted_art:
        item_w_with_min_margin = art['w'] + (MARGIN_IN * 2)
        if current_row_w + item_w_with_min_margin > roll_width_in and current_row:
            rows.append(current_row)
            current_row, current_row_w = [], 0
        current_row.append(art)
        current_row_w += item_w_with_min_margin
    
    if current_row: rows.append(current_row)

    placed_items = []
    curr_y = MARGIN_IN 
    for row in rows:
        row_max_h = max(item['h'] for item in row)
        total_art_w = sum(item['w'] for item in row)
        remaining_w = roll_width_in - (MARGIN_IN * 2) - total_art_w
        
        if len(row) > 1:
            h_gap = remaining_w / (len(row) - 1)
            curr_x = MARGIN_IN
        else:
            h_gap = 0
            curr_x = MARGIN_IN + (remaining_w / 2)
            
        for item in row:
            v_offset = (row_max_h - item['h']) / 2
            placed_items.append({**item, 'x': curr_x, 'y': curr_y + v_offset})
            curr_x += item['w'] + h_gap
        curr_y += row_max_h + MARGIN_IN 
        
    return placed_items, curr_y

def generate_png_file(placed_art, roll_w, roll_h, mirror=False):
    pixel_w, pixel_h = int(roll_w * DPI), int(roll_h * DPI)
    output_img = Image.new('RGBA', (pixel_w, pixel_h), (0, 0, 0, 0))
    for art in placed_art:
        target_w, target_h = int(art['w'] * DPI), int(art['h'] * DPI)
        resized_art = art['image'].resize((target_w, target_h), Image.Resampling.LANCZOS)
        paste_x, paste_y = int(art['x'] * DPI), int(art['y'] * DPI)
        output_img.alpha_composite(resized_art, (paste_x, paste_y))
    if mirror: output_img = ImageOps.mirror(output_img)
    buffer = io.BytesIO()
    output_img.save(buffer, format="PNG", dpi=(DPI, DPI))
    buffer.seek(0)
    return buffer

# --- Streamlit UI ---
st.set_page_config(page_title="DTF Pro Builder", layout="wide")

if 'inventory' not in st.session_state: st.session_state.inventory = []
if 'uploader_key' not in st.session_state: st.session_state.uploader_key = 0

st.title('🖨️ DTF Universal Format Builder')

with st.sidebar:
    st.header("1. Job Details")
    cust_name = st.text_input("Customer Name", value="Retail Client", key="cust_name_input")
    order_num = st.text_input("Order Number", value="1001", key="order_num_input")
    price_ft = st.number_input("Price per Foot ($)", value=15.0, key="price_ft_input")
    mirror_print = st.checkbox("Mirror Image (Flip Horizontal)", value=False)
    
    if st.button("🗑️ CLEAR ALL DATA", use_container_width=True, type="primary"):
        clear_all_data()
        st.rerun()

    st.divider()
    st.header("2. Upload & Auto-Trim")
    # UPDATED: Expanded formats
    file = st.file_uploader("Upload Art (PNG, PDF, AI, EPS, WebP, TIFF)", 
                            type=['png', 'pdf', 'ai', 'eps', 'webp', 'tiff', 'tif'], 
                            key=f"uploader_{st.session_state.uploader_key}")
    
    if file:
        ext = file.name.split('.')[-1].lower()
        
        # Logic to handle Vector vs Raster
        if ext in ['pdf', 'ai', 'eps']:
            with st.spinner("Rasterizing vector file..."):
                raw_img = rasterize_vector(file.read(), ext)
        else:
            raw_img = Image.open(file).convert("RGBA")
        
        if raw_img:
            bbox = raw_img.getbbox()
            img_data = raw_img.crop(bbox) if bbox else raw_img
            
            # Default to 300 DPI for auto-sizing
            dpi_val = img_data.info.get('dpi', (DPI, DPI))[0]
            auto_w, auto_h = round(img_data.width / dpi_val, 2), round(img_data.height / dpi_val, 2)

            if auto_w > ROLL_WIDTH_IN:
                st.error(f"❌ REJECTED: Content is {auto_w}\" wide. Max is {ROLL_WIDTH_IN}\".")
                if st.button("Clear Offending File"): reset_uploader()
                st.stop()

            st.caption(f"Trimmed Size: {img_data.width}x{img_data.height}px")

            with st.form("add_art", clear_on_submit=True):
                col1, col2 = st.columns(2)
                w_in = col1.number_input("Print Width (in)", 0.1, 22.0, float(auto_w))
                h_in = col2.number_input("Print Height (in)", 0.1, 120.0, float(auto_h))
                qty = st.number_input("Qty", 1, 100, 1)
                
                if st.form_submit_button("Add to Roll"):
                    for _ in range(qty):
                        st.session_state.inventory.append({'id': file.name, 'image': img_data, 'print_w': w_in, 'print_h': h_in})
                    st.rerun()

if st.session_state.inventory:
    placed, actual_h = optimize_layout_distributed(st.session_state.inventory, ROLL_WIDTH_IN)
    billable_len = math.ceil(actual_h / 12) * 12
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Roll Length", f"{billable_len}\"")
    m2.metric("Total Cost", f"${(billable_len/12)*price_ft:.2f}")
    m3.metric("Edge Margin", '0.375"')

    # Auto-Fill Logic
    last_item = st.session_state.inventory[-1]
    temp_inv = st.session_state.inventory.copy()
    added_count = 0
    while True:
        temp_inv.append(last_item)
        _, test_h = optimize_layout_distributed(temp_inv, ROLL_WIDTH_IN)
        if test_h > billable_len: break
        added_count += 1
    
    if added_count > 0:
        if st.button(f"💡 Evenly fill {billable_len}\" space (+{added_count} items)"):
            for _ in range(added_count): st.session_state.inventory.append(last_item)
            st.rerun()

    with st.spinner("Generating High-Res PNG..."):
        png_output = generate_png_file(placed, ROLL_WIDTH_IN, billable_len, mirror=mirror_print)
        st.download_button("📥 Download 300 DPI Transparent PNG", png_output, f"{cust_name}_{order_num}.png", "image/png", use_container_width=True)

    preview_scale = 20
    viz = Image.new('RGBA', (int(ROLL_WIDTH_IN * preview_scale), int(billable_len * preview_scale)), (240, 240, 240, 255))
    for art in placed:
        thumb = art['image'].copy()
        thumb.thumbnail((int(art['w'] * preview_scale), int(art['h'] * preview_scale)))
        px, py = int(art['x'] * preview_scale), int(art['y'] * preview_scale)
        viz.paste(thumb, (px, py), thumb)
    if mirror_print: viz = ImageOps.mirror(viz)
    st.image(viz, caption="Justified Layout Preview", use_container_width=True)
else:
    st.info("Upload Art (Vector or Raster) to begin.")
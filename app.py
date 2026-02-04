import streamlit as st
from PIL import Image, ImageDraw
import io
import math

# --- Configuration ---
ROLL_WIDTH_IN = 22
MARGIN_IN = 0.5
DPI = 300

def clear_all_data():
    for key in st.session_state.keys():
        del st.session_state[key]
    st.session_state.inventory = []

def optimize_layout(artworks, roll_width_in):
    processed_art = []
    for art in artworks:
        w, h = art['print_w'], art['print_h']
        img = art['image']
        rotated = False
        
        # Auto-rotate logic for efficiency
        if w + (2 * MARGIN_IN) > roll_width_in:
            if h + (2 * MARGIN_IN) <= roll_width_in:
                w, h = h, w
                img = img.rotate(90, expand=True)
                rotated = True
        elif h > w and (h + (2 * MARGIN_IN) <= roll_width_in):
            w, h = h, w
            img = img.rotate(90, expand=True)
            rotated = True
        
        processed_art.append({
            'id': art['id'], 'image': img, 'w': w, 'h': h,
            'total_w': w + (2 * MARGIN_IN), 'total_h': h + (2 * MARGIN_IN),
            'rotated': rotated
        })

    sorted_art = sorted(processed_art, key=lambda x: x['total_h'], reverse=True)
    placed_items, curr_x, curr_y, shelf_h = [], 0, 0, 0
    
    for art in sorted_art:
        if curr_x + art['total_w'] > roll_width_in:
            curr_x = 0
            curr_y += shelf_h
            shelf_h = 0
        placed_items.append({**art, 'x': curr_x, 'y': curr_y})
        curr_x += art['total_w']
        shelf_h = max(shelf_h, art['total_h'])

    return placed_items, curr_y + shelf_h

def generate_png_file(placed_art, roll_w, roll_h):
    pixel_w, pixel_h = int(roll_w * DPI), int(roll_h * DPI)
    output_img = Image.new('RGBA', (pixel_w, pixel_h), (0, 0, 0, 0))
    
    for art in placed_art:
        target_w, target_h = int(art['w'] * DPI), int(art['h'] * DPI)
        resized_art = art['image'].resize((target_w, target_h), Image.Resampling.LANCZOS)
        paste_x = int((art['x'] + MARGIN_IN) * DPI)
        paste_y = int((art['y'] + MARGIN_IN) * DPI)
        output_img.alpha_composite(resized_art, (paste_x, paste_y))
    
    buffer = io.BytesIO()
    output_img.save(buffer, format="PNG", dpi=(DPI, DPI))
    buffer.seek(0)
    return buffer

# --- Streamlit UI ---
st.set_page_config(page_title="DTF Content Optimizer", layout="wide")

if 'inventory' not in st.session_state: 
    st.session_state.inventory = []

st.title("🖼️ DTF "Content-Only" Gang Sheet Builder")

with st.sidebar:
    st.header("1. Job Details")
    cust_name = st.text_input("Customer Name", value="Retail Client", key="cust_name")
    order_num = st.text_input("Order Number", value="1001", key="order_num")
    price_ft = st.number_input("Price per Foot ($)", value=15.0, key="price_ft")
    
    if st.button("🗑️ CLEAR ALL DATA", use_container_width=True, type="primary"):
        clear_all_data()
        st.rerun()

    st.divider()
    st.header("2. Upload & Auto-Trim")
    file = st.file_uploader("Upload PNG (App will auto-trim artboard)", type=['png'], key="file_uploader")
    
    if file:
        raw_img = Image.open(file).convert("RGBA")
        
        # --- AUTO-TRIM LOGIC ---
        # Find the bounding box of non-zero (non-transparent) pixels
        bbox = raw_img.getbbox()
        if bbox:
            img_data = raw_img.crop(bbox)
            st.success("Artboard trimmed to design edges!")
        else:
            img_data = raw_img
            st.warning("No transparent pixels found to trim.")

        dpi_val = img_data.info.get('dpi', (DPI, DPI))[0]
        auto_w = round(img_data.width / dpi_val, 2)
        auto_h = round(img_data.height / dpi_val, 2)
        
        st.caption(f"Trimmed Content: {img_data.width}x{img_data.height}px")

        with st.form("add_art", clear_on_submit=True):
            col1, col2 = st.columns(2)
            w_in = col1.number_input("Print Width (in)", 0.1, 22.0, float(auto_w))
            h_in = col2.number_input("Print Height (in)", 0.1, 120.0, float(auto_h))
            qty = st.number_input("Qty", 1, 100, 1)
            
            if st.form_submit_button("Add to Roll"):
                for _ in range(qty):
                    st.session_state.inventory.append({
                        'id': file.name, 'image': img_data, 
                        'print_w': w_in, 'print_h': h_in
                    })
                st.rerun()

if st.session_state.inventory:
    placed, actual_h = optimize_layout(st.session_state.inventory, ROLL_WIDTH_IN)
    billable_len = math.ceil(actual_h / 12) * 12
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Roll Length", f"{billable_len}\"")
    m2.metric("Total Cost", f"${(billable_len/12)*price_ft:.2f}")
    m3.metric("Free Space", f"{billable_len - actual_h:.1f}\"")

    # PNG Export
    with st.spinner("Generating High-Res PNG..."):
        png_output = generate_png_file(placed, ROLL_WIDTH_IN, billable_len)
        st.download_button(
            label="📥 Download 300 DPI Transparent PNG", 
            data=png_output, 
            file_name=f"{cust_name}_{order_num}.png", 
            mime="image/png",
            use_container_width=True
        )

    # Visualization
    preview_scale = 20
    viz = Image.new('RGBA', (int(ROLL_WIDTH_IN * preview_scale), int(billable_len * preview_scale)), (240, 240, 240, 255))
    for art in placed:
        thumb = art['image'].copy()
        thumb.thumbnail((int(art['w'] * preview_scale), int(art['h'] * preview_scale)))
        px, py = int((art['x'] + MARGIN_IN) * preview_scale), int((art['y'] + MARGIN_IN) * preview_scale)
        viz.paste(thumb, (px, py), thumb)
    st.image(viz, caption="Trimmed Layout Preview", use_container_width=True)
else:
    st.info("Upload a file to automatically detect design dimensions.")
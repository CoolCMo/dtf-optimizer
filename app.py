import streamlit as st
from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
import io
import math

# --- Standards ---
ROLL_WIDTH_IN = 22
MARGIN_IN = 0.5
DPI = 300

def optimize_layout(artworks, roll_width_in):
    processed_art = []
    for art in artworks:
        w, h = art['print_w'], art['print_h']
        img = art['image']
        rotated = False
        
        # Auto-rotate to Landscape if it saves vertical space
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
    placed_items = []
    curr_x, curr_y, shelf_h = 0, 0, 0
    
    for art in sorted_art:
        if curr_x + art['total_w'] > roll_width_in:
            curr_x = 0
            curr_y += shelf_h
            shelf_h = 0
        placed_items.append({**art, 'x': curr_x, 'y': curr_y})
        curr_x += art['total_w']
        shelf_h = max(shelf_h, art['total_h'])

    return placed_items, curr_y + shelf_h

def generate_pdf(placed_art, roll_w, roll_h):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=(roll_w * inch, roll_h * inch))
    for art in placed_art:
        pdf_x, pdf_y = art['x'] * inch, (roll_h - art['y'] - art['total_h']) * inch
        p.drawInlineImage(art['image'], pdf_x + (MARGIN_IN * inch), pdf_y + (MARGIN_IN * inch), 
                          width=art['w'] * inch, height=art['h'] * inch)
    p.save()
    buffer.seek(0)
    return buffer

# --- Streamlit UI ---
st.set_page_config(page_title="DTF Pro Optimizer", layout="wide")
st.title("🚀 DTF Optimizer: Auto-Fill Edition")

if 'inventory' not in st.session_state: st.session_state.inventory = []

with st.sidebar:
    st.header("1. Setup")
    price_per_ft = st.number_input("Cost per Foot ($)", value=15.0)
    
    st.header("2. Upload & Add")
    file = st.file_uploader("Upload Artwork", type=['png', 'jpg'])
    if file:
        with st.form("add_art"):
            c1, c2 = st.columns(2)
            w_in, h_in = c1.number_input("Width", 1.0, 22.0, 10.0), c2.number_input("Height", 1.0, 120.0, 10.0)
            qty = st.number_input("Qty", 1, 50, 1)
            if st.form_submit_button("Add to Roll"):
                img_data = Image.open(file)
                for _ in range(qty):
                    st.session_state.inventory.append({'id': file.name, 'image': img_data, 'print_w': w_in, 'print_h': h_in})

if st.session_state.inventory:
    # Initial Calculation
    placed, actual_h = optimize_layout(st.session_state.inventory, ROLL_WIDTH_IN)
    billable_len = math.ceil(actual_h / 12) * 12
    remaining_in = billable_len - actual_h
    
    # KPI Row
    m1, m2, m3 = st.columns(3)
    m1.metric("Current Length", f"{actual_h:.1f}\"")
    m2.metric("Billable Length", f"{billable_len}\"")
    m3.metric("Free Space Left", f"{remaining_in:.1f}\"")

    # --- AUTO-FILL SECTION ---
    st.divider()
    st.subheader("💡 Optimize Your Spend")
    last_item = st.session_state.inventory[-1]
    
    # Calculate how many more fit in the REMAINING current foot
    # This is a greedy simulation
    temp_inv = st.session_state.inventory.copy()
    added_count = 0
    while True:
        temp_inv.append(last_item)
        _, test_h = optimize_layout(temp_inv, ROLL_WIDTH_IN)
        if test_h > billable_len:
            break
        added_count += 1
    
    if added_count > 0:
        st.success(f"You have room for **{added_count} more** of '{last_item['id']}' without increasing your cost!")
        if st.button(f"Fill remaining space (+{added_count} items)"):
            for _ in range(added_count):
                st.session_state.inventory.append(last_item)
            st.rerun()
    else:
        st.info("Your current roll is perfectly packed for this foot.")

    # PDF & Clear
    col_dl, col_clr = st.columns([1, 4])
    pdf = generate_pdf(placed, ROLL_WIDTH_IN, billable_len)
    col_dl.download_button("📥 Download 300 DPI PDF", pdf, "dtf_gang_sheet.pdf")
    if col_clr.button("Clear All"):
        st.session_state.inventory = []
        st.rerun()

    # Visual Preview
    preview_scale = 30 
    viz = Image.new('RGBA', (int(ROLL_WIDTH_IN * preview_scale), int(billable_len * preview_scale)), (240, 240, 240, 255))
    draw = ImageDraw.Draw(viz)
    for art in placed:
        thumb = art['image'].copy()
        thumb.thumbnail((int(art['w'] * preview_scale), int(art['h'] * preview_scale)))
        px, py = int((art['x'] + MARGIN_IN) * preview_scale), int((art['y'] + MARGIN_IN) * preview_scale)
        viz.paste(thumb, (px, py), thumb if thumb.mode == 'RGBA' else None)
        draw.rectangle([art['x']*preview_scale, art['y']*preview_scale, (art['x']+art['total_w'])*preview_scale, (art['y']+art['total_h'])*preview_scale], outline="#ff4b4b")
    st.image(viz, use_container_width=True)
import streamlit as st
from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
import io
import math

# --- Configuration ---
ROLL_WIDTH_IN = 22
MARGIN_IN = 0.5
DPI = 300

def optimize_layout(artworks, roll_width_in):
    processed_art = []
    for art in artworks:
        w, h = art['print_w'], art['print_h']
        img = art['image']
        rotated = False
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

def generate_pdf(placed_art, roll_w, roll_h, customer, order_no):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=(roll_w * inch, roll_h * inch))
    
    # Add Job Identification at the very top
    p.setFont("Helvetica-Bold", 14)
    p.drawString(0.5 * inch, (roll_h - 0.4) * inch, f"CUSTOMER: {customer} | ORDER: #{order_no}")
    p.line(0.5 * inch, (roll_h - 0.5) * inch, (roll_w - 0.5) * inch, (roll_h - 0.5) * inch)
    
    for art in placed_art:
        pdf_x, pdf_y = art['x'] * inch, (roll_h - art['y'] - art['total_h']) * inch
        p.drawInlineImage(art['image'], pdf_x + (MARGIN_IN * inch), pdf_y + (MARGIN_IN * inch), 
                          width=art['w'] * inch, height=art['h'] * inch)
    p.save()
    buffer.seek(0)
    return buffer

# --- Streamlit UI ---
st.set_page_config(page_title="DTF Pro Builder", layout="wide")

# Persistent Session State
if 'inventory' not in st.session_state: st.session_state.inventory = []

st.title("🖨️ DTF Pro Gang Sheet Builder")

with st.sidebar:
    st.header("1. Job Details")
    cust_name = st.text_input("Customer Name", "Retail Client")
    order_num = st.text_input("Order Number", "1001")
    price_ft = st.number_input("Price per Foot ($)", value=15.0)
    
    if st.button("🔥 RESET ALL DATA", use_container_width=True):
        st.session_state.inventory = []
        st.rerun()

    st.divider()
    st.header("2. Add Artwork")
    file = st.file_uploader("Upload PNG", type=['png', 'jpg'])
    if file:
        with st.form("add_art", clear_on_submit=True):
            c1, c2 = st.columns(2)
            w_in, h_in = c1.number_input("Width", 1.0, 22.0, 10.0), c2.number_input("Height", 1.0, 120.0, 10.0)
            qty = st.number_input("Qty", 1, 100, 1)
            if st.form_submit_button("Add to Roll"):
                img_data = Image.open(file)
                for _ in range(qty):
                    st.session_state.inventory.append({'id': file.name, 'image': img_data, 'print_w': w_in, 'print_h': h_in})
                st.rerun()

if st.session_state.inventory:
    # Calculation
    placed, actual_h = optimize_layout(st.session_state.inventory, ROLL_WIDTH_IN)
    # Add 1 inch buffer for the Header text at the top
    actual_h_with_header = actual_h + 1 
    billable_len = math.ceil(actual_h_with_header / 12) * 12
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Roll Length", f"{billable_len}\"")
    m2.metric("Cost", f"${(billable_len/12)*price_ft:.2f}")
    m3.metric("Free Space", f"{billable_len - actual_h_with_header:.1f}\"")

    # Optimization Suggestion
    last_item = st.session_state.inventory[-1]
    temp_inv = st.session_state.inventory.copy()
    added_count = 0
    while True:
        temp_inv.append(last_item)
        _, test_h = optimize_layout(temp_inv, ROLL_WIDTH_IN)
        if (test_h + 1) > billable_len: break
        added_count += 1
    
    if added_count > 0:
        st.info(f"💡 You can fit **{added_count} more** '{last_item['id']}' for free.")
        if st.button(f"Fill Space (+{added_count})"):
            for _ in range(added_count): st.session_state.inventory.append(last_item)
            st.rerun()

    pdf = generate_pdf(placed, ROLL_WIDTH_IN, billable_len, cust_name, order_num)
    st.download_button("📥 Download Print PDF", pdf, f"Order_{order_num}_{cust_name}.pdf", use_container_width=True)

    # Preview
    viz = Image.new('RGBA', (int(ROLL_WIDTH_IN * 20), int(billable_len * 20)), (255,255,255,255))
    draw = ImageDraw.Draw(viz)
    draw.text((10, 10), f"JOB: {cust_name} #{order_num}", fill="black")
    for art in placed:
        thumb = art['image'].copy()
        thumb.thumbnail((int(art['w'] * 20), int(art['h'] * 20)))
        # Shift everything down for the header
        viz.paste(thumb, (int(art['x']*20 + MARGIN_IN*20), int(art['y']*20 + 1*20 + MARGIN_IN*20)), thumb if thumb.mode == 'RGBA' else None)
    st.image(viz, use_container_width=True)
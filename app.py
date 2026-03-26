# --- Production Instructions Section ---
st.divider()
st.subheader("🔥 Heat Press & Operator Details")

p_col1, p_col2, p_col3, p_col4 = st.columns([1, 1, 1, 2])

# 1. Operator Name
operator_name = p_col1.text_input("Operator Name:", value="Production Lead")

# 2. Temperature Settings
press_temp = p_col2.selectbox("Temp (°F):", ["300°F", "310°F", "320°F", "330°F"], index=2)

# 3. Press Time
press_time = p_col3.text_input("Press Time (sec):", value="15s")

# 4. Special Instructions / Notes
press_notes = p_col4.text_input("Notes (e.g. 'Cold Peel Only', 'Heavy Pressure'):", value="Standard Hot Peel")

# --- Update History Logic to include these notes ---
if st.session_state.inventory:
    current_date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    clean_operator = operator_name.replace(" ", "_")
    final_filename = f"{cust}_{order}_{current_date_str}_{clean_operator}.png"
    
    # Download Button
    if st.download_button(
        label=f"📥 Download Final Gang Sheet (Tagged: {operator_name})",
        data=png,
        file_name=final_filename,
        mime="image/png",
        use_container_width=True
    ):
        # Save detailed log to history
        st.session_state.history.append({
            'timestamp': datetime.datetime.now().strftime("%H:%M:%S"),
            'name': f"{cust}_{order}",
            'operator': operator_name,
            'specs': f"{press_temp} @ {press_time}",
            'notes': press_notes
        })
        st.rerun()

# --- Updated Session History Display ---
if st.session_state.history:
    st.divider()
    st.subheader("🕒 Production Log")
    for entry in st.session_state.history[::-1]:
        st.info(f"✅ **{entry['timestamp']}** | **Job:** {entry['name']} | **Op:** {entry['operator']} | **Settings:** {entry['specs']} | **Notes:** {entry['notes']}")
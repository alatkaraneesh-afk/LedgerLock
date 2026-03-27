
import streamlit as st
from supabase import create_client, Client

# This pulls the "Secrets" you saved in Step 1
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]

# This creates the connection (the "Pipe")
supabase: Client = create_client(url, key)
import streamlit as st
import pandas as pd
from fpdf import FPDF
import datetime
from thefuzz import fuzz
import re

# --- 1. THE DATA ENGINE (The "Brain") ---
# --- 1. THE DATA ENGINE (The "Brain") ---
def run_audit(df):
    df = df.copy()
    df.columns = df.columns.str.lower().str.strip()
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
    df = df.dropna(subset=['date', 'amount']).reset_index(drop=True)
    df['row_id'] = df.index
    
    # --- 1. THE "SYNONYM" SHIELD (Fixes AWS/Amazon) ---
    def simplify_vendor(v):
        v = str(v).lower()
        if 'aws' in v or 'amazon' in v or 'amzn' in v: return 'amazon/aws'
        if 'acme' in v: return 'acme industrial'
        if 'gravel' in v: return 'local gravel'
        return v

    df['vendor_group'] = df['vendor'].apply(simplify_vendor)
    findings = []
    flagged_ids = set()

    # --- 2. PASS 1: DUPLICATES (Strict) ---
    for i, row_a in df.iterrows():
        if row_a['row_id'] in flagged_ids: continue
        for j, row_b in df.iterrows():
            # FIXED INDENTATION HERE
            if i >= j or row_b['row_id'] in flagged_ids: continue
            
            same_amt = abs(row_a['amount'] - row_b['amount']) < 0.01
            name_match = (row_a['vendor_group'] == row_b['vendor_group']) or (fuzz.token_set_ratio(row_a['vendor'], row_b['vendor']) > 85)
            days_diff = abs((row_a['date'] - row_b['date']).days)

            if same_amt and name_match and days_diff <= 7:
                findings.append({
                    'date': row_b['date'],
                    'vendor': f"{row_a['vendor']} / {row_b['vendor']}",
                    'amount': row_b['amount'],
                    'issue': "DUPLICATE BILLING IDENTIFIED",
                    'row_ids': [row_a['row_id'], row_b['row_id']]
                })
                flagged_ids.update([row_a['row_id'], row_b['row_id']])

    # --- 3. PASS 2: PRICE SPIKES (Now correctly inside the function) ---
    df_sorted = df.sort_values(['vendor_group', 'date'])
    df_sorted['prev_amt'] = df_sorted.groupby('vendor_group')['amount'].shift(1)
    
    spikes = df_sorted[(df_sorted['amount'] > df_sorted['prev_amt'] * 1.2) & (df_sorted['prev_amt'] > 0)]
    
    for _, row in spikes.iterrows():
        if row['row_id'] not in flagged_ids:
            findings.append({
                'date': row['date'],
                'vendor': row['vendor'],
                'amount': row['amount'] - row['prev_amt'],
                'issue': f"UNAUTHORIZED PRICE SPIKE (+{((row['amount']/row['prev_amt'])-1)*100:.0f}%)"
            })

    # FINAL RETURN: Must be indented to be part of the function
    return pd.DataFrame(findings)
# --- 2. THE PRODUCT ENGINE (The PDF Generator) ---
class AuditPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'LEDGERLOCK FINANCIAL FORENSICS', 0, 1, 'C')
        self.set_font('Arial', 'I', 8)
        self.cell(0, 5, f'Audit ID: LL-{datetime.datetime.now().strftime("%Y%m%d-%H%M")}', 0, 1, 'C')
        self.ln(10)

def generate_pdf_report(findings, waste):
    pdf = AuditPDF()
    pdf.add_page()
    
    pdf.set_fill_color(245, 245, 245)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 12, f"EXECUTIVE SUMMARY: Total Leakage Identified: ${waste:,.2f}", 1, 1, 'L', True)
    pdf.ln(5)
    
    pdf.set_fill_color(33, 37, 41)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(35, 10, "Date", 1, 0, 'C', True)
    pdf.cell(75, 10, "Vendor", 1, 0, 'C', True)
    pdf.cell(80, 10, "Issue Detected", 1, 1, 'C', True)
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", '', 9)
    
    for _, row in findings.iterrows():
        pdf.cell(35, 10, str(row['date'].date()), 1)
        pdf.cell(75, 10, str(row['vendor'])[:40], 1) # Cap vendor name length
        pdf.cell(80, 10, f"{row['issue']} (${row['amount']:,.2f})", 1, 1)
    
    pdf.ln(20)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 10, "Certified Audit Signature: _________________________________", 0, 1)
    return pdf.output(dest='S').encode('latin-1')

# --- 3. THE INTERFACE ---
st.set_page_config(page_title="LedgerLock Core", layout="wide")
st.title("🏛️ LedgerLock: Forensic Audit Engine")
st.markdown("---")

uploaded_file = st.file_uploader("Upload Company Ledger (CSV)", type="csv")
if uploaded_file:
    import csv
    import io

    # 1. READ THE FILE MANUALLY TO "SMELL" THE DELIMITER
    stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8", errors="ignore"))
    sample = stringio.read(2048) # Read a small chunk to analyze
    stringio.seek(0) # Reset to start

    try:
        dialect = csv.Sniffer().sniff(sample)
        sep = dialect.delimiter
    except:
        sep = ',' # Fallback to comma if sniffing fails

    # 2. LOAD DATA WITH DETECTED SEPARATOR
    df_raw = pd.read_csv(stringio, sep=sep)
    
    # 3. STRIP ALL WHITESPACE FROM COLUMN NAMES
    # This fixes " Date " vs "Date"
    df_raw.columns = [str(col).strip() for col in df_raw.columns]
    
    st.write("### 🧩 Map Your Columns")
    columns = df_raw.columns.tolist()

    # Smart Defaults logic
    def get_default(target, cols):
        for i, c in enumerate(cols):
            if target.lower() in str(c).lower(): return i
        return 0

    col_a, col_b, col_c = st.columns(3)
    date_col = col_a.selectbox("Date Column", columns, index=get_default('date', columns))
    vendor_col = col_b.selectbox("Vendor Column", columns, index=get_default('vendor', columns))
    amount_col = col_c.selectbox("Amount Column", columns, index=get_default('amount', columns))
    
# --- 3. THE INTERFACE & ENGINE ---
if st.button("🚀 Run Forensic Audit"):
    # 1. Map columns into a standard format
    df_clean = pd.DataFrame({
        'date': df_raw[date_col], 
        'vendor': df_raw[vendor_col], 
        'amount': df_raw[amount_col]
    })
    
    # 2. Run the audit logic
    results = run_audit(df_clean)
    
    # 3. SAVE TO SESSION STATE (The "Memory" Fix)
    st.session_state.findings = results
    st.session_state.total_waste = results['amount'].sum() if not results.empty else 0
    
    # 4. CLOUD SYNC (The "Anti-Spam" Fix)
    if not results.empty and st.session_state.get('last_sync') != uploaded_file.name:
        for _, row in results.iterrows():
            try:
                supabase.table("audits").insert({
                    "vendor": str(row['vendor']), 
                    "amount": float(row['amount']),
                    "issue": str(row['issue']), 
                    "user_email": "guest@example.com"
                }).execute()
            except Exception as e: 
                st.error(f"Sync Error: {e}")
        st.session_state.last_sync = uploaded_file.name

# --- 4. PERSISTENT DISPLAY (Must be OUTSIDE the button block) ---
if st.session_state.findings is not None:
    findings = st.session_state.findings
    total_waste = st.session_state.total_waste
    
    if not findings.empty:
        st.success(f"📊 {len(findings)} potential leaks identified.")
        
        # Metrics Display
        c1, c2, c3 = st.columns(3)
        c1.metric("Monthly Waste", f"${total_waste:,.2f}")
        c2.metric("Annualized Recovery", f"${total_waste * 12:,.2f}")
        c3.metric("Audit Health", f"{max(0, 100 - len(findings))}%")
        
        # PDF Generation
        pdf_bytes = generate_pdf_report(findings, total_waste)
        st.download_button("📥 Download Certified Audit", data=pdf_bytes, 
                           file_name="LedgerLock_Report.pdf", mime="application/pdf")

        # Risk Analysis (The Expanders)
        st.write("### 🚩 Actionable Leakage")
        for i, row in findings.iterrows():
            with st.expander(f"{row['vendor']} - ${row['amount']:,.2f}"):
                st.write(f"**Issue:** {row['issue']}")
                st.text_area("Dispute Draft", f"Regarding the ${row['amount']} charge...", key=f"mail_{i}")
    else:
        st.success("✅ No financial leakage detected.")

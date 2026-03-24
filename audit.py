
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
            if i >= j or row_b['row_id'] in flagged_ids: continue
            
            # Match if: Same Amount AND (Same simplified name OR High Fuzzy Score)
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

    # --- 3. PASS 2: PRICE SPIKES (Deep Scan) ---
    # We group by the 'vendor_group' to catch spikes even if the name changed slightly
    df_sorted = df.sort_values(['vendor_group', 'date'])
    df_sorted['prev_amt'] = df_sorted.groupby('vendor_group')['amount'].shift(1)
    
    # Flag spikes where current amount is 20%+ higher than previous
    spikes = df_sorted[(df_sorted['amount'] > df_sorted['prev_amt'] * 1.2) & (df_sorted['prev_amt'] > 0)]
    
    for _, row in spikes.iterrows():
        # Only flag the spike if this specific row wasn't already caught as a duplicate
        if row['row_id'] not in flagged_ids:
            findings.append({
                'date': row['date'],
                'vendor': row['vendor'],
                'amount': row['amount'] - row['prev_amt'], # WASTE = The Increase
                'issue': f"UNAUTHORIZED PRICE SPIKE (+{((row['amount']/row['prev_amt'])-1)*100:.0f}%)"
            })

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
    
if st.button("🚀 Run Forensic Audit"):
    df_clean = pd.DataFrame({
        'date': df_raw[date_col],
        'vendor': df_raw[vendor_col],
        'amount': df_raw[amount_col]
    })

    # Professional Vendor Sanitization
    def clean_vendor(v):
        v = str(v).lower()
        v = re.sub(r'[^a-z0-9\s]', '', v)
        v = v.replace('inc', '').replace('llc', '').replace('co', '').replace('company', '')
        return v.strip()

    df_clean['vendor'] = df_clean['vendor'].apply(clean_vendor)
    findings = run_audit(df_clean)
    
    # --- EVERYTHING BELOW MOVED INSIDE THE BUTTON BLOCK ---
    if not findings.empty:
        # --- THE CLOUD SAVE ENGINE ---
        for _, row in findings.iterrows():
            try:
                data_to_save = {
                    "vendor": str(row['vendor']),
                    "amount": float(row['amount']),
                    "issue": str(row['issue']),
                    "user_email": "guest@example.com"
                }
                supabase.table("audits").insert(data_to_save).execute()
            except Exception as e:
                st.error(f"Cloud Save Error: {e}")
        
        st.success(f"📊 {len(findings)} findings backed up to the Cloud Ledger.")

        # --- KPI SECTION (Precision Math) ---
        total_waste = findings['amount'].sum()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Identified Monthly Waste", f"${total_waste:,.2f}")
        c2.metric("Annualized Recovery", f"${total_waste * 12:,.2f}", delta="Actionable")
        c3.metric("Audit Health", f"{max(0, 100 - len(findings))}%")

        # --- SIDEBAR IMPACT ---
        st.sidebar.header("📈 Financial Impact")
        st.sidebar.metric("Monthly Leakage", f"${total_waste:,.2f}")
        st.sidebar.metric("5-Year Projected Loss", f"${total_waste * 12 * 5:,.2f}", delta="Risk", delta_color="inverse")
        
        # --- THE FORENSIC RISK ANALYSIS DISPLAY ---
        st.write("### 🚩 Actionable Leakage Detected")
        
        pdf_bytes = generate_pdf_report(findings, total_waste)
        st.download_button("📥 Download Certified Forensic Audit", data=pdf_bytes, 
                           file_name="LedgerLock_Report.pdf", mime="application/pdf")

        for i, row in findings.iterrows():
            risk_score = 0
            if row['amount'] > 1000: risk_score += 40
            if "Match" in row['issue'] or "DUPLICATE" in row['issue']: risk_score += 30
            if "SPIKE" in row['issue']: risk_score += 30
            
            if risk_score >= 70: label = "🔴 CRITICAL RISK"
            elif risk_score >= 40: label = "🟠 HIGH WARNING"
            else: label = "🟡 MONITOR"

            with st.expander(f"{label} (Score: {risk_score}) | {row['vendor']} - ${row['amount']:,.2f}"):
                st.write(f"**Detected Issue:** {row['issue']}")
                
                clean_amt = f"{row['amount']:,.2f}"
                clean_date = row['date'].strftime('%Y-%m-%d')
                
                email_body = (
                    f"Subject: Billing Inquiry: Potential Overcharge - {row['vendor']}\n\n"
                    f"To the Billing Department,\n\n"
                    f"Our internal audit (LedgerLock) flagged a discrepancy of ${clean_amt} "
                    f"on {clean_date}.\n\n"
                    f"Issue: {row['issue']}\n\n"
                    f"Please review this transaction for a potential credit.\n\n"
                    f"Reference: LL-{clean_date.replace('-', '')}"
                )
                
                st.text_area("One-Click Dispute Draft", email_body, height=200, key=f"risk_txt_{i}")
    else:
        st.success("✅ No financial leakage detected. This company ledger is lean.")

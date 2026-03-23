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
    # Standardize and Clean Data
    df.columns = df.columns.str.lower().str.strip()
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
    df = df.dropna(subset=['date', 'amount'])
    
    findings = []
    processed_indices = set()

    # --- ALGORITHM 1: FUZZY DUPLICATE DETECTION ---
    # Convert to list for faster indexing
    df_list = df.reset_index(drop=True)
    
    for i in range(len(df_list)):
        if i in processed_indices: continue

        for j in range(i + 1, len(df_list)):
            if j in processed_indices: continue

            row = df_list.iloc[i]
            compare_row = df_list.iloc[j]

            same_amount = abs(row['amount'] - compare_row['amount']) < 0.01
            name_score = fuzz.token_set_ratio(str(row['vendor']), str(compare_row['vendor']))
            days_diff = abs((row['date'] - compare_row['date']).days)

            if same_amount and name_score > 70 and days_diff <= 3:
                findings.append({
                    'date': row['date'],
                    'vendor': f"{row['vendor']} / {compare_row['vendor']}",
                    'amount': row['amount'],
                    'issue': f"FUZZY DUPLICATE ({name_score}% Match)"
                })
                processed_indices.add(i)
                processed_indices.add(j)
                break

    # --- ALGORITHM 2: PRICE ESCALATION DETECTION ---
    df_sorted = df.sort_values(['vendor', 'date'])
    df_sorted['prev_amt'] = df_sorted.groupby('vendor')['amount'].shift(1)
    
    spikes = df_sorted[(df_sorted['amount'] > df_sorted['prev_amt'] * 1.2) & (df_sorted['prev_amt'] > 0)]
    
    for _, row in spikes.iterrows():
        findings.append({
            'date': row['date'],
            'vendor': row['vendor'],
            'amount': row['amount'],
            'issue': f"PRICE SPIKE (+{((row['amount']/row['prev_amt'])-1)*100:.0f}%)"
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
        if not findings.empty:
            # Loop through each finding and save it to the 'audits' table
            for _, row in findings.iterrows():
                data_to_save = {
                    "vendor": str(row['vendor']),
                    "amount": float(row['amount']),
                    "issue": str(row['issue'])
                }
                # This pushes the data to your Supabase table
                supabase.table("audits").insert(data_to_save).execute()
            
            st.success(f"📊 {len(findings)} findings backed up to the Cloud Ledger.")
        total_waste = findings['amount'].sum() if not findings.empty else 0
        
        # KPIs
        c1, c2, c3 = st.columns(3)
        c1.metric("Identified Monthly Waste", f"${total_waste:,.2f}")
        c2.metric("Annualized Recovery", f"${total_waste * 12:,.2f}", delta="Actionable")
        c3.metric("Audit Health", f"{max(0, 100 - len(findings))}%")

     # --- NEW: ACTION CENTER & ROI SIDEBAR ---
        if not findings.empty:
            # 1. THE SIDEBAR (The "Fear Factor" Math)
            st.sidebar.header("📈 Financial Impact")
            st.sidebar.metric("Monthly Leakage", f"${total_waste:,.2f}")
            st.sidebar.metric("5-Year Projected Loss", f"${total_waste * 12 * 5:,.2f}", delta="Risk", delta_color="inverse")
            
            st.sidebar.markdown("---")
            st.sidebar.write("### 💰 LedgerLock Recovery")
            commission = total_waste * 0.15 # 15% Success Fee
            st.sidebar.metric("Potential Commission", f"${commission:,.2f}")
            st.sidebar.info("Tip: Charge a 15% recovery fee to turn this script into a business.")

            # 2. THE MAIN DISPLAY
            pdf_bytes = generate_pdf_report(findings, total_waste)
            st.download_button("📥 Download Certified Forensic Audit", data=pdf_bytes, 
                               file_name="LedgerLock_Report.pdf", mime="application/pdf")
            
            st.write("### 🚩 Actionable Leakage Detected")
            
            # 3. THE DISPUTE GENERATOR LOOP
            for i, row in findings.iterrows():
                # Create an expandable box for every finding
                with st.expander(f"Ref #LL-{i:03}: {row['vendor']} - ${row['amount']:,.2f}"):
                    st.write(f"**Reason:** {row['issue']}")
                    
                    # Generate the Professional Dispute Email
                    email_body = f"""Subject: Billing Inquiry: Potential Duplicate/Overcharge - {row['vendor']}

To the Billing Department,

Our internal financial audit (LedgerLock) has flagged a discrepancy regarding a charge of ${row['amount']:.2f} on {row['date'].date()}.

Issue Identified: {row['issue']}

Please review this transaction. If this was a duplicate or unauthorized escalation, we request a formal credit to our account.

Reference ID: LL-{row['date'].strftime('%Y%m%d')}"""
                    
                    st.text_area("Dispute Draft (Copy & Paste)", email_body, height=200, key=f"txt_{i}")
                    st.caption("Copy this text and send it to the vendor's billing department to recover these funds.")
        else:
            st.success("✅ No financial leakage detected. This company ledger is lean.")

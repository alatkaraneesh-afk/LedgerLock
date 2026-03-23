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
    # THE FIX: sep=None and engine='python' tells Pandas to GUESS the delimiter
    # it will find ',', ';', or '|' automatically.
    df_raw = pd.read_csv(uploaded_file, sep=None, engine='python')
    
    # Clean the column names of any weird characters or spaces
    df_raw.columns = [re.sub(r'[^a-zA-Z0-9]', '', str(col)) for col in df_raw.columns]
    
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
        total_waste = findings['amount'].sum() if not findings.empty else 0
        
        # KPIs
        c1, c2, c3 = st.columns(3)
        c1.metric("Identified Monthly Waste", f"${total_waste:,.2f}")
        c2.metric("Annualized Recovery", f"${total_waste * 12:,.2f}", delta="Actionable")
        c3.metric("Audit Health", f"{max(0, 100 - len(findings))}%")

        if not findings.empty:
            pdf_bytes = generate_pdf_report(findings, total_waste)
            st.download_button("📥 Download Certified PDF", data=pdf_bytes, 
                               file_name="LedgerLock_Report.pdf", mime="application/pdf")
            st.write("### 🚩 Detected Financial Leakage")
            st.dataframe(findings, use_container_width=True)
        else:
            st.success("✅ No leakage detected.")

import streamlit as st
import pandas as pd
from fpdf import FPDF
import datetime
from thefuzz import fuzz
# --- 1. THE DATA ENGINE (The "Brain") ---
def run_audit(df):
    # 1. Standardize column names
    df.columns = df.columns.str.lower().str.strip()
    
    # 2. Force Data Types
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
    
    findings = []
    processed_indices = set()

    # --- ADVANCED ALGORITHM: FUZZY DUPLICATE DETECTION ---
    # We compare every row to every other row to find "Close Matches"
    for i, row in df.iterrows():
        if i in processed_indices: continue
        
        for j, compare_row in df.iloc[i+1:].iterrows():
            if j + i + 1 in processed_indices: continue
            
            # Check 1: Is the amount the same?
            same_amount = row['amount'] == compare_row['amount']
            
            # Check 2: How similar are the names? (0 to 100)
            name_score = fuzz.token_set_ratio(str(row['vendor']), str(compare_row['vendor']))
            
            # Check 3: Are the dates within 3 days of each other?
            days_diff = abs((row['date'] - compare_row['date']).days)
            
            # If it's a "Close Match" (High name similarity + Same amount + Close dates)
            if name_score > 85 and same_amount and days_diff <= 3:
                findings.append({
                    'date': row['date'],
                    'vendor': f"{row['vendor']} | {compare_row['vendor']}",
                    'amount': row['amount'],
                    'issue': f"FUZZY DUPLICATE ({name_score}% Match)"
                })
                processed_indices.add(i)
                processed_indices.add(j + i + 1)

    # --- ALGORITHM 2: PRICE ESCALATION (>20% jump) ---
    df = df.sort_values(['vendor', 'date'])
    df['prev_amt'] = df.groupby('vendor')['amount'].shift(1)
    spikes = df[(df['amount'] > df['prev_amt'] * 1.2) & (df['prev_amt'] > 0)]
    
    for _, row in spikes.iterrows():
        findings.append({
            'date': row['date'],
            'vendor': row['vendor'],
            'amount': row['amount'],
            'issue': f"PRICE SPIKE (+{((row['amount']/row['prev_amt'])-1)*100:.1f}%)"
        })

    return pd.DataFrame(findings)

# --- 2. THE PRODUCT ENGINE (The PDF Generator) ---
class AuditPDF(FPDF):
    def header(self):
        # Professional Header with Timestamp
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'LEDGERLOCK FINANCIAL FORENSICS', 0, 1, 'C')
        self.set_font('Arial', 'I', 8)
        self.cell(0, 5, f'Audit ID: LL-{datetime.datetime.now().strftime("%Y%m%d-%H%M")}', 0, 1, 'C')
        self.ln(10)

def generate_pdf_report(dupes, spikes, waste):
    pdf = AuditPDF()
    pdf.add_page()
    
    # Executive Summary Box
    pdf.set_fill_color(245, 245, 245)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 12, f"EXECUTIVE SUMMARY: Total Leakage Identified: ${waste:,.2f}", 1, 1, 'L', True)
    pdf.ln(5)
    
    # Findings Table Header
    pdf.set_fill_color(33, 37, 41)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(40, 10, "Date", 1, 0, 'C', True)
    pdf.cell(90, 10, "Vendor", 1, 0, 'C', True)
    pdf.cell(60, 10, "Amount", 1, 1, 'C', True)
    
    # Findings Table Rows
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", '', 10)
    
    # Add Duplicates to PDF
    for _, row in dupes.iterrows():
        pdf.cell(40, 10, str(row['date'].date()), 1)
        pdf.cell(90, 10, str(row['vendor']), 1)
        pdf.cell(60, 10, f"${row['amount']:,.2f} (DUPE)", 1, 1)

    # Add Spikes to PDF
    for _, row in spikes.iterrows():
        pdf.cell(40, 10, str(row['date'].date()), 1)
        pdf.cell(90, 10, str(row['vendor']), 1)
        pdf.cell(60, 10, f"${row['amount']:,.2f} (SPIKE)", 1, 1)
    
    pdf.ln(20)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 10, "Certified Audit Signature: _________________________________", 0, 1)
    pdf.set_font("Arial", 'I', 8)
    pdf.cell(0, 5, "Confidential - Proprietary LedgerLock Analysis", 0, 1)
    
    return pdf.output(dest='S').encode('latin-1')

# --- 3. THE INTERFACE (The Dashboard) ---
st.set_page_config(page_title="LedgerLock Core", layout="wide")
st.title("🏛️ LedgerLock: Forensic Audit Engine")
st.markdown("---")

uploaded_file = st.file_uploader("Upload Company Ledger (CSV)", type="csv")

if uploaded_file:
    df_raw = pd.read_csv(uploaded_file)
    dupes, spikes = run_audit(df_raw)
    
    # Calculate Total Waste (Difference in spikes + Total of duplicates)
    spike_waste = (spikes['amount'] - spikes['prev_amt']).sum()
    dupe_waste = dupes['amount'].sum()
    total_waste = spike_waste + dupe_waste
    
    # Key Performance Indicators
    col1, col2, col3 = st.columns(3)
    col1.metric("Identified Monthly Waste", f"${total_waste:,.2f}")
    col2.metric("Annualized Recovery", f"${total_waste * 12:,.2f}", delta="Actionable")
    col3.metric("Audit Health", f"{max(0, 100 - len(dupes) - len(spikes))}%")

    # The PDF Download Button
    if not dupes.empty or not spikes.empty:
        pdf_bytes = generate_pdf_report(dupes, spikes, total_waste)
        st.download_button(
            label="📥 Download Certified Forensic Audit",
            data=pdf_bytes,
            file_name=f"LedgerLock_Audit_{datetime.date.today()}.pdf",
            mime="application/pdf"
        )
        
        st.write("### 🚩 Detected Financial Leakage")
        # Combine dupes and spikes for the on-screen table
        findings = pd.concat([dupes, spikes]).drop_duplicates()
        st.dataframe(findings[['date', 'vendor', 'amount']], use_container_width=True)
    else:
        st.success("✅ No financial leakage detected. This company ledger is lean.")
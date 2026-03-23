import streamlit as st
import pandas as pd
from fpdf import FPDF
import datetime
from thefuzz import fuzz
# --- 1. THE DATA ENGINE (The "Brain") ---
def run_audit(df):
    """
    The LedgerLock Core Engine: 
    Uses Fuzzy String Matching and Time-Window Analysis to find financial leakage.
    """
    # 1. Standardize and Clean Data
    df.columns = df.columns.str.lower().str.strip()
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
    
    # Remove any rows with broken dates/amounts so the math doesn't crash
    df = df.dropna(subset=['date', 'amount'])
    
    findings = []
    processed_indices = set()

    # --- ALGORITHM 1: FUZZY DUPLICATE DETECTION ---
# Safer indexing version (fixes duplicate/missed detection bugs)

for i in range(len(df)):
    if i in processed_indices:
        continue

    for j in range(i + 1, len(df)):
        if j in processed_indices:
            continue

        row = df.iloc[i]
        compare_row = df.iloc[j]

        # Check A: Are the amounts identical?
        same_amount = abs(row['amount'] - compare_row['amount']) < 0.01

        # Check B: Name Similarity
        name_score = fuzz.token_set_ratio(str(row['vendor']), str(compare_row['vendor']))

        # Check C: Date proximity
        days_diff = abs((row['date'] - compare_row['date']).days)

        # THE LOGIC GATE
        if same_amount and name_score > 70 and days_diff <= 3:
            findings.append({
                'date': row['date'],
                'vendor': f"{row['vendor']} / {compare_row['vendor']}",
                'amount': row['amount'],
                'issue': f"FUZZY DUPLICATE ({name_score}% Match)"
            })

            # Mark both as processed
            processed_indices.add(i)
            processed_indices.add(j)
            break
    # --- ALGORITHM 2: PRICE ESCALATION DETECTION ---
    # Sort by vendor and date to see the "Timeline" of spending
    df_sorted = df.sort_values(['vendor', 'date'])
    df_sorted['prev_amt'] = df_sorted.groupby('vendor')['amount'].shift(1)
    
    # Detect jumps of more than 20%
    spikes = df_sorted[(df_sorted['amount'] > df_sorted['prev_amt'] * 1.2) & (df_sorted['prev_amt'] > 0)]
    
    for _, row in spikes.iterrows():
        # Check if we already flagged this row as a duplicate
        # (We don't want to double-count a spike if it's actually just a dupe)
        findings.append({
            'date': row['date'],
            'vendor': row['vendor'],
            'amount': row['amount'],
            'issue': f"PRICE SPIKE (+{((row['amount']/row['prev_amt'])-1)*100:.0f}%)"
        })

    # Return as a clean DataFrame for the Streamlit UI
    return pd.DataFrame(findings)def run_audit(df):
    """
    The LedgerLock Core Engine: 
    Uses Fuzzy String Matching and Time-Window Analysis to find financial leakage.
    """
    # 1. Standardize and Clean Data
    df.columns = df.columns.str.lower().str.strip()
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
    
    # Remove any rows with broken dates/amounts
    df = df.dropna(subset=['date', 'amount'])
    
    findings = []
    processed_indices = set()

    # --- ALGORITHM 1: FUZZY DUPLICATE DETECTION ---
    for i in range(len(df)):
        if i in processed_indices:
            continue

        for j in range(i + 1, len(df)):
            if j in processed_indices:
                continue

            row = df.iloc[i]
            compare_row = df.iloc[j]

            # Check A: Are the amounts identical?
            same_amount = abs(row['amount'] - compare_row['amount']) < 0.01

            # Check B: Name Similarity
            name_score = fuzz.token_set_ratio(str(row['vendor']), str(compare_row['vendor']))

            # Check C: Date proximity
            days_diff = abs((row['date'] - compare_row['date']).days)

            # Logic gate
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

    # Return findings — MUST be inside the function
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

# THIS IS THE MISSING LINE:
uploaded_file = st.file_uploader("Upload Company Ledger (CSV)", type="csv")

if uploaded_file:
    df_raw = pd.read_csv(uploaded_file)

    st.write("### 🧩 Map Your Columns (Required)")
    
    columns = df_raw.columns.tolist()

    date_col = st.selectbox("Select Date Column", columns)
    vendor_col = st.selectbox("Select Vendor Column", columns)
    amount_col = st.selectbox("Select Amount Column", columns)

    if st.button("Run Audit"):
        # Create standardized dataframe
        df_clean = pd.DataFrame({
            'date': df_raw[date_col],
            'vendor': df_raw[vendor_col],
            'amount': df_raw[amount_col]
        })

        # --- BASIC CLEANING ---
        import re

        def clean_vendor(v):
            v = str(v).lower()
            v = re.sub(r'[^a-z0-9\s]', '', v)
            v = v.replace('inc', '').replace('llc', '').replace('co', '').replace('company', '')
            return v.strip()

        df_clean['vendor'] = df_clean['vendor'].apply(clean_vendor)

        # Run your audit engine
        findings = run_audit(df_clean)

        # Calculate Waste
        total_waste = findings['amount'].sum() if not findings.empty else 0
        
        # KPIs
        col1, col2, col3 = st.columns(3)
        col1.metric("Identified Monthly Waste", f"${total_waste:,.2f}")
        col2.metric("Annualized Recovery", f"${total_waste * 12:,.2f}", delta="Actionable")
        
        health = max(0, 100 - len(findings))
        col3.metric("Audit Health", f"{health}%")

        # PDF + Results
        if not findings.empty:
            pdf_bytes = generate_pdf_report(findings, pd.DataFrame(), total_waste)
            
            st.download_button(
                label="📥 Download Certified Forensic Audit",
                data=pdf_bytes,
                file_name=f"LedgerLock_Audit_{datetime.date.today()}.pdf",
                mime="application/pdf"
            )
            
            st.write("### 🚩 Detected Financial Leakage")
            st.dataframe(findings[['date', 'vendor', 'amount', 'issue']], use_container_width=True)
        else:
            st.success("✅ No financial leakage detected. This company ledger is lean.")

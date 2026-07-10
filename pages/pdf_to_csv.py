"""Streamlit page: convert statement PDFs to CSV."""

from __future__ import annotations

import streamlit as st

from csv_format import STANDARD_COLUMNS, normalized_to_standard, standard_to_csv_bytes
from pdf_parser import extract_pdf_debug_text
from pdf_to_csv import extract_pdfs

st.title("PDF to CSV")
st.caption(
    "Step 1: Upload credit card statement PDFs here, review the extraction, and download a CSV. "
    "Step 2: Use that CSV in **Finance Tracker**."
)

uploaded_pdfs = st.file_uploader(
    "Upload statement PDF files",
    type=["pdf"],
    accept_multiple_files=True,
    help="Upload one or more PDF statements. They will be combined into a single CSV download.",
)

if not uploaded_pdfs:
    st.info("Upload PDF statement files to extract transactions.")
    with st.expander("How this works"):
        st.markdown(
            """
            1. Upload your bank statement PDF(s)
            2. Review the extracted transactions below
            3. Download the combined CSV
            4. Open **Finance Tracker** in the sidebar and upload the CSV

            **Output columns:** """ + ", ".join(f"`{c}`" for c in STANDARD_COLUMNS) + """

            **American Express** — multi-line statement layout is supported.

            **Apple Card:** Wallet → statement → **Export Transactions** (CSV) skips this step.

            **Privacy:** PDF conversion runs **locally in your browser session** on this machine.
            Statement files are **not** sent to any external server during conversion.
            """
        )
    with st.expander("Privacy"):
        st.markdown(
            """
            - PDF bytes stay on the computer running Streamlit
            - No cloud upload, no API calls during PDF → CSV
            - Download the CSV and use it in Finance Tracker
            - Optional auto-categorization (in Finance Tracker) is separate and on by default
            """
        )
    st.stop()

try:
    transactions = extract_pdfs(uploaded_pdfs)
except ValueError as exc:
    st.error(str(exc))
    with st.expander("PDF troubleshooting (extracted text preview)"):
        for pdf_file in uploaded_pdfs:
            st.markdown(f"**{pdf_file.name}**")
            preview = extract_pdf_debug_text(pdf_file.getvalue())
            if preview.strip():
                st.code(preview, language=None)
            else:
                st.warning("No readable text — this PDF is likely a scanned image.")
    st.stop()

export_df = normalized_to_standard(transactions)
csv_name = "combined_statements.csv" if len(uploaded_pdfs) > 1 else uploaded_pdfs[0].name.replace(".pdf", ".csv")

st.success(f"Extracted **{len(transactions):,}** transactions from **{len(uploaded_pdfs)}** PDF(s).")

st.download_button(
    label="Download CSV",
    data=standard_to_csv_bytes(transactions),
    file_name=csv_name,
    mime="text/csv",
    type="primary",
)

st.subheader("Preview")
st.dataframe(
    export_df,
    use_container_width=True,
    hide_index=True,
)

st.caption("When this looks right, download the CSV and upload it in **Finance Tracker**.")

"""
Generates the 6 demo-case intake PDFs into documents/demo_pdfs/.

Run with: conda run -n pa_hack python3 documents/generate_demo_pdfs.py

Each PDF is a standalone Prior Authorization Request document meant to be
uploaded through the Patient Portal (POST /api/v1/upload), paired with the
query text documented in documents/demo.md. Same document shape as
backend/scripts/seed_hero_cases.py's HERO_CASES, kept separate so the demo
set (PA-101..PA-106) doesn't collide with the hero cases (PA-001..PA-005).
"""
from pathlib import Path

from fpdf import FPDF

OUT_DIR = Path(__file__).resolve().parent / "demo_pdfs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DEMO_CASES = [
    {
        "key": "PA-101",
        "filename": "PA-101_hip_replacement_request.pdf",
        "text": (
            "Prior Authorization Request\n\n"
            "Patient Name: Dorothy Mensah\nDate of Birth: 1950-02-11\nPatient Zip: 90210\n\n"
            "Clinical Note:\nDiagnosis: M16.11 (unilateral primary osteoarthritis, right hip)\n"
            "Requested Service: Total hip arthroplasty (CPT 27130)\n\n"
            "Billing Sheet:\nBilled Amount: $1300.00\n"
            "Prescribing Physician: Dr. Alan Whitcombe\nProvider NPI: 1002003010\n"
        ),
        "query": "Please check whether this hip replacement is covered under my plan "
        "and whether the billed amount is reasonable.",
    },
    {
        "key": "PA-102",
        "filename": "PA-102_vasectomy_request.pdf",
        "text": (
            "Prior Authorization Request\n\n"
            "Patient Name: Marcus Delaney\nDate of Birth: 1962-07-30\nPatient Zip: 36104\n\n"
            "Clinical Note:\nDiagnosis: Z30.2 (encounter for sterilization)\n"
            "Requested Service: Vasectomy, unilateral or bilateral (CPT 55250)\n\n"
            "Billing Sheet:\nBilled Amount: $350.00\n"
            "Prescribing Physician: Dr. Priya Ramachandran\nProvider NPI: 1002003011\n"
        ),
        "query": "Is this vasectomy procedure covered under my plan?",
    },
    {
        "key": "PA-103",
        "filename": "PA-103_lumbar_decompression_request.pdf",
        "text": (
            "Prior Authorization Request\n\n"
            "Patient Name: Irene Kowalczyk\nDate of Birth: 1957-04-18\nPatient Zip: 10001\n\n"
            "Clinical Note:\nDiagnosis: J06.9 (acute upper respiratory infection, unspecified "
            "/ common cold)\n"
            "Requested Service: Laminotomy with decompression of nerve root, single lumbar "
            "level (CPT 63030)\n\n"
            "Billing Sheet:\nBilled Amount: $1100.00\n"
            "Prescribing Physician: Dr. Kevin Ostrander\nProvider NPI: 1002003012\n"
        ),
        "query": "Please check if this procedure is covered and appropriate for my "
        "diagnosis.",
    },
    {
        "key": "PA-104",
        "filename": "PA-104_endoscopy_request.pdf",
        "text": (
            "Prior Authorization Request\n\n"
            "Patient Name: Walter Iniguez\nDate of Birth: 1949-12-05\nPatient Zip: 60601\n\n"
            "Clinical Note:\nDiagnosis: K21.9 (gastro-esophageal reflux disease without "
            "esophagitis)\n"
            "Requested Service: Upper GI endoscopy with biopsy (CPT 43239)\n\n"
            "Billing Sheet:\nBilled Amount: $5000.00\n"
            "Prescribing Physician: Dr. Naomi Feldstein\nProvider NPI: 1002003013\n"
        ),
        "query": "Is this billed amount reasonable for my endoscopy procedure compared to "
        "what Medicare usually pays?",
    },
    {
        "key": "PA-105",
        "filename": "PA-105_knee_injection_intake.pdf",
        "text": (
            "Prior Auth Req (handwritten intake, low legibility)\n\n"
            "Pt: B. Alvarez?  dob approx 1953  zip 30301\n\n"
            "note: r knee pain (M25.561) pt needs knee injection thing cpt maybe 20610 or "
            "20605 not fully sure billing unclear\n\n"
            "billed: ~$180  npi: illegible  physician: Dr. T.?\n"
        ),
        "query": "Can you check if this request is complete and covered?",
    },
    {
        "key": "PA-106",
        "filename": "PA-106_knee_replacement_request.pdf",
        "text": (
            "Prior Authorization Request\n\n"
            "Patient Name: Sylvia Brennan\nDate of Birth: 1946-09-22\nPatient Zip: 90210\n\n"
            "Clinical Note:\nDiagnosis: M17.11 (unilateral primary osteoarthritis, right "
            "knee)\n"
            "Requested Service: Total knee arthroplasty (CPT 27447)\n\n"
            "Billing Sheet:\nBilled Amount: $1800.00\n"
            "Prescribing Physician: Dr. Michael Osei\nProvider NPI: 1002003014\n"
        ),
        "query": "Please review whether this knee replacement is covered and whether the "
        "billed cost is fair.",
    },
]


def write_pdf(case: dict) -> Path:
    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Helvetica", size=12)
    for line in case["text"].split("\n"):
        pdf.cell(0, 8, line, new_x="LMARGIN", new_y="NEXT")

    out_path = OUT_DIR / case["filename"]
    pdf.output(str(out_path))
    return out_path


def main():
    for case in DEMO_CASES:
        path = write_pdf(case)
        print(f"[{case['key']}] wrote {path}")


if __name__ == "__main__":
    main()

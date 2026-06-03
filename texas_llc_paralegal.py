"""
Texas LLC Paralegal Back-Office Tool
ParalegalRob — Internal Use Only

Modules:
  1. Formation    — Form 205 + Operating Agreement + Mailing Checklist
  2. Reinstatement — Form 801 (tax forfeiture) / Form 811 (other termination) + Checklist
  3. Dissolution  — Form 651 (Certificate of Termination) + Winding-Up Checklist
  4. Foreign Reg  — Form 304 (Foreign LLC Registration) + Checklist

Each module:
  - Collects client intake via sidebar
  - Generates one or more fillable PDF documents
  - Outputs a delivery checklist (what to mail, fees, notes to client)
"""

import streamlit as st
import datetime
import re
from io import BytesIO

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

APP_NAME  = "Texas LLC Paralegal — ParalegalRob"
YEAR      = datetime.datetime.now().year
BRAND_COL = "#1a3a5c"
ACCENT    = "#c8a44a"

US_STATES = [
    "TX","AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID",
    "IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO",
    "MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA",
    "RI","SC","SD","TN","UT","VT","VA","WA","WV","WI","WY"
]

# ─────────────────────────────────────────────
# PAGE CONFIG & CSS
# ─────────────────────────────────────────────

st.set_page_config(
    page_title=APP_NAME,
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(f"""
<style>
.block-container {{ padding-top: 1.5rem; padding-bottom: 3rem; max-width: 900px; }}
.module-title {{ font-size: 1.5rem; font-weight: 700; color: {BRAND_COL}; margin-bottom: 0; }}
.module-sub {{ font-size: 0.9rem; color: #555; margin-top: 2px; margin-bottom: 1.5rem; }}
.section-head {{ font-size: 0.7rem; text-transform: uppercase; letter-spacing: .08em;
                 color: #888; margin: 1.2rem 0 .3rem; font-weight: 600; }}
.checklist-box {{ background: #f0f7ff; border-left: 4px solid {BRAND_COL};
                  border-radius: 6px; padding: 14px 18px; margin: 1rem 0; font-size: .88rem; }}
.fee-tag {{ display:inline-block; background: #fff3cd; border:1px solid #ffc107;
            border-radius: 4px; padding: 2px 8px; font-size:.8rem; font-weight:600; color:#7a5700; }}
.warn-box {{ background: #fff8e1; border: 1px solid #f0c040;
             border-radius: 6px; padding: 10px 14px; font-size: .82rem; color: #5a4a00; margin: .6rem 0; }}
.doc-ready {{ background: #e8f5e9; border-left: 4px solid #2e7d32;
              border-radius: 6px; padding: 12px 18px; margin: 1rem 0; font-size:.88rem; }}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _wrap(text: str, max_chars: int = 75) -> list:
    words = (text or "").split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= max_chars:
            cur = (cur + " " + w).strip()
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines or [""]

def ordinal(n: int) -> str:
    s = {1:"st",2:"nd",3:"rd"}
    return f"{n}{s.get(n%10,'th') if not 11<=n%100<=13 else 'th'}"

def fmt_date(dt) -> str:
    return f"{dt.strftime('%B')} {ordinal(dt.day)}, {dt.year}" if dt else ""

def safe_fname(s: str, suffix: str) -> str:
    return re.sub(r'[^a-zA-Z0-9]','_', s or "Entity") + suffix

# ─────────────────────────────────────────────
# PDF PRIMITIVES
# ─────────────────────────────────────────────

def _styles():
    s = getSampleStyleSheet()
    base = dict(fontName="Helvetica", fontSize=10, leading=14, spaceAfter=4)
    s.add(ParagraphStyle("Rob_Title",   fontName="Helvetica-Bold", fontSize=15,
                         leading=18, spaceAfter=6, textColor=colors.HexColor(BRAND_COL)))
    s.add(ParagraphStyle("Rob_Sub",     fontName="Helvetica", fontSize=9,
                         leading=12, spaceAfter=4, textColor=colors.gray))
    s.add(ParagraphStyle("Rob_Head",    fontName="Helvetica-Bold", fontSize=10,
                         leading=13, spaceAfter=3, textColor=colors.HexColor(BRAND_COL)))
    s.add(ParagraphStyle("Rob_Body",    **base))
    s.add(ParagraphStyle("Rob_Small",   fontName="Helvetica", fontSize=8,
                         leading=11, textColor=colors.gray))
    s.add(ParagraphStyle("Rob_Label",   fontName="Helvetica-Bold", fontSize=9,
                         leading=12, textColor=colors.HexColor("#444")))
    s.add(ParagraphStyle("Rob_Warn",    fontName="Helvetica-Oblique", fontSize=8.5,
                         leading=12, textColor=colors.HexColor("#7a5700"),
                         backColor=colors.HexColor("#fff8e1"), borderPadding=6))
    return s

def _header_block(c, title: str, subtitle: str, form_no: str):
    """Draw a branded page header using canvas (for simple canvas-based PDFs)."""
    W, _ = LETTER
    c.setFillColor(colors.HexColor(BRAND_COL))
    c.rect(0, 750, W, 60, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, 790, title)
    c.setFont("Helvetica", 9)
    c.drawString(40, 775, subtitle)
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(W - 40, 783, form_no)
    c.setFillColor(colors.HexColor(ACCENT))
    c.rect(0, 748, W, 3, fill=1, stroke=0)

def _footer(c, page_num: int):
    W, _ = LETTER
    c.setFont("Helvetica", 7.5)
    c.setFillColor(colors.gray)
    c.drawString(40, 28, f"Prepared by ParalegalRob  |  Not legal advice  |  Page {page_num}")
    c.drawRightString(W - 40, 28, f"Generated {datetime.date.today().strftime('%B %d, %Y')}")

def _field_row(c, y: int, label: str, value: str, label_x=40, value_x=220, row_h=20):
    """Draw a label:value pair on a canvas page."""
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.HexColor("#333"))
    c.drawString(label_x, y, label)
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.black)
    for i, line in enumerate(_wrap(value, 62)):
        c.drawString(value_x, y - (i * 11), line)
    return y - max(row_h, 11 * len(_wrap(value, 62)))

def _divider(c, y, W=LETTER[0]):
    c.setStrokeColor(colors.HexColor("#cccccc"))
    c.setLineWidth(0.5)
    c.line(40, y, W - 40, y)
    return y - 10

# ─────────────────────────────────────────────
# MODULE 1 — FORMATION
# ─────────────────────────────────────────────

def pdf_form205(d: dict) -> BytesIO:
    from reportlab.pdfgen import canvas as cv_mod
    buf = BytesIO()
    c = cv_mod.Canvas(buf, pagesize=LETTER)
    W, H = LETTER
    _header_block(c, "Certificate of Formation — Texas LLC",
                  "Texas Business Organizations Code § 3.005  |  Form 205", "FORM 205")

    y = 730
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor(BRAND_COL))
    c.drawString(40, y, "ARTICLE I — ENTITY INFORMATION"); y -= 18
    y = _field_row(c, y, "1. Entity Name:", d.get("name",""))
    y = _field_row(c, y, "2. Entity Type:", "Texas Limited Liability Company")
    y = _field_row(c, y, "3. Management:", d.get("mgmt","Member-Managed"))
    y = _field_row(c, y, "4. Purpose:", d.get("purpose","Any lawful purpose under the TBOC"))
    y = _field_row(c, y, "5. Effective Date:", d.get("eff_date", datetime.date.today().strftime("%B %d, %Y")))
    y = _divider(c, y - 6)

    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor(BRAND_COL))
    c.drawString(40, y, "ARTICLE II — REGISTERED AGENT & OFFICE"); y -= 18
    y = _field_row(c, y, "Agent Name:", d.get("agent_name",""))
    y = _field_row(c, y, "Agent Street:", d.get("agent_street",""))
    y = _field_row(c, y, "Agent City/State/ZIP:",
                   f"{d.get('agent_city','')}, {d.get('agent_state','TX')} {d.get('agent_zip','')}")
    y = _divider(c, y - 6)

    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor(BRAND_COL))
    c.drawString(40, y, "ARTICLE III — ORGANIZER"); y -= 18
    y = _field_row(c, y, "Organizer Name:", d.get("org_name",""))
    y = _field_row(c, y, "Organizer Address:", d.get("org_address",""))
    y = _divider(c, y - 6)

    # Signature block
    y -= 10
    c.setFont("Helvetica-Bold", 9); c.setFillColor(colors.HexColor("#333"))
    c.drawString(40, y, "SIGNATURE OF ORGANIZER"); y -= 20
    c.setFont("Helvetica", 9); c.setFillColor(colors.black)
    c.drawString(40, y, "Signature: _______________________________   Date: _______________"); y -= 16
    c.drawString(40, y, f"Printed Name: {d.get('org_name','')}"); y -= 30

    # Filing instructions box
    c.setFillColor(colors.HexColor("#e8f0fe"))
    c.rect(40, y - 50, W - 80, 60, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 9); c.setFillColor(colors.HexColor(BRAND_COL))
    c.drawString(50, y + 4, "FILING INSTRUCTIONS — PRINT TWO COPIES — STATE KEEPS ONE")
    c.setFont("Helvetica", 8.5); c.setFillColor(colors.HexColor("#333"))
    c.drawString(50, y - 10, "Mail to: Secretary of State, P.O. Box 13697, Austin, TX 78711-3697")
    c.drawString(50, y - 22, "Filing Fee: $300.00 (check payable to 'Secretary of State')")
    c.drawString(50, y - 34, "Processing: 7–10 business days  |  Expedited same-day via SOSDirect + $50/doc fee")

    _footer(c, 1)
    c.save(); buf.seek(0)
    return buf

def pdf_operating_agreement(d: dict) -> BytesIO:
    """Full TBOC-compliant Operating Agreement using Platypus (multi-page)."""
    buf = BytesIO()
    styles = _styles()

    members = d.get("members", [])
    mgmt    = d.get("mgmt", "Member-Managed")
    name    = d.get("name", "the Company")
    today   = fmt_date(datetime.date.today())

    story = []

    # Cover
    story.append(Spacer(1, 0.4*inch))
    story.append(Paragraph(f"COMPANY AGREEMENT", styles["Rob_Title"]))
    story.append(Paragraph(f"of", styles["Rob_Sub"]))
    story.append(Paragraph(f"{name}", styles["Rob_Title"]))
    story.append(Paragraph(f"A Texas Limited Liability Company", styles["Rob_Sub"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor(ACCENT)))
    story.append(Spacer(1, 0.15*inch))
    story.append(Paragraph(
        f"Effective {d.get('eff_date', today)}, the member(s) of {name} adopt this Company Agreement "
        f"pursuant to the Texas Business Organizations Code (TBOC), Chapter 101.", styles["Rob_Body"]))
    story.append(Spacer(1, 0.2*inch))

    # Membership table
    story.append(Paragraph("ARTICLE I — MEMBERSHIP & OWNERSHIP", styles["Rob_Head"]))
    tdata = [["Member Name", "Ownership %", "Capital Contribution"]]
    for m in members:
        tdata.append([m.get("name",""), f"{m.get('pct',0):.1f}%", m.get("capital","$0")])
    tdata.append(["TOTAL", f"{sum(float(m.get('pct',0)) for m in members):.1f}%", ""])
    t = Table(tdata, colWidths=[2.8*inch, 1.2*inch, 2*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,0), colors.HexColor(BRAND_COL)),
        ("TEXTCOLOR",   (0,0), (-1,0), colors.white),
        ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",    (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS", (0,1), (-1,-2), [colors.white, colors.HexColor("#f5f7fa")]),
        ("BACKGROUND",  (0,-1), (-1,-1), colors.HexColor("#e8f0fe")),
        ("FONTNAME",    (0,-1), (-1,-1), "Helvetica-Bold"),
        ("GRID",        (0,0), (-1,-1), 0.5, colors.HexColor("#cccccc")),
        ("TOPPADDING",  (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0), (-1,-1), 5),
    ]))
    story.append(t); story.append(Spacer(1, 0.15*inch))

    # Management
    story.append(Paragraph("ARTICLE II — MANAGEMENT", styles["Rob_Head"]))
    if mgmt == "Member-Managed":
        story.append(Paragraph(
            "The Company shall be managed by its member(s). Each member shall have authority to act "
            "on behalf of and bind the Company in the ordinary course of business, proportionate to "
            "their ownership interest.", styles["Rob_Body"]))
    else:
        story.append(Paragraph(
            f"The Company shall be managed by a designated Manager: "
            f"<b>{d.get('manager_name','[Manager Name]')}</b>. The Manager is authorized to act on behalf "
            f"of the Company without further approval of the members except as required by the TBOC.",
            styles["Rob_Body"]))
    story.append(Spacer(1, 0.1*inch))

    # Standard articles
    articles = [
        ("ARTICLE III — PURPOSE", f"The purpose of the Company is: {d.get('purpose','any lawful business permitted under Texas law')}."),
        ("ARTICLE IV — PRINCIPAL OFFICE", f"The principal place of business is: {d.get('address','[Address]')}."),
        ("ARTICLE V — REGISTERED AGENT",
         f"The registered agent is {d.get('agent_name','[Agent Name]')}, located at "
         f"{d.get('agent_street','')}, {d.get('agent_city','')}, {d.get('agent_state','TX')} "
         f"{d.get('agent_zip','')}."),
        ("ARTICLE VI — FISCAL YEAR", f"The Company's fiscal year ends on {d.get('fiscal_year','December 31')}."),
        ("ARTICLE VII — CAPITAL ACCOUNTS",
         "A separate capital account shall be maintained for each member reflecting contributions, "
         "allocations of profits and losses, and distributions per TBOC § 101.203."),
        ("ARTICLE VIII — DISTRIBUTIONS",
         "Distributions shall be made at the discretion of the managing authority and in proportion "
         "to each member's ownership interest per TBOC § 101.205."),
        ("ARTICLE IX — TRANSFERS",
         "No member may transfer, assign, pledge, or encumber their membership interest without "
         "the prior written consent of all other members, unless otherwise agreed."),
        ("ARTICLE X — DISSOLUTION",
         "The Company shall dissolve upon: (a) unanimous written consent of all members; "
         "(b) entry of a judicial decree; or (c) any event under TBOC § 101.552."),
        ("ARTICLE XI — INDEMNIFICATION",
         "The Company shall indemnify each member and officer to the fullest extent permitted "
         "under the TBOC and the Company's governing documents."),
        ("ARTICLE XII — GOVERNING LAW",
         "This Agreement is governed by the laws of the State of Texas and the Texas Business "
         "Organizations Code. Any dispute shall be resolved in the county where the Company's "
         "registered office is located."),
        ("ARTICLE XIII — AMENDMENTS",
         "This Agreement may be amended only by written consent of members holding a majority "
         "of the ownership interests, unless unanimity is required by this Agreement or the TBOC."),
    ]
    for title, text in articles:
        story.append(Paragraph(title, styles["Rob_Head"]))
        story.append(Paragraph(text, styles["Rob_Body"]))
        story.append(Spacer(1, 0.08*inch))

    story.append(PageBreak())

    # Signature page
    story.append(Paragraph("SIGNATURE PAGE", styles["Rob_Title"]))
    story.append(Paragraph(
        f"IN WITNESS WHEREOF, the undersigned member(s) of {name} have executed this "
        f"Company Agreement as of {d.get('eff_date', today)}.", styles["Rob_Body"]))
    story.append(Spacer(1, 0.2*inch))
    for m in members:
        sig_data = [
            ["Member:", m.get("name","")],
            ["Ownership:", f"{m.get('pct',0):.1f}%"],
            ["Signature:", "________________________________"],
            ["Date:", "________________"],
        ]
        story.append(Table(sig_data, colWidths=[1.2*inch, 4*inch]))
        story.append(Spacer(1, 0.3*inch))

    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#aaa")))
    story.append(Paragraph(
        f"IMPORTANT: This document is an internal governance record. DO NOT file with the "
        f"Texas Secretary of State. Prepared by ParalegalRob  |  Not legal advice.",
        styles["Rob_Small"]))

    doc = SimpleDocTemplate(buf, pagesize=LETTER,
                            leftMargin=0.75*inch, rightMargin=0.75*inch,
                            topMargin=0.75*inch, bottomMargin=0.75*inch)
    doc.build(story)
    buf.seek(0)
    return buf

# ─────────────────────────────────────────────
# MODULE 2 — REINSTATEMENT
# ─────────────────────────────────────────────

def pdf_form801(d: dict) -> BytesIO:
    """Form 801 — Application for Reinstatement (Tax Forfeiture)."""
    buf = BytesIO()
    from reportlab.pdfgen import canvas as cv_mod
    c = cv_mod.Canvas(buf, pagesize=LETTER)
    W, H = LETTER
    _header_block(c, "Application for Reinstatement — Tax Forfeiture",
                  "Texas SOS Form 801  |  TBOC § 171.313  |  Filing Fee: $75.00", "FORM 801")
    y = 720
    c.setFont("Helvetica-Bold", 9.5); c.setFillColor(colors.HexColor(BRAND_COL))
    c.drawString(40, y, "ENTITY INFORMATION"); y -= 18

    y = _field_row(c, y, "1. Entity Legal Name:", d.get("name",""))
    y = _field_row(c, y, "2. SOS File Number:", d.get("sos_file","(see SOS records)"))
    y = _field_row(c, y, "3. Date of Forfeiture:", d.get("forfeit_date",""))
    y = _field_row(c, y, "4. Entity Type:", d.get("entity_type","Texas LLC"))
    y = _divider(c, y - 8)

    c.setFont("Helvetica-Bold", 9.5); c.setFillColor(colors.HexColor(BRAND_COL))
    c.drawString(40, y, "REGISTERED AGENT (CURRENT)"); y -= 18
    y = _field_row(c, y, "Agent Name:", d.get("agent_name",""))
    y = _field_row(c, y, "Agent Street:", d.get("agent_street",""))
    y = _field_row(c, y, "City/State/ZIP:",
                   f"{d.get('agent_city','')}, {d.get('agent_state','TX')} {d.get('agent_zip','')}")
    y = _divider(c, y - 8)

    c.setFont("Helvetica-Bold", 9.5); c.setFillColor(colors.HexColor(BRAND_COL))
    c.drawString(40, y, "CERTIFICATION"); y -= 18
    c.setFont("Helvetica", 9); c.setFillColor(colors.black)
    c.drawString(40, y,
        "The undersigned certifies that all franchise taxes, penalties, and interest have been")
    y -= 13
    c.drawString(40, y, "paid or arrangements made, and a Tax Clearance Letter has been obtained.")
    y -= 28
    c.drawString(40, y, "Signature: ____________________________   Date: _______________"); y -= 16
    c.drawString(40, y, f"Authorized Person: {d.get('signatory','')}"); y -= 35

    c.setFillColor(colors.HexColor("#fff3cd"))
    c.rect(40, y - 60, W - 80, 70, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 8.5); c.setFillColor(colors.HexColor("#7a5700"))
    c.drawString(50, y - 2, "REQUIRED ENCLOSURES — Submit in duplicate")
    c.setFont("Helvetica", 8.5)
    c.drawString(50, y - 16, "1. This completed Form 801 (2 copies)")
    c.drawString(50, y - 28, "2. Tax Clearance Letter from Texas Comptroller of Public Accounts")
    c.drawString(50, y - 40, "3. Check for $75.00 payable to 'Secretary of State'")
    c.drawString(50, y - 52, "Mail to: SOS, P.O. Box 13697, Austin, TX 78711-3697")

    _footer(c, 1); c.save(); buf.seek(0)
    return buf

def pdf_form811(d: dict) -> BytesIO:
    """Form 811 — Certificate of Reinstatement (Voluntary/Involuntary/Foreign)."""
    buf = BytesIO()
    from reportlab.pdfgen import canvas as cv_mod
    c = cv_mod.Canvas(buf, pagesize=LETTER)
    W, H = LETTER
    _header_block(c, "Certificate of Reinstatement",
                  "Texas SOS Form 811  |  TBOC § 11.201–11.206  |  Filing Fee: $15–$75", "FORM 811")
    y = 718
    c.setFont("Helvetica-Bold", 9.5); c.setFillColor(colors.HexColor(BRAND_COL))
    c.drawString(40, y, "ITEM 1 — ENTITY NAME & FILE NUMBER"); y -= 18
    y = _field_row(c, y, "Legal Name:", d.get("name",""))
    y = _field_row(c, y, "SOS File Number:", d.get("sos_file",""))
    y = _field_row(c, y, "Assumed TX Name (if any):", d.get("assumed_name","N/A"))
    y = _divider(c, y - 6)

    c.setFont("Helvetica-Bold", 9.5); c.setFillColor(colors.HexColor(BRAND_COL))
    c.drawString(40, y, "ITEM 2 — JURISDICTIONAL INFORMATION"); y -= 18
    y = _field_row(c, y, "Jurisdiction of Organization:", d.get("jurisdiction","Texas"))
    y = _field_row(c, y, "Date of Organization:", d.get("org_date",""))
    y = _divider(c, y - 6)

    c.setFont("Helvetica-Bold", 9.5); c.setFillColor(colors.HexColor(BRAND_COL))
    c.drawString(40, y, "ITEM 3 — DATE OF TERMINATION/REVOCATION"); y -= 18
    y = _field_row(c, y, "Termination/Revocation Date:", d.get("term_date",""))
    y = _divider(c, y - 6)

    c.setFont("Helvetica-Bold", 9.5); c.setFillColor(colors.HexColor(BRAND_COL))
    c.drawString(40, y, "ITEM 4 — CONDITIONS FOR REINSTATEMENT"); y -= 18
    c.setFont("Helvetica", 9); c.setFillColor(colors.black)
    reinstate_type = d.get("reinstate_type","4A")
    box_4a = "[X]" if reinstate_type == "4A" else "[ ]"
    box_4b = "[X]" if reinstate_type == "4B" else "[ ]"
    box_4c = "[X]" if reinstate_type == "4C" else "[ ]"
    c.drawString(40, y, f"{box_4a} 4A. Voluntary Termination — TBOC § 11.202 (3-yr limit)"); y -= 14
    c.drawString(40, y, f"{box_4b} 4B. Involuntary Termination by SOS — TBOC subchapter F, Ch.11"); y -= 14
    c.drawString(40, y, f"{box_4c} 4C. Revocation of Foreign Registration — TBOC subchapter C, Ch.9"); y -= 20
    y = _divider(c, y - 4)

    c.setFont("Helvetica-Bold", 9.5); c.setFillColor(colors.HexColor(BRAND_COL))
    c.drawString(40, y, "ITEM 5 — REGISTERED AGENT"); y -= 18
    y = _field_row(c, y, "Agent Name:", d.get("agent_name",""))
    y = _field_row(c, y, "Agent Street:", d.get("agent_street",""))
    y = _field_row(c, y, "City/State/ZIP:",
                   f"{d.get('agent_city','')}, {d.get('agent_state','TX')} {d.get('agent_zip','')}")
    y = _divider(c, y - 6)

    y -= 4
    c.setFont("Helvetica", 9); c.setFillColor(colors.black)
    c.drawString(40, y, "Signature: ____________________________   Date: _______________"); y -= 16
    c.drawString(40, y, f"Authorized Person: {d.get('signatory','')}"); y -= 35

    fees = {"4A":"$15.00","4B":"$75.00","4C":"$75.00"}
    c.setFillColor(colors.HexColor("#fff3cd"))
    c.rect(40, y - 55, W - 80, 65, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 8.5); c.setFillColor(colors.HexColor("#7a5700"))
    c.drawString(50, y - 2, f"FILING — Submit in duplicate  |  Fee: {fees.get(reinstate_type,'$75')}")
    c.setFont("Helvetica", 8.5)
    c.drawString(50, y - 16, "1. Form 811 (2 copies)  2. Tax Clearance Letter (unless nonprofit)")
    c.drawString(50, y - 28, f"3. Check payable to 'Secretary of State' for {fees.get(reinstate_type,'$75')}")
    c.drawString(50, y - 40, "Mail to: SOS, P.O. Box 13697, Austin, TX 78711-3697")
    c.drawString(50, y - 52, "Fax (if applicable): (512) 463-5709  |  Online: SOSDirect")

    _footer(c, 1); c.save(); buf.seek(0)
    return buf

# ─────────────────────────────────────────────
# MODULE 3 — DISSOLUTION / TERMINATION
# ─────────────────────────────────────────────

def pdf_form651(d: dict) -> BytesIO:
    """Form 651 — Certificate of Termination of a Domestic Entity."""
    buf = BytesIO()
    from reportlab.pdfgen import canvas as cv_mod
    c = cv_mod.Canvas(buf, pagesize=LETTER)
    W, H = LETTER
    _header_block(c, "Certificate of Termination — Texas LLC",
                  "Texas SOS Form 651  |  TBOC § 11.101  |  Filing Fee: $40.00", "FORM 651")
    y = 718

    c.setFont("Helvetica-Bold", 9.5); c.setFillColor(colors.HexColor(BRAND_COL))
    c.drawString(40, y, "ITEMS 1–4 — ENTITY INFORMATION"); y -= 18
    y = _field_row(c, y, "1. Entity Name:", d.get("name",""))
    y = _field_row(c, y, "2. Entity Type:", d.get("entity_type","Texas Limited Liability Company"))
    y = _field_row(c, y, "3. Date of Formation:", d.get("formation_date",""))
    y = _field_row(c, y, "4. SOS File Number:", d.get("sos_file",""))
    y = _divider(c, y - 6)

    c.setFont("Helvetica-Bold", 9.5); c.setFillColor(colors.HexColor(BRAND_COL))
    c.drawString(40, y, "ITEM 5 — GOVERNING PERSONS"); y -= 18
    for i, gp in enumerate(d.get("governing_persons",[]), 1):
        y = _field_row(c, y, f"Person {i} Name:", gp.get("name",""))
        y = _field_row(c, y, f"Person {i} Address:", gp.get("address",""))
        y -= 6
    if not d.get("governing_persons"):
        y = _field_row(c, y, "Governing Person:", "(see client records)")
    y = _divider(c, y - 6)

    c.setFont("Helvetica-Bold", 9.5); c.setFillColor(colors.HexColor(BRAND_COL))
    c.drawString(40, y, "ITEM 6 — EVENT REQUIRING WINDING UP"); y -= 18
    c.setFont("Helvetica", 9); c.setFillColor(colors.black)
    wind_event = d.get("wind_event","A")
    opts = {
        "A": "Voluntary decision to wind up approved by the governing authority",
        "B": "Expiration of the entity's period of duration in the certificate of formation",
        "C": "Occurrence of an event specified in the governing documents requiring winding up",
        "D": "Occurrence of an event specified by the TBOC requiring winding up",
        "E": "Court decree requiring winding up under the TBOC or other law",
    }
    for k, v in opts.items():
        box = "[X]" if k == wind_event else "[ ]"
        c.drawString(40, y, f"{box} {k}. {v}"); y -= 13
    y = _divider(c, y - 6)

    c.setFont("Helvetica-Bold", 9.5); c.setFillColor(colors.HexColor(BRAND_COL))
    c.drawString(40, y, "ITEM 7 — COMPLETION OF WINDING UP"); y -= 16
    c.setFont("Helvetica", 9); c.setFillColor(colors.black)
    c.drawString(40, y,
        "[X] The entity has complied with all TBOC provisions governing winding up."); y -= 22
    y = _divider(c, y - 6)

    c.setFont("Helvetica-Bold", 9.5); c.setFillColor(colors.HexColor(BRAND_COL))
    c.drawString(40, y, "EFFECTIVENESS OF FILING"); y -= 16
    c.setFont("Helvetica", 9); c.setFillColor(colors.black)
    eff = d.get("effectiveness","A")
    c.drawString(40, y, f"{'[X]' if eff=='A' else '[ ]'} A. Effective on filing by SOS"); y -= 13
    c.drawString(40, y, f"{'[X]' if eff=='B' else '[ ]'} B. Delayed effective date: {d.get('delay_date','')}"); y -= 22
    y = _divider(c, y - 4)

    y -= 4
    c.setFont("Helvetica", 9); c.setFillColor(colors.black)
    c.drawString(40, y, "Signature: ____________________________   Date: _______________"); y -= 16
    c.drawString(40, y, f"Authorized Manager/Member: {d.get('signatory','')}"); y -= 35

    c.setFillColor(colors.HexColor("#e8f5e9"))
    c.rect(40, y - 44, W - 80, 52, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 8.5); c.setFillColor(colors.HexColor("#1b5e20"))
    c.drawString(50, y - 2, "FILING — Submit in duplicate  |  Filing Fee: $40.00")
    c.setFont("Helvetica", 8.5); c.setFillColor(colors.HexColor("#333"))
    c.drawString(50, y - 14, "Mail to: Secretary of State, P.O. Box 13697, Austin, TX 78711-3697")
    c.drawString(50, y - 26, "Check payable to 'Secretary of State' — $40.00")
    c.drawString(50, y - 38, "Obtain Tax Clearance Letter from TX Comptroller BEFORE filing")

    _footer(c, 1); c.save(); buf.seek(0)
    return buf

# ─────────────────────────────────────────────
# MODULE 4 — FOREIGN REGISTRATION
# ─────────────────────────────────────────────

def pdf_form304(d: dict) -> BytesIO:
    """Form 304 — Application for Registration of a Foreign LLC."""
    buf = BytesIO()
    from reportlab.pdfgen import canvas as cv_mod
    c = cv_mod.Canvas(buf, pagesize=LETTER)
    W, H = LETTER
    _header_block(c, "Application for Registration — Foreign LLC",
                  "Texas SOS Form 304  |  TBOC § 9.001  |  Filing Fee: $750.00", "FORM 304")
    y = 718

    c.setFont("Helvetica-Bold", 9.5); c.setFillColor(colors.HexColor(BRAND_COL))
    c.drawString(40, y, "ENTITY INFORMATION"); y -= 18
    y = _field_row(c, y, "1. LLC Legal Name (home state):", d.get("name",""))
    y = _field_row(c, y, "2. Assumed Name in TX (if conflict):", d.get("assumed_name","N/A"))
    y = _field_row(c, y, "3. State of Formation:", d.get("home_state",""))
    y = _field_row(c, y, "4. Date of Formation:", d.get("formation_date",""))
    y = _field_row(c, y, "5. EIN / FEIN:", d.get("fein","(not yet obtained)"))
    y = _field_row(c, y, "6. Purpose in Texas:", d.get("purpose","Any lawful business under Texas law"))
    y = _field_row(c, y, "7. Texas Business Start Date:", d.get("tx_start_date",""))
    y = _divider(c, y - 6)

    c.setFont("Helvetica-Bold", 9.5); c.setFillColor(colors.HexColor(BRAND_COL))
    c.drawString(40, y, "TEXAS REGISTERED AGENT"); y -= 18
    y = _field_row(c, y, "Agent Name:", d.get("agent_name",""))
    y = _field_row(c, y, "Agent Street Address:", d.get("agent_street",""))
    y = _field_row(c, y, "City / State / ZIP:",
                   f"{d.get('agent_city','')}, TX {d.get('agent_zip','')}")
    y = _divider(c, y - 6)

    c.setFont("Helvetica-Bold", 9.5); c.setFillColor(colors.HexColor(BRAND_COL))
    c.drawString(40, y, "GOVERNING PERSONS / MANAGERS"); y -= 18
    for i, gp in enumerate(d.get("governing_persons",[]), 1):
        y = _field_row(c, y, f"{i}. Name:", gp.get("name",""))
        y = _field_row(c, y, f"   Address:", gp.get("address",""))
        y -= 4
    y = _divider(c, y - 6)

    y -= 4
    c.setFont("Helvetica", 9); c.setFillColor(colors.black)
    c.drawString(40, y, "Signature: ____________________________   Date: _______________"); y -= 16
    c.drawString(40, y, f"Authorized Person: {d.get('signatory','')}"); y -= 35

    c.setFillColor(colors.HexColor("#fce4ec"))
    c.rect(40, y - 58, W - 80, 68, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 8.5); c.setFillColor(colors.HexColor("#880e4f"))
    c.drawString(50, y - 2, "FILING — Submit 2 copies  |  Filing Fee: $750.00  |  +$25 expedite")
    c.setFont("Helvetica", 8.5); c.setFillColor(colors.HexColor("#333"))
    c.drawString(50, y - 14, "Online via SOSDirect (2.7% CC surcharge, ~2 business days)")
    c.drawString(50, y - 26, "Mail to: SOS, P.O. Box 13697, Austin, TX 78711-3697")
    c.drawString(50, y - 38, "Attach: Certificate of Fact/Good Standing from home state (< 90 days)")
    c.drawString(50, y - 50, "NOTE: Register within 90 days of beginning TX business to avoid late fees")

    _footer(c, 1); c.save(); buf.seek(0)
    return buf

# ─────────────────────────────────────────────
# SIDEBAR — MODULE SELECTOR
# ─────────────────────────────────────────────

with st.sidebar:
    st.markdown(f"### ⚖️ {APP_NAME}")
    st.caption("Internal paralegal back-office tool — not for client distribution")
    st.divider()
    module = st.radio("Select Service Module", [
        "1 — Formation",
        "2 — Reinstatement",
        "3 — Dissolution / Termination",
        "4 — Foreign LLC Registration",
    ])
    st.divider()
    st.markdown("**Client intake tip:** Collect info via email intake form, then enter here to generate docs.")
    st.caption(f"© {YEAR} ParalegalRob")

# ─────────────────────────────────────────────
# MODULE 1 — FORMATION UI
# ─────────────────────────────────────────────

if module.startswith("1"):
    st.markdown('<p class="module-title">Texas LLC Formation</p>', unsafe_allow_html=True)
    st.markdown('<p class="module-sub">Generates: Form 205 (Certificate of Formation) + Company Operating Agreement + Mailing Checklist</p>', unsafe_allow_html=True)

    st.markdown('<p class="section-head">Entity Details</p>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        name    = st.text_input("LLC Name*", placeholder="Pearland Tech, LLC")
        mgmt    = st.radio("Management Structure", ["Member-Managed","Manager-Managed"])
        manager_name = ""
        if mgmt == "Manager-Managed":
            manager_name = st.text_input("Manager Name*")
    with c2:
        purpose = st.text_input("Business Purpose", "Any lawful purpose under the TBOC")
        fiscal  = st.selectbox("Fiscal Year End", ["December 31","March 31","June 30","September 30"])
        eff_dt  = st.date_input("Effective Date", datetime.date.today())
        address = st.text_input("Principal Business Address*")

    st.markdown('<p class="section-head">Registered Agent</p>', unsafe_allow_html=True)
    c3, c4, c5, c6 = st.columns([3, 2, 1, 1])
    with c3: ra_name   = st.text_input("Agent Name*")
    with c4: ra_street = st.text_input("Street*")
    with c5: ra_city   = st.text_input("City*")
    with c6: ra_state  = st.selectbox("State", US_STATES, index=US_STATES.index("TX"))
    ra_zip = st.text_input("ZIP*", max_chars=10)

    st.markdown('<p class="section-head">Organizer</p>', unsafe_allow_html=True)
    c7, c8 = st.columns(2)
    with c7: org_name    = st.text_input("Organizer Name*", "Rob Jackson")
    with c8: org_address = st.text_input("Organizer Address*")

    st.markdown('<p class="section-head">Members & Ownership</p>', unsafe_allow_html=True)
    if "f1_members" not in st.session_state:
        st.session_state.f1_members = [{"name":"","pct":100.0,"capital":"$0"}]

    for i, m in enumerate(st.session_state.f1_members):
        mc1, mc2, mc3, mc4 = st.columns([4, 2, 2, 1])
        with mc1:
            st.session_state.f1_members[i]["name"] = st.text_input(
                f"Member {i+1} Name", value=m["name"], key=f"f1mn_{i}")
        with mc2:
            st.session_state.f1_members[i]["pct"] = st.number_input(
                "Ownership %", min_value=0.0, max_value=100.0,
                value=float(m["pct"]), step=0.5, key=f"f1mp_{i}")
        with mc3:
            st.session_state.f1_members[i]["capital"] = st.text_input(
                "Capital Contribution", value=m["capital"], key=f"f1mc_{i}")
        with mc4:
            st.markdown("<br>", unsafe_allow_html=True)
            if len(st.session_state.f1_members) > 1:
                if st.button("🗑️", key=f"f1del_{i}"):
                    st.session_state.f1_members.pop(i); st.rerun()

    total_pct = sum(m["pct"] for m in st.session_state.f1_members)
    if abs(total_pct - 100.0) < 0.01:
        st.success(f"✅ Total ownership: {total_pct:.1f}%")
    else:
        st.warning(f"⚠️ Total: {total_pct:.1f}% — must equal 100%")

    if st.button("➕ Add Member"):
        st.session_state.f1_members.append({"name":"","pct":max(0.0, round(100-total_pct,2)),"capital":"$0"})
        st.rerun()

    st.divider()
    ready = name and ra_name and ra_street and ra_city and ra_zip and org_name
    if st.button("⚙️ Generate Formation Documents", type="primary", disabled=not ready):
        payload = {
            "name": name, "mgmt": mgmt, "manager_name": manager_name,
            "purpose": purpose, "fiscal_year": fiscal,
            "eff_date": fmt_date(eff_dt), "address": address,
            "agent_name": ra_name, "agent_street": ra_street,
            "agent_city": ra_city, "agent_state": ra_state, "agent_zip": ra_zip,
            "org_name": org_name, "org_address": org_address,
            "members": st.session_state.f1_members,
        }
        st.markdown('<div class="doc-ready">✅ Documents ready — download below</div>', unsafe_allow_html=True)
        dc1, dc2 = st.columns(2)
        with dc1:
            st.download_button("📥 Form 205 (Certificate of Formation)",
                               pdf_form205(payload), safe_fname(name,"_Form205.pdf"),
                               mime="application/pdf", use_container_width=True)
        with dc2:
            st.download_button("📥 Company Operating Agreement",
                               pdf_operating_agreement(payload), safe_fname(name,"_OperatingAgreement.pdf"),
                               mime="application/pdf", use_container_width=True)

        st.markdown(f"""
<div class="checklist-box">
<b>📋 Client Delivery Checklist</b><br><br>
<b>Documents to deliver to client:</b><br>
• Form 205 — print 2 copies, client signs both, mails both + $300 check<br>
• Company Agreement — 1 copy for client records (do NOT mail)<br><br>
<b>What client must do:</b><br>
• Mail Form 205 (×2) + $300 check to SOS, P.O. Box 13697, Austin TX 78711-3697<br>
• Or file online via SOSDirect (faster; credit card surcharge applies)<br>
• After filing: obtain EIN at IRS.gov (free) · Open business bank account<br>
• Set annual franchise tax reminder (due May 15 each year)<br><br>
<b>State fees (client pays direct):</b>
<span class="fee-tag">$300 SOS filing</span>
<span class="fee-tag">$0 EIN</span>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# MODULE 2 — REINSTATEMENT UI
# ─────────────────────────────────────────────

elif module.startswith("2"):
    st.markdown('<p class="module-title">Texas LLC Reinstatement</p>', unsafe_allow_html=True)
    st.markdown('<p class="module-sub">Generates: Form 801 (tax forfeiture) or Form 811 (other termination) + Checklist</p>', unsafe_allow_html=True)

    st.markdown('<div class="warn-box">⚠️ <b>Reinstatement type matters.</b> Tax forfeiture → Form 801. Voluntary/involuntary/foreign revocation → Form 811. Confirm the reason with client via SOS records before proceeding.</div>', unsafe_allow_html=True)

    r_type = st.radio("Reason for Termination",
        ["Tax Forfeiture (Form 801)", "Voluntary Termination (Form 811-A)",
         "Involuntary Termination by SOS (Form 811-B)",
         "Foreign Revocation (Form 811-C)"])

    st.markdown('<p class="section-head">Entity Information</p>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        r_name     = st.text_input("Entity Legal Name*")
        r_sos      = st.text_input("SOS File Number", help="From SOS records / SOSDirect lookup")
        r_entity_t = st.text_input("Entity Type", "Texas LLC")
    with c2:
        r_jx       = st.text_input("Jurisdiction", "Texas")
        r_orgdate  = st.text_input("Date of Organization (MM/DD/YYYY)")
        r_termdate = st.text_input("Date of Termination/Forfeiture (MM/DD/YYYY)")
        r_aname    = st.text_input("Assumed TX Name (if foreign entity)", "")

    st.markdown('<p class="section-head">Current Registered Agent</p>', unsafe_allow_html=True)
    rc1, rc2, rc3, rc4 = st.columns([3, 2, 1, 1])
    with rc1: r_aname2  = st.text_input("Agent Name*", key="r_agent")
    with rc2: r_astreet = st.text_input("Street*", key="r_street")
    with rc3: r_acity   = st.text_input("City*", key="r_city")
    with rc4: r_astate  = st.selectbox("State", US_STATES, index=US_STATES.index("TX"), key="r_state")
    r_azip = st.text_input("ZIP*", max_chars=10, key="r_zip")

    r_sig = st.text_input("Authorized Signatory (printed name)*")

    st.divider()
    r_ready = r_name and r_aname2 and r_sig
    if st.button("⚙️ Generate Reinstatement Document", type="primary", disabled=not r_ready):
        base = {
            "name": r_name, "sos_file": r_sos, "entity_type": r_entity_t,
            "jurisdiction": r_jx, "org_date": r_orgdate, "term_date": r_termdate,
            "assumed_name": r_aname,
            "agent_name": r_aname2, "agent_street": r_astreet,
            "agent_city": r_acity, "agent_state": r_astate, "agent_zip": r_azip,
            "signatory": r_sig,
        }
        st.markdown('<div class="doc-ready">✅ Document ready — download below</div>', unsafe_allow_html=True)

        if r_type.startswith("Tax Forfeiture"):
            st.download_button("📥 Form 801 — Application for Reinstatement",
                               pdf_form801(base), safe_fname(r_name,"_Form801.pdf"),
                               mime="application/pdf", use_container_width=True)
            fee, extra = "$75.00", "Tax Clearance Letter from TX Comptroller"
        else:
            rmap = {"Voluntary":"4A","Involuntary":"4B","Foreign":"4C"}
            base["reinstate_type"] = next((v for k,v in rmap.items() if k in r_type), "4A")
            st.download_button("📥 Form 811 — Certificate of Reinstatement",
                               pdf_form811(base), safe_fname(r_name,"_Form811.pdf"),
                               mime="application/pdf", use_container_width=True)
            fee = "$15.00" if "Voluntary" in r_type else "$75.00"
            extra = "Tax Clearance Letter from TX Comptroller"

        st.markdown(f"""
<div class="checklist-box">
<b>📋 Reinstatement Delivery Checklist</b><br><br>
<b>Client must provide before filing:</b><br>
• Tax Clearance Letter from Texas Comptroller of Public Accounts<br>
  (Request online at comptroller.texas.gov or mail Tax Clearance Letter Request form)<br>
• Any outstanding franchise tax payments + penalties + interest<br><br>
<b>Filing package (2 copies of form + enclosures):</b><br>
• Completed {extra}<br>
• Check for <b>{fee}</b> payable to 'Secretary of State'<br>
• Mail to: SOS, P.O. Box 13697, Austin, TX 78711-3697<br>
• Or file via SOSDirect (online) for faster processing<br><br>
<b>State fees (client pays direct):</b>
<span class="fee-tag">{fee} SOS filing</span>
<span class="fee-tag">Franchise tax arrears (varies)</span>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# MODULE 3 — DISSOLUTION UI
# ─────────────────────────────────────────────

elif module.startswith("3"):
    st.markdown('<p class="module-title">Texas LLC Dissolution / Termination</p>', unsafe_allow_html=True)
    st.markdown('<p class="module-sub">Generates: Form 651 (Certificate of Termination) + Winding-Up Checklist</p>', unsafe_allow_html=True)

    st.markdown('<div class="warn-box">⚠️ Confirm winding-up is complete before preparing Form 651 — all debts settled, assets distributed, and Tax Clearance Letter obtained from the TX Comptroller.</div>', unsafe_allow_html=True)

    st.markdown('<p class="section-head">Entity Information</p>', unsafe_allow_html=True)
    d1, d2 = st.columns(2)
    with d1:
        dis_name    = st.text_input("Entity Legal Name*")
        dis_sos     = st.text_input("SOS File Number")
        dis_entity  = st.text_input("Entity Type", "Texas Limited Liability Company")
    with d2:
        dis_formed  = st.text_input("Date of Formation (MM/DD/YYYY)")
        dis_event   = st.selectbox("Winding-Up Event (TBOC § 11.051)",
            ["A — Voluntary decision by governing authority",
             "B — Expiration of duration period",
             "C — Event in governing documents",
             "D — Event specified by TBOC",
             "E — Court decree"])
        dis_eff     = st.radio("Effectiveness of Filing",
            ["A — Effective on filing", "B — Delayed effective date"])
        dis_delay   = ""
        if dis_eff.startswith("B"):
            dis_delay = st.text_input("Delayed Effective Date (MM/DD/YYYY, ≤90 days)")

    st.markdown('<p class="section-head">Governing Persons (managers or managing members)</p>', unsafe_allow_html=True)
    if "f3_gp" not in st.session_state:
        st.session_state.f3_gp = [{"name":"","address":""}]
    for i, gp in enumerate(st.session_state.f3_gp):
        gc1, gc2, gc3 = st.columns([3, 4, 1])
        with gc1:
            st.session_state.f3_gp[i]["name"] = st.text_input(
                f"Person {i+1} Name", value=gp["name"], key=f"gpn_{i}")
        with gc2:
            st.session_state.f3_gp[i]["address"] = st.text_input(
                f"Address", value=gp["address"], key=f"gpa_{i}")
        with gc3:
            st.markdown("<br>", unsafe_allow_html=True)
            if len(st.session_state.f3_gp) > 1:
                if st.button("🗑️", key=f"gpdel_{i}"):
                    st.session_state.f3_gp.pop(i); st.rerun()
    if st.button("➕ Add Governing Person"):
        st.session_state.f3_gp.append({"name":"","address":""}); st.rerun()

    dis_sig = st.text_input("Authorized Signatory (manager or managing member)*")

    st.divider()
    dis_ready = dis_name and dis_sig
    if st.button("⚙️ Generate Dissolution Document", type="primary", disabled=not dis_ready):
        dpayload = {
            "name": dis_name, "sos_file": dis_sos, "entity_type": dis_entity,
            "formation_date": dis_formed,
            "wind_event": dis_event[0],
            "effectiveness": dis_eff[0],
            "delay_date": dis_delay,
            "governing_persons": st.session_state.f3_gp,
            "signatory": dis_sig,
        }
        st.markdown('<div class="doc-ready">✅ Document ready — download below</div>', unsafe_allow_html=True)
        st.download_button("📥 Form 651 — Certificate of Termination",
                           pdf_form651(dpayload), safe_fname(dis_name,"_Form651.pdf"),
                           mime="application/pdf", use_container_width=True)

        st.markdown(f"""
<div class="checklist-box">
<b>📋 Dissolution Delivery Checklist</b><br><br>
<b>Before filing — confirm all winding-up steps complete:</b><br>
• All business debts paid / creditors notified<br>
• All business assets distributed to members per ownership interests<br>
• All bank accounts closed, contracts terminated<br>
• Texas franchise tax paid through dissolution date<br>
• Tax Clearance Letter obtained from TX Comptroller<br><br>
<b>Filing package (submit in duplicate):</b><br>
• Form 651 (×2 copies) signed by authorized manager/member<br>
• Check for <b>$40.00</b> payable to 'Secretary of State'<br>
• Mail to: SOS, P.O. Box 13697, Austin, TX 78711-3697<br><br>
<b>After filing:</b><br>
• File final franchise tax return with TX Comptroller<br>
• Cancel EIN / notify IRS of entity dissolution<br>
• Cancel business licenses, permits, assumed name filings<br><br>
<b>State fees:</b>
<span class="fee-tag">$40 SOS filing</span>
<span class="fee-tag">Final franchise tax (varies)</span>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# MODULE 4 — FOREIGN REGISTRATION UI
# ─────────────────────────────────────────────

elif module.startswith("4"):
    st.markdown('<p class="module-title">Texas Foreign LLC Registration</p>', unsafe_allow_html=True)
    st.markdown('<p class="module-sub">Generates: Form 304 (Application for Registration) + Filing Checklist</p>', unsafe_allow_html=True)

    st.markdown('<div class="warn-box">⚠️ Filing fee is $750. Advise client to register within 90 days of beginning TX business to avoid late fees. Confirm LLC name is available in TX via SOSDirect ($1/search).</div>', unsafe_allow_html=True)

    st.markdown('<p class="section-head">Foreign LLC Information</p>', unsafe_allow_html=True)
    fg1, fg2 = st.columns(2)
    with fg1:
        fg_name     = st.text_input("LLC Legal Name (as registered in home state)*")
        fg_aname    = st.text_input("Assumed Name in TX (if home-state name unavailable)")
        fg_hstate   = st.selectbox("Home State of Formation", US_STATES, index=US_STATES.index("TX"))
        fg_formed   = st.text_input("Date of Formation in Home State (MM/DD/YYYY)")
    with fg2:
        fg_fein     = st.text_input("EIN / FEIN", placeholder="XX-XXXXXXX (or 'not yet obtained')")
        fg_purpose  = st.text_input("Purpose in Texas", "Any lawful business under Texas law")
        fg_txstart  = st.text_input("Date TX Business Began / Will Begin (MM/DD/YYYY)",
                                     help="Affects late-fee calculation — confirm with client carefully")

    st.markdown('<p class="section-head">Texas Registered Agent</p>', unsafe_allow_html=True)
    fc1, fc2, fc3 = st.columns([3, 2, 1])
    with fc1: fg_agname  = st.text_input("Agent Name*", key="fg_an")
    with fc2: fg_agst    = st.text_input("Street Address* (no P.O. Box)", key="fg_as")
    with fc3: fg_agcity  = st.text_input("City*", key="fg_ac")
    fg_agzip = st.text_input("ZIP*", max_chars=10, key="fg_az")

    st.markdown('<p class="section-head">Governing Persons / Managers</p>', unsafe_allow_html=True)
    if "f4_gp" not in st.session_state:
        st.session_state.f4_gp = [{"name":"","address":""}]
    for i, gp in enumerate(st.session_state.f4_gp):
        fgc1, fgc2, fgc3 = st.columns([3, 4, 1])
        with fgc1:
            st.session_state.f4_gp[i]["name"] = st.text_input(
                f"Person {i+1} Name", value=gp["name"], key=f"f4gpn_{i}")
        with fgc2:
            st.session_state.f4_gp[i]["address"] = st.text_input(
                f"Address", value=gp["address"], key=f"f4gpa_{i}")
        with fgc3:
            st.markdown("<br>", unsafe_allow_html=True)
            if len(st.session_state.f4_gp) > 1:
                if st.button("🗑️", key=f"f4del_{i}"):
                    st.session_state.f4_gp.pop(i); st.rerun()
    if st.button("➕ Add Person"):
        st.session_state.f4_gp.append({"name":"","address":""}); st.rerun()

    fg_sig = st.text_input("Authorized Signatory*")

    st.divider()
    fg_ready = fg_name and fg_agname and fg_agst and fg_agcity and fg_agzip and fg_sig
    if st.button("⚙️ Generate Foreign Registration Document", type="primary", disabled=not fg_ready):
        fgpayload = {
            "name": fg_name, "assumed_name": fg_aname or "N/A",
            "home_state": fg_hstate, "formation_date": fg_formed, "fein": fg_fein,
            "purpose": fg_purpose, "tx_start_date": fg_txstart,
            "agent_name": fg_agname, "agent_street": fg_agst,
            "agent_city": fg_agcity, "agent_state": "TX", "agent_zip": fg_agzip,
            "governing_persons": st.session_state.f4_gp,
            "signatory": fg_sig,
        }
        st.markdown('<div class="doc-ready">✅ Document ready — download below</div>', unsafe_allow_html=True)
        st.download_button("📥 Form 304 — Application for Foreign LLC Registration",
                           pdf_form304(fgpayload), safe_fname(fg_name,"_Form304.pdf"),
                           mime="application/pdf", use_container_width=True)

        st.markdown(f"""
<div class="checklist-box">
<b>📋 Foreign Registration Delivery Checklist</b><br><br>
<b>Required before/during filing:</b><br>
• Certificate of Good Standing / Fact from home state (must be < 90 days old)<br>
• Confirm LLC name availability in TX via SOSDirect ($1/search)<br>
• If name conflict: file Assumed Name Certificate (Form 503) simultaneously<br>
• FEIN — if not yet obtained, note on form; obtain at IRS.gov after filing<br><br>
<b>Filing options:</b><br>
• <b>Online (SOSDirect):</b> fastest (~2 business days), 2.7% CC surcharge → ~$770.25<br>
• <b>By mail (2 copies):</b> SOS, P.O. Box 13697, Austin, TX 78711-3697<br>
• Check payable to 'Secretary of State' — <b>$750.00</b><br>
• Fax no longer accepted as of September 15, 2025<br><br>
<b>After approval:</b><br>
• Client receives Certificate of Fact-Status (proof of TX registration)<br>
• Must maintain TX registered agent and file franchise tax returns annually<br><br>
<b>State fees:</b>
<span class="fee-tag">$750 SOS registration</span>
<span class="fee-tag">$1 name search</span>
<span class="fee-tag">+$25 expedite (optional)</span>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────

st.markdown(f"""
<div style="text-align:center; padding:40px 0 20px; font-size:0.72rem; color:#999;">
Texas LLC Paralegal Back-Office Tool &nbsp;·&nbsp; ParalegalRob &nbsp;·&nbsp;
Internal Use Only — Not Legal Advice &nbsp;·&nbsp; © {YEAR}
</div>
""", unsafe_allow_html=True)

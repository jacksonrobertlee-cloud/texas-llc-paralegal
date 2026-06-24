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
    """Full TBOC-compliant Operating Agreement — upgraded to match consumer generator article depth."""
    buf = BytesIO()
    styles = _styles()

    # Add supplemental styles needed for numbered sub-sections
    from reportlab.lib.enums import TA_JUSTIFY
    numbered_style = ParagraphStyle(
        "Rob_Numbered", parent=styles["Rob_Body"],
        leftIndent=18, alignment=TA_JUSTIFY, spaceAfter=6,
    )
    justify_style = ParagraphStyle(
        "Rob_Justify", parent=styles["Rob_Body"],
        alignment=TA_JUSTIFY, spaceAfter=6,
    )
    disclaimer_style = ParagraphStyle(
        "Rob_Disclaimer", fontName="Helvetica", fontSize=8, leading=11,
        spaceAfter=6, textColor=colors.HexColor("#555555"), alignment=TA_JUSTIFY,
    )

    members  = d.get("members", [])
    mgmt     = d.get("mgmt", "Member-Managed")
    name     = d.get("name", "the Company")
    today    = fmt_date(datetime.date.today())
    eff_date = d.get("eff_date", today)
    purpose  = d.get("purpose", "any lawful purpose permitted under the Texas Business Organizations Code")
    fiscal   = d.get("fiscal_year", "December 31")
    agent    = d.get("agent_name", "[Registered Agent]")
    agent_addr = (f"{d.get('agent_street','')}, {d.get('agent_city','')}, "
                  f"{d.get('agent_state','TX')} {d.get('agent_zip','')}").strip(", ")
    address  = d.get("address", "[Principal Office Address]")

    story = []

    # ── COVER PAGE ──
    story.append(Spacer(1, 0.4*inch))
    story.append(Paragraph("COMPANY AGREEMENT", styles["Rob_Title"]))
    story.append(Paragraph("OF", styles["Rob_Sub"]))
    story.append(Paragraph(name.upper(), styles["Rob_Title"]))
    story.append(Spacer(1, 0.05*inch))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor(ACCENT)))
    story.append(Spacer(1, 0.08*inch))
    story.append(Paragraph("A Texas Limited Liability Company", styles["Rob_Sub"]))
    story.append(Paragraph(f"Effective: {eff_date}", styles["Rob_Sub"]))
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph(
        "DISCLAIMER: This document was generated by ParalegalRob, an automated document preparation "
        "service, and does not constitute legal advice. It has not been reviewed by an attorney. "
        "You are encouraged to consult a licensed Texas attorney before executing this agreement. "
        "Use of this document is at your sole risk.",
        disclaimer_style
    ))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#aaaaaa")))
    story.append(PageBreak())

    # ── RECITALS ──
    story.append(Paragraph("RECITALS", styles["Rob_Head"]))
    story.append(Paragraph(
        f"This Company Agreement (this <b>\"Agreement\"</b>) of {name}, a Texas limited liability "
        f"company (the <b>\"Company\"</b>), is entered into and effective as of {eff_date}, "
        f"by and among the persons executing this Agreement as members (collectively, the "
        f"<b>\"Members\"</b> and each individually, a <b>\"Member\"</b>).",
        justify_style
    ))
    story.append(Paragraph(
        f"The Company was organized as a limited liability company under the Texas Business "
        f"Organizations Code (<b>\"TBOC\"</b>), Title 3, Chapter 101, et seq., as amended from "
        f"time to time. The Members desire to set forth their respective rights, duties, and "
        f"obligations with respect to the Company.",
        justify_style
    ))
    story.append(Spacer(1, 0.1*inch))

    # ── ARTICLE I — ORGANIZATION ──
    story.append(Paragraph("ARTICLE I — ORGANIZATION", styles["Rob_Head"]))

    story.append(Paragraph("<b>1.1 Name.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        f"The name of the limited liability company is {name}. The Company may conduct business "
        f"under any assumed name or trade name permitted by applicable law.",
        numbered_style
    ))

    story.append(Paragraph("<b>1.2 Principal Office.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        f"The principal office and place of business of the Company is located at {address}, "
        f"or at such other place as the Members may designate from time to time.",
        numbered_style
    ))

    story.append(Paragraph("<b>1.3 Registered Agent and Registered Office.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        f"The registered agent for service of process is {agent}, located at {agent_addr}. "
        f"The registered agent and registered office may be changed by filing the appropriate "
        f"form with the Texas Secretary of State.",
        numbered_style
    ))

    story.append(Paragraph("<b>1.4 Purpose.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        f"The purpose of the Company is to engage in {purpose}. The Company shall have all "
        f"powers necessary or convenient to carry out its purposes as provided by the TBOC.",
        numbered_style
    ))

    story.append(Paragraph("<b>1.5 Term.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        f"The Company shall continue in existence until dissolved in accordance with this "
        f"Agreement or the TBOC.",
        numbered_style
    ))

    story.append(Paragraph("<b>1.6 Governing Law.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        f"This Agreement and the rights and obligations of the parties hereunder shall be "
        f"governed by and construed in accordance with the laws of the State of Texas, without "
        f"regard to its conflicts of law principles. Any dispute shall be resolved in the county "
        f"where the Company's registered office is located.",
        numbered_style
    ))
    story.append(Spacer(1, 0.08*inch))

    # ── ARTICLE II — MEMBERS AND MEMBERSHIP INTERESTS ──
    story.append(Paragraph("ARTICLE II — MEMBERS AND MEMBERSHIP INTERESTS", styles["Rob_Head"]))

    story.append(Paragraph("<b>2.1 Initial Members.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "The initial Members of the Company, together with their respective Membership Interests "
        "and capital contributions, are set forth below:",
        numbered_style
    ))

    # Membership table — keeps capital contribution column from back-office tool
    tdata = [["Member Name", "Membership Interest (%)", "Capital Contribution"]]
    for m in members:
        tdata.append([m.get("name",""), f"{m.get('pct',0):.1f}%", m.get("capital","$0")])
    tdata.append(["TOTAL", f"{sum(float(m.get('pct',0)) for m in members):.1f}%", ""])
    t = Table(tdata, colWidths=[2.6*inch, 1.6*inch, 1.8*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND",     (0,0), (-1,0), colors.HexColor(BRAND_COL)),
        ("TEXTCOLOR",      (0,0), (-1,0), colors.white),
        ("FONTNAME",       (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",       (0,0), (-1,-1), 9),
        ("ALIGN",          (1,0), (2,-1), "CENTER"),
        ("ROWBACKGROUNDS", (0,1), (-1,-2), [colors.white, colors.HexColor("#f5f7fa")]),
        ("BACKGROUND",     (0,-1), (-1,-1), colors.HexColor("#e8f0fe")),
        ("FONTNAME",       (0,-1), (-1,-1), "Helvetica-Bold"),
        ("GRID",           (0,0), (-1,-1), 0.5, colors.HexColor("#cccccc")),
        ("TOPPADDING",     (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",  (0,0), (-1,-1), 5),
        ("LEFTPADDING",    (0,0), (-1,-1), 8),
    ]))
    story.append(Spacer(1, 4))
    story.append(t)
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>2.2 Nature of Membership Interest.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "A Member's Membership Interest shall be personal property for all purposes. A Member "
        "has no interest in specific property of the Company. A Member's Membership Interest "
        "entitles the Member to such Member's allocable share of profits, losses, and "
        "distributions, and such voting rights as are provided in this Agreement.",
        numbered_style
    ))

    story.append(Paragraph("<b>2.3 Liability of Members.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "No Member shall be personally liable for any debt, obligation, or liability of the "
        "Company, whether arising in contract, tort, or otherwise, solely by reason of being "
        "or acting as a Member of the Company, except as otherwise required by the TBOC or "
        "other applicable law.",
        numbered_style
    ))

    story.append(Paragraph("<b>2.4 Admission of Additional Members.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "Additional Members may be admitted to the Company only upon the unanimous written "
        "consent of all existing Members. Any new Member shall execute a counterpart signature "
        "page or joinder to this Agreement as a condition of admission.",
        numbered_style
    ))

    story.append(Paragraph("<b>2.5 No Resignation.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "No Member shall have the right to resign or withdraw from the Company prior to "
        "dissolution and winding up of the Company without the written consent of all remaining "
        "Members, except as otherwise provided in this Agreement.",
        numbered_style
    ))
    story.append(Spacer(1, 0.08*inch))

    # ── ARTICLE III — CAPITAL CONTRIBUTIONS ──
    story.append(Paragraph("ARTICLE III — CAPITAL CONTRIBUTIONS", styles["Rob_Head"]))

    story.append(Paragraph("<b>3.1 Initial Capital Contributions.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "Each Member's initial capital contribution is reflected in the table in Section 2.1. "
        "Such contributions are formally documented herein and in the Company's books and records "
        "as of the effective date of this Agreement.",
        numbered_style
    ))

    story.append(Paragraph("<b>3.2 Capital Accounts.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "A separate capital account shall be maintained for each Member per TBOC § 101.203. "
        "Each Member's capital account shall be (a) credited with such Member's capital "
        "contributions and allocable share of Company profits, and (b) debited with "
        "distributions to such Member and such Member's allocable share of Company losses.",
        numbered_style
    ))

    story.append(Paragraph("<b>3.3 No Interest on Capital.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "No Member shall be entitled to receive any interest on such Member's capital "
        "contribution unless otherwise unanimously agreed by the Members in writing.",
        numbered_style
    ))

    story.append(Paragraph("<b>3.4 Additional Contributions.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "No Member shall be required to make any additional capital contribution to the Company "
        "without such Member's prior written consent. The Members may unanimously agree to "
        "require additional contributions from all Members in proportion to their respective "
        "Membership Interests.",
        numbered_style
    ))

    story.append(Paragraph("<b>3.5 Return of Capital.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "No Member shall have the right to demand or receive the return of such Member's capital "
        "contribution except upon dissolution of the Company or as otherwise provided herein.",
        numbered_style
    ))
    story.append(Spacer(1, 0.08*inch))

    # ── ARTICLE IV — PROFITS, LOSSES, AND DISTRIBUTIONS ──
    story.append(Paragraph("ARTICLE IV — PROFITS, LOSSES, AND DISTRIBUTIONS", styles["Rob_Head"]))

    story.append(Paragraph("<b>4.1 Allocation of Profits and Losses.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "Except as otherwise provided in this Agreement, the net profits and net losses of the "
        "Company for each fiscal year shall be allocated among the Members in proportion to "
        "their respective Membership Interests.",
        numbered_style
    ))

    story.append(Paragraph("<b>4.2 Distributions.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "Distributions of Company cash or other assets shall be made to the Members at such "
        "times and in such amounts as determined by the Members in accordance with Article V "
        "of this Agreement, pro rata in accordance with each Member's Membership Interest per "
        "TBOC § 101.205, subject to any restrictions imposed by applicable law or any loan "
        "agreement to which the Company is a party.",
        numbered_style
    ))

    story.append(Paragraph("<b>4.3 Limitation on Distributions.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "No distribution shall be made if, after giving effect to the distribution, the Company "
        "would not be able to pay its debts as they become due in the ordinary course of "
        "business, or the Company's total assets would be less than the sum of its total "
        "liabilities, as required by TBOC § 101.206.",
        numbered_style
    ))

    story.append(Paragraph("<b>4.4 Tax Distributions.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "The Members may, but shall not be required to, cause the Company to make tax "
        "distributions to each Member in an amount sufficient to enable each Member to satisfy "
        "such Member's estimated income tax obligations attributable to such Member's allocable "
        "share of Company taxable income.",
        numbered_style
    ))
    story.append(Spacer(1, 0.08*inch))

    # ── ARTICLE V — MANAGEMENT ──
    story.append(Paragraph("ARTICLE V — MANAGEMENT", styles["Rob_Head"]))

    if mgmt == "Member-Managed":
        story.append(Paragraph("<b>5.1 Member-Managed Company.</b>", styles["Rob_Body"]))
        story.append(Paragraph(
            "The Company shall be a <b>member-managed</b> limited liability company. Each Member "
            "shall have authority to act on behalf of the Company and to bind the Company in the "
            "ordinary course of business, unless otherwise restricted by this Agreement or a "
            "resolution of the Members.",
            numbered_style
        ))

        story.append(Paragraph("<b>5.2 Voting Rights.</b>", styles["Rob_Body"]))
        story.append(Paragraph(
            "Except as otherwise provided in this Agreement or required by the TBOC, all "
            "decisions of the Company shall be made by Members holding a majority of the "
            "Membership Interests. Each Member shall have voting power proportionate to such "
            "Member's Membership Interest.",
            numbered_style
        ))

        story.append(Paragraph("<b>5.3 Unanimous Consent Required.</b>", styles["Rob_Body"]))
        story.append(Paragraph(
            "The following actions shall require the unanimous written consent of all Members: "
            "(a) amendment of this Agreement; (b) admission of new Members; (c) merger, "
            "consolidation, or conversion of the Company; (d) sale, lease, or exchange of all "
            "or substantially all of the Company's assets outside the ordinary course of "
            "business; (e) dissolution of the Company; (f) any action that would make it "
            "impossible to carry on the ordinary business of the Company.",
            numbered_style
        ))
    else:
        manager_name = d.get("manager_name", "[Manager Name]")
        story.append(Paragraph("<b>5.1 Manager-Managed Company.</b>", styles["Rob_Body"]))
        story.append(Paragraph(
            f"The Company shall be a <b>manager-managed</b> limited liability company. The "
            f"business and affairs of the Company shall be managed by the designated Manager: "
            f"<b>{manager_name}</b>. Members who are not Managers shall have no authority to "
            f"act on behalf of the Company or to bind the Company solely by virtue of their "
            f"status as Members.",
            numbered_style
        ))

        story.append(Paragraph("<b>5.2 Powers of Manager.</b>", styles["Rob_Body"]))
        story.append(Paragraph(
            f"Subject to the limitations set forth in this Agreement, the Manager shall have "
            f"full and exclusive power and authority to manage, control, administer, and operate "
            f"the business and affairs of the Company.",
            numbered_style
        ))

        story.append(Paragraph("<b>5.3 Unanimous Member Consent Required.</b>", styles["Rob_Body"]))
        story.append(Paragraph(
            f"Notwithstanding the foregoing, the following actions shall require the unanimous "
            f"written consent of all Members: (a) amendment of this Agreement; (b) admission of "
            f"new Members; (c) merger, consolidation, or conversion; (d) sale of all or "
            f"substantially all assets; (e) dissolution of the Company.",
            numbered_style
        ))

    story.append(Paragraph("<b>5.4 Meetings.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "Meetings of the Members may be held at any time and place as determined by the Members. "
        "Meetings may be held in person, by telephone, or by any other means of communication "
        "by which all participants can hear each other. Action may also be taken by written "
        "consent without a meeting if all Members entitled to vote on such action consent in writing.",
        numbered_style
    ))

    story.append(Paragraph("<b>5.5 Compensation.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "No Member shall be entitled to any salary or compensation from the Company for services "
        "rendered to the Company solely in such Member's capacity as a Member, unless otherwise "
        "agreed by all Members in writing.",
        numbered_style
    ))

    story.append(Paragraph("<b>5.6 Duties of Care and Loyalty.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "Each Member who participates in management of the Company owes a duty of loyalty and a "
        "duty of care to the Company and to the other Members as provided under the TBOC. A "
        "Member shall not engage in any activity that competes with the Company without the prior "
        "written consent of all other Members.",
        numbered_style
    ))
    story.append(Spacer(1, 0.08*inch))

    # ── ARTICLE VI — TRANSFER OF MEMBERSHIP INTERESTS ──
    story.append(Paragraph("ARTICLE VI — TRANSFER OF MEMBERSHIP INTERESTS", styles["Rob_Head"]))

    story.append(Paragraph("<b>6.1 Restrictions on Transfer.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "No Member may sell, assign, transfer, pledge, hypothecate, or otherwise dispose of all "
        "or any portion of such Member's Membership Interest (a <b>\"Transfer\"</b>) without the "
        "prior unanimous written consent of all other Members, which consent may be withheld in "
        "each Member's sole and absolute discretion.",
        numbered_style
    ))

    story.append(Paragraph("<b>6.2 Right of First Refusal.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "Before any Member (the <b>\"Selling Member\"</b>) may Transfer any Membership Interest "
        "to any third party, the Selling Member shall first offer such interest to the remaining "
        "Members at the same price and on the same terms as proposed for the third-party "
        "transfer. The remaining Members shall have thirty (30) days to accept such offer. If "
        "the remaining Members do not accept, the Selling Member may complete the Transfer to "
        "the third party on terms no more favorable than those offered to the remaining Members.",
        numbered_style
    ))

    story.append(Paragraph("<b>6.3 Involuntary Transfers.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "In the event of any involuntary Transfer of a Membership Interest, including by "
        "operation of law, foreclosure, or court order, the transferee shall have only the "
        "rights of an assignee per TBOC §§ 101.108–101.111 and shall not be admitted as a "
        "substituted Member without the unanimous written consent of the remaining Members.",
        numbered_style
    ))

    story.append(Paragraph("<b>6.4 Permitted Transfers.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "Notwithstanding the foregoing, a Member may Transfer all or any portion of such "
        "Member's Membership Interest to a revocable living trust for estate planning purposes "
        "in which such Member is the sole trustee and beneficiary, provided that such Member "
        "retains exclusive voting and management rights over such transferred interest.",
        numbered_style
    ))
    story.append(Spacer(1, 0.08*inch))

    # ── ARTICLE VII — DISSOCIATION AND BUYOUT OF MEMBERSHIP INTERESTS ──
    story.append(Paragraph("ARTICLE VII — DISSOCIATION AND BUYOUT OF MEMBERSHIP INTERESTS", styles["Rob_Head"]))

    story.append(Paragraph("<b>7.1 Events of Dissociation.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "A Member shall be deemed to have dissociated from the Company (a &#x201C;Dissociated "
        "Member&#x201D;) upon the occurrence of any of the following events with respect to such "
        "Member: (a) death; (b) adjudication of incapacity or disability rendering the Member "
        "unable to participate in the Company's affairs for a continuous period of ninety (90) "
        "days or more; (c) Bankruptcy; (d) entry of a final divorce decree purporting to award all "
        "or part of such Member's Membership Interest to a former spouse; (e) voluntary withdrawal "
        "in violation of Section 2.5; or (f) expulsion by unanimous written consent of all other "
        "Members for a material, uncured breach of this Agreement.",
        numbered_style
    ))

    story.append(Paragraph("<b>7.2 Effect of Dissociation.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "A Dissociated Member ceases to have any right to participate in the management of the "
        "Company and retains only the rights of an assignee under TBOC &#xA7;&#xA7; 101.108&#x2013;101.111 "
        "to receive distributions and allocations attributable to such Member's Membership "
        "Interest, unless and until the Company exercises the buyout option in Section 7.3.",
        numbered_style
    ))

    story.append(Paragraph("<b>7.3 Company Buyout Option.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "Upon a Member's dissociation under Section 7.1, the Company shall have the option, "
        "exercisable by written notice to the Dissociated Member (or such Member's estate or "
        "representative) within ninety (90) days after the Company has actual knowledge of the "
        "dissociating event, to purchase all (but not less than all) of the Dissociated Member's "
        "Membership Interest at the Buyout Price determined under Section 7.4. If the Company "
        "does not exercise this option, the remaining Members shall have a further thirty (30) "
        "days to exercise the same option pro rata in proportion to their respective Membership "
        "Interests (or as they otherwise agree).",
        numbered_style
    ))

    story.append(Paragraph("<b>7.4 Determination of Buyout Price.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "The &#x201C;Buyout Price&#x201D; for a Dissociated Member's Membership Interest shall be "
        "the fair market value of such Interest as agreed in writing by the Company and the "
        "Dissociated Member within thirty (30) days after exercise of the option under Section "
        "7.3. If the parties cannot agree on fair market value within that period, each party "
        "shall select a qualified, independent business appraiser, the two appraisers shall "
        "jointly select a third, and the Buyout Price shall be the average of the two appraisals "
        "closest in value, with no minority-interest discount applied to the extent the Dissociated "
        "Member's Interest, together with any other Interests acting in concert, represented a "
        "controlling interest immediately before dissociation. The cost of appraisal shall be "
        "borne equally by the Company and the Dissociated Member.",
        numbered_style
    ))

    story.append(Paragraph("<b>7.5 Payment Terms.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "Unless the Company and the Dissociated Member otherwise agree in writing, the Buyout "
        "Price shall be paid (a) twenty percent (20%) in cash at closing, and (b) the balance by "
        "promissory note payable in equal quarterly installments over a term not to exceed five "
        "(5) years, bearing interest at the applicable federal rate published by the IRS for the "
        "month of closing, secured by the Membership Interest being purchased. The Company may "
        "prepay the note in whole or in part at any time without penalty.",
        numbered_style
    ))
    story.append(Spacer(1, 0.08*inch))

    # ── ARTICLE VIII — BOOKS, RECORDS, AND ACCOUNTING ──
    story.append(Paragraph("ARTICLE VIII — BOOKS, RECORDS, AND ACCOUNTING", styles["Rob_Head"]))

    story.append(Paragraph("<b>8.1 Books and Records.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "The Company shall keep accurate and complete books and records of account and other "
        "Company records at its principal office or at such other place as the Members shall "
        "designate. Each Member shall have the right to inspect and copy the Company's books "
        "and records at any reasonable time per TBOC §§ 101.501–101.502.",
        numbered_style
    ))

    story.append(Paragraph("<b>8.2 Fiscal Year.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        f"The fiscal year of the Company shall end on {fiscal} of each calendar year, "
        f"unless otherwise determined by the Members.",
        numbered_style
    ))

    story.append(Paragraph("<b>8.3 Tax Treatment.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "The Members intend for the Company to be treated as a partnership for federal and "
        "state income tax purposes (or, if there is only one Member, as a disregarded entity), "
        "unless the Members unanimously elect otherwise. The Company shall file all required "
        "federal and state tax returns and informational statements.",
        numbered_style
    ))

    story.append(Paragraph("<b>8.4 Partnership Representative.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "If the Company is treated as a partnership for federal income tax purposes, the Members "
        "designate the Manager (or, if the Company is member-managed, the Member holding the "
        "largest Membership Interest, or such other Member as the Members shall designate) as the "
        "Company's \"Partnership Representative\" within the meaning of Section 6223 of the "
        "Internal Revenue Code, as enacted by the Bipartisan Budget Act of 2015. The Partnership "
        "Representative shall have sole authority to act on behalf of the Company in connection "
        "with any audit or other proceeding before the Internal Revenue Service, shall keep the "
        "Members reasonably informed of any such proceeding, and shall not bind the Members to a "
        "settlement or election without the consent of Members holding a majority of the "
        "Membership Interests, except as required by law.",
        numbered_style
    ))

    story.append(Paragraph("<b>8.5 Bank Accounts.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "The Company shall maintain one or more bank accounts in the name of the Company. All "
        "Company funds shall be deposited in such accounts and shall not be commingled with the "
        "personal funds of any Member. Withdrawals shall be made only by persons authorized by "
        "the Members.",
        numbered_style
    ))
    story.append(Spacer(1, 0.08*inch))

    # ── ARTICLE IX — DISSOLUTION AND WINDING UP ──
    story.append(Paragraph("ARTICLE IX — DISSOLUTION AND WINDING UP", styles["Rob_Head"]))

    story.append(Paragraph("<b>9.1 Events of Dissolution.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "The Company shall be dissolved and its affairs wound up upon the occurrence of any of "
        "the following events: (a) the written consent of all Members to dissolve; (b) the "
        "entry of a decree of judicial dissolution by a court of competent jurisdiction pursuant "
        "to the TBOC; or (c) any other event that causes dissolution under TBOC § 101.552.",
        numbered_style
    ))

    story.append(Paragraph("<b>9.2 Winding Up.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "Upon dissolution, the Members, or a liquidating trustee appointed by the Members, "
        "shall wind up the Company's affairs. The assets of the Company shall be applied in "
        "the following order: (a) payment of creditors of the Company in the order of priority "
        "as provided by applicable law; (b) return of capital contributions to Members to the "
        "extent of their capital account balances; and (c) distribution of remaining assets to "
        "Members in proportion to their Membership Interests.",
        numbered_style
    ))

    story.append(Paragraph("<b>9.3 Certificate of Termination.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "Upon completion of the winding up of the Company's affairs, the Members shall file a "
        "Certificate of Termination (Form 651) with the Texas Secretary of State as required "
        "by the TBOC.",
        numbered_style
    ))
    story.append(Spacer(1, 0.08*inch))

    # ── ARTICLE X — CONFIDENTIALITY AND DISPUTE RESOLUTION ──
    story.append(Paragraph("ARTICLE X — CONFIDENTIALITY AND DISPUTE RESOLUTION", styles["Rob_Head"]))

    story.append(Paragraph("<b>10.1 Confidentiality.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "Each Member shall hold in strict confidence all non-public information concerning the "
        "business, financial condition, strategy, and operations of the Company (\"Confidential "
        "Information\") and shall not disclose Confidential Information to any third party without "
        "the prior written consent of the Members, except (a) to the Member's attorneys, "
        "accountants, or other professional advisors who are bound by a duty of confidentiality, "
        "(b) as required by applicable law, subpoena, or court order, or (c) information that is "
        "or becomes generally available to the public other than through a breach of this Section. "
        "This obligation shall survive a Member's dissociation or Transfer of such Member's "
        "Membership Interest and the termination of this Agreement.",
        numbered_style
    ))

    story.append(Paragraph("<b>10.2 Negotiation and Mediation.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "Before initiating any arbitration or litigation under this Article, the Members shall "
        "attempt in good faith to resolve any dispute arising out of or relating to this Agreement "
        "through direct negotiation for a period of not less than fifteen (15) days, followed, if "
        "unresolved, by non-binding mediation administered by a mutually agreeable mediator in the "
        "county where the Company's principal office is located.",
        numbered_style
    ))

    story.append(Paragraph("<b>10.3 Binding Arbitration.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "Any dispute not resolved under Section 10.2 within forty-five (45) days after the "
        "initial notice of dispute shall be resolved by binding arbitration administered by the "
        "American Arbitration Association under its Commercial Arbitration Rules, before a single "
        "arbitrator, in the county where the Company's principal office is located. The arbitrator "
        "may award costs and reasonable attorneys' fees to the prevailing party. Notwithstanding "
        "the foregoing, any Member or the Company may seek emergency injunctive relief from a "
        "court of competent jurisdiction without first complying with this Article, and any matter "
        "requiring judicial dissolution under TBOC &#xA7; 101.552(1) may be brought directly in court.",
        numbered_style
    ))
    story.append(Spacer(1, 0.08*inch))

    # ── ARTICLE XI — MISCELLANEOUS ──
    story.append(Paragraph("ARTICLE XI — MISCELLANEOUS", styles["Rob_Head"]))

    story.append(Paragraph("<b>11.1 Indemnification.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "The Company shall indemnify and hold harmless each Member from and against any claims, "
        "liabilities, damages, costs, and expenses (including reasonable attorneys' fees) "
        "arising out of the Member's activities on behalf of the Company, to the fullest extent "
        "permitted by the TBOC and Chapter 8 thereof, provided that such Member acted in good "
        "faith and in a manner reasonably believed to be in the best interests of the Company.",
        numbered_style
    ))

    story.append(Paragraph("<b>11.2 Entire Agreement.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "This Agreement constitutes the entire agreement of the Members with respect to the "
        "subject matter hereof and supersedes all prior agreements, understandings, "
        "negotiations, and discussions, whether oral or written, between the Members.",
        numbered_style
    ))

    story.append(Paragraph("<b>11.3 Amendment.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "This Agreement may be amended only by a written instrument signed by all Members, "
        "as required by TBOC § 101.053.",
        numbered_style
    ))

    story.append(Paragraph("<b>11.4 Severability.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "If any provision of this Agreement is found to be invalid, illegal, or unenforceable, "
        "the remaining provisions shall remain in full force and effect.",
        numbered_style
    ))

    story.append(Paragraph("<b>11.5 Counterparts.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "This Agreement may be executed in one or more counterparts, each of which shall be "
        "deemed an original, and all of which together shall constitute one and the same "
        "instrument. Electronic signatures shall be deemed valid and binding.",
        numbered_style
    ))

    story.append(Paragraph("<b>11.6 Notices.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "All notices required or permitted under this Agreement shall be in writing and shall "
        "be delivered personally, by certified mail (return receipt requested), or by electronic "
        "mail to the address of each Member as reflected in the Company's records.",
        numbered_style
    ))

    story.append(Paragraph("<b>11.7 Waiver.</b>", styles["Rob_Body"]))
    story.append(Paragraph(
        "The failure of any Member to exercise any right or remedy under this Agreement shall "
        "not constitute a waiver of such right or remedy.",
        numbered_style
    ))
    story.append(Spacer(1, 0.08*inch))

    # ── SIGNATURE PAGE ──
    story.append(PageBreak())
    story.append(Paragraph("SIGNATURE PAGE", styles["Rob_Title"]))
    story.append(Paragraph(
        f"IN WITNESS WHEREOF, the undersigned Member(s) of {name} have executed this Company "
        f"Agreement as of {eff_date}.",
        justify_style
    ))
    story.append(Spacer(1, 0.25*inch))

    for m in members:
        sig_data = [
            [f"Member: {m.get('name','')}", f"Membership Interest: {m.get('pct',0):.1f}%"],
            ["", ""],
            ["Signature: _________________________________", "Date: _________________"],
            ["", ""],
            ["Printed Name: _______________________________", ""],
        ]
        sig_table = Table(sig_data, colWidths=[3.4*inch, 2.6*inch])
        sig_table.setStyle(TableStyle([
            ("FONTSIZE",      (0,0), (-1,-1), 10),
            ("LEADING",       (0,0), (-1,-1), 16),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("TOPPADDING",    (0,0), (-1,-1), 4),
        ]))
        story.append(sig_table)
        story.append(Spacer(1, 0.25*inch))

    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#aaaaaa")))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "IMPORTANT: This document is an internal governance record. DO NOT file with the "
        "Texas Secretary of State. Prepared by ParalegalRob | Not legal advice.",
        styles["Rob_Small"]
    ))

    doc = SimpleDocTemplate(buf, pagesize=LETTER,
                            leftMargin=0.85*inch, rightMargin=0.85*inch,
                            topMargin=0.85*inch, bottomMargin=0.85*inch)
    doc.build(story)
    buf.seek(0)
    return buf


def pdf_banking_resolution(d: dict) -> BytesIO:
    """Banking Resolution — authorizes signatories and bank account opening."""
    buf = BytesIO()
    styles = _styles()

    from reportlab.lib.enums import TA_JUSTIFY
    justify_style = ParagraphStyle(
        "BR_Justify", parent=styles["Rob_Body"],
        alignment=TA_JUSTIFY, spaceAfter=6,
    )
    numbered_style = ParagraphStyle(
        "BR_Numbered", parent=styles["Rob_Body"],
        leftIndent=18, alignment=TA_JUSTIFY, spaceAfter=6,
    )
    disclaimer_style = ParagraphStyle(
        "BR_Disclaimer", fontName="Helvetica", fontSize=8, leading=11,
        spaceAfter=6, textColor=colors.HexColor("#555555"), alignment=TA_JUSTIFY,
    )

    name      = d.get("name", "the Company")
    members   = d.get("members", [])
    eff_date  = d.get("eff_date", fmt_date(datetime.date.today()))
    address   = d.get("address", "[Principal Office Address]")

    story = []

    # Cover
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph("BANKING RESOLUTION", styles["Rob_Title"]))
    story.append(Paragraph("OF", styles["Rob_Sub"]))
    story.append(Paragraph(name.upper(), styles["Rob_Title"]))
    story.append(Spacer(1, 0.05 * inch))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor(ACCENT)))
    story.append(Spacer(1, 0.08 * inch))
    story.append(Paragraph("A Texas Limited Liability Company", styles["Rob_Sub"]))
    story.append(Paragraph(f"Effective: {eff_date}", styles["Rob_Sub"]))
    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph(
        "DISCLAIMER: This document was prepared by ParalegalRob, a document preparation service. "
        "It does not constitute legal advice and has not been reviewed by an attorney. "
        "Consult a licensed Texas attorney before executing.",
        disclaimer_style
    ))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#aaaaaa")))
    story.append(Spacer(1, 0.15 * inch))

    # Preamble
    story.append(Paragraph(
        f"The undersigned, being all of the Members of {name} (the \"Company\"), a Texas limited "
        f"liability company, hereby certify and resolve as follows, effective as of {eff_date}:",
        justify_style
    ))
    story.append(Spacer(1, 0.1 * inch))

    # Resolutions
    resolutions = [
        (
            "1. Authority to Open Accounts",
            f"The Company is authorized to open, maintain, and close deposit accounts, checking "
            f"accounts, savings accounts, and other banking accounts at such financial institutions "
            f"as the Members shall determine (each, a \"Depository\")."
        ),
        (
            "2. Authorized Signatories",
            "The following individuals are hereby authorized to sign checks, drafts, orders, and "
            "other instruments on behalf of the Company, and to execute any agreements with the "
            "Depository on behalf of the Company:\n\n"
            + "\n".join(
                f"   \u2022  {m.get('name', '')}  \u2014  {m.get('pct', 0):.1f}% Member"
                for m in members
            )
            + "\n\nAny one (1) authorized signatory acting alone shall have authority to act on "
            "behalf of the Company for routine banking transactions."
        ),
        (
            "3. Certification of Company Documents",
            f"A copy of the Company's Certificate of Formation as filed with the Texas Secretary "
            f"of State, and a copy of the Company Agreement, are hereby certified as true and "
            f"correct and may be presented to the Depository."
        ),
        (
            "4. Employer Identification Number",
            f"The Company's Employer Identification Number (EIN), as issued by the Internal "
            f"Revenue Service, shall be provided to the Depository and used for all banking and "
            f"tax purposes."
        ),
        (
            "5. Prohibition on Commingling",
            f"All Company funds shall be maintained separately from the personal funds of any "
            f"Member. No Member shall use Company accounts for personal transactions. "
            f"Commingling of funds may result in loss of limited liability protection."
        ),
        (
            "6. Further Authority",
            f"The authorized signatories are further authorized to execute signature cards, "
            f"Depository resolutions, and all other bank documentation necessary to open and "
            f"maintain Company accounts."
        ),
    ]

    for res_title, res_text in resolutions:
        story.append(Paragraph(f"<b>{res_title}</b>", styles["Rob_Body"]))
        story.append(Paragraph(res_text, numbered_style))
        story.append(Spacer(1, 4))

    # Adoption language
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(
        f"This Banking Resolution is adopted by unanimous written consent of all Members of "
        f"{name} and is effective as of {eff_date}.",
        justify_style
    ))
    story.append(Spacer(1, 0.25 * inch))

    # Signature blocks
    for m in members:
        sig_data = [
            [f"Member: {m.get('name', '')}",
             f"Membership Interest: {m.get('pct', 0):.1f}%"],
            ["", ""],
            ["Signature: _________________________________", "Date: _________________"],
            ["", ""],
            ["Printed Name: _______________________________", ""],
        ]
        sig_table = Table(sig_data, colWidths=[3.4 * inch, 2.6 * inch])
        sig_table.setStyle(TableStyle([
            ("FONTSIZE",      (0, 0), (-1, -1), 10),
            ("LEADING",       (0, 0), (-1, -1), 16),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ]))
        story.append(sig_table)
        story.append(Spacer(1, 0.2 * inch))

    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#aaaaaa")))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "IMPORTANT: This is an internal governance record. DO NOT file with the Texas Secretary "
        "of State. Prepared by ParalegalRob | Not legal advice.",
        styles["Rob_Small"]
    ))

    doc = SimpleDocTemplate(buf, pagesize=LETTER,
                            leftMargin=0.85 * inch, rightMargin=0.85 * inch,
                            topMargin=0.85 * inch, bottomMargin=0.85 * inch)
    doc.build(story)
    buf.seek(0)
    return buf


def pdf_organizational_minutes(d: dict) -> BytesIO:
    """Organizational Meeting Minutes — records initial member resolutions."""
    buf = BytesIO()
    styles = _styles()

    from reportlab.lib.enums import TA_JUSTIFY
    justify_style = ParagraphStyle(
        "OM_Justify", parent=styles["Rob_Body"],
        alignment=TA_JUSTIFY, spaceAfter=6,
    )
    numbered_style = ParagraphStyle(
        "OM_Numbered", parent=styles["Rob_Body"],
        leftIndent=18, alignment=TA_JUSTIFY, spaceAfter=6,
    )
    disclaimer_style = ParagraphStyle(
        "OM_Disclaimer", fontName="Helvetica", fontSize=8, leading=11,
        spaceAfter=6, textColor=colors.HexColor("#555555"), alignment=TA_JUSTIFY,
    )

    name      = d.get("name", "the Company")
    members   = d.get("members", [])
    mgmt      = d.get("mgmt", "Member-Managed")
    eff_date  = d.get("eff_date", fmt_date(datetime.date.today()))
    address   = d.get("address", "[Principal Office Address]")
    agent     = d.get("agent_name", "[Registered Agent]")
    fiscal    = d.get("fiscal_year", "December 31")
    manager_name = d.get("manager_name", "")

    story = []

    # Cover
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph("MINUTES OF ORGANIZATIONAL MEETING", styles["Rob_Title"]))
    story.append(Paragraph("OF THE MEMBERS OF", styles["Rob_Sub"]))
    story.append(Paragraph(name.upper(), styles["Rob_Title"]))
    story.append(Spacer(1, 0.05 * inch))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor(ACCENT)))
    story.append(Spacer(1, 0.08 * inch))
    story.append(Paragraph("A Texas Limited Liability Company", styles["Rob_Sub"]))
    story.append(Paragraph(f"Date of Meeting: {eff_date}", styles["Rob_Sub"]))
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(
        "NOTE: Fill in bracketed fields before execution. Retain with Company records. "
        "Do not file with the Texas Secretary of State.",
        disclaimer_style
    ))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#aaaaaa")))
    story.append(Spacer(1, 0.15 * inch))

    # Meeting details
    story.append(Paragraph("<b>Meeting Details</b>", styles["Rob_Head"]))
    details = [
        ["Date:", eff_date],
        ["Time:", "[_______ AM / PM]"],
        ["Location:", address if address.strip() else "[Meeting Location]"],
        ["Members Present:", ", ".join(m.get("name", "") for m in members) or "[Member Names]"],
        ["Members Absent:", "None"],
        ["Management Structure:", mgmt],
    ]
    det_table = Table(details, colWidths=[1.8 * inch, 4.2 * inch])
    det_table.setStyle(TableStyle([
        ("FONTNAME",      (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("LEADING",       (0, 0), (-1, -1), 14),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TEXTCOLOR",     (0, 0), (0, -1), colors.HexColor(BRAND_COL)),
    ]))
    story.append(det_table)
    story.append(Spacer(1, 0.15 * inch))

    # Minutes body
    story.append(Paragraph("<b>1. Call to Order</b>", styles["Rob_Head"]))
    story.append(Paragraph(
        f"The organizational meeting of the Members of {name} was called to order at the time "
        f"and place noted above. A quorum of Members was present and the meeting was duly convened.",
        justify_style
    ))

    story.append(Paragraph("<b>2. Company Agreement</b>", styles["Rob_Head"]))
    story.append(Paragraph(
        f"The Company Agreement of {name} was presented to the Members for review. Upon motion "
        f"duly made and seconded, the Company Agreement was unanimously approved and adopted as "
        f"the governing document of the Company.",
        justify_style
    ))

    story.append(Paragraph("<b>3. Management Structure</b>", styles["Rob_Head"]))
    if mgmt == "Member-Managed":
        story.append(Paragraph(
            f"The Members confirmed that the Company shall be member-managed. Each Member shall "
            f"have authority to act on behalf of the Company in the ordinary course of business "
            f"in proportion to their respective Membership Interests.",
            justify_style
        ))
    else:
        story.append(Paragraph(
            f"The Members confirmed that the Company shall be manager-managed. "
            f"{'The following individual was designated as the initial Manager: ' + manager_name + '.' if manager_name else 'The initial Manager shall be designated by separate written resolution.'}",
            justify_style
        ))

    story.append(Paragraph("<b>4. Registered Agent</b>", styles["Rob_Head"]))
    story.append(Paragraph(
        f"The appointment of {agent} as the registered agent of the Company at the address "
        f"reflected in the Certificate of Formation was confirmed and approved.",
        justify_style
    ))

    story.append(Paragraph("<b>5. Fiscal Year and Tax Classification</b>", styles["Rob_Head"]))
    story.append(Paragraph(
        f"The fiscal year of the Company ending {fiscal} was confirmed. The Members acknowledged "
        f"the Company's default federal tax classification as a "
        f"{'disregarded entity' if len(members) == 1 else 'partnership'} and confirmed no "
        f"election to change classification has been made at this time.",
        justify_style
    ))

    story.append(Paragraph("<b>6. Banking Authorization</b>", styles["Rob_Head"]))
    story.append(Paragraph(
        f"The Members authorized the Company to open one or more business bank accounts in the "
        f"name of the Company. The Banking Resolution adopted concurrently with these Minutes "
        f"identifies the authorized signatories. No Company funds shall be commingled with "
        f"personal funds of any Member.",
        justify_style
    ))

    story.append(Paragraph("<b>7. EIN Authorization</b>", styles["Rob_Head"]))
    story.append(Paragraph(
        f"The Members authorized any Member or designated representative to apply for an "
        f"Employer Identification Number from the Internal Revenue Service on behalf of the "
        f"Company, and to execute all documents necessary therefor.",
        justify_style
    ))

    story.append(Paragraph("<b>8. BOI Filing Authorization</b>", styles["Rob_Head"]))
    story.append(Paragraph(
        f"The Members acknowledged the Company's obligation to file a Beneficial Ownership "
        f"Information (BOI) report with the Financial Crimes Enforcement Network (FinCEN) under "
        f"the Corporate Transparency Act. Any Member is authorized to complete and submit such "
        f"filing at fincen.gov/boi within the required deadline.",
        justify_style
    ))

    story.append(Paragraph("<b>9. Adjournment</b>", styles["Rob_Head"]))
    story.append(Paragraph(
        "There being no further business to come before the meeting, the meeting was duly "
        "adjourned.",
        justify_style
    ))

    # Certification and signatures
    story.append(PageBreak())
    story.append(Paragraph("CERTIFICATION", styles["Rob_Title"]))
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(
        f"The undersigned, being all of the Members of {name}, hereby certify that the foregoing "
        f"Minutes are a true and accurate record of the organizational meeting of the Company "
        f"held on {eff_date}.",
        justify_style
    ))
    story.append(Spacer(1, 0.25 * inch))

    for m in members:
        sig_data = [
            [f"Member: {m.get('name', '')}",
             f"Membership Interest: {m.get('pct', 0):.1f}%"],
            ["", ""],
            ["Signature: _________________________________", "Date: _________________"],
            ["", ""],
            ["Printed Name: _______________________________", ""],
        ]
        sig_table = Table(sig_data, colWidths=[3.4 * inch, 2.6 * inch])
        sig_table.setStyle(TableStyle([
            ("FONTSIZE",      (0, 0), (-1, -1), 10),
            ("LEADING",       (0, 0), (-1, -1), 16),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ]))
        story.append(sig_table)
        story.append(Spacer(1, 0.2 * inch))

    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#aaaaaa")))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "IMPORTANT: This is an internal governance record. DO NOT file with the Texas Secretary "
        "of State. Prepared by ParalegalRob | Not legal advice.",
        styles["Rob_Small"]
    ))

    doc = SimpleDocTemplate(buf, pagesize=LETTER,
                            leftMargin=0.85 * inch, rightMargin=0.85 * inch,
                            topMargin=0.85 * inch, bottomMargin=0.85 * inch)
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
    ready = (name and ra_name and ra_street and ra_city and ra_zip and org_name
             and abs(total_pct - 100.0) < 0.01)
    if not ready and abs(total_pct - 100.0) >= 0.01:
        st.error("⚠️ Cannot generate documents until Membership Interests total exactly 100%.")
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
            st.download_button(
                "📥 Form 205 (Certificate of Formation)",
                pdf_form205(payload),
                safe_fname(name, "_Form205.pdf"),
                mime="application/pdf",
                use_container_width=True
            )
        with dc2:
            st.download_button(
                "📥 Company Operating Agreement",
                pdf_operating_agreement(payload),
                safe_fname(name, "_OperatingAgreement.pdf"),
                mime="application/pdf",
                use_container_width=True
            )

        dc3, dc4 = st.columns(2)
        with dc3:
            st.download_button(
                "📥 Banking Resolution",
                pdf_banking_resolution(payload),
                safe_fname(name, "_BankingResolution.pdf"),
                mime="application/pdf",
                use_container_width=True
            )
        with dc4:
            st.download_button(
                "📥 Organizational Meeting Minutes",
                pdf_organizational_minutes(payload),
                safe_fname(name, "_MeetingMinutes.pdf"),
                mime="application/pdf",
                use_container_width=True
            )

        st.markdown(f"""
<div class="checklist-box">
<b>📋 Client Delivery Checklist</b><br><br>
<b>Documents generated — all 4 retain in client records:</b><br>
• <b>Form 205</b> — print 2 copies, client signs both, mail both + $300 check to SOS<br>
• <b>Company Agreement</b> — 1 copy for client records (do NOT file with state)<br>
• <b>Banking Resolution</b> — present to bank when opening business account<br>
• <b>Organizational Meeting Minutes</b> — fill in bracketed fields, sign, retain in records<br><br>
<b>Client action sequence:</b><br>
1. File Form 205 with SOS (mail or SOSDirect) — $300 fee<br>
2. Obtain EIN at IRS.gov (free, instant online)<br>
3. Execute Company Agreement, Banking Resolution, and Meeting Minutes<br>
4. Open business bank account (bring EIN letter, Form 205, Banking Resolution)<br>
5. File BOI report at fincen.gov/boi within 30–90 days of formation<br>
6. Set franchise tax reminder — due May 15 annually<br><br>
<b>State fees (client pays direct):</b>
<span class="fee-tag">$300 SOS filing</span>
<span class="fee-tag">$0 EIN</span>
<span class="fee-tag">$0 BOI filing</span>
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

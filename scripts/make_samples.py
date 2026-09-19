"""Generate the SAMPLE / FICTIONAL HR documents shipped with the repository.

Creates:
  data/documents/employee_handbook.pdf      (hand-built minimal PDF)
  data/documents/employee_handbook.docx     (python-docx)
  data/documents/leave_policy.txt
  data/documents/remote_work_policy.txt
  data/documents/parental_leave_policy.txt
  data/documents/code_of_conduct.txt
  data/documents/workplace_harassment_policy.txt
  data/documents/confidentiality_policy.txt

All content is fictional and used only to demonstrate the RAG pipeline.
Run:  python scripts/make_samples.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, ".")

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = REPO_ROOT / "data" / "documents"


# --------------------------------------------------------------------------- #
# Content
# --------------------------------------------------------------------------- #
HANDBOOK_SECTIONS: list[tuple[str, list[str]]] = [
    (
        "Acme Corp Employee Handbook",
        [
            "Effective Date: January 1, 2026. Version 3.2",
            "This handbook describes the general employment policies of Acme Corp.",
        ],
    ),
    (
        "Working Hours",
        [
            "Standard working hours are 9:00 AM to 5:30 PM, Monday through Friday, totalling 40 hours per week.",
            "Employees may adjust their start and end times by up to one hour with their manager's approval.",
            "Full-time employees are entitled to a one-hour unpaid lunch break and two paid 15-minute breaks per day.",
            "Overtime must be approved in advance by the employee's manager and is compensated according to local law.",
            "Flexible and remote working arrangements are described in the Remote Work Policy.",
        ],
    ),
    (
        "Employment Classification",
        [
            "Employees are classified as exempt or non-exempt in line with applicable labour law.",
            "Non-exempt employees are paid on an hourly basis, while exempt employees receive a salaried compensation package.",
            "All employees must record their working time in the Acme HR Portal.",
        ],
    ),
    (
        "Compensation and Pay Periods",
        [
            "Salaries are paid on the last business day of every month via direct deposit.",
            "Hourly wages are paid bi-weekly on Fridays.",
            "Employees can review their payslips in the Acme HR Portal at any time.",
        ],
    ),
    (
        "Annual Leave",
        [
            "Full-time employees accrue 20 days of paid annual leave per calendar year.",
            "Annual leave is accrued monthly at a rate of 1.67 days per month.",
            "Up to 5 unused days may be carried over to the next calendar year, subject to manager approval.",
            "Annual leave requests must be submitted at least 7 days in advance through the HR Portal.",
        ],
    ),
    (
        "Sick Leave",
        [
            "All employees are entitled to 10 paid sick leave days per calendar year.",
            "For absences longer than 3 consecutive days, a medical certificate is required.",
            "Employees must notify their manager before 9:00 AM on the first day of absence.",
        ],
    ),
    (
        "Code of Conduct",
        [
            "Employees must behave with honesty, integrity and respect at all times.",
            "Secondary employment is permitted only when it does not create a conflict of interest and has been approved in writing by the People team.",
        ],
    ),
]

LEAVE_POLICY = """
Annual Leave Policy

Effective Date: January 1, 2026

1. Eligibility

All full-time employees who complete their probation period are eligible for paid annual leave. Part-time employees accrue annual leave on a pro-rata basis.

2. Annual Leave Entitlement

Full-time employees are entitled to 20 working days of paid annual leave per calendar year. Annual leave accrues monthly at a rate of 1.67 days per month. Leave does not accrue during unpaid leave or extended absences without pay.

3. Requesting Annual Leave

Annual leave requests must be submitted through the Acme HR Portal at least 7 working days in advance. Requests are reviewed and approved by the employee's manager. Managers must respond within 3 working days. Leave may be refused or rescheduled only for operational reasons.

4. Carry Over

A maximum of 5 unused annual leave days may be carried over into the next calendar year. Carry-over requires written manager approval and must be used before the end of the first quarter of the following year.

5. Sick Leave

Every employee is entitled to 10 paid sick leave days per calendar year. Sick days do not roll over. If an illness lasts longer than 3 consecutive days, a medical certificate must be provided to the People team.

6. Public Holidays

Acme Corp observes the national public holidays as listed on the company intranet. Public holidays do not reduce an employee's annual leave entitlement.

7. Unpaid Leave

Employees who have exhausted their paid leave may request unpaid leave for personal reasons, subject to manager and People team approval.

8. Leave Balance

Employees can view their current leave balances at any time in the Acme HR Portal.
"""

REMOTE_WORK_POLICY = """
Remote Work Policy

Effective Date: January 1, 2026

1. Overview

Acme Corp supports a hybrid working model that combines time in the office with remote work.

2. Eligibility

Employees in roles that do not require continuous physical presence on site are eligible for hybrid work. The employee's manager makes the final decision on eligibility based on role requirements.

3. Hybrid Schedule

Employees are expected to work from the office at least 3 days per week and may work remotely for up to 2 days per week. Employees must coordinate their office days with their team to ensure adequate coverage.

4. Remote Work Agreement

Employees who regularly work remotely must sign a Remote Work Agreement with their manager. The agreement covers working hours, communication expectations, data security obligations and equipment use.

5. Equipment and Stipend

Acme Corp provides a company laptop for employees with an approved remote work arrangement. Remote employees receive a one-time home office setup stipend of $500 for furniture and peripherals.

6. Data Security

Remote work must comply with the Confidentiality Policy. Employees must use the company VPN when accessing corporate systems and must not work on company data in public locations without a privacy screen.

7. Availability

During agreed working hours, remote employees must be reachable on the company messaging system and must respond within two business hours.

8. Health and Safety

Employees are responsible for ensuring their home workstation meets basic ergonomic and safety standards. Acme Corp may schedule an ergonomic assessment on request.
"""

PARENTAL_LEAVE_POLICY = """
Parental Leave Policy

Effective Date: January 1, 2026

1. Overview

Acme Corp supports its employees during the arrival of a new child through paid parental leave.

2. Maternity Leave

Biological mothers are entitled to 16 weeks of fully paid maternity leave. The leave may begin up to 4 weeks before the expected due date.

3. Paternity Leave

Biological fathers and same-sex partners are entitled to 8 weeks of fully paid paternity leave.

4. Adoption Leave

Employees who adopt a child are entitled to 8 weeks of fully paid adoption leave.

5. Shared Parental Leave

Where both parents work at Acme Corp, the combined parental leave may be shared between them, with a maximum combined total of 16 paid weeks.

6. Notification

Employees must notify the People team of their intention to take parental leave at least 30 days before the leave start date, or as soon as reasonably possible.

7. Job Protection

An employee on parental leave is guaranteed the right to return to the same role, or a comparable role at the same level and salary, at the end of their leave.

8. Summary of Entitlements

Maternity: 16 weeks paid. Paternity: 8 weeks paid. Adoption: 8 weeks paid. Shared parental: up to 16 weeks paid combined.
"""

CODE_OF_CONDUCT = """
Code of Conduct

Effective Date: January 1, 2026

1. Purpose

The Code of Conduct sets out the standards of behaviour expected from every Acme Corp employee, contractor and representative.

2. Honesty and Integrity

Employees must act with honesty, fairness and integrity in all business dealings. Deliberately misleading customers, colleagues, regulators or the public is a disciplinary offence.

3. Conflicts of Interest

Employees must avoid situations where their personal interests conflict with the interests of Acme Corp. Any real or perceived conflict must be disclosed in writing to the People team.

4. Gifts and Hospitality

Employees may accept gifts or hospitality with a value of up to $50 from a business partner. Gifts above this threshold must be declared. Cash gifts are never acceptable.

5. Anti-Bribery

Acme Corp has a zero-tolerance policy towards bribery and corruption. Offering, giving, soliciting or accepting bribes in any form is strictly prohibited.

6. Confidentiality

Employees must protect Acme Corp's confidential information and the personal data of colleagues and customers as described in the Confidentiality Policy.

7. Equal Treatment and Respect

Employees must treat every colleague with respect. Discrimination, bullying or harassment of any kind is prohibited and is addressed in the Workplace Harassment Policy.

8. Social Media

Employees are personally responsible for their public social media activity. Content must not disclose confidential information, disparage Acme Corp, or otherwise damage the company's reputation.

9. Reporting Violations

Employees who become aware of a breach of this Code must report it through the internal reporting channels. Concerns may be raised confidentially without fear of retaliation.
"""

HARASSMENT_POLICY = """
Workplace Harassment Policy

Effective Date: January 1, 2026

1. Zero Tolerance

Acme Corp maintains a zero-tolerance policy towards workplace harassment, sexual harassment, bullying and discrimination in any form.

2. Definition of Harassment

Harassment is unwelcome conduct, whether verbal, physical or visual, that is based on a protected characteristic such as race, colour, religion, sex, gender identity, sexual orientation, national origin, age, disability or pregnancy status. Harassment also includes any behaviour that creates an intimidating, hostile or offensive working environment.

3. Sexual Harassment

Sexual harassment includes unwelcome sexual advances, requests for sexual favours, and other verbal, non-verbal or physical conduct of a sexual nature. This applies regardless of seniority, gender or the relationship between the individuals involved.

4. Examples of Prohibited Conduct

Prohibited conduct includes, but is not limited to: offensive jokes or slurs, unwanted physical contact, sexual comments or images, intrusive questions about a person's private life, and retaliation against anyone who reports or participates in an investigation.

5. Reporting Channels

Employees who experience or witness harassment must report it as soon as possible. Reports can be made through any of the following channels: their line manager, the People team, the confidential HR hotline, or the dedicated reporting email address speaks-up@acme-corp.test.

6. Investigation Process

All reports are taken seriously and investigated promptly. Investigations are conducted confidentially to the extent possible. Initial feedback on the investigation is provided within 10 business days of the report being received.

7. No Retaliation

Acme Corp strictly prohibits retaliation against any employee who reports harassment in good faith or who participates in an investigation. Retaliation is itself a disciplinary offence that can result in termination.

8. Disciplinary Consequences

Employees found to have engaged in harassment will be subject to disciplinary action, up to and including termination of employment.
"""

CONFIDENTIALITY_POLICY = """
Confidentiality Policy

Effective Date: January 1, 2026

1. Purpose

Acme Corp employees frequently handle confidential and proprietary information. This policy describes how that information must be protected.

2. Types of Confidential Information

Confidential information includes trade secrets, source code, product roadmaps, financial data, customer and partner information, employee personal data, salary information and any information marked as confidential.

3. Data Classification

Information is classified as public, internal, confidential or restricted. Restricted information is the most sensitive and includes salary data, legal documents and personal data of employees and customers.

4. Handling and Storage

Confidential information must be stored only on approved corporate systems, which are protected by managed access controls. Personal devices must not be used to store restricted information.

5. Passwords and Access

Employees must use strong passphrases, enable multi-factor authentication on all corporate accounts and never share their credentials with anyone.

6. Sharing with Third Parties

Confidential information may be shared with third parties only under a signed non-disclosure agreement and with prior approval from the Legal team.

7. Remote Work

When working remotely, employees must use the corporate VPN, lock their screens when away and follow the Remote Work Policy.

8. Breach Reporting

Any actual or suspected loss, theft or disclosure of confidential information must be reported to the Security team within 24 hours. Employees who mishandle confidential information are subject to disciplinary action, up to and including termination.
"""


# --------------------------------------------------------------------------- #
# Minimal PDF builder (no third-party PDF library required)
# --------------------------------------------------------------------------- #
def _content_stream(lines: list[str], font_size: int = 10) -> bytes:
    escaped = [
        line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        for line in lines
    ]
    ops: list[str] = ["BT", f"/F1 {font_size} Tf", "72 720 Td"]
    for line in escaped:
        ops.append(f"({line}) Tj")
        ops.append("0 -14 Td")
    ops.append("ET")
    return "\n".join(ops).encode("latin-1", errors="replace")


def _build_pdf(pages: list[list[str]]) -> bytes:
    num_pages = len(pages)
    body = bytearray()
    offsets: list[int] = []

    def add_object(data: bytes) -> int:
        obj_num = len(offsets) + 1
        offsets.append(len(body))
        body.extend(f"{obj_num} 0 obj\n".encode("latin-1"))
        body.extend(data)
        body.extend(b"\nendobj\n")
        return obj_num

    add_object(b"<< /Type /Catalog /Pages 2 0 R >>")

    kids = " ".join(f"{3 + i} 0 R" for i in range(num_pages))
    add_object(
        f"<< /Type /Pages /Kids [{kids}] /Count {num_pages} >>".encode("latin-1")
    )

    first_content = 3 + num_pages
    font_obj = 3 + 2 * num_pages

    for i in range(num_pages):
        add_object(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Contents {first_content + i} 0 R "
                f"/Resources << /Font << /F1 {font_obj} 0 R >> >> >>"
            ).encode("latin-1")
        )

    for lines in pages:
        stream = _content_stream(lines)
        add_object(
            f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1")
            + stream
            + b"\nendstream"
        )

    add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    header = b"%PDF-1.4\n"
    xref_offset = len(header) + len(body)
    xref = f"xref\n0 {len(offsets) + 1}\n".encode("latin-1")
    xref += b"0000000000 65535 f \n"
    for offset in offsets:
        xref += f"{offset:010d} 00000 n \n".encode("latin-1")
    trailer = (
        f"trailer\n<< /Size {len(offsets) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode("latin-1")
    return header + bytes(body) + xref + trailer


def _lines_from_sections(width: int = 92) -> list[list[str]]:
    """Turn the handbook into pages of wrapped lines."""
    pages: list[list[str]] = [[]]
    for heading, paragraphs in HANDBOOK_SECTIONS:
        page = pages[-1]
        page.append("")
        page.extend(_wrap(heading, width))
        for paragraph in paragraphs:
            page.extend(_wrap(paragraph, width))
    return pages


def _wrap(text: str, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def build_pdf_output() -> bytes:
    return _build_pdf(_lines_from_sections())


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


_DOCX_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>
""".strip()

_DOCX_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
""".strip()

_DOCX_DOCUMENT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
""".strip()

_DOCX_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="22"/></w:rPr></w:rPrDefault></w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:keepLines/><w:spacing w:before="240" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr></w:style>
</w:styles>
""".strip()


def build_docx_output() -> bytes:
    """Build the DOCX handbook using only the Python standard library.

    Produces a valid OOXML package (zip of parts) that python-docx can open.
    """
    from io import BytesIO
    from zipfile import ZIP_DEFLATED, ZipFile

    def paragraph_xml(text: str, heading: bool = False) -> str:
        style = '<w:pPr><w:pStyle w:val="Heading1"/></w:pPr>' if heading else ""
        return (
            f"<w:p>{style}<w:r><w:t xml:space=\"preserve\">"
            f"{_xml_escape(text)}</w:t></w:r></w:p>"
        )

    body_parts: list[str] = []
    for heading, paragraphs in HANDBOOK_SECTIONS:
        body_parts.append(paragraph_xml(heading, heading=True))
        for paragraph in paragraphs:
            body_parts.append(paragraph_xml(paragraph))

    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{''.join(body_parts)}</w:body></w:document>"
    )

    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _DOCX_CONTENT_TYPES)
        archive.writestr("_rels/.rels", _DOCX_RELS)
        archive.writestr("word/document.xml", document_xml)
        archive.writestr("word/_rels/document.xml.rels", _DOCX_DOCUMENT_RELS)
        archive.writestr("word/styles.xml", _DOCX_STYLES)
    return buffer.getvalue()


def write_txt(name: str, content: str) -> Path:
    target = DOCS_DIR / name
    target.write_text(content.strip() + "\n", encoding="utf-8")
    return target


def main() -> int:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    (DOCS_DIR / "employee_handbook.pdf").write_bytes(build_pdf_output())
    (DOCS_DIR / "employee_handbook.docx").write_bytes(build_docx_output())

    write_txt("leave_policy.txt", LEAVE_POLICY)
    write_txt("remote_work_policy.txt", REMOTE_WORK_POLICY)
    write_txt("parental_leave_policy.txt", PARENTAL_LEAVE_POLICY)
    write_txt("code_of_conduct.txt", CODE_OF_CONDUCT)
    write_txt("workplace_harassment_policy.txt", HARASSMENT_POLICY)
    write_txt("confidentiality_policy.txt", CONFIDENTIALITY_POLICY)

    print(f"Sample documents written to {DOCS_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
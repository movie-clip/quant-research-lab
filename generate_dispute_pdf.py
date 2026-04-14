from pathlib import Path
import textwrap


OUTPUT = Path(r"C:/projects/investments/portfolio/dispute-letter.pdf")

LETTER_TEXT = """To: Banc Sabadell / Redsys Dispute Department
Date: April 12, 2026
Claim Reference: 1428834
Expediente: 206646525

Subject: Clarification and Documentation for Duplicate Transaction Claim

Dear Dispute Team,

I am writing in response to your documentation request regarding my claim for a duplicate charge at the merchant LE COQ LAS ROZAS on March 28, 2026.

I believe there is a misunderstanding in the specific documentation requested. Your email asks for a \"confirmation of reservation proving collection on the 3rd.\" However, this dispute does not involve a rental or a scheduled pickup. This was an in-person meal at a restaurant.

Reason for Dispute:
On March 28, 2026, I paid for a single meal at Le Coq Las Rozas. As shown in my previous evidence and your own records (Operation 206646525), I was charged 31.90 EUR at 13:56:52. A second, identical charge for 31.90 EUR was processed less than one minute later at 13:57. I did not place a second order; this is a clear technical duplication by the merchant's terminal.

Documentation Provided:

Bank Statement (Attached): Highlighting two identical charges from the same merchant within 60 seconds of each other.

Proof of Contact: I have previously provided a screenshot of the message sent to the merchant on March 30, 2026, requesting a refund for the error. The merchant has failed to respond.

Because this was a spontaneous restaurant visit, there is no \"reservation\" or \"collection date.\" The evidence of the duplication lies in the timestamp and identical amount of the two transactions.

I kindly ask you to proceed with the chargeback for the duplicate transaction (the one at 13:57) based on the evidence of the simultaneous billing error.

Kind regards,

Anton Ametov"""


def pdf_escape(value: str) -> str:
    return value.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def wrap_text(text: str, width: int = 92, lines_per_page: int = 48) -> list[list[str]]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        lines.extend(textwrap.wrap(paragraph, width=width, break_long_words=False, break_on_hyphens=False))
    return [lines[i : i + lines_per_page] for i in range(0, len(lines), lines_per_page)]


def build_pdf(text: str, output_path: Path) -> None:
    pages = wrap_text(text)
    objects: list[bytes] = []

    def add_object(body: str) -> int:
        objects.append(body.encode("latin-1"))
        return len(objects)

    font_id = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    pages_id = add_object("<< /Type /Pages /Count 0 /Kids [] >>")
    page_ids: list[int] = []

    for page_lines in pages:
        commands = ["BT", "/F1 12 Tf", "50 770 Td", "14 TL"]
        first_line = True
        for line in page_lines:
            if not first_line:
                commands.append("T*")
            commands.append(f"({pdf_escape(line)}) Tj")
            first_line = False
        commands.append("ET")
        stream = "\n".join(commands)
        content_id = add_object(f"<< /Length {len(stream.encode('latin-1'))} >>\nstream\n{stream}\nendstream")
        page_id = add_object(f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>")
        page_ids.append(page_id)

    objects[pages_id - 1] = f"<< /Type /Pages /Count {len(page_ids)} /Kids [{' '.join(f'{page_id} 0 R' for page_id in page_ids)}] >>".encode("latin-1")
    catalog_id = add_object(f"<< /Type /Catalog /Pages {pages_id} 0 R >>")

    raw = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(raw))
        raw.extend(f"{index} 0 obj\n".encode("latin-1"))
        raw.extend(body)
        raw.extend(b"\nendobj\n")

    xref_offset = len(raw)
    raw.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    raw.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        raw.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    raw.extend(f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("latin-1"))

    output_path.write_bytes(raw)


if __name__ == "__main__":
    build_pdf(LETTER_TEXT, OUTPUT)
    print(f"Wrote {OUTPUT}")

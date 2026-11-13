"""Sample data for demos. EVERYTHING here is illustrative: dates are generated
relative to today and eligibility ranges are simplified. Verify against the
official sources before relying on any of it. Records carry is_sample=1 so the
interface labels them."""
import uuid
from datetime import date, timedelta
from pathlib import Path

from flask import current_app

from .models import eligibility as rule_model
from .models import examination as exam_model
from .models import note as note_model


def make_pdf(title, lines):
    """Build a tiny valid one-page PDF (no external libraries)."""
    def esc(text):
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    parts = [f"BT /F1 18 Tf 72 740 Td ({esc(title)}) Tj ET"]
    y = 700
    for line in lines:
        parts.append(f"BT /F1 12 Tf 72 {y} Td ({esc(line)}) Tj ET")
        y -= 22
    stream = "\n".join(parts).encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref_at = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref_at)
    return bytes(out)


def _day(offset):
    return (date.today() + timedelta(days=offset)).isoformat()


def _exam(**kw):
    base = {
        "conducting_body": None, "description": None, "category": "Other", "board": "All",
        "medium": "All", "exam_date": None, "registration_start": None, "registration_end": None,
        "fee_info": None, "official_url": None, "link_last_checked": None,
        "is_sample": 1, "is_published": 1,
    }
    base.update(kw)
    return base


SAMPLE_NOTE = "SAMPLE DATA - illustrative only. Verify details on the official website."


def seed_sample_data():
    if exam_model.count() > 0:
        return False

    exams = {
        "nso": _exam(name="National Science Olympiad (NSO)", conducting_body="Science Olympiad Foundation",
                     category="Olympiad", description=f"{SAMPLE_NOTE} A school-level science olympiad.",
                     registration_start=_day(-10), registration_end=_day(25), exam_date=_day(60),
                     fee_info="Sample fee - verify", official_url="https://www.sofworld.org", medium="English"),
        "imo": _exam(name="International Mathematics Olympiad (IMO)", conducting_body="Science Olympiad Foundation",
                     category="Olympiad", description=f"{SAMPLE_NOTE} A school-level mathematics olympiad.",
                     registration_start=_day(15), registration_end=_day(45), exam_date=_day(80),
                     fee_info="Sample fee - verify", official_url="https://www.sofworld.org", medium="English"),
        "ntse": _exam(name="National Talent Search Examination (NTSE)", conducting_body="NCERT",
                      category="Talent Search", description=f"{SAMPLE_NOTE} A talent search and scholarship examination.",
                      exam_date=_day(120), official_url="https://ncert.nic.in"),
        "nmms": _exam(name="National Means-cum-Merit Scholarship (NMMS)", conducting_body="Ministry of Education / State agencies",
                      category="Scholarship", description=f"{SAMPLE_NOTE} A merit scholarship for students from families with limited income.",
                      registration_start=_day(-40), registration_end=_day(-5), exam_date=_day(30),
                      official_url="https://scholarships.gov.in", board="State Board"),
        "mhsch": _exam(name="Maharashtra Scholarship Examination (Std 5 and 8)", conducting_body="Maharashtra State Council of Examination, Pune",
                       category="Scholarship", board="State Board", medium="Marathi",
                       description=f"{SAMPLE_NOTE} State scholarship examination for upper-primary and secondary stages.",
                       registration_start=_day(-5), registration_end=_day(20), exam_date=_day(70),
                       official_url="https://www.mscepune.in"),
        "hb": _exam(name="Homi Bhabha Balvaidnyanik Competition", conducting_body="Mumbai Science Teachers' Association (verify)",
                    category="Talent Search", board="State Board", medium="Marathi",
                    description=f"{SAMPLE_NOTE} A science competition held in two stages of school."),
        "asset": _exam(name="ASSET Talent Search", conducting_body="Educational Initiatives (verify)",
                       category="Aptitude", description=f"{SAMPLE_NOTE} A skills and aptitude assessment."),
        "dts": _exam(name="Sample District Talent Search", conducting_body="Fictional body for demo",
                     category="Talent Search",
                     description=f"{SAMPLE_NOTE} Deliberately has NO eligibility data, to show the verification notice."),
        "ysq": _exam(name="Sample Young Scientist Quiz", conducting_body="Fictional body for demo",
                     category="Aptitude",
                     description=f"{SAMPLE_NOTE} Deliberately has an INCOMPLETE rule (no upper standard)."),
    }
    ids = {key: exam_model.create_exam(data) for key, data in exams.items()}

    rules = {
        "nso": [(1, 10, "Open to students of these standards (sample).")],
        "imo": [(1, 10, "Open to students of these standards (sample).")],
        "ntse": [(10, 10, "Students of Standard 10 (sample - confirm state-wise rules).")],
        "nmms": [(8, 8, "Standard 8 students meeting income and marks conditions (sample).")],
        "mhsch": [(5, 5, "Standard 5: upper primary scholarship stage (sample)."),
                  (8, 8, "Standard 8: secondary scholarship stage (sample).")],
        "hb": [(6, 6, "Standard 6: first stage (sample)."), (9, 9, "Standard 9: second stage (sample).")],
        "asset": [(3, 10, "Standards 3 to 10 (sample).")],
        "ysq": [(4, None, "Standard 4 and above - upper limit not recorded.")],
    }
    for key, entries in rules.items():
        for low, high, text in entries:
            rule_model.create_rule(ids[key], {
                "min_standard": low, "max_standard": high, "criteria_text": text,
                "source_note": "Sample data - not checked against the official notice.",
            })

    upload_dir = Path(current_app.config["UPLOAD_DIR"])
    upload_dir.mkdir(parents=True, exist_ok=True)

    notes = [
        ("nso", "Science", "Sample questions", "NSO Sample Questions - Standard 5", True, 0),
        ("imo", "Mathematics", "Number sense", "IMO Number Sense Workbook", False, 14900),
        ("ntse", "Mental Ability", "Reasoning", "NTSE Mental Ability Practice Set", False, 19900),
        ("ntse", "General", "Exam pattern", "NTSE Exam Pattern Guide", True, 0),
        ("nmms", "Mental Ability", "Series and analogy", "NMMS Mental Ability Notes", False, 9900),
        ("mhsch", "Mathematics", "Standard 8", "Scholarship Maths Revision - Standard 8", True, 0),
        (None, "General", "Study skills", "How to Prepare for Competitive Exams", True, 0),
    ]
    for key, subject, topic, title, free, price in notes:
        stored = f"{uuid.uuid4().hex}.pdf"
        (upload_dir / stored).write_bytes(make_pdf(title, [
            "SAMPLE STUDY NOTE - generated for demonstration.",
            f"Subject: {subject}    Topic: {topic}",
            "Replace this file from the Administrator panel with real material.",
        ]))
        note_model.create_note({
            "exam_id": ids[key] if key else None, "subject": subject, "topic": topic, "title": title,
            "description": f"{SAMPLE_NOTE} Short preview text students can read before buying.",
            "is_free": 1 if free else 0, "price_paise": price, "is_published": 1, "is_sample": 1,
        }, stored, f"{title.replace(' ', '_')}.pdf")
    return True

# apps/reports/renderers.py
import csv
import io
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet


def _format_dt(dt):
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M")


def _format_date(d):
    if d is None:
        return ""
    return str(d)


# ------------------------------------------------------------------ #
#  CSV                                                                 #
# ------------------------------------------------------------------ #

def render_employee_csv(report):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Employee ID", "Full Name", "Date",
        "Clock In", "Clock Out", "Hours Worked", "Status"
    ])
    for entry in report["attendance"]:
        writer.writerow([
            report["erpnext_employee_id"],
            report["full_name"],
            _format_date(entry["date"]),
            _format_dt(entry["clock_in"]),
            _format_dt(entry["clock_out"]),
            entry["hours_worked"] or "",
            entry["status"],
        ])
    response = HttpResponse(output.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="report_{report["erpnext_employee_id"]}.csv"'
    )
    return response


def render_company_csv(report):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Employee ID", "Full Name", "Date",
        "Clock In", "Clock Out", "Hours Worked", "Status"
    ])
    for emp in report["employees"]:
        for entry in emp["attendance"]:
            writer.writerow([
                emp["erpnext_employee_id"],
                emp["full_name"],
                _format_date(entry["date"]),
                _format_dt(entry["clock_in"]),
                _format_dt(entry["clock_out"]),
                entry["hours_worked"] or "",
                entry["status"],
            ])
    response = HttpResponse(output.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="company_report_{report["company"]}.csv"'
    )
    return response


# ------------------------------------------------------------------ #
#  PDF                                                                 #
# ------------------------------------------------------------------ #

def _build_attendance_table(entries, employee_id, full_name):
    styles = getSampleStyleSheet()
    elements = []
    elements.append(Paragraph(f"{full_name} ({employee_id})", styles["Heading2"]))
    elements.append(Spacer(1, 6))

    data = [["Date", "Clock In", "Clock Out", "Hours", "Status"]]
    for entry in entries:
        data.append([
            _format_date(entry["date"]),
            _format_dt(entry["clock_in"]),
            _format_dt(entry["clock_out"]),
            entry["hours_worked"] or "—",
            entry["status"],
        ])

    table = Table(data, colWidths=[80, 110, 110, 60, 90])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 12))
    return elements


def render_employee_pdf(report):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Attendance Report", styles["Title"]))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        f"Period: {report['date_from'] or 'All'} → {report['date_to'] or 'All'}",
        styles["Normal"]
    ))
    elements.append(Paragraph(
        f"Total Days Present: {report['total_days_present']} | "
        f"Total Hours: {report['total_hours_worked']}",
        styles["Normal"]
    ))
    elements.append(Spacer(1, 12))
    elements.extend(_build_attendance_table(
        report["attendance"],
        report["erpnext_employee_id"],
        report["full_name"],
    ))

    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="report_{report["erpnext_employee_id"]}.pdf"'
    )
    return response


def render_company_pdf(report):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(f"Company Attendance Report — {report['company']}", styles["Title"]))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        f"Period: {report['date_from'] or 'All'} → {report['date_to'] or 'All'}",
        styles["Normal"]
    ))
    elements.append(Paragraph(
        f"Company Total Hours: {report['company_total_hours_worked']}",
        styles["Normal"]
    ))
    elements.append(Spacer(1, 12))

    for emp in report["employees"]:
        elements.extend(_build_attendance_table(
            emp["attendance"],
            emp["erpnext_employee_id"],
            emp["full_name"],
        ))

    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="company_report_{report["company"]}.pdf"'
    )
    return response
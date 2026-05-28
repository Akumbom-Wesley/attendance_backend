# apps/reports/services.py
from datetime import date, timedelta
from apps.checkins.models import CheckinRecord
from apps.employees.models import Employee


def _pair_records(records):
    """
    Walk a list of CheckinRecords sorted by timestamp_gps ascending.
    Returns a list of attendance entry dicts.
    """
    entries = []
    pending_in = None

    for record in records:
        if record.log_type == "IN":
            if pending_in is not None:
                # Consecutive INs — close previous as INCOMPLETE
                entries.append({
                    "date": pending_in.timestamp_gps.date(),
                    "clock_in": pending_in.timestamp_gps,
                    "clock_out": None,
                    "hours_worked": None,
                    "status": "INCOMPLETE",
                })
            pending_in = record
        elif record.log_type == "OUT":
            if pending_in is not None:
                delta = record.timestamp_gps - pending_in.timestamp_gps
                total_seconds = int(delta.total_seconds())
                hours, remainder = divmod(total_seconds, 3600)
                minutes = remainder // 60
                entries.append({
                    "date": pending_in.timestamp_gps.date(),
                    "clock_in": pending_in.timestamp_gps,
                    "clock_out": record.timestamp_gps,
                    "hours_worked": f"{hours}:{minutes:02d}",
                    "status": "COMPLETE",
                })
                pending_in = None
            else:
                entries.append({
                    "date": record.timestamp_gps.date(),
                    "clock_in": None,
                    "clock_out": record.timestamp_gps,
                    "hours_worked": None,
                    "status": "OUT_ONLY",
                })

    # Close any trailing pending IN
    if pending_in is not None:
        entries.append({
            "date": pending_in.timestamp_gps.date(),
            "clock_in": pending_in.timestamp_gps,
            "clock_out": None,
            "hours_worked": None,
            "status": "INCOMPLETE",
        })

    return entries


def _total_hours(entries):
    total_minutes = 0
    for e in entries:
        if e["hours_worked"]:
            h, m = e["hours_worked"].split(":")
            total_minutes += int(h) * 60 + int(m)
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}:{minutes:02d}"


def _get_records(employee, date_from, date_to):
    qs = CheckinRecord.objects.filter(
        device_binding__employee=employee,
    ).order_by("timestamp_gps")
    if date_from:
        qs = qs.filter(timestamp_gps__date__gte=date_from)
    if date_to:
        qs = qs.filter(timestamp_gps__date__lte=date_to)
    return qs


def build_employee_report(employee, date_from=None, date_to=None):
    records = _get_records(employee, date_from, date_to)
    entries = _pair_records(list(records))
    complete = [e for e in entries if e["status"] == "COMPLETE"]
    return {
        "erpnext_employee_id": employee.erpnext_employee_id,
        "full_name": employee.full_name,
        "date_from": date_from,
        "date_to": date_to,
        "total_days_present": len(complete),
        "total_hours_worked": _total_hours(complete),
        "attendance": entries,
    }


def build_company_report(company, date_from=None, date_to=None):
    employees = Employee.objects.filter(company=company, is_active=True)
    employee_reports = [
        build_employee_report(emp, date_from, date_to)
        for emp in employees
    ]
    all_complete = [
        e
        for r in employee_reports
        for e in r["attendance"]
        if e["status"] == "COMPLETE"
    ]
    return {
        "company": company.name,
        "date_from": date_from,
        "date_to": date_to,
        "company_total_hours_worked": _total_hours(all_complete),
        "employees": employee_reports,
    }
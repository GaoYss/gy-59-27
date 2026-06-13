from datetime import date, datetime, timedelta

from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models import Appointment, Rule, Waitlist

appointments_bp = Blueprint("appointments", __name__, url_prefix="/api/appointments")


def parse_exam_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def get_daily_appointment_count(subject, exam_date):
    return Appointment.query.filter(
        Appointment.subject == subject,
        Appointment.exam_date == exam_date,
        Appointment.status.in_(["已预约", "已确认"]),
    ).count()


def validate_appointment(payload, for_waitlist=False):
    required = ["studentName", "idNumber", "subject", "examDate", "timeslot"]
    missing = [field for field in required if not payload.get(field)]
    if missing:
        return f"缺少字段：{', '.join(missing)}", None

    exam_date = parse_exam_date(payload.get("examDate"))
    if not exam_date:
        return "考试日期格式应为 YYYY-MM-DD", None
    if exam_date < date.today():
        return "不能预约过去日期", None

    rule = Rule.query.filter_by(subject=payload["subject"]).first()
    if not rule or not rule.enabled:
        return "该科目暂未开放预约", None
    if exam_date.weekday() >= 5 and not rule.allow_weekend:
        return "该科目规则不允许周末预约", None

    daily_count = get_daily_appointment_count(payload["subject"], exam_date)
    if not for_waitlist and daily_count >= rule.max_daily_slots:
        return "当日该科目预约名额已满", None

    earliest_date = date.today() + timedelta(days=rule.min_interval_days)
    if exam_date < earliest_date:
        return f"该科目需至少提前 {rule.min_interval_days} 天预约", None

    active = Appointment.query.filter(
        Appointment.id_number == payload["idNumber"],
        Appointment.subject == payload["subject"],
        Appointment.status.in_(["已预约", "已确认"]),
    ).first()
    if active:
        return "该学员已有同科目有效预约", None

    waitlist_active = Waitlist.query.filter(
        Waitlist.id_number == payload["idNumber"],
        Waitlist.subject == payload["subject"],
        Waitlist.status == "候补中",
    ).first()
    if waitlist_active:
        return "该学员已在同科目候补队列中", None

    return None, exam_date


def update_waitlist_positions(subject, exam_date):
    waitlist_items = Waitlist.query.filter(
        Waitlist.subject == subject,
        Waitlist.exam_date == exam_date,
        Waitlist.status == "候补中",
    ).order_by(Waitlist.created_at.asc()).all()
    for idx, item in enumerate(waitlist_items, start=1):
        item.position = idx


def try_fill_from_waitlist(subject, exam_date):
    rule = Rule.query.filter_by(subject=subject).first()
    if not rule:
        return None

    daily_count = get_daily_appointment_count(subject, exam_date)
    if daily_count >= rule.max_daily_slots:
        return None

    waitlist_item = Waitlist.query.filter(
        Waitlist.subject == subject,
        Waitlist.exam_date == exam_date,
        Waitlist.status == "候补中",
    ).order_by(Waitlist.created_at.asc()).first()

    if not waitlist_item:
        return None

    appointment = Appointment(
        student_name=waitlist_item.student_name,
        id_number=waitlist_item.id_number,
        subject=waitlist_item.subject,
        exam_date=waitlist_item.exam_date,
        timeslot=waitlist_item.timeslot,
        status="已预约",
    )
    db.session.add(appointment)

    waitlist_item.status = "已补位"
    waitlist_item.notified = True

    update_waitlist_positions(subject, exam_date)
    db.session.commit()

    return appointment


@appointments_bp.get("")
def list_appointments():
    subject = request.args.get("subject")
    status = request.args.get("status")
    query = Appointment.query.order_by(Appointment.exam_date.asc(), Appointment.timeslot.asc())
    if subject:
        query = query.filter_by(subject=subject)
    if status:
        query = query.filter_by(status=status)
    return jsonify([item.to_dict() for item in query.all()])


@appointments_bp.get("/waitlist")
def list_waitlist():
    subject = request.args.get("subject")
    status = request.args.get("status")
    query = Waitlist.query.order_by(Waitlist.exam_date.asc(), Waitlist.position.asc())
    if subject:
        query = query.filter_by(subject=subject)
    if status:
        query = query.filter_by(status=status)
    return jsonify([item.to_dict() for item in query.all()])


@appointments_bp.post("/waitlist")
def create_waitlist():
    payload = request.get_json() or {}
    error, exam_date = validate_appointment(payload, for_waitlist=True)
    if error:
        return jsonify({"message": error}), 400

    rule = Rule.query.filter_by(subject=payload["subject"]).first()
    daily_count = get_daily_appointment_count(payload["subject"], exam_date)
    if daily_count < rule.max_daily_slots:
        return jsonify({"message": "当前仍有名额，请直接预约"}), 400

    waitlist_count = Waitlist.query.filter(
        Waitlist.subject == payload["subject"],
        Waitlist.exam_date == exam_date,
        Waitlist.status == "候补中",
    ).count()

    waitlist = Waitlist(
        student_name=payload["studentName"].strip(),
        id_number=payload["idNumber"].strip(),
        subject=payload["subject"],
        exam_date=exam_date,
        timeslot=payload["timeslot"],
        status="候补中",
        position=waitlist_count + 1,
    )
    db.session.add(waitlist)
    db.session.commit()
    return jsonify(waitlist.to_dict()), 201


@appointments_bp.patch("/waitlist/<int:waitlist_id>")
def update_waitlist_status(waitlist_id):
    waitlist = Waitlist.query.get_or_404(waitlist_id)
    payload = request.get_json() or {}
    status = payload.get("status")
    if status not in ["候补中", "已补位", "已取消"]:
        return jsonify({"message": "无效候补状态"}), 400
    waitlist.status = status
    update_waitlist_positions(waitlist.subject, waitlist.exam_date)
    db.session.commit()
    return jsonify(waitlist.to_dict())


@appointments_bp.post("")
def create_appointment():
    payload = request.get_json() or {}
    error, exam_date = validate_appointment(payload)
    if error:
        return jsonify({"message": error}), 400

    appointment = Appointment(
        student_name=payload["studentName"].strip(),
        id_number=payload["idNumber"].strip(),
        subject=payload["subject"],
        exam_date=exam_date,
        timeslot=payload["timeslot"],
        status="已预约",
    )
    db.session.add(appointment)
    db.session.commit()
    return jsonify(appointment.to_dict()), 201


@appointments_bp.patch("/<int:appointment_id>")
def update_appointment_status(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    payload = request.get_json() or {}
    status = payload.get("status")
    if status not in ["已预约", "已确认", "已取消", "已完成"]:
        return jsonify({"message": "无效预约状态"}), 400

    was_active = appointment.status in ["已预约", "已确认"]
    appointment.status = status
    db.session.flush()

    filled_appointment = None
    if was_active and status == "已取消":
        filled = try_fill_from_waitlist(appointment.subject, appointment.exam_date)
        if filled:
            filled_appointment = filled

    db.session.commit()

    result = appointment.to_dict()
    if filled_appointment:
        result["filledFromWaitlist"] = filled_appointment.to_dict()
    return jsonify(result)

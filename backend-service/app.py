import os
import random
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import jwt
from flask import Flask, jsonify, request
from pymongo import MongoClient, ReturnDocument

app = Flask(__name__)
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "180"))
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017/bowling")

mongo_client = MongoClient(MONGO_URL)
mongo_db = mongo_client.get_default_database()
if mongo_db is None:
    mongo_db = mongo_client["bowling"]
users_col = mongo_db["users"]
reservations_col = mongo_db["reservations"]
counters_col = mongo_db["counters"]

ADMIN_USERS = [
    {"name": "Yama Admin", "email": "yama@admin", "password": "akuyama", "role": "admin"},
]

LANES = [f"Lane {i}" for i in range(1, 9)]
TIME_SLOTS = [
    "10:00",
    "11:00",
    "12:00",
    "13:00",
    "14:00",
    "15:00",
    "16:00",
    "17:00",
    "18:00",
    "19:00",
    "20:00",
]

RATE_PER_HOUR = 50000
EXTRA_PER_PERSON = 25000
INCLUDED_PLAYERS = 2


def ensure_indexes():
    users_col.create_index("email", unique=True)
    reservations_col.create_index("date")
    reservations_col.create_index("lane")
    reservations_col.create_index("customer_email")


def ensure_admin_users():
    for admin in ADMIN_USERS:
        admin_doc = {
            "name": admin["name"],
            "email": admin["email"].lower(),
            "password": admin["password"],
            "role": "admin",
        }
        users_col.update_one(
            {"email": admin_doc["email"]},
            {"$set": admin_doc},
            upsert=True,
        )


def get_next_sequence(name: str) -> int:
    doc = counters_col.find_one_and_update(
        {"_id": name},
        {"$inc": {"value": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int(doc["value"])


def create_token(user: Dict) -> str:
    payload = {
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
        "exp": datetime.now(timezone.utc).timestamp() + JWT_EXPIRE_MINUTES * 60,
        "iat": datetime.now(timezone.utc).timestamp(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> Optional[Dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None


def find_user(email: str) -> Optional[Dict]:
    return users_col.find_one({"email": email.lower()}, {"_id": 0})


def is_admin(user: Dict) -> bool:
    return user.get("role") == "admin"


def require_auth():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ", 1)[1]
    return decode_token(token)


def parse_date(date_str: str):
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def time_to_minutes(time_str: str) -> int:
    h, m = time_str.split(":")
    return int(h) * 60 + int(m)


def add_hours(time_str: str, hours: int) -> str:
    start_minutes = time_to_minutes(time_str)
    end_minutes = start_minutes + hours * 60
    end_h = (end_minutes // 60)
    end_m = end_minutes % 60
    return f"{end_h:02d}:{end_m:02d}"


def intervals_overlap(start1: str, dur1: int, start2: str, dur2: int) -> bool:
    s1 = time_to_minutes(start1)
    e1 = s1 + dur1 * 60
    s2 = time_to_minutes(start2)
    e2 = s2 + dur2 * 60
    return not (e1 <= s2 or e2 <= s1)


def has_conflict(date: str, start_time: str, duration_hours: int, lane: str, exclude_id: Optional[int] = None) -> bool:
    query = {"date": date, "lane": lane}
    for r in reservations_col.find(query, {"_id": 0}):
        if exclude_id and r.get("id") == exclude_id:
            continue
        if intervals_overlap(start_time, duration_hours, r["start_time"], r["duration_hours"]):
            return True
    return False


def serialize_reservation(reservation: Dict) -> Dict:
    reservation.pop("_id", None)
    return reservation


def fetch_reservations(query: Dict) -> List[Dict]:
    cursor = reservations_col.find(query).sort([("date", 1), ("start_time", 1), ("lane", 1)])
    return [serialize_reservation(r) for r in cursor]


def seed_dummy_reservations():
    if reservations_col.count_documents({}) > 0:
        return

    rng = random.Random(int(os.getenv("DUMMY_SEED", "20240101")))
    target_count = int(os.getenv("DUMMY_COUNT", "18"))
    base_date = datetime.now(timezone.utc).date().isoformat()

    names = [
        "Ari Pratama",
        "Nia Kartika",
        "Rizky Ramadhan",
        "Salsa Dwi",
        "Dito Mahendra",
        "Putri Ayu",
        "Fajar Hidayat",
        "Maya Sari",
        "Dimas Saputra",
        "Lia Oktaviani",
    ]
    notes_pool = [
        "",
        "Booking latihan 2 jam",
        "Main bareng kantor",
        "Butuh 2 jam, lane bersebelahan",
        "Sesi malam setelah jam 18",
        "Reservasi untuk 4 orang",
    ]
    email_pool = [
        "demo1@bowling.local",
        "demo2@bowling.local",
        "demo3@bowling.local",
        "demo4@bowling.local",
    ]

    reservations: List[Dict] = []
    attempts = 0
    max_attempts = target_count * 10
    while len(reservations) < target_count and attempts < max_attempts:
        attempts += 1
        lane = rng.choice(LANES)
        start_time = rng.choice(TIME_SLOTS)
        duration_hours = rng.choice([1, 2, 3])

        if has_conflict(base_date, start_time, duration_hours, lane):
            continue

        players = rng.randint(2, 6)
        extra_players = max(players - INCLUDED_PLAYERS, 0)
        total_cost = RATE_PER_HOUR * duration_hours + EXTRA_PER_PERSON * extra_players

        phone = f"08{rng.randint(1111, 9999)}{rng.randint(1111, 9999)}"
        reservations.append(
            {
                "id": get_next_sequence("reservation_id"),
                "name": rng.choice(names),
                "phone": phone,
                "date": base_date,
                "start_time": start_time,
                "end_time": add_hours(start_time, duration_hours),
                "duration_hours": duration_hours,
                "lane": lane,
                "players": players,
                "notes": rng.choice(notes_pool),
                "total_cost": total_cost,
                "customer_email": rng.choice(email_pool),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    if reservations:
        reservations_col.insert_many(reservations)


def initialize_storage():
    ensure_indexes()
    ensure_admin_users()
    seed_dummy_reservations()


initialize_storage()


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = find_user(email)
    if user and user.get("password") == password:
        token = create_token(user)
        if isinstance(token, bytes):
            token = token.decode("utf-8")
        public_info = {k: user[k] for k in ("name", "email", "role")}
        return jsonify({"status": "success", "user": public_info, "token": token})

    return jsonify({"status": "error", "message": "Kredensial tidak valid"}), 401


@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not all([name, email, password]):
        return jsonify({"status": "error", "message": "Nama, email, dan password wajib diisi."}), 400
    if find_user(email):
        return jsonify({"status": "error", "message": "Email sudah terdaftar."}), 400

    user = {"name": name, "email": email, "password": password, "role": "customer"}
    users_col.insert_one(user)
    return jsonify({"status": "success", "user": {"name": name, "email": email, "role": "customer"}})


@app.route("/api/reservations", methods=["GET"])
def list_reservations():
    auth = require_auth()
    date_filter = request.args.get("date")
    scope = (request.args.get("scope") or "").strip().lower()

    query: Dict = {}
    if date_filter:
        try:
            parse_date(date_filter)
        except ValueError:
            return jsonify({"status": "error", "message": "Format tanggal harus YYYY-MM-DD"}), 400
        query["date"] = date_filter

    if scope == "all":
        return jsonify(fetch_reservations(query))

    if not auth:
        return jsonify(fetch_reservations(query))

    role = auth.get("role")
    email = auth.get("email")
    if role != "admin":
        query["customer_email"] = email

    return jsonify(fetch_reservations(query))


@app.route("/api/reservations", methods=["POST"])
def create_reservation():
    auth = require_auth()
    if not auth:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    role = auth.get("role")
    auth_name = auth.get("name")
    auth_email = auth.get("email")

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()
    date = (data.get("date") or "").strip()
    start_time = (data.get("time") or data.get("start_time") or "").strip()
    duration_hours = int(data.get("duration_hours") or 0)
    lane = (data.get("lane") or "").strip()
    players = int(data.get("players") or 0)
    notes = (data.get("notes") or "").strip()

    customer_email = data.get("customer_email", "").strip().lower() or None
    if role == "customer":
        name = auth_name
        customer_email = auth_email

    if not all([name, phone, date, start_time, lane]) or players <= 0 or duration_hours <= 0:
        return jsonify({"status": "error", "message": "Nama, kontak, tanggal, jam, durasi, lane, dan jumlah pemain wajib diisi."}), 400

    if lane not in LANES:
        return jsonify({"status": "error", "message": "Lane tidak valid."}), 400
    if start_time not in TIME_SLOTS:
        return jsonify({"status": "error", "message": "Slot waktu tidak valid."}), 400
    if duration_hours not in {1, 2, 3}:
        return jsonify({"status": "error", "message": "Durasi hanya boleh 1-3 jam."}), 400
    try:
        parse_date(date)
    except ValueError:
        return jsonify({"status": "error", "message": "Format tanggal harus YYYY-MM-DD."}), 400

    end_time = add_hours(start_time, duration_hours)

    if has_conflict(date, start_time, duration_hours, lane):
        return jsonify({"status": "error", "message": "Slot sudah dipesan. Pilih jam atau lane lain."}), 409

    extra_players = max(players - INCLUDED_PLAYERS, 0)
    total_cost = RATE_PER_HOUR * duration_hours + EXTRA_PER_PERSON * extra_players

    new_res = {
        "id": get_next_sequence("reservation_id"),
        "name": name,
        "phone": phone,
        "date": date,
        "start_time": start_time,
        "end_time": end_time,
        "duration_hours": duration_hours,
        "lane": lane,
        "players": players,
        "notes": notes,
        "total_cost": total_cost,
        "customer_email": customer_email,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    reservations_col.insert_one(new_res)
    return jsonify({"status": "success", "reservation": new_res})


@app.route("/api/reservations/<int:res_id>", methods=["DELETE"])
def delete_reservation(res_id: int):
    auth = require_auth()
    if not auth:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    role = auth.get("role")
    email = auth.get("email")

    reservation = reservations_col.find_one({"id": res_id})
    if not reservation:
        return jsonify({"status": "error", "message": "Reservasi tidak ditemukan."}), 404

    if role != "admin" and reservation.get("customer_email") != email:
        return jsonify({"status": "error", "message": "Forbidden"}), 403

    reservations_col.delete_one({"id": res_id})
    return jsonify({"status": "success"})


@app.route("/api/meta", methods=["GET"])
def meta():
    return jsonify(
        {
            "lanes": LANES,
            "slots": TIME_SLOTS,
            "rate_per_hour": RATE_PER_HOUR,
            "extra_per_person": EXTRA_PER_PERSON,
            "included_players": INCLUDED_PLAYERS,
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

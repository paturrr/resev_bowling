import itertools
from datetime import datetime
from typing import Dict, List

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

# In-memory store for demo purposes; replace with DB in production
reservation_id = itertools.count(1)
reservations: List[Dict] = []

LANES = [f"Lane {i}" for i in range(1, 9)]
TIME_SLOTS = [
    "10:00", "11:00", "12:00", "13:00",
    "14:00", "15:00", "16:00", "17:00",
    "18:00", "19:00", "20:00", "21:00",
]


def parse_date(date_str: str) -> datetime.date:
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def is_conflict(date: str, time: str, lane: str, exclude_id: int = None) -> bool:
    for r in reservations:
        if exclude_id and r["id"] == exclude_id:
            continue
        if r["date"] == date and r["time"] == time and r["lane"] == lane:
            return True
    return False


@app.route("/")
def home():
    return render_template(
        "index.html",
        lanes=LANES,
        slots=TIME_SLOTS,
    )


@app.route("/api/reservations", methods=["GET"])
def list_reservations():
    date = request.args.get("date")
    if date:
        try:
            parse_date(date)
        except ValueError:
            return jsonify({"status": "error", "message": "Format tanggal tidak valid (YYYY-MM-DD)."}), 400
        filtered = [r for r in reservations if r["date"] == date]
        return jsonify(filtered)
    return jsonify(reservations)


@app.route("/api/reservations", methods=["POST"])
def create_reservation():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()
    date = (data.get("date") or "").strip()
    time = (data.get("time") or "").strip()
    lane = (data.get("lane") or "").strip()
    players = int(data.get("players") or 0)

    if not all([name, phone, date, time, lane]) or players <= 0:
        return jsonify({"status": "error", "message": "Nama, kontak, tanggal, jam, lane, dan jumlah pemain wajib diisi."}), 400
    if lane not in LANES:
        return jsonify({"status": "error", "message": "Lane tidak valid."}), 400
    if time not in TIME_SLOTS:
        return jsonify({"status": "error", "message": "Slot waktu tidak valid."}), 400
    try:
        parse_date(date)
    except ValueError:
        return jsonify({"status": "error", "message": "Format tanggal harus YYYY-MM-DD."}), 400
    if is_conflict(date, time, lane):
        return jsonify({"status": "error", "message": "Slot sudah dipesan. Pilih jam atau lane lain."}), 409

    new_res = {
        "id": next(reservation_id),
        "name": name,
        "phone": phone,
        "date": date,
        "time": time,
        "lane": lane,
        "players": players,
        "notes": (data.get("notes") or "").strip(),
    }
    reservations.append(new_res)
    return jsonify({"status": "success", "reservation": new_res})


@app.route("/api/reservations/<int:res_id>", methods=["DELETE"])
def cancel_reservation(res_id: int):
    for i, r in enumerate(reservations):
        if r["id"] == res_id:
            reservations.pop(i)
            return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Reservasi tidak ditemukan."}), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

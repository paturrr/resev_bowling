import os
from typing import Any, Dict, Optional

import requests
from flask import Flask, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend-service:5000")


def current_user() -> Optional[Dict[str, Any]]:
    return session.get("user")


def token() -> Optional[str]:
    return session.get("token")


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    info = request.args.get("info")
    if current_user():
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        try:
            resp = requests.post(
                f"{BACKEND_URL}/api/login",
                json={"email": email, "password": password},
                timeout=5,
            )
        except requests.RequestException:
            error = "Tidak dapat terhubung ke backend."
        else:
            data = resp.json()
            if resp.ok and data.get("status") == "success":
                session["user"] = data.get("user")
                session["token"] = data.get("token")
                return redirect(url_for("dashboard"))
            error = data.get("message", "Login gagal.")

    return render_template("login.html", error=error, info=info)


@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if current_user():
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        try:
            resp = requests.post(
                f"{BACKEND_URL}/api/register",
                json={"name": name, "email": email, "password": password},
                timeout=5,
            )
        except requests.RequestException:
            error = "Tidak dapat terhubung ke backend."
        else:
            data = resp.json()
            if resp.ok and data.get("status") == "success":
                return redirect(url_for("login", info="Registrasi berhasil, silakan masuk."))
            error = data.get("message", "Registrasi gagal.")

    return render_template("register.html", error=error)


@app.route("/logout")
def logout():
    session.pop("user", None)
    session.pop("token", None)
    return redirect(url_for("dashboard"))


@app.route("/", methods=["GET", "POST"])
def dashboard():
    user = current_user()
    message = None
    error = None
    is_authenticated = bool(user)
    is_admin = user.get("role") == "admin" if user else False
    message = session.pop("flash_message", None)
    error = session.pop("flash_error", None)

    if request.method == "POST":
        if not user:
            return redirect(url_for("login", info="Silakan login untuk membuat reservasi."))
        form_type = request.form.get("form_type")

        if form_type == "create_reservation":
            payload = {
                "name": user.get("name") if user.get("role") == "customer" else request.form.get("name"),
                "phone": request.form.get("phone"),
                "date": request.form.get("date"),
                "time": request.form.get("time"),
                "duration_hours": request.form.get("duration_hours"),
                "lane": request.form.get("lane"),
                "players": request.form.get("players"),
                "notes": request.form.get("notes"),
            }
            try:
                resp = requests.post(
                    f"{BACKEND_URL}/api/reservations",
                    json=payload,
                    headers={"Authorization": f"Bearer {token()}"},
                    timeout=5,
                )
                data = resp.json()
                if resp.ok:
                    session["flash_message"] = "Reservasi berhasil disimpan."
                else:
                    session["flash_error"] = data.get("message", "Gagal menyimpan reservasi.")
            except requests.RequestException:
                session["flash_error"] = "Tidak dapat terhubung ke backend."
            return redirect(url_for("dashboard"))

        elif form_type == "delete_reservation":
            res_id = request.form.get("res_id")
            if res_id:
                try:
                    resp = requests.delete(
                        f"{BACKEND_URL}/api/reservations/{res_id}",
                        headers={"Authorization": f"Bearer {token()}"},
                        timeout=5,
                    )
                    data = resp.json()
                    if resp.ok:
                        session["flash_message"] = "Reservasi dibatalkan."
                    else:
                        session["flash_error"] = data.get("message", "Gagal membatalkan.")
                except requests.RequestException:
                    session["flash_error"] = "Tidak dapat terhubung ke backend."
            return redirect(url_for("dashboard"))

    lanes = []
    slots = []
    meta_rate_per_hour = 50000
    meta_extra_per_person = 25000
    meta_included_players = 2
    reservations = []
    reservations_view = []
    date_filter = request.args.get("date") or request.form.get("filter_date")

    try:
        meta_resp = requests.get(f"{BACKEND_URL}/api/meta", timeout=5)
        if meta_resp.ok:
            meta = meta_resp.json()
            lanes = meta.get("lanes", [])
            slots = meta.get("slots", [])
            meta_rate_per_hour = meta.get("rate_per_hour", meta_rate_per_hour)
            meta_extra_per_person = meta.get("extra_per_person", meta_extra_per_person)
            meta_included_players = meta.get("included_players", meta_included_players)
    except requests.RequestException:
        error = error or "Tidak dapat memuat data lane/slot."

    try:
        params = {"scope": "all"}
        if date_filter:
            params["date"] = date_filter
        headers = {"Authorization": f"Bearer {token()}"} if token() else {}
        resp = requests.get(
            f"{BACKEND_URL}/api/reservations",
            params=params,
            headers=headers,
            timeout=5,
        )
        if resp.ok:
            reservations = resp.json()
    except requests.RequestException:
        if user:
            error = error or "Tidak dapat memuat data reservasi."

    if is_admin:
        reservations_view = reservations
    elif user:
        reservations_view = [r for r in reservations if r.get("customer_email") == user.get("email")]
    else:
        reservations_view = reservations

    return render_template(
        "dashboard.html",
        user=user,
        message=message,
        error=error,
        lanes=lanes,
        slots=slots,
        reservations=reservations,
        reservations_view=reservations_view,
        date_filter=date_filter,
        meta_rate_per_hour=meta_rate_per_hour,
        meta_extra_per_person=meta_extra_per_person,
        meta_included_players=meta_included_players,
        is_admin=is_admin,
        is_authenticated=is_authenticated,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

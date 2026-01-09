# Reservasi Bowling

Project ini berisi dua service sederhana:
- `backend-service`: API + data in-memory.
- `frontend-service`: UI Flask yang memanggil backend.

## Cara menjalankan
1. Jalankan docker compose:
   ```bash
   docker-compose up --build
   ```
2. Buka UI:
   - UI (frontend): `http://127.0.0.1:6001`
   - API (backend): `http://127.0.0.1:6000`
    - MongoDB: `mongodb://127.0.0.1:27017` (opsional jika ingin inspeksi)

## Akun admin
- Email: `yama@admin`
- Password: `akuyama`

## Alur penggunaan singkat
- Halaman awal langsung masuk ke dashboard.
- Guest (belum login):
  - Bisa melihat ketersediaan lane (warna merah = sudah terisi).
  - Tidak bisa mengisi form reservasi.
- User login:
  - Bisa membuat reservasi.
  - Melihat history pemesanannya sendiri (tanpa nama/kontak orang lain).
- Admin:
  - Melihat seluruh daftar reservasi lengkap dan bisa membatalkan.

## Dummy data
- Dummy reservasi otomatis dibuat saat backend start.
- Dummy hanya untuk tanggal hari ini.
- Data disimpan di MongoDB, jadi tetap ada selama volume `mongo_data` tidak dihapus.

Opsional environment variable:
- `DUMMY_COUNT` jumlah dummy (default 18).
- `DUMMY_SEED` seed random untuk pola dummy (default 20240101).

## Database (MongoDB)
- Service MongoDB berjalan lewat docker-compose (`mongodb`).
- URI default backend: `mongodb://mongodb:27017/bowling`.
- Untuk reset data: stop compose lalu hapus volume `mongo_data`.

### Struktur data singkat
- Database: `bowling`
- Collections:
  - `users`: akun admin + customer
  - `reservations`: semua booking
  - `counters`: auto-increment sederhana untuk `reservation_id`

### Contoh dokumen
`users`
```json
{
  "name": "Yama Admin",
  "email": "yama@admin",
  "password": "akuyama",
  "role": "admin"
}
```

`reservations`
```json
{
  "id": 1,
  "name": "Ari Pratama",
  "phone": "081234567890",
  "date": "2026-01-09",
  "start_time": "17:00",
  "end_time": "19:00",
  "duration_hours": 2,
  "lane": "Lane 3",
  "players": 4,
  "notes": "Main bareng kantor",
  "total_cost": 125000,
  "customer_email": "demo1@bowling.local",
  "created_at": "2026-01-09T15:00:00+00:00"
}
```

### Cara cek di MongoDB Compass
1. Jalankan `docker-compose up --build` hingga service `mongodb` aktif.
2. Buka MongoDB Compass → **New Connection**.
3. Masukkan connection string:
   ```
   mongodb://127.0.0.1:27017
   ```
4. Klik **Connect**.
5. Pilih database `bowling`, lalu lihat koleksi `users`, `reservations`, `counters`.

## Catatan
- Form menggunakan pola POST/Redirect/GET, jadi refresh tidak memunculkan confirm resubmission.
- `docker-compose.yml` memetakan port host ke port internal 5000, jadi log Flask akan tetap menampilkan `:5000` di dalam container (normal).

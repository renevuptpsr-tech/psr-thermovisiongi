# PLN Thermovisi Importer

Aplikasi Streamlit untuk membaca hasil pengukuran Thermovisi dari Excel, memetakan setiap sheet ke Bay pada hierarki `mst_functloc`, menghitung `delta_ambient_c`, mengunggah file asli ke Google Drive, dan menyimpan data terstruktur ke Supabase.

## Alur

1. Login menggunakan Supabase Auth.
2. Pilih ULTG dan GI dari `v_dropdown_ultg` / `v_dropdown_gi`.
3. Isi tanggal, waktu, arus pengukuran, arus puncak bulanan, dan suhu lingkungan.
4. Pilih template standar atau custom lalu unggah Excel.
5. Periksa hasil validasi dan petakan setiap sheet terisi ke Bay.
6. Simpan: file ke Google Drive; metadata, inspeksi, dan nilai suhu ke Supabase.

## Instalasi Windows PowerShell

Pastikan terminal berada di folder yang berisi `app.py`, lalu jalankan:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup_windows.ps1
```

Setelah mengisi `.streamlit\secrets.toml`, jalankan aplikasi dengan:

```powershell
.\run_windows.ps1
```

Skrip menggunakan interpreter di `.venv` secara langsung sehingga aktivasi virtual environment tidak diperlukan.

### Instalasi manual di Windows

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .streamlit\secrets.toml.example .streamlit\secrets.toml
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Jika pembuatan `.venv` sebelumnya dihentikan, ubah nama folder yang tidak lengkap terlebih dahulu:

```powershell
Rename-Item .venv .venv_incomplete
python -m venv .venv
```

Jangan menekan `Ctrl+C` selama proses `ensurepip`; pada komputer kantor atau saat antivirus memindai file baru, tahap ini dapat memerlukan waktu lebih lama.

## Instalasi Linux/macOS

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
mkdir -p .streamlit
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
streamlit run app.py
```

Gunakan Supabase **publishable/anon key**, bukan `service_role`. RLS tetap diterapkan dengan JWT pengguna yang login.

Role `authenticated` perlu `SELECT` pada tiga view dropdown dan tabel referensi template, serta hak DML yang sesuai pada tabel transaksi. RLS tetap menjadi pembatas baris per pengguna.

## Google Drive

Aktifkan Google Drive API, buat service account, lalu bagikan folder tujuan kepada `client_email` service account dengan akses Editor. Salin ID folder dan kredensial JSON ke `.streamlit/secrets.toml` mengikuti contoh. File tidak disimpan di Supabase Storage.

## Catatan validasi

- Sheet yang cocok pola template tetapi tidak memiliki nilai angka akan dilewati.
- Nilai wajib kosong menjadi `INVALID` dan memblokir penyimpanan.
- Nilai di luar -50 sampai 300 °C menjadi `WARNING`.
- Hanya baris dengan nilai suhu yang dimasukkan ke `trx_thermovisi_measurement`.
- `delta_ambient_c = temperature_c - ambient_temperature_c` dihitung sebelum insert.

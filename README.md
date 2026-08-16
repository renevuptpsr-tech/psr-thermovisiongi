# PLN Thermovisi Importer

Aplikasi Streamlit untuk membaca hasil pengukuran Thermovisi dari Excel, memetakan setiap sheet ke Bay pada hierarki `mst_functloc`, menghitung `delta_ambient_c`, mengunggah file asli ke Google Drive, dan menyimpan data terstruktur ke Supabase.

## Alur

1. Login menggunakan Supabase Auth.
2. Pilih ULTG, GI, lalu satu atau beberapa Bay yang akan diproses.
3. Isi tanggal, waktu, arus pengukuran, arus tertinggi yang pernah dicapai, dan suhu lingkungan untuk setiap Bay.
4. Pilih template yang otomatis difilter berdasarkan fungsi/tegangan Bay, lalu unggah Excel.
5. Untuk setiap Bay Trafo, pilih dua sumber: `Sheet Trafo` (bagian A) dan `Sheet Bay` (bagian B).
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

Aktifkan Google Drive API, buat service account, lalu bagikan folder tujuan kepada `client_email` service account dengan akses Editor. Buat key bertipe JSON dan salin seluruh nilai dari file JSON tersebut ke bagian `[google_service_account]` pada `.streamlit/secrets.toml`. Jangan membiarkan nilai contoh/placeholder `...`, terutama pada `private_key`. File tidak disimpan di Supabase Storage.

Folder penyimpanan proyek ini menggunakan ID `1mWx5bX5siYp0d63h1VSy0QHsblOXJT6i`. Isi konfigurasi berikut; aplikasi juga dapat menormalisasi URL folder lengkap menjadi ID tersebut:

```toml
[google_drive]
folder_id = "1mWx5bX5siYp0d63h1VSy0QHsblOXJT6i"
```

`private_key` harus memuat header, isi key, dan footer lengkap:

```toml
private_key = """-----BEGIN PRIVATE KEY-----
ISI_KEY_DARI_JSON_TANPA_DIUBAH
-----END PRIVATE KEY-----
"""
```

Jika menulis key dalam satu baris, pemisah baris literal `\\n` dari JSON juga didukung. Jangan mengunggah atau melakukan commit terhadap `.streamlit/secrets.toml` karena file tersebut berisi kredensial rahasia.

## Catatan validasi

- Nama sheet tidak menjadi syarat. Bagian form dikenali dari label titik ukur di dalam sheet, lalu pengguna memetakan Bay ke sheet yang dipilih.
- Sheet yang dikenali dari isinya tetapi tidak memiliki nilai angka akan dilewati.
- Referensi ULTG, GI, Bay, dan template disimpan dalam cache sesi agar tidak dibaca ulang pada setiap perubahan form.
- Gangguan koneksi sementara seperti Windows `10054` akan dicoba ulang untuk operasi baca yang aman.
- Pemetaan dimulai dari setiap Bay lalu pengguna memilih sheet Excel tujuan; satu sheet tidak dapat dipakai untuk dua Bay.
- Nama sheet bebas. Isi `Sheet Trafo` dan `Sheet Bay` divalidasi dari label titik ukurnya agar tidak tertukar.
- Review memilih satu Bay, lalu menampilkan tab Trafo Utama dan Bay Trafo.
- Tabel utama menggunakan kolom Pengukuran, Delta T, Kondisi, Kesimpulan/Rekomendasi, dan Status Data; nilai tunggal maupun R/S/T tetap berada dalam satu kolom.
- Baris data INVALID ditandai merah dan WARNING ditandai kuning; detail teknis tetap tersedia dalam expander.
- Tombol simpan tetap terkunci sampai seluruh hasil review dikonfirmasi pengguna.
- Untuk workflow dua sheet Trafo, penyimpanan sementara dikunci sampai model relasi satu inspeksi ke banyak sheet ditetapkan.
- Nilai wajib kosong menjadi `INVALID` dan memblokir penyimpanan.
- Nilai di luar -50 sampai 300 °C menjadi `WARNING`.
- Hanya baris dengan nilai suhu yang dimasukkan ke `trx_thermovisi_measurement`.
- `delta_ambient_c = temperature_c - ambient_temperature_c` dihitung menggunakan suhu lingkungan Bay tujuan masing-masing.
- Evaluasi Trafo menggunakan rule set berversi `THERMOVISI_TRAFO_V1`.
- Pada beban 0 A, evaluasi klem memakai ΔT aktual tanpa koreksi beban dan diberi basis `RAW_DELTA_ZERO_LOAD`.

# Google Drive Gateway

1. Buat project standalone di script.google.com.
2. Salin Code.gs dan aktifkan tampilan manifest, lalu salin appsscript.json.
3. Buka Project Settings > Script Properties dan tambahkan:
   - TARGET_FOLDER_ID: 1mWx5bX5siYp0d63h1VSy0QHsblOXJT6i
   - UPLOAD_SHARED_SECRET: token acak minimal 32 karakter.
4. Jalankan fungsi authorizeDrive satu kali dari editor untuk memberikan izin Drive.
5. Pilih Deploy > New deployment > Web app:
   - Execute as: Me
   - Who has access: Anyone
6. Salin URL deployment yang berakhir /exec ke .streamlit/secrets.toml.

Setiap perubahan Code.gs harus diterbitkan sebagai versi deployment baru melalui
Deploy > Manage deployments > Edit > New version > Deploy.

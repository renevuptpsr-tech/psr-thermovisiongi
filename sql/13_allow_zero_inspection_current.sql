-- Selaraskan constraint database dengan validasi aplikasi: nilai 0 A valid
-- untuk peralatan/trafo yang belum beroperasi saat inspeksi.

alter table public.trx_thermovisi_inspection
  drop constraint if exists trx_thermovisi_inspection_current_positive,
  drop constraint if exists trx_thermovisi_inspection_peak_current_positive;

alter table public.trx_thermovisi_inspection
  add constraint trx_thermovisi_inspection_current_nonnegative
    check (measurement_current_a >= 0),
  add constraint trx_thermovisi_inspection_peak_current_nonnegative
    check (monthly_peak_current_a >= 0);

comment on constraint trx_thermovisi_inspection_current_nonnegative
  on public.trx_thermovisi_inspection is
  'Beban ukur 0 A diperbolehkan untuk peralatan yang belum beroperasi.';

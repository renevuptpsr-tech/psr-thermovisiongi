-- Satu workbook adalah satu sumber file. Aplikasi dapat menambahkan sheet yang
-- belum pernah diproses ke upload_id yang sama tanpa mengunggah ulang ke Drive.
-- Constraint hash file tetap dipertahankan untuk mencegah file sumber duplikat.

do $$
begin
  if exists (
    select 1
    from public.trx_thermovisi_inspection
    where work_type = 'ROUTINE'
    group by
      target_functloc_id,
      extract(year from measurement_date),
      extract(month from measurement_date),
      stage_code
    having count(*) > 1
  ) then
    raise exception
      'Tidak dapat membuat constraint: masih ada inspeksi ROUTINE duplikat untuk Bay, bulan, dan tahap yang sama.';
  end if;
end $$;

create unique index if not exists uq_thermovisi_routine_bay_month_stage
  on public.trx_thermovisi_inspection (
    target_functloc_id,
    (extract(year from measurement_date)),
    (extract(month from measurement_date)),
    stage_code
  )
  where work_type = 'ROUTINE';

comment on index public.uq_thermovisi_routine_bay_month_stage is
  'Mencegah upload ROUTINE ganda untuk Bay, bulan, dan tahap yang sama; FOLLOW_UP dan URGENT tetap dapat berulang.';

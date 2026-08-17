drop view if exists public.v_thermovisi_plan_gi_summary;
drop view if exists public.v_thermovisi_plan_monitoring;

alter table public.trx_thermovisi_inspection
  drop constraint if exists fk_thermovisi_inspection_plan_item;
drop index if exists public.uq_thermovisi_inspection_plan_item;
alter table public.trx_thermovisi_inspection
  drop column if exists plan_item_id;

drop table if exists public.trx_thermovisi_plan_item;
drop table if exists public.trx_thermovisi_plan;

alter table public.trx_thermovisi_inspection
  add column if not exists work_type character varying(20) not null default 'ROUTINE',
  add column if not exists stage_code character varying(20) not null default 'TAHAP_1';

alter table public.trx_thermovisi_inspection
  add constraint chk_thermovisi_inspection_work_type
    check (work_type in ('ROUTINE', 'FOLLOW_UP', 'URGENT')),
  add constraint chk_thermovisi_inspection_stage
    check (
      (work_type = 'ROUTINE' and stage_code in ('TAHAP_1', 'TAHAP_2'))
      or (work_type in ('FOLLOW_UP', 'URGENT') and stage_code = 'ADHOC')
    );

create index if not exists idx_thermovisi_inspection_monitoring
  on public.trx_thermovisi_inspection
    (measurement_date, work_type, stage_code, target_functloc_id);

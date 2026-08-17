create table if not exists public.trx_thermovisi_evaluation (
  evaluation_id uuid primary key default gen_random_uuid(),
  inspection_id uuid not null,
  inspection_sheet_id uuid not null,
  target_template_item_id bigint not null,
  point_code varchar(100) not null,
  equipment_group_code varchar(50) not null,
  comparison_group_code varchar(100),
  evaluation_scope_code varchar(20) not null,
  rule_set_code varchar(100) not null,
  rule_code text not null,
  rule_version varchar(20) not null default '1.0',
  method text not null,
  evaluation_basis varchar(100),
  phase_delta_c numeric(10,3),
  ambient_delta_c numeric(10,3),
  corrected_delta_c numeric(10,3),
  analyzed_delta_c numeric(10,3),
  maximum_temperature_c numeric(10,3),
  gradient_pattern_code varchar(50),
  condition_label text not null,
  recommendation text not null,
  severity smallint not null,
  ahi_score smallint,
  ahi_category varchar(30),
  data_quality_status varchar(30) not null,
  analysis_status varchar(30) not null,
  input_snapshot jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint uq_thermovisi_evaluation_target
    unique (inspection_id, inspection_sheet_id, target_template_item_id),
  constraint fk_thermovisi_evaluation_inspection
    foreign key (inspection_id)
    references public.trx_thermovisi_inspection(inspection_id)
    on delete cascade,
  constraint fk_thermovisi_evaluation_sheet
    foreign key (inspection_sheet_id, inspection_id)
    references public.trx_thermovisi_inspection_sheet(inspection_sheet_id, inspection_id)
    on delete cascade,
  constraint fk_thermovisi_evaluation_template_item
    foreign key (target_template_item_id)
    references public.ref_thermovisi_template_item(template_item_id)
    on update cascade on delete restrict,
  constraint chk_thermovisi_evaluation_scope
    check (evaluation_scope_code in ('POINT', 'PAIR', 'PHASE_GROUP', 'GRADIENT')),
  constraint chk_thermovisi_evaluation_severity
    check (severity between 0 and 4),
  constraint chk_thermovisi_evaluation_ahi
    check (ahi_score is null or ahi_score between 1 and 5),
  constraint chk_thermovisi_evaluation_quality
    check (data_quality_status in (
      'VALID', 'WARNING', 'INVALID', 'NOT_MEASURED', 'NOT_APPLICABLE'
    )),
  constraint chk_thermovisi_evaluation_snapshot
    check (jsonb_typeof(input_snapshot) = 'object')
);

comment on table public.trx_thermovisi_evaluation is
  'Hasil final Evaluation Engine Python per target analisis Thermovisi, termasuk rule, kondisi, rekomendasi, AHI, dan snapshot input audit.';
comment on column public.trx_thermovisi_evaluation.input_snapshot is
  'Salinan nilai input yang dipakai Python agar hasil evaluasi dapat direproduksi saat rule berubah.';

create index if not exists idx_thermovisi_evaluation_inspection
  on public.trx_thermovisi_evaluation (inspection_id, inspection_sheet_id);
create index if not exists idx_thermovisi_evaluation_sheet
  on public.trx_thermovisi_evaluation (inspection_sheet_id, inspection_id);
create index if not exists idx_thermovisi_evaluation_template_item
  on public.trx_thermovisi_evaluation (target_template_item_id);
create index if not exists idx_thermovisi_evaluation_rule
  on public.trx_thermovisi_evaluation (rule_set_code, rule_code);
create index if not exists idx_thermovisi_evaluation_ahi_attention
  on public.trx_thermovisi_evaluation (ahi_score desc, inspection_id)
  where ahi_score >= 3;

alter table public.trx_thermovisi_evaluation enable row level security;

create policy thermovisi_evaluation_select_own
on public.trx_thermovisi_evaluation
for select
to authenticated
using (
  (select auth.uid()) is not null
  and exists (
    select 1
    from public.trx_thermovisi_inspection i
    where i.inspection_id = trx_thermovisi_evaluation.inspection_id
      and i.created_by = (select auth.uid())
  )
);

create policy thermovisi_evaluation_insert_own
on public.trx_thermovisi_evaluation
for insert
to authenticated
with check (
  (select auth.uid()) is not null
  and exists (
    select 1
    from public.trx_thermovisi_inspection i
    join public.trx_thermovisi_inspection_sheet s
      on s.inspection_id = i.inspection_id
    join public.ref_thermovisi_template_item ti
      on ti.template_item_id = trx_thermovisi_evaluation.target_template_item_id
     and ti.template_code = i.template_code
    where i.inspection_id = trx_thermovisi_evaluation.inspection_id
      and s.inspection_sheet_id = trx_thermovisi_evaluation.inspection_sheet_id
      and i.created_by = (select auth.uid())
      and ti.point_code = trx_thermovisi_evaluation.point_code
      and ti.equipment_group_code = trx_thermovisi_evaluation.equipment_group_code
  )
);

create policy thermovisi_evaluation_update_own
on public.trx_thermovisi_evaluation
for update
to authenticated
using (
  (select auth.uid()) is not null
  and exists (
    select 1
    from public.trx_thermovisi_inspection i
    where i.inspection_id = trx_thermovisi_evaluation.inspection_id
      and i.created_by = (select auth.uid())
  )
)
with check (
  (select auth.uid()) is not null
  and exists (
    select 1
    from public.trx_thermovisi_inspection i
    join public.trx_thermovisi_inspection_sheet s
      on s.inspection_id = i.inspection_id
    where i.inspection_id = trx_thermovisi_evaluation.inspection_id
      and s.inspection_sheet_id = trx_thermovisi_evaluation.inspection_sheet_id
      and i.created_by = (select auth.uid())
  )
);

grant select, insert, update on public.trx_thermovisi_evaluation to authenticated;

create trigger trg_trx_thermovisi_evaluation_updated_at
before update on public.trx_thermovisi_evaluation
for each row execute function public.set_current_updated_at();

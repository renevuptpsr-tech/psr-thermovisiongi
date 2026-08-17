create table if not exists public.trx_thermovisi_plan (
  plan_id uuid primary key default gen_random_uuid(),
  period_month date not null,
  ultg_functloc_id character varying(100) not null,
  work_type character varying(20) not null,
  stage_code character varying(20) not null,
  plan_status character varying(20) not null default 'DRAFT',
  notes text,
  created_by uuid default auth.uid(),
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  constraint fk_thermovisi_plan_ultg
    foreign key (ultg_functloc_id)
    references public.mst_functloc(functloc_id)
    on update cascade on delete restrict,
  constraint fk_thermovisi_plan_created_by
    foreign key (created_by) references auth.users(id) on delete set null,
  constraint uq_thermovisi_plan_period
    unique (period_month, ultg_functloc_id, work_type, stage_code),
  constraint chk_thermovisi_plan_month_start
    check (period_month = date_trunc('month', period_month)::date),
  constraint chk_thermovisi_plan_work_type
    check (work_type in ('ROUTINE', 'FOLLOW_UP', 'URGENT')),
  constraint chk_thermovisi_plan_stage
    check (
      (work_type = 'ROUTINE' and stage_code in ('TAHAP_1', 'TAHAP_2'))
      or (work_type in ('FOLLOW_UP', 'URGENT') and stage_code = 'ADHOC')
    ),
  constraint chk_thermovisi_plan_status
    check (plan_status in ('DRAFT', 'ACTIVE', 'CLOSED', 'CANCELLED'))
);

create table if not exists public.trx_thermovisi_plan_item (
  plan_item_id uuid primary key default gen_random_uuid(),
  plan_id uuid not null,
  bay_functloc_id character varying(100) not null,
  template_code character varying(100),
  item_status character varying(20) not null default 'PLANNED',
  notes text,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  constraint fk_thermovisi_plan_item_plan
    foreign key (plan_id) references public.trx_thermovisi_plan(plan_id)
    on update cascade on delete cascade,
  constraint fk_thermovisi_plan_item_bay
    foreign key (bay_functloc_id) references public.mst_functloc(functloc_id)
    on update cascade on delete restrict,
  constraint fk_thermovisi_plan_item_template
    foreign key (template_code) references public.ref_thermovisi_template(template_code)
    on update cascade on delete restrict,
  constraint uq_thermovisi_plan_item_bay unique (plan_id, bay_functloc_id),
  constraint uq_thermovisi_plan_item_identity unique (plan_item_id, bay_functloc_id),
  constraint chk_thermovisi_plan_item_status
    check (item_status in ('PLANNED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED'))
);

alter table public.trx_thermovisi_inspection
  add column if not exists plan_item_id uuid;

alter table public.trx_thermovisi_inspection
  add constraint fk_thermovisi_inspection_plan_item
  foreign key (plan_item_id, target_functloc_id)
  references public.trx_thermovisi_plan_item(plan_item_id, bay_functloc_id)
  on update cascade on delete set null (plan_item_id);

create unique index if not exists uq_thermovisi_inspection_plan_item
  on public.trx_thermovisi_inspection(plan_item_id)
  where plan_item_id is not null;
create index if not exists idx_thermovisi_plan_period_ultg
  on public.trx_thermovisi_plan(period_month, ultg_functloc_id, work_type, stage_code);
create index if not exists idx_thermovisi_plan_ultg
  on public.trx_thermovisi_plan(ultg_functloc_id);
create index if not exists idx_thermovisi_plan_created_by
  on public.trx_thermovisi_plan(created_by);
create index if not exists idx_thermovisi_plan_item_plan_status
  on public.trx_thermovisi_plan_item(plan_id, item_status);
create index if not exists idx_thermovisi_plan_item_bay
  on public.trx_thermovisi_plan_item(bay_functloc_id);
create index if not exists idx_thermovisi_plan_item_template
  on public.trx_thermovisi_plan_item(template_code)
  where template_code is not null;

alter table public.trx_thermovisi_plan enable row level security;
alter table public.trx_thermovisi_plan_item enable row level security;

create policy thermovisi_plan_select_authenticated
  on public.trx_thermovisi_plan for select to authenticated
  using (true);
create policy thermovisi_plan_insert_owner
  on public.trx_thermovisi_plan for insert to authenticated
  with check ((select auth.uid()) = created_by);
create policy thermovisi_plan_update_owner
  on public.trx_thermovisi_plan for update to authenticated
  using ((select auth.uid()) = created_by)
  with check ((select auth.uid()) = created_by);
create policy thermovisi_plan_delete_owner
  on public.trx_thermovisi_plan for delete to authenticated
  using ((select auth.uid()) = created_by);

create policy thermovisi_plan_item_select_authenticated
  on public.trx_thermovisi_plan_item for select to authenticated
  using (true);
create policy thermovisi_plan_item_insert_owner
  on public.trx_thermovisi_plan_item for insert to authenticated
  with check (exists (
    select 1 from public.trx_thermovisi_plan p
    where p.plan_id = trx_thermovisi_plan_item.plan_id
      and p.created_by = (select auth.uid())
  ));
create policy thermovisi_plan_item_update_owner
  on public.trx_thermovisi_plan_item for update to authenticated
  using (exists (
    select 1 from public.trx_thermovisi_plan p
    where p.plan_id = trx_thermovisi_plan_item.plan_id
      and p.created_by = (select auth.uid())
  ))
  with check (exists (
    select 1 from public.trx_thermovisi_plan p
    where p.plan_id = trx_thermovisi_plan_item.plan_id
      and p.created_by = (select auth.uid())
  ));
create policy thermovisi_plan_item_delete_owner
  on public.trx_thermovisi_plan_item for delete to authenticated
  using (exists (
    select 1 from public.trx_thermovisi_plan p
    where p.plan_id = trx_thermovisi_plan_item.plan_id
      and p.created_by = (select auth.uid())
  ));

grant select, insert, update, delete on public.trx_thermovisi_plan to authenticated;
grant select, insert, update, delete on public.trx_thermovisi_plan_item to authenticated;

create trigger trg_trx_thermovisi_plan_updated_at
before update on public.trx_thermovisi_plan
for each row execute function public.set_current_updated_at();

create trigger trg_trx_thermovisi_plan_item_updated_at
before update on public.trx_thermovisi_plan_item
for each row execute function public.set_current_updated_at();

create or replace view public.v_thermovisi_plan_monitoring
with (security_invoker = true)
as
select
  p.plan_id,
  pi.plan_item_id,
  p.period_month,
  p.work_type,
  p.stage_code,
  p.plan_status,
  b.ultg_flc,
  b.ultg_name,
  b.gi_flc,
  b.gi_name,
  b.bay_flc,
  b.bay_name,
  b.bay_short_name,
  b.bay_function_code,
  b.voltage_code,
  pi.template_code,
  case
    when i.inspection_id is not null then 'COMPLETED'
    else pi.item_status
  end as execution_status,
  i.inspection_id,
  i.measurement_date,
  i.measurement_time,
  i.inspection_status,
  pi.notes
from public.trx_thermovisi_plan_item pi
join public.trx_thermovisi_plan p on p.plan_id = pi.plan_id
join public.v_dropdown_bay b on b.bay_flc = pi.bay_functloc_id
left join public.trx_thermovisi_inspection i on i.plan_item_id = pi.plan_item_id;

create or replace view public.v_thermovisi_plan_gi_summary
with (security_invoker = true)
as
select
  period_month,
  work_type,
  stage_code,
  ultg_flc,
  ultg_name,
  gi_flc,
  gi_name,
  count(*) filter (where execution_status <> 'CANCELLED') as total_bay,
  count(*) filter (where execution_status = 'COMPLETED') as completed_bay,
  count(*) filter (where execution_status in ('PLANNED', 'IN_PROGRESS')) as outstanding_bay,
  round(
    100.0 * count(*) filter (where execution_status = 'COMPLETED')
    / nullif(count(*) filter (where execution_status <> 'CANCELLED'), 0),
    2
  ) as completion_percent
from public.v_thermovisi_plan_monitoring
group by period_month, work_type, stage_code, ultg_flc, ultg_name, gi_flc, gi_name;

grant select on public.v_thermovisi_plan_monitoring to authenticated;
grant select on public.v_thermovisi_plan_gi_summary to authenticated;

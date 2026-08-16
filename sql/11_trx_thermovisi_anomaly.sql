create table if not exists public.trx_thermovisi_anomaly (
  anomaly_id uuid primary key default gen_random_uuid(),
  evaluation_id uuid not null,
  inspection_id uuid not null,
  equipment_group_code character varying(50),
  point_code character varying(100),
  condition_label text not null,
  recommendation text not null,
  analyzed_delta_c numeric(10, 3),
  maximum_temperature_c numeric(10, 3),
  severity smallint not null,
  ahi_score smallint,
  ahi_category character varying(30),
  anomaly_status character varying(20) not null default 'OPEN',
  notification_status character varying(20) not null default 'PENDING',
  telegram_chat_id text,
  telegram_message_id text,
  notification_attempts smallint not null default 0,
  notification_error text,
  notified_at timestamp with time zone,
  acknowledged_by uuid,
  acknowledged_at timestamp with time zone,
  resolved_by uuid,
  resolved_at timestamp with time zone,
  resolution_notes text,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  constraint uq_thermovisi_anomaly_evaluation unique (evaluation_id),
  constraint fk_thermovisi_anomaly_evaluation
    foreign key (evaluation_id)
    references public.trx_thermovisi_evaluation(evaluation_id)
    on update cascade on delete cascade,
  constraint fk_thermovisi_anomaly_inspection
    foreign key (inspection_id)
    references public.trx_thermovisi_inspection(inspection_id)
    on update cascade on delete cascade,
  constraint fk_thermovisi_anomaly_acknowledged_by
    foreign key (acknowledged_by) references auth.users(id) on delete set null,
  constraint fk_thermovisi_anomaly_resolved_by
    foreign key (resolved_by) references auth.users(id) on delete set null,
  constraint chk_thermovisi_anomaly_severity check (severity between 1 and 4),
  constraint chk_thermovisi_anomaly_ahi check (ahi_score is null or ahi_score between 1 and 5),
  constraint chk_thermovisi_anomaly_status
    check (anomaly_status in ('OPEN', 'ACKNOWLEDGED', 'RESOLVED', 'FALSE_POSITIVE')),
  constraint chk_thermovisi_anomaly_notification_status
    check (notification_status in ('PENDING', 'SENT', 'FAILED', 'SKIPPED')),
  constraint chk_thermovisi_anomaly_notification_attempts
    check (notification_attempts >= 0)
);

create index if not exists idx_thermovisi_anomaly_inspection
  on public.trx_thermovisi_anomaly(inspection_id);
create index if not exists idx_thermovisi_anomaly_open_severity
  on public.trx_thermovisi_anomaly(severity desc, created_at desc)
  where anomaly_status in ('OPEN', 'ACKNOWLEDGED');
create index if not exists idx_thermovisi_anomaly_notification_pending
  on public.trx_thermovisi_anomaly(notification_status, created_at)
  where notification_status in ('PENDING', 'FAILED');
create index if not exists idx_thermovisi_anomaly_acknowledged_by
  on public.trx_thermovisi_anomaly(acknowledged_by)
  where acknowledged_by is not null;
create index if not exists idx_thermovisi_anomaly_resolved_by
  on public.trx_thermovisi_anomaly(resolved_by)
  where resolved_by is not null;

alter table public.trx_thermovisi_anomaly enable row level security;

create policy thermovisi_anomaly_select_own
  on public.trx_thermovisi_anomaly for select to authenticated
  using (exists (
    select 1 from public.trx_thermovisi_inspection i
    where i.inspection_id = trx_thermovisi_anomaly.inspection_id
      and i.created_by = (select auth.uid())
  ));
create policy thermovisi_anomaly_insert_own
  on public.trx_thermovisi_anomaly for insert to authenticated
  with check (exists (
    select 1 from public.trx_thermovisi_inspection i
    where i.inspection_id = trx_thermovisi_anomaly.inspection_id
      and i.created_by = (select auth.uid())
  ));
create policy thermovisi_anomaly_update_own
  on public.trx_thermovisi_anomaly for update to authenticated
  using (exists (
    select 1 from public.trx_thermovisi_inspection i
    where i.inspection_id = trx_thermovisi_anomaly.inspection_id
      and i.created_by = (select auth.uid())
  ))
  with check (exists (
    select 1 from public.trx_thermovisi_inspection i
    where i.inspection_id = trx_thermovisi_anomaly.inspection_id
      and i.created_by = (select auth.uid())
  ));

grant select, insert, update on public.trx_thermovisi_anomaly to authenticated;

create trigger trg_trx_thermovisi_anomaly_updated_at
before update on public.trx_thermovisi_anomaly
for each row execute function public.set_current_updated_at();

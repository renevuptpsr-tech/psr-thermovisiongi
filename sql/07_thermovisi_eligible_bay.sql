create or replace view public.v_thermovisi_eligible_bay
with (security_invoker = true)
as
select
  b.ultg_flc,
  b.ultg_name,
  b.gi_flc,
  b.gi_name,
  b.bay_flc,
  b.bay_name,
  b.bay_short_name,
  b.bay_function_code,
  f.description as bay_function_name,
  b.baygroup_code,
  b.voltage_code,
  b.status_code
from public.v_dropdown_bay b
join public.ref_function f
  on f.function_code = b.bay_function_code
where b.bay_function_code in ('1', '2', 'D', 'E')
  and f.is_active = true;

grant select on public.v_thermovisi_eligible_bay to authenticated;

drop policy if exists thermovisi_plan_item_insert_owner
  on public.trx_thermovisi_plan_item;
drop policy if exists thermovisi_plan_item_update_owner
  on public.trx_thermovisi_plan_item;

create policy thermovisi_plan_item_insert_owner
  on public.trx_thermovisi_plan_item for insert to authenticated
  with check (exists (
    select 1
    from public.trx_thermovisi_plan p
    join public.v_thermovisi_eligible_bay b
      on b.bay_flc = trx_thermovisi_plan_item.bay_functloc_id
     and b.ultg_flc = p.ultg_functloc_id
    where p.plan_id = trx_thermovisi_plan_item.plan_id
      and p.created_by = (select auth.uid())
  ));

create policy thermovisi_plan_item_update_owner
  on public.trx_thermovisi_plan_item for update to authenticated
  using (exists (
    select 1
    from public.trx_thermovisi_plan p
    where p.plan_id = trx_thermovisi_plan_item.plan_id
      and p.created_by = (select auth.uid())
  ))
  with check (exists (
    select 1
    from public.trx_thermovisi_plan p
    join public.v_thermovisi_eligible_bay b
      on b.bay_flc = trx_thermovisi_plan_item.bay_functloc_id
     and b.ultg_flc = p.ultg_functloc_id
    where p.plan_id = trx_thermovisi_plan_item.plan_id
      and p.created_by = (select auth.uid())
  ));

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
  b.status_code,
  (b.gi_flc <> 'TRS-3213-048.048') as is_routine_required,
  case
    when b.gi_flc = 'TRS-3213-048.048' then 'OPTIONAL'
    else 'REQUIRED'
  end::character varying(20) as monitoring_category
from public.v_dropdown_bay b
join public.ref_function f
  on f.function_code = b.bay_function_code
where b.bay_function_code in ('1', '2', 'D', 'E')
  and f.is_active = true
  and b.gi_flc <> 'TRS-3213-164.164';

grant select on public.v_thermovisi_eligible_bay to authenticated;

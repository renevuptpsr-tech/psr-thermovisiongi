create or replace view public.v_dropdown_ultg
with (security_invoker = true)
as
select
  u.functloc_id as ultg_flc,
  u.location_name as ultg_name,
  u.short_name as ultg_short_name,
  u.status_code,
  u.region_code,
  u.plant_id
from public.mst_functloc u
join public.ref_flc ru
  on ru.flc_id = u.functloc_id
 and ru.is_active = true
where u.nlevel = 3.0
  and u.function_code = 'B'
  and u.plant_id = '3213';

create or replace view public.v_dropdown_gi
with (security_invoker = true)
as
select
  u.functloc_id as ultg_flc,
  u.location_name as ultg_name,
  g.functloc_id as gi_flc,
  g.location_name as gi_name,
  g.short_name as gi_short_name,
  g.voltage_code,
  g.status_code,
  g.region_code,
  g.city,
  g.latitude,
  g.longitude
from public.mst_functloc g
join public.ref_flc rg
  on rg.flc_id = g.functloc_id
 and rg.is_active = true
join public.mst_functloc u
  on u.functloc_id = g.bc_flc
 and u.nlevel = 3.0
 and u.function_code = 'B'
 and u.plant_id = '3213'
join public.ref_flc ru
  on ru.flc_id = u.functloc_id
 and ru.is_active = true
where g.nlevel = 3.0
  and g.function_code = 'G'
  and g.plant_id = '3213';

create or replace view public.v_dropdown_bay
with (security_invoker = true)
as
select
  u.functloc_id as ultg_flc,
  u.location_name as ultg_name,
  g.functloc_id as gi_flc,
  g.location_name as gi_name,
  b.functloc_id as bay_flc,
  b.location_name as bay_name,
  b.short_name as bay_short_name,
  b.function_code as bay_function_code,
  b.baygroup_code,
  b.voltage_code,
  b.status_code
from public.mst_functloc b
join public.ref_flc rb
  on rb.flc_id = b.functloc_id
 and rb.is_active = true
join public.mst_functloc g
  on g.functloc_id = b.gi_flc
 and g.nlevel = 3.0
 and g.function_code = 'G'
 and g.plant_id = '3213'
join public.ref_flc rg
  on rg.flc_id = g.functloc_id
 and rg.is_active = true
join public.mst_functloc u
  on u.functloc_id = g.bc_flc
 and u.nlevel = 3.0
 and u.function_code = 'B'
 and u.plant_id = '3213'
join public.ref_flc ru
  on ru.flc_id = u.functloc_id
 and ru.is_active = true
where b.nlevel = 4.0
  and b.functloc_id ~ '-B[0-9]+$'
  and b.plant_id = '3213';

grant select on public.v_dropdown_ultg to authenticated;
grant select on public.v_dropdown_gi to authenticated;
grant select on public.v_dropdown_bay to authenticated;

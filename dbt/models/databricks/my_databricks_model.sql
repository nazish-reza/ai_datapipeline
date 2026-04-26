{{ config(materialized='table', tags=['databricks']) }}

select
  id,
  name,
  loaded_at
from {{ source('databricks_raw', 'raw_table') }}

{{ config(materialized='table', tags=['bigquery']) }}

select
  id,
  department
from {{ source('demo_dataset', 'employees') }}


    
    

with dbt_test__target as (

  select isbn as unique_field
  from `genuine-arena-458814-u7`.`books_clean_stg`.`books_clean_stg`
  where isbn is not null

)

select
    unique_field,
    count(*) as n_records

from dbt_test__target
group by unique_field
having count(*) > 1



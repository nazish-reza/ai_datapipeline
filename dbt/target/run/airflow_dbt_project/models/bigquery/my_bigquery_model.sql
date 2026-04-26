
  
    

    create or replace table `genuine-arena-458814-u7`.`dbt_dataset`.`my_bigquery_model`
      
    
    

    
    OPTIONS()
    as (
      

select
  id,
  department
from `genuine-arena-458814-u7`.`demo_dataset`.`employees`
    );
  
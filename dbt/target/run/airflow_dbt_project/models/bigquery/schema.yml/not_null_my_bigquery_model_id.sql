
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select id
from `genuine-arena-458814-u7`.`dbt_dataset`.`my_bigquery_model`
where id is null



  
  
      
    ) dbt_internal_test

    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select department
from `genuine-arena-458814-u7`.`dbt_dataset`.`my_bigquery_model`
where department is null



  
  
      
    ) dbt_internal_test

    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select publisher
from `genuine-arena-458814-u7`.`books_clean_stg`.`books_clean_stg`
where publisher is null



  
  
      
    ) dbt_internal_test
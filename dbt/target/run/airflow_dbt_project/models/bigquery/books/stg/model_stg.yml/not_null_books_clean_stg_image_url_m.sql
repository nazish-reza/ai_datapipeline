
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select image_url_m
from `genuine-arena-458814-u7`.`books_clean_stg`.`books_clean_stg`
where image_url_m is null



  
  
      
    ) dbt_internal_test
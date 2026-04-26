
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select year_of_publication
from `genuine-arena-458814-u7`.`books_clean_stg`.`books_clean_stg`
where year_of_publication is null



  
  
      
    ) dbt_internal_test
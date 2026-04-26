
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select book_title
from `genuine-arena-458814-u7`.`books_clean_stg`.`books_clean_stg`
where book_title is null



  
  
      
    ) dbt_internal_test
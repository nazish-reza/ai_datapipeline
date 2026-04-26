
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select book_author
from `genuine-arena-458814-u7`.`books_clean_stg`.`books_clean_stg`
where book_author is null



  
  
      
    ) dbt_internal_test
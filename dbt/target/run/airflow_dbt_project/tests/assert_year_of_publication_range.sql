
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
 
SELECT *
FROM `genuine-arena-458814-u7`.`books_clean_stg`.`books_clean_stg`
WHERE SAFE_CAST(year_of_publication AS INT64) NOT BETWEEN 1000 AND 2025
  AND year_of_publication IS NOT NULL
  
  
      
    ) dbt_internal_test
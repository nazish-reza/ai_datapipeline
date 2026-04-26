
  
    

    create or replace table `genuine-arena-458814-u7`.`books_clean_stg`.`books_clean_stg`
      
    
    

    
    OPTIONS()
    as (
      

SELECT
    ISBN AS isbn,
    `Book-Title` AS book_title,
    `Book-Author` AS book_author,
    `Year-Of-Publication` AS year_of_publication,
    Publisher AS publisher,
    `Image-URL-S` AS image_url_s,
    `Image-URL-M` AS image_url_m,
    `Image-URL-L` AS image_url_l
 FROM `genuine-arena-458814-u7`.`book_dataset_stg`.`books`
    );
  
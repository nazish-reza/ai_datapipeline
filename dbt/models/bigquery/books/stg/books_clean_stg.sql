{{ config(
    materialized='table',
    schema='books_clean_stg',
    tags=['bigquery']
) }}

SELECT
    ISBN AS isbn,
    `Book-Title` AS book_title,
    `Book-Author` AS book_author,
    `Year-Of-Publication` AS year_of_publication,
    Publisher AS publisher,
    `Image-URL-S` AS image_url_s,
    `Image-URL-M` AS image_url_m,
    `Image-URL-L` AS image_url_l
 FROM {{ source('book_dataset', 'books') }}
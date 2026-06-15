{{ config( materialized='table' ) }}

-- Model: dim_books
-- Description: Staging model for book dimension with cleaned and transformed fields
-- Inputs: {{ source('raw', 'books') }}

with

-- import CTEs
books as (
    select * from {{ source('raw', 'books') }}
),

-- logical CTEs
transformed as (
    select
        safe_cast(isbn as string) as book_id,
        trim(title) as title,
        initcap(author) as author_name,
        case when publication_year = 0 then null else publication_year end as publication_year,
        trim(publisher) as publisher_name,
        image_small,
        image_medium,
        image_large
    from books
),

-- final select
final as (
    select * from transformed
)

select * from final
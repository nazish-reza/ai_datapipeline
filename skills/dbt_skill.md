# dbt Skill — House Conventions

This skill defines how ALL dbt models and YAML files must be written.
It is injected into every generation prompt. Edit this file to change
output style everywhere — no code changes needed.

## SQL Model Structure

Every model follows this exact structure:

```sql
{{
  config(
    materialized='table'
  )
}}

-- Model: <model_name>
-- Description: <one line description>
-- Inputs: <list every source() and ref() used>

with

-- import CTEs (one per input, named after the input)
<input_name> as (
    select * from {{ source('raw', '<table>') }}   -- or {{ ref('<model>') }}
),

-- logical CTEs (transformations)
transformed as (
    select
        ...
    from <input_name>
),

-- final select
final as (
    select * from transformed
)

select * from final
```

Rules:
- Import CTEs first, one per input, lowercase, named after the source/ref
- All transformation logic in middle CTEs, never in import CTEs
- Always end with a `final` CTE and `select * from final`
- Lowercase SQL keywords (select, from, where, case when)
- One column per line in select lists
- Aliases use `as` keyword explicitly

## Naming

- All output columns: snake_case (user_id, not UserID or `User-ID`)
- Primary keys: `<entity>_id` (book_id, user_id)
- Booleans/flags: prefix `is_` or `has_` or suffix `_flag`
- Dates: suffix `_date`; timestamps: suffix `_at`

## BigQuery Specifics

- Backtick-quote raw column names containing hyphens or spaces: `` `User-ID` ``
- Use SAFE_CAST instead of CAST for type conversions from raw data
- Use SAFE_OFFSET / SAFE_ORDINAL for array access
- Use `split(col, ',')[SAFE_OFFSET(n)]` for string splitting

## ref() and source() Usage

- NEVER use source() for a table that an existing model already cleans — ref() that model
- When using ref(), use that model's OUTPUT column names (clean snake_case), never raw names
- Join on cleaned keys (user_id), never raw keys (`User-ID`)

## YAML Schema Files

```yaml
version: 2

models:
  - name: <model_name>
    description: <meaningful description of grain and purpose>
    columns:
      - name: <column>
        description: <what it is, where it came from>
        data_tests:
          - not_null        # all PK and FK columns
          - unique          # PK columns only
```

Rules:
- Every output column listed, no exceptions
- Primary keys: not_null + unique
- Foreign keys: not_null
- Derived categorical columns: accepted_values with the exact values from the CASE logic
- Descriptions explain business meaning, not just restate the column name
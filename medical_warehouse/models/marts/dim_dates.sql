{{
  config(
    materialized='table'
  )
}}

select distinct
    to_char(message_date::date, 'YYYYMMDD')::int as date_key,
    message_date::date as full_date,
    extract(dow from message_date::date)::int as day_of_week,
    trim(to_char(message_date::date, 'Day')) as day_name,
    extract(week from message_date::date)::int as week_of_year,
    extract(month from message_date::date)::int as month,
    trim(to_char(message_date::date, 'Month')) as month_name,
    extract(quarter from message_date::date)::int as quarter,
    extract(year from message_date::date)::int as year,
    case
        when extract(dow from message_date::date) in (0, 6) then true
        else false
    end as is_weekend
from {{ ref('stg_telegram_messages') }}
where message_date is not null

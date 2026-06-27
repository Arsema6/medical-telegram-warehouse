select distinct

to_char(message_date,'YYYYMMDD')::int as date_key,

message_date::date as full_date,

extract(year from message_date) as year,

extract(month from message_date) as month,

to_char(message_date,'Month') as month_name

from {{ ref('stg_telegram_messages') }}
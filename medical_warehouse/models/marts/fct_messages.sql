{{
  config(
    materialized='incremental',
    unique_key='message_key',
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns'
  )
}}

select
    s.message_key,
    s.message_id,
    c.channel_key,
    d.date_key,
    s.channel_name,
    s.message_text,
    s.message_length,
    s.views as view_count,
    s.forwards as forward_count,
    s.has_image,
    s.image_path,
    s.message_date,
    s.updated_at
from {{ ref('stg_telegram_messages') }} s
inner join {{ ref('dim_channels') }} c
    on s.channel_name = c.channel_name
inner join {{ ref('dim_dates') }} d
    on to_char(s.message_date::date, 'YYYYMMDD')::int = d.date_key
{% if is_incremental() %}
where s.updated_at >= (
    select coalesce(max(updated_at), '1970-01-01'::timestamptz) from {{ this }}
)
{% endif %}

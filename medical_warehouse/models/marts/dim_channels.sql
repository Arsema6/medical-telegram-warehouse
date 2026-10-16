{{
  config(
    materialized='table'
  )
}}

select
    md5(channel_name) as channel_key,
    channel_name,
    max(channel_type) as channel_type,
    count(*) as total_posts,
    avg(views)::numeric(12, 2) as avg_views,
    min(message_date) as first_post_date,
    max(message_date) as last_post_date
from {{ ref('stg_telegram_messages') }}
group by channel_name

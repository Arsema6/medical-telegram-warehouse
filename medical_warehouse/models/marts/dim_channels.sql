select
row_number() over(order by channel_name) as channel_key,
channel_name,
count(*) total_posts,
avg(views) avg_views,
min(message_date) first_post_date,
max(message_date) last_post_date
from {{ ref('stg_telegram_messages') }}
group by channel_name
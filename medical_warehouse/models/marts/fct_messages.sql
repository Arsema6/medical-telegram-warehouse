select
    s.message_id,
    c.channel_key,
    d.date_key,
    s.message_text,
    s.message_length,
    s.views as view_count,
    s.forwards as forward_count,
    s.has_image,
    s.image_path
from {{ ref('stg_telegram_messages') }} s
inner join {{ ref('dim_channels') }} c
    on s.channel_name = c.channel_name
inner join {{ ref('dim_dates') }} d
    on to_char(s.message_date, 'YYYYMMDD')::int = d.date_key
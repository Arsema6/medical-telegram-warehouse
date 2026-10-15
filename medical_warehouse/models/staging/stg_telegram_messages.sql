select
    message_id,
    channel_name,
    message_date,
    message_text,
    coalesce(views, 0) as views,
    coalesce(forwards, 0) as forwards,
    has_media,
    image_path,
    length(coalesce(message_text, '')) as message_length,
    case
        when image_path is not null and trim(image_path) <> '' then true
        else false
    end as has_image
from raw.telegram_messages
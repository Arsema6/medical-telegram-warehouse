{{
  config(
    materialized='view'
  )
}}

with source as (
    select * from {{ source('raw', 'telegram_messages') }}
),

cleaned as (
    select
        md5(channel_name || ':' || message_id::text) as message_key,
        message_id,
        channel_name,
        channel_type,
        message_date,
        message_text,
        coalesce(views, 0) as views,
        coalesce(forwards, 0) as forwards,
        coalesce(has_media, false) as has_media,
        nullif(trim(image_path), '') as image_path,
        length(coalesce(message_text, '')) as message_length,
        case
            when image_path is not null and trim(image_path) <> '' then true
            else false
        end as has_image,
        loaded_at,
        updated_at
    from source
    where message_id is not null
      and channel_name is not null
)

select * from cleaned

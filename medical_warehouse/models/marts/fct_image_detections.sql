{{
  config(
    materialized='incremental',
    unique_key='detection_key',
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns'
  )
}}

select
    md5(f.message_key || ':' || coalesce(d.image_path, '')) as detection_key,
    f.message_key,
    f.message_id,
    f.channel_key,
    f.date_key,
    d.image_path,
    d.detected_objects,
    d.image_category,
    d.max_confidence,
    d.loaded_at,
    d.updated_at
from {{ ref('fct_messages') }} f
inner join {{ source('raw', 'image_detections') }} d
    on f.message_id = d.message_id
   and f.channel_name = d.channel_name
where f.has_image = true
{% if is_incremental() %}
  and d.updated_at >= (
      select coalesce(max(updated_at), '1970-01-01'::timestamptz) from {{ this }}
  )
{% endif %}

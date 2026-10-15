select
    f.message_id,
    f.channel_key,
    f.date_key,
    d.id as detection_id,
    d.image_path,
    d.detected_objects as detected_class,
    d.confidence_score
from {{ ref('fct_messages') }} f
inner join {{ source('raw', 'image_detections') }} d
    on f.message_id = d.message_id::bigint
where f.has_image = true

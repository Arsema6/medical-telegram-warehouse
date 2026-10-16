-- Raw landing schema for Telegram messages and YOLO detections.
-- Applied by scripts/migrate.py and on first Postgres container start.

CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.telegram_messages (
    id BIGSERIAL PRIMARY KEY,
    message_id BIGINT NOT NULL,
    channel_name TEXT NOT NULL,
    channel_type TEXT,
    message_date TIMESTAMPTZ,
    message_text TEXT,
    views INTEGER,
    forwards INTEGER,
    has_media BOOLEAN,
    image_path TEXT,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_telegram_messages_channel_message UNIQUE (channel_name, message_id),
    CONSTRAINT chk_telegram_messages_views_nonneg CHECK (views IS NULL OR views >= 0),
    CONSTRAINT chk_telegram_messages_forwards_nonneg CHECK (forwards IS NULL OR forwards >= 0)
);

CREATE INDEX IF NOT EXISTS idx_telegram_messages_date
    ON raw.telegram_messages (message_date);

CREATE INDEX IF NOT EXISTS idx_telegram_messages_channel
    ON raw.telegram_messages (channel_name);

CREATE INDEX IF NOT EXISTS idx_telegram_messages_channel_type
    ON raw.telegram_messages (channel_type);

CREATE TABLE IF NOT EXISTS raw.image_detections (
    detection_id BIGSERIAL PRIMARY KEY,
    message_id BIGINT NOT NULL,
    channel_name TEXT NOT NULL,
    image_path TEXT NOT NULL DEFAULT '',
    detected_objects TEXT,
    image_category TEXT,
    max_confidence DOUBLE PRECISION,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_image_detections_msg_path UNIQUE (channel_name, message_id, image_path),
    CONSTRAINT chk_image_category CHECK (
        image_category IS NULL
        OR image_category IN ('promotional', 'product_display', 'lifestyle', 'other')
    )
);

CREATE INDEX IF NOT EXISTS idx_image_detections_category
    ON raw.image_detections (image_category);

CREATE INDEX IF NOT EXISTS idx_image_detections_message
    ON raw.image_detections (channel_name, message_id);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_image_detections_messages'
    ) THEN
        ALTER TABLE raw.image_detections
            ADD CONSTRAINT fk_image_detections_messages
            FOREIGN KEY (channel_name, message_id)
            REFERENCES raw.telegram_messages (channel_name, message_id)
            ON DELETE CASCADE;
    END IF;
END $$;

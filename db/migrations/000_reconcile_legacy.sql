-- Reconcile databases that were created before db/migrations existed.
--
-- This file runs first (lexical order) and is a strict no-op on a fresh
-- database because it only touches tables that already exist. It exists so
-- `python -m scripts.migrate` is safe on pre-existing installs whose raw
-- tables were created ad hoc by early versions of the loaders:
--
--   * raw.telegram_messages gained channel_type / loaded_at / updated_at and
--     lost its NULL keys and duplicate (channel_name, message_id) pairs.
--   * raw.image_detections changed grain from a surrogate (message_id) key to
--     (channel_name, message_id, image_path).
--
-- When a repair requires changing a raw column type, the projections built on
-- top of that column (the dbt views) are dropped first and rebuilt by the next
-- `dbt run`; the migration emits a NOTICE for each one it removes.
--
-- Everything below is guarded, so re-running it is always safe and a database
-- that is already on the current schema is never modified.

-- ---------------------------------------------------------------------------
-- raw.telegram_messages
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    stale_view record;
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'raw' AND table_name = 'telegram_messages'
    ) THEN
        RETURN;
    END IF;

    ALTER TABLE raw.telegram_messages
        ADD COLUMN IF NOT EXISTS channel_type TEXT;
    ALTER TABLE raw.telegram_messages
        ADD COLUMN IF NOT EXISTS loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
    ALTER TABLE raw.telegram_messages
        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

    -- Legacy installs stored a timezone-naive timestamp. Converting the type
    -- requires dropping the dependent projections first.
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'raw'
          AND table_name = 'telegram_messages'
          AND column_name = 'message_date'
          AND data_type = 'timestamp without time zone'
    ) THEN
        FOR stale_view IN
            SELECT DISTINCT vn.nspname AS schema_name, v.relname AS view_name
            FROM pg_depend d
            JOIN pg_rewrite rw ON d.objid = rw.oid
            JOIN pg_class v ON rw.ev_class = v.oid
            JOIN pg_namespace vn ON v.relnamespace = vn.oid
            JOIN pg_class src ON d.refobjid = src.oid
            JOIN pg_namespace sn ON src.relnamespace = sn.oid
            WHERE sn.nspname = 'raw'
              AND src.relname = 'telegram_messages'
              AND v.relkind = 'v'
              AND vn.nspname <> 'raw'
        LOOP
            EXECUTE format('DROP VIEW IF EXISTS %I.%I CASCADE', stale_view.schema_name, stale_view.view_name);
            RAISE NOTICE 'Reconcile: dropped view %.% (rebuilt by dbt run)',
                stale_view.schema_name, stale_view.view_name;
        END LOOP;

        ALTER TABLE raw.telegram_messages
            ALTER COLUMN message_date TYPE TIMESTAMPTZ
            USING message_date AT TIME ZONE 'UTC';
    END IF;

    -- Rows without a key cannot be upserted and break the star schema joins.
    DELETE FROM raw.telegram_messages
    WHERE channel_name IS NULL OR message_id IS NULL;

    -- Collapse exact duplicate keys, keeping the most recently written row.
    DELETE FROM raw.telegram_messages a
    USING raw.telegram_messages b
    WHERE a.ctid < b.ctid
      AND a.channel_name = b.channel_name
      AND a.message_id = b.message_id;

    ALTER TABLE raw.telegram_messages ALTER COLUMN message_id SET NOT NULL;
    ALTER TABLE raw.telegram_messages ALTER COLUMN channel_name SET NOT NULL;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_telegram_messages_channel_message'
    ) THEN
        ALTER TABLE raw.telegram_messages
            ADD CONSTRAINT uq_telegram_messages_channel_message
            UNIQUE (channel_name, message_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_telegram_messages_views_nonneg'
    ) THEN
        ALTER TABLE raw.telegram_messages
            ADD CONSTRAINT chk_telegram_messages_views_nonneg
            CHECK (views IS NULL OR views >= 0);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_telegram_messages_forwards_nonneg'
    ) THEN
        ALTER TABLE raw.telegram_messages
            ADD CONSTRAINT chk_telegram_messages_forwards_nonneg
            CHECK (forwards IS NULL OR forwards >= 0);
    END IF;

    CREATE INDEX IF NOT EXISTS idx_telegram_messages_date
        ON raw.telegram_messages (message_date);
    CREATE INDEX IF NOT EXISTS idx_telegram_messages_channel
        ON raw.telegram_messages (channel_name);
    CREATE INDEX IF NOT EXISTS idx_telegram_messages_channel_type
        ON raw.telegram_messages (channel_type);
END $$;

-- ---------------------------------------------------------------------------
-- raw.image_detections
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    is_legacy boolean;
    stale_view record;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'raw' AND table_name = 'image_detections'
    ) AND NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'raw'
          AND table_name = 'image_detections'
          AND column_name = 'channel_name'
    ) INTO is_legacy;

    IF NOT is_legacy THEN
        RETURN;
    END IF;

    CREATE TABLE raw.image_detections_new (
        detection_id BIGSERIAL PRIMARY KEY,
        message_id BIGINT NOT NULL,
        channel_name TEXT NOT NULL,
        image_path TEXT NOT NULL DEFAULT '',
        detected_objects TEXT,
        image_category TEXT,
        max_confidence DOUBLE PRECISION,
        loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_image_detections_msg_path
            UNIQUE (channel_name, message_id, image_path),
        CONSTRAINT chk_image_category CHECK (
            image_category IS NULL
            OR image_category IN ('promotional', 'product_display', 'lifestyle', 'other')
        )
    );

    -- Legacy rows only carried a numeric message id; recover the channel from
    -- the message table and drop rows that cannot be mapped.
    INSERT INTO raw.image_detections_new (
        message_id,
        channel_name,
        image_path,
        detected_objects,
        image_category,
        max_confidence,
        loaded_at,
        updated_at
    )
    SELECT
        d.message_id::bigint,
        m.channel_name,
        COALESCE(d.image_path, ''),
        d.detected_objects,
        d.image_category,
        d.confidence_score,
        NOW(),
        NOW()
    FROM raw.image_detections d
    JOIN raw.telegram_messages m
      ON m.message_id::text = d.message_id::text
    WHERE d.message_id ~ '^[0-9]+$';

    FOR stale_view IN
        SELECT DISTINCT vn.nspname AS schema_name, v.relname AS view_name
        FROM pg_depend d
        JOIN pg_rewrite rw ON d.objid = rw.oid
        JOIN pg_class v ON rw.ev_class = v.oid
        JOIN pg_namespace vn ON v.relnamespace = vn.oid
        JOIN pg_class src ON d.refobjid = src.oid
        JOIN pg_namespace sn ON src.relnamespace = sn.oid
        WHERE sn.nspname = 'raw'
          AND src.relname = 'image_detections'
          AND v.relkind = 'v'
          AND vn.nspname <> 'raw'
    LOOP
        EXECUTE format('DROP VIEW IF EXISTS %I.%I CASCADE', stale_view.schema_name, stale_view.view_name);
        RAISE NOTICE 'Reconcile: dropped view %.% (rebuilt by dbt run)',
            stale_view.schema_name, stale_view.view_name;
    END LOOP;

    DROP TABLE raw.image_detections;
    ALTER TABLE raw.image_detections_new RENAME TO image_detections;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'raw' AND table_name = 'image_detections'
    ) THEN
        RETURN;
    END IF;

    CREATE INDEX IF NOT EXISTS idx_image_detections_category
        ON raw.image_detections (image_category);
    CREATE INDEX IF NOT EXISTS idx_image_detections_message
        ON raw.image_detections (channel_name, message_id);

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_image_detections_messages'
    ) THEN
        ALTER TABLE raw.image_detections
            ADD CONSTRAINT fk_image_detections_messages
            FOREIGN KEY (channel_name, message_id)
            REFERENCES raw.telegram_messages (channel_name, message_id)
            ON DELETE CASCADE;
    END IF;
END $$;

from src.config import Settings, get_settings
from src.scraper import serialize_message


def test_settings_build_sqlalchemy_url() -> None:
    settings = get_settings()
    assert settings.database_url.startswith("postgresql+psycopg2://")
    assert str(settings.db_port) in settings.database_url


def test_skip_yolo_parses_common_boolean_strings() -> None:
    assert Settings(skip_yolo="1").skip_yolo is True
    assert Settings(skip_yolo="true").skip_yolo is True
    assert Settings(skip_yolo="0").skip_yolo is False
    assert Settings(skip_yolo="no").skip_yolo is False


def test_channels_yaml_loads() -> None:
    channels = get_settings().load_channels()
    keys = {item["key"] for item in channels}
    assert keys == {"chemed", "lobelia", "tikvah_pharma"}
    assert all("entity" in item and "type" in item for item in channels)


def test_serialize_message_omits_missing_image() -> None:
    record = serialize_message(
        message_id=1,
        channel_name="chemed",
        channel_type="Medical",
        message_date="2024-06-01T00:00:00+00:00",
        text="hello",
        views=1,
        forwards=0,
        has_media=False,
    )
    assert "image_path" not in record
    assert record["message_id"] == 1

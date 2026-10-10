from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text


def test_migration_roundtrip_and_schema_alignment(engine):
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
        assert "gpid" not in inspect(connection).get_schema_names()
        assert "raw" not in inspect(connection).get_schema_names()
        assert connection.scalar(text("SELECT PostGIS_Version()"))
        command.upgrade(config, "head")
        assert len(inspect(connection).get_table_names(schema="gpid")) == 15
        assert inspect(connection).get_table_names(schema="raw") == ["artifact"]
        command.check(config)
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0002"

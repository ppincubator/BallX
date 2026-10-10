from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from ballx.config import get_settings
from ballx.db.base import Base
from ballx.domain import (
    ingestion_models,  # noqa: F401
    models,  # noqa: F401
)

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)


def include_name(name, type_, parent_names):
    if type_ == "schema":
        return name in {"gpid", "raw"}
    return True


options = {
    "target_metadata": Base.metadata,
    "include_schemas": True,
    "include_name": include_name,
    "compare_type": True,
    "compare_server_default": True,
}
# Tests can provide a connection without placing credentials in the Alembic INI.
connection = config.attributes.get("connection")
if context.is_offline_mode():
    context.configure(
        url=get_settings().database_url.get_secret_value(),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **options,
    )
    with context.begin_transaction():
        context.run_migrations()
elif connection is not None:
    context.configure(connection=connection, **options)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(get_settings().database_url.get_secret_value(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, **options)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()

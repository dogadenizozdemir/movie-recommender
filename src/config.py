"""Reads connection settings from the .env file in the project root."""
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SQL_DIR = ROOT / "sql"


def load_env():
    settings = {}
    for line in (ROOT / ".env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            settings[key.strip()] = value.strip()
    return settings


ENV = load_env()

PG_PARAMS = dict(
    host=ENV["POSTGRES_HOST"],
    port=int(ENV["POSTGRES_PORT"]),
    dbname=ENV["POSTGRES_DB"],
    user=ENV["POSTGRES_USER"],
    password=ENV["POSTGRES_PASSWORD"],
)

MONGO_URI = (
    f"mongodb://{quote_plus(ENV['MONGO_USER'])}:{quote_plus(ENV['MONGO_PASSWORD'])}"
    f"@{ENV['MONGO_HOST']}:{ENV['MONGO_PORT']}/?authSource=admin"
)
MONGO_DB = ENV["MONGO_DB"]

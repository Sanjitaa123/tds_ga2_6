
import os
from pathlib import Path

import yaml
from dotenv import dotenv_values
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent

DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

def coerce(key, value):
    value = str(value)

    if key in ("port", "workers"):
        return int(value)

    if key == "debug":
        return value.strip().lower() in ("true", "1", "yes", "on")

    return value

def normalize_key(key):
    key = key.strip()

    if key == "NUM_WORKERS":
        return "workers"

    if key.startswith("APP_"):
        key = key[4:].lower()
        if key == "num_workers":
            return "workers"
        return key

    return key.lower()

def apply_layer(config, values):
    for raw_key, value in values.items():
        if value is None:
            continue

        key = normalize_key(raw_key)
        config[key] = coerce(key, value)

@app.get("/effective-config")
def effective_config(set: list[str] = Query(default=[])):
    config = DEFAULTS.copy()

    # Layer 2: environment-specific YAML
    yaml_path = BASE_DIR / "config.development.yaml"
    if yaml_path.exists():
        with yaml_path.open("r", encoding="utf-8") as file:
            yaml_config = yaml.safe_load(file) or {}
        apply_layer(config, yaml_config)

    # Layer 3: .env file (read without modifying OS environment)
    env_path = BASE_DIR / ".env"
    env_config = dotenv_values(env_path)
    apply_layer(config, env_config)

    # Layer 4: actual OS environment variables
    os_config = {
        key: value
        for key, value in os.environ.items()
        if key.startswith("APP_")
    }
    apply_layer(config, os_config)

    # Layer 5: CLI/query overrides
    for item in set:
        key, separator, value = item.partition("=")
        if not separator or not key.strip():
            continue

        key = normalize_key(key)
        config[key] = coerce(key, value)

    # Never expose the actual API key
    config["api_key"] = "****"

    return config

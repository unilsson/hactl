from dataclasses import dataclass
from pathlib import Path
import os
import stat
import tomllib


class ConfigError(Exception):
    pass


@dataclass
class Config:
    url: str
    token: str
    aliases: dict[str, str]


def get_config_dir() -> Path:
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")

    if xdg_config_home:
        return Path(xdg_config_home) / "hactl"

    return Path.home() / ".config" / "hactl"


def load_config() -> Config:
    config_dir = get_config_dir()

    config_file = config_dir / "config.toml"
    credentials_file = config_dir / "credentials"

    if not config_file.exists():
        raise ConfigError(
            f"Configuration file not found: {config_file}"
        )

    if not credentials_file.exists():
        raise ConfigError(
            f"Credentials file not found: {credentials_file}"
        )

    mode = credentials_file.stat().st_mode

    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise ConfigError(
            f"{credentials_file} is accessible by other users. "
            f"Run: chmod 600 {credentials_file}"
        )

    with config_file.open("rb") as f:
        data = tomllib.load(f)

    url = data.get("url")

    if not url:
        raise ConfigError("Missing 'url' in config.toml")

    token = credentials_file.read_text().strip()

    if not token:
        raise ConfigError("Credentials file is empty")

    aliases = data.get("aliases", {})

    return Config(
        url=url.rstrip("/"),
        token=token,
        aliases=aliases,
    )

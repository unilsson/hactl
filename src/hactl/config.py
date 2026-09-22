from dataclasses import dataclass
from pathlib import Path
import os
import stat
import tempfile
import tomllib

import tomlkit


class ConfigError(Exception):
    pass


@dataclass
class Config:
    url: str
    token: str
    aliases: dict[str, str]
    binary_sensor_states: dict[str, dict[str, str]]


def get_config_dir() -> Path:
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")

    if xdg_config_home:
        return Path(xdg_config_home) / "hactl"

    return Path.home() / ".config" / "hactl"


def set_alias(
    alias: str,
    entity_id: str,
) -> dict[str, str]:
    alias = alias.strip()

    if not alias:
        raise ConfigError("Alias cannot be empty")

    if "\n" in alias or "\r" in alias:
        raise ConfigError("Alias cannot contain line breaks")

    if not entity_id or "." not in entity_id:
        raise ConfigError(
            f"Invalid entity ID: {entity_id}"
        )

    config_file = get_config_dir() / "config.toml"

    if not config_file.exists():
        raise ConfigError(
            f"Configuration file not found: {config_file}"
        )

    try:
        document = tomlkit.parse(
            config_file.read_text(
                encoding="utf-8"
            )
        )
    except Exception as exc:
        raise ConfigError(
            f"Could not parse {config_file}: {exc}"
        ) from exc

    aliases = document.get("aliases")

    if aliases is None:
        aliases = tomlkit.table()
        document["aliases"] = aliases

    if not hasattr(aliases, "items"):
        raise ConfigError(
            "'aliases' must be a TOML table"
        )

    existing_target = aliases.get(alias)

    if (
        existing_target is not None
        and str(existing_target) != entity_id
    ):
        raise ConfigError(
            f"Alias '{alias}' is already assigned to "
            f"{existing_target}"
        )

    for existing_alias, target in list(
        aliases.items()
    ):
        if (
            str(target) == entity_id
            and str(existing_alias) != alias
        ):
            del aliases[existing_alias]

    aliases[alias] = entity_id

    temp_path = None

    try:
        mode = stat.S_IMODE(
            config_file.stat().st_mode
        )

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=config_file.parent,
            prefix=".config.toml.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(
                tomlkit.dumps(document)
            )
            temp_file.flush()
            os.fsync(temp_file.fileno())

        os.chmod(temp_path, mode)
        os.replace(
            temp_path,
            config_file,
        )
        temp_path = None

    except OSError as exc:
        raise ConfigError(
            f"Could not update {config_file}: {exc}"
        ) from exc

    finally:
        if (
            temp_path is not None
            and temp_path.exists()
        ):
            temp_path.unlink()

    return {
        str(key): str(value)
        for key, value in aliases.items()
    }


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

    try:
        with config_file.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(
            f"Invalid TOML in {config_file}: {exc}"
        ) from exc

    url = data.get("url")

    if not url:
        raise ConfigError("Missing 'url' in config.toml")

    token = credentials_file.read_text().strip()

    if not token:
        raise ConfigError("Credentials file is empty")

    aliases = data.get("aliases", {})
    binary_sensor_states = data.get(
        "binary_sensor_states",
        {},
    )

    if not isinstance(binary_sensor_states, dict):
        raise ConfigError(
            "'binary_sensor_states' must be a TOML table"
        )

    for device_class, mapping in binary_sensor_states.items():
        if not isinstance(mapping, dict):
            raise ConfigError(
                f"binary_sensor_states.{device_class} must be a TOML table"
            )

        for state_name, label in mapping.items():
            if state_name not in {"on", "off"}:
                raise ConfigError(
                    f"Unsupported binary sensor state mapping: "
                    f"{device_class}.{state_name}"
                )

            if not isinstance(label, str):
                raise ConfigError(
                    f"binary_sensor_states.{device_class}.{state_name} "
                    f"must be a string"
                )

    return Config(
        url=url.rstrip("/"),
        token=token,
        aliases=aliases,
        binary_sensor_states=binary_sensor_states,
    )

import time

import typer

from rich.console import Console
from rich.table import Table

from hactl.client import (
    HomeAssistantClient,
    HomeAssistantError,
)
from hactl.config import (
    ConfigError,
    load_config,
)


app = typer.Typer(
    help="Command-line interface for Home Assistant."
)

console = Console()


def get_client():
    try:
        config = load_config()
    except ConfigError as exc:
        console.print(
            f"[red]Configuration error:[/red] {exc}"
        )
        raise typer.Exit(1)

    client = HomeAssistantClient(
        config.url,
        config.token,
    )

    return config, client


def resolve_entity(name: str, aliases: dict[str, str]) -> str:
    return aliases.get(name, name)


def entity_domain(entity_id: str) -> str:
    if "." not in entity_id:
        raise ValueError(
            f"Invalid entity ID: {entity_id}"
        )

    return entity_id.split(".", 1)[0]


def format_state_value(
    state: dict,
    binary_sensor_states: dict[str, dict[str, str]] | None = None,
) -> str:
    value = str(state.get("state", ""))
    attributes = state.get(
        "attributes",
        {},
    )

    entity_id = str(state.get("entity_id", ""))

    if (
        entity_id.startswith("binary_sensor.")
        and value in {"on", "off"}
        and binary_sensor_states
    ):
        device_class = attributes.get("device_class")
        mapping = None

        if device_class:
            mapping = binary_sensor_states.get(
                str(device_class)
            )

        if mapping is None:
            mapping = binary_sensor_states.get("default")

        if mapping:
            value = mapping.get(value, value)

    unit = attributes.get("unit_of_measurement")

    if unit:
        return f"{value} {unit}"

    return value


def get_device_class(state: dict) -> str | None:
    return state.get(
        "attributes",
        {},
    ).get("device_class")


def wait_for_state(
    client: HomeAssistantClient,
    entity_id: str,
    expected_state: str,
    timeout: float = 2.0,
    interval: float = 0.1,
) -> tuple[dict, bool]:
    deadline = time.monotonic() + timeout
    state = client.get_state(entity_id)

    while True:
        if state.get("state") == expected_state:
            return state, True

        if time.monotonic() >= deadline:
            return state, False

        time.sleep(interval)
        state = client.get_state(entity_id)


def get_brightness_percent(state: dict) -> int | None:
    attributes = state.get(
        "attributes",
        {},
    )

    brightness = attributes.get("brightness")

    if brightness is not None:
        return round(
            brightness / 255 * 100
        )

    if state.get("state") == "off":
        return 0

    return None


def wait_for_brightness(
    client: HomeAssistantClient,
    entity_id: str,
    target_percent: int,
    timeout: float = 2.0,
    interval: float = 0.1,
) -> tuple[dict, bool]:
    deadline = time.monotonic() + timeout
    state = client.get_state(entity_id)

    while True:
        actual_percent = get_brightness_percent(state)

        if target_percent == 0:
            if state.get("state") == "off":
                return state, True
        elif (
            state.get("state") == "on"
            and actual_percent is not None
            and abs(actual_percent - target_percent) <= 1
        ):
            return state, True

        if time.monotonic() >= deadline:
            return state, False

        time.sleep(interval)
        state = client.get_state(entity_id)


def call_entity_service(
    name: str,
    service: str,
):
    config, client = get_client()

    entity_id = resolve_entity(
        name,
        config.aliases,
    )

    try:
        domain = entity_domain(entity_id)
        current_state = client.get_state(entity_id)
        current_value = current_state.get("state")

        expected_state = None

        if service == "turn_on":
            expected_state = "on"
        elif service == "turn_off":
            expected_state = "off"
        elif service == "toggle" and current_value in {"on", "off"}:
            expected_state = (
                "off"
                if current_value == "on"
                else "on"
            )

        client.call_service(
            domain,
            service,
            entity_id,
        )

        if expected_state is not None:
            state, confirmed = wait_for_state(
                client,
                entity_id,
                expected_state,
            )
        else:
            state = client.get_state(entity_id)
            confirmed = True

        friendly_name = state.get(
            "attributes",
            {},
        ).get(
            "friendly_name",
            entity_id,
        )

        if confirmed:
            console.print(
                f"[green]✓[/green] "
                f"{friendly_name} "
                f"({entity_id}) → "
                f"{state['state']}"
            )
        else:
            console.print(
                f"[yellow]Warning:[/yellow] "
                f"Home Assistant accepted the command, but "
                f"{friendly_name} ({entity_id}) still reports "
                f"{state['state']}."
            )

    except (
        HomeAssistantError,
        ValueError,
    ) as exc:
        console.print(
            f"[red]Error:[/red] {exc}"
        )
        raise typer.Exit(1)

    finally:
        client.close()


@app.command()
def status(name: str):
    """Show the state of an entity."""

    config, client = get_client()

    entity_id = resolve_entity(
        name,
        config.aliases,
    )

    try:
        state = client.get_state(entity_id)

        attributes = state.get(
            "attributes",
            {},
        )

        friendly_name = attributes.get(
            "friendly_name",
            entity_id,
        )

        console.print(
            f"[bold]{friendly_name}[/bold]"
        )

        console.print(
            f"Entity: {entity_id}"
        )

        console.print(
            f"State:  {format_state_value(state, config.binary_sensor_states)}"
        )

        device_class = attributes.get("device_class")

        if device_class:
            console.print(
                f"Device class: {device_class}"
            )

        if "brightness" in attributes:
            brightness = attributes["brightness"]

            percent = round(
                brightness / 255 * 100
            )

            console.print(
                f"Brightness: {percent}%"
            )

    except HomeAssistantError as exc:
        console.print(
            f"[red]Error:[/red] {exc}"
        )
        raise typer.Exit(1)

    finally:
        client.close()


@app.command()
def on(name: str):
    """Turn an entity on."""

    call_entity_service(
        name,
        "turn_on",
    )


@app.command()
def off(name: str):
    """Turn an entity off."""

    call_entity_service(
        name,
        "turn_off",
    )


@app.command()
def toggle(name: str):
    """Toggle an entity."""

    call_entity_service(
        name,
        "toggle",
    )


@app.command()
def brightness(name: str, percent: int):
    """Set light brightness from 0 to 100 percent."""

    if percent < 0 or percent > 100:
        console.print(
            "[red]Error:[/red] Brightness must be between 0 and 100."
        )
        raise typer.Exit(1)

    config, client = get_client()

    entity_id = resolve_entity(
        name,
        config.aliases,
    )

    try:
        if entity_domain(entity_id) != "light":
            raise ValueError(
                f"{entity_id} is not a light entity"
            )

        current_state = client.get_state(entity_id)
        current_attributes = current_state.get(
            "attributes",
            {},
        )

        supported_color_modes = set(
            current_attributes.get(
                "supported_color_modes",
                [],
            )
            or []
        )

        if supported_color_modes == {"onoff"}:
            raise ValueError(
                f"{entity_id} does not support brightness control"
            )

        if percent == 0:
            client.call_service(
                "light",
                "turn_off",
                entity_id,
            )
        else:
            client.call_service(
                "light",
                "turn_on",
                entity_id,
                {
                    "brightness_pct": percent,
                },
            )

        state, confirmed = wait_for_brightness(
            client,
            entity_id,
            percent,
        )

        attributes = state.get(
            "attributes",
            {},
        )

        friendly_name = attributes.get(
            "friendly_name",
            entity_id,
        )

        actual_percent = get_brightness_percent(state)

        if confirmed:
            console.print(
                f"[green]✓[/green] "
                f"{friendly_name} "
                f"({entity_id}) → "
                f"{state['state']}, "
                f"brightness {actual_percent}%"
            )
        else:
            reported = (
                f", brightness {actual_percent}%"
                if actual_percent is not None
                else ""
            )

            console.print(
                f"[yellow]Warning:[/yellow] "
                f"Home Assistant accepted the command, but "
                f"{friendly_name} ({entity_id}) still reports "
                f"{state['state']}{reported}."
            )

    except (
        HomeAssistantError,
        ValueError,
    ) as exc:
        console.print(
            f"[red]Error:[/red] {exc}"
        )
        raise typer.Exit(1)

    finally:
        client.close()


@app.command()
def find(search: str):
    """Search Home Assistant entities."""

    config, client = get_client()

    try:
        states = client.get_states()

        search_lower = search.lower()

        matches = []

        for state in states:
            entity_id = state["entity_id"]
            attributes = state.get(
                "attributes",
                {},
            )

            friendly_name = attributes.get(
                "friendly_name",
                "",
            )
            device_class = attributes.get(
                "device_class",
                "",
            )
            unit = attributes.get(
                "unit_of_measurement",
                "",
            )

            searchable = " ".join(
                str(value)
                for value in (
                    entity_id,
                    friendly_name,
                    device_class,
                    unit,
                )
                if value
            ).lower()

            if search_lower in searchable:
                matches.append(state)

        table = Table()

        table.add_column("Entity")
        table.add_column("State")
        table.add_column("Name")

        for state in matches:
            table.add_row(
                state["entity_id"],
                format_state_value(
                    state,
                    config.binary_sensor_states,
                ),
                state.get(
                    "attributes",
                    {},
                ).get(
                    "friendly_name",
                    "",
                ),
            )

        console.print(table)

    except HomeAssistantError as exc:
        console.print(
            f"[red]Error:[/red] {exc}"
        )
        raise typer.Exit(1)

    finally:
        client.close()


@app.command()
def tui():
    """Open the interactive terminal interface."""

    try:
        config = load_config()
    except ConfigError as exc:
        console.print(
            f"[red]Configuration error:[/red] {exc}"
        )
        raise typer.Exit(1)

    from hactl.tui import run_tui

    run_tui(config)


@app.command()
def aliases():
    """List configured aliases."""

    try:
        config = load_config()
    except ConfigError as exc:
        console.print(
            f"[red]Configuration error:[/red] {exc}"
        )
        raise typer.Exit(1)

    table = Table()

    table.add_column("Alias")
    table.add_column("Entity")

    for alias, entity_id in sorted(
        config.aliases.items(),
        key=lambda item: item[0].casefold(),
    ):
        table.add_row(
            alias,
            entity_id,
        )

    console.print(table)


@app.command()
def entities(
    domain: str | None = typer.Option(
        None,
        "--domain",
        "-d",
        help="Only list entities from this Home Assistant domain, e.g. light.",
    ),
    device_class: str | None = typer.Option(
        None,
        "--class",
        "-c",
        help="Only list entities with this device class, e.g. temperature.",
    ),
):
    """List Home Assistant entities, optionally filtered by domain or class."""

    config, client = get_client()

    try:
        states = client.get_states()

        if domain:
            normalized_domain = (
                domain.lower()
                .removesuffix(".*")
                .removesuffix(".")
            )

            states = [
                state
                for state in states
                if state["entity_id"].lower().startswith(
                    f"{normalized_domain}."
                )
            ]

        if device_class:
            normalized_class = device_class.lower()

            states = [
                state
                for state in states
                if str(
                    state.get(
                        "attributes",
                        {},
                    ).get(
                        "device_class",
                        "",
                    )
                ).lower() == normalized_class
            ]

        table = Table()

        table.add_column("Entity")
        table.add_column("State")
        table.add_column("Name")

        for state in sorted(
            states,
            key=lambda item: item["entity_id"],
        ):
            table.add_row(
                state["entity_id"],
                format_state_value(
                    state,
                    config.binary_sensor_states,
                ),
                state.get(
                    "attributes",
                    {},
                ).get(
                    "friendly_name",
                    "",
                ),
            )

        console.print(table)

    except HomeAssistantError as exc:
        console.print(
            f"[red]Error:[/red] {exc}"
        )
        raise typer.Exit(1)

    finally:
        client.close()


if __name__ == "__main__":
    app()

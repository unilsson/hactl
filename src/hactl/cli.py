import time
from typing import Annotated

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
    remove_alias,
    set_alias,
)


app = typer.Typer(
    help="Command-line interface for Home Assistant."
)

console = Console()


def complete_alias(incomplete: str) -> list[str]:
    """Return configured aliases for shell completion."""

    try:
        config = load_config()
    except ConfigError:
        return []

    return [
        alias
        for alias in sorted(
            config.aliases,
            key=str.casefold,
        )
        if alias.casefold().startswith(
            incomplete.casefold()
        )
    ]


AliasName = Annotated[
    str,
    typer.Argument(
        autocompletion=complete_alias,
    ),
]


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


def resolve_area(name: str, areas: list[dict]) -> dict:
    normalized_name = name.casefold()

    direct_matches = [
        area
        for area in areas
        if str(area.get("area_id", "")).casefold()
        == normalized_name
        or str(area.get("name", "")).casefold()
        == normalized_name
    ]

    if len(direct_matches) == 1:
        return direct_matches[0]

    alias_matches = [
        area
        for area in areas
        if normalized_name
        in {
            str(alias).casefold()
            for alias in area.get("aliases", [])
        }
    ]

    if len(alias_matches) == 1:
        return alias_matches[0]

    if len(direct_matches) + len(alias_matches) > 1:
        raise ValueError(
            f"Area '{name}' is ambiguous."
        )

    raise ValueError(
        f"Unknown area: {name}. Run 'hactl areas' to list available areas."
    )


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

    if value == "unavailable":
        return "⚠ unavailable"

    if value == "unknown":
        return "? unknown"

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


def action_service_for_domain(domain: str) -> str:
    services = {
        "scene": "turn_on",
        "script": "turn_on",
        "automation": "trigger",
    }

    try:
        return services[domain]
    except KeyError as exc:
        raise ValueError(
            f"{domain} entities cannot be run; expected scene, script, or automation"
        ) from exc


def list_action_domain(domain: str) -> None:
    config, client = get_client()

    try:
        states = [
            state
            for state in client.get_states()
            if state["entity_id"].startswith(
                f"{domain}."
            )
        ]

        table = Table()
        table.add_column("Entity")
        table.add_column("State")
        table.add_column("Name")
        table.add_column("Last triggered")

        for state in sorted(
            states,
            key=lambda item: item["entity_id"],
        ):
            attributes = state.get(
                "attributes",
                {},
            )

            table.add_row(
                state["entity_id"],
                format_state_value(
                    state,
                    config.binary_sensor_states,
                ),
                str(
                    attributes.get(
                        "friendly_name",
                        "",
                    )
                ),
                str(
                    attributes.get(
                        "last_triggered",
                        "",
                    )
                    or ""
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
def status(name: AliasName):
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

        if entity_id.startswith("light."):
            percent = get_brightness_percent(state)

            if percent is not None:
                console.print(
                    f"Brightness: {percent}%"
                )

        last_triggered = attributes.get(
            "last_triggered"
        )

        if last_triggered:
            console.print(
                f"Last triggered: {last_triggered}"
            )

    except HomeAssistantError as exc:
        console.print(
            f"[red]Error:[/red] {exc}"
        )
        raise typer.Exit(1)

    finally:
        client.close()


@app.command()
def on(name: AliasName):
    """Turn an entity on."""

    call_entity_service(
        name,
        "turn_on",
    )


@app.command()
def off(name: AliasName):
    """Turn an entity off."""

    call_entity_service(
        name,
        "turn_off",
    )


@app.command()
def toggle(name: AliasName):
    """Toggle an entity."""

    call_entity_service(
        name,
        "toggle",
    )


@app.command()
def brightness(name: AliasName, percent: int):
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
def run(name: AliasName):
    """Run a scene, script, or automation."""

    config, client = get_client()
    entity_id = resolve_entity(
        name,
        config.aliases,
    )

    try:
        domain = entity_domain(entity_id)
        service = action_service_for_domain(
            domain
        )
        before = client.get_state(entity_id)
        friendly_name = before.get(
            "attributes",
            {},
        ).get(
            "friendly_name",
            entity_id,
        )

        client.call_service(
            domain,
            service,
            entity_id,
        )

        console.print(
            f"[green]✓[/green] "
            f"{friendly_name} ({entity_id}) → "
            f"{service} requested"
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
def scenes():
    """List Home Assistant scenes."""

    list_action_domain("scene")


@app.command()
def scripts():
    """List Home Assistant scripts."""

    list_action_domain("script")


@app.command()
def automations():
    """List Home Assistant automations."""

    list_action_domain("automation")


@app.command()
def automation(
    action: str,
    name: AliasName,
):
    """Inspect or control one automation."""

    normalized_action = action.casefold()

    if normalized_action not in {
        "status",
        "enable",
        "disable",
        "toggle",
        "trigger",
    }:
        console.print(
            "[red]Error:[/red] ACTION must be one of: "
            "status, enable, disable, toggle, trigger"
        )
        raise typer.Exit(1)

    config, client = get_client()
    entity_id = resolve_entity(
        name,
        config.aliases,
    )

    try:
        if entity_domain(entity_id) != "automation":
            raise ValueError(
                f"{entity_id} is not an automation entity"
            )

        state = client.get_state(entity_id)
        attributes = state.get(
            "attributes",
            {},
        )
        friendly_name = attributes.get(
            "friendly_name",
            entity_id,
        )

        if normalized_action == "status":
            console.print(
                f"[bold]{friendly_name}[/bold]"
            )
            console.print(
                f"Entity: {entity_id}"
            )
            console.print(
                f"State:  {format_state_value(state, config.binary_sensor_states)}"
            )

            last_triggered = attributes.get(
                "last_triggered"
            )

            if last_triggered:
                console.print(
                    f"Last triggered: {last_triggered}"
                )

            return

        service_by_action = {
            "enable": "turn_on",
            "disable": "turn_off",
            "toggle": "toggle",
            "trigger": "trigger",
        }
        service = service_by_action[
            normalized_action
        ]

        current_value = state.get("state")
        expected_state = None

        if normalized_action == "enable":
            expected_state = "on"
        elif normalized_action == "disable":
            expected_state = "off"
        elif (
            normalized_action == "toggle"
            and current_value in {"on", "off"}
        ):
            expected_state = (
                "off"
                if current_value == "on"
                else "on"
            )

        client.call_service(
            "automation",
            service,
            entity_id,
        )

        if expected_state is None:
            console.print(
                f"[green]✓[/green] "
                f"{friendly_name} ({entity_id}) → "
                f"{service} requested"
            )
            return

        latest_state, confirmed = wait_for_state(
            client,
            entity_id,
            expected_state,
        )

        if confirmed:
            console.print(
                f"[green]✓[/green] "
                f"{friendly_name} ({entity_id}) → "
                f"{latest_state.get('state')}"
            )
        else:
            console.print(
                f"[yellow]Warning:[/yellow] "
                f"Home Assistant accepted the command, but "
                f"{friendly_name} ({entity_id}) still reports "
                f"{latest_state.get('state')}."
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


@app.command("alias")
def alias_command(
    alias: str,
    entity_id: str,
):
    """Create or change an alias."""

    try:
        aliases = set_alias(
            alias,
            entity_id,
        )
    except ConfigError as exc:
        console.print(
            f"[red]Configuration error:[/red] {exc}"
        )
        raise typer.Exit(1)

    normalized_alias = alias.strip()
    console.print(
        f"[green]✓[/green] Alias '{normalized_alias}' → "
        f"{aliases[normalized_alias]}"
    )


@app.command()
def unalias(alias: AliasName):
    """Remove a configured alias."""

    try:
        remove_alias(alias)
    except ConfigError as exc:
        console.print(
            f"[red]Configuration error:[/red] {exc}"
        )
        raise typer.Exit(1)

    console.print(
        f"[green]✓[/green] Removed alias '{alias}'"
    )


@app.command()
def aliases(
    check: bool = typer.Option(
        False,
        "--check",
        help=(
            "Check whether configured alias targets still exist "
            "in Home Assistant."
        ),
    ),
):
    """List configured aliases."""

    try:
        config = load_config()
    except ConfigError as exc:
        console.print(
            f"[red]Configuration error:[/red] {exc}"
        )
        raise typer.Exit(1)

    state_by_entity: dict[str, dict] = {}
    client = None

    if check:
        client = HomeAssistantClient(
            config.url,
            config.token,
        )

        try:
            states = client.get_states()
            state_by_entity = {
                state["entity_id"]: state
                for state in states
            }
        except HomeAssistantError as exc:
            console.print(
                f"[red]Error:[/red] {exc}"
            )
            raise typer.Exit(1)
        finally:
            client.close()

    table = Table()

    table.add_column("Alias")
    table.add_column("Entity")

    if check:
        table.add_column("Status")

    for alias, entity_id in sorted(
        config.aliases.items(),
        key=lambda item: item[0].casefold(),
    ):
        row = [
            alias,
            entity_id,
        ]

        if check:
            state = state_by_entity.get(
                entity_id
            )

            if state is None:
                status_value = "[red]missing[/red]"
            elif state.get("state") == "unavailable":
                status_value = "[yellow]unavailable[/yellow]"
            elif state.get("state") == "unknown":
                status_value = "[yellow]unknown[/yellow]"
            else:
                status_value = "[green]ok[/green]"

            row.append(status_value)

        table.add_row(*row)

    console.print(table)


@app.command()
def areas():
    """List Home Assistant areas."""

    _, client = get_client()

    try:
        area_entries = client.get_areas()

        table = Table()
        table.add_column("Name")
        table.add_column("Area ID")

        for area in sorted(
            area_entries,
            key=lambda item: str(
                item.get("name", "")
            ).casefold(),
        ):
            table.add_row(
                str(area.get("name", "")),
                str(area.get("area_id", "")),
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
def devices(
    area: str = typer.Option(
        ...,
        "--area",
        "-a",
        help=(
            "Only list devices assigned directly to this "
            "Home Assistant area (name or area ID)."
        ),
    ),
):
    """List devices assigned to a Home Assistant area."""

    _, client = get_client()

    try:
        area_entries, device_entries = (
            client.get_areas_and_devices()
        )

        selected_area = resolve_area(
            area,
            area_entries,
        )

        area_id = selected_area.get("area_id")
        area_name = selected_area.get(
            "name",
            area_id,
        )

        matching_devices = [
            device
            for device in device_entries
            if device.get("area_id") == area_id
        ]

        console.print(
            f"[bold]{area_name}[/bold] "
            f"([dim]{area_id}[/dim])"
        )

        if not matching_devices:
            console.print(
                "[yellow]No devices are assigned directly "
                "to this area.[/yellow]"
            )
            return

        table = Table()
        table.add_column("Name")
        table.add_column("Manufacturer")
        table.add_column("Model")
        table.add_column("Device ID")

        for device in sorted(
            matching_devices,
            key=lambda item: str(
                item.get("name_by_user")
                or item.get("name")
                or item.get("id")
                or ""
            ).casefold(),
        ):
            table.add_row(
                str(
                    device.get("name_by_user")
                    or device.get("name")
                    or device.get("id")
                    or ""
                ),
                str(
                    device.get("manufacturer")
                    or ""
                ),
                str(
                    device.get("model")
                    or ""
                ),
                str(device.get("id") or ""),
            )

        console.print(table)

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
    aliased: bool = typer.Option(
        False,
        "--aliased",
        help="Only list entities configured under [aliases].",
    ),
):
    """List Home Assistant entities with optional filters."""

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

        alias_by_entity = {
            entity_id: alias
            for alias, entity_id in config.aliases.items()
        }

        if aliased:
            states = [
                state
                for state in states
                if state["entity_id"] in alias_by_entity
            ]

        table = Table()

        if aliased:
            table.add_column("Alias")

        table.add_column("Entity")
        table.add_column("State")
        table.add_column("Name")

        for state in sorted(
            states,
            key=lambda item: item["entity_id"],
        ):
            row = []

            if aliased:
                row.append(
                    alias_by_entity.get(
                        state["entity_id"],
                        "",
                    )
                )

            row.extend(
                [
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
                ]
            )

            table.add_row(*row)

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

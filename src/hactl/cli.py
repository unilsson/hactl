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

        client.call_service(
            domain,
            service,
            entity_id,
        )

        state = client.get_state(entity_id)

        friendly_name = state.get(
            "attributes",
            {},
        ).get(
            "friendly_name",
            entity_id,
        )

        console.print(
            f"[green]✓[/green] "
            f"{friendly_name} "
            f"({entity_id}) → "
            f"{state['state']}"
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
            f"State:  {state['state']}"
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
def find(search: str):
    """Search Home Assistant entities."""

    _, client = get_client()

    try:
        states = client.get_states()

        search_lower = search.lower()

        matches = []

        for state in states:
            entity_id = state["entity_id"]

            friendly_name = state.get(
                "attributes",
                {},
            ).get(
                "friendly_name",
                "",
            )

            if (
                search_lower in entity_id.lower()
                or search_lower in friendly_name.lower()
            ):
                matches.append(state)

        table = Table()

        table.add_column("Entity")
        table.add_column("State")
        table.add_column("Name")

        for state in matches:
            table.add_row(
                state["entity_id"],
                str(state["state"]),
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
def entities():
    """List all Home Assistant entities."""

    _, client = get_client()

    try:
        states = client.get_states()

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
                str(state["state"]),
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

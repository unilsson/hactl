from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Static,
)

from hactl.client import HomeAssistantClient, HomeAssistantError
from hactl.config import Config
from hactl.cli import (
    entity_domain,
    format_state_value,
    get_brightness_percent,
    wait_for_brightness,
    wait_for_state,
)


class HactlApp(App):
    """Interactive terminal interface for Home Assistant."""

    TITLE = "hactl"

    CSS = """
    Screen {
        layout: vertical;
    }

    #search {
        margin: 1 1 0 1;
    }

    #filters {
        height: auto;
        margin: 0 1;
    }

    #filters Button {
        margin-right: 1;
    }

    #entities {
        height: 1fr;
        margin: 0 1;
    }

    #details {
        height: auto;
        min-height: 7;
        margin: 1;
        padding: 1;
        border: round $accent;
    }

    #actions {
        height: auto;
        margin: 0 1;
    }

    #actions Button {
        margin-right: 1;
    }

    #status-bar {
        height: auto;
        margin: 0 1 1 1;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("/", "focus_search", "Search"),
        Binding("escape", "focus_list", "List"),
        Binding("r", "refresh", "Refresh"),
        Binding("space", "toggle_selected", "Toggle"),
        Binding("o", "turn_on_selected", "On"),
        Binding("f", "turn_off_selected", "Off"),
        Binding("+", "brightness_up", "Brightness +"),
        Binding("-", "brightness_down", "Brightness -"),
    ]

    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.client = HomeAssistantClient(
            config.url,
            config.token,
        )
        self.states: dict[str, dict] = {}
        self.search_query = ""
        self.domain_filter: str | None = None
        self.aliases_only = True
        self.selected_entity_id: str | None = None

        self.alias_by_entity = {
            entity_id: alias
            for alias, entity_id in config.aliases.items()
        }

    def compose(self) -> ComposeResult:
        yield Header()

        yield Input(
            placeholder="Search entity, name, alias or device class…",
            id="search",
        )

        with Horizontal(id="filters"):
            yield Button(
                "Aliased",
                id="filter-aliased",
                variant="primary",
            )
            yield Button("All", id="filter-all")
            yield Button("Lights", id="filter-light")
            yield Button("Sensors", id="filter-sensor")
            yield Button("Binary", id="filter-binary_sensor")
            yield Button("Switches", id="filter-switch")

        yield DataTable(id="entities")

        yield Static(
            "Select an entity to see details.",
            id="details",
        )

        with Horizontal(id="actions"):
            yield Button("On", id="action-on")
            yield Button("Off", id="action-off")
            yield Button("Toggle", id="action-toggle")
            yield Button("-10%", id="action-dim")
            yield Button("+10%", id="action-brighten")

        yield Static(
            "Ready",
            id="status-bar",
        )

        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#entities", DataTable)
        table.cursor_type = "row"
        table.add_columns(
            "Alias",
            "Entity",
            "State",
            "Name",
        )

        self.refresh_states()
        table.focus()

    def on_unmount(self) -> None:
        self.client.close()

    def set_status(self, message: str) -> None:
        self.query_one("#status-bar", Static).update(message)

    def visible_states(self) -> list[dict]:
        query = self.search_query.casefold().strip()

        visible = []

        for state in self.states.values():
            entity_id = state["entity_id"]

            if (
                self.aliases_only
                and entity_id not in self.alias_by_entity
            ):
                continue

            if self.domain_filter:
                if not entity_id.startswith(
                    f"{self.domain_filter}."
                ):
                    continue

            attributes = state.get(
                "attributes",
                {},
            )

            alias = self.alias_by_entity.get(
                entity_id,
                "",
            )
            friendly_name = attributes.get(
                "friendly_name",
                "",
            )
            device_class = attributes.get(
                "device_class",
                "",
            )

            searchable = " ".join(
                str(value)
                for value in (
                    alias,
                    entity_id,
                    friendly_name,
                    device_class,
                )
                if value
            ).casefold()

            if query and query not in searchable:
                continue

            visible.append(state)

        return sorted(
            visible,
            key=lambda item: (
                self.alias_by_entity.get(
                    item["entity_id"],
                    "",
                ).casefold(),
                item["entity_id"],
            ),
        )

    def refresh_states(
        self,
        selected_entity_id: str | None = None,
    ) -> None:
        try:
            states = self.client.get_states()
        except HomeAssistantError as exc:
            self.set_status(f"Error: {exc}")
            return

        self.states = {
            state["entity_id"]: state
            for state in states
        }

        if selected_entity_id:
            self.selected_entity_id = selected_entity_id

        self.refresh_table()

        visible_count = len(
            self.visible_states()
        )
        self.set_status(
            f"Loaded {len(self.states)} entities; "
            f"showing {visible_count} aliased entities"
        )

    def refresh_table(self) -> None:
        table = self.query_one("#entities", DataTable)
        table.clear(columns=False)

        visible = self.visible_states()

        for state in visible:
            entity_id = state["entity_id"]
            attributes = state.get(
                "attributes",
                {},
            )

            table.add_row(
                self.alias_by_entity.get(
                    entity_id,
                    "",
                ),
                entity_id,
                format_state_value(
                    state,
                    self.config.binary_sensor_states,
                ),
                attributes.get(
                    "friendly_name",
                    "",
                ),
                key=entity_id,
            )

        if not visible:
            self.selected_entity_id = None
            self.query_one("#details", Static).update(
                "No matching entities."
            )
            return

        visible_ids = {
            state["entity_id"]
            for state in visible
        }

        if self.selected_entity_id not in visible_ids:
            self.selected_entity_id = visible[0]["entity_id"]

        selected_row = table.get_row_index(
            self.selected_entity_id
        )
        table.move_cursor(
            row=selected_row,
            column=0,
            animate=False,
        )

        self.update_details()

    def update_details(self) -> None:
        details = self.query_one("#details", Static)

        if not self.selected_entity_id:
            details.update(
                "Select an entity to see details."
            )
            return

        state = self.states.get(
            self.selected_entity_id
        )

        if not state:
            details.update(
                "Selected entity is no longer available."
            )
            return

        entity_id = state["entity_id"]
        attributes = state.get(
            "attributes",
            {},
        )

        alias = self.alias_by_entity.get(
            entity_id
        )
        friendly_name = attributes.get(
            "friendly_name",
            entity_id,
        )
        device_class = attributes.get(
            "device_class",
        )
        brightness = get_brightness_percent(state)

        lines = [
            f"[bold]{friendly_name}[/bold]",
            f"Entity: {entity_id}",
            (
                "State:  "
                + format_state_value(
                    state,
                    self.config.binary_sensor_states,
                )
            ),
        ]

        if alias:
            lines.append(f"Alias: {alias}")

        if device_class:
            lines.append(
                f"Device class: {device_class}"
            )

        if entity_id.startswith("light.") and brightness is not None:
            lines.append(
                f"Brightness: {brightness}%"
            )

        details.update("\n".join(lines))

    def on_input_changed(
        self,
        event: Input.Changed,
    ) -> None:
        if event.input.id != "search":
            return

        self.search_query = event.value
        self.refresh_table()

    def on_data_table_row_highlighted(
        self,
        event: DataTable.RowHighlighted,
    ) -> None:
        if event.row_key is None:
            return

        self.selected_entity_id = str(
            event.row_key.value
        )
        self.update_details()

    def on_data_table_row_selected(
        self,
        event: DataTable.RowSelected,
    ) -> None:
        if event.row_key is None:
            return

        self.selected_entity_id = str(
            event.row_key.value
        )
        self.update_details()

    def on_button_pressed(
        self,
        event: Button.Pressed,
    ) -> None:
        button_id = event.button.id or ""

        if button_id.startswith("filter-"):
            filter_name = button_id.removeprefix(
                "filter-"
            )

            if filter_name == "aliased":
                self.aliases_only = True
                self.domain_filter = None
                label = "aliased entities"
            elif filter_name == "all":
                self.aliases_only = False
                self.domain_filter = None
                label = "all entities"
            else:
                self.aliases_only = False
                self.domain_filter = filter_name
                label = filter_name

            self.refresh_table()
            self.set_status(
                f"Filter: {label}"
            )
            return

        actions = {
            "action-on": "turn_on",
            "action-off": "turn_off",
            "action-toggle": "toggle",
        }

        if button_id in actions:
            self.call_selected_service(
                actions[button_id]
            )
            return

        if button_id == "action-dim":
            self.change_brightness(-10)
        elif button_id == "action-brighten":
            self.change_brightness(10)

    def selected_state(self) -> dict | None:
        if not self.selected_entity_id:
            self.set_status(
                "No entity selected"
            )
            return None

        state = self.states.get(
            self.selected_entity_id
        )

        if not state:
            self.set_status(
                "Selected entity is unavailable"
            )
            return None

        return state

    def call_selected_service(
        self,
        service: str,
    ) -> None:
        state = self.selected_state()

        if not state:
            return

        entity_id = state["entity_id"]
        domain = entity_domain(entity_id)

        if domain not in {
            "light",
            "switch",
        }:
            self.set_status(
                f"{entity_id} is read-only in the TUI MVP"
            )
            return

        current_value = state.get("state")
        expected_state = None

        if service == "turn_on":
            expected_state = "on"
        elif service == "turn_off":
            expected_state = "off"
        elif (
            service == "toggle"
            and current_value in {"on", "off"}
        ):
            expected_state = (
                "off"
                if current_value == "on"
                else "on"
            )

        try:
            self.client.call_service(
                domain,
                service,
                entity_id,
            )

            if expected_state is not None:
                latest_state, confirmed = wait_for_state(
                    self.client,
                    entity_id,
                    expected_state,
                )
                self.states[entity_id] = latest_state

                if not confirmed:
                    self.refresh_table()
                    self.set_status(
                        f"Command accepted, but {entity_id} "
                        f"still reports {latest_state.get('state')}"
                    )
                    return

        except HomeAssistantError as exc:
            self.set_status(f"Error: {exc}")
            return

        self.refresh_states(entity_id)
        self.set_status(
            f"{service} confirmed for {entity_id}"
        )

    def change_brightness(
        self,
        delta: int,
    ) -> None:
        state = self.selected_state()

        if not state:
            return

        entity_id = state["entity_id"]

        if entity_domain(entity_id) != "light":
            self.set_status(
                "Brightness is only available for lights"
            )
            return

        attributes = state.get(
            "attributes",
            {},
        )

        supported_color_modes = set(
            attributes.get(
                "supported_color_modes",
                [],
            )
            or []
        )

        if supported_color_modes == {"onoff"}:
            self.set_status(
                f"{entity_id} does not support brightness"
            )
            return

        current = get_brightness_percent(
            state
        )

        if current is None:
            current = 0

        target = max(
            0,
            min(
                100,
                current + delta,
            ),
        )

        try:
            if target == 0:
                self.client.call_service(
                    "light",
                    "turn_off",
                    entity_id,
                )
            else:
                self.client.call_service(
                    "light",
                    "turn_on",
                    entity_id,
                    {
                        "brightness_pct": target,
                    },
                )

            latest_state, confirmed = wait_for_brightness(
                self.client,
                entity_id,
                target,
            )
            self.states[entity_id] = latest_state

        except HomeAssistantError as exc:
            self.set_status(f"Error: {exc}")
            return

        if not confirmed:
            self.refresh_table()
            self.set_status(
                f"Brightness command accepted, but {entity_id} "
                "has not confirmed the target yet"
            )
            return

        self.refresh_states(entity_id)
        self.set_status(
            f"Brightness {target}% confirmed for {entity_id}"
        )

    def action_focus_search(self) -> None:
        self.query_one("#search", Input).focus()

    def action_focus_list(self) -> None:
        self.query_one("#entities", DataTable).focus()

    def action_refresh(self) -> None:
        self.refresh_states(
            self.selected_entity_id
        )

    def action_toggle_selected(self) -> None:
        self.call_selected_service("toggle")

    def action_turn_on_selected(self) -> None:
        self.call_selected_service("turn_on")

    def action_turn_off_selected(self) -> None:
        self.call_selected_service("turn_off")

    def action_brightness_up(self) -> None:
        self.change_brightness(10)

    def action_brightness_down(self) -> None:
        self.change_brightness(-10)


def run_tui(config: Config) -> None:
    HactlApp(config).run()

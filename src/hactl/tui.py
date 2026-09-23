from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Static,
)

from hactl.client import HomeAssistantClient, HomeAssistantError
from hactl.config import (
    Config,
    ConfigError,
    remove_alias,
    set_alias,
)
from hactl.cli import (
    entity_domain,
    format_state_value,
    get_brightness_percent,
    resolve_area,
    wait_for_brightness,
    wait_for_state,
)


class AliasScreen(ModalScreen[str | None]):
    """Dialog for adding or changing an hactl alias."""

    CSS = """
    AliasScreen {
        align: center middle;
    }

    #alias-dialog {
        grid-size: 2;
        grid-gutter: 1 2;
        grid-rows: auto auto auto 3;
        width: 64;
        height: auto;
        padding: 1 2;
        border: thick $background 80%;
        background: $surface;
    }

    #alias-title,
    #alias-entity,
    #alias-input,
    #alias-error {
        column-span: 2;
    }

    #alias-title {
        text-style: bold;
    }

    #alias-error {
        color: $error;
        min-height: 1;
    }

    #alias-dialog Button {
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        entity_id: str,
        current_alias: str | None,
        aliases: dict[str, str],
    ):
        super().__init__()
        self.entity_id = entity_id
        self.current_alias = current_alias or ""
        self.aliases = aliases

    def compose(self) -> ComposeResult:
        yield Grid(
            Label(
                "Add hactl alias",
                id="alias-title",
            ),
            Label(
                f"Entity: {self.entity_id}",
                id="alias-entity",
            ),
            Input(
                value=self.current_alias,
                placeholder="e.g. ute-temp",
                id="alias-input",
            ),
            Static(
                "",
                id="alias-error",
            ),
            Button(
                "Save",
                variant="primary",
                id="alias-save",
            ),
            Button(
                "Cancel",
                id="alias-cancel",
            ),
            id="alias-dialog",
        )

    def on_mount(self) -> None:
        alias_input = self.query_one(
            "#alias-input",
            Input,
        )
        alias_input.focus()
        alias_input.cursor_position = len(
            alias_input.value
        )

    def validate_alias(self) -> str | None:
        alias_input = self.query_one(
            "#alias-input",
            Input,
        )
        alias = alias_input.value.strip()
        error = self.query_one(
            "#alias-error",
            Static,
        )

        if not alias:
            error.update("Alias cannot be empty.")
            return None

        if "\n" in alias or "\r" in alias:
            error.update(
                "Alias cannot contain line breaks."
            )
            return None

        existing_entity = self.aliases.get(alias)

        if (
            existing_entity is not None
            and existing_entity != self.entity_id
        ):
            error.update(
                f"Alias '{alias}' is already used by "
                f"{existing_entity}."
            )
            return None

        return alias

    def submit_alias(self) -> None:
        alias = self.validate_alias()

        if alias is not None:
            self.dismiss(alias)

    def on_input_submitted(
        self,
        event: Input.Submitted,
    ) -> None:
        if event.input.id == "alias-input":
            self.submit_alias()

    def on_button_pressed(
        self,
        event: Button.Pressed,
    ) -> None:
        if event.button.id == "alias-save":
            self.submit_alias()
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class AreaScreen(ModalScreen[tuple[bool, str | None]]):
    """Dialog for assigning an entity to a Home Assistant area."""

    CSS = """
    AreaScreen {
        align: center middle;
    }

    #area-dialog {
        grid-size: 2;
        grid-gutter: 1 2;
        grid-rows: auto auto auto auto auto 3;
        width: 72;
        height: auto;
        padding: 1 2;
        border: thick $background 80%;
        background: $surface;
    }

    #area-title,
    #area-entity,
    #area-current,
    #area-input,
    #area-error {
        column-span: 2;
    }

    #area-title {
        text-style: bold;
    }

    #area-error {
        color: $error;
        min-height: 1;
    }

    #area-dialog Button {
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        entity_id: str,
        areas: list[dict],
        current_area_id: str | None,
        inherited_area_id: str | None,
    ):
        super().__init__()
        self.entity_id = entity_id
        self.areas = areas
        self.current_area_id = current_area_id
        self.inherited_area_id = inherited_area_id

    def area_name(
        self,
        area_id: str | None,
    ) -> str:
        if not area_id:
            return "none"

        for area in self.areas:
            if area.get("area_id") == area_id:
                return str(
                    area.get("name")
                    or area_id
                )

        return area_id

    def compose(self) -> ComposeResult:
        current_text = (
            f"{self.area_name(self.current_area_id)} "
            "(entity assignment)"
            if self.current_area_id
            else (
                f"{self.area_name(self.inherited_area_id)} "
                "(inherited from device)"
                if self.inherited_area_id
                else "none"
            )
        )

        input_value = (
            self.area_name(self.current_area_id)
            if self.current_area_id
            else ""
        )

        yield Grid(
            Label(
                "Assign Home Assistant area",
                id="area-title",
            ),
            Label(
                f"Entity: {self.entity_id}",
                id="area-entity",
            ),
            Label(
                f"Current area: {current_text}",
                id="area-current",
            ),
            Input(
                value=input_value,
                placeholder=(
                    "Area name or ID; blank clears entity override"
                ),
                id="area-input",
            ),
            Static(
                "",
                id="area-error",
            ),
            Button(
                "Save",
                variant="primary",
                id="area-save",
            ),
            Button(
                "Cancel",
                id="area-cancel",
            ),
            id="area-dialog",
        )

    def on_mount(self) -> None:
        area_input = self.query_one(
            "#area-input",
            Input,
        )
        area_input.focus()
        area_input.cursor_position = len(
            area_input.value
        )

    def submit_area(self) -> None:
        area_input = self.query_one(
            "#area-input",
            Input,
        )
        value = area_input.value.strip()

        if not value:
            self.dismiss(
                (
                    True,
                    None,
                )
            )
            return

        try:
            selected_area = resolve_area(
                value,
                self.areas,
            )
        except ValueError as exc:
            self.query_one(
                "#area-error",
                Static,
            ).update(str(exc))
            return

        self.dismiss(
            (
                True,
                str(
                    selected_area.get("area_id")
                ),
            )
        )

    def on_input_submitted(
        self,
        event: Input.Submitted,
    ) -> None:
        if event.input.id == "area-input":
            self.submit_area()

    def on_button_pressed(
        self,
        event: Button.Pressed,
    ) -> None:
        if event.button.id == "area-save":
            self.submit_area()
        else:
            self.dismiss(
                (
                    False,
                    None,
                )
            )

    def action_cancel(self) -> None:
        self.dismiss(
            (
                False,
                None,
            )
        )


class ConfirmRemoveAliasScreen(ModalScreen[bool]):
    """Confirm removal of an alias."""

    CSS = """
    ConfirmRemoveAliasScreen {
        align: center middle;
    }

    #confirm-dialog {
        grid-size: 2;
        grid-gutter: 1 2;
        grid-rows: auto 3;
        width: 64;
        height: auto;
        padding: 1 2;
        border: thick $background 80%;
        background: $surface;
    }

    #confirm-message {
        column-span: 2;
    }

    #confirm-dialog Button {
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        alias: str,
        entity_id: str,
    ):
        super().__init__()
        self.alias = alias
        self.entity_id = entity_id

    def compose(self) -> ComposeResult:
        yield Grid(
            Label(
                f"Remove alias '{self.alias}' from "
                f"{self.entity_id}?",
                id="confirm-message",
            ),
            Button(
                "Remove",
                variant="error",
                id="confirm-remove",
            ),
            Button(
                "Cancel",
                id="confirm-cancel",
            ),
            id="confirm-dialog",
        )

    def on_button_pressed(
        self,
        event: Button.Pressed,
    ) -> None:
        self.dismiss(
            event.button.id == "confirm-remove"
        )

    def action_cancel(self) -> None:
        self.dismiss(False)


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

    #filters,
    #action-filters {
        height: auto;
        margin: 0 1;
    }

    #filters Button,
    #action-filters Button {
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
        Binding("a", "alias_selected", "Alias"),
        Binding("d", "remove_alias_selected", "Remove alias"),
        Binding("m", "area_selected", "Area"),
        Binding("s", "cycle_sort", "Sort"),
        Binding("x", "run_selected", "Run"),
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
        self.sort_mode = "alias"
        self.selected_entity_id: str | None = None
        self.areas: list[dict] = []
        self.area_by_id: dict[str, dict] = {}
        self.devices: dict[str, dict] = {}
        self.entity_registry: dict[str, dict] = {}

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

        with Horizontal(id="action-filters"):
            yield Button("Scenes", id="filter-scene")
            yield Button("Scripts", id="filter-script")
            yield Button("Automations", id="filter-automation")

        yield DataTable(id="entities")

        yield Static(
            "Select an entity to see details.",
            id="details",
        )

        with Horizontal(id="actions"):
            yield Button("Run", id="action-run")
            yield Button("On", id="action-on")
            yield Button("Off", id="action-off")
            yield Button("Toggle", id="action-toggle")
            yield Button("Area", id="action-area")
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

        self.refresh_registry_data()
        self.refresh_states()
        table.focus()

    def on_unmount(self) -> None:
        self.client.close()

    def set_status(self, message: str) -> None:
        self.query_one("#status-bar", Static).update(message)

    def refresh_registry_data(self) -> None:
        try:
            areas, devices, entities = (
                self.client.get_registry_data()
            )
        except HomeAssistantError as exc:
            self.set_status(
                f"Could not load area registry: {exc}"
            )
            return

        self.areas = areas
        self.area_by_id = {
            str(area.get("area_id")): area
            for area in areas
            if area.get("area_id")
        }
        self.devices = {
            str(device.get("id")): device
            for device in devices
            if device.get("id")
        }
        self.entity_registry = {
            str(entity.get("entity_id")): entity
            for entity in entities
            if entity.get("entity_id")
        }

    def area_name(
        self,
        area_id: str | None,
    ) -> str | None:
        if not area_id:
            return None

        area = self.area_by_id.get(
            area_id
        )

        if not area:
            return area_id

        return str(
            area.get("name")
            or area_id
        )

    def entity_area_info(
        self,
        entity_id: str,
    ) -> tuple[str | None, str | None, str | None]:
        entry = self.entity_registry.get(
            entity_id
        )

        if not entry:
            return (
                None,
                None,
                None,
            )

        explicit_area_id = entry.get(
            "area_id"
        )

        if explicit_area_id:
            area_id = str(explicit_area_id)
            return (
                area_id,
                self.area_name(area_id),
                "entity",
            )

        device_id = entry.get(
            "device_id"
        )
        device = self.devices.get(
            str(device_id)
        ) if device_id else None
        device_area_id = (
            device.get("area_id")
            if device
            else None
        )

        if device_area_id:
            area_id = str(device_area_id)
            return (
                area_id,
                self.area_name(area_id),
                "device",
            )

        return (
            None,
            None,
            None,
        )

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

        def sort_key(item: dict):
            entity_id = item["entity_id"]
            attributes = item.get(
                "attributes",
                {},
            )
            alias = self.alias_by_entity.get(
                entity_id,
                "",
            )
            friendly_name = str(
                attributes.get(
                    "friendly_name",
                    "",
                )
            )
            state_value = format_state_value(
                item,
                self.config.binary_sensor_states,
            )

            if self.sort_mode == "name":
                return (
                    friendly_name.casefold(),
                    entity_id,
                )

            if self.sort_mode == "state":
                return (
                    state_value.casefold(),
                    entity_id,
                )

            if self.sort_mode == "entity":
                return (
                    entity_id.casefold(),
                    entity_id,
                )

            return (
                alias.casefold(),
                entity_id,
            )

        return sorted(
            visible,
            key=sort_key,
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
            f"showing {visible_count}"
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

        _, area_name, area_source = (
            self.entity_area_info(
                entity_id
            )
        )

        if area_name:
            source_label = (
                "entity"
                if area_source == "entity"
                else "device"
            )
            lines.append(
                f"Area: {area_name} ({source_label})"
            )
        else:
            lines.append(
                "Area: none"
            )

        if device_class:
            lines.append(
                f"Device class: {device_class}"
            )

        if entity_id.startswith("light.") and brightness is not None:
            lines.append(
                f"Brightness: {brightness}%"
            )

        last_triggered = attributes.get(
            "last_triggered"
        )

        if last_triggered:
            lines.append(
                f"Last triggered: {last_triggered}"
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

            for selector in (
                "#filters Button",
                "#action-filters Button",
            ):
                for button in self.query(
                    selector
                ):
                    button.variant = "default"

            self.query_one(
                f"#filter-{filter_name}",
                Button,
            ).variant = "primary"

            self.refresh_table()
            self.set_status(
                f"Filter: {label}"
            )
            return

        if button_id == "action-run":
            self.run_selected()
            return

        if button_id == "action-area":
            self.action_area_selected()
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
            "automation",
        }:
            self.set_status(
                f"{entity_id} does not support on/off/toggle in the TUI"
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

    def run_selected(self) -> None:
        state = self.selected_state()

        if not state:
            return

        entity_id = state["entity_id"]
        domain = entity_domain(entity_id)

        service_by_domain = {
            "scene": "turn_on",
            "script": "turn_on",
            "automation": "trigger",
        }

        service = service_by_domain.get(
            domain
        )

        if service is None:
            self.set_status(
                "Run is only available for scenes, scripts, and automations"
            )
            return

        try:
            self.client.call_service(
                domain,
                service,
                entity_id,
            )
        except HomeAssistantError as exc:
            self.set_status(f"Error: {exc}")
            return

        self.refresh_states(entity_id)
        self.set_status(
            f"{service} requested for {entity_id}"
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

    def action_alias_selected(self) -> None:
        state = self.selected_state()

        if not state:
            return

        entity_id = state["entity_id"]
        current_alias = self.alias_by_entity.get(
            entity_id
        )

        def alias_saved(
            alias: str | None,
        ) -> None:
            if alias is None:
                self.query_one(
                    "#entities",
                    DataTable,
                ).focus()
                return

            try:
                aliases = set_alias(
                    alias,
                    entity_id,
                )
            except ConfigError as exc:
                self.set_status(
                    f"Could not save alias: {exc}"
                )
                return

            self.config.aliases = aliases
            self.alias_by_entity = {
                target: alias_name
                for alias_name, target in aliases.items()
            }

            self.selected_entity_id = entity_id
            self.refresh_table()
            self.query_one(
                "#entities",
                DataTable,
            ).focus()
            self.set_status(
                f"Alias '{alias}' saved for {entity_id}"
            )

        self.push_screen(
            AliasScreen(
                entity_id,
                current_alias,
                self.config.aliases,
            ),
            alias_saved,
        )

    def action_remove_alias_selected(self) -> None:
        state = self.selected_state()

        if not state:
            return

        entity_id = state["entity_id"]
        alias = self.alias_by_entity.get(
            entity_id
        )

        if not alias:
            self.set_status(
                f"{entity_id} has no hactl alias"
            )
            return

        def alias_removed(
            confirmed: bool,
        ) -> None:
            if not confirmed:
                self.query_one(
                    "#entities",
                    DataTable,
                ).focus()
                return

            try:
                aliases = remove_alias(alias)
            except ConfigError as exc:
                self.set_status(
                    f"Could not remove alias: {exc}"
                )
                return

            self.config.aliases = aliases
            self.alias_by_entity = {
                target: alias_name
                for alias_name, target in aliases.items()
            }

            self.selected_entity_id = entity_id
            self.refresh_table()
            self.query_one(
                "#entities",
                DataTable,
            ).focus()
            self.set_status(
                f"Alias '{alias}' removed"
            )

        self.push_screen(
            ConfirmRemoveAliasScreen(
                alias,
                entity_id,
            ),
            alias_removed,
        )

    def action_area_selected(self) -> None:
        state = self.selected_state()

        if not state:
            return

        entity_id = state["entity_id"]
        entity_entry = self.entity_registry.get(
            entity_id
        )

        if entity_entry is None:
            self.set_status(
                f"{entity_id} is not present in the Home Assistant entity registry"
            )
            return

        explicit_area_id = entity_entry.get(
            "area_id"
        )
        device_id = entity_entry.get(
            "device_id"
        )
        device = self.devices.get(
            str(device_id)
        ) if device_id else None
        inherited_area_id = (
            device.get("area_id")
            if device
            else None
        )

        def area_saved(
            result: tuple[bool, str | None],
        ) -> None:
            confirmed, area_id = result

            if not confirmed:
                self.query_one(
                    "#entities",
                    DataTable,
                ).focus()
                return

            try:
                self.client.update_entity_area(
                    entity_id,
                    area_id,
                )
            except HomeAssistantError as exc:
                self.set_status(
                    f"Could not update area: {exc}"
                )
                return

            self.refresh_registry_data()
            self.selected_entity_id = entity_id
            self.update_details()
            self.query_one(
                "#entities",
                DataTable,
            ).focus()

            if area_id:
                self.set_status(
                    f"{entity_id} → "
                    f"{self.area_name(area_id) or area_id}"
                )
            else:
                _, effective_name, source = (
                    self.entity_area_info(
                        entity_id
                    )
                )

                if effective_name and source == "device":
                    self.set_status(
                        f"Entity area cleared; {entity_id} now inherits "
                        f"{effective_name} from its device"
                    )
                else:
                    self.set_status(
                        f"Entity area cleared for {entity_id}"
                    )

        self.push_screen(
            AreaScreen(
                entity_id,
                self.areas,
                (
                    str(explicit_area_id)
                    if explicit_area_id
                    else None
                ),
                (
                    str(inherited_area_id)
                    if inherited_area_id
                    else None
                ),
            ),
            area_saved,
        )

    def action_cycle_sort(self) -> None:
        sort_modes = [
            "alias",
            "name",
            "state",
            "entity",
        ]
        current_index = sort_modes.index(
            self.sort_mode
        )
        self.sort_mode = sort_modes[
            (current_index + 1) % len(sort_modes)
        ]

        self.refresh_table()
        self.set_status(
            f"Sort: {self.sort_mode}"
        )

    def action_focus_search(self) -> None:
        self.query_one("#search", Input).focus()

    def action_focus_list(self) -> None:
        self.query_one("#entities", DataTable).focus()

    def action_refresh(self) -> None:
        self.refresh_registry_data()
        self.refresh_states(
            self.selected_entity_id
        )

    def action_run_selected(self) -> None:
        self.run_selected()

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

# hactl

`hactl` is a small command-line and terminal user interface for Home Assistant.

The project is designed for fast day-to-day access to Home Assistant entities without having to open the full Home Assistant web UI. It provides:

- a CLI for inspecting and controlling entities
- aliases with short, human-friendly names
- sensor-aware output with units and device classes
- configurable human-readable binary sensor states
- brightness control for dimmable lights
- an interactive Textual TUI
- complete alias lifecycle from both CLI and TUI
- alias health checks against Home Assistant
- alias-aware shell completion
- scenes, scripts, and automations as first-class runnable entities
- local configuration and credentials kept outside the Git repository

The current implementation is at the Sprint 7 scenes/scripts/automations stage.

## Requirements

- Python 3.11 or newer
- a reachable Home Assistant instance
- a Home Assistant long-lived access token

The Python dependencies are installed from `pyproject.toml` and currently include:

- `httpx`
- `rich`
- `typer`
- `textual`
- `tomlkit`

## Installation

Clone the repository:

```bash
git clone https://github.com/unilsson/hactl.git
cd hactl
```

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install hactl in editable mode:

```bash
pip install -e .
```

You can now run:

```bash
hactl --help
```

### Using hactl in a new shell

The virtual environment must be activated in each new shell:

```bash
cd ~/Development/hactl
source .venv/bin/activate
```

After that, `hactl` is available in that shell.

## Configuration

hactl deliberately keeps Home Assistant credentials outside the repository.

By default, configuration is stored in:

```text
~/.config/hactl/
├── config.toml
└── credentials
```

If `XDG_CONFIG_HOME` is set, hactl instead uses:

```text
$XDG_CONFIG_HOME/hactl/
```

Create the directory:

```bash
mkdir -p ~/.config/hactl
```

### Home Assistant URL

Create `~/.config/hactl/config.toml`:

```toml
url = "http://homeassistant.local:8123"
```

The trailing slash is optional.

You can also use an IP address or another hostname as long as the machine running hactl can reach Home Assistant.

### Credentials

Put the Home Assistant long-lived access token in:

```text
~/.config/hactl/credentials
```

The file must contain only the token.

Protect it with:

```bash
chmod 600 ~/.config/hactl/credentials
```

hactl checks the file permissions at startup and refuses to use a credentials file that is accessible by group or other users.

The token is never intended to be stored in the repository or passed as a command-line argument.

## Security model

The repository is intended to be safe to keep public.

Secrets and machine-local configuration are excluded by `.gitignore`, including:

```text
.env
.env.*
credentials
credentials.*
*.token
*.secret
*.key
config.toml
local.toml
```

The Python virtual environment is also ignored.

Even though these files are ignored, the recommended design is still to keep the actual hactl configuration under `~/.config/hactl/`, completely outside the repository.

## Aliases

Aliases let you use short names instead of full Home Assistant entity IDs.

Example:

```toml
url = "http://homeassistant.local:8123"

[aliases]
veranda = "light.veranda"
"dagbädden" = "light.example_dagbadd"
"vardagsrum-temp" = "sensor.vardagsrum_temperature"
"kök-fukt" = "sensor.kok_humidity"
"ytterdörr" = "binary_sensor.ytterdorr"
```

You can then write:

```bash
hactl status veranda
hactl on veranda
hactl status vardagsrum-temp
```

instead of using the full entity ID.

Commands also accept a full entity ID directly:

```bash
hactl status sensor.vardagsrum_temperature
```

For sensor aliases, a useful convention is:

```text
<place>-<type>
```

Examples:

```text
vardagsrum-temp
ute-temp
kök-fukt
garage-effekt
```

Aliases containing characters such as `å`, `ä`, and `ö` should be quoted in TOML.

### Managing aliases from the CLI

Create or change an alias:

```bash
hactl alias veranda light.veranda
```

Remove an alias:

```bash
hactl unalias veranda
```

When an entity is assigned a new alias, any previous alias pointing to that same entity is removed automatically.

### Listing aliases

```bash
hactl aliases
```

Validate every configured alias against the current Home Assistant entity list:

```bash
hactl aliases --check
```

The status column reports:

- `ok` when the entity exists and has a normal state
- `unavailable` when Home Assistant currently reports it as unavailable
- `unknown` when Home Assistant reports an unknown state
- `missing` when the configured entity ID no longer exists

Example output:

```text
Alias              Entity
──────────────────────────────────────────────
veranda            light.veranda
vardagsrum-temp    sensor.vardagsrum_temperature
ytterdörr           binary_sensor.ytterdorr
```

## Command reference

The complete CLI currently consists of:

| Command | Syntax | Description |
|---|---|---|
| Status | `hactl status NAME` | Show the current state of one entity |
| On | `hactl on NAME` | Call `turn_on` for the entity |
| Off | `hactl off NAME` | Call `turn_off` for the entity |
| Toggle | `hactl toggle NAME` | Call `toggle` for the entity |
| Brightness | `hactl brightness NAME PERCENT` | Set a light to 0-100% |
| Find | `hactl find SEARCH` | Search Home Assistant entities |
| Entities | `hactl entities [OPTIONS]` | List entities |
| Areas | `hactl areas` | List Home Assistant areas |
| Devices | `hactl devices --area AREA` | List devices assigned directly to an area |
| Entity area | `hactl entity-area NAME [AREA]` | Show, assign, reassign, or clear an entity's area |
| Alias | `hactl alias ALIAS ENTITY_ID` | Create or change an alias |
| Unalias | `hactl unalias ALIAS` | Remove an alias |
| Aliases | `hactl aliases [--check]` | List aliases and optionally validate targets |
| Run | `hactl run NAME` | Activate a scene, run a script, or trigger an automation |
| Scenes | `hactl scenes` | List scenes |
| Scripts | `hactl scripts` | List scripts |
| Automations | `hactl automations` | List automations |
| Automation | `hactl automation ACTION NAME` | Inspect, enable, disable, toggle, or trigger an automation |
| TUI | `hactl tui` | Start the interactive terminal interface |

Every command has generated Typer help:

```bash
hactl --help
hactl status --help
hactl entities --help
hactl brightness --help
```

### `status`

Syntax:

```bash
hactl status NAME
```

`NAME` can be an alias or a full Home Assistant entity ID.

Example:

```bash
hactl status veranda
```

For a light, output can include brightness:

```text
Veranda
Entity: light.veranda
State:  on
Brightness: 50%
```

For sensors, units and device class are shown when Home Assistant provides them:

```bash
hactl status vardagsrum-temp
```

Example:

```text
Vardagsrum temperatur
Entity: sensor.vardagsrum_temperature
State:  21.7 °C
Device class: temperature
```

### `on`

Syntax:

```bash
hactl on NAME
```

Example:

```bash
hactl on veranda
```

hactl resolves the alias, calls the entity domain's `turn_on` service, then polls Home Assistant briefly to confirm the reported state.

### `off`

Syntax:

```bash
hactl off NAME
```

Example:

```bash
hactl off veranda
```

### `toggle`

Syntax:

```bash
hactl toggle NAME
```

Example:

```bash
hactl toggle veranda
```

For entities reporting a normal `on` or `off` state, hactl waits for the expected opposite state after sending the command.

### `brightness`

Syntax:

```bash
hactl brightness NAME PERCENT
```

Examples:

```bash
hactl brightness veranda 50
hactl brightness dagbädden 25
hactl brightness veranda 0
```

Rules:

- `PERCENT` must be between `0` and `100`
- the entity must be in the `light` domain
- lights that explicitly report only the `onoff` color mode are rejected as non-dimmable
- `0` turns the light off
- values above `0` use Home Assistant's `brightness_pct`
- hactl polls Home Assistant to confirm the resulting brightness

### `find`

Syntax:

```bash
hactl find SEARCH
```

The search is case-insensitive and currently searches:

- entity ID
- friendly name
- device class
- unit of measurement

Examples:

```bash
hactl find temperature
hactl find veranda
hactl find °C
```

The result table contains:

```text
Entity    State    Name
```

Units are included in the displayed state when available.

### `entities`

Syntax:

```bash
hactl entities
hactl entities --domain DOMAIN
hactl entities -d DOMAIN
hactl entities --class DEVICE_CLASS
hactl entities -c DEVICE_CLASS
hactl entities --aliased
```

Options:

| Option | Short form | Description |
|---|---|---|
| `--domain DOMAIN` | `-d DOMAIN` | Only show entities from a Home Assistant domain |
| `--class DEVICE_CLASS` | `-c DEVICE_CLASS` | Only show entities with a particular device class |
| `--aliased` | — | Only show entities configured under `[aliases]` |

Examples:

```bash
hactl entities
hactl entities -d light
hactl entities --domain sensor
hactl entities -d binary_sensor
hactl entities -d sensor --class temperature
hactl entities -d sensor -c temperature
hactl entities --aliased -c door
hactl entities -d binary_sensor -c door
hactl entities --aliased
hactl entities --aliased -c door
```

The domain filter also tolerates forms such as:

```bash
hactl entities -d 'light.*'
```

The output is sorted by entity ID. When `--aliased` is used, an additional `Alias` column is shown.

Filters can be combined. For example:

```bash
hactl entities --aliased -c door
hactl entities --aliased -d sensor -c temperature
```

This makes it possible to inspect only the curated entities you have added to `[aliases]`.

## Areas and devices

hactl can inspect Home Assistant's area and device registries through the
Home Assistant WebSocket API.

List every configured area:

```bash
hactl areas
```

Example output:

```text
Name          Area ID
────────────────────────────
Kök           kok
Vardagsrum    vardagsrum
```

List devices assigned directly to an area:

```bash
hactl devices --area Vardagsrum
hactl devices -a vardagsrum
```

The area argument accepts either the displayed area name or the Home Assistant
area ID. Area aliases are also accepted when Home Assistant provides them.

The device table shows:

```text
Name | Manufacturer | Model | Device ID
```

This command reports the device registry's direct `area_id` assignment.

### Entity area assignment

Inspect the effective area for an entity:

```bash
hactl entity-area light.bordslampa
hactl entity-area veranda
```

If the entity has its own area assignment, hactl reports it as an entity
assignment. Otherwise, if its parent device has an area, hactl reports that
the area is inherited from the device.

Assign or reassign an entity to an area:

```bash
hactl entity-area light.bordslampa Vardagsrum
hactl entity-area veranda Kök
```

The entity argument may be a normal hactl alias or a full Home Assistant
entity ID. The area argument accepts area name, area ID, or a Home Assistant
area alias.

Remove the entity-level override:

```bash
hactl entity-area light.bordslampa --clear
```

After clearing an entity-level assignment, the entity inherits its parent
device's area when the device has one; otherwise it has no area.

Changing entity registry data through Home Assistant requires an administrator
account. The long-lived token used by hactl must therefore belong to a Home
Assistant administrator for area changes to succeed.

## Scenes, scripts, and automations

Sprint 7 adds first-class support for Home Assistant action-oriented entities:

```text
scene.*
script.*
automation.*
```

Aliases work for these entities exactly as they do for lights and sensors.

For example:

```toml
[aliases]
filmkväll = "scene.filmkvall"
godnatt = "script.godnatt"
nattbelysning = "automation.nattbelysning"
```

### Run a scene, script, or automation

Use the generic `run` command:

```bash
hactl run filmkväll
hactl run godnatt
hactl run nattbelysning
```

The mapping is:

| Domain | Home Assistant service |
|---|---|
| `scene` | `scene.turn_on` |
| `script` | `script.turn_on` |
| `automation` | `automation.trigger` |

Unlike light on/off commands, running a scene or triggering an automation does not necessarily produce a simple state transition that hactl can confirm. hactl therefore reports that the Home Assistant service request was accepted rather than pretending that a resulting state has been verified.

### List action entities

```bash
hactl scenes
hactl scripts
hactl automations
```

These tables show entity ID, state, friendly name, and `last_triggered` when Home Assistant provides it.

The existing generic commands also continue to work:

```bash
hactl entities -d scene
hactl entities -d script
hactl entities -d automation
hactl find godnatt
hactl status nattbelysning
```

### Control automations

Syntax:

```bash
hactl automation ACTION NAME
```

Supported actions:

```text
status
enable
disable
toggle
trigger
```

Examples:

```bash
hactl automation status nattbelysning
hactl automation disable nattbelysning
hactl automation enable nattbelysning
hactl automation toggle nattbelysning
hactl automation trigger nattbelysning
```

Enable, disable, and toggle operations use Home Assistant's normal `on` / `off` automation state and are confirmed using the same polling logic as lights and switches.

`trigger` calls `automation.trigger` without changing whether the automation itself is enabled.

## Sensors

Sensors are read-only from the hactl MVP.

hactl uses Home Assistant attributes to improve sensor output:

- `friendly_name`
- `device_class`
- `unit_of_measurement`

For example, a Home Assistant state of:

```text
21.7
```

with `unit_of_measurement = "°C"` is displayed as:

```text
21.7 °C
```

Useful commands include:

```bash
hactl entities -d sensor
hactl entities -d sensor -c temperature
hactl areas
hactl devices --area Vardagsrum
hactl entity-area light.bordslampa Vardagsrum
hactl find temperature
hactl status vardagsrum-temp
```

## Binary sensors

Home Assistant stores binary sensor state internally as:

```text
on
off
```

For people, that is often less useful than labels such as:

```text
öppen / stängd
rörelse / ingen rörelse
```

hactl therefore supports configurable state mappings based on the Home Assistant `device_class`.

Example:

```toml
[binary_sensor_states.door]
on = "öppen"
off = "stängd"

[binary_sensor_states.window]
on = "öppet"
off = "stängt"

[binary_sensor_states.motion]
on = "rörelse"
off = "ingen rörelse"
```

You can also define a fallback:

```toml
[binary_sensor_states.default]
on = "aktiv"
off = "inaktiv"
```

The mapping is applied by:

- `hactl status`
- `hactl find`
- `hactl entities`
- the TUI

Example:

```bash
hactl status ytterdörr
```

Output:

```text
Ytterdörr
Entity: binary_sensor.ytterdorr
State:  öppen
Device class: door
```

If no matching mapping and no `default` mapping exist, hactl keeps the raw Home Assistant state `on` or `off`.

Only `on` and `off` keys are accepted in `binary_sensor_states`.

## Shell completion

hactl uses Typer's shell completion support. Install completion for the active shell with:

```bash
hactl --install-completion
```

After restarting the shell, hactl can complete command names, options, and configured aliases.

For example:

```text
hactl status ver<TAB>
hactl unalias var<TAB>
```

The alias completion source is `[aliases]` in the active hactl configuration.

Typer also supports showing the generated completion script without installing it:

```bash
hactl --show-completion
```

## Interactive TUI

Start the Textual interface with:

```bash
hactl tui
```

The TUI is intended to be faster and easier to browse than a long raw entity list.

### Default view

The TUI deliberately opens in the **Aliased** view.

That means it shows only entities you have explicitly chosen and named in `[aliases]`.

This is important for Home Assistant installations with many hundreds or thousands of entities: the default screen should remain useful instead of immediately showing one enormous list.

Use the **All** filter when you explicitly want to browse every entity.

### Filters

The TUI currently has these filters:

- **Aliased** — only entities configured under `[aliases]`
- **All** — every Home Assistant entity
- **Lights** — `light.*`
- **Sensors** — `sensor.*`
- **Binary** — `binary_sensor.*`
- **Switches** — `switch.*`
- **Scenes** — `scene.*`
- **Scripts** — `script.*`
- **Automations** — `automation.*`

### Search

The TUI search field matches:

- alias
- entity ID
- friendly name
- device class

Press:

```text
/
```

to focus the search field.

### Entity table

The table contains:

```text
Alias | Entity | State | Name
```

Selecting an entity shows a detail panel containing available information such as:

- friendly name
- entity ID
- state
- alias
- device class
- brightness for lights
- effective Home Assistant area and whether it comes from the entity or device
- last-triggered time when Home Assistant provides it

### Controls

The TUI supports normal on/off/toggle control for:

- lights
- switches
- automations

It also provides a dedicated **Run** action for:

- scenes
- scripts
- automations

Sensors and binary sensors remain read-only.

Available control buttons are:

- Run
- On
- Off
- Toggle
- Area
- -10%
- +10%

Brightness changes are limited to lights and are clamped to the range 0-100%.

Lights that explicitly report only `onoff` capability are treated as non-dimmable.

### Keyboard controls

| Key | Action |
|---|---|
| `/` | Focus search |
| `Esc` | Return focus to entity list |
| `a` | Add or change alias for selected entity |
| `d` | Remove the selected entity's alias after confirmation |
| `m` | Assign or reassign the selected entity to a Home Assistant area |
| `s` | Cycle sort order: alias, name, state, entity |
| `x` | Run selected scene/script or trigger selected automation |
| `Space` | Toggle selected light, switch, or automation |
| `o` | Turn selected light/switch on or enable selected automation |
| `f` | Turn selected light/switch off or disable selected automation |
| `+` | Increase brightness by 10% |
| `-` | Decrease brightness by 10% |
| `r` | Refresh states |
| `q` | Quit |

### Adding aliases from the TUI

A normal workflow is:

1. open the TUI
2. choose **All**
3. find the entity
4. select it
5. press `a`
6. enter a useful alias
7. save

The alias is written to:

```text
~/.config/hactl/config.toml
```

The entity then appears in the **Aliased** view.

If the entity already has an alias, the dialog is pre-filled so the alias can be renamed.

An alias already assigned to another entity is rejected.

When an entity is renamed to a new alias, the old alias for that same entity is removed.

To remove an alias from the TUI, select the entity and press `d`. hactl asks for confirmation before changing `config.toml`.

Press `s` to cycle the entity list sort order through alias, friendly name, state, and entity ID.

### Safe config updates

Alias changes from the TUI use `tomlkit` and an atomic file replacement.

The intent is to:

- preserve existing TOML comments and formatting
- avoid partially written configuration files
- preserve the original file mode

## State confirmation

State-changing commands do not assume that a successful HTTP request means that the device has already changed state.

After commands such as:

```bash
hactl on veranda
hactl off veranda
hactl toggle veranda
hactl brightness veranda 50
```

hactl polls Home Assistant for a short period.

If the requested state is confirmed, hactl reports success.

If Home Assistant accepted the command but the entity still reports the previous or another state, hactl shows a warning instead of falsely claiming success.

The TUI uses the same confirmation logic.

## Home Assistant API

hactl uses both the Home Assistant REST API and WebSocket API.

The REST client uses:

```text
GET  /api/states
GET  /api/states/<entity_id>
POST /api/services/<domain>/<service>
```

Area and device registry inspection uses the WebSocket endpoint:

```text
/api/websocket
```

with these Home Assistant WebSocket commands:

```text
config/area_registry/list
config/device_registry/list
config/entity_registry/list
config/entity_registry/update
```

The same Home Assistant long-lived access token is used for both REST and
WebSocket authentication.

The default HTTP/WebSocket connection timeout is 10 seconds.

## Configuration example

A more complete configuration might look like:

```toml
url = "http://homeassistant.local:8123"

[aliases]
veranda = "light.veranda"
"dagbädden" = "light.dagbadden"
"vardagsrum-temp" = "sensor.vardagsrum_temperature"
"kök-fukt" = "sensor.kok_humidity"
"ytterdörr" = "binary_sensor.ytterdorr"

[binary_sensor_states.door]
on = "öppen"
off = "stängd"

[binary_sensor_states.window]
on = "öppet"
off = "stängt"

[binary_sensor_states.motion]
on = "rörelse"
off = "ingen rörelse"

[binary_sensor_states.default]
on = "aktiv"
off = "inaktiv"
```

Remember that the token belongs in the separate `credentials` file, never in `config.toml`.

## Troubleshooting

### `hactl: command not found`

If you installed the project in its local virtual environment, activate it:

```bash
cd ~/Development/hactl
source .venv/bin/activate
```

Then check:

```bash
hactl --help
```

If necessary, reinstall the editable package:

```bash
pip install -e .
```

### Configuration file not found

Create:

```text
~/.config/hactl/config.toml
```

or, if `XDG_CONFIG_HOME` is set:

```text
$XDG_CONFIG_HOME/hactl/config.toml
```

### Credentials file not found

Create:

```text
~/.config/hactl/credentials
```

and put the long-lived Home Assistant access token in it.

### Credentials file is accessible by other users

Run:

```bash
chmod 600 ~/.config/hactl/credentials
```

### Invalid TOML

hactl catches TOML parsing errors and reports the configuration error rather than exposing a normal Python traceback.

Check the reported line and column in `config.toml`.

A common TOML issue is forgetting to quote aliases containing characters that require quoted keys.

### Could not connect to Home Assistant

Check the configured URL:

```toml
url = "http://homeassistant.local:8123"
```

Then verify from the same machine that the Home Assistant host is reachable.

If Home Assistant is on another network reached through a VPN or subnet router, routing to that network must already work independently of hactl.

### HTTP 401 or 403

Check that the token in:

```text
~/.config/hactl/credentials
```

is valid and has not been replaced or revoked.

### Brightness rejected

The command only works for `light.*` entities.

A light that reports only:

```text
supported_color_modes = ["onoff"]
```

is treated as non-dimmable.

## Development

The project uses a conventional `src` layout:

```text
hactl/
├── README.md
├── pyproject.toml
├── .gitignore
└── src/
    └── hactl/
        ├── cli.py
        ├── client.py
        ├── config.py
        └── tui.py
```

The command entry point is defined in `pyproject.toml`:

```toml
[project.scripts]
hactl = "hactl.cli:app"
```

During development, use:

```bash
pip install -e .
```

so changes in the source tree are immediately available to the installed command.

## Current scope

The current implementation focuses on:

- Home Assistant entity discovery
- Home Assistant area listing and device-to-area inspection
- entity-level area inspection, assignment, reassignment, and clearing from CLI and TUI
- full alias lifecycle from CLI and TUI
- alias target validation
- shell completion for configured aliases
- explicit unavailable/unknown state display
- TUI sorting
- scenes
- scripts
- automation inspection, enable/disable/toggle, and trigger
- lights
- switches
- sensors
- binary sensors
- dimmable light brightness
- readable state presentation
- a curated TUI suitable for large Home Assistant installations

The TUI intentionally does not expose generic service execution for every Home Assistant domain. Sensors and binary sensors remain read-only.

Future functionality should keep the same design principles:

- simple commands
- safe defaults
- no secrets in Git
- useful behavior with large Home Assistant installations
- clear state confirmation after control actions
- README documentation updated whenever commands, arguments, options, or configuration change

## Quick start

After installation and configuration:

```bash
hactl alias veranda light.veranda
hactl status veranda
hactl on veranda
hactl brightness veranda 50
hactl status vardagsrum-temp
hactl entities -d sensor -c temperature
hactl find temperature
hactl aliases
hactl aliases --check
hactl scenes
hactl scripts
hactl automations
hactl run godnatt
hactl automation status nattbelysning
hactl tui
```

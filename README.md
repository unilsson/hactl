# hactl

A command-line interface for Home Assistant.

## Configuration

Local configuration is stored outside the repository under:

```text
~/.config/hactl/
├── config.toml
└── credentials
```

Keep the Home Assistant long-lived access token only in `credentials` and protect it with:

```bash
chmod 600 ~/.config/hactl/credentials
```

Example `config.toml`:

```toml
url = "http://homeassistant.local:8123"

[aliases]
veranda = "light.veranda"
"dagbädden" = "light.example_dagbadd"
"vardagsrum-temp" = "sensor.vardagsrum_temperature"
"kök-fukt" = "sensor.kok_humidity"
"ytterdörr" = "binary_sensor.ytterdorr"

[binary_sensor_states.door]
on = "öppen"
off = "stängd"
```

For sensor aliases, prefer the pattern `<place>-<type>`, for example `vardagsrum-temp`, `ute-temp`, and `kök-fukt`. Quote aliases containing Swedish characters such as å, ä, and ö.

## Commands

```bash
hactl status veranda
hactl on veranda
hactl off veranda
hactl toggle veranda
hactl find veranda
hactl entities
hactl entities -d light
hactl aliases
```

## Sensors

`status` includes the Home Assistant unit of measurement and device class when available:

```bash
hactl status vardagsrum-temp
```

Example output:

```text
Vardagsrum temperatur
Entity: sensor.vardagsrum_temperature
State:  21.7 °C
Device class: temperature
```

List only temperature sensors:

```bash
hactl entities -d sensor --class temperature
```

The shorter form is:

```bash
hactl entities -d sensor -c temperature
```

State values in `entities` and `find` include units when Home Assistant provides them, for example `21.7 °C`, `48 %`, or `312 W`.

`find` searches entity IDs, friendly names, device classes, and units:

```bash
hactl find temperature
hactl find °C
```

List configured aliases:

```bash
hactl aliases
```

## Binary sensors

Binary sensors such as doors, windows, motion detectors, and occupancy sensors can be listed and inspected like any other entity:

```bash
hactl entities -d binary_sensor
hactl entities -d binary_sensor -c door
hactl status ytterdörr
```

Home Assistant stores binary sensor state as `on` or `off`. hactl can map those raw values to human-readable labels based on the entity's `device_class`.

For door sensors:

```toml
[binary_sensor_states.door]
on = "öppen"
off = "stängd"
```

With that configuration:

```text
Ytterdörr
Entity: binary_sensor.ytterdorr
State:  öppen
Device class: door
```

Mappings are configurable per device class, so other binary sensor types can use different words:

```toml
[binary_sensor_states.window]
on = "öppet"
off = "stängt"

[binary_sensor_states.motion]
on = "rörelse"
off = "ingen rörelse"
```

An optional fallback can be configured for binary sensors without a matching device class:

```toml
[binary_sensor_states.default]
on = "aktiv"
off = "inaktiv"
```

If no mapping is configured, hactl keeps the raw Home Assistant state `on` / `off`.

## TUI

Sprint 5 adds an interactive terminal interface powered by Textual.

After switching to the Sprint 5 branch, reinstall the editable package so the new dependency is installed:

```bash
pip install -e .
```

Start the interface with:

```bash
hactl tui
```

The MVP includes:

- a curated default view that shows only entities configured under `[aliases]`
- an explicit `All` filter for browsing every Home Assistant entity
- entity list with alias, entity ID, state, and friendly name
- live search across aliases, entity IDs, friendly names, and device classes
- filters for aliased entities, all entities, lights, sensors, binary sensors, and switches
- detail view for the selected entity
- read-only display for sensors and binary sensors
- on/off/toggle for lights and switches
- brightness changes in 10 percent steps for dimmable lights
- binary sensor state mappings from `config.toml`
- add or rename aliases directly from the TUI with `a`
- atomic updates of `config.toml` while preserving TOML comments and formatting
- refresh with `r`

Keyboard controls:

```text
/       focus search
Esc     focus entity list
a       add/change alias for selected entity
Space   toggle selected light/switch
o       turn selected light/switch on
f       turn selected light/switch off
+       brightness +10%
-       brightness -10%
r       refresh
q       quit
```

The TUI deliberately keeps sensor entities read-only and reuses the same Home Assistant client, aliases, binary sensor mappings, and state confirmation logic as the CLI.

To add an alias without editing the config file manually, select an entity (typically from `All`) and press `a`. Enter the alias and save. The alias is written to `~/.config/hactl/config.toml` and appears immediately in the `Aliased` view. If an entity already has an alias, the dialog is pre-filled so it can be renamed. An alias already assigned to another entity is rejected.

## Brightness

Set a dimmable light from 0 to 100 percent:

```bash
hactl brightness veranda 50
hactl brightness dagbädden 25
```

A value of `0` turns the light off. The command rejects values outside `0-100` and entities outside the `light` domain. Lights that explicitly report only `onoff` capability are rejected as non-dimmable.

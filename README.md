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

## Brightness

Set a dimmable light from 0 to 100 percent:

```bash
hactl brightness veranda 50
hactl brightness dagbädden 25
```

A value of `0` turns the light off. The command rejects values outside `0-100` and entities outside the `light` domain. Lights that explicitly report only `onoff` capability are rejected as non-dimmable.

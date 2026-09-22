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
```

## Commands

```bash
hactl status veranda
hactl on veranda
hactl off veranda
hactl toggle veranda
hactl find veranda
hactl entities
hactl entities -d light
```

### Brightness

Set a dimmable light from 0 to 100 percent:

```bash
hactl brightness veranda 50
hactl brightness dagbädden 25
```

A value of `0` turns the light off. The command rejects values outside `0-100` and entities outside the `light` domain. Lights that explicitly report only `onoff` capability are rejected as non-dimmable.

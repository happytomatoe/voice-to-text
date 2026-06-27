# Voxtral IBus Engine - Quick Start

## One-Line Install

```bash
just ibus-install && echo "Log out and log back in, then run: just ibus-run"
```

## Daily Usage

```bash
# Start the engine and bridge
just ibus-run

# Then:
# 1. Switch to Voxtral (Super+Space)
# 2. Open a text editor
# 3. Speak into microphone
# 4. Text appears!
```

## Available Commands

```bash
just ibus-install      # Install engine
just ibus-run          # Start engine + bridge
just ibus-engine       # Start engine only
just ibus-bridge       # Start bridge only
just ibus-verify       # Check installation
just ibus-uninstall    # Remove engine
```

## Troubleshooting

```bash
# Check if engine is registered
ibus list-engine | grep -i voxtral

# Verify installation
just ibus-verify

# Check if IBus daemon is running
pgrep ibus-daemon
```

## How It Works

1. **Engine** registers with IBus as input method
2. **Bridge** captures audio from microphone
3. **Voxtral** transcribes audio to text
4. **Text** is sent to engine via Unix socket
5. **Engine** commits text to focused application

## Files

- Engine: `src/voice_to_text/ibus/engine.py`
- Bridge: `src/voice_to_text/ibus/bridge.py`
- XML: `~/.local/share/ibus/component/voxtral.xml`
- Config: `~/.config/environment.d/ibus.conf`

## Need Help?

- Run `just ibus-verify` to check installation
- Run `python3 test_engine.py` to test engine
- Check `USAGE.md` for detailed documentation

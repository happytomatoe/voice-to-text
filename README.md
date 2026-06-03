# voice-to-text

Convert speech to text for free by using free APIs on Linux

# Providers

Cloud:

- **Voxtral** (Mistral) — ASR model. Free tier (Experiment): 2 req/min, 1B tokens/month. Paid: $0.001/min (Mini) / $0.004/min (Small).
- **Groq** — Whisper on LPU hardware. Free tier: 20 req/min, 2,000 req/day for whisper models. Paid: $0.04/hr (v3 Turbo) / $0.111/hr (v3 Large).

Local:

- **Parakeet** (NVIDIA) — Runs locally via Docker. No API limits. Free.

This repo contains gnome extension and python application

<https://github.com/user-attachments/assets/a51d6826-e417-4e69-afd0-9ff40799d3a1>

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Groq API key](https://console.groq.com/keys) OR [Voxtral API key](https://mistral.ai)
- Linux with `xclip`/`xsel` (X11) for clipboard functionality

## Installation

```bash
 curl -sSL https://raw.githubusercontent.com/happytomatoe/voice-to-text/refs/heads/main/install.sh | bash
```

If you want to use Parakeet check out [this script](./parakeet-v2.sh)

## How to use

- Press Super+W
- Dictate
- Press Super+W

## Configuration

Edit [`config.yaml`](./config.yaml) to customize if you are using python app or right click on microphone icon->Preferences if you are using gnome extension

## Output Methods

- **clipboard**: Copies text to system clipboard using `xclip`/`xsel`
- **output** - used by gnome extension

## License

MIT

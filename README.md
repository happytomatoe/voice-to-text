# voice-to-text

Convert speech to text for free by using free APIs(Voxtral, Groq) on Linux

<video src="./demo.webm" controls></video>

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Groq API key](https://console.groq.com/keys) OR [Voxtral API key](https://mistral.ai)(slightly better)
- Linux with `xclip`/`xsel` (X11) for clipboard functionality

## Installation

```bash
 curl -sSL https://raw.githubusercontent.com/happytomatoe/voice-to-text/refs/heads/main/install.sh | bash
```

## Configuration

Edit [`config.yaml`](./config.yaml) to customize

## Output Methods

- **clipboard**: Copies text to system clipboard using `xclip`/`xsel`
- **output** - used by gnome extension

## License

MIT

#!/usr/bin/env bash
set -euo pipefail

# Store API keys for voice-to-text providers using gum

if ! command -v gum &>/dev/null; then
    echo "Error: 'gum' is required. Install it from https://github.com/charmbracelet/gum"
    echo "  go install github.com/charmbracelet/gum@latest"
    echo "  brew install gum      # macOS"
    echo "  sudo dnf install gum  # Fedora"
    exit 1
fi

GUM=$(command -v gum)

$GUM style --border normal --padding "0 2" --margin "0 0 1" "voice-to-text — API Key Storage"

provider=$($GUM choose \
    --header "Which provider's API key do you want to store?" \
    "Deepgram" \
    "Voxtral" \
    "Groq")

if [ -z "$provider" ]; then
    echo "No provider selected. Aborted."
    exit 0
fi

# Map display name to keyring username
case "$provider" in
    Deepgram) username="deepgram" ;;
    Voxtral)  username="voxtral" ;;
    Groq)     username="groq" ;;
    *)        echo "Invalid provider. Aborted."; exit 1 ;;
esac

echo
secret-tool store --label="${provider} API Key" service voice-to-text username "$username" && \
    $GUM style --foreground 10 "✓ ${provider} API key stored (service=voice-to-text, username=${username})"
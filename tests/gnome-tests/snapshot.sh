#!/bin/bash
# Snapshot testing: captures full-screen screenshots of all GNOME extension states.
# Usage: ./snapshot.sh [--update]
#
# With --update: saves screenshots as new references
# Without --update: compares against existing references (like run-test.sh)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/../.."
REFERENCES_DIR="${SCRIPT_DIR}/../gnome-references"
OUTPUT_DIR="${SCRIPT_DIR}/../gnome-snapshots"
EXTENSION_UUID="voice-to-text@happytomatoe.com"
EXTENSION_ZIP="/app/tests/gnome-references/${EXTENSION_UUID}.shell-extension.zip"

UPDATE_MODE=false
if [[ "${1:-}" == "--update" ]]; then
  UPDATE_MODE=true
fi

cd "${PROJECT_ROOT}"

# Build container if needed
IMAGE="voice-to-text-gnome-test"
if ! podman image exists "${IMAGE}"; then
  echo "Building test container..."
  podman build -t "${IMAGE}" -f tests/gnome-tests/Containerfile .
fi

# Run container
echo "Starting container..."
POD=$(podman run --rm --cap-add=SYS_NICE --cap-add=IPC_LOCK -td "${IMAGE}")

if [[ "${UPDATE_MODE}" == "true" ]]; then
  mkdir -p "${REFERENCES_DIR}"
else
  mkdir -p "${OUTPUT_DIR}"
fi

cleanup() {
  podman kill "${POD}" 2>/dev/null || true
}
trap cleanup EXIT

# Helper to run commands in container
do_in_pod() {
  podman exec --user gnomeshell --workdir /home/gnomeshell "${POD}" set-env.sh "$@"
}

# Helper to capture full-screen screenshot
capture_full() {
  local output_file="${1}"
  podman cp "${POD}:/opt/Xvfb_screen0" - | tar xf - --to-command "convert xwd:- ${output_file}"
}

# Helper to capture cropped screenshot
capture_crop() {
  local output_file="${1}"
  local crop="${2}"
  podman cp "${POD}:/opt/Xvfb_screen0" - | tar xf - --to-command \
    "convert xwd:- -crop ${crop} +repage ${output_file}"
}

# Wait for container to start
echo "Waiting for D-Bus..."
sleep 5

# Set up GSK_RENDERER for consistent rendering
do_in_pod 'echo "export GSK_RENDERER=cairo" >> .bash_profile'

# Disable welcome tour
echo "Disabling welcome tour..."
do_in_pod gsettings set org.gnome.shell welcome-dialog-last-shown-version "999" || true
do_in_pod gsettings set org.gnome.mutter center-new-windows true

# Start GNOME Shell
echo "Starting GNOME Shell..."
do_in_pod systemctl --user start "gnome-xsession@:99"
sleep 10

# Install and enable extension
echo "Installing extension..."
do_in_pod gnome-extensions install "${EXTENSION_ZIP}" --force
do_in_pod gnome-extensions enable "${EXTENSION_UUID}"

# Close overview if open
echo "Closing Overview..."
do_in_pod xdotool keydown super
sleep 0.5
do_in_pod xdotool keyup super
sleep 3

echo ""
if [[ "${UPDATE_MODE}" == "true" ]]; then
  echo "=== Capturing snapshot references ==="
  DEST="${REFERENCES_DIR}"
else
  echo "=== Running snapshot tests ==="
  DEST="${OUTPUT_DIR}"
fi

TESTS_FAILED=0
TESTS_RUN=0

# Snapshot test function
snapshot_test() {
  local test_name="${1}"
  local description="${2}"
  local capture_cmd="${3:-full}"  # "full" or "crop:WxH+X+Y"
  
  TESTS_RUN=$((TESTS_RUN + 1))
  echo -n "  ${test_name} (${description})... "
  
  local actual="${DEST}/${test_name}.png"
  
  # Capture the screenshot
  if [[ "${capture_cmd}" == "full" ]]; then
    capture_full "${actual}"
  else
    local crop="${capture_cmd#crop:}"
    capture_crop "${actual}" "${crop}"
  fi
  
  if [[ "${UPDATE_MODE}" == "true" ]]; then
    echo "SAVED"
    return
  fi
  
  # Compare with reference
  local reference="${REFERENCES_DIR}/${test_name}.png"
  local diff="${OUTPUT_DIR}/${test_name}-diff.png"
  
  if [[ ! -f "${reference}" ]]; then
    echo "NEW (no reference)"
    return
  fi
  
  METRIC=$(compare -metric MSE "${reference}" "${actual}" "${diff}" 2>&1 || true)
  
  if [[ -z "${METRIC}" ]] || [[ "${METRIC}" == "0" ]]; then
    echo "PASS (exact match)"
    rm -f "${diff}"
  else
    MSE=$(echo "${METRIC}" | grep -oP '[\d.]+')
    if (( $(echo "${MSE} < 100" | bc -l 2>/dev/null || echo 0) )); then
      echo "PASS (MSE: ${MSE})"
      rm -f "${diff}"
    else
      echo "FAIL (MSE: ${MSE})"
      TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
  fi
}

# ============================================
# State 1: Default indicator (idle state)
# ============================================
echo ""
echo "1. Indicator - idle state"
sleep 2
snapshot_test "snapshot-indicator-idle" "top bar with mic icon"

# ============================================
# State 2: Right-click menu open
# ============================================
echo ""
echo "2. Right-click menu"
# Right-click on the extension area in top panel
# The indicator is typically at the right side of the panel
do_in_pod xdotool mousemove 1850 12
sleep 0.5
do_in_pod xdotool click 3  # Right click
sleep 2
snapshot_test "snapshot-indicator-menu" "context menu with Preferences"
# Close menu by clicking elsewhere
do_in_pod xdotool mousemove 960 540
do_in_pod xdotool click 1
sleep 1

# ============================================
# State 3: Preferences dialog - General tab
# ============================================
echo ""
echo "3. Preferences dialog"
do_in_pod gnome-extensions prefs "${EXTENSION_UUID}"
sleep 5
snapshot_test "snapshot-prefs-general" "preferences window - general settings"
# Keep prefs open for next screenshot

# ============================================
# State 4: Preferences dialog - scrolled down
# ============================================
echo ""
echo "4. Preferences - scrolled down"
# Scroll down in the preferences window to show more settings
do_in_pod xdotool key Tab
sleep 0.5
do_in_pod xdotool key Down
do_in_pod xdotool key Down
do_in_pod xdotool key Down
do_in_pod xdotool key Down
sleep 1
snapshot_test "snapshot-prefs-scrolled" "preferences scrolled to provider settings"

# Close preferences
do_in_pod xdotool keydown alt
do_in_pod xdotool key F4
sleep 1
do_in_pod xdotool keyup alt

# ============================================
# State 5: Full desktop overview
# ============================================
echo ""
echo "5. Full desktop"
sleep 2
snapshot_test "snapshot-desktop-full" "full desktop with extension active"

# ============================================
# State 6: Top bar close-up (for indicator detail)
# ============================================
echo ""
echo "6. Top bar indicator detail"
# Capture just the top-right area where indicator lives
snapshot_test "snapshot-topbar-indicator" "top bar right section" "crop:200x30+1750+0"

echo ""
echo "========================================="

if [[ "${UPDATE_MODE}" == "true" ]]; then
  echo "Snapshot references saved to: ${REFERENCES_DIR}"
  echo "Review the screenshots and commit them."
  echo ""
  ls -la "${REFERENCES_DIR}"/snapshot-*.png 2>/dev/null || echo "No snapshot files found"
else
  echo "Results: $((TESTS_RUN - TESTS_FAILED))/${TESTS_RUN} passed"
  if [[ ${TESTS_FAILED} -eq 0 ]]; then
    echo "All snapshots match!"
    exit 0
  else
    echo "${TESTS_FAILED} snapshot(s) failed."
    echo "Diff images saved to: ${OUTPUT_DIR}"
    exit 1
  fi
fi

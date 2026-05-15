import GLib from 'gi://GLib';

export function typeText(text) {
    GLib.spawn_command_line_async(
        `ydotool type --key-delay=0 --key-hold=0 -- ${GLib.shell_quote(text)}`);
}

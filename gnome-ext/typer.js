import GLib from 'gi://GLib';

export function typeText(text) {
    try {
        const [ok] = GLib.spawn_command_line_async(
            `ydotool type --key-delay=0 --key-hold=0 -- ${GLib.shell_quote(text)}`);
        return ok;
    } catch (e) {
        console.error(`VoiceToText: failed to run ydotool: ${e.message}`);
        return false;
    }
}

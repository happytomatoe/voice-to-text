import GLib from 'gi://GLib';
import St from 'gi://St';

export function typeText(text) {
    try {
        const ok = GLib.spawn_command_line_async(
            `ydotool type --key-delay=0 --key-hold=0 -- ${GLib.shell_quote(text)}`);
        if (ok) return true;
    } catch (e) {
        console.error(`VoiceToText: failed to run ydotool: ${e.message}`);
    }

    St.Clipboard.get_default().set_text(St.ClipboardType.CLIPBOARD, text);
    return false;
}

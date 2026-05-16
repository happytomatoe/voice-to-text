import GLib from 'gi://GLib';
import St from 'gi://St';

export function typeText(text) {
    try {
        const [ok, , exitStatus] = GLib.spawn_command_line_sync(
            `ydotool type --key-delay=0 --key-hold=0 -- ${GLib.shell_quote(text)}`);
        if (ok && exitStatus === 0) {
            return true;
        }
    } catch (e) {
        console.error(`VoiceToText: failed to run ydotool: ${e.message}`);
    }

    St.Clipboard.get_default().set_text(St.ClipboardType.CLIPBOARD, text);
    return false;
}

import GLib from 'gi://GLib';
import St from 'gi://St';

export function typeText(text, outputMethod = 'type-fallback-clipboard') {
    let typed = false;
    
    if (outputMethod === 'type' || outputMethod === 'type-fallback-clipboard') {
        typed = tryType(text);
    }
    
    if (outputMethod === 'type-fallback-clipboard') {
        if (!typed) {
            copyToClipboard(text);
        }
    } else if (outputMethod === 'clipboard') {
        copyToClipboard(text);
    }
    return typed;
}

function tryType(text) {
    try {
        const [ok, , , exitStatus] = GLib.spawn_command_line_sync(
            `ydotool type --key-delay=0 --key-hold=0 -- ${GLib.shell_quote(text)}`);
        if (ok && exitStatus === 0) {
            return true;
        }
    } catch (e) {
        console.error(`VoiceToText: failed to run ydotool: ${e.message}`);
    }
    return false;
}

function copyToClipboard(text) {
    St.Clipboard.get_default().set_text(St.ClipboardType.CLIPBOARD, text);
}

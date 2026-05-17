import GLib from 'gi://GLib';
import St from 'gi://St';

let _lastTyped = '';

export function getLastTyped() {
    return _lastTyped;
}

export function typeText(text) {
    _lastTyped = text;
    try {
        const [ok, , , exitStatus] = GLib.spawn_command_line_sync(
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

export function typeTextIncremental(text) {
    const oldText = _lastTyped;
    const oldLen = oldText.length;

    if (oldLen === 0) {
        return typeText(text);
    }

    if (text.startsWith(oldText)) {
        const diff = text.slice(oldLen);
        if (diff.length > 0) {
            _lastTyped = text;
            return typeText(diff);
        }
        return true;
    }

    for (let i = 0; i < Math.min(oldLen, text.length); i++) {
        if (text[i] !== oldText[i]) {
            const backspaces = oldLen - i;
            const newChars = text.slice(i);
            _lastTyped = text;
            const cmd = `ydotool key ${'14:1 14:0 '.repeat(backspaces)} && ydotool type --key-delay=0 --key-hold=0 -- ${GLib.shell_quote(newChars)}`;
            try {
                const [ok, , , exitStatus] = GLib.spawn_command_line_sync(cmd);
                if (ok && exitStatus === 0) return true;
            } catch (e) {}
            return false;
        }
    }

    return typeText(text);
}

export function typeTextWithCorrection(newText) {
    const oldText = _lastTyped;
    _lastTyped = newText;

    const oldLen = oldText.length;

    if (oldLen === 0) {
        return typeText(newText);
    }

    let backspaceSeq = '';
    for (let i = 0; i < oldLen; i++) {
        backspaceSeq += '14:1 14:0 ';
    }
    const fullCmd = `ydotool key ${backspaceSeq.trim()} && ydotool type --key-delay=0 --key-hold=0 -- ${GLib.shell_quote(newText)}`;

    try {
        const [ok, , , exitStatus] = GLib.spawn_command_line_sync(fullCmd);
        if (ok && exitStatus === 0) {
            return true;
        }
    } catch (e) {
        console.error(`VoiceToText: failed to run ydotool: ${e.message}`);
    }

    St.Clipboard.get_default().set_text(St.ClipboardType.CLIPBOARD, newText);
    return false;
}

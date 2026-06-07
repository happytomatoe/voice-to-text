import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import St from 'gi://St';

let _lastTyped = '';

export function resetTypedState() {
    _lastTyped = '';
}

export function getLastTyped() {
    return _lastTyped;
}

export function typeText(text, onDone = () => {}) {
    _lastTyped = text;
    try {
        const argv = [
            'ydotool', 'type',
            '--key-delay=0', '--key-hold=0',
            '--', text,
        ];
        const proc = new Gio.Subprocess({ argv, flags: Gio.SubprocessFlags.NONE });
        proc.init(null);
        proc.wait_check_async(null, (proc, res) => {
            try {
                onDone(proc.wait_check_finish(res));
            } catch (e) {
                console.error(`VoiceToText: ydotool failed: ${e.message}`);
                onDone(false);
            }
        });
    } catch (e) {
        console.error(`VoiceToText: failed to run ydotool: ${e.message}`);
        onDone(false);
    }
}

export function typeTextIncremental(text) {
    const oldText = _lastTyped;

    if (oldText.length === 0) {
        _lastTyped = text;
        _ydotoolType(text);
        return;
    }

    // Streaming partials can change completely (not just append).
    // Replace entire text: Select All -> Delete -> Type new
    if (text !== oldText) {
        _lastTyped = text;
        _ydotoolReplace(text);
    }
}

function _ydotoolType(text) {
    try {
        const argv = ['ydotool', 'type', '--key-delay=0', '--key-hold=0', '--', text];
        const proc = new Gio.Subprocess({ argv, flags: Gio.SubprocessFlags.NONE });
        proc.init(null);
    } catch (e) {
        console.error(`VoiceToText: ydotool type failed: ${e.message}`);
    }
}

function _ydotoolReplace(text) {
    // Select all (Ctrl+A), Delete, then type new text
    try {
        GLib.spawn_command_line_sync(
            `ydotool key 37:1 38:1 38:0 37:0 && ydotool type --key-delay=0 --key-hold=0 -- ${GLib.shell_quote(text)}`
        );
    } catch (e) {
        console.error(`VoiceToText: ydotool replace failed: ${e.message}`);
    }
}

export function copyToClipboard(text) {
    St.Clipboard.get_default().set_text(St.ClipboardType.CLIPBOARD, text);
}

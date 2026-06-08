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
                proc.wait_check_finish(res);
                _lastTyped = text;
                onDone(true);
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

    if (text === oldText) return;

    // Find common prefix between old and new text
    let commonLen = 0;
    const minLen = Math.min(oldText.length, text.length);
    while (commonLen < minLen && oldText[commonLen] === text[commonLen]) {
        commonLen++;
    }

    const backspaceCount = oldText.length - commonLen;
    const newSuffix = text.slice(commonLen);

    console.log('VoiceToText: typeTextIncremental:', {
        backspaceCount,
        newSuffix: newSuffix.slice(0, 60),
    });
    _ydotoolDiffType(backspaceCount, newSuffix, text);
}

// Diff-based typing: backspace the changed suffix, then type only what's new.
// Based on the nerd-dictation algorithm (ideasman42/nerd-dictation).
function _ydotoolDiffType(backspaceCount, newSuffix, newText) {
    try {
        if (backspaceCount > 0) {
            // KEY_BACKSPACE = evdev keycode 14
            const backspaces = Array(backspaceCount).fill('14:1 14:0').join(' ');
            GLib.spawn_command_line_sync(
                `ydotool key --key-delay=3 -- ${backspaces}`
            );
        }
        if (newSuffix.length > 0) {
            GLib.spawn_command_line_sync(
                `ydotool type --key-delay=0 --key-hold=0 -- ${GLib.shell_quote(newSuffix)}`
            );
        }
        _lastTyped = newText;
    } catch (e) {
        console.error(`VoiceToText: ydotool diff type failed: ${e.message}`);
    }
}

export function copyToClipboard(text) {
    St.Clipboard.get_default().set_text(St.ClipboardType.CLIPBOARD, text);
}

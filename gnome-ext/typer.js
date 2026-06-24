import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import St from 'gi://St';
import * as MessageTray from 'resource:///org/gnome/shell/ui/messageTray.js';

let _lastTyped = '';

function _showNotification(message) {
    const systemSource = MessageTray.getSystemSource();
    const notification = new MessageTray.Notification({
        source: systemSource,
        title: 'Voice to Text',
        body: message,
        iconName: 'audio-input-microphone-symbolic',
    });
    systemSource.addNotification(notification);
}

export function resetTypedState() {
    _lastTyped = '';
}

export function getLastTyped() {
    return _lastTyped;
}

export function typeText(text, onDone = () => {}) {
    try {
        // dotool reads from stdin: echo "type TEXT" | dotool
        const input = `type ${text}\n`;
        const proc = new Gio.Subprocess({
            argv: ['dotool'],
            flags: Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDIN_PIPE,
        });
        proc.init(null);
        proc.communicate_utf8(null, input, null, null);
        proc.wait_check_async(null, (proc, res) => {
            try {
                proc.wait_check_finish(res);
                _lastTyped = text;
                onDone(true);
            } catch (e) {
                console.error(`VoiceToText: dotool failed: ${e.message}`);
                _showNotification(`dotool failed: ${e.message}`);
                onDone(false);
            }
        });
    } catch (e) {
        console.error(`VoiceToText: failed to run dotool: ${e.message}`);
        _showNotification(`Failed to run dotool: ${e.message}`);
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
    _dotoolDiffType(backspaceCount, newSuffix, text);
}

// Diff-based typing: backspace the changed suffix, then type only what's new.
// Based on the nerd-dictation algorithm (ideasman42/nerd-dictation).
function _dotoolDiffType(backspaceCount, newSuffix, newText) {
    try {
        if (backspaceCount > 0) {
            // KEY_BACKSPACE = evdev keycode 14
            const backspaces = Array(backspaceCount)
                .fill('14:1 14:0')
                .join(' ');
            GLib.spawn_command_line_sync(
                `printf '%s\\n' '${backspaces}' | dotool`
            );
        }
        if (newSuffix.length > 0) {
            GLib.spawn_command_line_sync(
                `echo type ${GLib.shell_quote(newSuffix)} | dotool`
            );
        }
        _lastTyped = newText;
    } catch (e) {
        console.error(`VoiceToText: dotool diff type failed: ${e.message}`);
        _showNotification(`dotool diff type failed: ${e.message}`);
    }
}

export function copyToClipboard(text) {
    St.Clipboard.get_default().set_text(St.ClipboardType.CLIPBOARD, text);
}
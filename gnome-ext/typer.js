import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import St from 'gi://St';
import * as MessageTray from 'resource:///org/gnome/shell/ui/messageTray.js';

let _lastTyped = '';
const DOTOOLC_PATH = GLib.find_program_in_path('dotoolc') || '/var/home/l/.local/bin/dotoolc';

console.log(`VoiceToText: Using dotoolc path: ${DOTOOLC_PATH}`);

let _typingQueue = Promise.resolve();

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

function _executeDotoolc(input) {
    return new Promise((resolve) => {
        try {
            const proc = new Gio.Subprocess({
                argv: [DOTOOLC_PATH],
                flags: Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDIN_PIPE,
            });
            proc.init(null);
            proc.communicate_utf8(input, null, null, null);
            proc.wait_check_async(null, (p, res) => {
                try {
                    p.wait_check_finish(res);
                } catch (e) {
                    console.error(`VoiceToText: dotoolc execution failed: ${e.message}`);
                }
                resolve();
            });
        } catch (e) {
            console.error(`VoiceToText: failed to spawn dotoolc: ${e.message}`);
            resolve();
        }
    });
}

export function typeText(text, onDone = () => {}) {
    _typingQueue = _typingQueue.then(() => {
        return _executeDotoolc(`type ${text}\n`).then(() => {
            _lastTyped = text;
            onDone(true);
        });
    }).catch(e => {
        console.error(`VoiceToText: typeText queue error: ${e.message}`);
        onDone(false);
    });
}

export function typeTextIncremental(text) {
    _typingQueue = _typingQueue.then(async () => {
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

        console.log('VoiceToText: typeTextIncremental processing:', {
            backspaceCount,
            newSuffix: newSuffix.slice(0, 60),
        });
        
        await _dotoolDiffType(backspaceCount, newSuffix, text);
    });
}

// Diff-based typing: backspace the changed suffix, then type only what's new.
// Based on the nerd-dictation algorithm (ideasman42/nerd-dictation).
function _dotoolDiffType(backspaceCount, newSuffix, newText) {
    _typingQueue = _typingQueue.then(async () => {
        try {
            if (backspaceCount > 0) {
                // Use 'key backspace' as per verified command
                const backspaces = Array(backspaceCount)
                    .fill('key backspace')
                    .join(' ');
                await _executeDotoolc(`${backspaces}\n`);
            }
            if (newSuffix.length > 0) {
                await _executeDotoolc(`type ${newSuffix}\n`);
            }
            _lastTyped = newText;
        } catch (e) {
            console.error(`VoiceToText: dotoolc diff type failed: ${e.message}`);
            _showNotification(`dotoolc diff type failed: ${e.message}`);
        }
    });
}

export function copyToClipboard(text) {
    St.Clipboard.get_default().set_text(St.ClipboardType.CLIPBOARD, text);
}
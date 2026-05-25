import Gio from 'gi://Gio';
import St from 'gi://St';

export function typeText(text, onDone) {
    tryTypeAsync(text, onDone ?? (() => {}));
}

function tryTypeAsync(text, callback) {
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
                callback(proc.wait_check_finish(res));
            } catch (e) {
                console.error(`VoiceToText: ydotool failed: ${e.message}`);
                callback(false);
            }
        });
    } catch (e) {
        console.error(`VoiceToText: failed to run ydotool: ${e.message}`);
        callback(false);
    }
}

export function copyToClipboard(text) {
    St.Clipboard.get_default().set_text(St.ClipboardType.CLIPBOARD, text);
}

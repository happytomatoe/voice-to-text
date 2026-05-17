import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

export function registerHotkey(name, settings, callback) {
    try {
        Main.wm.addKeybinding(
            name,
            settings,
            Meta.KeyBindingFlags.NONE,
            Shell.ActionMode.NORMAL | Shell.ActionMode.OVERVIEW,
            callback
        );
        console.log(`VoiceToText: hotkey '${name}' registered`);
    } catch (e) {
        console.error(`VoiceToText: failed to register hotkey '${name}': ${e.message}`);
        Main.notify('Voice to Text', `Hotkey "${name}" failed to register — use the panel icon instead`);
    }
}

export function unregisterHotkey(key) {
    Main.wm.removeKeybinding(key);
}

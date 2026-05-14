import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

export function registerHotkey(name, settings, callback) {
    Main.wm.addKeybinding(
        name,
        settings,
        Meta.KeyBindingFlags.NONE,
        Shell.ActionMode.NORMAL | Shell.ActionMode.OVERVIEW,
        callback
    );
    console.log(`VoiceToText: hotkey '${name}' registered`);
}

export function unregisterHotkey(key) {
    Main.wm.removeKeybinding(key);
}

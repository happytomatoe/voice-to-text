import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

export function registerHotkey(name, settings, callback) {
    const hotkeyArr = settings.get_strv(name);
    const hotkeyValue = hotkeyArr && hotkeyArr.length > 0 ? hotkeyArr[0] : '';
    console.log(`VoiceToText: registerHotkey called, name=${name}, hotkey=${hotkeyValue}`);
    
    try {
        Main.wm.addKeybinding(
            name,
            settings,
            Meta.KeyBindingFlags.NONE,
            Shell.ActionMode.NORMAL | Shell.ActionMode.OVERVIEW,
            () => {
                console.log(`VoiceToText: hotkey ${hotkeyValue} pressed!`);
                callback();
            }
        );
        console.log(`VoiceToText: hotkey '${hotkeyValue}' registered successfully`);
        Main.notify('Voice to Text', `Hotkey ${hotkeyValue} registered`);
    } catch (e) {
        console.error(`VoiceToText: failed to register hotkey '${hotkeyValue}': ${e.message}`);
        Main.notify('Voice to Text', `Hotkey "${hotkeyValue}" failed to register`);
    }
}

export function unregisterHotkey() {
    Main.wm.removeKeybinding('hotkey');
}

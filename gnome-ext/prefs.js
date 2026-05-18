import Adw from 'gi://Adw';
import Gtk from 'gi://Gtk';
import Gio from 'gi://Gio';
import {ExtensionPreferences, gettext as _} from 'resource:///org/gnome/Shell/Extensions/js/extensions/prefs.js';

export default class VoiceToTextPrefs extends ExtensionPreferences {
    fillPreferencesWindow(window) {
        const settings = this.getSettings();
        
        // Create a preferences page
        const page = new Adw.PreferencesPage({
            title: _('General'),
            icon_name: 'audio-input-microphone-symbolic',
        });
        window.add(page);

        // Create a preferences group
        const group = new Adw.PreferencesGroup({
            title: _('Recording Settings'),
            description: _('Configure voice to text recording behavior'),
        });
        page.add(group);

        // Hotkey setting - Note: This is read-only as GNOME handles hotkeys via gsettings
        // Users should use gsettings or dconf-editor to change the hotkey
        const hotkeyRow = new Adw.ActionRow({
            title: _('Recording Hotkey'),
            subtitle: _('Configure in GNOME Settings or via: gsettings set org.gnome.shell.extensions.voice-to-text hotkey "[\'<Super>w\']"'),
        });
        group.add(hotkeyRow);

        // Show recording notification toggle
        const showNotificationRow = new Adw.SwitchRow({
            title: _('Show Recording Notification'),
            subtitle: _('Show a notification when recording starts'),
        });
        settings.bind('show-recording-notification',
            showNotificationRow, 'active',
            Gio.SettingsBindFlags.DEFAULT);
        group.add(showNotificationRow);

        // Stop timeout setting
        const stopTimeoutRow = new Adw.SpinRow({
            title: _('Stop Timeout'),
            subtitle: _('Seconds to wait for recording process to stop before forcing it'),
            adjustment: new Gtk.Adjustment({
                lower: 1,
                upper: 120,
                step_increment: 1,
                page_increment: 10,
            }),
        });
        settings.bind('stop-timeout-seconds',
            stopTimeoutRow, 'value',
            Gio.SettingsBindFlags.DEFAULT);
        group.add(stopTimeoutRow);
    }
}

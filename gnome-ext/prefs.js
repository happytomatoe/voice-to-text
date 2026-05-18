import Adw from 'gi://Adw';
import Gtk from 'gi://Gtk';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Gdk from 'gi://Gdk';
import {ExtensionPreferences, gettext as _} from 'resource:///org/gnome/Shell/Extensions/js/extensions/prefs.js';

export default class VoiceToTextPrefs extends ExtensionPreferences {
    fillPreferencesWindow(window) {
        this._window = window;
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

        // Hotkey setting - using a custom row with key capture
        const hotkeyRow = new Adw.ActionRow({
            title: _('Recording Hotkey'),
        });
        
        const hotkeyBox = new Gtk.Box({
            hexpand: true,
            spacing: 6,
        });
        hotkeyRow.add_suffix(hotkeyBox);
        
        const hotkeyLabel = new Gtk.Label({
            label: this._getHotkeyDisplay(settings.get_string('hotkey')),
            xalign: 0,
        });
        hotkeyBox.append(hotkeyLabel);
        
        const hotkeyButton = new Gtk.Button({
            label: _('Set Shortcut…'),
            halign: Gtk.Align.END,
        });
        hotkeyBox.append(hotkeyButton);
        
        // Create a key capture dialog
        hotkeyButton.connect('clicked', () => {
            this._showHotkeyDialog(settings, hotkeyLabel);
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

    _getHotkeyDisplay(hotkeyValue) {
        // Parse the hotkey array string like "['<Super>w']"
        try {
            // Remove brackets and quotes
            const clean = hotkeyValue.replace(/[\['\]]/g, '');
            if (clean) {
                return clean;
            }
        } catch (e) {
            console.error('Error parsing hotkey:', e);
        }
        return _('Not set');
    }

    _showHotkeyDialog(settings, label) {
        const dialog = new Gtk.Window({
            title: _('Set Shortcut'),
            modal: true,
            transient_for: this._window,
            default_width: 400,
            default_height: 200,
        });
        
        const mainBox = new Gtk.Box({
            orientation: Gtk.Orientation.VERTICAL,
            spacing: 12,
            margin_top: 12,
            margin_bottom: 12,
            margin_start: 12,
            margin_end: 12,
        });
        dialog.set_child(mainBox);
        
        const instructionLabel = new Gtk.Label({
            label: _('Press a new shortcut key combination'),
            wrap: true,
            xalign: 0,
        });
        mainBox.append(instructionLabel);
        
        const keyLabel = new Gtk.Label({
            label: _('New shortcut: None'),
            xalign: 0,
        });
        mainBox.append(keyLabel);
        
        const cancelButton = new Gtk.Button({
            label: _('Cancel'),
            halign: Gtk.Align.END,
        });
        const setButton = new Gtk.Button({
            label: _('Set'),
            halign: Gtk.Align.END,
            sensitive: false,
        });
        
        const buttonBox = new Gtk.Box({
            spacing: 6,
            halign: Gtk.Align.END,
        });
        buttonBox.append(cancelButton);
        buttonBox.append(setButton);
        mainBox.append(buttonBox);
        
        let currentKey = null;
        
        // Create a key capture controller
        const keyController = new Gtk.EventControllerKey();
        dialog.add_controller(keyController);
        
        keyController.connect('key-pressed', (controller, keyval, keycode, state) => {
            // Ignore modifier-only keys
            const mask = state & Gtk.accelerator_get_default_mod_mask();
            
            // Check if it's a valid accelerator
            const accel = Gtk.accelerator_name(keyval, mask);
            if (accel) {
                currentKey = accel;
                keyLabel.set_label(`New shortcut: ${accel}`);
                setButton.sensitive = true;
            }
            return true;
        });
        
        cancelButton.connect('clicked', () => {
            dialog.close();
        });
        
        setButton.connect('clicked', () => {
            if (currentKey) {
                // Save the new hotkey
                settings.set_string('hotkey', `[ '${currentKey}' ]`);
                label.set_label(currentKey);
            }
            dialog.close();
        });
        
        // Handle escape key
        const escapeController = new Gtk.EventControllerKey();
        dialog.add_controller(escapeController);
        escapeController.connect('key-pressed', (controller, keyval) => {
            if (keyval === Gdk.KEY_Escape) {
                dialog.close();
                return GLib.SOURCE_REMOVE;
            }
            return false;
        });
        
        dialog.present();
    }
}

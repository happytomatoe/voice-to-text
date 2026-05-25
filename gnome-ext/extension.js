import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import {VoiceIndicator} from './indicator.js';
import {Recorder} from './recorder.js';
import {registerHotkey, unregisterHotkey} from './hotkey.js';
import {typeText} from './typer.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as MessageTray from 'resource:///org/gnome/shell/ui/messageTray.js';
import {gettext as _} from 'resource:///org/gnome/shell/extensions/extension.js';


export default class VoiceToTextExtension extends Extension {
    enable() {
        this._settings = this.getSettings('org.gnome.shell.extensions.voice-to-text');
        this._indicator = new VoiceIndicator();
        this._binPath = GLib.find_program_in_path('voice-to-text');
        this._recorder = null;
        this._recording = false;
        this._stopTimeoutId = null;
        this._hotkeySignalId = null;

        this._indicator.onStart = () => this._start();
        this._indicator.onStop = () => this._stop();
        this._indicator.onConfigure = () => this._openPreferences();

        Main.panel.addToStatusArea(this.uuid, this._indicator, 0, 'right');
        this._registerHotkey();
        
        // Listen for hotkey changes
        this._hotkeySignalId = this._settings.connect('changed::hotkey', () => {
            this._registerHotkey();
        });
    }

    disable() {
        this._unregisterHotkey();

        if (this._hotkeySignalId) {
            this._settings.disconnect(this._hotkeySignalId);
            this._hotkeySignalId = null;
        }

        if (this._stopTimeoutId) {
            GLib.source_remove(this._stopTimeoutId);
            this._stopTimeoutId = null;
        }

        if (this._recorder) {
            this._recorder.onAudioLevel = null;
            this._recorder.onTranscription = null;
            this._recorder.onTimeout = null;
            this._recorder.onError = null;
            this._recorder.stop();
            this._recorder = null;
        }

        this._indicator?.destroy();
        this._indicator = null;
        this._settings = null;
        this._binPath = null;
        this._recording = false;
    }

    _toggle() {
        console.log('VoiceToText: _toggle called');
        if (this._recording) {
            this._stop();
        } else {
            this._start();
        }
    }

    _start() {
        console.log('VoiceToText: _start called');
        if (this._recording) return;

        if (!this._binPath) {
            console.log('VoiceToText: binary not found in PATH');
            this._showNotification('voice-to-text binary not found in PATH');
            return;
        }
        console.log('VoiceToText: binary found at', this._binPath);

        this._indicator.setProcessing();
        this._recording = true;

        let firstLevelReceived = false;
        this._recorder = new Recorder(this._binPath, this._settings);
        this._recorder.onAudioLevel = (level) => {
            if (!firstLevelReceived) {
                firstLevelReceived = true;
                this._indicator.setRecordingActive();
            }
            this._indicator.updateLevel(level);
        };
        this._recorder.onTranscription = (text) => {
            const outputMethod = this._settings.get_string('output-method');
            typeText(text, outputMethod, () => this._setIdle());
        };
        this._recorder.onError = (msg) => {
            this._showNotification('Transcription failed: ' + msg);
            this._setIdle();
        };
        this._recorder.start();
        if (this._settings.get_boolean('show-recording-notification')) {
            this._showNotification('Recording...');
        }
    }

    _stop() {
        console.log('VoiceToText: _stop called');
        if (!this._recording) return;
        
        this._recorder?.stop();
        this._indicator?.setProcessing();
        
        // Set a timeout to forcefully return to idle if the process doesn't exit
        // This prevents the spinner from hanging indefinitely
        const stopTimeoutSeconds = this._settings.get_int('stop-timeout-seconds');
        console.log(`VoiceToText: setting stop timeout for ${stopTimeoutSeconds} seconds`);
        
        if (this._stopTimeoutId) {
            GLib.source_remove(this._stopTimeoutId);
            this._stopTimeoutId = null;
        }
        
        this._stopTimeoutId = GLib.timeout_add_seconds(
            GLib.PRIORITY_DEFAULT,
            stopTimeoutSeconds,
            () => {
                console.log('VoiceToText: stop timeout reached, forcing idle state');
                this._forceStop();
                return GLib.SOURCE_REMOVE;
            }
        );
    }
    
    _forceStop() {
        if (this._stopTimeoutId) {
            GLib.source_remove(this._stopTimeoutId);
            this._stopTimeoutId = null;
        }
        
        if (this._recorder?._proc) {
            console.log('VoiceToText: forcefully killing process');
            const pid = this._recorder._proc;
            Gio.Subprocess.new(['kill', '-9', String(pid)], 0).wait_async(null, null);
        }
        
        this._setIdle();
    }

    _setIdle() {
        if (this._stopTimeoutId) {
            GLib.source_remove(this._stopTimeoutId);
            this._stopTimeoutId = null;
        }
        
        this._recording = false;
        this._indicator?.setRecording(false);
        this._recorder = null;
    }

    _showNotification(message) {
        const systemSource = MessageTray.getSystemSource();
        const notification = new MessageTray.Notification({
            source: systemSource,
            title: 'Voice to Text',
            body: message,
            iconName: 'audio-input-microphone-symbolic',
        });
        systemSource.addNotification(notification);
    }

    _registerHotkey() {
        this._unregisterHotkey();
        
        try {
            registerHotkey('hotkey', this._settings, () => this._toggle());
            console.log('VoiceToText: hotkey registered');
        } catch (e) {
            console.error('VoiceToText: failed to register hotkey:', e.message);
        }
    }

    _unregisterHotkey() {
        try {
unregisterHotkey('hotkey');
            console.log('VoiceToText: hotkey unregistered');
        } catch (e) {
            console.error('VoiceToText: failed to unregister hotkey:', e.message);
        }
    }

    _openPreferences() {
        console.log('VoiceToText: opening preferences dialog');
        try {
            const launcher = new Gio.SubprocessLauncher();
            launcher.spawnv(['gnome-extensions', 'prefs', this.uuid]);
        } catch (e) {
            console.error('VoiceToText: failed to open preferences:', e);
            this._showNotification('Failed to open preferences: ' + e.message);
        }
    }
}

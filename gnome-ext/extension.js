import GLib from 'gi://GLib';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import {VoiceIndicator} from './indicator.js';
import {Recorder} from './recorder.js';
import {registerHotkey, unregisterHotkey} from './hotkey.js';
import {typeText} from './typer.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';


export default class VoiceToTextExtension extends Extension {
    enable() {
        this._settings = this.getSettings('org.gnome.shell.extensions.voice-to-text');
        this._indicator = new VoiceIndicator();
        this._binPath = GLib.find_program_in_path('voice-to-text');
        this._recorder = null;
        this._recording = false;

        this._indicator.onStart = () => this._start();
        this._indicator.onStop = () => this._stop();

        Main.panel.addToStatusArea(this.uuid, this._indicator, 0, 'right');
        registerHotkey('hotkey', this._settings, () => this._toggle());
    }

    disable() {
        unregisterHotkey('hotkey');
        this._indicator?.destroy();
        this._recorder?.stop();
        this._settings = null;
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

        this._indicator.setRecording(true);
        this._recording = true;

        this._recorder = new Recorder(this._binPath);
        this._recorder.onAudioLevel = (level) => this._indicator.updateLevel(level);
        this._recorder.onTranscription = (text) => {
            typeText(text);
            this._setIdle();
        };
        this._recorder.onTimeout = () => {
            this._showNotification('Recording timed out after 5 minutes');
            this._setIdle();
        };
        this._recorder.onError = (msg) => {
            this._showNotification('Transcription failed: ' + msg);
            this._setIdle();
        };
        this._recorder.start();
        this._showNotification('Recording...');
    }

    _stop() {
        console.log('VoiceToText: _stop called');
        if (!this._recording) return;
        this._recorder?.stop();
        this._setIdle();
    }

    _setIdle() {
        this._recording = false;
        this._indicator.setRecording(false);
    }

    _showNotification(message) {
        Main.notify('Voice to Text', message);
    }
}

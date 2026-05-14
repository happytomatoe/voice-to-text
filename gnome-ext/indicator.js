import St from 'gi://St';
import Clutter from 'gi://Clutter';
import GObject from 'gi://GObject';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';

export const VoiceIndicator = GObject.registerClass(
class VoiceIndicator extends PanelMenu.Button {
    _init() {
        super._init(0.0, 'Voice to Text');
        this._buildUI();
        this._recording = false;
        this.onStart = null;
        this.onStop = null;
    }

    _buildUI() {
        this._bars = [];
        this._barBox = new St.BoxLayout({ style_class: 'vtt-bars' });
        for (let i = 0; i < 5; i++) {
            const bar = new St.Widget({
                style_class: 'vtt-bar',
                y_align: Clutter.ActorAlign.END,
            });
            this._barBox.add_child(bar);
            this._bars.push(bar);
        }

        this._startBtn = new St.Button({
            reactive: true,
            can_focus: true,
            track_hover: true,
        });
        this._startBtn.add_child(new St.Icon({
            icon_name: 'audio-input-microphone-symbolic',
            style_class: 'system-status-icon',
        }));
        this._startBtn.connect('clicked', () => this.onStart?.());

        this._stopBtn = new St.Button({
            reactive: true,
            can_focus: true,
            track_hover: true,
        });
        this._stopBtn.add_child(new St.Icon({
            icon_name: 'media-playback-stop-symbolic',
            style_class: 'system-status-icon',
        }));
        this._stopBtn.connect('clicked', () => this.onStop?.());

        const box = new St.BoxLayout();
        box.add_child(this._startBtn);
        box.add_child(this._barBox);
        box.add_child(this._stopBtn);
        this.add_child(box);

        this._setIdleUI();
    }

    setRecording(recording) {
        this._recording = recording;
        if (recording) {
            this._setRecordingUI();
        } else {
            this._setIdleUI();
        }
    }

    _setIdleUI() {
        this._startBtn.visible = true;
        this._barBox.hide();
        this._stopBtn.visible = false;
    }

    _setRecordingUI() {
        this._startBtn.visible = false;
        this._barBox.show();
        this._stopBtn.visible = true;
    }

    updateLevel(level) {
        this._bars.forEach((bar, i) => {
            const h = Math.max(4, Math.round(level * 8000));
            bar.set_height(h);
        });
    }
});

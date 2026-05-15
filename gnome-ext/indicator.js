import St from 'gi://St';
import Clutter from 'gi://Clutter';
import GObject from 'gi://GObject';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';

const NUM_BARS = 16;
const BAR_WIDTH = 3;
const BAR_MARGIN = 1;
const MAX_HEIGHT = 32;
const MIN_HEIGHT = 2;

export const VoiceIndicator = GObject.registerClass(
class VoiceIndicator extends PanelMenu.Button {
    _init() {
        super._init(0.0, 'Voice to Text');
        this._heights = new Array(NUM_BARS).fill(MIN_HEIGHT);
        this._destroyed = false;
        this._buildUI();
        this._recording = false;
        this.onStart = null;
        this.onStop = null;
    }

    _buildUI() {
        this._bars = [];
        this._barBox = new St.BoxLayout({
            style_class: 'vtt-bars',
            vertical: false,
            x_align: Clutter.ActorAlign.CENTER,
            y_align: Clutter.ActorAlign.END,
        });
        for (let i = 0; i < NUM_BARS; i++) {
            const bar = new St.Widget({
                style_class: 'vtt-bar',
                width: BAR_WIDTH,
                height: MIN_HEIGHT,
                x_expand: false,
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
        this._heights.fill(MIN_HEIGHT);
        this._barBox.hide();
        this._stopBtn.visible = false;
    }

    _setRecordingUI() {
        this._startBtn.visible = false;
        this._barBox.show();
        this._stopBtn.visible = true;
    }

    updateLevel(level) {
        if (this._destroyed) return;
        const h = Math.max(MIN_HEIGHT, Math.round(level * 8000));
        this._heights.fill(h);
        this._updateBarHeights();
    }

    updateBars(heights) {
        if (this._destroyed) return;
        for (let i = 0; i < NUM_BARS; i++) {
            this._heights[i] = Math.max(MIN_HEIGHT, Math.round(heights[i] ?? MIN_HEIGHT));
        }
        this._updateBarHeights();
    }

    _updateBarHeights() {
        if (this._destroyed) return;
        for (let i = 0; i < NUM_BARS; i++) {
            const h = this._heights[i];
            this._bars[i].set_height(h);
            const frac = h / MAX_HEIGHT;
            if (frac < 0.5) {
                this._bars[i].set_style('background-color: rgba(51, 217, 51, 0.9);');
            } else if (frac < 0.8) {
                this._bars[i].set_style('background-color: rgba(242, 204, 25, 0.9);');
            } else {
                this._bars[i].set_style('background-color: rgba(242, 51, 51, 0.9);');
            }
        }
    }

    destroy() {
        this._destroyed = true;
        super.destroy();
    }
});

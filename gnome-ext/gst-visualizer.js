import Gst from 'gi://Gst';
import GLib from 'gi://GLib';

const FFT_SIZE = 2048;
const SAMPLE_RATE = 44100;
const MIN_HEIGHT = 2;
const NOISE_FLOOR = 0.02;
const MAX_HEIGHT = 32;
const FRAMERATE = 20;

function fft(re, im) {
    const n = re.length;
    let j = 0;
    for (let i = 1; i < n; i++) {
        let bit = n >> 1;
        for (; j & bit; bit >>= 1) j ^= bit;
        j ^= bit;
        if (i < j) {
            [re[i], re[j]] = [re[j], re[i]];
            [im[i], im[j]] = [im[j], im[i]];
        }
    }
    for (let len = 2; len <= n; len <<= 1) {
        const ang = -2 * Math.PI / len;
        const wRe = Math.cos(ang);
        const wIm = Math.sin(ang);
        for (let i = 0; i < n; i += len) {
            let curRe = 1, curIm = 0;
            for (let k = 0; k < len / 2; k++) {
                const uRe = re[i + k];
                const uIm = im[i + k];
                const vRe = re[i + k + len / 2] * curRe - im[i + k + len / 2] * curIm;
                const vIm = re[i + k + len / 2] * curIm + im[i + k + len / 2] * curRe;
                re[i + k] = uRe + vRe;
                im[i + k] = uIm + vIm;
                re[i + k + len / 2] = uRe - vRe;
                im[i + k + len / 2] = uIm - vIm;
                const newRe = curRe * wRe - curIm * wIm;
                curIm = curRe * wIm + curIm * wRe;
                curRe = newRe;
            }
        }
    }
}

function hannWindow(n) {
    const w = new Float32Array(n);
    for (let i = 0; i < n; i++)
        w[i] = 0.5 * (1 - Math.cos(2 * Math.PI * i / (n - 1)));
    return w;
}

function buildLogMap(numBars, numBins) {
    const map = new Array(numBars).fill(null).map(() => []);
    const fMin = Math.log(20);
    const fMax = Math.log(20000);
    const binHz = SAMPLE_RATE / FFT_SIZE;

    for (let b = 1; b < numBins; b++) {
        const freq = b * binHz;
        if (freq < 20 || freq > 20000) continue;
        const logPos = (Math.log(freq) - fMin) / (fMax - fMin);
        const barIdx = Math.min(numBars - 1, Math.floor(logPos * numBars));
        map[barIdx].push(b);
    }
    for (let i = 0; i < numBars; i++) {
        if (map[i].length === 0) {
            const prev = i > 0 ? map[i - 1] : null;
            const next = i < numBars - 1 ? map[i + 1] : null;
            map[i] = prev && prev.length ? [prev[prev.length - 1]]
                   : next && next.length ? [next[0]] : [1];
        }
    }
    return map;
}

export class GstVisualizer {
    constructor(onFrame, { numBars = 16 } = {}) {
        this._onFrame = onFrame;
        this._numBars = numBars;
        this._running = false;
        this._gstInit = false;

        this._prevHeights = new Array(this._numBars).fill(MIN_HEIGHT);
        this._silentFrames = 0;

        this._hannWin = hannWindow(FFT_SIZE);
        this._pcmBuffer = new Float32Array(FFT_SIZE);
        this._fftRe = new Float32Array(FFT_SIZE);
        this._fftIm = new Float32Array(FFT_SIZE);
        this._mags = new Float32Array(FFT_SIZE / 2);
        this._barMags = new Float32Array(this._numBars);
        this._pcmFill = 0;
        this._logMap = buildLogMap(this._numBars, FFT_SIZE / 2);

        this._pipeline = null;
        this._appsink = null;
        this._pollId = null;
    }

    start() {
        if (this._running) return;
        this._running = true;

        if (!this._gstInit) {
            try {
                Gst.init(null);
            } catch (e) {
                console.log('GstVisualizer: Gst.init (may already be initialized)');
            }
            this._gstInit = true;
        }

        try {
            this._buildPipeline();
        } catch (e) {
            console.error('GstVisualizer: failed to start pipeline', e);
            this._running = false;
        }
    }

    _buildPipeline() {
        const pipelineStr =
            'pulsesrc ! audioconvert ! audioresample ! audio/x-raw,format=S16LE,rate=44100,channels=1 ! appsink name=sink max-buffers=4 drop=true sync=false';

        this._pipeline = Gst.parse_launch(pipelineStr);
        if (!this._pipeline) {
            throw new Error('Failed to parse pipeline');
        }

        this._appsink = this._pipeline.get_by_name('sink');
        if (!this._appsink) {
            throw new Error('Failed to get appsink element');
        }

        const stateChange = this._pipeline.set_state(Gst.State.PLAYING);
        if (stateChange === Gst.StateChangeReturn.FAILURE) {
            throw new Error('Failed to set pipeline to PLAYING');
        }

        const pollMs = Math.round(1000 / FRAMERATE);
        this._pollId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, pollMs, () => {
            this._pollSamples();
            return GLib.SOURCE_CONTINUE;
        });
    }

    _pollSamples() {
        if (!this._appsink) return;

        let sample;
        try {
            sample = this._appsink.emit('try-pull-sample', 0);
        } catch (e) {
            console.log('VTT pull error:', e.message);
            return;
        }
        if (!sample) {
            console.log('VTT no sample');
            return;
        }

        const buf = sample.get_buffer();
        if (!buf) return;

        const size = buf.get_size();
        if (size === 0) return;

        const data = buf.extract_dup(0, size);
        if (!data || data.length === 0) {
            console.log('VTT empty data');
            return;
        }

        console.log('VTT got', data.length, 'bytes');
        const numSamples = Math.floor(data.length / 2);
        this._processFFT(data, numSamples);
    }

    _processFFT(data, numSamples) {
        for (let i = 0; i < numSamples; i++) {
            const lo = data[i * 2];
            const hi = data[i * 2 + 1];
            let s = (hi << 8) | lo;
            if (s >= 32768) s -= 65536;
            this._pcmBuffer[this._pcmFill % FFT_SIZE] = s / 32768.0;
            this._pcmFill++;
        }

        if (this._pcmFill < FFT_SIZE) return;

        const offset = this._pcmFill % FFT_SIZE;
        for (let i = 0; i < FFT_SIZE; i++) {
            this._fftRe[i] = this._pcmBuffer[(offset + i) % FFT_SIZE] * this._hannWin[i];
            this._fftIm[i] = 0;
        }

        fft(this._fftRe, this._fftIm);

        const numBins = FFT_SIZE / 2;
        for (let i = 0; i < numBins; i++) {
            const mag = Math.sqrt(
                this._fftRe[i] * this._fftRe[i] + this._fftIm[i] * this._fftIm[i]
            ) / FFT_SIZE;
            this._mags[i] = mag > 0 ? 20 * Math.log10(mag) : -80;
        }

        let maxMag = 0.001;
        for (let i = 0; i < this._numBars; i++) {
            let best = 0;
            for (const b of this._logMap[i]) {
                const mag = this._mags[b];
                const norm = Math.max(0, (mag + 80) / 80);
                if (norm > best) best = norm;
            }
            this._barMags[i] = best;
            if (best > maxMag) maxMag = best;
        }

        for (let i = 0; i < this._numBars; i++) {
            this._barMags[i] /= maxMag;
        }

        let totalEnergy = 0;
        for (let i = 0; i < this._numBars; i++) {
            totalEnergy += this._barMags[i];
        }
        const isSilent = totalEnergy / this._numBars < NOISE_FLOOR;
        if (isSilent) this._silentFrames++; else this._silentFrames = 0;

        let changed = false;
        if (this._silentFrames >= 10) {
            for (let i = 0; i < this._numBars; i++) {
                if (this._prevHeights[i] !== MIN_HEIGHT) {
                    this._prevHeights[i] = MIN_HEIGHT;
                    changed = true;
                }
            }
        } else {
            const SMOOTH = 0.7;
            for (let i = 0; i < this._numBars; i++) {
                const target = this._barMags[i] * MAX_HEIGHT;
                const prev = this._prevHeights[i];
                const h = SMOOTH * prev + (1 - SMOOTH) * target;
                if (Math.abs(h - prev) > 0.3) {
                    this._prevHeights[i] = h;
                    changed = true;
                }
            }
        }

        if (this._onFrame) {
            console.log('VTT gst frame:', this._barMags.slice(0, 4).map(v => v.toFixed(3)).join(', '), 'silent:', this._silentFrames);
            this._onFrame({
                silentFrames: this._silentFrames,
                prevHeights: this._prevHeights,
                changed,
            });
        }
    }

    stop() {
        if (!this._running) return;
        this._running = false;

        if (this._pollId) {
            GLib.Source.remove(this._pollId);
            this._pollId = null;
        }

        try {
            if (this._pipeline) {
                this._pipeline.set_state(Gst.State.NULL);
            }
        } catch (e) {
            console.error('GstVisualizer: stop error', e);
        }

        this._pipeline = null;
        this._appsink = null;
        this._pcmFill = 0;
        this._prevHeights.fill(MIN_HEIGHT);
        this._silentFrames = 0;
    }
}

import Gst from 'gi://Gst';
import GLib from 'gi://GLib';

const N_FFT = 2048;
const SAMPLE_RATE = 44100;
const MIN_FREQ = 20;
const MAX_FREQ = 8000;
const NOISE_FLOOR = 0.02;
const ALPHA_RISE = 0.4;
const ALPHA_FALL = 0.15;

export class GstVisualizer {
    constructor(onFrame, { numBars = 16 } = {}) {
        this._onFrame = onFrame;
        this._numBars = numBars;
        this._prevHeights = new Float64Array(numBars);
        this._running = false;
        this._samples = new Int16Array(N_FFT);
        this._sampleCount = 0;
        this._silentFrames = 0;
        this._framePending = false;
        this._gstInit = false;

        this._real = new Float64Array(N_FFT);
        this._imag = new Float64Array(N_FFT);
        this._magnitudes = new Float64Array(N_FFT >> 1);

        this._precomputeBitRev();
        this._precomputeHann();
        this._precomputeFreqMap();
    }

    _bitReverse(x) {
        let result = 0;
        for (let i = 0; i < 11; i++) {
            result = (result << 1) | (x & 1);
            x >>= 1;
        }
        return result;
    }

    _precomputeBitRev() {
        this._bitRev = new Uint16Array(N_FFT);
        for (let i = 0; i < N_FFT; i++) {
            this._bitRev[i] = this._bitReverse(i);
        }
    }

    _precomputeHann() {
        this._hann = new Float64Array(N_FFT);
        for (let i = 0; i < N_FFT; i++) {
            this._hann[i] = 0.5 * (1 - Math.cos(2 * Math.PI * i / (N_FFT - 1)));
        }
    }

    _precomputeFreqMap() {
        const barFreqs = new Float64Array(this._numBars);
        for (let k = 0; k < this._numBars; k++) {
            barFreqs[k] = MIN_FREQ * Math.pow(MAX_FREQ / MIN_FREQ, k / (this._numBars - 1));
        }

        const barRanges = [];
        for (let k = 0; k < this._numBars; k++) {
            const fLow = k > 0 ? Math.sqrt(barFreqs[k - 1] * barFreqs[k]) : MIN_FREQ;
            const fHigh = k < this._numBars - 1
                ? Math.sqrt(barFreqs[k] * barFreqs[k + 1])
                : MAX_FREQ;
            barRanges.push({ low: fLow, high: fHigh });
        }

        const binFreq = SAMPLE_RATE / N_FFT;
        this._binsPerBar = [];
        this._allBins = [];
        for (let k = 0; k < this._numBars; k++) {
            this._binsPerBar[k] = [];
        }
        for (let bin = 1; bin < N_FFT / 2; bin++) {
            const freq = bin * binFreq;
            for (let k = 0; k < this._numBars; k++) {
                if (freq >= barRanges[k].low && freq < barRanges[k].high) {
                    this._binsPerBar[k].push(bin);
                    this._allBins.push(bin);
                    break;
                }
            }
        }
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

        const pipelineStr =
            'pulsesrc ! audioconvert ! audioresample ! audio/x-raw,format=S16LE,rate=44100,channels=1 ! appsink name=sink max-buffers=4 drop=true sync=false';
        try {
            this._pipeline = Gst.parse_launch(pipelineStr);
            if (!this._pipeline) {
                throw new Error('Failed to parse pipeline');
            }
            
            this._appsink = this._pipeline.get_by_name('sink');
            if (!this._appsink) {
                throw new Error('Failed to get appsink element');
            }
            
            this._appsink.props.emit_signals = true;
            this._appsink.connect('new-sample', () => this._onNewSample());
            this._pipeline.set_state(Gst.State.PLAYING);
        } catch (e) {
            console.error('GstVisualizer: failed to start pipeline', e);
            this._running = false;
        }
    }

    _onNewSample() {
        try {
            const sample = this._appsink.emit('pull-sample');
            if (!sample) return 0;

            const buffer = sample.get_buffer();
            if (!buffer) return 0;

            const [success, map] = buffer.map(Gst.MapFlags.READ);
            if (!success) return 0;

            const data = map.get_data();
            const numSamples = data.byteLength / 2;

            let offset = 0;
            while (offset < numSamples) {
                const remaining = N_FFT - this._sampleCount;
                const toCopy = Math.min(remaining, numSamples - offset);
                for (let i = 0; i < toCopy; i++) {
                    this._samples[this._sampleCount + i] =
                        (data[2 * (offset + i) + 1] << 8) | data[2 * (offset + i)];
                }
                this._sampleCount += toCopy;
                offset += toCopy;

                if (this._sampleCount >= N_FFT) {
                    this._processFFT();
                    this._sampleCount = 0;
                }
            }

            buffer.unmap(map);
        } catch (e) {
            console.error('GstVisualizer: _onNewSample error', e);
        }

        return 0;
    }

    _processFFT() {
        for (let i = 0; i < N_FFT; i++) {
            this._real[i] = this._samples[i] * this._hann[i];
            this._imag[i] = 0;
        }

        for (let i = 0; i < N_FFT; i++) {
            const j = this._bitRev[i];
            if (i < j) {
                const tre = this._real[i];
                this._real[i] = this._real[j];
                this._real[j] = tre;
                const tim = this._imag[i];
                this._imag[i] = this._imag[j];
                this._imag[j] = tim;
            }
        }

        for (let len = 2; len <= N_FFT; len <<= 1) {
            const halfLen = len >> 1;
            const wRe = Math.cos(-2 * Math.PI / len);
            const wIm = Math.sin(-2 * Math.PI / len);
            for (let i = 0; i < N_FFT; i += len) {
                let wr = 1, wi = 0;
                for (let j = 0; j < halfLen; j++) {
                    const tRe = wr * this._real[i + j + halfLen] - wi * this._imag[i + j + halfLen];
                    const tIm = wr * this._imag[i + j + halfLen] + wi * this._real[i + j + halfLen];
                    this._real[i + j + halfLen] = this._real[i + j] - tRe;
                    this._imag[i + j + halfLen] = this._imag[i + j] - tIm;
                    this._real[i + j] += tRe;
                    this._imag[i + j] += tIm;
                    const nwr = wr * wRe - wi * wIm;
                    wi = wr * wIm + wi * wRe;
                    wr = nwr;
                }
            }
        }

        for (let i = 0; i < N_FFT / 2; i++) {
            this._magnitudes[i] = Math.sqrt(
                this._real[i] * this._real[i] + this._imag[i] * this._imag[i]
            );
        }

        const targetHeights = new Float64Array(this._numBars);
        let maxMag = 0.001;
        for (let k = 0; k < this._numBars; k++) {
            const bins = this._binsPerBar[k];
            let sum = 0;
            for (const bin of bins) {
                sum += this._magnitudes[bin];
            }
            targetHeights[k] = sum / (bins.length || 1);
            maxMag = Math.max(maxMag, targetHeights[k]);
        }

        for (let k = 0; k < this._numBars; k++) {
            targetHeights[k] /= maxMag;
        }

        let totalEnergy = 0;
        for (let k = 0; k < this._numBars; k++) {
            totalEnergy += targetHeights[k];
        }
        const isSilent = totalEnergy / this._numBars < NOISE_FLOOR;

        if (isSilent) {
            this._silentFrames++;
        } else {
            this._silentFrames = 0;
        }

        let changed = false;
        for (let k = 0; k < this._numBars; k++) {
            const target = isSilent ? 0 : targetHeights[k];
            const prev = this._prevHeights[k];
            const alpha = target > prev ? ALPHA_RISE : ALPHA_FALL;
            const smoothed = prev + alpha * (target - prev);
            if (Math.abs(smoothed - prev) > 0.001) changed = true;
            this._prevHeights[k] = smoothed;
        }

        if (this._onFrame && changed && !this._framePending) {
            this._framePending = true;
            const heights = new Float64Array(this._prevHeights);
            const silentCount = this._silentFrames;
            GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
                this._framePending = false;
                try {
                    this._onFrame({
                        silentFrames: silentCount,
                        prevHeights: heights,
                        changed,
                    });
                } catch (e) {
                    console.error('GstVisualizer: onFrame error', e);
                }
                return GLib.SOURCE_REMOVE;
            });
        }
    }

    stop() {
        if (!this._running) return;
        this._running = false;
        try {
            if (this._pipeline) {
                this._pipeline.set_state(Gst.State.NULL);
            }
        } catch (e) {
            console.error('GstVisualizer: stop error', e);
        }
        this._pipeline = null;
        this._appsink = null;
        this._sampleCount = 0;
        this._framePending = false;
        this._prevHeights.fill(0);
        this._silentFrames = 0;
    }
}

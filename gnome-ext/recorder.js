import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import GioUnix from 'gi://GioUnix';

export class Recorder {
    constructor(pythonAppPath, settings) {
        this._appPath = pythonAppPath;
        this._settings = settings;
        this._proc = null;
        this._childWatchId = null;
        this._stdout = null;
        this._cancellable = null;
        this.onTranscription = null;
        this.onAudioLevel = null;
        this.onStreamingText = null;
        this.onError = null;
        this.onProcessExit = null;

        // Retry logic properties
        this._retryCount = 0;
        this._startTimeoutId = null;
        this._hasStarted = false;
        this._stopped = false;
    }

    start() {
        this._stopped = false;
        this._retryCount = 0;
        this._spawn();
    }

    _spawn() {
        this._hasStarted = false;
        const provider = this._settings.get_string('provider');
        const language = this._settings.get_string('language');
        const mode = this._settings.get_string('mode');
        const decreaseSpeakerVolume = this._settings.get_int(
            'decrease-speaker-volume'
        );
        const argv = [
            this._appPath,
            '--output',
            'stdout',
            '--provider',
            provider,
            '--language',
            language,
            '--mode',
            mode,
        ];
        if (mode === 'hybrid' || mode === 'streaming') {
            const streamingProvider =
                this._settings.get_string('streaming-provider');
            argv.push('--streaming-provider', streamingProvider);
        }
        if (mode === 'hybrid') {
            const batchProvider = this._settings.get_string('batch-provider');
            argv.push('--batch-provider', batchProvider);
        }
        if (decreaseSpeakerVolume > 0) {
            argv.push(
                '--decrease-speaker-volume',
                String(decreaseSpeakerVolume)
            );
        }
        const [ok, pid, stdin, stdout, stderr] = GLib.spawn_async_with_pipes(
            null,
            argv,
            null,
            GLib.SpawnFlags.DO_NOT_REAP_CHILD,
            null
        );

        if (!ok) {
            GLib.close(stdin);
            GLib.close(stdout);
            GLib.close(stderr);
            this.onError?.('Failed to spawn voice-to-text process');
            return;
        }

        GLib.close(stdin);
        GLib.close(stderr);

        this._proc = pid;
        this._cancellable = new Gio.Cancellable();
        this._stdout = new Gio.DataInputStream({
            base_stream: new GioUnix.InputStream({fd: stdout, close_fd: true}),
        });
        this._readOutput();

        this._clearStartTimeout();
        this._startTimeoutId = GLib.timeout_add_seconds(
            GLib.PRIORITY_DEFAULT,
            5,
            () => {
                console.log('VoiceToText: Start token timeout reached');
                this._handleStartTimeout();
                return GLib.SOURCE_REMOVE;
            }
        );

        this._childWatchId = GLib.child_watch_add(
            GLib.PRIORITY_DEFAULT,
            pid,
            (p, status) => {
                this._childWatchId = null;
                this._proc = null;
                GLib.spawn_close_pid(p);

                if (this._stopped) {
                    return;
                }

                if (!this._hasStarted) {
                    console.log('VoiceToText: Process exited before sending start token');
                    this._handleStartTimeout();
                } else {
                    this.onProcessExit?.();
                }
            }
        );
    }

    _clearStartTimeout() {
        if (this._startTimeoutId) {
            GLib.source_remove(this._startTimeoutId);
            this._startTimeoutId = null;
        }
    }

    _handleStartTimeout() {
        this._clearStartTimeout();

        if (this._childWatchId) {
            GLib.source_remove(this._childWatchId);
            this._childWatchId = null;
        }
        if (this._cancellable) {
            this._cancellable.cancel();
            this._cancellable = null;
        }
        if (this._proc) {
            const pid = this._proc;
            this._proc = null;
            Gio.Subprocess.new(['kill', '-9', String(pid)], 0).wait_async(
                null,
                null
            );
        }

        this._retryCount++;
        if (this._retryCount > 3) {
            console.log('VoiceToText: Failed to start after 3 retries');
            this.onError?.('Could not start the recording application. Start token not received after 3 retries.');
        } else {
            console.log(`VoiceToText: Retrying to spawn process (attempt ${this._retryCount + 1}/4)`);
            this._spawn();
        }
    }

    stop() {
        this._clearStartTimeout();

        if (!this._hasStarted) {
            this._stopped = true;
            if (this._cancellable) {
                this._cancellable.cancel();
                this._cancellable = null;
            }
            if (this._childWatchId) {
                GLib.source_remove(this._childWatchId);
                this._childWatchId = null;
            }
            if (this._proc) {
                const pid = this._proc;
                this._proc = null;
                Gio.Subprocess.new(['kill', '-9', String(pid)], 0).wait_async(
                    null,
                    null
                );
            }
        } else {
            if (this._proc) {
                const pid = this._proc;
                this._proc = null;
                Gio.Subprocess.new(['kill', '-INT', String(pid)], 0).wait_async(
                    null,
                    null
                );
            }
        }
    }

    _readOutput() {
        this._stdout.read_line_async(
            GLib.PRIORITY_DEFAULT,
            this._cancellable,
            (src, res) => {
                let line;
                try {
                    [line] = src.read_line_finish_utf8(res);
                } catch (e) {
                    return;
                }

                if (line === null) return;

                const trimmedLine = line.trim();
                if (trimmedLine === 'START') {
                    console.log('VoiceToText: received START token');
                    this._hasStarted = true;
                    this._clearStartTimeout();
                } else if (trimmedLine.startsWith('LEVEL:')) {
                    const level = parseFloat(trimmedLine.slice(6));
                    if (!Number.isNaN(level)) {
                        this.onAudioLevel?.(level);
                    }
                } else if (trimmedLine.startsWith('STREAM:')) {
                    const text = trimmedLine.slice(7).trim();
                    this.onStreamingText?.(text);
                } else if (trimmedLine.startsWith('TEXT:')) {
                    const text = trimmedLine.slice(5).trim();
                    console.log('VoiceToText: received TEXT:', text);
                    this.onTranscription?.(text);
                } else if (trimmedLine.startsWith('ERROR:')) {
                    const errorMsg = trimmedLine.slice(6).trim();
                    console.log('VoiceToText: received ERROR:', errorMsg);
                    this.stop();
                    this.onError?.(errorMsg);
                    return;
                }

                this._readOutput();
            }
        );
    }
}

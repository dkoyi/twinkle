// Capture mono audio, resample continuously, and send 20 ms little-endian PCM16.
class MicrophoneCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.pending = [];
    this.position = 0;
    this.frame = new ArrayBuffer(640);
    this.view = new DataView(this.frame);
    this.count = 0;
  }
  process(inputs) {
    const channel = inputs[0]?.[0];
    if (!channel) return true;
    for (const value of channel) this.pending.push(value);
    const ratio = sampleRate / 16000;
    while (this.position + 1 < this.pending.length) {
      const i = Math.floor(this.position), fraction = this.position - i;
      const value = Math.max(-1, Math.min(1,
        this.pending[i] * (1 - fraction) + this.pending[i + 1] * fraction));
      this.view.setInt16(this.count++ * 2, Math.round(value * (value < 0 ? 32768 : 32767)), true);
      if (this.count === 320) {
        this.port.postMessage(this.frame, [this.frame]);
        this.frame = new ArrayBuffer(640);
        this.view = new DataView(this.frame);
        this.count = 0;
      }
      this.position += ratio;
    }
    const consumed = Math.min(Math.floor(this.position), this.pending.length);
    this.pending.splice(0, consumed);
    this.position -= consumed;
    return true;
  }
}
registerProcessor('microphone-capture', MicrophoneCapture);

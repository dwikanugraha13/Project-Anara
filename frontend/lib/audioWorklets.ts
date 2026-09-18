/**
 * audioWorklets.ts — Audio Worklet Processors for Project Anara.
 * Full parity with Anara audio worklet standards.
 */

export const CALIBRATION_WORKLET_CODE = `
class CalibrationRecorderProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buf = new Float32Array(4096);
    this._idx = 0;
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;

    const samples = input[0];
    for (let i = 0; i < samples.length; i++) {
      this._buf[this._idx++] = samples[i];
      if (this._idx >= this._buf.length) {
        const copy = this._buf.slice();
        this.port.postMessage(copy, [copy.buffer]);
        this._idx = 0;
      }
    }
    return true;
  }
}

registerProcessor('calibration-recorder', CalibrationRecorderProcessor);
`;

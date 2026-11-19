import type { Alignment, Role } from './model.ts';

const sampleRate = 8000;
const framesPerSecond = 100;
const hop = sampleRate / framesPerSecond;
const windowSize = 256;
const bandEdges = [4, 10, 22, 43, 75, 128];
const bandCount = bandEdges.length - 1;
export const analysisSeconds = 300;

export type AudioMatch = {
  alignment: Exclude<Alignment, { method: 'manual' }>;
  offsets?: Record<Role, number>;
};

// The same transform serves both the short spectral windows and lag correlation.
class FFT {
  private size: number;
  private reversed: Uint32Array;
  private cosine: Float64Array;
  private sine: Float64Array;

  constructor(size: number) {
    this.size = size;
    this.reversed = new Uint32Array(size);
    this.cosine = new Float64Array(size / 2);
    this.sine = new Float64Array(size / 2);
    for (let i = 1; i < size; i++) {
      this.reversed[i] = (this.reversed[i >> 1] >> 1) | ((i & 1) * (size / 2));
    }
    for (let i = 0; i < size / 2; i++) {
      const angle = -2 * Math.PI * i / size;
      this.cosine[i] = Math.cos(angle);
      this.sine[i] = Math.sin(angle);
    }
  }

  transform(real: Float64Array, imag: Float64Array, inverse = false) {
    const size = this.size;
    for (let i = 0; i < size; i++) {
      const j = this.reversed[i];
      if (j > i) {
        [real[i], real[j]] = [real[j], real[i]];
        [imag[i], imag[j]] = [imag[j], imag[i]];
      }
    }
    for (let width = 2; width <= size; width *= 2) {
      const half = width / 2;
      const step = size / width;
      for (let start = 0; start < size; start += width) {
        for (let i = 0; i < half; i++) {
          const a = start + i;
          const b = a + half;
          const c = this.cosine[i * step];
          const s = this.sine[i * step] * (inverse ? -1 : 1);
          const r = real[b] * c - imag[b] * s;
          const m = real[b] * s + imag[b] * c;
          real[b] = real[a] - r;
          imag[b] = imag[a] - m;
          real[a] += r;
          imag[a] += m;
        }
      }
    }
    if (inverse) {
      for (let i = 0; i < size; i++) {
        real[i] /= size;
        imag[i] /= size;
      }
    }
  }
}

const spectralFFT = new FFT(windowSize);
const hann = Float64Array.from({ length: windowSize }, (_, i) => .5 - .5 * Math.cos(2 * Math.PI * i / (windowSize - 1)));

// Retain only short PCM windows and five onset-strength samples per centisecond.
export class AudioFingerprint {
  readonly bands: number[][] = Array.from({ length: bandCount }, () => []);
  private pcm = new Float64Array(windowSize);
  private real = new Float64Array(windowSize);
  private imag = new Float64Array(windowSize);
  private previous = Array.from({ length: 3 }, () => new Float64Array(bandCount));
  private frame = 0;
  private bin = 0;
  private sum = 0;
  private count = 0;

  append(channels: Float32Array[], nativeRate: number, timestamp: number) {
    if (!channels.length || !Number.isFinite(timestamp) || !Number.isFinite(nativeRate) || nativeRate <= 0) return;
    const start = Math.round(timestamp * nativeRate);
    const ratio = sampleRate / nativeRate;
    for (let i = 0; i < channels[0].length; i++) {
      const next = Math.floor((start + i) * ratio);
      if (next < this.bin) continue;
      const limit = Math.min(next, sampleRate * analysisSeconds);
      while (this.bin < limit) {
        this.write(this.count ? this.sum / this.count : 0);
        this.bin++;
        this.sum = 0;
        this.count = 0;
      }
      if (next >= sampleRate * analysisSeconds) return;
      let mono = 0;
      for (const channel of channels) mono += channel[i];
      this.sum += mono / channels.length;
      this.count++;
    }
  }

  private write(value: number) {
    this.pcm[this.bin % windowSize] = value;
    const start = this.bin + 1 - windowSize;
    if (start < 0 || start % hop !== 0) return;
    for (let i = 0; i < windowSize; i++) {
      this.real[i] = this.pcm[(start + i) % windowSize] * hann[i];
    }
    this.imag.fill(0);
    spectralFFT.transform(this.real, this.imag);
    const previous = this.previous[this.frame % this.previous.length];
    for (let band = 0; band < bandCount; band++) {
      const lo = bandEdges[band];
      const hi = bandEdges[band + 1];
      let energy = 0;
      for (let i = lo; i < hi; i++) energy += this.real[i] ** 2 + this.imag[i] ** 2;
      const logEnergy = Math.log1p(100 * energy / (hi - lo));
      if (this.frame >= this.previous.length) {
        this.bands[band].push(Math.min(4, Math.max(0, logEnergy - previous[band])));
      }
      previous[band] = logEnergy;
    }
    this.frame++;
  }
}

function prefixSums(values: number[]) {
  const sum = new Float64Array(values.length + 1);
  const square = new Float64Array(values.length + 1);
  for (let i = 0; i < values.length; i++) {
    sum[i + 1] = sum[i] + values[i];
    square[i + 1] = square[i] + values[i] ** 2;
  }
  return { sum, square };
}

function normalized(sum: number, aSum: number, bSum: number, aSquare: number, bSquare: number, length: number) {
  const aVariance = Math.max(0, aSquare - aSum ** 2 / length);
  const bVariance = Math.max(0, bSquare - bSum ** 2 / length);
  const scale = Math.sqrt(aVariance * bVariance);
  return scale > 1e-8 ? (sum - aSum * bSum / length) / scale : 0;
}

function correlate(a: number[][], b: number[][], minLength: number) {
  const aLength = a[0].length;
  const bLength = b[0].length;
  const firstLag = minLength - aLength;
  const lastLag = bLength - minLength;
  const scores = new Float64Array(lastLag - firstLag + 1);
  const size = 2 ** Math.ceil(Math.log2(aLength + bLength - 1));
  const fft = new FFT(size);
  const ar = new Float64Array(size), ai = new Float64Array(size);
  const br = new Float64Array(size), bi = new Float64Array(size);
  for (let band = 0; band < bandCount; band++) {
    const left = a[band], right = b[band];
    const p = prefixSums(left), q = prefixSums(right);
    ar.fill(0); ai.fill(0); br.fill(0); bi.fill(0);
    ar.set(left); br.set(right);
    fft.transform(ar, ai);
    fft.transform(br, bi);
    for (let i = 0; i < size; i++) {
      const real = ar[i] * br[i] + ai[i] * bi[i];
      ai[i] = ar[i] * bi[i] - ai[i] * br[i];
      ar[i] = real;
    }
    fft.transform(ar, ai, true);
    for (let lag = firstLag; lag <= lastLag; lag++) {
      const i = Math.max(0, -lag), j = Math.max(0, lag);
      const length = Math.min(aLength - i, bLength - j);
      scores[lag - firstLag] += normalized(
        ar[(lag + size) % size],
        p.sum[i + length] - p.sum[i], q.sum[j + length] - q.sum[j],
        p.square[i + length] - p.square[i], q.square[j + length] - q.square[j], length,
      ) / bandCount;
    }
  }
  let peak = 0;
  for (let i = 1; i < scores.length; i++) if (scores[i] > scores[peak]) peak = i;
  let runnerUp = 0;
  for (let i = 0; i < scores.length; i++) {
    if (Math.abs(i - peak) > 30) runnerUp = Math.max(runnerUp, scores[i]);
  }
  return { lag: peak + firstLag, score: scores[peak], runnerUp };
}

function match(a: number[][], b: number[][]) {
  const shortest = Math.min(a[0].length, b[0].length);
  if (shortest < 3 * framesPerSecond) return;
  const minimum = Math.min(shortest, Math.max(3 * framesPerSecond, Math.ceil(shortest * .45)));
  const best = correlate(a, b, minimum);
  if (best.score < .18 || best.score - best.runnerUp < .07) return;

  // Verify the peak in disjoint sections, rejecting isolated events and changing offsets.
  const start = Math.max(0, -best.lag);
  const end = Math.min(a[0].length, b[0].length - best.lag);
  const third = Math.floor((end - start) / 3);
  const agreeing: number[] = [];
  for (let section = 0; section < 3; section++) {
    const from = start + section * third;
    const to = from + third;
    const window = a.map(band => band.slice(from, to));
    const clipStart = Math.max(0, from + best.lag - 30);
    const clipEnd = Math.min(b[0].length, to + best.lag + 30);
    const clip = b.map(band => band.slice(clipStart, clipEnd));
    const local = correlate(window, clip, third);
    const lag = local.lag + clipStart - from;
    if (local.score >= .15) agreeing.push(lag);
  }
  if (agreeing.length < 2 || agreeing.some(lag => Math.abs(lag - best.lag) > 3)) return;
  return { offset: best.lag / framesPerSecond, score: Math.min(1, best.score) };
}

export function alignAudio(tracks: Record<Role, AudioFingerprint>): AudioMatch {
  const left = match(tracks.ego.bands, tracks.left.bands);
  const right = match(tracks.ego.bands, tracks.right.bands);
  if (!left || !right) return { alignment: { method: 'unverified', reason: 'weak-match' } };
  const start = Math.max(0, -left.offset, -right.offset);
  const end = Math.min(
    tracks.ego.bands[0].length / framesPerSecond,
    tracks.left.bands[0].length / framesPerSecond - left.offset,
    tracks.right.bands[0].length / framesPerSecond - right.offset,
  );
  if (start >= end) return { alignment: { method: 'unverified', reason: 'no-overlap' } };
  const wrists = match(tracks.left.bands, tracks.right.bands);
  if (wrists && Math.abs(wrists.offset - (right.offset - left.offset)) > .04) {
    return { alignment: { method: 'unverified', reason: 'weak-match' } };
  }
  return {
    alignment: { method: 'audio', scores: { left: left.score, right: right.score } },
    offsets: { ego: 0, left: left.offset, right: right.offset },
  };
}

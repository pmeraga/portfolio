import { spawn } from 'node:child_process';
import { resolve } from 'node:path';
import { alignAudio, analysisSeconds, AudioFingerprint } from '../lib/audio-alignment.ts';

const args = process.argv.slice(2);
if (args.length !== 3) {
  console.error('Usage: node scripts/sync-episode.mjs <ego video> <left wrist video> <right wrist video>');
  process.exit(2);
}

const sampleRate = 8000;
async function fingerprint(file) {
  const audio = new AudioFingerprint();
  const ffmpeg = spawn(process.env.FFMPEG || 'ffmpeg', [
    '-nostdin', '-v', 'error', '-i', resolve(file), '-map', '0:a:0',
    '-t', String(analysisSeconds), '-ac', '1',
    '-af', `aresample=${sampleRate}:async=1:first_pts=0`,
    '-f', 'f32le', '-',
  ], { stdio: ['ignore', 'pipe', 'pipe'] });
  let errors = '';
  ffmpeg.stderr.setEncoding('utf8').on('data', chunk => { errors = (errors + chunk).slice(-4000); });
  const exit = new Promise(resolve => {
    ffmpeg.once('error', error => resolve({ error }));
    ffmpeg.once('close', code => resolve({ code }));
  });
  let tail = Buffer.alloc(0);
  let position = 0;
  for await (const chunk of ffmpeg.stdout) {
    const data = tail.length ? Buffer.concat([tail, chunk]) : chunk;
    const samples = new Float32Array(Math.floor(data.length / 4));
    for (let i = 0; i < samples.length; i++) samples[i] = data.readFloatLE(i * 4);
    audio.append([samples], sampleRate, position / sampleRate);
    position += samples.length;
    tail = data.subarray(samples.length * 4);
  }
  const result = await exit;
  if (result.error) throw result.error;
  if (result.code !== 0) {
    if (/matches no streams/.test(errors)) return null;
    throw Error(errors.trim() || 'FFmpeg could not decode this recording.');
  }
  return audio;
}

try {
  const [ego, left, right] = await Promise.all(args.map(fingerprint));
  const result = ego && left && right
    ? alignAudio({ ego, left, right })
    : { alignment: { method: 'unverified', reason: 'missing-audio' } };
  console.log(JSON.stringify(result));
  if (!result.offsets) process.exitCode = 1;
} catch (error) {
  console.error(error.message);
  console.log(JSON.stringify({ alignment: { method: 'unverified', reason: 'decode-failed' } }));
  process.exitCode = 1;
}

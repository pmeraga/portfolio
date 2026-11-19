import test from 'node:test';
import assert from 'node:assert/strict';
import {alignAudio,AudioFingerprint} from '../lib/audio-alignment.ts';
import {overlap} from '../lib/model.ts';
test('aligned recordings use the shortest duration',()=>assert.deepEqual(overlap([{duration:20,offset:0},{duration:18,offset:0},{duration:22,offset:0}]),{start:0,end:18,duration:18}));
test('positive wrist offset trims its end',()=>assert.deepEqual(overlap([{duration:20,offset:0},{duration:18,offset:2},{duration:22,offset:0}]),{start:0,end:16,duration:16}));
test('negative offset trims the beginning of the shared timeline',()=>assert.deepEqual(overlap([{duration:20,offset:0},{duration:18,offset:-3},{duration:22,offset:2}]),{start:3,end:20,duration:17}));
test('nonoverlapping recordings produce zero duration',()=>assert.equal(overlap([{duration:2,offset:0},{duration:2,offset:5}]).duration,0));
test('all camera times stay within valid recording boundaries',()=>{const cameras=[{duration:31.6,offset:0},{duration:29.2,offset:-2.5},{duration:34.8,offset:1.7}];const r=overlap(cameras);for(let t=r.start;t<=r.end;t+=.01)for(const c of cameras){assert.ok(t+c.offset>=-1e-9);assert.ok(t+c.offset<=c.duration+1e-9);}});

function audio(size, seed) {
 const signal=new Float32Array(size);
 const random=()=>{
  seed=(Math.imul(seed,1664525)+1013904223)>>>0;
  return seed/2**32;
 };
 let next=0,start=0,end=0,frequency=0,gain=0;
 for(let i=0;i<size;i++){
  if(i===next){
   start=i;
   end=i+Math.floor(180+900*random());
   next=end+Math.floor(400+2100*random());
   frequency=(200+3000*random())/8000;
   gain=.2+.55*random();
  }
  const envelope=i<end?Math.sin(Math.PI*(i-start)/(end-start)):0;
  signal[i]=gain*envelope*Math.sin(2*Math.PI*frequency*i)+.002*(random()-.5);
 }
 return signal;
}

function fingerprint(signal) {
 const track=new AudioFingerprint();
 // The packet size intentionally does not align with the fingerprint hop.
 for(let i=0;i<signal.length;i+=1024)track.append([signal.subarray(i,i+1024)],8000,i/8000);
 return track;
}

test('shared audio recovers both signs with different gains and starts',()=>{
 const source=audio(16*8000,14);
 const result=alignAudio({
  ego:fingerprint(source.slice(2*8000,14*8000)),
  left:fingerprint(source.slice(8000,13*8000).map(sample=>sample*.6)),
  right:fingerprint(source.slice(4*8000,16*8000).map(sample=>sample*1.2)),
 });
 assert.equal(result.alignment.method,'audio');
 assert.deepEqual(result.offsets,{ego:0,left:1,right:-2});
});

test('one silent camera prevents partial results from being applied',()=>{
 const source=fingerprint(audio(10*8000,14));
 const result=alignAudio({ego:source,left:source,right:fingerprint(new Float32Array(10*8000))});
 assert.deepEqual(result,{alignment:{method:'unverified',reason:'weak-match'}});
});

test('repeating audio with no unique lag needs review',()=>{
 const loop=audio(8000,42);
 const repeating=Float32Array.from({length:10*8000},(_,i)=>loop[i%loop.length]);
 const track=fingerprint(repeating);
 assert.deepEqual(alignAudio({ego:track,left:track,right:track}),{alignment:{method:'unverified',reason:'weak-match'}});
});

export const roles = ['ego', 'left', 'right'] as const;
export type Role = typeof roles[number];
export const labels: Record<Role,string> = {ego:'Egocentric',left:'Left wrist',right:'Right wrist'};
export type Camera = {role:Role; filename:string; size:number; duration:number; width:number; height:number; mime:string; offset:number; key?:string; uploadId?:string; uploaded?:boolean};
export const alignmentFailureReasons = ['missing-audio', 'weak-match', 'decode-failed', 'no-overlap'] as const;
export type AlignmentFailure = typeof alignmentFailureReasons[number];
export type Alignment =
 | {method:'audio'; scores:Record<Exclude<Role,'ego'>,number>}
 | {method:'unverified'; reason:AlignmentFailure}
 | {method:'manual'};
export type Episode = {id:string; name:string; createdAt:string; status:string; cameras:Camera[]; description?:string; demo?:boolean; alignment?:Alignment};
export function overlap(cameras:Pick<Camera,'duration'|'offset'>[]) {
 const start = Math.max(0,...cameras.map(c=>-c.offset));
 const end = Math.min(...cameras.map(c=>c.duration-c.offset));
 return {start, end:Math.max(start,end), duration:Math.max(0,end-start)};
}
export function formatTime(n:number) {if(!Number.isFinite(n)) return '00:00'; return `${Math.floor(Math.max(0,n)/60).toString().padStart(2,'0')}:${Math.floor(Math.max(0,n)%60).toString().padStart(2,'0')}`;}
export function bytes(n:number) {return n>=1073741824?`${(n/1073741824).toFixed(2)} GB`:`${(n/1048576).toFixed(1)} MB`;}
export const demo:Episode={id:'demo',name:'Pick & place · calibration study',description:'Synthetic multi-camera demonstration. Generated sample footage.',createdAt:'2026-10-24T12:00:00Z',status:'ready',demo:true,cameras:roles.map(role=>({role,filename:`synthetic_${role}.mp4`,size:0,duration:12,width:960,height:540,mime:'video/mp4',offset:0,uploaded:true}))};

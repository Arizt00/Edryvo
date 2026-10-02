// Uses Emma's own local inference API. No Emma profile, memory or credentials are read.
import {pathToFileURL} from 'node:url';
import path from 'node:path';
import readline from 'node:readline';
const emit=value=>process.stdout.write(JSON.stringify(value)+'\n');
let runtime;
try {
 const directory=process.argv[2];
 const {NativeInferenceRuntime}=await import(pathToFileURL(path.join(directory,'electron','inference-runtime.mjs')).href);
 runtime=new NativeInferenceRuntime({directory:path.join(directory,'resources','inference')});
 const status=runtime.status({});
 if(!status.available)throw new Error(status.reason||'El modelo local de Emma no está disponible.');
 emit({type:'ready',model:status.model,provider:status.provider});
 if(process.argv.includes('--models'))process.exit(0);
 const lines=readline.createInterface({input:process.stdin});
 const controller=new AbortController();let started=false;
 lines.on('line',async line=>{
  try{
   const request=JSON.parse(line);
   if(request.cancel){controller.abort();runtime.stop();return;}
   if(started)return;started=true;
   emit({type:'status',message:'Cargando el modelo local de Emma…'});
   const result=await runtime.complete({settings:{localContextTokens:4096,localGpuLayers:48},messages:request.messages,signal:controller.signal,maxTokens:request.maxTokens,onDelta:text=>emit({type:'delta',text})});
   emit({type:'done',metrics:result.metrics});
  }catch(error){emit({type:'error',message:error.message});}
  finally{runtime.stop();lines.close();setTimeout(()=>process.exit(0),50);}
 });
 process.stdin.on('end',()=>{controller.abort();runtime.stop();});
}catch(error){emit({type:'error',message:error.message});runtime?.stop();process.exitCode=1;}

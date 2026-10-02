/** A PTY is an ordered byte stream. Concurrent HTTP writes must never reorder keys. */
export class OrderedTerminalInput {
  constructor(send){this.send=send;this.pending=[];this.sending=false;this.error=null;}
  write(data){
    if(this.error)return Promise.reject(this.error);
    if(typeof data!=='string'||data.length>65536)return Promise.reject(new Error('Entrada de terminal demasiado grande.'));
    if(!data)return Promise.resolve();
    return new Promise((resolve,reject)=>{this.pending.push({data,resolve,reject});this.flush();});
  }
  async flush(){
    if(this.sending)return;this.sending=true;
    try{
      while(this.pending.length&&!this.error){
        const batch=[];let size=0;
        while(this.pending.length&&size+this.pending[0].data.length<=65536){const item=this.pending.shift();batch.push(item);size+=item.data.length;}
        try{await this.send(batch.map(x=>x.data).join(''));for(const item of batch)item.resolve();}
        catch(error){for(const item of batch)item.reject(error);this.close(error);}
      }
    }finally{this.sending=false;}
  }
  close(error=new Error('La sesión de terminal está cerrada.')){this.error=error;for(const item of this.pending.splice(0))item.reject(error);}
}

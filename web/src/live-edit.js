// A stream owns one model revision. Monaco normalizes inserted LF to the model's
// CRLF on Windows; compare against the resulting buffer, never the wire text.
export class LiveEditSession {
  constructor(editor, snapshot=null) {
    this.editor=editor;this.path=snapshot?.path??editor.current;this.record=editor.models?.get(this.path);this.model=this.record?.model||editor.view?.getModel?.();
    this.expected=snapshot?.text??editor.getValue();this.version=snapshot?.version??this.model?.getVersionId();
    this.changed=false;this.complete=false;this.applying=false;this.interrupted=false;
    this.model?.pushStackElement?.();
    this.listener=this.model?.onDidChangeContent?.(()=>{if(!this.applying)this.interrupted=true;});
  }
  assertCurrent(){
    const ed=this.editor;
    if(this.interrupted||this.model?.isDisposed?.()||(this.record&&ed.models.get(this.path)!==this.record)||
      (this.model?this.model.getValue():ed.getValue())!==this.expected||
      (!this.model&&ed.current!==this.path)||(this.model&&this.model.getVersionId()!==this.version))
      throw new Error('Edición en vivo detenida: el archivo cambió. Tus cambios se conservan.');
  }
  apply(stream){
    this.assertCurrent();
    const opening=/^ {0,3}(`{3,}|~{3,})[^\r\n]*\r?\n/m.exec(stream);
    if(!opening)return;
    let body=stream.slice(opening.index+opening[0].length);
    const fence=opening[1][0],closing=new RegExp('^ {0,3}'+fence+'{'+opening[1].length+',}[ \\t]*(?:\\r?\\n|$)','m').exec(body);
    this.complete=!!closing;
    // A split closing fence must not briefly become part of the source.
    if(closing)body=body.slice(0,closing.index);
    else body=body.replace(new RegExp('(?:^|\\n)[ \\t]*'+fence+'{1,'+opening[1].length+'}$'),'');
    const eol=this.model?.getEOL?.()||'\n';
    const proposed=body.replace(/\r\n?|\n/g,eol),before=this.expected;
    if(proposed===before)return;
    this.applying=true;
    try{
      if(this.model){
        let prefix=0,end=before.length,tail=proposed.length;
        while(prefix<end&&prefix<tail&&before[prefix]===proposed[prefix])prefix++;
        while(end>prefix&&tail>prefix&&before[end-1]===proposed[tail-1]){end--;tail--;}
        const a=this.model.getPositionAt(prefix),b=this.model.getPositionAt(end);
        this.model.pushEditOperations(null,[{range:{startLineNumber:a.lineNumber,startColumn:a.column,endLineNumber:b.lineNumber,endColumn:b.column},text:proposed.slice(prefix,tail),forceMoveMarkers:true}],()=>null);
      }else this.editor.setValue(proposed);
      this.expected=this.model?this.model.getValue():this.editor.getValue();this.version=this.model?.getVersionId();this.changed=true;
      if(this.record)this.record.value=this.expected;
    }finally{this.applying=false;}
  }
  dispose(){this.listener?.dispose();if(!this.model?.isDisposed?.())this.model?.pushStackElement?.();}
}

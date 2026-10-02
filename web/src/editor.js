import {installMonacoOverlays} from './monaco-overlays.js';
import {themePalette} from './extension-theme.js';
import {escapeHTML, icon} from './icons.js';
// Monaco rejects outstanding worker requests when a model/provider is disposed.
// Handle only that expected cancellation; other editor failures still surface.
window.addEventListener('unhandledrejection',event=>{
  const reason=event.reason;
  if(reason?.name==='Canceled'&&reason?.message==='Canceled'&&String(reason.stack).includes('/vendor/monaco/'))event.preventDefault();
});

const languages = Object.assign(Object.create(null), {cs:'csharp',fs:'fsharp',fsx:'fsharp',vb:'vb',js:'javascript',jsx:'javascript',mjs:'javascript',cjs:'javascript',ts:'typescript',tsx:'typescript',json:'json',jsonc:'json',py:'python',pyw:'python',c:'c',h:'cpp',hpp:'cpp',cpp:'cpp',cc:'cpp',cxx:'cpp',rs:'rust',css:'css',scss:'scss',less:'less',html:'html',htm:'html',htmll:'html',md:'markdown',markdown:'markdown',s:'asm',asm:'asm',n:'nc',nc:'nc',nm:'nc',ncp:'nc',nb:'nc',nbb:'nc',xml:'xml',svg:'xml',sh:'shell',bash:'shell',zsh:'shell',ps1:'powershell',psm1:'powershell',bat:'bat',cmd:'bat',yml:'yaml',yaml:'yaml',java:'java',go:'go',kt:'kotlin',kts:'kotlin',swift:'swift',rb:'ruby',php:'php',pl:'perl',pm:'perl',lua:'lua',r:'r',jl:'julia',dart:'dart',ex:'elixir',exs:'elixir',erl:'erlang',hrl:'erlang',hs:'haskell',scala:'scala',clj:'clojure',sql:'sql',toml:'ini',ini:'ini',conf:'ini',cmake:'cmake',make:'makefile',zig:'zig',pas:'pascal',f90:'fortran',f:'fortran',cob:'cobol',tex:'latex',proto:'protobuf',graphql:'graphql',vue:'html',svelte:'html',ipynb:'json'});
let contributedAssociations=new Map();
export const languageFor = path => {
  const normalized=String(path||'').replaceAll('\\','/').toLowerCase(),name=normalized.split('/').at(-1);
  if(name==='cmakelists.txt')return 'cmake';if(name==='makefile'||name==='gnumakefile')return 'makefile';if(name==='dockerfile')return 'dockerfile';
  const extra=[...contributedAssociations.entries()].sort((a,b)=>b[0].length-a[0].length).find(([suffix])=>normalized.endsWith(suffix));
  return extra?.[1]||languages[normalized.split('.').pop()]||'plaintext';
};
export const languageLabel = path => ({csharp:'C#',javascript:'JavaScript',typescript:'TypeScript',cpp:'C++',c:'C',python:'Python',rust:'Rust',asm:'ASM',nc:'nC',plaintext:'Plain Text',markdown:'Markdown',json:'JSON',css:'CSS',html:'HTML'}[languageFor(path)] || languageFor(path));
const keywords = new Set(('using namespace public private protected internal class sealed abstract static readonly const void float double int long short byte string bool char var new return if else for foreach while do switch case default break continue null true false this base override virtual async await interface enum struct get set in out ref try catch finally throw sizeof typeof import from def print for in is not and or pass with as lambda yield global nonlocal elif None True False match fn let mut impl use pub mod self trait extern unsafe auto unsigned signed volatile template typename std include define primitive stc fa strictly binary bind raw probe').split(' '));
const types = new Set(('MonoBehaviour Vector2 Vector3 Vector4 Quaternion Transform Rigidbody Camera Time Input Mathf Debug Header SerializeField List Dictionary HashSet Console String Object Task int32_t uint32_t size_t uint64_t float32 bool8 vec3 mat4').split(' '));

export function highlighted(text, path='') {
  if (text.length > 180000) return escapeHTML(text);
  const py = languageFor(path) === 'python';
  const re = /\/\*[\s\S]*?(?:\*\/|$)|\/\/[^\n]*|#[^\n]*|(?:@?"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)|\b\d+(?:\.\d+)?(?:[fFuUlL])?\b|\b[A-Za-z_][A-Za-z_0-9]*\b/g;
  let output='', last=0;
  for (const match of text.matchAll(re)) {
    const value=match[0], pos=match.index;
    output += escapeHTML(text.slice(last,pos));
    let cls='';
    if (value.startsWith('//') || value.startsWith('/*') || (py && value.startsWith('#'))) cls='comment';
    else if (/^[@"'`]/.test(value)) cls='string';
    else if (/^\d/.test(value)) cls='number';
    else if (keywords.has(value)) cls='keyword';
    else if (types.has(value)) cls='type';
    else if (/^\s*\(/.test(text.slice(pos+value.length))) cls='function';
    output += cls ? `<span class="tok-${cls}">${escapeHTML(value)}</span>` : escapeHTML(value);
    last=pos+value.length;
  }
  return output+escapeHTML(text.slice(last));
}

export class LumenEditor {
  constructor(mount, callbacks={}) {
    this.mount=mount; this.callbacks=callbacks; this.models=new Map(); this.current=null;
    this.kind='base'; this.settings={fontSize:12.5,tabSize:4,minimap:true,wordWrap:false};
    this.view=null; this.disposables=[]; this.highlightFrame=0;
  }
  async init(state, settings) {
    Object.assign(this.settings,settings);
    if (state.monaco) {
      try { await this.initMonaco(); return; }
      catch(error) {
        this.view?.dispose(); this.view=null; this.kind='base';
        console.warn('Monaco unavailable; using the local base editor.',error);
      }
    }
    this.initBase();
  }
  async initMonaco() {
    await new Promise((resolve,reject)=>{
      const script=document.createElement('script');script.src='/vendor/monaco/vs/loader.js';
      script.onload=resolve;script.onerror=reject;document.head.appendChild(script);
    });
    // Language workers resolve their own modules outside the document context.
    // An absolute base also works inside their blob/module workers in WebView2.
    window.require.config({paths:{vs:new URL('/vendor/monaco/vs',location.href).href}});
    // The bundled translations are AMD modules and must execute after the loader,
    // but before editor.main reads the message table.
    if(document.documentElement.lang!=='en')await new Promise((resolve,reject)=>window.require(['vs/nls.messages.es'],resolve,reject));
    await new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>reject(new Error('Monaco startup timed out')),15000);
      window.require(['vs/editor/editor.main'],()=>{clearTimeout(timer);resolve();},error=>{clearTimeout(timer);reject(error);});
    });
    this.kind='monaco';
    this.disposables.push(installMonacoOverlays());
    for (const [id,exts] of [['nc',['.n','.nm','.ncp','.nb','.nbb']],['asm',['.asm','.S','.s']]]) {
      monaco.languages.register({id,extensions:exts});
      monaco.languages.setMonarchTokensProvider(id,{tokenizer:{root:[
        [/\/\/.*$/,'comment'],[/;.*$/,'comment'],[/\[@[^\]]*\]/,'annotation'],
        [/\b(stc|fn|use|primitive|return|if|else|for|while|const|static|binary|raw|mov|lea|push|pop|call|ret|xor|test|cmp|je|jne|add|sub)\b/,'keyword'],
        [/\b(int|str|text|bool|float|double|ptr|memRegion|void)\b/,'type'],
        [/"([^"\\]|\\.)*"/,'string'],[/\b\d+\b/,'number']
      ]}});
    }
    this.defineMonacoTheme();
    this.view=monaco.editor.create(this.mount,{
      value:'',language:'csharp',theme:'lumen-theme',fontFamily:'Consolas, "Cascadia Code", "Liberation Mono", monospace',
      fontSize:this.settings.fontSize,lineHeight:Math.round(this.settings.fontSize*1.31),
      automaticLayout:true,renderLineHighlight:'none',lineNumbersMinChars:3,glyphMargin:true,
      lineDecorationsWidth:15,scrollBeyondLastLine:false,roundedSelection:false,contextmenu:true,
      minimap:{enabled:this.settings.minimap,renderCharacters:false,maxColumn:95,scale:1},
      padding:{top:5,bottom:40},tabSize:this.settings.tabSize,insertSpaces:true,wordWrap:this.settings.wordWrap?'on':'off',
      guides:{indentation:true,highlightActiveIndentation:false,bracketPairs:false},
      bracketPairColorization:{enabled:false},folding:true,showFoldingControls:'mouseover',
      overviewRulerLanes:0,hideCursorInOverviewRuler:true,overviewRulerBorder:false,
      scrollbar:{vertical:'hidden',horizontal:'hidden',verticalScrollbarSize:0,horizontalScrollbarSize:0,useShadows:false},
      fixedOverflowWidgets:true,overflowWidgetsDomNode:document.body,stickyScroll:{enabled:false},accessibilitySupport:'auto',ariaLabel:'Lumen code editor',
      quickSuggestions:{other:true,comments:false,strings:false},suggest:{preview:true},inlineSuggest:{enabled:true},
      tabCompletion:'on',wordBasedSuggestions:'currentDocument',
    });
    this.view.onDidChangeModelContent(()=>this.changed());
    this.view.onDidChangeCursorPosition(event=>this.callbacks.cursor?.(event.position.lineNumber,event.position.column));
    this.view.addCommand(monaco.KeyMod.CtrlCmd|monaco.KeyCode.KeyS,()=>this.callbacks.save?.());
    monaco.editor.onDidChangeMarkers(()=>this.callbacks.diagnostics?.(this.diagnostics()));
    this.breakpoints=new Map();this.breakpointDecorations=[];
    this.view.onMouseDown(e=>{if(e.target.type===monaco.editor.MouseTargetType.GUTTER_GLYPH_MARGIN&&e.target.position&&this.current){const lines=this.breakpoints.get(this.current)||new Set(),line=e.target.position.lineNumber;lines.has(line)?lines.delete(line):lines.add(line);this.breakpoints.set(this.current,lines);this.paintBreakpoints();}});
    this.registerLocalIntelligence();
  }
  registerLocalIntelligence(){
    const m=monaco;
    const words={asm:'mov lea add sub mul imul div idiv xor and or not shl shr cmp test jmp je jne jz jnz call ret push pop nop section global extern db dw dd dq resb resw resd resq rax rbx rcx rdx rsi rdi rsp rbp eax ebx ecx edx',python:'def class import from return if elif else for while try except finally raise with as async await yield None True False print range len self',csharp:'public private protected class namespace using static void int string bool var return new async await override readonly Console WriteLine',c:'int char float double void const struct return if else while for sizeof include printf',cpp:'namespace class public private template typename constexpr auto std cout vector string nullptr return include',rust:'fn let mut pub impl struct enum match use mod crate self return loop while for Some None Ok Err',go:'package import func var const type struct interface return range if else for defer go chan select',java:'public private class static void int String System out println new return import package extends implements',nc:'stc fn use primitive return if else for while const static binary raw int str text bool float'};
    for(const [language,list] of Object.entries(words))this.disposables.push(m.languages.registerCompletionItemProvider(language,{provideCompletionItems:(model,pos)=>{
      if(this.settings.completion===false)return {suggestions:[]};const w=model.getWordUntilPosition(pos);return {suggestions:list.split(' ').map(label=>({label,kind:m.languages.CompletionItemKind.Keyword,insertText:label,detail:'Lenguaje · '+language,range:new m.Range(pos.lineNumber,w.startColumn,pos.lineNumber,w.endColumn)}))};
    }}));
    // Reuse each installed Monaco grammar's own complete keyword/type lists.
    for(const language of ['python','csharp','cpp','c','rust','go','java','swift','kotlin','dart','php','ruby','sql','lua']){
      const grammar=language==='c'?'cpp':language;
      window.require(['vs/basic-languages/'+grammar+'/'+grammar],module=>{
        const definition=module.language||{},entries=[...new Set([...(definition.keywords||[]),...(definition.typeKeywords||[]),...(definition.builtins||[])])];
        this.disposables.push(m.languages.registerCompletionItemProvider(language,{provideCompletionItems:(model,pos)=>{
          if(this.settings.completion===false)return {suggestions:[]};const w=model.getWordUntilPosition(pos);
          return {suggestions:entries.filter(label=>typeof label==='string').map(label=>({label,kind:m.languages.CompletionItemKind.Keyword,insertText:label,detail:'Sintaxis '+language,sortText:'z-'+label,range:new m.Range(pos.lineNumber,w.startColumn,pos.lineNumber,w.endColumn)}))};
        }}));
      },()=>{});
    }
    for(const language of [...Object.keys(words),'javascript','typescript','html','css'])this.disposables.push(m.languages.registerInlineCompletionsProvider(language,{provideInlineCompletions:(model,pos)=>{
      if(this.settings.prediction===false||model.getLineContent(pos.lineNumber).slice(pos.column-1).trim().length>0)return {items:[]};
      const prefix=model.getLineContent(pos.lineNumber).slice(0,pos.column-1);if(prefix.trim().length<4)return {items:[]};
      const sample=model.getLinesContent().slice(Math.max(0,pos.lineNumber-300),pos.lineNumber-1).reverse();
      const line=sample.find(l=>l.trimStart().startsWith(prefix.trimStart())&&l.trimStart().length>prefix.trimStart().length);
      return {items:line?[{insertText:line.trimStart().slice(prefix.trimStart().length),range:new m.Range(pos.lineNumber,pos.column,pos.lineNumber,pos.column)}]:[]};
    },freeInlineCompletions(){}}));
  }
  paintBreakpoints(){if(this.kind!=='monaco')return;this.breakpointDecorations=this.view.deltaDecorations(this.breakpointDecorations||[],[...(this.breakpoints?.get(this.current)||[])].map(line=>({range:new monaco.Range(line,1,line,1),options:{isWholeLine:true,glyphMarginClassName:'lumen-breakpoint',glyphMarginHoverMessage:{value:'Punto de interrupción · pulsa para quitarlo'}}})));}
  setDiagnostics(path,items,owner='lumen-syntax'){
    const record=this.models.get(path);if(!record)return;record.diagnosticCache??={};const key=JSON.stringify(items);if(record.diagnosticCache[owner]===key)return;record.diagnosticCache[owner]=key;
    if(record.model&&window.monaco)monaco.editor.setModelMarkers(record.model,owner,items.map(x=>({...x,endLineNumber:x.endLineNumber||x.startLineNumber,endColumn:x.endColumn||x.startColumn+1})));
    else if(path===this.current){this.externalDiagnostics=items;this.callbacks.diagnostics?.(this.diagnostics());}
  }
  highlightExecution(path,line){
    if(this.kind!=='monaco')return;
    const same=path===this.current||String(path).replaceAll('\\','/').endsWith('/'+this.current);
    this.executionDecorations=this.view.deltaDecorations(this.executionDecorations||[],same&&line?[{range:new monaco.Range(line,1,line,1),options:{isWholeLine:true,className:'lumen-execution-line',glyphMarginClassName:'lumen-execution-arrow'}}]:[]);
  }
  defineMonacoTheme() {
    if (!window.monaco) return;
    const css=getComputedStyle(document.documentElement);
    const c=name=>css.getPropertyValue('--'+name).trim();
    monaco.editor.defineTheme('lumen-theme',{
      base:document.documentElement.dataset.theme==='day'?'vs':'vs-dark',inherit:true,
      rules:[{token:'',foreground:c('text').slice(1)},{token:'keyword',foreground:c('syntax-keyword').slice(1)},
        {token:'type',foreground:c('syntax-type').slice(1)},{token:'type.identifier',foreground:c('syntax-type').slice(1)},
        {token:'number',foreground:c('syntax-number').slice(1)},{token:'string',foreground:c('syntax-string').slice(1)},
        {token:'comment',foreground:c('syntax-comment').slice(1),fontStyle:'italic'},
        {token:'annotation',foreground:c('syntax-type').slice(1)}],
      colors:{'editor.background':c('editor'),'editor.foreground':c('text'),'editorLineNumber.foreground':c('muted'),
        'editorLineNumber.activeForeground':c('secondary'),'editorCursor.foreground':c('text'),
        'editor.selectionBackground':c('selection'),'editor.inactiveSelectionBackground':c('selection'),
        'editor.lineHighlightBackground':c('line'),'editorIndentGuide.background1':c('border'),
        'editorIndentGuide.activeBackground1':c('border-strong'),'editorWidget.background':c('surface'),
        'editorWidget.border':c('border-strong'),'editorSuggestWidget.background':c('surface'),
        'editorSuggestWidget.foreground':c('text'),'editorSuggestWidget.border':c('border'),
        'editorGutter.background':c('editor'),'minimap.background':c('editor'),
        'scrollbarSlider.background':c('border-strong').slice(0,7)+'70','scrollbarSlider.hoverBackground':c('border-strong').slice(0,7)+'b0',
        'editorSuggestWidget.selectedBackground':c('selected'),'editorSuggestWidget.selectedForeground':c('text'),
        'editorSuggestWidget.highlightForeground':c('accent'),'editorSuggestWidget.focusHighlightForeground':c('accent'),
        'editorHoverWidget.background':c('surface'),'editorHoverWidget.border':c('border'),
        'editorError.foreground':c('error-color')||'#df3958','editorGhostText.foreground':c('muted'),
        'list.hoverBackground':c('hover'),'list.activeSelectionBackground':c('selected'),'focusBorder':'#00000000'},
    });
    if(this.extensionTheme){
      const theme=this.extensionTheme,{colors,dark}=themePalette(theme),rules=[];
      const aliases={storage:'keyword',constant:'number','constant.numeric':'number','entity.name.function':'function','support.function':'function','entity.name.type':'type','support.type':'type'};
      for(const entry of theme.data?.tokenColors||[])for(const scope of Array.isArray(entry.scope)?entry.scope:String(entry.scope||'').split(',')){const settings=entry.settings||{};if(/^#[0-9a-f]{6}$/i.test(settings.foreground||''))rules.push({token:aliases[scope.trim()]||scope.trim(),foreground:settings.foreground.slice(1),fontStyle:settings.fontStyle||''});}
      monaco.editor.defineTheme('lumen-extension-theme',{base:dark?'vs-dark':'vs',inherit:true,rules,colors});monaco.editor.setTheme('lumen-extension-theme');
    }else monaco.editor.setTheme('lumen-theme');
  }
  initBase() {
    this.kind='base';
    this.mount.innerHTML=`<div class="fallback-editor"><div class="code-gutter" aria-hidden="true"><div class="gutter-lines"></div></div><div class="code-scroller"><div class="code-canvas"><pre class="code-highlight" aria-hidden="true"></pre><textarea class="code-input" aria-label="Editor de código" spellcheck="false" autocapitalize="off" autocomplete="off" wrap="off"></textarea></div></div><div class="code-minimap" title="Navegar por el archivo"><canvas></canvas><div class="minimap-window"></div></div><div class="editor-find hidden"><input placeholder="Find..." aria-label="Buscar en el archivo"><small></small><button class="icon-button find-next" title="Siguiente">${icon('chevron-down')}</button><button class="icon-button find-close" title="Cerrar búsqueda">${icon('close')}</button></div></div>`;
    this.base=this.mount.firstElementChild;
    this.input=this.mount.querySelector('.code-input');
    this.pre=this.mount.querySelector('.code-highlight');this.scroller=this.mount.querySelector('.code-scroller');
    this.gutter=this.mount.querySelector('.gutter-lines');this.canvas=this.mount.querySelector('.code-canvas');
    this.minimap=this.mount.querySelector('.code-minimap canvas');this.miniWindow=this.mount.querySelector('.minimap-window');
    this.findBar=this.mount.querySelector('.editor-find');this.findInput=this.findBar.querySelector('input');
    this.input.addEventListener('input',()=>{this.changed();this.schedulePaint();this.updateCursor();});
    this.input.addEventListener('keydown',event=>this.handleKey(event));
    ['click','keyup','select'].forEach(name=>this.input.addEventListener(name,()=>this.updateCursor()));
    this.scroller.addEventListener('scroll',()=>this.syncScroll(),{passive:true});
    this.mount.querySelector('.code-minimap').addEventListener('pointerdown',event=>{
      const rect=this.minimap.getBoundingClientRect();
      this.scroller.scrollTop=(event.clientY-rect.top)/rect.height*Math.max(0,this.scroller.scrollHeight-this.scroller.clientHeight);
    });
    this.findInput.addEventListener('keydown',event=>{
      if(event.key==='Enter'){event.preventDefault();this.find(event.shiftKey?-1:1);}
      if(event.key==='Escape')this.closeFind();
    });
    this.findInput.addEventListener('input',()=>this.find(1,true));
    this.findBar.querySelector('.find-next').onclick=()=>this.find(1);
    this.findBar.querySelector('.find-close').onclick=()=>this.closeFind();
    this.resizeObserver=new ResizeObserver(()=>this.schedulePaint());this.resizeObserver.observe(this.mount);
    this.applySettings(this.settings);
  }
  open(item) {
    if (!this.models.has(item.path)) {
      const record={...item,savedValue:item.content,value:item.content,selection:[0,0],scrollTop:0,scrollLeft:0};
      if(this.kind==='monaco')record.model=monaco.editor.createModel(item.content,languageFor(item.path),monaco.Uri.parse('file:///'+item.path));
      this.models.set(item.path,record);
    }
    this.activate(item.path);
  }
  activate(path) {
    const previous=this.models.get(this.current);
    if(previous){
      previous.value=this.getValue();
      if(this.kind==='monaco')previous.viewState=this.view.saveViewState();
      else{previous.selection=[this.input.selectionStart,this.input.selectionEnd];previous.scrollTop=this.scroller.scrollTop;previous.scrollLeft=this.scroller.scrollLeft;}
    }
    this.current=path;
    const record=this.models.get(path);
    if(!record)return;
    if(this.kind==='monaco'){
      this.view.setModel(record.model);if(record.viewState)this.view.restoreViewState(record.viewState);
    }else{
      this.input.value=record.value;this.paint();this.input.setSelectionRange(...record.selection);
      this.scroller.scrollTop=record.scrollTop;this.scroller.scrollLeft=record.scrollLeft;this.syncScroll();
    }
    this.updateCursor();
    this.paintBreakpoints();
  }
  configureLanguages(items=[],associations={}) {
    contributedAssociations=new Map();
    for(const item of items||[])for(const suffix of item.extensions||[])if(typeof suffix==='string'&&suffix.startsWith('.'))contributedAssociations.set(suffix.toLowerCase(),item.id);
    for(const [suffix,id] of Object.entries(associations||{}))contributedAssociations.set(suffix.toLowerCase(),id);
    if(this.kind==='monaco'){
      const registered=new Set(monaco.languages.getLanguages().map(x=>x.id));
      for(const id of new Set([...Object.values(languages),...contributedAssociations.values()]))if(!registered.has(id)){monaco.languages.register({id});registered.add(id);}
      for(const [path,record] of this.models)if(record.model)monaco.editor.setModelLanguage(record.model,languageFor(path));
    }else this.schedulePaint();
  }
  insertText(text,replace=false) {
    if(!this.current)return;this.focus();
    if(this.kind==='monaco'){
      this.view.pushUndoStop();this.view.executeEdits('lumen.review',[{range:replace?this.view.getModel().getFullModelRange():this.view.getSelection(),text:String(text),forceMoveMarkers:true}]);this.view.pushUndoStop();
    }else this.insert(String(text),replace?0:this.input.selectionStart,replace?this.input.value.length:this.input.selectionEnd);
  }
  getValue() {
    if(!this.current)return '';
    return this.kind==='monaco'?this.view.getValue():this.input.value;
  }
  getSelection() {
    if(!this.current)return '';
    if(this.kind==='monaco')return this.view.getModel().getValueInRange(this.view.getSelection());
    return this.input.value.slice(this.input.selectionStart,this.input.selectionEnd);
  }
  setValue(value) {
    if(this.kind==='monaco')this.view.setValue(value);
    else{this.input.value=value;this.changed();this.paint();}
  }
  changed() {
    const record=this.models.get(this.current);if(!record)return;
    record.value=this.getValue();
    this.callbacks.change?.(record.path,record.value!==record.savedValue);
  }
  isDirty(path=this.current){const item=this.models.get(path);return item?item.value!==item.savedValue:false;}
  markSaved(result) {
    const record=this.models.get(result.path);if(!record)return;
    record.savedValue=result.content;record.revision=result.revision;record.newline=result.newline;record.bom=result.bom;
    this.callbacks.change?.(result.path,record.value!==record.savedValue);
  }
  close(path) {
    const item=this.models.get(path);if(!item)return;
    if(this.current===path){this.current=null;if(this.kind==='monaco')this.view.setModel(null);else{this.input.value='';this.paint();}}
    if(item.model)item.model.dispose();
    this.models.delete(path);
  }
  reset(){this.current=null;if(this.kind==='monaco')this.view.setModel(null);for(const item of this.models.values())item.model?.dispose();this.models.clear();if(this.kind==='base'){this.input.value='';this.paint();}}
  focus(){if(this.kind==='monaco')this.view.focus();else this.input.focus({preventScroll:true});}
  changedTheme(){this.defineMonacoTheme();if(this.kind==='base')this.schedulePaint();}
  applySettings(settings) {
    Object.assign(this.settings,settings);
    this.view?.updateOptions({quickSuggestions:this.settings.completion!==false,suggestOnTriggerCharacters:this.settings.completion!==false,inlineSuggest:{enabled:this.settings.prediction!==false},renderValidationDecorations:this.settings.diagnostics===false?'off':'on'});
    const size=this.settings.fontSize;
    document.documentElement.style.setProperty('--editor-font',size+'px');
    const lineHeight=Math.round(size*(this.settings.lineHeight||1.31));
    document.documentElement.style.setProperty('--editor-line',lineHeight+'px');
    if(this.settings.fontFamily)document.documentElement.style.setProperty('--font-code',this.settings.fontFamily);
    document.documentElement.style.setProperty('--editor-tab-size',this.settings.tabSize);
    if(this.kind==='monaco'&&this.view){this.view.updateOptions({fontSize:size,fontFamily:this.settings.fontFamily,lineHeight,tabSize:this.settings.tabSize,insertSpaces:this.settings.insertSpaces!==false,minimap:{enabled:this.settings.minimap},wordWrap:this.settings.wordWrap?'on':'off',lineNumbers:this.settings.lineNumbers===false?'off':'on',fontLigatures:!!this.settings.fontLigatures,bracketPairColorization:{enabled:this.settings.bracketColors!==false},renderWhitespace:this.settings.renderWhitespace||'selection',cursorBlinking:this.settings.cursorBlinking||'blink',smoothScrolling:!!this.settings.smoothScrolling});for(const record of this.models.values())record.model?.updateOptions({tabSize:this.settings.tabSize,insertSpaces:this.settings.insertSpaces!==false});}
    else if(this.base){this.base.classList.toggle('no-minimap',!this.settings.minimap);this.base.classList.toggle('no-line-numbers',this.settings.lineNumbers===false);this.schedulePaint();}
  }
  schedulePaint(){cancelAnimationFrame(this.highlightFrame);this.highlightFrame=requestAnimationFrame(()=>this.paint());}
  paint() {
    if(!this.input)return;
    const value=this.input.value;
    const lines=value.split('\n');
    this.pre.innerHTML=highlighted(value,this.current||'')+'\n';
    this.gutter.innerHTML=lines.map((_,i)=>`<span>${i+1}</span>`).join('');
    const test=document.createElement('canvas').getContext('2d');
    const css=getComputedStyle(this.input);test.font=`${css.fontSize} ${css.fontFamily}`;
    const max=Math.max(...lines.slice(0,12000).map(line=>line.replace(/\t/g,' '.repeat(this.settings.tabSize)).length),1);
    this.canvas.style.width=Math.max(this.scroller.clientWidth,Math.ceil(max*test.measureText('M').width+45))+'px';
    this.canvas.style.height=Math.max(this.scroller.clientHeight,lines.length*parseFloat(css.lineHeight)+85)+'px';
    this.paintMinimap(lines);this.syncScroll();
  }
  paintMinimap(lines) {
    const width=this.minimap.clientWidth||82,height=this.minimap.clientHeight||500,dpr=Math.min(devicePixelRatio||1,2);
    this.minimap.width=Math.round(width*dpr);this.minimap.height=Math.round(height*dpr);
    const ctx=this.minimap.getContext('2d');ctx.scale(dpr,dpr);ctx.clearRect(0,0,width,height);
    const css=getComputedStyle(document.documentElement);
    const colors=['syntax-keyword','syntax-type','syntax-number','syntax-comment','muted'].map(key=>css.getPropertyValue('--'+key).trim());
    const gap=Math.min(2.1,(height-5)/Math.max(lines.length,1));
    for(let i=0;i<Math.min(lines.length,1200);i++){
      const line=lines[i];
      for(const match of line.matchAll(/\S+/g)){
        const color=line.trim().startsWith('//')?3:keywords.has(match[0])?0:types.has(match[0])?1:/\d/.test(match[0])?2:4;
        ctx.globalAlpha=.65;ctx.fillStyle=colors[color];
        ctx.fillRect(match.index*.63,2+i*gap,Math.min(match[0].length*.55,width-match.index*.63),Math.max(.6,gap*.6));
      }
    }
  }
  syncScroll(){
    if(!this.scroller)return;
    this.gutter.style.transform=`translateY(${-this.scroller.scrollTop}px)`;
    const fraction=Math.min(1,this.scroller.clientHeight/this.scroller.scrollHeight);
    this.miniWindow.style.height=Math.max(16,fraction*this.minimap.clientHeight)+'px';
    this.miniWindow.style.top=(this.scroller.scrollTop/this.scroller.scrollHeight)*this.minimap.clientHeight+'px';
  }
  updateCursor(){
    if(this.kind==='monaco'){
      const p=this.view?.getPosition();if(p)this.callbacks.cursor?.(p.lineNumber,p.column);return;
    }
    if(!this.input)return;
    const before=this.input.value.slice(0,this.input.selectionStart),parts=before.split('\n');
    this.callbacks.cursor?.(parts.length,parts.at(-1).length+1);
  }
  insert(text,start=this.input.selectionStart,end=this.input.selectionEnd) {
    this.input.focus();this.input.setSelectionRange(start,end);
    if(!document.execCommand('insertText',false,text)){
      this.input.setRangeText(text,start,end,'end');this.changed();this.paint();
    }
    this.updateCursor();
  }
  handleKey(event) {
    const command=event.ctrlKey||event.metaKey;
    if(command&&event.key.toLowerCase()==='f'){event.preventDefault();event.stopPropagation();this.openFind();return;}
    if(event.key==='Tab'){
      event.preventDefault();
      const {selectionStart:start,selectionEnd:end,value}=this.input;
      if(start!==end&&value.slice(start,end).includes('\n')){
        const lineStart=value.lastIndexOf('\n',start-1)+1;
        const selected=value.slice(lineStart,end);
        const next=selected.split('\n').map(line=>event.shiftKey?line.replace(new RegExp('^ {1,'+this.settings.tabSize+'}'),''):' '.repeat(this.settings.tabSize)+line).join('\n');
        this.insert(next,lineStart,end);this.input.setSelectionRange(lineStart,lineStart+next.length);
      }else if(event.shiftKey){
        const lineStart=value.lastIndexOf('\n',start-1)+1;
        const len=Math.min(this.settings.tabSize,/^ */.exec(value.slice(lineStart))[0].length);
        if(len)this.insert('',lineStart,lineStart+len);
      }else this.insert(this.settings.insertSpaces===false?'\t':' '.repeat(this.settings.tabSize));
    }else if(event.key==='Enter'){
      event.preventDefault();
      const {value,selectionStart:start,selectionEnd:end}=this.input;
      const prev=value.slice(value.lastIndexOf('\n',start-1)+1,start);
      const indent=/^[\t ]*/.exec(prev)[0];
      const extra=/[{(:]\s*$/.test(prev)?' '.repeat(this.settings.tabSize):'';
      const closing=value.slice(end).startsWith('}')&&prev.trimEnd().endsWith('{');
      const text='\n'+indent+extra+(closing?'\n'+indent:'');
      this.insert(text);
      if(closing)this.input.setSelectionRange(start+1+indent.length+extra.length,start+1+indent.length+extra.length);
      const line=parseFloat(getComputedStyle(this.input).lineHeight),row=this.input.value.slice(0,this.input.selectionStart).split('\n').length;
      if(row*line>this.scroller.scrollTop+this.scroller.clientHeight-20)this.scroller.scrollTop=row*line-this.scroller.clientHeight+30;
    }
  }
  openFind(){
    if(this.kind==='monaco'){this.view.getAction('actions.find').run();return;}
    this.findBar.classList.remove('hidden');
    const selected=this.getSelection();if(selected&&!selected.includes('\n'))this.findInput.value=selected;
    this.findInput.focus();this.findInput.select();
  }
  closeFind(){this.findBar.classList.add('hidden');this.focus();}
  find(direction=1,fromStart=false){
    const q=this.findInput.value.toLowerCase();if(!q){this.findBar.querySelector('small').textContent='';return;}
    const text=this.input.value.toLowerCase();
    const start=fromStart?0:direction>0?this.input.selectionEnd:Math.max(0,this.input.selectionStart-1);
    let index=direction>0?text.indexOf(q,start):text.lastIndexOf(q,start);
    if(index<0)index=direction>0?text.indexOf(q):text.lastIndexOf(q);
    const count=text.split(q).length-1;
    this.findBar.querySelector('small').textContent=`${count} found`;
    if(index>=0){this.input.setSelectionRange(index,index+q.length);this.showOffset(index);this.updateCursor();}
  }
  showOffset(offset){const line=this.input.value.slice(0,offset).split('\n').length;this.scroller.scrollTop=Math.max(0,(line-4)*parseFloat(getComputedStyle(this.input).lineHeight));}
  showLine(number){
    if(this.kind==='monaco'){this.view.setPosition({lineNumber:number,column:1});this.view.revealLineInCenter(number);this.focus();return;}
    const offset=this.input.value.split('\n').slice(0,number-1).join('\n').length+(number>1?1:0);
    this.input.setSelectionRange(offset,offset);this.showOffset(offset);this.updateCursor();this.focus();
  }
  diagnostics(){
    if(this.kind!=='monaco'||!this.view.getModel())return (this.externalDiagnostics||[]).map(m=>({line:m.startLineNumber,message:m.message,severity:m.severity>=8?'error':'warning'}));
    return monaco.editor.getModelMarkers({resource:this.view.getModel().uri}).map(m=>({line:m.startLineNumber,message:m.message,severity:m.severity>=8?'error':'warning'}));
  }
  trimTrailingWhitespace(){this.setValue(this.getValue().split('\n').map(line=>line.replace(/[ \t]+$/,'')).join('\n'));}
}

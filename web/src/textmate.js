/** Real TextMate/Oniguruma tokenization. Declarative grammars never start JS hosts. */
export class TextMateState {
  constructor(stack,generation){this.stack=stack;this.generation=generation;}
  clone(){return this;}
  equals(other){return other instanceof TextMateState&&other.generation===this.generation&&this.stack.equals(other.stack);}
}

export function textMateTheme(colors,entries=[]){
  const settings=[{settings:{foreground:colors.text,background:colors.editor}},
    ...Object.entries({keyword:'keyword, storage',type:'entity.name.type, support.type',number:'constant.numeric',string:'string',comment:'comment',function:'entity.name.function, support.function'})
      .map(([key,scope])=>({scope,settings:{foreground:colors[key],...(key==='comment'?{fontStyle:'italic'}:{})}}))];
  for(const entry of entries){
    if(!entry||typeof entry!=='object')continue;
    const values={};for(const name of ['foreground','background'])if(/^#[\da-f]{6}(?:[\da-f]{2})?$/i.test(entry.settings?.[name]||''))values[name]=entry.settings[name].slice(0,7);
    if(typeof entry.settings?.fontStyle==='string')values.fontStyle=entry.settings.fontStyle;
    if(Object.keys(values).length)settings.push({scope:entry.scope,settings:values});
  }
  return {settings};
}

let libraries;
async function loadLibraries(){
  if(!libraries)libraries=(async()=>{
    const [tm,onig]=await new Promise((resolve,reject)=>window.require([
      new URL('../vendor/textmate/main.js',import.meta.url).href,
      new URL('../vendor/oniguruma/main.js',import.meta.url).href
    ],(...modules)=>resolve(modules),reject));
    const response=await fetch(new URL('../vendor/oniguruma/onig.wasm',import.meta.url));
    if(!response.ok)throw new Error('No se pudo cargar Oniguruma local.');
    await onig.loadWASM(await response.arrayBuffer());return {tm,onig};
  })().catch(error=>{libraries=null;throw error;});
  return libraries;
}

export class TextMateLanguages {
  constructor(monaco,onChange=()=>{},prepare=async()=>{},restore=async()=>{}){this.monaco=monaco;this.onChange=onChange;this.prepare=prepare;this.restore=restore;this.providers=[];this.sequence=0;this.generation=0;this.loaded=[];}
  setTheme(theme){this.theme=theme;if(this.registry){this.registry.setTheme(theme);this.generation++;this.registerProviders();}return this.colorMap();}
  // TextMate reserves index 0; Monaco's encodedTokensColors allocates it itself.
  colorMap(){return this.registry?this.registry.getColorMap().slice(1):undefined;}
  registerProviders(){
    for(const disposable of this.providers)disposable.dispose();this.providers=[];
    for(const {language,grammar,id} of this.loaded){
      this.providers.push(this.monaco.languages.setTokensProvider(language,{
        getInitialState:()=>new TextMateState(this.tm.INITIAL,this.generation),
        tokenizeEncoded:(line,state)=>{
          const previous=state?.generation===this.generation?state.stack:this.tm.INITIAL;
          // Very long lines keep editor navigation responsive and do not run regexes.
          if(line.length>20000)return {tokens:new Uint32Array([0,id|(1<<15)]),endState:new TextMateState(previous,this.generation)};
          const result=grammar.tokenizeLine2(line,previous,20);
          return {tokens:result.tokens,endState:new TextMateState(result.stoppedEarly?this.tm.INITIAL:result.ruleStack,this.generation)};
        }
      }));
    }
  }
  async configure(declarations=[]){
    const sequence=++this.sequence,errors=[];
    if(!declarations.length){const previous=this.loaded.map(x=>x.language);this.clear();for(const language of previous)await this.restore(language,()=>sequence===this.sequence);if(sequence===this.sequence)this.onChange();return errors;}
    const {tm,onig}=await loadLibraries();if(sequence!==this.sequence)return errors;
    const byScope=new Map(),byLanguage=new Map(),injections=new Map();
    for(const item of declarations){
      try{
        const raw=tm.parseRawGrammar(item.content,item.path);
        if(raw.scopeName!==item.scopeName)throw new Error('scopeName no coincide con la gramática.');
        byScope.set(item.scopeName,raw);
        if(item.language)byLanguage.set(item.language,item);
        for(const target of item.injectTo||[]){if(!injections.has(target))injections.set(target,[]);injections.get(target).push(item.scopeName);}
      }catch(error){errors.push({id:item.owner,error:'Gramática '+item.scopeName+': '+error.message});}
    }
    const registry=new tm.Registry({theme:this.theme,onigLib:Promise.resolve(onig),loadGrammar:async scope=>byScope.get(scope)||null,getInjections:scope=>injections.get(scope)||[]});
    const loaded=[];
    for(const [language,item] of byLanguage){
      try{
        await this.prepare(language);
        const embeddedLanguages={};for(const [scope,id] of Object.entries(item.embeddedLanguages||{}))embeddedLanguages[scope]=this.monaco.languages.getEncodedLanguageId(id);
        const tokenTypes={};for(const [scope,type] of Object.entries(item.tokenTypes||{}))if(type in {other:0,comment:1,string:2})tokenTypes[scope]={other:0,comment:1,string:2}[type];
        const id=this.monaco.languages.getEncodedLanguageId(language);
        if(!id)throw new Error('Lenguaje no registrado: '+language);
        const grammar=await registry.loadGrammarWithConfiguration(item.scopeName,id,{embeddedLanguages,tokenTypes});
        if(grammar)loaded.push({language,grammar,id});
      }catch(error){errors.push({id:item.owner,error:'Gramática '+item.scopeName+': '+error.message});}
    }
    if(sequence!==this.sequence){registry.dispose();return errors;}
    const previous=this.loaded.map(x=>x.language);this.clear();this.tm=tm;this.registry=registry;this.loaded=loaded;this.generation++;
    for(const language of previous)if(!loaded.some(x=>x.language===language))await this.restore(language,()=>sequence===this.sequence);
    if(sequence!==this.sequence)return errors;
    this.registerProviders();this.onChange();return errors;
  }
  clear(){for(const disposable of this.providers)disposable.dispose();this.providers=[];this.loaded=[];this.registry?.dispose();this.registry=null;}
  dispose(){this.sequence++;this.clear();}
}

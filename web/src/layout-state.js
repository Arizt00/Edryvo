/** Versioned, validated layout data. No DOM or project files are stored here. */
export const PANEL_IDS = Object.freeze(['project', 'assistant', 'console']);
export const SIDES = Object.freeze(['left', 'right', 'bottom']);
export const LAYOUT_KEY = 'lumen.layout.v3';
export const PRESET_NAMES = Object.freeze({studio:'Lumen', code:'Código', grouped:'Agrupado', focus:'Enfoque'});

export function defaultLayout() {
  return {version:3, collapsed:[], railCompact:false, preset:'studio', groups:{left:['project'],right:['assistant'],bottom:['console']},
    active:{left:'project',right:'assistant',bottom:'console'}, hidden:[], sizes:{}, floating:{}};
}

export function normalizeLayout(input) {
  const state=defaultLayout();
  if(!input || typeof input!=='object' || ![2,3].includes(input.version)) return state;
  state.collapsed=Array.isArray(input.collapsed)?[...new Set(input.collapsed.filter(side=>['left','right'].includes(side)))]:[];
  state.railCompact=input.railCompact===true;
  const seen=new Set();
  for(const side of SIDES) {
    const list=Array.isArray(input.groups?.[side])?input.groups[side]:[];
    state.groups[side]=list.filter(id=>PANEL_IDS.includes(id)&&!seen.has(id)&&(seen.add(id),true));
  }
  for(const id of PANEL_IDS) if(!seen.has(id)) state.groups[{project:'left',assistant:'right',console:'bottom'}[id]].push(id);
  state.hidden=Array.isArray(input.hidden)?[...new Set(input.hidden.filter(id=>PANEL_IDS.includes(id)))]:[];
  for(const id of PANEL_IDS){
    const r=input.floating?.[id];
    if(r&&['x','y','width','height'].every(k=>typeof r[k]==='number'&&Number.isFinite(r[k])))
      state.floating[id]={x:Math.max(0,Math.min(10000,r.x)),y:Math.max(0,Math.min(10000,r.y)),width:Math.max(280,Math.min(1600,r.width)),height:Math.max(200,Math.min(1200,r.height))};
  }
  for(const side of SIDES) {
    const visible=state.groups[side].filter(id=>!state.hidden.includes(id)&&!state.floating[id]);
    state.active[side]=visible.includes(input.active?.[side])?input.active[side]:(visible[0]||null);
    const n=input.sizes?.[side],range=side==='bottom'?[110,720]:[200,620];
    if(typeof n==='number'&&Number.isFinite(n)) state.sizes[side]=Math.max(range[0],Math.min(range[1],n));
  }
  state.preset=Object.hasOwn(PRESET_NAMES,input.preset)?input.preset:'custom';
  return state;
}

export function layoutPreset(name) {
  const state=defaultLayout();
  if(name==='code') state.hidden=['assistant'];
  if(name==='grouped') {state.groups={left:['project'],right:['assistant','console'],bottom:[]};state.active={left:'project',right:'assistant',bottom:null};}
  if(name==='focus') state.hidden=[...PANEL_IDS];
  state.preset=Object.hasOwn(PRESET_NAMES,name)?name:'studio';
  return normalizeLayout(state);
}

export function sideOf(state,id) { return SIDES.find(side=>state.groups[side].includes(id)); }

export function movePanel(input,id,side,index=Infinity) {
  const state=normalizeLayout(input);
  if(!PANEL_IDS.includes(id)||!SIDES.includes(side)) return state;
  delete state.floating[id];
  for(const key of SIDES) state.groups[key]=state.groups[key].filter(item=>item!==id);
  const slot=Number.isFinite(index)?Math.max(0,Math.min(state.groups[side].length,index)):state.groups[side].length;
  state.groups[side].splice(slot,0,id);
  state.collapsed=state.collapsed.filter(value=>value!==side);
  state.hidden=state.hidden.filter(item=>item!==id);state.active[side]=id;state.preset='custom';
  return normalizeLayout(state);
}

/** Collapsing a dock preserves membership, active tab and the requested width. */
export function setCollapsed(input,side,collapsed=true) {
  const state=normalizeLayout(input);
  if(!['left','right'].includes(side))return state;
  state.collapsed=state.collapsed.filter(value=>value!==side);
  if(collapsed)state.collapsed.push(side);
  state.preset='custom';
  return state;
}

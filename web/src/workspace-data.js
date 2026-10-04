/** CSV parsing is bounded and supports quoted separators, escapes and newlines. */
export function parseCSV(text,delimiter=','){
  if(text.length>2_000_000)throw Error('La tabla admite búferes de hasta 2 MB.');
  const rows=[];let row=[],cell='',quoted=false;
  const push=()=>{row.push(cell);cell='';if(row.length>200)throw Error('La tabla admite hasta 200 columnas.');};
  const line=()=>{push();if(row.some(v=>v!==''))rows.push(row);row=[];if(rows.length>10001)throw Error('La tabla admite hasta 10 000 filas de datos.');};
  text=text.replace(/^\uFEFF/,'');
  for(let i=0;i<text.length;i++){
    const c=text[i];if(quoted){if(c==='"'){if(text[i+1]==='"'){cell+='"';i++;}else quoted=false;}else cell+=c;}
    else if(c==='"'&&cell==='')quoted=true;
    else if(c===delimiter)push();
    else if(c==='\n'||c==='\r'){if(c==='\r'&&text[i+1]==='\n')i++;line();}
    else cell+=c;
  }
  if(quoted)throw Error('Hay una cadena CSV sin cerrar.');if(cell!==''||row.length)line();
  const header=rows.shift()||[];return {header,rows};
}
export function numericSummary(rows,column){
  const values=rows.map(r=>r[column]?.trim()).filter(v=>v!==''&&v!==undefined).map(Number).filter(Number.isFinite);
  if(!values.length)return null;let sum=0,min=Infinity,max=-Infinity;for(const v of values){sum+=v;min=Math.min(min,v);max=Math.max(max,v);}return {count:values.length,min,max,mean:sum/values.length};
}
export function cssColors(text){
  const colors=[...text.matchAll(/#[\da-f]{8}\b|#[\da-f]{6}\b|#[\da-f]{4}\b|#[\da-f]{3}\b/gi)].map(m=>m[0].toLowerCase());return [...new Set(colors)].slice(0,40);
}
export function opaqueHex(color){
  let c=color.slice(1);if(c.length<5)c=[...c].map(v=>v+v).join('');return '#'+c.slice(0,6);
}
export function contrast(a,b){
  const luminance=color=>{let c=color.slice(1);if(c.length<5)c=[...c].map(v=>v+v).join('');const rgb=[0,2,4].map(i=>parseInt(c.slice(i,i+2),16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);return rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722;};
  const x=luminance(a),y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);
}

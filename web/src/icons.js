/** Lumen Line. Original 24-unit vector family; local, theme-aware and font-free. */
export const ICON_NAMES=Object.freeze(["camera", "minus", "maximize", "layout", "sliders", "grip", "focus", "dock-left", "dock-right", "dock-bottom", "panel-collapse-left", "panel-collapse-right", "panel-expand-left", "panel-expand-right", "rail-compact", "search", "files", "file", "folder", "folder-open", "git", "play", "run", "stop", "extensions", "ai-circle", "settings", "plus", "more", "close", "chevron-down", "chevron-up", "chevron-right", "chevron-left", "cube", "sparkles", "refactor", "book", "bug", "send", "bulb", "plus-square", "terminal", "split", "trash", "error-circle", "warning", "bell", "sun", "moon", "leaf", "check", "shield", "info", "refresh", "code", "copy", "keyboard", "arrow-up-right", "pin", "globe", "build", "cpu", "download", "upload", "arrow-right", "palette", "cloud-off"]);
const paths = {
  "camera": '<rect x="3" y="6" width="18" height="15" rx="3"/><path d="m8 6 1.5-3h5L16 6"/><circle cx="12" cy="13.5" r="4"/>',
  "globe": "<circle cx=\"12\" cy=\"12\" r=\"8.5\"/><path d=\"M3.5 12h17M12 3.5c5 4.5 5 12.5 0 17-5-4.5-5-12.5 0-17Z\"/>",
  "build": "<path d=\"m13.5 5 3.5 3.5 3-1a6 6 0 0 1-7.5 7.5L6 21l-3-3 6-6.5A6 6 0 0 1 16.5 4Z\"/>",
  "cpu": "<rect x=\"6\" y=\"6\" width=\"12\" height=\"12\" rx=\"2.5\"/><rect x=\"9\" y=\"9\" width=\"6\" height=\"6\" rx=\"1\"/><path d=\"M9 3v3m6-3v3M9 18v3m6-3v3M3 9h3m-3 6h3m12-6h3m-3 6h3\"/>",
  "download": "<path d=\"M12 3v12m-4-4 4 4 4-4M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3\"/>",
  "upload": "<path d=\"M12 15V3m-4 4 4-4 4 4M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3\"/>",
  "arrow-right": "<path d=\"M4 12h16m-6-6 6 6-6 6\"/>",
  "palette": "<path d=\"M12 3a9 9 0 1 0 0 18h1a2 2 0 0 0 1-3.7 1.5 1.5 0 0 1 1-2.8h3a3 3 0 0 0 3-3C21 6.8 17 3 12 3Z\"/><path d=\"M7.5 8h.01M12 6.5h.01M16.5 8.5h.01M6.5 12.5h.01\" stroke-width=\"2.8\"/>",
  "cloud-off": "<path d=\"m3 3 18 18M6 8a5 5 0 0 0 0 10h10M10 4.5A6.5 6.5 0 0 1 19 10a4 4 0 0 1 2 6\"/>",

  "minus": "<path d=\"M6 12h12\"/>",
  "maximize": "<rect x=\"4.5\" y=\"4.5\" width=\"15\" height=\"15\" rx=\"2.5\"/>",
  "layout": "<rect x=\"3.5\" y=\"3.5\" width=\"17\" height=\"17\" rx=\"3\"/><path d=\"M9 4v16m0-6h11m-4-10v10\"/>",
  "sliders": "<path d=\"M4 6h4m4 0h8M4 12h10m4 0h2M4 18h3m4 0h9\"/><circle cx=\"10\" cy=\"6\" r=\"2\"/><circle cx=\"16\" cy=\"12\" r=\"2\"/><circle cx=\"9\" cy=\"18\" r=\"2\"/>",
  "grip": "<path d=\"M9 5h.01M15 5h.01M9 12h.01M15 12h.01M9 19h.01M15 19h.01\" stroke-width=\"2.7\"/>",
  "focus": "<path d=\"M8 4H5a1 1 0 0 0-1 1v3m12-4h3a1 1 0 0 1 1 1v3M4 16v3a1 1 0 0 0 1 1h3m12-4v3a1 1 0 0 1-1 1h-3\"/>",
  "dock-left": "<rect x=\"3.5\" y=\"4\" width=\"17\" height=\"16\" rx=\"3\"/><path d=\"M9 4v16\"/><path class=\"icon-tone\" d=\"M6.5 4H9v16H6.5a3 3 0 0 1-3-3V7a3 3 0 0 1 3-3Z\"/>",
  "dock-right": "<rect x=\"3.5\" y=\"4\" width=\"17\" height=\"16\" rx=\"3\"/><path d=\"M15 4v16\"/><path class=\"icon-tone\" d=\"M15 4h2.5a3 3 0 0 1 3 3v10a3 3 0 0 1-3 3H15Z\"/>",
  "dock-bottom": "<rect x=\"3.5\" y=\"4\" width=\"17\" height=\"16\" rx=\"3\"/><path d=\"M4 14h16\"/><path class=\"icon-tone\" d=\"M4 14h16v3a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3Z\"/>",
  "panel-collapse-left": "<rect x=\"3.5\" y=\"4\" width=\"17\" height=\"16\" rx=\"3\"/><path d=\"M9 4v16m7-11-3 3 3 3\"/>",
  "panel-collapse-right": "<rect x=\"3.5\" y=\"4\" width=\"17\" height=\"16\" rx=\"3\"/><path d=\"M15 4v16m-7-11 3 3-3 3\"/>",
  "panel-expand-left": "<rect x=\"3.5\" y=\"4\" width=\"17\" height=\"16\" rx=\"3\"/><path d=\"M9 4v16m4-11 3 3-3 3\"/>",
  "panel-expand-right": "<rect x=\"3.5\" y=\"4\" width=\"17\" height=\"16\" rx=\"3\"/><path d=\"M15 4v16m-4-11-3 3 3 3\"/>",
  "rail-compact": "<path d=\"M4 5h3v3H4zm0 6h3v3H4zm0 6h3v3H4z\"/><path d=\"M12 6.5h8m-8 6h8m-8 6h8\"/>",
  "search": "<circle cx=\"10.75\" cy=\"10.75\" r=\"6.75\"/><path d=\"m16 16 4.5 4.5\"/>",
  "files": "<path d=\"M9 3.5h5.5L19.5 9v10a1.5 1.5 0 0 1-1.5 1.5H9A1.5 1.5 0 0 1 7.5 19V5A1.5 1.5 0 0 1 9 3.5Z\"/><path d=\"M14 3.5V9h5.5M4.5 7v13A1.5 1.5 0 0 0 6 21.5M11 13h5m-5 3.5h3\"/>",
  "file": "<path d=\"M7 3.5h7L19 9v10a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 5 19V5a1.5 1.5 0 0 1 2-1.5ZM14 3.5V9h5M9 13h6m-6 3.5h4\"/>",
  "folder": "<path class=\"icon-tone\" d=\"M3.5 8h17v10a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2Z\"/><path d=\"M3.5 8V6a2 2 0 0 1 2-2h4l2 2.5h7a2 2 0 0 1 2 2V18a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2V8Zm0 .5h17\"/>",
  "folder-open": "<path d=\"M3.5 17V6a2 2 0 0 1 2-2h4l2 2.5h7a2 2 0 0 1 2 2V10M3.5 18l2.8-7.5H22l-3 8a2 2 0 0 1-2 1.5H5.5a2 2 0 0 1-2-2Z\"/>",
  "git": "<circle cx=\"6\" cy=\"5\" r=\"2.5\"/><circle cx=\"6\" cy=\"19\" r=\"2.5\"/><circle cx=\"18\" cy=\"6\" r=\"2.5\"/><path d=\"M6 7.5v9M18 8.5v1c0 5-12 1-12 7\"/>",
  "play": "<path d=\"M8 4.5a.8.8 0 0 0-1.2.7v13.6a.8.8 0 0 0 1.2.7l11-6.8a.8.8 0 0 0 0-1.4Z\"/>",
  "run": "<path d=\"m10 3.5 11 7-11 7Z\"/><path d=\"M5.5 9v11.5l9-5.5\"/>",
  "stop": "<rect x=\"5\" y=\"5\" width=\"14\" height=\"14\" rx=\"3\"/>",
  "extensions": "<rect x=\"3.5\" y=\"3.5\" width=\"6.5\" height=\"6.5\" rx=\"1.7\"/><rect x=\"14\" y=\"3.5\" width=\"6.5\" height=\"6.5\" rx=\"1.7\"/><rect x=\"3.5\" y=\"14\" width=\"6.5\" height=\"6.5\" rx=\"1.7\"/><path class=\"icon-tone\" d=\"M14 14h6.5v6.5H14Z\"/><rect x=\"14\" y=\"14\" width=\"6.5\" height=\"6.5\" rx=\"1.7\"/>",
  "ai-circle": "<rect x=\"4\" y=\"4\" width=\"16\" height=\"16\" rx=\"5\"/><path d=\"m12 7 1.5 3.5L17 12l-3.5 1.5L12 17l-1.5-3.5L7 12l3.5-1.5Z\"/>",
  "settings": "<path d=\"m9.7 3.5-.5 2-1.9 1.1-2-.5-2.1 3.8 1.5 1.5v2.2l-1.5 1.5 2.1 3.8 2-.5 1.9 1.1.5 2h4.4l.5-2 1.9-1.1 2 .5 2.1-3.8-1.5-1.5v-2.2l1.5-1.5-2.1-3.8-2 .5-1.9-1.1-.5-2Z\"/><circle cx=\"11.9\" cy=\"12.5\" r=\"3.1\"/>",
  "plus": "<path d=\"M12 5v14M5 12h14\"/>",
  "more": "<path d=\"M5 12h.01M12 12h.01M19 12h.01\" stroke-width=\"3\"/>",
  "close": "<path d=\"m7 7 10 10M17 7 7 17\"/>",
  "chevron-down": "<path d=\"m7 9 5 5 5-5\"/>",
  "chevron-up": "<path d=\"m7 15 5-5 5 5\"/>",
  "chevron-right": "<path d=\"m9 6 6 6-6 6\"/>",
  "chevron-left": "<path d=\"m15 6-6 6 6 6\"/>",
  "cube": "<path d=\"m12 3 8 4.5v9L12 21l-8-4.5v-9Z\"/><path d=\"m4 7.5 8 4.5 8-4.5M12 12v9m-4-15.8 8 4.5\"/>",
  "sparkles": "<path class=\"icon-tone\" d=\"m10 4 2.5 6.5L19 13l-6.5 2.5L10 22l-2.5-6.5L1 13l6.5-2.5Z\"/><path d=\"m10 4 2.5 6.5L19 13l-6.5 2.5L10 22l-2.5-6.5L1 13l6.5-2.5ZM19 2l1.1 3L23 6l-2.9 1L19 10l-1-3-3-1 3-1Z\"/>",
  "refactor": "<path d=\"M4 9a7 7 0 0 1 12-4l3 3M19 3v5h-5M20 15a7 7 0 0 1-12 4l-3-3M5 21v-5h5\"/>",
  "book": "<path d=\"M12 5c-3-2-6-2-9-1v15c3-1 6-1 9 1 3-2 6-2 9-1V4c-3-1-6-1-9 1ZM12 5v15M6 8h3m6 0h3M6 11h3m6 0h3\"/>",
  "bug": "<path d=\"M8 8V6a4 4 0 0 1 8 0v2M8 4 6 2m10 2 2-2M3 10l4 1m10 0 4-1M3 15h4m10 0h4M5 21l3-3m8 0 3 3\"/><rect x=\"7\" y=\"8\" width=\"10\" height=\"12\" rx=\"5\"/><path d=\"M12 9v10\"/>",
  "send": "<path d=\"m3.5 4 17 8-17 8 3-8Zm3 8h14\"/>",
  "bulb": "<path d=\"M8.5 16c0-2-3-3-3-7a6.5 6.5 0 0 1 13 0c0 4-3 5-3 7M8.5 17h7M9 20h6m-4.5 2h3M10 8a2.5 2.5 0 0 1 2-1\"/>",
  "plus-square": "<rect x=\"4\" y=\"4\" width=\"16\" height=\"16\" rx=\"4\"/><path d=\"M12 8v8M8 12h8\"/>",
  "terminal": "<rect x=\"3.5\" y=\"4\" width=\"17\" height=\"16\" rx=\"3\"/><path d=\"m7 9 3 3-3 3m6 0h4\"/>",
  "split": "<rect x=\"3.5\" y=\"4\" width=\"17\" height=\"16\" rx=\"3\"/><path d=\"M12 4v16\"/>",
  "trash": "<path d=\"M4 6.5h16M9 6.5V4h6v2.5M6 6.5 7 20h10l1-13.5M10 10v6.5M14 10v6.5\"/>",
  "error-circle": "<circle cx=\"12\" cy=\"12\" r=\"8.5\"/><path d=\"m9 9 6 6m0-6-6 6\"/>",
  "warning": "<path d=\"m10.7 4.2-8.2 14A1.3 1.3 0 0 0 3.6 20h16.8a1.3 1.3 0 0 0 1.1-1.8l-8.2-14a1.5 1.5 0 0 0-2.6 0ZM12 8v5.5m0 3.5h.01\"/>",
  "bell": "<path d=\"M6 10a6 6 0 0 1 12 0v5l2 3H4l2-3Zm4 11h4M12 2v2\"/>",
  "sun": "<circle cx=\"12\" cy=\"12\" r=\"4\"/><path d=\"M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5\"/>",
  "moon": "<path d=\"M20.5 13.5A8.5 8.5 0 0 1 10.5 3.4a8.5 8.5 0 1 0 10 10.1Z\"/>",
  "leaf": "<path d=\"M20.5 3.5c0 11-3 16-10 16a6 6 0 0 1-6-6c0-7 6-8 16-10ZM3.5 21l12-12m-8 8v-5m4 1h5\"/>",
  "check": "<path d=\"m5 12 4.5 4.5L19 7\"/>",
  "shield": "<path d=\"m12 3-8 3.5v5.2c0 5 4 8.2 8 10 4-1.8 8-5 8-10V6.5ZM8 12l3 3 5-6\"/>",
  "info": "<circle cx=\"12\" cy=\"12\" r=\"8.5\"/><path d=\"M12 11v6m0-10h.01\"/>",
  "refresh": "<path d=\"M20 9a8.5 8.5 0 0 0-14-4L3.5 7.5M3.5 3v4.5H8M4 15a8.5 8.5 0 0 0 14 4l2.5-2.5m0 4.5v-4.5H16\"/>",
  "code": "<path d=\"m7 7-5 5 5 5m10-10 5 5-5 5M14 4l-4 16\"/>",
  "copy": "<rect x=\"8\" y=\"8\" width=\"12\" height=\"12\" rx=\"2.5\"/><path d=\"M15 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h2\"/>",
  "keyboard": "<rect x=\"2.5\" y=\"5\" width=\"19\" height=\"14\" rx=\"3\"/><path d=\"M6 9h.01M10 9h.01M14 9h.01M18 9h.01M6 12h.01M10 12h.01M14 12h.01M18 12h.01M7 15.5h10\"/>",
  "arrow-up-right": "<path d=\"M7 17 17 7M7 7h10v10\"/>",
  "pin": "<path d=\"m9 3 6 0-1 6 4 4v2H6v-2l4-4Zm3 12v6\"/>"
};
export function icon(name, className='') {
  return `<svg class="icon ${className}" viewBox="0 0 24 24" aria-hidden="true" focusable="false" data-glyph="${escapeHTML(name)}">${paths[name] || paths.file}</svg>`;
}
export function renderIcons(root=document) {
  root.querySelectorAll('[data-icon]').forEach(node => { node.innerHTML = icon(node.dataset.icon); });
}
export function escapeHTML(value) {
  return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
let activeFileIcons=null;
export function setFileIcons(theme){activeFileIcons=theme||null;}
export function fileIcon(path) {
  if(activeFileIcons){
    const name=path.split('/').pop().toLowerCase(),parts=name.split('.');
    let id=activeFileIcons.fileNames?.[name];
    for(let i=1;!id&&i<parts.length;i++)id=activeFileIcons.fileExtensions?.[parts.slice(i).join('.')];
    const src=activeFileIcons.definitions?.[id||activeFileIcons.file];
    if(typeof src==='string'&&src.startsWith('data:image/svg+xml;base64,'))return `<span class="file-type extension-file-icon"><img src="${escapeHTML(src)}" alt=""></span>`;
  }
  const ext = path.split('.').pop().toLowerCase();
  const label = {cs:'C#',js:'JS',mjs:'JS',ts:'TS',py:'Py',cpp:'C++',cc:'C++',c:'C',h:'H',hpp:'H',rs:'Rs',s:'ASM',asm:'ASM',n:'nC',nm:'nC',ncp:'nC',nb:'nC',nbb:'nC',json:'{}',css:'#'}[ext];
  if (label) return `<span class="file-type file-type-${ext} ${ext==='py'?'python':''}">${label}</span>`;
  return `<span class="file-type">${icon(['unity','prefab'].includes(ext)?'cube':'file')}</span>`;
}

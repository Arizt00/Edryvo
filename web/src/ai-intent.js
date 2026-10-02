// Classify only a direct first-person request, excluding quoted/code content.
// The concrete target still requires per-request confirmation before editing.
export function requestsLiveEdit(question){
  const text=String(question).replace(/```[\s\S]*?(?:```|$)/g,'').replace(/^\s*>.*$/gm,'').replace(/["“][^"”]*["”]/g,'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  if(/\b(no|nunca|sin|don't|do not|never)\b/.test(text))return false;
  if(/\b(explica|explicame|analiza|analizame|opina|depura|revisa|explain|analy[sz]e|review|debug)\b/.test(text)&&!/(?:y|despues|luego|and|then)\s+(?:por favor\s+)?(?:escribe|reescribe|modifica|edita|cambia|crea|genera|write|rewrite|edit|change|create)/.test(text))return false;
  return /(?:^|[.!?]\s*|\b(?:por favor|puedes|quiero que|necesito que|please|can you|and|y)\s+)(?:escribe|escribir|reescribe|reescribir|modifica|modificar|edita|editar|cambia|cambiar|crea|crear|genera|generar|anade|anadir|implementa|implementar|write|rewrite|edit|change|create|generate|implement)\b/.test(text)&&/\b(en vivo|real[ -]?time|tiempo real|live|archivo|codigo|file|code)\b/.test(text);
}

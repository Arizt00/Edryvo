/** Lenon Glass: Babylon rendering, shared fixed palette and Three crystal geometry. */
let engineScript;
function loadBabylon() {
  if (window.BABYLON) return Promise.resolve(window.BABYLON);
  return engineScript ||= new Promise((resolve,reject)=>{
    const script=document.createElement('script');script.src='/vendor/babylon/babylon.js';
    script.onload=()=>resolve(window.BABYLON);script.onerror=()=>{engineScript=null;reject(new Error('Babylon no disponible'));};
    document.head.appendChild(script);
  });
}
export function glassArt(kind='orb', extra='') {
  return `<div class="glass-art ${kind} ${extra}" aria-hidden="true"><div class="glass-aura"></div><div class="glass-fallback"><i></i></div><canvas data-glass="${kind}" tabindex="-1"></canvas></div>`;
}
export async function createLumenScene(canvas, available=true, onStatus=()=>{}) {
  const fallback={kind:'css',setTheme(){},setMotion(){},dispose(){}};
  if(!canvas||!available)return fallback;
  let engine,scene,cleanup=()=>{};
  try {
    const B=await loadBabylon();
    if(!canvas.isConnected||!B.Engine.IsSupported)return fallback;
    engine=new B.Engine(canvas,true,{alpha:true,stencil:false,preserveDrawingBuffer:false,powerPreference:'default',disableWebGL2Support:false},false);
    canvas.dataset.engine=engine.webGLVersion>=2?'WebGL2':'WebGL';
    engine.setHardwareScalingLevel(1/Math.min(devicePixelRatio||1,1.5));
    scene=new B.Scene(engine);scene.clearColor=new B.Color4(0,0,0,0);
    const hero=canvas.dataset.glass==='hero';
    const camera=new B.FreeCamera('glass-camera',new B.Vector3(0,0,8),scene);camera.setTarget(B.Vector3.Zero());
    camera.mode=B.Camera.ORTHOGRAPHIC_CAMERA;camera.minZ=.1;
    const vertexSource=`precision highp float;attribute vec3 position;attribute vec3 normal;
      uniform mat4 worldViewProjection;uniform mat4 world;varying vec3 n;varying vec3 p;
      void main(){n=normalize(mat3(world)*normal);p=position;gl_Position=worldViewProjection*vec4(position,1.);}`;
    const fragmentSource=`precision highp float;varying vec3 n;varying vec3 p;
      uniform float time;uniform float crystal;
      #ifdef LENS
      uniform sampler2D refractionMap;uniform vec2 resolution;
      #endif
      void main(){
        vec3 N=normalize(vec3(-n.x,n.y,abs(n.z)));
        vec2 uv=N.xy;float radius=length(uv),facing=N.z;
        float t=time*.32;float angle=atan(uv.y,uv.x);
        float fresnel=pow(1.-facing,2.4);
        // A thin film changes optical thickness locally; its colours flow without spinning.
        vec2 q=uv+vec2(sin(uv.y*3.+t*.7),cos(uv.x*2.7-t*.6))*.09;
        float thickness=.45+.15*sin(q.x*2.4+q.y*1.9+t*.55)+.065*sin(q.y*4.2-q.x*2.1-t*.4);
        vec3 spectrum=.5+.5*cos(6.2831853*(thickness*(1.2+facing*.3)+vec3(.0,.32,.64)));
        vec3 pearl=vec3(.54,.34,.97),pink=vec3(1.,.22,.70),ice=vec3(.05,.83,1.);
        vec3 mint=vec3(.34,1.,.70),gold=vec3(1.,.93,.32);
        // Advected light fields converge and separate; the shell reflection stays still.
        vec2 a=vec2(-.34+.28*sin(t*.93), .38+.22*cos(t*.73));
        vec2 b=vec2(-.38+.27*cos(t*.81),-.38+.24*sin(t*.89));
        vec2 c=vec2(.35+.23*sin(t*.79+2.),.29+.27*cos(t*.91+1.));
        vec2 d=vec2(.48+.25*cos(t*.87+1.),-.38+.26*sin(t*.67+3.));
        vec2 e=vec2(.40+.32*sin(t*.61+4.),.03+.30*cos(t*.83));
        float p1=exp(-dot(q-a,q-a)*5.5);
        float p2=exp(-dot(q-b,q-b)*4.3);
        float p3=exp(-dot(q-c,q-c)*8.);
        float p4=exp(-dot(q-d,q-d)*10.);
        float p5=exp(-dot(q-e,q-e)*9.);
        vec3 volume=(pearl*.38+pink*(p1+p4)+ice*p2+gold*p3+mint*p5)/(.38+p1+p2+p3+p4+p5);
        vec3 film=mix(volume,mix(vec3(.90,.88,1.),spectrum,.52),fresnel*.65);
        // Clear central window and a denser curved meniscus, rather than a filled gradient.
        float band=exp(-pow((radius-(.73+.055*sin(angle*2.+t*.32)))*9.,2.));
        float colourWeight=.22+.43*radius+.32*band+.22*fresnel;
        colourWeight+=.13*(p3+p4);
        vec3 color=mix(vec3(.967,.977,1.),film,clamp(colourWeight,0.,.97));
        #ifdef LENS
        vec2 screen=gl_FragCoord.xy/resolution;
        vec2 displacement=uv*(.012+.020*pow(radius,2.));
        vec2 chroma=uv*.0028*fresnel;
        vec4 behind=texture2D(refractionMap,screen-displacement);
        vec3 refracted=vec3(texture2D(refractionMap,screen-displacement-chroma).r,behind.g,texture2D(refractionMap,screen-displacement+chroma).b);
        refracted=clamp(refracted/max(behind.a,.05),0.,1.);
        color=mix(color,refracted,clamp(behind.a*.60,0.,.30));
        #endif
        // Double wall: a lit outer lip, separated from the inner reflected edge.
        float rim=exp(-pow((radius-.984)*95.,2.));
        float inner=exp(-pow((radius-.937)*60.,2.));
        float rimLight=.45+.55*pow(abs(sin(angle-.40)),2.);
        float wallShadow=exp(-pow((radius-.956)*46.,2.))*(.5+.5*sin(angle+.7));
        color-=vec3(.24,.21,.09)*wallShadow;
        color=mix(color,mix(vec3(.88,.85,1.),vec3(1.),rimLight),clamp(rim*.90+inner*.25,0.,.96));
        // Reflected softboxes: long curved highlight, sharp core and warm lower glint.
        vec2 h=uv-vec2(-.50,.58);vec2 hr=vec2(h.x*.76+h.y*.65,-h.x*.65+h.y*.76);
        float mainGlow=exp(-dot(hr*vec2(5.,7.),hr*vec2(5.,7.)));
        float mainSpec=exp(-dot(hr*vec2(24.,6.),hr*vec2(24.,6.)));
        vec2 l=uv-vec2(.52,-.56);vec2 lr=vec2(l.x*.8+l.y*.6,-l.x*.6+l.y*.8);
        float lowerGlow=exp(-dot(lr*vec2(5.,7.),lr*vec2(5.,7.)));
        float lowerSpec=exp(-dot(lr*vec2(22.,7.),lr*vec2(22.,7.)));
        float upperArc=exp(-pow((length((uv-vec2(.04,-.02))*vec2(.95,1.))-.90)*55.,2.))*smoothstep(.3,.8,uv.y)*(1.-smoothstep(-.6,.6,uv.x));
        float lowerArc=exp(-pow((length((uv-vec2(-.12,.07))*vec2(.96,1.05))-.78)*65.,2.))*(1.-smoothstep(-.8,-.15,uv.y))*.32;
        // Small reflected windows and caustic arcs keep the shell optically crisp.
        float sideSpec=exp(-pow((radius-.955)*95.,2.))*exp(-pow((angle+.10)*9.,2.));
        float pinSpec=exp(-dot((uv-vec2(.36,.33))*vec2(34.,80.),(uv-vec2(.36,.33))*vec2(34.,80.)));
        color=mix(color,vec3(1.,.95,.76),lowerGlow*.64+mainGlow*.28);
        float highlight=clamp(mainGlow*.40+mainSpec+lowerSpec+upperArc*.92+lowerArc+sideSpec*.7+pinSpec*.8,0.,1.);
        color=mix(color,vec3(1.),highlight);
        // The 48.5% base remains; reflection increases opacity only at the glass wall.
        float alpha=.485+fresnel*.22+rim*.16+inner*.06;
        alpha=mix(alpha,.36+fresnel*.22,crystal);
        alpha=max(alpha,highlight*.96);alpha=clamp(alpha,0.,.96);
        gl_FragColor=vec4(color,alpha);
      }`;
    const material=(name,crystal=0)=>{
      const m=new B.ShaderMaterial(name,scene,{vertexSource,fragmentSource},{attributes:['position','normal'],uniforms:['worldViewProjection','world','time','crystal','resolution'],samplers:crystal===0?['refractionMap']:[],defines:crystal===0?['#define LENS']:[],needAlphaBlending:true});
      m.setFloat('crystal',crystal);m.backFaceCulling=true;return m;
    };
    const pearl=B.MeshBuilder.CreateSphere('melody',{diameter:2.75,segments:96},scene);const pearlMaterial=material('iridescence');pearl.material=pearlMaterial;
    const materials=[pearlMaterial],crystals=[];let ribbon;pearl.position.set(0,0,0);
    if(hero){
      const three=await import('/vendor/three/three.core.js');
      const positions=[[-1.95,.55,.38],[2.05,-.65,.37],[-1.4,-1.25,.15],[1.85,1.2,.13],[-1.1,1.55,.12]];
      positions.forEach(([x,y,size],i)=>{
        const geometry=new three.IcosahedronGeometry(size,0);const mesh=new B.Mesh('crystal-'+i,scene),data=new B.VertexData();
        data.positions=Array.from(geometry.attributes.position.array);data.normals=Array.from(geometry.attributes.normal.array);
        data.indices=Array.from({length:data.positions.length/3},(_,j)=>j%3===0?j:j%3===1?j+1:j-1);data.applyToMesh(mesh);geometry.dispose();
        mesh.position.set(x,y,.15);mesh.scaling.y=2.2;mesh.rotation.z=i*.75;mesh.material=material('crystal-glass-'+i,1);
        mesh.enableEdgesRendering(.98);mesh.edgesWidth=1.25;mesh.edgesColor=new B.Color4(1,1,1,.72);
        crystals.push({mesh,y,phase:i});materials.push(mesh.material);
      });
      const curve=new three.CatmullRomCurve3([new three.Vector3(-2.5,2.3,-.8),new three.Vector3(-1.7,.85,.8),new three.Vector3(1.5,-.3,1.5),new three.Vector3(.6,-1.65,.4),new three.Vector3(-1.2,-2.7,-.9)]);
      const ribbonPath=curve.getPoints(130).map(v=>new B.Vector3(v.x,v.y,v.z));
      ribbon=B.MeshBuilder.CreateTube('liquid-ribbon',{path:ribbonPath,radius:.018,tessellation:12},scene);
      const orbitalGlass=new B.StandardMaterial('orbital-glass',scene);orbitalGlass.disableLighting=true;orbitalGlass.emissiveColor=new B.Color3(1.,1.,1.);orbitalGlass.alpha=.10;ribbon.material=orbitalGlass;
      const ring=B.MeshBuilder.CreateTorus('orbit',{diameter:3.95,thickness:.014,tessellation:130},scene);ring.rotation.set(1.07,.32,-.36);ring.material=orbitalGlass;
    }
    // An actual offscreen view of the scene behind the lens, never a screen capture.
    const backdrop=B.MeshBuilder.CreatePlane('light-field',{width:18,height:10},scene);backdrop.position.z=-2.8;
    backdrop.material=new B.ShaderMaterial('light-field-material',scene,{vertexSource:`precision highp float;attribute vec3 position;attribute vec2 uv;uniform mat4 worldViewProjection;varying vec2 v;void main(){v=uv;gl_Position=worldViewProjection*vec4(position,1.);}`,fragmentSource:`precision highp float;varying vec2 v;void main(){float a=exp(-pow((v.y-.52-sin(v.x*8.)*.13)*45.,2.));float b=exp(-pow((v.y-.40+sin(v.x*7.)*.08)*60.,2.));gl_FragColor=vec4(mix(vec3(.88,.83,1.),vec3(.75,.92,1.),v.x),.055+a*.20+b*.13);}`},{attributes:['position','uv'],uniforms:['worldViewProjection'],needAlphaBlending:true});
    const refraction=new B.RenderTargetTexture('lens-background',{width:Math.max(1,engine.getRenderWidth()),height:Math.max(1,engine.getRenderHeight())},scene,false);
    refraction.clearColor=new B.Color4(0,0,0,0);refraction.activeCamera=camera;refraction.renderList=scene.meshes.filter(m=>m!==pearl&&!['liquid-ribbon','orbit'].includes(m.name));refraction.ignoreCameraViewport=true;
    if(!hero)refraction.refreshRate=0;scene.customRenderTargets.push(refraction);pearlMaterial.setTexture('refractionMap',refraction);
    let enabled=document.documentElement.dataset.motion!=='off',visible=false,disposed=false,ready=false,elapsed=0,last=performance.now();
    const reduced=matchMedia('(prefers-reduced-motion: reduce)');
    function render(){
      if(disposed||!ready||document.hidden||!visible)return;
      if(!canvas.isConnected||canvas.closest('[hidden],[inert]')||getComputedStyle(canvas).visibility==='hidden'){engine.stopRenderLoop(render);return;}
      const now=performance.now();if(enabled&&!reduced.matches)elapsed+=Math.min(now-last,45)/1000;last=now;
      materials.forEach(m=>m.setFloat('time',elapsed));
      pearl.position.y=Math.sin(elapsed*.36)*.035;pearl.scaling.setAll(.99+Math.sin(elapsed*.23)*.01);
      for(const {mesh,y,phase} of crystals){mesh.position.y=y+Math.sin(elapsed*.22+phase)*.12;mesh.rotation.y=elapsed*.055+phase;}
      if(ribbon)ribbon.rotation.z=Math.sin(elapsed*.12)*.07;
      scene.render();
    }
    function schedule(){engine.stopRenderLoop(render);last=performance.now();if(ready&&visible&&!document.hidden){render();if(enabled&&!reduced.matches)engine.runRenderLoop(render);}}
    function resize(){const rect=canvas.getBoundingClientRect();if(rect.width<1||rect.height<1)return;engine.resize();const width=engine.getRenderWidth(),height=engine.getRenderHeight();pearlMaterial.setVector2('resolution',new B.Vector2(width,height));const textureSize=refraction.getSize();if(textureSize.width!==width||textureSize.height!==height)refraction.resize({width,height});const half=hero?2.08:1.70;camera.orthoTop=half;camera.orthoBottom=-half;camera.orthoLeft=-half*rect.width/rect.height;camera.orthoRight=half*rect.width/rect.height;render();}
    const appearance=new MutationObserver(records=>{if(records.some(record=>record.target.contains(canvas)))schedule();});appearance.observe(document.documentElement,{attributes:true,attributeFilter:['data-screen','data-motion']});appearance.observe(document.body,{subtree:true,attributes:true,attributeFilter:['hidden','inert']});
    const observer=new ResizeObserver(resize);observer.observe(canvas);
    const intersection=new IntersectionObserver(entries=>{visible=!!entries[0]?.isIntersecting;schedule();});intersection.observe(canvas);
    document.addEventListener('visibilitychange',schedule);reduced.addEventListener('change',schedule);
    const lost=()=>{canvas.parentElement.classList.remove('gpu-ready');};canvas.addEventListener('webglcontextlost',lost);
    const restored=engine.onContextRestoredObservable.add(()=>{canvas.parentElement.classList.add('gpu-ready');resize();schedule();});
    cleanup=()=>{disposed=true;appearance.disconnect();observer.disconnect();intersection.disconnect();document.removeEventListener('visibilitychange',schedule);reduced.removeEventListener('change',schedule);canvas.removeEventListener('webglcontextlost',lost);engine.onContextRestoredObservable.remove(restored);engine.stopRenderLoop(render);};
    let readyTimer;try{await Promise.race([scene.whenReadyAsync(),new Promise((_,reject)=>{readyTimer=setTimeout(()=>reject(new Error('El motor gráfico no respondió a tiempo')),12000);})]);}finally{clearTimeout(readyTimer);}if(!canvas.isConnected){cleanup();scene.dispose();engine.dispose();return fallback;}ready=true;resize();visible=canvas.getClientRects().length>0;render();
    canvas.parentElement.classList.add('gpu-ready');schedule();onStatus('Babylon.js + Three.js · Lenon Glass');
    return {kind:'babylon',renderer:canvas.dataset.engine,setTheme(){render();},setMotion(value){enabled=value;schedule();},dispose(){const gl=engine._gl;cleanup();scene.dispose();engine.dispose();gl?.getExtension('WEBGL_lose_context')?.loseContext();}};
  }catch(error){cleanup();scene?.dispose();engine?.dispose();canvas.dataset.graphicsError=error.message;onStatus('Cristal CSS · '+error.message);return fallback;}
}


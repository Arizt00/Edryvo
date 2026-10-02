/** A small, power-conscious Babylon.js pearl. All UI text stays in the DOM. */
export async function createLumenScene(canvas, available, onStatus=()=>{}) {
  const fallback={kind:'css',setTheme(){},setMotion(){},dispose(){}};
  if(!available){onStatus('CSS fallback · Babylon not installed');return fallback;}
  try {
    await new Promise((resolve,reject)=>{
      const script=document.createElement('script');script.src='/vendor/babylon/babylon.js';script.onload=resolve;script.onerror=reject;document.head.appendChild(script);
    });
    const B=window.BABYLON;
    if(!B || !B.Engine.IsSupported())throw new Error('WebGL is unavailable');
    const engine=new B.Engine(canvas,true,{alpha:true,stencil:false,preserveDrawingBuffer:false,powerPreference:'low-power'},false);
    engine.setHardwareScalingLevel(1/Math.min(devicePixelRatio||1,2));
    const scene=new B.Scene(engine);scene.clearColor=new B.Color4(0,0,0,0);
    const camera=new B.FreeCamera('pearl-camera',new B.Vector3(0,0,4),scene);
    camera.setTarget(B.Vector3.Zero());camera.mode=B.Camera.ORTHOGRAPHIC_CAMERA;
    camera.orthoLeft=-1.22;camera.orthoRight=1.22;camera.orthoTop=1.44;camera.orthoBottom=-1.44;
    const pearl=B.MeshBuilder.CreateSphere('lumen-pearl',{diameter:2,segments:40},scene);pearl.scaling.y=1.05;
    const vertexSource=`precision highp float;
      attribute vec3 position; attribute vec3 normal;
      uniform mat4 worldViewProjection; uniform mat4 world;
      varying vec3 vNormal; varying vec3 vPosition;
      void main(){vNormal=normalize(mat3(world)*normal);vPosition=position;
        gl_Position=worldViewProjection*vec4(position,1.0);}`;
    const fragmentSource=`precision highp float;
      varying vec3 vNormal; varying vec3 vPosition;
      uniform float time; uniform float forest; uniform float night;
      void main(){
        vec3 n=normalize(vNormal); vec3 view=vec3(0.,0.,1.);
        float rim=pow(1.0-max(0.0,dot(n,view)),2.6);
        vec3 purple=vec3(.48,.44,.85); vec3 lilac=vec3(.79,.70,.92); vec3 ice=vec3(.67,.92,.99);
        float band=smoothstep(-.9,.8,n.y*.6+n.x*.5+sin(n.z*3.0+time*.14)*.20);
        vec3 base=mix(lilac,purple,band);
        base=mix(base,ice,smoothstep(.25,.92,dot(n,normalize(vec3(.7,.9,.9)))));
        vec3 green=mix(vec3(.07,.25,.17),vec3(.51,.78,.60),band);
        green=mix(green,vec3(.82,.94,.69),pow(max(0.,dot(n,normalize(vec3(.55,.8,1.)))),14.));
        base=mix(base,green,forest);
        float spec=pow(max(0.,dot(n,normalize(vec3(.60,.73,1.)))),24.);
        base=base*(.72+.28*max(0.,n.z));
        base+=vec3(spec*.25)+rim*vec3(.11,.07,.12);
        base*=1.0-night*.13;
        gl_FragColor=vec4(base,1.0);
      }`;
    const material=new B.ShaderMaterial('lumen-porcelain',scene,{vertexSource,fragmentSource},{attributes:['position','normal'],uniforms:['worldViewProjection','world','time','forest','night']});
    pearl.material=material;
    let interval=null,enabled=true,destroyed=false,intersecting=true;
    const media=matchMedia('(prefers-reduced-motion: reduce)');
    const frame=()=>{
      if(destroyed||document.hidden||!intersecting||!canvas.getClientRects().length)return;
      material.setFloat('time',performance.now()/1000);
      pearl.rotation.y=enabled&&!media.matches?Math.sin(performance.now()/14000)*.15:0;
      scene.render();
    };
    const schedule=()=>{
      if(interval)clearInterval(interval);
      interval=null;
      if(!document.hidden&&intersecting&&canvas.getClientRects().length){frame();if(enabled&&!media.matches)interval=setInterval(frame,50);}
    };
    const setTheme=theme=>{
      material.setFloat('forest',theme==='forest'?1:0);material.setFloat('night',theme==='dark'?1:0);frame();
    };
    const setMotion=motion=>{enabled=motion;schedule();};
    const resize=new ResizeObserver(()=>{if(canvas.getClientRects().length)engine.resize();schedule();});resize.observe(canvas);
    const intersection=new IntersectionObserver(entries=>{intersecting=entries[0]?.isIntersecting??false;schedule();});intersection.observe(canvas);
    document.addEventListener('visibilitychange',schedule);media.addEventListener('change',schedule);
    setTheme(document.documentElement.dataset.theme);schedule();
    canvas.parentElement.classList.add('gpu-ready');onStatus('Babylon.js · WebGL');
    return {kind:'babylon',setTheme,setMotion,dispose(){destroyed=true;clearInterval(interval);resize.disconnect();intersection.disconnect();document.removeEventListener('visibilitychange',schedule);media.removeEventListener('change',schedule);scene.dispose();engine.dispose();}};
  }catch(error){
    onStatus('CSS fallback · '+error.message);
    return fallback;
  }
}

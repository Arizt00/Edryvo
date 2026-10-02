// Uses the JDK's real debugger interface; no source execution is simulated.
import com.sun.jdi.*;
import com.sun.jdi.connect.*;
import com.sun.jdi.event.*;
import com.sun.jdi.request.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

class LumenJavaDebugger {
    static VirtualMachine vm;
    static volatile ThreadReference active;
    static String source;
    static String main;
    static Set<Integer> points = new HashSet<>();
    static Set<Location> installed = new HashSet<>();
    static String q(String s) {
        if(s==null) return "\"\"";
        StringBuilder out=new StringBuilder("\"");
        for(char c:s.toCharArray()) {
            if(c=='"'||c=='\\') out.append('\\').append(c);
            else if(c<32) out.append(String.format("\\u%04x",(int)c));
            else out.append(c);
        }
        return out.append('"').toString();
    }
    static synchronized void emit(String json) {System.out.println(json);System.out.flush();}
    static Thread drain(InputStream stream) {
        Thread t=new Thread(()->{try(var reader=new InputStreamReader(stream,StandardCharsets.UTF_8)) {
            char[] b=new char[1024];int n;
            while((n=reader.read(b))!=-1)emit("{\"event\":\"output\",\"text\":"+q(new String(b,0,n))+"}");
        }catch(IOException ignored){}});t.setDaemon(true);t.start();return t;
    }
    static void breakpoint(Location location,boolean once) {
        if(!installed.add(location)) return;
        BreakpointRequest b=vm.eventRequestManager().createBreakpointRequest(location);
        if(once)b.addCountFilter(1);
        b.setSuspendPolicy(EventRequest.SUSPEND_ALL);b.enable();
    }
    static void prepare(ReferenceType type) throws Exception {
        for(int line:points)for(Location location:type.locationsOfLine(line))breakpoint(location,false);
        if(type.name().equals(main))for(Method method:type.methodsByName("main")) {
            List<Location> locations=method.allLineLocations();
            if(!locations.isEmpty())breakpoint(locations.get(0),!points.contains(locations.get(0).lineNumber()));
        }
    }
    static void paused(ThreadReference thread) throws Exception {
        active=thread;
        List<StackFrame> frames=thread.frames(0,Math.min(thread.frameCount(),25));
        StringJoiner stack=new StringJoiner(","),vars=new StringJoiner(",");
        for(StackFrame frame:frames) {
            Location l=frame.location();String path;
            try{path=l.sourcePath();}catch(AbsentInformationException e){path=source;}
            stack.add("{\"name\":"+q(l.declaringType().name()+"."+l.method().name())+",\"path\":"+q(path)+",\"line\":"+l.lineNumber()+"}");
        }
        if(!frames.isEmpty())try {
            StackFrame top=frames.get(0);
            for(LocalVariable v:top.visibleVariables().stream().limit(100).toList()) {
                Value value=top.getValue(v);String text=String.valueOf(value);
                vars.add("{\"name\":"+q(v.name())+",\"type\":"+q(v.typeName())+",\"value\":"+q(text.substring(0,Math.min(text.length(),400)))+"}");
            }
        }catch(AbsentInformationException ignored){}
        emit("{\"status\":\"paused\",\"path\":"+q(source)+",\"line\":"+(frames.isEmpty()?0:frames.get(0).location().lineNumber())+",\"stack\":["+stack+"],\"variables\":["+vars+"]}");
    }
    static void commands() {
        try(var input=new BufferedReader(new InputStreamReader(System.in,StandardCharsets.UTF_8))) {
            String command;
            while((command=input.readLine())!=null) {
                if(command.equals("stop")){vm.exit(0);return;}
                if(active==null)continue;
                for(StepRequest request:new ArrayList<>(vm.eventRequestManager().stepRequests()))vm.eventRequestManager().deleteEventRequest(request);
                if(!command.equals("continue")) {
                    int depth=command.equals("next")?StepRequest.STEP_OVER:command.equals("out")?StepRequest.STEP_OUT:StepRequest.STEP_INTO;
                    StepRequest request=vm.eventRequestManager().createStepRequest(active,StepRequest.STEP_LINE,depth);
                    for(String pattern:List.of("java.*","javax.*","sun.*","jdk.*"))request.addClassExclusionFilter(pattern);
                    request.addCountFilter(1);request.setSuspendPolicy(EventRequest.SUSPEND_ALL);request.enable();
                }
                active=null;emit("{\"status\":\"running\"}");vm.resume();
            }
            vm.exit(0);
        }catch(VMDisconnectedException ignored){}catch(Exception e){emit("{\"status\":\"error\",\"error\":"+q(e.toString())+"}");}
    }
    public static void main(String[] args) {
        try {
            source=args[2];main=args[1];for(String point:args[3].split(","))if(!point.isEmpty())points.add(Integer.parseInt(point));
            LaunchingConnector connector=Bootstrap.virtualMachineManager().defaultConnector();
            Map<String,Connector.Argument> options=connector.defaultArguments();
            options.get("main").setValue(main);options.get("options").setValue("-Dfile.encoding=UTF-8 -cp \""+args[0]+"\"");options.get("suspend").setValue("true");
            vm=connector.launch(options);
            Runtime.getRuntime().addShutdownHook(new Thread(()->{try{vm.process().destroyForcibly();}catch(Exception ignored){}}));
            Thread stdout=drain(vm.process().getInputStream()),stderr=drain(vm.process().getErrorStream());
            ClassPrepareRequest request=vm.eventRequestManager().createClassPrepareRequest();request.addClassFilter(main+"*");request.setSuspendPolicy(EventRequest.SUSPEND_ALL);request.enable();
            Thread input=new Thread(LumenJavaDebugger::commands);input.setDaemon(true);input.start();
            boolean finished=false;
            while(!finished) {
                EventSet events=vm.eventQueue().remove();boolean hold=false;
                for(Event event:events) {
                    if(event instanceof ClassPrepareEvent prepared)prepare(prepared.referenceType());
                    else if(event instanceof BreakpointEvent hit){paused(hit.thread());hold=true;}
                    else if(event instanceof StepEvent step){vm.eventRequestManager().deleteEventRequest(step.request());paused(step.thread());hold=true;}
                    else if(event instanceof VMDeathEvent||event instanceof VMDisconnectEvent)finished=true;
                }
                if(!hold&&!finished)events.resume();
            }
            stdout.join(1500);stderr.join(1500);emit("{\"status\":\"finished\",\"variables\":[],\"stack\":[]}");
        }catch(VMDisconnectedException e){emit("{\"status\":\"finished\"}");}
        catch(Exception e){emit("{\"status\":\"error\",\"error\":"+q(e.toString())+"}");if(vm!=null)vm.process().destroyForcibly();}
    }
}

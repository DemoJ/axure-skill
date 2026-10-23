using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Collections.Generic;
using System.Runtime.Serialization;
using System.Web.Script.Serialization;

// Isolated RP 9.0.0.3744 HTML generator. Never attaches to the editor.
// Caller supplies a private copy of the RP and a disposable runtime directory.
internal static class NativeExport {
    const BindingFlags F = BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Static|BindingFlags.Instance;
    static Assembly ax;
    static object Call(object obj, string name, params object[] args) {
        return obj.GetType().GetMethod(name,F).Invoke(obj,args);
    }
    static object Make(string name, params object[] args) { return Activator.CreateInstance(ax.GetType(name,true),BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance,null,args,null); }
    static object Static(string type,string name,params object[] args) {return ax.GetType(type,true).GetMethod(name,F).Invoke(null,args);}

    [STAThread] static int Main(string[] args) {
        Console.OutputEncoding=new System.Text.UTF8Encoding(false);
        object file=null;
        try {
            string install=Path.GetFullPath(args[0]), input=Path.GetFullPath(args[1]), output=Path.GetFullPath(args[2]), runtime=Path.GetFullPath(args[3]);
            Directory.CreateDirectory(runtime);
            AppDomain.CurrentDomain.AssemblyResolve+=(s,e)=>{
                string p=Path.Combine(install,new AssemblyName(e.Name).Name+".dll");
                return File.Exists(p)?Assembly.LoadFrom(p):null;
            };
            ax=Assembly.LoadFrom(Path.Combine(install,"AxureRP9.exe"));
            if(ax.GetName().Version.ToString()!="9.0.0.3744")throw new Exception("Unsupported Axure version.");
            ax.GetType("Kecz.uecI").GetField("MePz",F).SetValue(null,true);

            // Initialize rendering and filesystem services without the application
            // constructor (which accesses user registry/preferences and creates UI).
            object paths=Make("ntwV.qtwA");
            var pathsBase=ax.GetType("yyYj.oyYx");
            pathsBase.GetField("nyYg",F).SetValue(paths,install);
            pathsBase.GetMethod("cyYs",F).Invoke(paths,new object[]{runtime});
            Static("NhHM.nhHV","ahyo",paths);
            ax.GetType("NhHM.nhHV").GetProperty("Information",F).SetValue(null,Make("xtfy.ztfH"),null);
            Type[] types;
            try{types=ax.GetTypes();}catch(ReflectionTypeLoadException e){types=e.Types.Where(t=>t!=null).ToArray();}
            Type coreType=ax.GetType("rtUS.jtUo");
            object core=FormatterServices.GetUninitializedObject(coreType);
            coreType.GetField("VtUk",F).SetValue(core,paths);
            var implementations=new Dictionary<string,string>{{"wtUg","rtfv"},{"LtUT","WtUy"},{"stUr","Mt6v"},{"BtUB","Ct2S"},{"GtUQ","Rhdt"}};
            foreach(var p in implementations)coreType.GetField(p.Key,F).SetValue(core,Activator.CreateInstance(types.Single(t=>t.Name==p.Value)));
            var handles=coreType.GetField("DtUA",F);handles.SetValue(core,Activator.CreateInstance(handles.FieldType));
            Static("NhHM.nhHV","Whyh",core);
            Static("qbLg.RbLk","AbLB",Make("yWrx.NWrv"));
            Static("nt8K.Nt8d","it8S",Make("it8Z.ft8P"));
            object settings=Make("at2p.pt28",core);
            coreType.GetField("qtUG",F).SetValue(core,settings);
            Static("NhHM.nhHV","Phym",settings);
            pathsBase.GetMethod("AyYL",F).Invoke(paths,new object[]{runtime});
            ax.GetType("Jaia.Saib").GetField("xaCb",F).SetValue(null,Path.Combine(runtime,"font-info.log"));

            file=Make("uWnT.UWng");
            object mode=Enum.Parse(ax.GetType("Axure.IO.AccessMode"),"ReadWrite");
            object[] loadArgs={input,null,false,mode,false};
            var loader=file.GetType().GetMethod("Load",F,null,new[]{typeof(string),typeof(string).MakeByRefType(),typeof(bool),mode.GetType(),typeof(bool)},null);
            if(!(bool)loader.Invoke(file,loadArgs))throw new Exception("Native document load failed: "+loadArgs[1]);
            object document=file.GetType().GetMethod("Load",F,null,new[]{typeof(bool)},null).Invoke(file,new object[]{false});
            object config=Make("tHJS.VHJo",document);
            Call(config,"uHJx",output);Call(config,"THJs",true);
            object generator=Make("beBp.meB8",config);

            // Generate() unconditionally opens a browser at the end. Its final
            // event runs AFTER files finish and BEFORE that UI branch. Cancel
            // only this final step; never call Generate without this handler.
            bool noBrowserStage=false;
            EventHandler preventBrowser=(sender,e)=>{noBrowserStage=true;Call(generator,"veQc",true);};
            Call(generator,"JeQF",preventBrowser);
            object result=Call(generator,"Generate",file,null,null,null);
            var errors=result.GetType().GetField("QeB2",F).GetValue(result) as Exception;
            if(errors!=null)throw errors;
            if(!noBrowserStage)throw new Exception("Export did not reach the guarded completion stage.");
            if(!File.Exists(Path.Combine(output,"start.html")))throw new Exception("Export entrypoint is missing.");
            Console.WriteLine(new JavaScriptSerializer().Serialize(new{ok=true,engine="Axure RP9 native HTML generator",browser_opened=false,output=output}));
            return 0;
        } catch(Exception e) {Console.Error.WriteLine(e);return 1;}
        finally {if(file!=null)try{Call(file,"Close",false);}catch{} }
    }
}

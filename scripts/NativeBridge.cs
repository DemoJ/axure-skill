using System;
using System.IO;
using System.IO.Compression;
using System.Text;
using System.Reflection;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.Serialization;
using System.Web.Script.Serialization;

// Local, isolated RP9 serializer adapter. Does not start or attach to Axure UI.
internal static class NativeBridge
{
    const BindingFlags All = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static | BindingFlags.Instance;
    static string install;
    static Assembly ax;
    static Type contextType;
    static MethodInfo load, save;
    static JavaScriptSerializer json = new JavaScriptSerializer { MaxJsonLength = 100000000, RecursionLimit = 200 };
    static FieldInfo Field(Type t, string name) { while(t != null) { var f=t.GetField(name, All | BindingFlags.DeclaredOnly); if(f!=null)return f; t=t.BaseType; } throw new Exception("Missing field: "+name); }
    static Dictionary<string,object> D(object o) { return (Dictionary<string,object>)o; }
    static object[] A(object o) { return ((IEnumerable)o).Cast<object>().ToArray(); }
    static IEnumerable<FieldInfo> Fields(Type t) { while(t!=null && t!=typeof(object)) { foreach(var f in t.GetFields(BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance|BindingFlags.DeclaredOnly))yield return f; t=t.BaseType; } }
    static void Init(string dir)
    {
        install=Path.GetFullPath(dir);
        AppDomain.CurrentDomain.AssemblyResolve += (s,e) => {
            string p=Path.Combine(install,new AssemblyName(e.Name).Name+".dll");
            if(File.Exists(p))return Assembly.LoadFrom(p);
            p=Path.Combine(install,new AssemblyName(e.Name).Name+".exe");
            return File.Exists(p)?Assembly.LoadFrom(p):null;
        };
        ax=Assembly.LoadFrom(Path.Combine(install,"AxureRP9.exe"));
        if(ax.GetName().Version.ToString()!="9.0.0.3744")throw new Exception("This adapter is verified only with Axure RP 9.0.0.3744.");
        var serializer=ax.GetType("wb8m.kb8O",true);
        load=serializer.GetMethod("Load",All);
        save=serializer.GetMethod("Save",All,null,new[]{typeof(object),typeof(object)},null);
        // Select memory streams inside THIS helper process; installed program is untouched.
        ax.GetType("Kecz.uecI",true).GetField("MePz",All).SetValue(null,true);
        contextType=ax.GetType("PbkS.Ubko",true);
    }
    static object Load(byte[] b) { return load.Invoke(null,new object[]{new MemoryStream(b,false),96.0,false}); }
    static byte[] Save(object c) { using(var m=new MemoryStream()){ save.Invoke(null,new[]{c,(object)m}); return m.ToArray(); } }
    static byte[] Lz(byte[] b, bool encode)
    {
        var asm=Assembly.LoadFrom(Path.Combine(install,"K4os.Compression.LZ4.Legacy.dll"));
        var t=asm.GetType("K4os.Compression.LZ4.Legacy.LZ4Legacy",true);
        using(var input=new MemoryStream(b)) using(var output=new MemoryStream()) {
            if(encode) { var stream=(Stream)t.GetMethod("Encode").Invoke(null,new object[]{output,false,1048576,true}); stream.Write(b,0,b.Length); stream.Dispose(); return output.ToArray(); }
            using(var stream=(Stream)t.GetMethod("Decode").Invoke(null,new object[]{input,false})){stream.CopyTo(output);return output.ToArray();}
        }
    }
    static byte[] Gzip(byte[] b,bool encode) { using(var m=new MemoryStream()) { if(encode){using(var z=new GZipStream(m,CompressionMode.Compress,true))z.Write(b,0,b.Length);return m.ToArray();} using(var z=new GZipStream(new MemoryStream(b),CompressionMode.Decompress))z.CopyTo(m);return m.ToArray();} }
    static object Encode(object o, int depth=0)
    {
        if(o==null)return null;
        if(depth>70)throw new Exception("Object nesting limit.");
        Type t=o.GetType();
        if(t==contextType)return new Dictionary<string,object>{{"$context",true}};
        string tn=t.FullName;
        if(o is double)return new Dictionary<string,object>{{"t",tn},{"v",((double)o).ToString("R",System.Globalization.CultureInfo.InvariantCulture)}};
        if(o is float)return new Dictionary<string,object>{{"t",tn},{"v",((float)o).ToString("R",System.Globalization.CultureInfo.InvariantCulture)}};
        if(t.IsPrimitive || t.IsEnum || o is string || o is Guid || o is decimal || o is DateTime)
            return new Dictionary<string,object>{{"t",tn},{"v",o is Guid || o is DateTime || t.IsEnum ? o.ToString() : o}};
        if(o is MemoryStream)return new Dictionary<string,object>{{"t",tn},{"s",Convert.ToBase64String(((MemoryStream)o).ToArray())},{"p",((MemoryStream)o).Position}};
        if(o is byte[])return new Dictionary<string,object>{{"t",tn},{"b",Convert.ToBase64String((byte[])o)}};
        if(o is IDictionary) {
            var entries=new List<object>();foreach(DictionaryEntry p in (IDictionary)o)entries.Add(new object[]{Encode(p.Key,depth+1),Encode(p.Value,depth+1)});
            return new Dictionary<string,object>{{"t",tn},{"d",entries}};
        }
        if(t.IsArray || (o is IList && t.Assembly!=ax))return new Dictionary<string,object>{{"t",tn},{"l",((IEnumerable)o).Cast<object>().Select(x=>Encode(x,depth+1)).ToArray()}};
        var fields=new Dictionary<string,object>();
        foreach(var f in Fields(t))fields.Add(f.DeclaringType.FullName+"::"+f.Name,Encode(f.GetValue(o),depth+1));
        return new Dictionary<string,object>{{"t",tn},{"f",fields}};
    }
    static Type Resolve(string name)
    {
        var t=ax.GetType(name,false)??Type.GetType(name,false);
        if(t==null)throw new Exception("Unsupported type: "+name);
        return t;
    }
    static object Decode(object node,object context)
    {
        if(node==null)return null;
        var n=D(node);if(n.ContainsKey("$context"))return context;
        var t=Resolve((string)n["t"]);
        if(n.ContainsKey("v")){var v=n["v"];if(t==typeof(Guid))return new Guid((string)v);if(t==typeof(DateTime))return DateTime.Parse((string)v);if(t.IsEnum)return Enum.Parse(t,(string)v);return Convert.ChangeType(v,t,System.Globalization.CultureInfo.InvariantCulture);}
        if(n.ContainsKey("s")){var m=new MemoryStream(Convert.FromBase64String((string)n["s"]));m.Position=Convert.ToInt64(n["p"]);return m;}
        if(n.ContainsKey("b"))return Convert.FromBase64String((string)n["b"]);
        if(n.ContainsKey("d")){var d=(IDictionary)Activator.CreateInstance(t);foreach(var pair in A(n["d"])){var a=A(pair);d.Add(Decode(a[0],context),Decode(a[1],context));}return d;}
        if(n.ContainsKey("l")){var values=A(n["l"]).Select(x=>Decode(x,context)).ToArray();if(t.IsArray){var a=Array.CreateInstance(t.GetElementType(),values.Length);Array.Copy(values,a,values.Length);return a;}var list=(IList)Activator.CreateInstance(t);foreach(var v in values)list.Add(v);return list;}
        if(t.Assembly!=ax)throw new Exception("Unsupported field object type: "+t.FullName);
        var obj=FormatterServices.GetUninitializedObject(t);
        foreach(var p in D(n["f"])) {var split=p.Key.LastIndexOf("::",StringComparison.Ordinal);var declaring=Resolve(p.Key.Substring(0,split));var f=declaring.GetField(p.Key.Substring(split+2),BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.DeclaredOnly);f.SetValue(obj,Decode(p.Value,context));}
        return obj;
    }
    static object Export(object c)
    {
        return new Dictionary<string,object>{{"root",Field(contextType,"dbgs").GetValue(c).ToString()},{"package",Field(contextType,"cbg1").GetValue(c).ToString()},
            {"objects",((IEnumerable)Field(contextType,"cbgc").GetValue(c)).Cast<object>().Select(x=>Encode(x)).ToArray()}};
    }
    static void Import(object c,object dto)
    {
        var doc=D(dto);var rt=ax.GetType("qbLg.RbLk",true);
        var list=(IList)Activator.CreateInstance(typeof(List<>).MakeGenericType(rt));
        foreach(var n in A(doc["objects"]))list.Add(Decode(n,c));
        var rootId=new Guid((string)doc["root"]);
        var root=list.Cast<object>().Single(x=>(Guid)Field(rt,"QbLz").GetValue(x)==rootId);
        Field(contextType,"cbgc").SetValue(c,list);Field(contextType,"Vbg8").SetValue(c,root);Field(contextType,"dbgs").SetValue(c,rootId);Field(contextType,"cbg1").SetValue(c,new Guid((string)doc["package"]));
    }
    static void Normalize(object obj)
    {
        var d=obj as Dictionary<string,object>;
        if(d!=null){if(d.ContainsKey("t") && d.ContainsKey("v")){if((string)d["t"]=="System.Double")d["v"]=Convert.ToDouble(d["v"],System.Globalization.CultureInfo.InvariantCulture).ToString("R",System.Globalization.CultureInfo.InvariantCulture);if((string)d["t"]=="System.Single")d["v"]=Convert.ToSingle(d["v"],System.Globalization.CultureInfo.InvariantCulture).ToString("R",System.Globalization.CultureInfo.InvariantCulture);}foreach(var v in d.Values.ToArray())Normalize(v);return;}
        if(obj is IEnumerable && !(obj is string))foreach(var v in (IEnumerable)obj)Normalize(v);
    }
    sealed class Part { public Dictionary<string,object> Parent;public string Key;public int Offset;public byte[] Bytes;public string File; }
    static void Collect(Dictionary<string,object> node,List<Part> parts) { if(node.ContainsKey("parts"))foreach(var p in D(node["parts"]))parts.Add(new Part{Parent=D(node["parts"]),Key=p.Key,Offset=Convert.ToInt32(p.Value)});if(node.ContainsKey("children"))foreach(var ch in D(node["children"]).Values)Collect(D(ch),parts); }
    static List<Part> Read(string file,out Dictionary<string,object> index)
    {
        byte[] b=File.ReadAllBytes(file);if(b.Length<12 || b[0]!=172 || b[1]!=239 || b[2]!=9 || b[3]!=0)throw new Exception("Expected RP9 AC EF container.");
        int len=BitConverter.ToInt32(b,4);if(len<0 || len>b.Length-12)throw new Exception("Invalid index length.");
        index=D(json.DeserializeObject(Encoding.UTF8.GetString(Lz(b.Skip(8).Take(len).ToArray(),false))));var parts=new List<Part>();Collect(D(index["root"]),parts);parts.Sort((a,z)=>a.Offset.CompareTo(z.Offset));
        foreach(var p in parts){int off=12+len+p.Offset;if(off<0 || off>b.Length-4)throw new Exception("Invalid part offset.");int n=BitConverter.ToInt32(b,off);if(n<0 || n>b.Length-off-4)throw new Exception("Invalid part length.");p.Bytes=b.Skip(off+4).Take(n).ToArray();}return parts;
    }
    static void Unpack(string file,string folder)
    {
        if(Directory.Exists(folder))throw new Exception("Unpack directory already exists.");
        Dictionary<string,object> index;var parts=Read(file,out index);Directory.CreateDirectory(folder);int i=0;
        foreach(var p in parts){string stem=(i++).ToString("D4");File.WriteAllBytes(Path.Combine(folder,stem+".part"),p.Bytes);if(p.Bytes.Length>2 && p.Bytes[0]==31 && p.Bytes[1]==139){var raw=Gzip(p.Bytes,false);File.WriteAllBytes(Path.Combine(folder,stem+".raw"),raw);if(raw.Length>0 && raw[0]==27){var c=Load(raw);File.WriteAllText(Path.Combine(folder,stem+".json"),json.Serialize(Export(c)),new UTF8Encoding(false));}}p.Parent[p.Key]=stem;}
        File.WriteAllText(Path.Combine(folder,"index.json"),json.Serialize(index),new UTF8Encoding(false));Console.WriteLine(json.Serialize(new{ok=true,parts=parts.Count,folder=Path.GetFullPath(folder)}));
    }
    static void Pack(string folder,string output)
    {
        if(File.Exists(output))throw new Exception("Output exists. Use a new output path.");
        var index=D(json.DeserializeObject(File.ReadAllText(Path.Combine(folder,"index.json"))));var parts=new List<Part>();CollectStrings(D(index["root"]),parts);
        int offset=0,verified=0;
        foreach(var p in parts){var jp=Path.Combine(folder,p.File+".json");p.Bytes=File.ReadAllBytes(Path.Combine(folder,p.File+".part"));if(File.Exists(jp)){var c=Load(File.ReadAllBytes(Path.Combine(folder,p.File+".raw")));var dto=json.DeserializeObject(File.ReadAllText(jp));Normalize(dto);Import(c,dto);var raw=Save(c);var check=Export(Load(raw));if(json.Serialize(check)!=json.Serialize(dto)){File.WriteAllText(Path.Combine(folder,p.File+".checked"),json.Serialize(check));throw new Exception("Native parser roundtrip mismatch: "+p.File);}p.Bytes=Gzip(raw,true);verified++;}p.Parent[p.Key]=offset;offset+=8+p.Bytes.Length;}
        var header=Lz(Encoding.UTF8.GetBytes(json.Serialize(index)),true);using(var m=new MemoryStream())using(var w=new BinaryWriter(m)){w.Write(new byte[]{172,239,9,0});w.Write(header.Length);w.Write(header);w.Write(0);for(int n=0;n<parts.Count;n++){w.Write(parts[n].Bytes.Length);w.Write(parts[n].Bytes);if(n+1<parts.Count)w.Write(0);}using(var f=new FileStream(output,FileMode.CreateNew,FileAccess.Write,FileShare.None))m.WriteTo(f);}
        Console.WriteLine(json.Serialize(new{ok=true,nativePackagesVerified=verified,output=Path.GetFullPath(output)}));
    }
    static void CollectStrings(Dictionary<string,object> node,List<Part> parts){if(node.ContainsKey("parts"))foreach(var p in D(node["parts"]))parts.Add(new Part{Parent=D(node["parts"]),Key=p.Key,File=(string)p.Value});if(node.ContainsKey("children"))foreach(var child in D(node["children"]).Values)CollectStrings(D(child),parts);}
    static object ModelSnapshot(object obj) {
        var b=ax.GetType("IbTX.Qbgz",true);
        var handling=Enum.ToObject(ax.GetType("Axure.Platform.ObjectPersistanceContext.SubPackageHandling",true),0);
        var c=b.GetMethod("DbTH",All).Invoke(null,new[]{obj,handling});
        return Export(Load(Save(c)));
    }
    static void Schema(string selector,string destination) {
        if(Directory.Exists(destination))throw new Exception("Schema destination already exists.");
        Directory.CreateDirectory(destination);
        var packageType=ax.GetType("Nb6q.Gb6E",true);
        var pkg=Activator.CreateInstance(ax.GetType("HWf8.WWf2",true),All,null,new object[]{Guid.NewGuid(),Guid.NewGuid()},null);
        Type[] types;try{types=ax.GetTypes();}catch(ReflectionTypeLoadException e){types=e.Types.Where(t=>t!=null).ToArray();}
        var reports=new List<object>();
        foreach(var t in types.Where(t=>!t.IsAbstract && !t.IsEnum && t.FullName.StartsWith("Axure.DocumentModel.") && !t.FullName.Contains("+"))) {
            if(!(t.FullName.Contains(".Interaction.") || t.FullName.Contains(".Expressions.")))continue;
            foreach(var ctor in t.GetConstructors(All).Where(c=>c.GetParameters().Any(p=>p.ParameterType==packageType)).OrderBy(c=>c.GetParameters().Length)) {
                try {
                    var ps=ctor.GetParameters();var args=new object[ps.Length];
                    for(int n=0;n<ps.Length;n++){var pt=ps[n].ParameterType;args[n]=pt==packageType?pkg:pt==typeof(Guid)?(object)Guid.NewGuid():pt==typeof(string)?"":pt.IsValueType?Activator.CreateInstance(pt):pt==typeof(Dictionary<string,double>)?new Dictionary<string,double>():null;}
                    var obj=ctor.Invoke(args);
                    if(obj is IDisposable && ax.GetType("IbTX.Qbgz").IsAssignableFrom(t)) {
                        var add=t.GetMethod("hSyX",All);if(add!=null && t.Name!="IxAction")try{add.Invoke(obj,new object[]{Guid.NewGuid(),false});}catch{}
                        var dto=ModelSnapshot(obj);var path=Path.Combine(destination,t.Name+".json");File.WriteAllText(path,json.Serialize(dto),new UTF8Encoding(false));
                        reports.Add(new{type=t.FullName,file=Path.GetFileName(path)});break;
                    }
                }catch(Exception e){if(ctor==t.GetConstructors(All).Where(c=>c.GetParameters().Any(p=>p.ParameterType==packageType)).OrderBy(c=>c.GetParameters().Length).Last())reports.Add(new{type=t.FullName,error=e.GetBaseException().Message});}
            }
        }
        // Selectable native list items used by droplists and listboxes.
        var option=Activator.CreateInstance(ax.GetType("mbGg.YbGk",true),new object[]{pkg,"",false});
        File.WriteAllText(Path.Combine(destination,"SelectableListItem.json"),json.Serialize(ModelSnapshot(option)),new UTF8Encoding(false));
        reports.Add(new{type="mbGg.YbGk",file="SelectableListItem.json"});
        var enums=types.Where(t=>t.IsEnum && (t.FullName.Contains("Interaction") || t.FullName.Contains("Expressions") || t.FullName=="Axure.Constants.IxEventType" || t.FullName=="Axure.Constants.PName" || t.FullName=="Axure.Platform.LogicalComparison")).ToDictionary(t=>t.FullName,t=>(object)Enum.GetValues(t).Cast<object>().ToDictionary(v=>v.ToString(),v=>Convert.ToInt64(v)));
        File.WriteAllText(Path.Combine(destination,"enums.json"),json.Serialize(enums),new UTF8Encoding(false));
        File.WriteAllText(Path.Combine(destination,"catalog.json"),json.Serialize(reports),new UTF8Encoding(false));
        Console.WriteLine(json.Serialize(new{ok=true,models=reports.Count,folder=Path.GetFullPath(destination)}));
    }
    static int Main(string[] args)
    {
        Console.OutputEncoding=new UTF8Encoding(false);
        try{if(args.Length!=4)throw new Exception("Usage: NativeBridge <Axure9-install> unpack|pack|schema <source> <destination>");Init(args[0]);if(args[1]=="unpack")Unpack(args[2],args[3]);else if(args[1]=="pack")Pack(args[2],args[3]);else if(args[1]=="schema")Schema(args[2],args[3]);else throw new Exception("Unknown command.");return 0;}
        catch(Exception e){while(e is TargetInvocationException && e.InnerException!=null)e=e.InnerException;Console.Error.WriteLine(e.ToString());return 1;}
    }
}

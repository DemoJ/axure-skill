using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Web.Script.Serialization;
using Axure.Document;
using Axure.Document.Widgets;

// Optional independent check with Axure's public read-only API.
internal static class OfficialVerify
{
    static object Widget(RPWidget w,int depth) {
        if(depth>20)throw new Exception("Widget nesting exceeds verifier limit.");
        var result=new Dictionary<string,object>{{"name",w.Name},{"type",w.GetType().Name},
            {"x",w.Rectangle.X},{"y",w.Rectangle.Y},{"width",w.Rectangle.Width},{"height",w.Rectangle.Height},
            {"text",w is RPTextWidget ? ((RPTextWidget)w).Text : ""},{"font_size",w.FontSize},
            {"bold",w.Bold},{"fill",w.FillColor.ToString()},{"color",w.ForeColor.ToString()},{"has_interaction",w.HasInteraction}};
        if(w.HasInteraction) {
            result["interaction_description"]=w.Interaction.InteractionDescription;
            result["events"]=w.Interaction.Events.Select(e=>new{name=e.EventName,description=e.EventDescription}).ToArray();
        }
        if(w is RPDynamicPanel) {
            var panel=(RPDynamicPanel)w;result["visible"]=panel.IsVisible;
            result["states"]=panel.PanelStates.Select(s=>new{name=s.DiagramName,widgets=s.Widgets.Select(child=>Widget(child,depth+1)).ToArray()}).ToArray();
        } else if(w.HasChildren)result["children"]=w.Widgets.Select(child=>Widget(child,depth+1)).ToArray();
        return result;
    }
    static IEnumerable<RPPackageHandle> Pages(IEnumerable<RPTreeMapNode> nodes)
    {
        foreach(var n in nodes){if(n.NodeValue is RPPackageHandle)yield return (RPPackageHandle)n.NodeValue;foreach(var p in Pages(n.ChildNodes))yield return p;}
    }
    [STAThread]
    static int Main(string[] args)
    {
        try {
            Console.OutputEncoding=new System.Text.UTF8Encoding(false);
            var doc=RPDocument.Load(args[0]);
            var pages=new List<object>();int index=0;
            foreach(var h in Pages(doc.Sitemap.RootNodes)) {
                var page=(RPDiagramPackage)doc.LoadPackage(h);
                var widgets=page.Diagram.Widgets.Select(w=>Widget(w,0)).ToArray();
                string screenshot=null;
                if(args.Length>1){Directory.CreateDirectory(args[1]);screenshot=Path.Combine(args[1],"page-"+(++index)+".png");page.Diagram.RenderScreenshot(screenshot,RPImageFormat.Png,false,true);}
                if(args.Length>1) {int pn=0;foreach(var panel in page.Diagram.Widgets.OfType<RPDynamicPanel>()) {++pn;int sn=0;foreach(var state in panel.PanelStates) state.RenderScreenshot(Path.Combine(args[1],"page-"+index+"-panel-"+pn+"-state-"+(++sn)+".png"),RPImageFormat.Png,false,true);}}
                pages.Add(new {name=page.PackageName,widgets=widgets,screenshot=screenshot});page.Dispose();
            }
            Console.WriteLine(new JavaScriptSerializer{MaxJsonLength=10000000}.Serialize(new{ok=true,source="Axure public RP9 API",pages=pages}));
            return 0;
        } catch(Exception e){Console.Error.WriteLine(e);return 1;}
    }
}

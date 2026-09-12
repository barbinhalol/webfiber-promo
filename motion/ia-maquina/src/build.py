import base64, json, os, sys
S=os.path.dirname(os.path.abspath(__file__)); R=os.path.dirname(S)
tpl=open(f"{S}/template.html",encoding="utf-8").read()
fonts=[("Anton","Anton-Regular.ttf",400),("Space Mono","SpaceMono-Regular.ttf",400),("Space Mono","SpaceMono-Bold.ttf",700),("Bebas Neue","BebasNeue-Regular.ttf",400),("Space Grotesk","SpaceGrotesk[wght].ttf","300 700")]
css=""
for fam,fn,w in fonts:
    b=base64.b64encode(open(f"{R}/fonts/{fn}","rb").read()).decode()
    css+=f"@font-face{{font-family:'{fam}';font-weight:{w};font-style:normal;src:url(data:font/ttf;base64,{b}) format('truetype')}}\n"
env=json.load(open(f"{R}/env.json"))
out=tpl.replace("/*FONTS*/",css).replace("/*ENV*/","const ENV="+json.dumps(env)+";")
dst=sys.argv[1] if len(sys.argv)>1 else f"{R}/index.html"
open(dst,"w",encoding="utf-8").write(out); print("wrote",dst,len(out)//1024,"KB")

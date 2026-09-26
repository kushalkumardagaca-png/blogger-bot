"""Rendered-head SEO/Open Graph metadata injection for Blogger content packages."""
import json,re
START='<!-- DY_SEO_META_START -->';END='<!-- DY_SEO_META_END -->'
def ensure_seo_meta(content,title,description,image=''):
 description=re.sub(r'\s+',' ',description).strip()[:158]
 payload=json.dumps({'title':title,'description':description,'image':image},ensure_ascii=False).replace('</','<\\/')
 block=START+'''<script id="dySeoMeta">(function(){var d='''+payload+''',h=document.head;
 function m(sel,attr,key,val){var x=document.querySelector(sel);if(!x){x=document.createElement("meta");x.setAttribute(attr,key);h.appendChild(x)}x.content=val}
 m('meta[name="description"]','name','description',d.description);
 m('meta[property="og:title"]','property','og:title',d.title);m('meta[property="og:description"]','property','og:description',d.description);
 m('meta[name="twitter:card"]','name','twitter:card','summary_large_image');m('meta[name="twitter:title"]','name','twitter:title',d.title);m('meta[name="twitter:description"]','name','twitter:description',d.description);
 if(d.image){m('meta[property="og:image"]','property','og:image',d.image);m('meta[name="twitter:image"]','name','twitter:image',d.image)}
})();</script>'''+END
 pattern=re.escape(START)+r'.*?'+re.escape(END)
 content,n=re.subn(pattern,lambda _:block,content,flags=re.S)
 return content if n else content.rstrip()+'\n'+block

"""Shared fast, swipeable and reliably resumable horizontal-motion controller."""
MARKER_START='<!-- DY_CONTINUOUS_MOTION_START -->';MARKER_END='<!-- DY_CONTINUOUS_MOTION_END -->'
BLOCK=MARKER_START+r'''
<style id="dyContinuousMotionStyle">
.kvsd-mqwrap,.kn-rowwrap,.dyw-marquee,.marquee,.ar-viewport,.dy-related-viewport{cursor:grab;touch-action:pan-y;user-select:none;-webkit-user-select:none;overscroll-behavior-inline:contain}.dy-grabbing{cursor:grabbing!important}.dy-grabbing a,.dy-grabbing button{pointer-events:none}.dy-native-loop{scrollbar-width:none!important;-ms-overflow-style:none}.dy-native-loop::-webkit-scrollbar{display:none!important}
</style>
<script id="dyContinuousMotionScript">
(function(w,d){'use strict';
 /* Homepage motion is intentionally owned by the Theme and remains unchanged. */
 if(d.body&&d.body.classList.contains('fk-home'))return;
 var reduced=w.matchMedia&&w.matchMedia('(prefers-reduced-motion: reduce)').matches;
 function bind(view,track,speed,auto){
  if(!view||view.dataset.dyMotion)return;view.dataset.dyMotion='3';view.classList.add('dy-native-loop');
  if(track){track.style.animation='none';track.style.animationPlayState='running';track.style.transform='none';track.style.flexWrap='nowrap';track.style.maxWidth='none'}
  var drag=null,moved=false,last=0,pausedUntil=0,hover=false;
  function cycle(){if(!track)return 0;var first=track.querySelector('.dyw-category-copy,.dy-related-group');return first?first.scrollWidth:track.scrollWidth/2}
  function normalize(){var c=cycle();if(c>0){while(view.scrollLeft>=c)view.scrollLeft-=c;while(view.scrollLeft<0)view.scrollLeft+=c}}
  function delay(ms){pausedUntil=Date.now()+ms}
  view.addEventListener('pointerdown',function(e){if(e.pointerType==='mouse'&&e.button!==0)return;drag={x:e.clientX,s:view.scrollLeft,id:e.pointerId};moved=false;pausedUntil=0;view.classList.add('dy-grabbing');try{view.setPointerCapture(e.pointerId)}catch(_){}});
  view.addEventListener('pointermove',function(e){if(!drag)return;var dx=e.clientX-drag.x;if(Math.abs(dx)>5)moved=true;var next=drag.s-dx,c=cycle();if(next<0&&c>0){drag.s+=c;next+=c}view.scrollLeft=next;if(moved)e.preventDefault()});
  function end(){if(!drag)return;var id=drag.id;drag=null;normalize();view.classList.remove('dy-grabbing');try{if(view.hasPointerCapture(id))view.releasePointerCapture(id)}catch(_){}delay(180);if(moved){view.dataset.dySwiped='1';setTimeout(function(){delete view.dataset.dySwiped},420)}}
  view.addEventListener('pointerup',end);view.addEventListener('pointercancel',end);view.addEventListener('lostpointercapture',end);w.addEventListener('blur',end);
  view.addEventListener('pointerenter',function(e){if(e.pointerType==='mouse')hover=true});view.addEventListener('pointerleave',function(e){if(e.pointerType==='mouse'){hover=false;delay(250)}});
  view.addEventListener('click',function(e){if(view.dataset.dySwiped){e.preventDefault();e.stopPropagation()}},true);view.addEventListener('dragstart',function(e){e.preventDefault()});
  view.addEventListener('wheel',function(e){var delta=Math.abs(e.deltaX)>Math.abs(e.deltaY)?e.deltaX:(e.shiftKey?e.deltaY:0);if(!delta)return;view.scrollLeft+=delta;normalize();delay(900);e.preventDefault()},{passive:false});
  function frame(ts){if(!last)last=ts;var dt=Math.min(.05,(ts-last)/1000);last=ts;if(auto&&!drag&&!hover&&Date.now()>pausedUntil&&!reduced&&!d.hidden&&track&&track.scrollWidth>view.clientWidth+8){view.scrollLeft+=speed*dt;normalize()}w.requestAnimationFrame(frame)}w.requestAnimationFrame(frame)
 }
 function scan(){
  if(d.body&&d.body.classList.contains('fk-home'))return;
  d.querySelectorAll('.kvsd-mqwrap').forEach(function(v){bind(v,v.querySelector('.kvsd-mq'),72,true)});
  d.querySelectorAll('.kn-rowwrap').forEach(function(v){bind(v,v.querySelector('.kn-track'),72,true)});
  d.querySelectorAll('.dyw-marquee').forEach(function(v){bind(v,v.querySelector('.dyw-category-track'),72,true)});
  d.querySelectorAll('.marquee').forEach(function(v){bind(v,v.querySelector('.marquee-track'),72,true)});
  d.querySelectorAll('.dy-related-viewport').forEach(function(v){bind(v,v.querySelector('.dy-related-track'),72,true)});
  d.querySelectorAll('.ar-viewport').forEach(function(v){bind(v,null,0,false)});
 }
 if(d.readyState==='loading')d.addEventListener('DOMContentLoaded',scan);else scan();new MutationObserver(scan).observe(d.documentElement,{childList:true,subtree:true});
})(window,document);
</script>
'''+MARKER_END

def ensure(content):
 import re
 content=re.sub(re.escape(MARKER_START)+r'.*?'+re.escape(MARKER_END),'',content,flags=re.S)
 return BLOCK+'\n'+content

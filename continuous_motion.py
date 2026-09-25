"""Shared continuous, swipeable/dragable horizontal-motion controller."""
MARKER_START='<!-- DY_CONTINUOUS_MOTION_START -->';MARKER_END='<!-- DY_CONTINUOUS_MOTION_END -->'
BLOCK=MARKER_START+r'''
<style id="dyContinuousMotionStyle">
.kvsd-mqwrap:hover .kvsd-mq,.kn-rowwrap:hover .kn-track,.marquee:hover .marquee-track,.dyw-category-row:hover .dyw-category-track,.dyw-category-row:focus-within .dyw-category-track,.dyw-category-row.dyw-paused .dyw-category-track{animation-play-state:running!important}
.kvsd-mqwrap,.kn-rowwrap,.dyw-marquee,.marquee,.ar-viewport,.dy-related-viewport{cursor:grab;touch-action:pan-y;user-select:none;-webkit-user-select:none}.dy-grabbing{cursor:grabbing!important}.dy-grabbing a,.dy-grabbing button{pointer-events:none}.dy-native-loop{scrollbar-width:none!important;-ms-overflow-style:none}.dy-native-loop::-webkit-scrollbar{display:none!important}
</style>
<script id="dyContinuousMotionScript">
(function(){'use strict';
 var reduced=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;
 function bind(view,track,speed,auto){
  if(!view||view.dataset.dyMotion)return;view.dataset.dyMotion='2';view.classList.add('dy-native-loop');
  if(track){track.style.animation='none';track.style.transform='none';track.style.flexWrap='nowrap';track.style.maxWidth='none'}
  var drag=null,moved=false,last=0;
  function cycle(){if(!track)return 0;var first=track.querySelector('.dyw-category-copy,.dy-related-group');return first?first.scrollWidth:track.scrollWidth/2}
  function normalize(){var c=cycle();if(c>0){if(view.scrollLeft>=c)view.scrollLeft-=c;if(view.scrollLeft<0)view.scrollLeft+=c}}
  view.addEventListener('pointerdown',function(e){if(e.pointerType==='mouse'&&e.button!==0)return;drag={x:e.clientX,s:view.scrollLeft,id:e.pointerId};moved=false;view.classList.add('dy-grabbing');try{view.setPointerCapture(e.pointerId)}catch(_){}});
  view.addEventListener('pointermove',function(e){if(!drag)return;var dx=e.clientX-drag.x;if(Math.abs(dx)>5)moved=true;var next=drag.s-dx,c=cycle();if(next<0&&c>0){drag.s+=c;next+=c}view.scrollLeft=next;if(moved)e.preventDefault()});
  function end(){if(!drag)return;drag=null;normalize();view.classList.remove('dy-grabbing');if(moved){view.dataset.dySwiped='1';setTimeout(function(){delete view.dataset.dySwiped},500)}}
  view.addEventListener('pointerup',end);view.addEventListener('pointercancel',end);view.addEventListener('click',function(e){if(view.dataset.dySwiped){e.preventDefault();e.stopPropagation()}},true);view.addEventListener('dragstart',function(e){e.preventDefault()});
  view.addEventListener('wheel',function(e){var d=Math.abs(e.deltaX)>Math.abs(e.deltaY)?e.deltaX:(e.shiftKey?e.deltaY:0);if(!d)return;view.scrollLeft+=d;normalize();e.preventDefault()},{passive:false});
  function frame(ts){if(!last)last=ts;var dt=Math.min(.05,(ts-last)/1000);last=ts;if(auto&&!drag&&!reduced&&!document.hidden&&track&&track.scrollWidth>view.clientWidth+8){view.scrollLeft+=speed*dt;normalize()}requestAnimationFrame(frame)}requestAnimationFrame(frame)
 }
 function scan(){
  document.querySelectorAll('.kvsd-mqwrap').forEach(function(v){bind(v,v.querySelector('.kvsd-mq'),34,true)});
  document.querySelectorAll('.kn-rowwrap').forEach(function(v){bind(v,v.querySelector('.kn-track'),30,true)});
  document.querySelectorAll('.dyw-marquee').forEach(function(v){bind(v,v.querySelector('.dyw-category-track'),30,true)});
  document.querySelectorAll('.marquee').forEach(function(v){bind(v,v.querySelector('.marquee-track'),28,true)});
  document.querySelectorAll('.dy-related-viewport').forEach(function(v){bind(v,v.querySelector('.dy-related-track'),26,true)});
  document.querySelectorAll('.ar-viewport').forEach(function(v){bind(v,null,0,false)});
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',scan);else scan();new MutationObserver(scan).observe(document.documentElement,{childList:true,subtree:true});
})();
</script>
'''+MARKER_END

def ensure(content):
 import re
 content=re.sub(re.escape(MARKER_START)+r'.*?'+re.escape(MARKER_END),'',content,flags=re.S)
 return BLOCK+'\n'+content

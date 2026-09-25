"""Shared continuous, swipeable/dragable horizontal-motion controller."""
MARKER_START='<!-- DY_CONTINUOUS_MOTION_START -->';MARKER_END='<!-- DY_CONTINUOUS_MOTION_END -->'
BLOCK=MARKER_START+r'''
<style id="dyContinuousMotionStyle">
/* Motion continues after clicks/focus; dragging temporarily takes direct control. */
.kvsd-mqwrap:hover .kvsd-mq,.kn-rowwrap:hover .kn-track,.marquee:hover .marquee-track,.dyw-category-row:hover .dyw-category-track,.dyw-category-row:focus-within .dyw-category-track,.dyw-category-row.dyw-paused .dyw-category-track{animation-play-state:running!important}
.kvsd-mqwrap,.kn-rowwrap,.dyw-marquee,.marquee,.ar-row-viewport,.dy-related-viewport{cursor:grab;touch-action:pan-y;user-select:none;-webkit-user-select:none}
.dy-grabbing{cursor:grabbing!important}.dy-grabbing a,.dy-grabbing button{pointer-events:none}
</style>
<script id="dyContinuousMotionScript">
(function(){'use strict';
 var reduced=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;
 function matrixX(el){var t=getComputedStyle(el).transform;if(!t||t==='none')return 0;try{return new DOMMatrixReadOnly(t).m41||0}catch(e){var m=t.match(/matrix\([^,]+,[^,]+,[^,]+,[^,]+,([^,]+)/);return m?parseFloat(m[1]):0}}
 function bindTransform(view,track,speed){
  if(!view||!track||track.dataset.dyMotion)return;track.dataset.dyMotion='1';var pos=matrixX(track),drag=null,last=0,moved=false;
  track.style.animation='none';track.style.animationPlayState='running';track.style.transform='translate3d('+pos+'px,0,0)';
  function cycle(){var first=track.querySelector('.dyw-category-copy');return first?first.scrollWidth:track.scrollWidth/2}
  function wrap(){var c=cycle();if(c>0){while(pos<=-c)pos+=c;while(pos>0)pos-=c}}
  function paint(){wrap();track.style.transform='translate3d('+pos.toFixed(2)+'px,0,0)'}
  view.addEventListener('pointerdown',function(e){if(e.pointerType==='mouse'&&e.button!==0)return;drag={x:e.clientX,p:pos,id:e.pointerId};moved=false;view.classList.add('dy-grabbing');try{view.setPointerCapture(e.pointerId)}catch(_){}});
  view.addEventListener('pointermove',function(e){if(!drag)return;var dx=e.clientX-drag.x;if(Math.abs(dx)>5)moved=true;pos=drag.p+dx;paint();if(moved)e.preventDefault()});
  function end(){if(!drag)return;drag=null;view.classList.remove('dy-grabbing');if(moved){view.dataset.dySwiped='1';setTimeout(function(){delete view.dataset.dySwiped},500)}}
  view.addEventListener('pointerup',end);view.addEventListener('pointercancel',end);
  view.addEventListener('click',function(e){if(view.dataset.dySwiped){e.preventDefault();e.stopPropagation()}},true);
  view.addEventListener('wheel',function(e){var d=Math.abs(e.deltaX)>Math.abs(e.deltaY)?e.deltaX:(e.shiftKey?e.deltaY:0);if(!d)return;pos-=d;paint();e.preventDefault()},{passive:false});
  view.addEventListener('dragstart',function(e){e.preventDefault()});
  function frame(ts){if(!last)last=ts;var dt=Math.min(.05,(ts-last)/1000);last=ts;if(!drag&&!reduced&&!document.hidden&&track.scrollWidth>view.clientWidth+8){pos-=speed*dt;paint()}requestAnimationFrame(frame)}requestAnimationFrame(frame)
 }
 function bindNative(view){if(!view||view.dataset.dyNative)return;view.dataset.dyNative='1';var d=null,m=false;view.addEventListener('pointerdown',function(e){if(e.pointerType==='mouse'&&e.button!==0)return;d={x:e.clientX,s:view.scrollLeft,id:e.pointerId};m=false;view.classList.add('dy-grabbing');try{view.setPointerCapture(e.pointerId)}catch(_){}});view.addEventListener('pointermove',function(e){if(!d)return;var dx=e.clientX-d.x;if(Math.abs(dx)>5)m=true;view.scrollLeft=d.s-dx;if(m)e.preventDefault()});function end(){d=null;view.classList.remove('dy-grabbing');if(m){view.dataset.dySwiped='1';setTimeout(function(){delete view.dataset.dySwiped},500)}}view.addEventListener('pointerup',end);view.addEventListener('pointercancel',end);view.addEventListener('click',function(e){if(view.dataset.dySwiped){e.preventDefault();e.stopPropagation()}},true)}
 function scan(){document.querySelectorAll('.kvsd-mqwrap').forEach(function(v){bindTransform(v,v.querySelector('.kvsd-mq'),34)});document.querySelectorAll('.kn-rowwrap').forEach(function(v){bindTransform(v,v.querySelector('.kn-track'),30)});document.querySelectorAll('.dyw-marquee').forEach(function(v){bindTransform(v,v.querySelector('.dyw-category-track'),30)});document.querySelectorAll('.marquee').forEach(function(v){bindTransform(v,v.querySelector('.marquee-track'),28)});document.querySelectorAll('.dy-related-viewport').forEach(function(v){bindTransform(v,v.querySelector('.dy-related-track'),26)});document.querySelectorAll('.ar-row-viewport').forEach(bindNative)}
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',scan);else scan();new MutationObserver(scan).observe(document.documentElement,{childList:true,subtree:true});
})();
</script>
'''+MARKER_END

def ensure(content):
 import re
 content=re.sub(re.escape(MARKER_START)+r'.*?'+re.escape(MARKER_END),'',content,flags=re.S)
 return BLOCK+'\n'+content

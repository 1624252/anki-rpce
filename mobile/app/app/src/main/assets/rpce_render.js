/* Generated from anki.rpce.render_js — do not edit by hand. */
var RPCE_CSS = "\n.rpce-q{font-size:19px;line-height:1.6;color:#0a1f44}\n.rpce-hint{font-size:13px;color:#35548c;font-style:italic}\n.rpce-blank{display:inline-block;min-width:64px;text-align:center;border:none;\n  border-bottom:2px dashed #1d4ed8;background:rgba(37,99,235,.08);color:#1d4ed8;\n  border-radius:6px 6px 0 0;padding:1px 8px;margin:0 2px;font:inherit;font-weight:700;cursor:pointer}\n.rpce-blank.revealed{border-bottom-color:#15803d;background:rgba(21,128,61,.12);\n  color:#15803d;cursor:default}\n.rpce-controls{margin-top:16px;display:flex;gap:10px;flex-wrap:wrap}\n.rpce-btn{border:1px solid #caddf7;background:#f4f8ff;color:#1d4ed8;border-radius:12px;\n  padding:10px 16px;font:inherit;font-weight:700;cursor:pointer}\n.rpce-opts{display:flex;flex-direction:column;gap:4px;margin-top:14px}\n.rpce-opt{text-align:left;font-size:17px;line-height:1.4;padding:7px 16px;border-radius:12px;\n  border:1px solid #caddf7;background:#f4f8ff;color:#0a1f44;cursor:pointer;font:inherit}\n.rpce-opt .k{font-weight:800;color:#35548c;margin-right:8px}\n.rpce-opt .mark{float:right;font-weight:800}\n.rpce-opt.ok{background:rgba(21,128,61,.14);border-color:#15803d;color:#14532d;font-weight:700}\n.rpce-opt.no{background:rgba(190,18,60,.10);border-color:#be123c;color:#7f1d1d;font-weight:700}\n.rpce-opt:disabled{cursor:default}\n.rpce-chips{display:flex;flex-wrap:wrap;gap:10px;margin-top:16px}\n.rpce-chip{padding:12px 16px;border-radius:12px;border:1px solid #caddf7;background:#f4f8ff;\n  color:#0a1f44;cursor:pointer;font:inherit;font-size:16px;position:relative}\n.rpce-chip .pos{display:inline-block;min-width:22px;height:22px;line-height:22px;text-align:center;\n  border-radius:50%;background:#1d4ed8;color:#fff;font-size:13px;font-weight:800;margin-right:8px}\n.rpce-chip.ok{background:rgba(21,128,61,.14);border-color:#15803d}\n.rpce-chip.no{background:rgba(190,18,60,.10);border-color:#be123c}\n.rpce-fb{margin-top:14px;font-size:16px;font-weight:700;min-height:20px}\n.rpce-answer{margin-top:14px;font-size:17px;line-height:1.5;color:#0a1f44}\n.rpce-ref{margin-top:16px;padding:12px 15px;border-left:4px solid #2f6fed;background:#eef4ff;\n  border-radius:10px;text-align:left}\n.rpce-cite{font-weight:700;color:#1b3faa;font-size:15px}\n.rpce-quote{margin-top:6px;font-style:italic;color:#0a1f44;font-size:16px}\n/* multi-select */\n.rpce-opt.sel{background:#dbeafe;border-color:#1d4ed8;font-weight:700}\n.rpce-opt .box{display:inline-block;width:18px;height:18px;border:2px solid #94a3b8;border-radius:5px;margin-right:10px;vertical-align:-3px}\n.rpce-opt.sel .box{background:#1d4ed8;border-color:#1d4ed8}\n/* ordering (vertical; top = higher precedence) */\n.rpce-axis{font-size:12px;font-weight:700;color:#64748b;margin:14px 0 6px}\n.rpce-dest{display:flex;flex-direction:column;gap:4px;min-height:8px;\n  border-left:3px solid #caddf7;padding-left:12px;margin:4px 0}\n.rpce-slot{display:flex;align-items:center;gap:8px;padding:2px 10px;border-radius:10px;\n  border:1px solid #caddf7;background:#f4f8ff;color:#0a1f44;font-size:16px;line-height:1.25}\n.rpce-slot .n{min-width:20px;height:20px;line-height:20px;text-align:center;border-radius:50%;\n  background:#1d4ed8;color:#fff;font-size:12px;font-weight:800}\n.rpce-slot.ok{background:rgba(21,128,61,.14);border-color:#15803d}\n.rpce-slot.no{background:rgba(190,18,60,.10);border-color:#be123c}\n.rpce-src .rpce-chip.used{opacity:.35;pointer-events:none}\n/* drag-to-reorder ordering list */\n.rpce-order{touch-action:none}\n.rpce-order .rpce-slot{cursor:grab;touch-action:none;user-select:none;-webkit-user-select:none}\n.rpce-order .rpce-slot.drag{opacity:.6;box-shadow:0 4px 12px rgba(0,0,0,.18)}\n.rpce-order .rpce-slot .lbl{flex:1}\n.rpce-slot .rpce-omark{margin-left:8px;font-weight:800;font-size:13px;white-space:nowrap}\n.rpce-grip{color:#94a3b8;font-size:17px;cursor:grab;line-height:1}\n/* \u25b2/\u25bc side-by-side (accessible fallback to dragging) so the row stays one line tall */\n.rpce-moves{display:flex;flex-direction:row;gap:3px}\n.rpce-move{border:1px solid #caddf7;background:#fff;color:#1d4ed8;border-radius:6px;\n  width:26px;height:22px;line-height:1;font-size:12px;font-weight:800;cursor:pointer;padding:0}\n.rpce-move:disabled{opacity:.4;cursor:default}\n";

(function(){
  function el(tag, cls, html){ var e=document.createElement(tag);
    if(cls) e.className=cls; if(html!=null) e.innerHTML=html; return e; }
  // Answer-side citation block. A payload may carry a LIST of citations in
  // p.cites (e.g. select-all questions cite every relevant motion); otherwise
  // we fall back to the single p.cite/p.quote. All are rendered.
  function refBlock(p){
    var cites = (p.cites && p.cites.length) ? p.cites
      : (p.cite ? [{cite:p.cite, quote:p.quote}] : null);
    if(!cites) return null;
    var d=el('div','rpce-ref');
    cites.forEach(function(c){
      if(!c || !c.cite) return;
      d.appendChild(el('div','rpce-cite','RONR (12th ed.) §'+c.cite));
      if(c.quote) d.appendChild(el('div','rpce-quote','“'+c.quote+'”'));
    });
    return d; }
  function shuffle(a){ a=a.slice(); for(var i=a.length-1;i>0;i--){
    var j=Math.floor(Math.random()*(i+1)); var t=a[i];a[i]=a[j];a[j]=t;} return a; }
  function done(host,p,opts){ var r=refBlock(p); if(r) host.appendChild(r);
    if(opts&&opts.onComplete) opts.onComplete(); }

  // ---- cloze: tappable blanks with hints + reveal-all -----------------------
  function renderCloze(p, host, opts){
    var wrap=el('div','rpce-q');
    var parts=p.text.split(/(\[\[\d+\]\])/);
    var blanks=[], total=0;
    parts.forEach(function(seg){
      var m=seg.match(/^\[\[(\d+)\]\]$/);
      if(m){ var i=+m[1]; var b=p.blanks[i]||{a:'',h:''};
        total++;
        var span=el('span','rpce-blank');
        // Show a category hint only where the sentence can't give it away
        // (debatable/undebatable, amendable/not) — never a spelling hint.
        span.textContent = b.h ? ('? ('+b.h+')') : '?';
        span.title='Tap to reveal';
        span.dataset.a=b.a;
        wrap.appendChild(span); blanks.push(span);
      } else { wrap.appendChild(document.createTextNode(seg)); }
    });
    host.appendChild(wrap);
    var revealed=0, finished=false;
    function reveal(span){ if(span.classList.contains('revealed')) return;
      span.classList.add('revealed'); span.textContent=span.dataset.a; revealed++;
      if(revealed>=total && !finished){ finished=true; done(host,p,opts); } }
    blanks.forEach(function(s){ s.onclick=function(){ reveal(s); }; });
    if(opts&&opts.reveal){ blanks.forEach(reveal); return; }
    var ctr=el('div','rpce-controls');
    var all=el('button','rpce-btn','Reveal all'); all.onclick=function(){ blanks.forEach(reveal); };
    ctr.appendChild(all); host.appendChild(ctr);
  }

  // ---- multiple choice: tappable options ------------------------------------
  function renderMcq(p, host, opts){
    host.appendChild(el('div','rpce-q', p.stem));
    var box=el('div','rpce-opts'); var fb=el('div','rpce-fb');
    var letters='ABCDEFGH', picked=false;
    // Fresh question: forget any earlier pick (survives the desktop's
    // question->answer content swap, which shares this JS context).
    if(!(opts&&opts.reveal)){ try{window.__rpce_pick=-1;}catch(e){} }
    // Paint the answered state for a given picked index (-1 = none picked).
    function mark(pick){
      var btns=box.querySelectorAll('button');
      for(var j=0;j<btns.length;j++){ btns[j].disabled=true;
        if(j===p.answer){ btns[j].classList.add('ok'); btns[j].innerHTML+='<span class="mark">✓</span>'; }
        else if(j===pick){ btns[j].classList.add('no'); btns[j].innerHTML+='<span class="mark">✗</span>'; } }
      if(pick>=0){ fb.style.color=(pick===p.answer)?'#15803d':'#be123c';
        fb.textContent=(pick===p.answer)?'✓ Correct':'✗ Not quite — the correct answer is highlighted.'; }
    }
    p.options.forEach(function(opt,i){
      var b=el('button','rpce-opt','<span class="k">'+letters[i]+'</span>'+opt);
      b.onclick=function(){ if(picked) return; picked=true;
        try{window.__rpce_pick=i;}catch(e){}   // remember pick across the answer flip
        mark(i); done(host,p,opts); };
      box.appendChild(b);
    });
    host.appendChild(box); host.appendChild(fb);
    // Answer side: replay the SAME highlighted state the tap produced (pick +
    // correct + feedback) instead of re-listing options — so the desktop's flip
    // is seamless, matching the phone. No pick recorded => just show the answer.
    if(opts&&opts.reveal){
      var pk=-1; try{ if(typeof window.__rpce_pick==='number') pk=window.__rpce_pick; }catch(e){}
      mark(pk); done(host,p,opts); }
  }

  // ---- select-multiple: pick ALL that apply, then Check --------------------
  // On reveal, done()->refBlock() shows every citation in p.cites (one per
  // relevant motion/fact), not just a single reference.
  function renderMulti(p, host, opts){
    host.appendChild(el('div','rpce-q', p.stem));
    var box=el('div','rpce-opts rpce-multi'); var fb=el('div','rpce-fb');
    var letters='ABCDEFGH', graded=false;
    // Fresh question: forget the previous card's selection (this JS context
    // persists across the desktop question->answer content swap).
    if(!(opts&&opts.reveal)){ try{window.__rpce_multi=null;}catch(e){} }
    p.options.forEach(function(opt,i){
      var b=el('button','rpce-opt','<span class="box"></span><span class="k">'+letters[i]+'</span>'+opt);
      b.onclick=function(){ if(graded) return; b.classList.toggle('sel'); };
      box.appendChild(b);
    });
    host.appendChild(box);
    function grade(){
      if(graded) return; graded=true;
      var correct=p.correct||[], btns=box.querySelectorAll('button'), ok=true, picks=[];
      for(var j=0;j<btns.length;j++){
        var isC=correct.indexOf(j)>=0, sel=btns[j].classList.contains('sel');
        if(sel) picks.push(j);
        btns[j].disabled=true; btns[j].classList.remove('sel');
        if(isC && sel){ btns[j].classList.add('ok'); btns[j].innerHTML+='<span class="mark">✓ you picked</span>'; }
        else if(isC && !sel){ btns[j].classList.add('ok'); btns[j].innerHTML+='<span class="mark">← missed</span>'; ok=false; }
        else if(sel){ btns[j].classList.add('no'); btns[j].innerHTML+='<span class="mark">✗ you picked</span>'; ok=false; }
      }
      try{window.__rpce_multi=picks;}catch(e){}   // remember picks across the answer flip
      fb.style.color=ok?'#15803d':'#be123c';
      fb.textContent=ok?'✓ Correct — you selected all and only the right ones.'
        :'✗ Not quite — the ones you picked are marked ✓/✗ and the ones you missed are marked.';
      done(host,p,opts);
    }
    // Answer side: replay the user's OWN selection graded (so they see what they
    // chose + right/wrong), not just the key. No prior selection => show the key.
    if(opts&&opts.reveal){
      var saved=null; try{ if(window.__rpce_multi && window.__rpce_multi.length!=null) saved=window.__rpce_multi; }catch(e){}
      var sel=saved!=null?saved:(p.correct||[]);
      var mbtns=box.querySelectorAll('button');
      sel.forEach(function(i){ if(mbtns[i]) mbtns[i].classList.add('sel'); });
      grade(); return;
    }
    var ctr=el('div','rpce-controls'); var chk=el('button','rpce-btn','Check answers');
    chk.onclick=grade; ctr.appendChild(chk); host.appendChild(ctr); host.appendChild(fb);
  }

  // ---- order: drag the items into precedence order (top = higher) -----------
  // All items shown at once in one reorderable list; grading happens only on
  // Submit. Reorder by dragging (pointer events -> touch + mouse) or the ▲/▼
  // buttons (accessible fallback). Positions renumber live.
  function renderOrder(p, host, opts){
    host.appendChild(el('div','rpce-q', p.prompt));
    var order=p.order;               // correct sequence, highest → lowest
    // Fresh question: forget the previous card's arrangement (this JS context
    // persists across the desktop question->answer content swap).
    if(!(opts&&opts.reveal)){ try{window.__rpce_order=null;}catch(e){} }
    host.appendChild(el('div','rpce-axis','▲ top = HIGHER precedence, bottom = LOWER'));
    var list=el('div','rpce-dest rpce-order'); host.appendChild(list);
    var fb=el('div','rpce-fb');
    var graded=false;

    function renumber(){
      var rows=list.querySelectorAll('.rpce-slot');
      for(var i=0;i<rows.length;i++) rows[i].querySelector('.n').textContent=(i+1);
    }
    function currentOrder(){
      var rows=list.querySelectorAll('.rpce-slot'), out=[];
      for(var i=0;i<rows.length;i++) out.push(rows[i].dataset.label);
      return out;
    }
    // ▲/▼ fallback: swap a row with its neighbour.
    function nudge(row,dir){
      if(graded) return;
      if(dir<0 && row.previousElementSibling) list.insertBefore(row,row.previousElementSibling);
      else if(dir>0 && row.nextElementSibling) list.insertBefore(row.nextElementSibling,row);
      renumber();
    }
    // Which row (not the one being dragged) should the dragged row sit before,
    // given the pointer's Y? null => append to end. Standard sortable logic.
    function afterRow(y){
      var els=list.querySelectorAll('.rpce-slot:not(.drag)'), best=null, bestOff=-Infinity;
      for(var i=0;i<els.length;i++){
        var box=els[i].getBoundingClientRect(), off=y-box.top-box.height/2;
        if(off<0 && off>bestOff){ bestOff=off; best=els[i]; }
      }
      return best;
    }
    function slotFrom(node){
      while(node && node!==list){ if(node.classList && node.classList.contains('rpce-slot')) return node; node=node.parentNode; }
      return null;
    }
    // Drag-to-reorder via Pointer Events. CRITICAL FIX: capture the pointer on the
    // LIST (a stable element), not on the row — moving a captured element in the
    // DOM (insertBefore) releases its capture in Chromium/QtWebEngine, which broke
    // dragging after the first move. Delegating from the list keeps pointermove
    // flowing while we physically reorder the rows. One path serves mouse
    // (desktop) + touch (Android); touch-action:none (CSS) gives us the gesture.
    // The ▲/▼ buttons remain an accessible fallback.
    var dragRow=null, startY=0, moved=false;
    list.addEventListener('pointerdown',function(ev){
      if(graded) return;
      // Let the ▲/▼ buttons handle their own taps.
      if(ev.target && ev.target.classList && ev.target.classList.contains('rpce-move')) return;
      var row=slotFrom(ev.target); if(!row) return;
      dragRow=row; moved=false; startY=ev.clientY;
      try{ list.setPointerCapture(ev.pointerId); }catch(e){}
    });
    list.addEventListener('pointermove',function(ev){
      if(!dragRow) return;
      // Small threshold so a plain tap isn't treated as a drag.
      if(!moved){ if(Math.abs(ev.clientY-startY)<4) return; moved=true; dragRow.classList.add('drag'); }
      ev.preventDefault();                               // stop text selection / scroll
      var after=afterRow(ev.clientY);
      if(after==null) list.appendChild(dragRow); else list.insertBefore(dragRow,after);
      renumber();
    });
    function endDrag(ev){
      if(!dragRow) return; dragRow.classList.remove('drag'); dragRow=null;
      try{ list.releasePointerCapture(ev.pointerId); }catch(e){}
    }
    list.addEventListener('pointerup',endDrag);
    list.addEventListener('pointercancel',endDrag);
    list.addEventListener('lostpointercapture',endDrag);

    function makeRow(label){
      var row=el('div','rpce-slot'); row.dataset.label=label;
      row.appendChild(el('span','n',''));
      row.appendChild(el('span','rpce-grip','⠿'));
      row.appendChild(el('span','lbl',label));
      var mv=el('span','rpce-moves');
      var up=el('button','rpce-move','▲'), dn=el('button','rpce-move','▼');
      up.onclick=function(){ nudge(row,-1); }; dn.onclick=function(){ nudge(row,1); };
      mv.appendChild(up); mv.appendChild(dn); row.appendChild(mv);
      return row;
    }
    function submit(){
      if(graded) return; graded=true;
      // Rows stay in the user's submitted arrangement; mark each position right
      // or wrong so the user sees THEIR OWN answer graded, not just the key.
      var got=currentOrder(), rows=list.querySelectorAll('.rpce-slot'), allRight=true;
      try{window.__rpce_order=got.slice();}catch(e){}   // remember across the answer flip
      for(var i=0;i<rows.length;i++){
        var mv=rows[i].querySelector('.rpce-moves'), mk=el('span','rpce-omark');
        if(got[i]===order[i]){ rows[i].classList.add('ok'); mk.style.color='#15803d';
          mk.textContent='✓'; }
        else { rows[i].classList.add('no'); mk.style.color='#be123c'; allRight=false;
          // Show where this item actually belongs (its rank in the key).
          mk.textContent='✗ goes #'+(order.indexOf(got[i])+1); }
        rows[i].insertBefore(mk,mv);
        var mb=rows[i].querySelectorAll('.rpce-move');
        for(var k=0;k<mb.length;k++) mb[k].disabled=true;   // stop nudging
      }
      fb.style.color=allRight?'#15803d':'#be123c';
      fb.innerHTML=allRight?'✓ Correct — your order matches.'
        :'✗ Not quite — your order is graded above. The correct order (highest → lowest) is: <b>'+order.join(' → ')+'</b>';
      done(host,p,opts);
    }

    if(opts&&opts.reveal){
      // Answer side: rebuild the user's OWN submitted order and grade it, so they
      // see what they arranged + which rows were wrong. No prior submit => show key.
      var saved=null; try{ if(window.__rpce_order && window.__rpce_order.length) saved=window.__rpce_order; }catch(e){}
      (saved||order).forEach(function(label){ list.appendChild(makeRow(label)); });
      renumber(); host.appendChild(fb); submit(); return;
    }
    shuffle(p.order.slice()).forEach(function(label){ list.appendChild(makeRow(label)); });
    renumber();
    var ctr=el('div','rpce-controls'); var sub=el('button','rpce-btn','Submit');
    sub.onclick=submit; ctr.appendChild(sub); host.appendChild(ctr);
    host.appendChild(fb);
  }

  window.RPCE = { render: function(payload, host, opts){
    opts=opts||{};
    try {
      if(payload.kind==='mcq') return renderMcq(payload, host, opts);
      if(payload.kind==='multi') return renderMulti(payload, host, opts);
      if(payload.kind==='order') return renderOrder(payload, host, opts);
      return renderCloze(payload, host, opts);
    } catch(e){ host.textContent='render error: '+e; }
  }};
})();

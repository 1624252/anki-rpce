# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""The shared interactive question renderer (one source for both platforms).

The desktop reviewer and the phone are both WebViews, so the same JS renders a
card identically on each. This module is the single source: the desktop embeds
``RENDER_CSS`` + ``RENDER_JS`` in the card HTML it returns, and the starter-deck
export writes them to ``mobile/app/app/src/main/assets/rpce_render.js`` for the
phone. Keeping it here (not copied by hand) is what keeps the two in sync.

``RPCE.render(payload, host, opts)`` renders one question into ``host``:

- payload.kind ``"cloze"``  — text with ``[[0]]`` blanks; each blank is tappable
  to reveal (with a hint); a "Reveal all" control reveals the rest. Calls
  ``opts.onComplete`` once every blank is revealed.
- payload.kind ``"mcq"``    — tappable options (works on desktop click + phone
  tap); marks right/wrong; keeps the stem on screen. Completes on first pick.
- payload.kind ``"order"``  — tap the items in order of precedence; marks the
  sequence and shows the correct order. Completes when all are placed.

Every answer reveals the RONR (12th ed.) citation + verbatim quote (never in the
question). ``opts.reveal`` renders straight into the fully-answered state (used
for the desktop reviewer's answer side).
"""

from __future__ import annotations

RENDER_CSS = """
.rpce-q{font-size:19px;line-height:1.6;color:#0a1f44}
.rpce-hint{font-size:13px;color:#35548c;font-style:italic}
.rpce-blank{display:inline-block;min-width:64px;text-align:center;border:none;
  border-bottom:2px dashed #1d4ed8;background:rgba(37,99,235,.08);color:#1d4ed8;
  border-radius:6px 6px 0 0;padding:1px 8px;margin:0 2px;font:inherit;font-weight:700;cursor:pointer}
.rpce-blank.revealed{border-bottom-color:#15803d;background:rgba(21,128,61,.12);
  color:#15803d;cursor:default}
.rpce-controls{margin-top:16px;display:flex;gap:10px;flex-wrap:wrap}
.rpce-btn{border:1px solid #caddf7;background:#f4f8ff;color:#1d4ed8;border-radius:12px;
  padding:10px 16px;font:inherit;font-weight:700;cursor:pointer}
.rpce-opts{display:flex;flex-direction:column;gap:10px;margin-top:16px}
.rpce-opt{text-align:left;font-size:17px;line-height:1.4;padding:13px 16px;border-radius:12px;
  border:1px solid #caddf7;background:#f4f8ff;color:#0a1f44;cursor:pointer;font:inherit}
.rpce-opt .k{font-weight:800;color:#35548c;margin-right:8px}
.rpce-opt .mark{float:right;font-weight:800}
.rpce-opt.ok{background:rgba(21,128,61,.14);border-color:#15803d;color:#14532d;font-weight:700}
.rpce-opt.no{background:rgba(190,18,60,.10);border-color:#be123c;color:#7f1d1d;font-weight:700}
.rpce-opt:disabled{cursor:default}
.rpce-chips{display:flex;flex-wrap:wrap;gap:10px;margin-top:16px}
.rpce-chip{padding:12px 16px;border-radius:12px;border:1px solid #caddf7;background:#f4f8ff;
  color:#0a1f44;cursor:pointer;font:inherit;font-size:16px;position:relative}
.rpce-chip .pos{display:inline-block;min-width:22px;height:22px;line-height:22px;text-align:center;
  border-radius:50%;background:#1d4ed8;color:#fff;font-size:13px;font-weight:800;margin-right:8px}
.rpce-chip.ok{background:rgba(21,128,61,.14);border-color:#15803d}
.rpce-chip.no{background:rgba(190,18,60,.10);border-color:#be123c}
.rpce-fb{margin-top:14px;font-size:16px;font-weight:700;min-height:20px}
.rpce-answer{margin-top:14px;font-size:17px;line-height:1.5;color:#0a1f44}
.rpce-ref{margin-top:16px;padding:12px 15px;border-left:4px solid #2f6fed;background:#eef4ff;
  border-radius:10px;text-align:left}
.rpce-cite{font-weight:700;color:#1b3faa;font-size:15px}
.rpce-quote{margin-top:6px;font-style:italic;color:#0a1f44;font-size:16px}
/* multi-select */
.rpce-opt.sel{background:#dbeafe;border-color:#1d4ed8;font-weight:700}
.rpce-opt .box{display:inline-block;width:18px;height:18px;border:2px solid #94a3b8;border-radius:5px;margin-right:10px;vertical-align:-3px}
.rpce-opt.sel .box{background:#1d4ed8;border-color:#1d4ed8}
/* ordering (vertical; top = higher precedence) */
.rpce-axis{font-size:12px;font-weight:700;color:#64748b;margin:14px 0 6px}
.rpce-dest{display:flex;flex-direction:column;gap:8px;min-height:8px;
  border-left:3px solid #caddf7;padding-left:12px;margin:6px 0}
.rpce-slot{display:flex;align-items:center;gap:10px;padding:11px 14px;border-radius:12px;
  border:1px solid #caddf7;background:#f4f8ff;color:#0a1f44;font-size:16px}
.rpce-slot .n{min-width:24px;height:24px;line-height:24px;text-align:center;border-radius:50%;
  background:#1d4ed8;color:#fff;font-size:13px;font-weight:800}
.rpce-slot.ok{background:rgba(21,128,61,.14);border-color:#15803d}
.rpce-slot.no{background:rgba(190,18,60,.10);border-color:#be123c}
.rpce-src .rpce-chip.used{opacity:.35;pointer-events:none}
"""

RENDER_JS = r"""
(function(){
  function el(tag, cls, html){ var e=document.createElement(tag);
    if(cls) e.className=cls; if(html!=null) e.innerHTML=html; return e; }
  function refBlock(p){ if(!p.cite) return null;
    var d=el('div','rpce-ref');
    d.appendChild(el('div','rpce-cite','RONR (12th ed.) §'+p.cite));
    if(p.quote) d.appendChild(el('div','rpce-quote','“'+p.quote+'”'));
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
        span.textContent=b.h?('? '+b.h):'?';
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
    if(p.hint) host.appendChild(el('div','rpce-hint', 'Hint: '+p.hint));
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
  function renderMulti(p, host, opts){
    host.appendChild(el('div','rpce-q', p.stem));
    var box=el('div','rpce-opts rpce-multi'); var fb=el('div','rpce-fb');
    var letters='ABCDEFGH', graded=false;
    p.options.forEach(function(opt,i){
      var b=el('button','rpce-opt','<span class="box"></span><span class="k">'+letters[i]+'</span>'+opt);
      b.onclick=function(){ if(graded) return; b.classList.toggle('sel'); };
      box.appendChild(b);
    });
    host.appendChild(box);
    function grade(){
      if(graded) return; graded=true;
      var correct=p.correct||[], btns=box.querySelectorAll('button'), ok=true;
      for(var j=0;j<btns.length;j++){
        var isC=correct.indexOf(j)>=0, sel=btns[j].classList.contains('sel');
        btns[j].disabled=true; btns[j].classList.remove('sel');
        if(isC){ btns[j].classList.add('ok'); btns[j].innerHTML+='<span class="mark">'+(sel?'✓':'← should be selected')+'</span>'; if(!sel) ok=false; }
        else if(sel){ btns[j].classList.add('no'); btns[j].innerHTML+='<span class="mark">✗</span>'; ok=false; }
      }
      fb.style.color=ok?'#15803d':'#be123c';
      fb.textContent=ok?'✓ Correct — all and only the right ones.':'✗ Not quite — the correct set is highlighted.';
      done(host,p,opts);
    }
    if(opts&&opts.reveal){ (p.correct||[]).forEach(function(i){ box.querySelectorAll('button')[i].classList.add('sel'); }); grade(); return; }
    var ctr=el('div','rpce-controls'); var chk=el('button','rpce-btn','Check answers');
    chk.onclick=grade; ctr.appendChild(chk); host.appendChild(ctr); host.appendChild(fb);
  }

  // ---- order: tap items into precedence order (top = higher) ----------------
  function renderOrder(p, host, opts){
    host.appendChild(el('div','rpce-q', p.prompt));
    var order=p.order;               // correct sequence, highest → lowest
    var display=(opts&&opts.reveal)?order.slice():shuffle(order);
    host.appendChild(el('div','rpce-axis','▲ Tap in order — top = HIGHER precedence, bottom = LOWER'));
    var dest=el('div','rpce-dest'); host.appendChild(dest);
    var src=el('div','rpce-chips rpce-src'); host.appendChild(src);
    var fb=el('div','rpce-fb'); host.appendChild(fb);
    var picked=[], chips={};
    function evaluate(){
      var allRight=true;
      dest.querySelectorAll('.rpce-slot').forEach(function(slot,pos){
        if(order[pos]===picked[pos]){ slot.classList.add('ok'); }
        else { slot.classList.add('no'); allRight=false; }
      });
      fb.style.color=allRight?'#15803d':'#be123c';
      fb.innerHTML=allRight?'✓ Correct order.'
        :'✗ Not quite. Correct (highest → lowest): <b>'+order.join(' → ')+'</b>';
      done(host,p,opts);
    }
    function place(label){
      picked.push(label);
      var slot=el('div','rpce-slot','<span class="n">'+picked.length+'</span>'+label);
      dest.appendChild(slot);
      chips[label].classList.add('used');
      if(picked.length===order.length) evaluate();
    }
    display.forEach(function(label){
      var chip=el('button','rpce-chip',label); chips[label]=chip;
      chip.onclick=function(){ if(chips[label].classList.contains('used')) return; place(label); };
      src.appendChild(chip);
    });
    if(opts&&opts.reveal){ order.forEach(place); }
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
"""


def decode_payload_js(var_from_attr: str) -> str:
    """JS snippet that decodes a base64 payload attribute into an object."""
    return f"JSON.parse(decodeURIComponent(escape(atob({var_from_attr}))))"

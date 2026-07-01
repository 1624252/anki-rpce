/* Generated from anki.rpce.render_js — do not edit by hand. */
var RPCE_CSS = "\n.rpce-q{font-size:19px;line-height:1.6;color:#0a1f44}\n.rpce-hint{font-size:13px;color:#35548c;font-style:italic}\n.rpce-blank{display:inline-block;min-width:64px;text-align:center;border:none;\n  border-bottom:2px dashed #1d4ed8;background:rgba(37,99,235,.08);color:#1d4ed8;\n  border-radius:6px 6px 0 0;padding:1px 8px;margin:0 2px;font:inherit;font-weight:700;cursor:pointer}\n.rpce-blank.revealed{border-bottom-color:#15803d;background:rgba(21,128,61,.12);\n  color:#15803d;cursor:default}\n.rpce-controls{margin-top:16px;display:flex;gap:10px;flex-wrap:wrap}\n.rpce-btn{border:1px solid #caddf7;background:#f4f8ff;color:#1d4ed8;border-radius:12px;\n  padding:10px 16px;font:inherit;font-weight:700;cursor:pointer}\n.rpce-opts{display:flex;flex-direction:column;gap:10px;margin-top:16px}\n.rpce-opt{text-align:left;font-size:17px;line-height:1.4;padding:13px 16px;border-radius:12px;\n  border:1px solid #caddf7;background:#f4f8ff;color:#0a1f44;cursor:pointer;font:inherit}\n.rpce-opt .k{font-weight:800;color:#35548c;margin-right:8px}\n.rpce-opt .mark{float:right;font-weight:800}\n.rpce-opt.ok{background:rgba(21,128,61,.14);border-color:#15803d;color:#14532d;font-weight:700}\n.rpce-opt.no{background:rgba(190,18,60,.10);border-color:#be123c;color:#7f1d1d;font-weight:700}\n.rpce-opt:disabled{cursor:default}\n.rpce-chips{display:flex;flex-wrap:wrap;gap:10px;margin-top:16px}\n.rpce-chip{padding:12px 16px;border-radius:12px;border:1px solid #caddf7;background:#f4f8ff;\n  color:#0a1f44;cursor:pointer;font:inherit;font-size:16px;position:relative}\n.rpce-chip .pos{display:inline-block;min-width:22px;height:22px;line-height:22px;text-align:center;\n  border-radius:50%;background:#1d4ed8;color:#fff;font-size:13px;font-weight:800;margin-right:8px}\n.rpce-chip.ok{background:rgba(21,128,61,.14);border-color:#15803d}\n.rpce-chip.no{background:rgba(190,18,60,.10);border-color:#be123c}\n.rpce-fb{margin-top:14px;font-size:16px;font-weight:700;min-height:20px}\n.rpce-answer{margin-top:14px;font-size:17px;line-height:1.5;color:#0a1f44}\n.rpce-ref{margin-top:16px;padding:12px 15px;border-left:4px solid #2f6fed;background:#eef4ff;\n  border-radius:10px;text-align:left}\n.rpce-cite{font-weight:700;color:#1b3faa;font-size:15px}\n.rpce-quote{margin-top:6px;font-style:italic;color:#0a1f44;font-size:16px}\n";

(function(){
  function el(tag, cls, html){ var e=document.createElement(tag);
    if(cls) e.className=cls; if(html!=null) e.innerHTML=html; return e; }
  function refBlock(p){ if(!p.cite) return null;
    var d=el('div','rpce-ref');
    d.appendChild(el('div','rpce-cite','RONR (12th ed.) '+p.cite));
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
    var box=el('div','rpce-opts'); var fb=el('div','rpce-fb');
    var letters='ABCDEFGH', picked=false;
    p.options.forEach(function(opt,i){
      var b=el('button','rpce-opt','<span class="k">'+letters[i]+'</span>'+opt);
      b.onclick=function(){ if(picked) return; picked=true;
        var btns=box.querySelectorAll('button');
        for(var j=0;j<btns.length;j++){ btns[j].disabled=true;
          if(j===p.answer){ btns[j].classList.add('ok'); btns[j].innerHTML+='<span class="mark">✓</span>'; }
          else if(j===i){ btns[j].classList.add('no'); btns[j].innerHTML+='<span class="mark">✗</span>'; } }
        fb.style.color=(i===p.answer)?'#15803d':'#be123c';
        fb.textContent=(i===p.answer)?'✓ Correct':'✗ Not quite — the correct answer is highlighted.';
        done(host,p,opts); };
      box.appendChild(b);
    });
    host.appendChild(box); host.appendChild(fb);
    if(opts&&opts.reveal){ var btns=box.querySelectorAll('button');
      for(var j=0;j<btns.length;j++){ btns[j].disabled=true;
        if(j===p.answer){ btns[j].classList.add('ok'); btns[j].innerHTML+='<span class="mark">✓</span>'; } }
      done(host,p,opts); }
  }

  // ---- order: tap items into the correct sequence ---------------------------
  function renderOrder(p, host, opts){
    host.appendChild(el('div','rpce-q', p.prompt));
    var order=p.order;               // correct sequence of labels
    var display = (opts&&opts.reveal) ? order.slice() : shuffle(order);
    var box=el('div','rpce-chips'); var fb=el('div','rpce-fb');
    var picked=[], chips={};
    function evaluate(){
      var allRight=true;
      picked.forEach(function(label,pos){
        var chip=chips[label];
        if(order[pos]===label){ chip.classList.add('ok'); }
        else { chip.classList.add('no'); allRight=false; }
      });
      fb.style.color=allRight?'#15803d':'#be123c';
      fb.innerHTML=(allRight?'✓ Correct order.':'✗ Not quite. Correct order (highest → lowest): ')
        + (allRight?'':'<b>'+order.join(' → ')+'</b>');
      done(host,p,opts);
    }
    display.forEach(function(label){
      var chip=el('button','rpce-chip','<span class="pos" style="display:none"></span>'+label);
      chips[label]=chip;
      chip.onclick=function(){ if(chip.dataset.done||picked.indexOf(label)>=0) return;
        picked.push(label); var badge=chip.querySelector('.pos');
        badge.style.display='inline-block'; badge.textContent=picked.length;
        if(picked.length===order.length) evaluate(); };
      box.appendChild(chip);
    });
    host.appendChild(box); host.appendChild(fb);
    if(opts&&opts.reveal){ order.forEach(function(label,pos){ var chip=chips[label];
      chip.dataset.done='1'; var badge=chip.querySelector('.pos');
      badge.style.display='inline-block'; badge.textContent=pos+1; chip.classList.add('ok'); });
      done(host,p,opts); }
  }

  window.RPCE = { render: function(payload, host, opts){
    opts=opts||{};
    try {
      if(payload.kind==='mcq') return renderMcq(payload, host, opts);
      if(payload.kind==='order') return renderOrder(payload, host, opts);
      return renderCloze(payload, host, opts);
    } catch(e){ host.textContent='render error: '+e; }
  }};
})();

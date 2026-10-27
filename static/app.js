/* MakGeography front-end */
(() => {
  "use strict";
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];

  const EXAMPLES = [
    ["CP1", "Explain the formation of a tsunami and how Hong Kong coastal management reduces its impact."],
    ["CP2", "Compare the characteristics of a destructive and a constructive plate boundary, with examples."],
    ["CP3", "Why is Silicon Valley an example of a footloose industry? List the location factors in order of importance."],
    ["CP4", "What urban problems does Hong Kong face, and which planning strategies address them?"],
    ["CP5", "Explain the causes of famine in the Sahel region and evaluate the solutions used."],
    ["CP6", "Why has the Amazon rainforest been called a 'disappearing green canopy'? Discuss the causes."],
    ["CP7", "What are the causes and effects of global warming, and what can be done about it?"],
    ["EP1", "Describe the weathering processes that shape Hong Kong's landscape and their impacts."],
    ["CP3", "What is deindustrialisation, and what caused it in the UK and Hong Kong?"],
  ];

  // ---------------------------------------------------------------- tabs
  $$("nav.tabs button").forEach((btn) => {
    btn.addEventListener("click", () => {
      $$("nav.tabs button").forEach((b) => b.classList.remove("active"));
      $$(".panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      $("#panel-" + btn.dataset.panel).classList.add("active");
      if (btn.dataset.panel === "notes") loadNotes();
      if (btn.dataset.panel === "mc") loadMcStats();
      if (btn.dataset.panel === "news") loadNews();
    });
  });

  // ---------------------------------------------------------------- kb status
  async function loadStatus() {
    try {
      const r = await fetch("/api/kb/status");
      if (!r.ok) return;
      const d = await r.json();
      $("#kbChunks").textContent = d.chunks ?? "–";
      $("#kbDocs").textContent = `${d.docs} notes · built ${(d.built_at || "").slice(0, 10)}`;
      const opts = (d.topics || []).map((t) => `<option value="${t}">${t}</option>`).join("");
      $("#topicSel").insertAdjacentHTML("beforeend", opts);
      $("#notesTopic").insertAdjacentHTML("beforeend", opts);
      $("#mcTopic").insertAdjacentHTML("beforeend", opts);
      $("#newsTopic").insertAdjacentHTML("beforeend", opts);
    } catch (e) { /* offline indicator is enough */ }
  }
  loadStatus();

  // ---------------------------------------------------------------- examples
  $("#examples").innerHTML = EXAMPLES.map(
    ([tag, q]) => `<button data-q="${q.replace(/"/g, "&quot;")}"><span class="badge">${tag}</span> ${q.slice(0, 62)}…</button>`
  ).join("");
  $("#examples").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-q]");
    if (!b) return;
    $("#q").value = b.dataset.q;
    $("#chatForm").requestSubmit();
  });

  // ---------------------------------------------------------------- chat
  const log = $("#chatLog");
  const history = [];

  function esc(s) {
    return String(s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  // Minimal, safe markdown: bold, italics, inline code, bullets, headings,
  // numbered lists and pipe tables.
  //
  // Tables matter here because the geography notes are full of comparison
  // tables (plate boundaries, layer depths, landform processes). Rendered as
  // raw pipes they are unreadable.
  function md(s) {
    let t = esc(s);

    // Fenced code first, so nothing inside it gets rewritten.
    const fences = [];
    t = t.replace(/```([\s\S]*?)```/g, (m, body) => {
      fences.push(body);
      return `\u0000FENCE${fences.length - 1}\u0000`;
    });

    // Pipe tables: a header row, a |---|---| separator, then body rows.
    t = t.replace(/(^\s*\|[^\n]*\|\s*\n\s*\|\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|\s*\n)((?:\s*\|[^\n]*\|\s*\n?)*)/gm,
      (m, head, body) => {
        const rows = (head + body).trim().split("\n").map((r) =>
          r.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim())
        );
        const [h, ...body2] = rows;
        const thead = "<tr>" + h.map((c) => `<th>${c}</th>`).join("") + "</tr>";
        const tbody = body2
          .filter((r) => !/^[:\-\s]+$/.test(r.join("")))
          .map((r) => "<tr>" + r.map((c) => `<td>${c}</td>`).join("") + "</tr>")
          .join("");
        return `<table><thead>${thead}</thead><tbody>${tbody}</tbody></table>\n`;
      });

    t = t.replace(/`([^`]+)`/g, "<code>$1</code>");
    t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    t = t.replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>");
    t = t.replace(/^####\s+(.+)$/gm, "<h5>$1</h5>");
    t = t.replace(/^###\s+(.+)$/gm, "<h4>$1</h4>");
    t = t.replace(/^##\s+(.+)$/gm, "<h3>$1</h3>");
    t = t.replace(/^#\s+(.+)$/gm, "<h3>$1</h3>");
    t = t.replace(/^[-*]\s+(.+)$/gm, "<li>$1</li>");
    t = t.replace(/^(\d+)\.\s+(.+)$/gm, "<li>$2</li>");
    // Wrap runs of list items.
    t = t.replace(/(<li>[\s\S]*?<\/li>)(?!\s*<li>)/g, "<ul>$1</ul>");
    // Line breaks inside a paragraph.
    t = t.replace(/\n{2,}/g, "</p><p>");
    t = t.replace(/\n/g, "<br>");

    // Put the fences back.
    t = t.replace(/\u0000FENCE(\d+)\u0000/g, (m, i) => `<pre>${fences[i]}</pre>`);
    return t;
  }

  function addUser(text) {
    const d = document.createElement("div");
    d.className = "msg user";
    d.textContent = text;
    log.appendChild(d);
    log.scrollTop = log.scrollHeight;
  }

  function addBot(html, sources) {
    const d = document.createElement("div");
    d.className = "msg bot";
    let src = "";
    if (sources && sources.length) {
      src = `<div class="sources"><b>From these notes</b>` +
        sources.map((s) =>
          `<span class="source-chip" title="${esc(s.path)}">${esc(s.title)}${s.heading ? " · " + esc(s.heading) : ""}</span>`
        ).join("") + `</div>`;
    }
    d.innerHTML = `<div class="body">${html}</div>${src}`;
    log.appendChild(d);
    log.scrollTop = log.scrollHeight;
    return d;
  }

  $("#chatForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const q = $("#q").value.trim();
    if (!q) return;
    $("#q").value = "";
    addUser(q);
    const pending = addBot('<span class="loading">Looking in the notes…</span>', null);
    const btn = $("#sendBtn");
    btn.disabled = true;
    try {
      const r = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: q,
          topic: $("#topicSel").value === "ALL" ? null : $("#topicSel").value,
          history,
        }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || d.error || "Request failed");
      if (d.error) { pending.querySelector(".body").innerHTML = `<span class="loading">${esc(d.error)}</span>`; }
      else {
        pending.querySelector(".body").innerHTML = md(d.answer);
        if (d.sources) pending.insertAdjacentHTML("beforeend",
          `<div class="sources"><b>From these notes</b>` +
          d.sources.map((s) => `<span class="source-chip" title="${esc(s.path)}">${esc(s.title)}${s.heading ? " · " + esc(s.heading) : ""}</span>`).join("") +
          `</div>`);
        history.push({ role: "user", content: q });
        history.push({ role: "assistant", content: d.answer });
      }
    } catch (err) {
      pending.querySelector(".body").innerHTML = `<span class="loading">Could not reach the assistant: ${esc(err.message)}</span>`;
    } finally {
      btn.disabled = false;
      log.scrollTop = log.scrollHeight;
    }
  });

  $("#q").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("#chatForm").requestSubmit(); }
  });

  // ---------------------------------------------------------------- notes
  let notesCache = null;
  async function loadNotes() {
    if (notesCache) return renderNotes();
    $("#notesList").innerHTML = '<div class="empty">Loading notes…</div>';
    const r = await fetch("/api/notes");
    const d = await r.json();
    notesCache = d.electives || [];
    renderNotes();
  }

  function renderNotes() {
    const topic = $("#notesTopic").value;
    const q = $("#notesSearch").value.toLowerCase().trim();
    let electives = notesCache;
    if (topic !== "ALL") electives = electives.filter((e) => e.code === topic);

    // filter at leaf level, keeping the elective/sub-question shell
    const out = [];
    electives.forEach((el) => {
      const subs = [];
      el.subquestions.forEach((sq) => {
        const leaves = sq.leaves.filter((lf) => {
          if (!q) return true;
          const blob = (lf.title + " " + lf.summary + " " +
            lf.content.map((c) => c.title + " " + c.heading + " " + c.text).join(" ")).toLowerCase();
          return blob.includes(q);
        });
        if (leaves.length) subs.push({ ...sq, leaves });
      });
      if (subs.length) out.push({ ...el, subquestions: subs });
    });

    const nLeaves = out.reduce((n, e) => n + e.subquestions.reduce((m, s) => m + s.leaves.length, 0), 0);
    $("#notesCount").textContent = `${out.length} elective${out.length === 1 ? "" : "s"} · ${nLeaves} sub-topics`;
    if (!out.length) { $("#notesList").innerHTML = '<div class="empty">No notes match.</div>'; return; }

    $("#notesList").innerHTML = out.map((el, i) => `
      <div class="elective">
        <h3 class="elective-title"><span class="badge">${esc(el.code)}</span> ${esc(el.title)}</h3>
        ${el.module ? `<p class="elective-module">${esc(el.module)}</p>` : ""}
        ${el.subquestions.map((sq) => `
          <div class="subq">
            <h4 class="subq-title">${esc(sq.number)}. ${esc(sq.title)}</h4>
            ${sq.leaves.map((lf) => `
              <details class="note"${i === 0 && lf.content.length ? " open" : ""}>
                <summary><span>${esc(lf.title)}</span>
                  <span class="badge${lf.content.length ? "" : " warn"}">${lf.content.length ? lf.content.length + " note" + (lf.content.length === 1 ? "" : "s") : "no note yet"}</span>
                </summary>
                <div class="body">
                  <p class="leaf-summary">${esc(lf.summary)}</p>
                  ${lf.content.length ? lf.content.map((c) => `
                    <h4>${esc(c.title)}${c.heading ? " — " + esc(c.heading) : ""}</h4>
                    <div class="note-text">${md(c.text)}</div>`).join("")
                  : `<p class="hint-small">This sub-topic has no dedicated note in the MakGeography vault yet.</p>`}
                </div>
              </details>`).join("")}
          </div>`).join("")}
      </div>`).join("");
  }
  $("#notesTopic").addEventListener("change", renderNotes);
  $("#notesSearch").addEventListener("input", renderNotes);

  // ---------------------------------------------------------------- mc
  async function loadMcStats() {
    const r = await fetch("/api/mc?limit=1000");
    const d = await r.json();
    const st = localStorage.getItem("makgeo_mc_stats");
    const s = st ? JSON.parse(st) : { asked: 0, correct: 0, byTopic: {} };
    $("#mcStats").innerHTML = `
      <div class="card"><div class="stat">${s.asked}</div><p class="hint-small">questions attempted</p></div>
      <div class="card"><div class="stat">${s.asked ? Math.round((s.correct / s.asked) * 100) : 0}%</div><p class="hint-small">accuracy</p></div>
      <div class="card"><div class="stat">${s.asked ? s.asked - s.correct : 0}</div><p class="hint-small">wrong — needs drilling</p></div>`;
    const weakCount = Object.values(s.bySub || {}).filter((v) => v.asked && v.wrong).length;
    if (weakCount) {
      $("#mcStats").insertAdjacentHTML("beforeend",
        `<div class="card"><div class="stat">${weakCount}</div><p class="hint-small">weak sub-topics</p></div>`);
    }
  }

  function saveStats(s) { localStorage.setItem("makgeo_mc_stats", JSON.stringify(s)); }

  // Render a set of questions and wire up the answering.
  function renderDrill(qs) {
    if (!qs.length) {
      $("#mcList").innerHTML = '<div class="empty">No questions available for that topic yet.</div>';
      return;
    }
    let stats = JSON.parse(localStorage.getItem("makgeo_mc_stats") || '{"asked":0,"correct":0,"byTopic":{}}');

    $("#mcList").innerHTML = qs.map((q, i) => `
      <div class="mc-q" data-i="${i}">
        ${q.official ? `<div class="mc-official">Official HKDSE exam question &middot; ${esc(q.source || "")}</div>` : ""}
        ${q.slide_image ? `<details class="mc-slide"><summary>Show the original HKEAA slide</summary><img src="/slide-crops/${esc(q.slide_image.split("/").pop())}" alt="HKEAA examination briefing slide for this question" loading="lazy"><span class="credit">Source: HKEAA examination briefing. &copy; HKEAA.</span></details>` : ""}
        <div class="stem">${md(q.stem)}</div>
        <div class="mc-opts">${q.options.map((o, j) =>
          `<button class="mc-opt" data-k="${String.fromCharCode(65 + j)}"><span class="k">${String.fromCharCode(65 + j)}</span><span>${esc(o)}</span></button>`).join("")}
        </div>
        <div class="mc-fb" style="display:none"></div>
      </div>`).join("");

    $("#mcList").addEventListener("click", handler, { once: true });
    function handler(ev) {
      const opt = ev.target.closest(".mc-opt");
      if (!opt) return;
      const box = opt.closest(".mc-q");
      const q = qs[+box.dataset.i];
      const correct = q.answer.toUpperCase();
      const picked = opt.dataset.k;
      const fb = box.querySelector(".mc-fb");
      $$(".mc-opt", box).forEach((b) => {
        b.disabled = true;
        if (b.dataset.k === correct) b.classList.add("correct");
        else if (b === opt) b.classList.add("wrong");
      });
      fb.style.display = "block";
      fb.innerHTML = `<span class="ans">Answer: ${correct}</span>` +
        (q.explanation ? `<div class="why">${esc(q.explanation)}</div>` : "");
      stats.asked++;
      if (picked === correct) stats.correct++;
      // Track by sub-topic where possible, because "drill the similar topic"
      // is only useful at that grain: CP3 has six sub-topics and a student
      // weak on "Silicon Valley" does not need more iron-and-steel questions.
      const t = q.topics?.[0] || "General";
      stats.byTopic[t] = stats.byTopic[t] || { asked: 0, wrong: 0 };
      stats.byTopic[t].asked++;
      if (picked !== correct) stats.byTopic[t].wrong++;
      const st = q.subtopic || "";
      if (st) {
        stats.bySub = stats.bySub || {};
        stats.bySub[st] = stats.bySub[st] || { asked: 0, wrong: 0, title: q.subtopic_title || "", topic: t };
        stats.bySub[st].asked++;
        if (picked !== correct) stats.bySub[st].wrong++;
      }
      // Remember which questions were wrong, so they can come back around.
      stats.wrongIds = stats.wrongIds || [];
      if (picked !== correct && q.id) {
        if (!stats.wrongIds.includes(q.id)) stats.wrongIds.push(q.id);
      }
      saveStats(stats);
      loadMcStats();   // refresh the counters so the student sees the update
      $("#mcList").removeEventListener("click", handler);
      $("#mcList").addEventListener("click", handler, { once: true });
    }
  }

  $("#mcStart").addEventListener("click", async () => {
    const topic = $("#mcTopic").value;
    const n = $("#mcCount").value;
    const r = await fetch(`/api/mc?limit=${n}${topic === "ALL" ? "" : "&topic=" + topic}`);
    const d = await r.json();
    renderDrill(d.questions || []);
  });

  // Drill the topics the student is weakest on. Questions come back from the
  // server's weakest sub-topics first, so the round targets the gaps.
  $("#mcWeak").addEventListener("click", async () => {
    const s = JSON.parse(localStorage.getItem("makgeo_mc_stats") || "{}");
    const weak = Object.entries(s.bySub || {})
      .filter(([, v]) => v.asked >= 1 && v.wrong > 0)
      .sort((a, b) => (b[1].wrong / b[1].asked) - (a[1].wrong / a[1].asked));
    if (!weak.length) {
      $("#mcList").innerHTML =
        '<div class="empty">No weak topics yet. Answer a round first, then come back — anything you get wrong becomes a weak topic.</div>';
      return;
    }
    const n = Number($("#mcCount").value) || 10;
    const wanted = weak.map(([k]) => k);
    const r = await fetch(`/api/mc?limit=400`);
    const d = await r.json();
    const all = d.questions || [];
    const picked = [];
    for (const sub of wanted) {
      const pool = all.filter((q) => q.subtopic === sub);
      // Put the questions the student already got wrong first.
      pool.sort((a, b) => (s.wrongIds || []).includes(b.id) - (s.wrongIds || []).includes(a.id));
      picked.push(...pool);
    }
    if (!picked.length) {
      $("#mcList").innerHTML = '<div class="empty">No questions available for those topics yet.</div>';
      return;
    }
    renderDrill(picked.slice(0, n));
    const label = weak.slice(0, 4).map(([k, v]) => v.title || k).join(", ");
    $("#mcList").insertAdjacentHTML("afterbegin",
      `<p class="hint-small" style="margin-bottom:10px">Targeting your weak topics: ${esc(label)}</p>`);
  });

  $("#mcReport").addEventListener("click", async () => {
    const s = JSON.parse(localStorage.getItem("makgeo_mc_stats") || '{"asked":0,"correct":0,"byTopic":{}}');
    const rows = Object.entries(s.byTopic || {})
      .map(([t, v]) => ({ t, pct: v.asked ? Math.round((v.wrong / v.asked) * 100) : 0, ...v }))
      .filter((x) => x.asked)
      .sort((a, b) => b.pct - a.pct);
    if (!rows.length) { $("#mcList").innerHTML = '<div class="empty">No attempts recorded yet. Start a drilling round first.</div>'; return; }
    $("#mcList").innerHTML = `<div class="card"><h3 style="margin-bottom:12px">Mistake report — drill the red topics</h3>` +
      rows.map((x) => `
        <div style="margin-bottom:12px">
          <div style="display:flex;justify-content:space-between;font-size:.92rem">
            <b>${esc(x.t)}</b><span>${x.wrong} wrong of ${x.asked} (${x.pct}%)</span>
          </div>
          <div style="height:8px;background:#eef2f4;border-radius:999px;margin-top:5px;overflow:hidden">
            <div style="height:100%;width:${x.pct}%;background:${x.pct > 40 ? "#b42318" : x.pct > 20 ? "#b4531a" : "#0f7b6c"}"></div>
          </div>
        </div>`).join("") +
      `<p class="hint-small">Your report is stored in this browser only. Topics over 40% wrong are flagged red — drill those first.</p></div>`;

    // Sub-topic breakdown: the grain at which "drill the similar topic" works.
    const subs = Object.entries(s.bySub || {})
      .filter(([, v]) => v.asked)
      .sort((a, b) => (b[1].wrong / b[1].asked) - (a[1].wrong / a[1].asked));
    if (subs.length) {
      $("#mcList").insertAdjacentHTML("beforeend",
        `<h3 style="margin:22px 0 12px">By sub-topic</h3>` +
        subs.map(([k, v]) => {
          const pct = Math.round((v.wrong / v.asked) * 100);
          const col = pct > 40 ? "#b42318" : pct > 20 ? "#b4531a" : "#0f7b6c";
          return `<div style="margin-bottom:10px">
            <div style="display:flex;justify-content:space-between;font-size:.88rem;gap:10px">
              <b>${esc(v.title || k)}</b>
              <span style="white-space:nowrap">${v.wrong} wrong of ${v.asked} (${pct}%)</span>
            </div>
            <div style="height:7px;background:#eef2f4;border-radius:999px;margin-top:4px;overflow:hidden">
              <div style="height:100%;width:${pct}%;background:${col}"></div>
            </div>
          </div>`;
        }).join(""));
    }
  });

  // ---------------------------------------------------------------- news
  async function loadNews() {
    $("#newsList").innerHTML = '<div class="empty">Loading news…</div>';
    const t = $("#newsTopic").value;
    const r = await fetch("/api/news" + (t === "ALL" ? "" : "?topic=" + t));
    const d = await r.json();
    $("#newsUpdated").textContent = d.updated_at ? "updated " + d.updated_at : "";
    if (!d.items?.length) {
      $("#newsList").innerHTML = '<div class="empty">No news items yet — the news job has not run yet, or nothing matches this tag.</div>';
      return;
    }
    $("#newsList").innerHTML = '<div class="card">' + d.items.map((i) => `
      <article class="news-item">
        <h3><a href="${esc(i.url)}" target="_blank" rel="noopener">${esc(i.title)}</a></h3>
        <div class="meta">${esc(i.source || "")}${i.published ? " · " + esc(i.published) : ""}</div>
        <p>${esc(i.summary || "")}</p>
        <div class="tags">${(i.topics || []).map((x) => `<span class="tag">${esc(x)}</span>`).join("")}</div>
      </article>`).join("") + "</div>";
  }
  $("#newsTopic").addEventListener("change", loadNews);
})();

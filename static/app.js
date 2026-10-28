/* MakGeography front-end */
(() => {
  "use strict";
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];

  // ---------------------------------------------------------------- static build
  //
  // The live site is FastAPI. The GitHub Pages copy is static, so the
  // read-only data is fetched from JSON files instead of /api/*. The two
  // features that need a language model - Ask and Generate an essay - are
  // unavailable there, and the page says so rather than failing silently.
  const STATIC = window.MAKGEO_STATIC === true;
  const STATIC_ROOT = "";

  // A fetch that reads the static JSON in the static build, and the API
  // on the live server.
  //
  // The static files are named after the endpoint: /api/mc -> api/mc.json,
  // /api/kb/status -> api/kb/status.json. A query string on the live
  // server (the topic filter, the limit) is dropped, because the static
  // file already holds everything and the filter runs in the browser.
  async function getJSON(path) {
    if (!STATIC) {
      const r = await fetch(path);
      if (!r.ok) throw new Error(`${path} -> ${r.status}`);
      return r.json();
    }
    const clean = path.split("?")[0].replace(/\/api\/?/, "");
    const r = await fetch(`api/${clean}.json`);
    if (!r.ok) throw new Error(`${path} -> ${r.status}`);
    return r.json();
  }

  // The path prefix every media URL needs. On the live server the media is
  // served from /oqb-images/...; in the static build the same files sit
  // under oqb-media/....
  const MEDIA = STATIC ? "oqb-media/" : "/oqb-images/";
  const ATTACH = STATIC ? "oqb-media/" : "/oqb-attachments/";
  const QIMG = STATIC ? "question-images/" : "/question-images/";

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
      if (btn.dataset.panel === "essay") loadEssayTree();
      if (btn.dataset.panel === "news") loadNews();
      if (btn.dataset.panel === "activity") loadActivity();
    });
  });

  // ---------------------------------------------------------------- kb status
  async function loadStatus() {
    try {
      const d = await getJSON("/api/kb/status");
      $("#kbChunks").textContent = d.chunks ?? "–";
      $("#kbDocs").textContent = `${d.docs} notes · built ${(d.built_at || "").slice(0, 10)}`;
      const opts = (d.topics || []).map((t) => `<option value="${t}">${t}</option>`).join("");
      $("#topicSel").insertAdjacentHTML("beforeend", opts);
      $("#notesTopic").insertAdjacentHTML("beforeend", opts);
      $("#newsTopic").insertAdjacentHTML("beforeend", opts);
    } catch (e) { /* offline indicator is enough */ }

    // The MC filter is built from the question bank's own topics, not from
    // the note topics. The two are different sets: the bank also holds
    // official HKEAA map-reading questions ("MAP"), and it has no questions
    // at all for some note topics. Listing a note topic with nothing to
    // drill is a filter that silently returns an empty set.
    try {
      const d = await getJSON("/api/mc?limit=1");
      const sel = $("#mcTopic");
      if (d.topics && d.topics.length) {
        const have = [...sel.options].map((o) => o.value);
        const extra = d.topics
          .filter((t) => !have.includes(t))
          .map((t) => `<option value="${t}">${t}</option>`).join("");
        if (extra) sel.insertAdjacentHTML("beforeend", extra);
      }
      const note = document.querySelector("#mcTotal");
      if (note && d.total != null) {
        const off = (d.official_total != null) ? d.official_total : null;
        note.textContent = off
          ? `${d.total} questions in the bank — ${off} of them official HKEAA exam questions.`
          : `${d.total} questions in the bank.`;
      }
    } catch (e) { /* the drill still works without the filters */ }
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
      if (STATIC) {
        pending.querySelector(".body").innerHTML =
          `<span class="loading">Asking a question needs the live site. ` +
          `<a href="https://sunday-answer-prepare-companies.trycloudflare.com">Open MakGeography</a> ` +
          `and ask there &mdash; this page is the static copy.</span>`;
        btn.disabled = false;
        return;
      }
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
    const d = await getJSON("/api/notes");
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
                    <h4>${esc(c.title)}${c.heading && c.heading !== c.title ? " — " + esc(c.heading) : ""}</h4>
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
    const d = await getJSON("/api/mc?limit=1000");
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
        ${q.map_extract
          ? `<div class="mc-mapextract"><a href="${ATTACH}${esc(q.map_extract)}" target="_blank" rel="noopener">Open the map extract for this paper (${esc(q.map_extract.split("/").pop())})</a></div>`
          : ""}
        ${q.stem_image
          ? `<figure class="mc-question-image"><img src="${MEDIA}${esc(q.stem_image)}" alt="The question as it appeared in the HKDSE examination paper" loading="lazy"><figcaption>Source: HKEAA examination question paper. &copy; HKEAA.</figcaption></figure>`
          : q.question_image
            ? `<figure class="mc-question-image"><img src="${QIMG}${esc(q.question_image.split("/").pop())}" alt="The question as it appeared in the HKDSE examination paper" width="${q.image_width || 1200}" height="${q.image_height || 600}"><figcaption>Source: HKEAA examination question paper. &copy; HKEAA.</figcaption></figure>`
            : `<div class="stem">${md(q.stem)}</div>`}
        <div class="mc-opts">${q.options.map((o, j) =>
          `<button class="mc-opt${q.graphic_options ? " is-graphic" : ""}" data-k="${String.fromCharCode(65 + j)}"><span class="k">${String.fromCharCode(65 + j)}</span>${q.graphic_options ? "" : `<span>${esc(o)}</span>`}${q.option_images && q.option_images[j] ? `<img class="mc-opt-image" src="${MEDIA}${esc(q.option_images[j])}" alt="Option ${String.fromCharCode(65 + j)}" loading="lazy">` : ""}</button>`).join("")}
        </div>
        <div class="mc-fb" style="display:none"></div>
      </div>`).join("");

    // If the drill is rendered again, drop the previous listener first.
    // The old one closed over the previous question array, so leaving it
    // attached would answer from stale data.
    if ($("#mcList")._mcHandler) {
      $("#mcList").removeEventListener("click", $("#mcList")._mcHandler);
    }

    // A delegated listener on the list, NOT { once: true }.
    //
    // With { once: true }, any click that did not land on an option - the
    // "Show the original HKEAA slide" summary, the question text, the gap
    // between options - consumed the listener and then returned early. The
    // student then clicked an answer and nothing happened at all.
    // Safari hits that path more often than Chrome, because the click
    // target differs.
    //
    // The handler now stays attached for the life of the render, and it
    // ignores clicks on anything that is not an answer.
    $("#mcList")._mcHandler = handler;
    $("#mcList").addEventListener("click", handler);
    function handler(ev) {
      const opt = ev.target.closest(".mc-opt");
      if (!opt) return;                    // a click that is not an answer
      if (opt.disabled) return;            // this question is already done
      const box = opt.closest(".mc-q");
      if (!box) return;
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
    }
  }

  // The static build holds the whole bank in one file, so the topic filter
  // and the limit run here rather than on the server.
  let staticBank = null;
  async function pickQuestions(topic, n, subtopic) {
    if (!STATIC) {
      const d = await getJSON(
        `/api/mc?limit=${n}${topic === "ALL" ? "" : "&topic=" + topic}` +
        (subtopic ? `&subtopic=${encodeURIComponent(subtopic)}` : ""));
      return d.questions || [];
    }
    if (!staticBank) {
      const d = await getJSON("/api/mc");
      staticBank = d.questions || [];
    }
    let qs = staticBank;
    if (topic && topic !== "ALL") {
      qs = qs.filter((q) => (q.topics || []).some((t) => t.toUpperCase() === topic.toUpperCase()));
    }
    if (subtopic) qs = qs.filter((q) => q.subtopic === subtopic);
    const limit = Number(n);
    return limit > 0 ? qs.slice(0, limit) : qs;
  }

  $("#mcStart").addEventListener("click", async () => {
    const topic = $("#mcTopic").value;
    const n = $("#mcCount").value;
    const qs = await pickQuestions(topic, n);
    renderDrill(qs);
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
    const all = await pickQuestions("ALL", 0);
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

  // ---------------------------------------------------------------- essay
  let essayTree = null;

  async function loadEssayTree() {
    if (essayTree) { renderEssayTopics(); return; }
    $("#essayOut").innerHTML = '<div class="empty">Loading the sub-topics…</div>';
    const d = await getJSON("/api/essay/tree");
    essayTree = d.electives || [];
    $("#essayElective").insertAdjacentHTML("beforeend",
      essayTree.map((e) => `<option value="${esc(e.code)}">${esc(e.code)} — ${esc(e.title)}</option>`).join(""));
    // Two command lists, one per half of the essay. The server is the
    // authority on which words belong to which half.
    $("#essayCommandA").innerHTML = (d.commands_a || []).map((c) =>
      `<option value="${esc(c.key)}">${esc(c.label)}</option>`).join("");
    $("#essayCommandB").innerHTML = (d.commands_b || []).map((c) =>
      `<option value="${esc(c.key)}">${esc(c.label)}</option>`).join("");
    // Default to the pairing the recent real papers use.
    $("#essayCommandA").value = "describe_explain";
    $("#essayCommandB").value = "discuss";
    $("#essayOut").innerHTML = "";
    renderEssayTopics();
    syncEssayCommands();
  }

  // An 8-mark essay is a single part, so it only needs one command word.
  // Hiding the second one keeps the form honest about what will be
  // generated.
  function syncEssayCommands() {
    const marks = Number($("#essayMarks").value);
    const two = marks >= 12;
    const b = $("#essayCommandB");
    const label = b.closest(".field");
    b.disabled = !two;
    if (label) label.style.display = two ? "" : "none";
    const note = $("#essayCommandNote");
    if (note) {
      note.innerHTML = two
        ? "A DSE short essay is two parts with two different command words. " +
          "Part (a) earns marks for knowledge and mechanism; part (b) for " +
          "explanation and judgement. The same command word is not used for " +
          "both halves."
        : "An 8-mark essay is a single part, so it takes one command word.";
    }
  }

  function renderEssayTopics() {
    const code = $("#essayElective").value;
    const box = $("#essayTopics");
    if (!code || !essayTree) { box.innerHTML = ""; return; }
    const el = essayTree.find((e) => e.code === code);
    if (!el) { box.innerHTML = ""; return; }
    // Every sub-topic is ticked by default. The generator draws on the
    // notes for whichever ones are ticked, and a broad pick gives the
    // model more material to build a coherent essay from.
    box.innerHTML = `<div class="card"><h4 style="margin-bottom:10px">Sub-topics for the essay</h4>` +
      el.subquestions.map((sq) => `
        <div class="essay-sq">
          <div class="essay-sq-head">
            <b>${esc(sq.number)}. ${esc(sq.title)}</b>
            <button class="link-btn" data-sq="${esc(sq.number)}" data-code="${esc(code)}">all / none</button>
          </div>
          <div class="essay-leaves" data-sq="${esc(sq.number)}">
            ${sq.leaves.map((l) => `
              <label><input type="checkbox" value="${esc(l.id)}" checked> ${esc(l.title)}</label>`).join("")}
          </div>
        </div>`).join("") +
      `</div>`;
  }

  $("#essayElective").addEventListener("change", renderEssayTopics);
  $("#essayMarks").addEventListener("change", syncEssayCommands);

  $("#essayTopics").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-sq]");
    if (!b) return;
    const wrap = $(`.essay-leaves[data-sq="${b.dataset.sq}"]`);
    if (!wrap) return;
    const boxes = $$("input", wrap);
    const allOn = boxes.every((x) => x.checked);
    boxes.forEach((x) => { x.checked = !allOn; });
  });

  $("#essayGo").addEventListener("click", async () => {
    const code = $("#essayElective").value;
    if (!code) {
      $("#essayOut").innerHTML = '<div class="empty">Choose an elective first.</div>';
      return;
    }
    const leafIds = $$("#essayTopics input:checked").map((x) => x.value);
    const btn = $("#essayGo");
    btn.disabled = true;
    btn.textContent = "Writing…";
    $("#essayOut").innerHTML = '<div class="card"><span class="loading">Building the question, the mark scheme and the exemplar answer from the notes…</span></div>';
    try {
      if (STATIC) {
        $("#essayOut").innerHTML = `<div class="card"><span class="loading">Writing an essay needs the live site. ` +
          `<a href="https://sunday-answer-prepare-companies.trycloudflare.com">Open MakGeography</a> ` +
          `and generate it there &mdash; this page is the static copy.</span></div>`;
        btn.disabled = false;
        btn.textContent = "Generate";
        return;
      }
      const r = await fetch("/api/essay/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic: code,
          leaf_ids: leafIds,
          marks: Number($("#essayMarks").value),
          command_a: $("#essayCommandA").value,
          command_b: Number($("#essayMarks").value) >= 12
            ? $("#essayCommandB").value : null,
        }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || d.error || "Generation failed.");
      if (!d.ok) throw new Error(d.error || "Generation failed.");
      renderEssay(d);
    } catch (err) {
      $("#essayOut").innerHTML = `<div class="card"><span class="loading">${esc(err.message)}</span></div>`;
    } finally {
      btn.disabled = false;
      btn.textContent = "Generate essay";
    }
  });

  function renderEssay(d) {
    const src = (d.sources && d.sources.length)
      ? `<div class="sources"><b>Built from these notes</b>` +
        d.sources.map((s) =>
          `<span class="source-chip" title="${esc(s.path)}">${esc(s.title)}${s.leaf_title ? " · " + esc(s.leaf_title) : ""}</span>`
        ).join("") + `</div>`
      : "";
    $("#essayOut").innerHTML = `<div class="card essay-card">${md(d.essay)}${src}
      <p class="hint-small">Practice material written from the MakGeography notes.
       Nothing here is from a real exam paper.</p></div>`;
  }

  // ---------------------------------------------------------------- news
  async function loadNews() {
    $("#newsList").innerHTML = '<div class="empty">Loading news…</div>';
    const t = $("#newsTopic").value;
    const d = await getJSON("/api/news" + (t === "ALL" ? "" : "?topic=" + t));
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

  // ------------------------------------------------------------- activity
  // The teacher's own view of who has used the site. Only the teacher
  // has this panel, and the server refuses the request from anyone else,
  // so the data is not merely hidden here - it is not served.
  async function loadActivity() {
    const days = $("#activityDays").value;
    const box = $("#activitySummary");
    const table = $("#activityTable");
    box.innerHTML = '<div class="empty">Loading…</div>';
    table.innerHTML = "";
    let d;
    try {
      d = await getJSON(`/api/teacher/activity?days=${days}`);
    } catch (e) {
      box.innerHTML = '<div class="empty">Could not load the activity log.</div>';
      return;
    }
    const classes = Object.entries(d.by_class || {})
      .map(([k, v]) => `${esc(k)}: ${v}`).join(" · ");
    box.innerHTML = `<div class="card">
        <div class="stat-row">
          <div><strong>${d.active_students}</strong><span>students active</span></div>
          <div><strong>${d.total_logins}</strong><span>sign-ins</span></div>
          <div><strong>${d.total_asks}</strong><span>questions asked</span></div>
          <div><strong>${d.total_essays}</strong><span>essays written</span></div>
        </div>
        ${classes ? `<p class="meta">By class — ${classes}</p>` : ""}
      </div>`;
    if (!d.students?.length) {
      table.innerHTML = '<div class="empty">Nobody has signed in yet in this period.</div>';
      return;
    }
    table.innerHTML = `<div class="card"><table class="activity">
        <thead><tr><th>Student ID</th><th>Name</th><th>Class</th>
          <th>Sign-ins</th><th>Questions</th><th>Essays</th><th>Last seen</th></tr></thead>
        <tbody>${d.students.map((s) => `<tr>
          <td>${esc(s.sid)}</td>
          <td>${esc(s.name)}</td>
          <td>${esc(s.class)}</td>
          <td>${s.logins}</td><td>${s.asks}</td><td>${s.essays}</td>
          <td>${esc(s.last)}</td></tr>`).join("")}</tbody>
      </table></div>`;
  }
  $("#activityDays").addEventListener("change", loadActivity);
  $("#activityRefresh").addEventListener("click", loadActivity);
})();

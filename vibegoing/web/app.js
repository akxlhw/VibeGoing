/* VibeGoing 前端（无构建链，原生 JS）。intovibe 风格：暖白/鼠尾草绿/编号卡片/五步向导。 */
"use strict";

const $ = (sel, el = document) => el.querySelector(sel);
const state = { souls: [], chat: { soul: null, sessionId: null, approved: new Set() }, ver: "?" };

const api = {
  get: (p) => fetch(p).then(r => r.json()),
  post: (p, body) => fetch(p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) }).then(async r => { const d = await r.json(); if (!r.ok) throw new Error(d.detail || r.status); return d; }),
  patch: (p, body) => fetch(p, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) }).then(r => r.json()),
};

/* ---------- 路由 ---------- */
const routes = {
  mates: renderMates, chat: renderChat, tasks: renderTasks,
  runtimes: renderRuntimes, settings: renderSettings,
};
function nav() {
  const [page, arg] = location.hash.replace(/^#\//, "").split("/");
  (routes[page] || renderMates)(arg);
  document.querySelectorAll(".nav-item").forEach(el =>
    el.classList.toggle("active", el.dataset.nav === (page || "mates")));
}
window.addEventListener("hashchange", nav);

/* ---------- 伙伴 ---------- */
const EMOJIS = ["🎯", "🔍", "🧪", "🛠️", "📈", "🧭", "🪄", "🔭", "📐", "🖋️", "⚖️", "🌱", "🚀", "🧩", "🎧", "🛡️"];
async function renderMates() {
  const view = $("#view");
  view.innerHTML = `<div class="page-head"><h1>伙伴</h1><span class="en">Teammates</span>
    <span class="spacer"></span><button class="btn primary" id="new-mate">＋ 新建伙伴 →</button></div>
    <div class="cards" id="cards"><div class="loading">加载中…</div></div>`;
  $("#new-mate").onclick = openWizard;
  state.souls = await api.get("/api/souls");
  const grid = $("#cards");
  grid.innerHTML = state.souls.map(s => `
    <div class="card">
      <div class="who"><div class="avatar">${s.emoji}</div>
        <div><b>${s.name}</b><small>${s.model}</small></div></div>
      <div class="persona">${s.persona || "（尚未设置人设）"}</div>
      <div class="chips">
        <span class="chip rt">${s.runtime}</span>
        ${s.memory_enabled ? '<span class="chip">记忆 开</span>' : '<span class="chip">记忆 关</span>'}
        ${(s.capabilities || []).map(c => `<span class="chip">${c}</span>`).join("")}
      </div>
      <div class="ops">
        <button class="btn primary" data-chat="${s.name}">聊天 →</button>
        <button class="btn ghost" data-edit="${s.name}">编辑</button>
      </div>
    </div>`).join("") + `
    <div class="card new" id="add-card"><div><div class="plus">＋</div><small>创建新伙伴</small></div></div>`;
  $("#add-card").onclick = openWizard;
  grid.querySelectorAll("[data-chat]").forEach(b => b.onclick = () => { location.hash = `#/chat/${b.dataset.chat}`; });
  grid.querySelectorAll("[data-edit]").forEach(b => b.onclick = () => openWizard(state.souls.find(s => s.name === b.dataset.edit)));
}

/* ---------- 五步向导（01形象 02名字 03人设 04Soul 05Runtime） ---------- */
const wiz = { step: 1, data: { emoji: "🎯", name: "", persona: "", principles: [], capabilities: [], model: "openai/gpt-4o", runtime: "llm", memory_enabled: true } };
const RUNTIME_CAPTIONS = { llm: "BYO Key · LiteLLM", "claude-code": "stream-json 契约", codex: "exec 契约", zcode: "智谱 · zcode -p", "kimi-code": "月之暗面 · --auto", "deepseek-harness": "dsh headless" };

function openWizard(soul) {
  if (soul) Object.assign(wiz.data, soul, { principles: soul.principles || [], capabilities: soul.capabilities || [] });
  wiz.step = 1;
  $("#wiz-mask").style.display = "grid";
  drawWizard();
}
function closeWizard() { $("#wiz-mask").style.display = "none"; }

function drawWizard() {
  document.querySelectorAll(".step").forEach(el => el.classList.toggle("on", +el.dataset.s === wiz.step));
  $("#wiz-title").textContent = wiz.step === 5 ? "确认创建" : `创建伙伴 · 第 ${wiz.step} 步`;
  $("#wiz-next").textContent = wiz.step === 5 ? "创建伙伴 ✨" : "下一步 →";
  $("#wiz-prev").style.visibility = wiz.step === 1 ? "hidden" : "visible";
  const d = wiz.data, body = $("#wiz-body");
  if (wiz.step === 1) {
    body.innerHTML = `<div class="wiz-sub">选一个形象，或者摇一摇 🎲</div>
      <div class="emoji-grid">${EMOJIS.map(e => `<div class="emoji-cell ${e === d.emoji ? "on" : ""}" data-e="${e}">${e}</div>`).join("")}</div>
      <div style="margin-top:14px"><button class="btn" id="shuffle">🎲 摇一个</button></div>`;
    body.querySelectorAll(".emoji-cell").forEach(c => c.onclick = () => { d.emoji = c.dataset.e; drawWizard(); });
    $("#shuffle").onclick = () => { d.emoji = EMOJIS[Math.floor(Math.random() * EMOJIS.length)]; drawWizard(); };
  } else if (wiz.step === 2) {
    body.innerHTML = `<div class="wiz-sub">伙伴的名字（协作时用于点名与 @）</div>
      <div class="field"><label>名字</label><input type="text" id="f-name" value="${d.name}" placeholder="如 ava / bob" /></div>`;
    $("#f-name").oninput = e => d.name = e.target.value.trim();
  } else if (wiz.step === 3) {
    body.innerHTML = `<div class="wiz-sub">一句话描述 TA 是谁，或让 AI 帮你写 ✨</div>
      <div class="field"><label>描述</label><input type="text" id="f-desc" placeholder="如：一位严谨的法务顾问，擅长合同审查" /></div>
      <button class="btn" id="gen">Soul 一键生成 ✨</button>
      <div class="field" style="margin-top:14px"><label>人设</label>
        <textarea id="f-persona" placeholder="第二人称人设描述">${d.persona}</textarea></div>`;
    $("#f-persona").oninput = e => d.persona = e.target.value;
    $("#gen").onclick = async () => {
      $("#gen").disabled = true; $("#gen").textContent = "生成中…";
      try {
        const r = await api.post("/api/persona-draft", { description: $("#f-desc").value, model: d.model });
        d.persona = r.persona; d.principles = r.principles;
        $("#f-persona").value = d.persona;
      } catch (e) { alert("生成失败：" + e.message + "（可在 .env 配置 API Key）"); }
      $("#gen").disabled = false; $("#gen").textContent = "Soul 一键生成 ✨";
    };
  } else if (wiz.step === 4) {
    const tagRow = (key, label, hint) => `
      <div class="field"><label>${label}</label>
        <div class="tag-input" id="ti-${key}">${d[key].map((t, i) => `<span class="chip on" data-i="${i}" data-k="${key}">${t} ✕</span>`).join("")}</div>
        <input type="text" id="in-${key}" placeholder="${hint}，回车添加" style="margin-top:8px" /></div>`;
    body.innerHTML = `<div class="wiz-sub">工作原则与能力标签（协作路由按能力分派任务）</div>
      ${tagRow("principles", "工作原则", "如：先给结论")}
      ${tagRow("capabilities", "能力标签", "如：调研")}`;
    const wire = (key) => {
      $(`#in-${key}`).onkeydown = e => {
        if (e.key === "Enter" && e.target.value.trim()) { d[key].push(e.target.value.trim()); drawWizard(); }
      };
      body.querySelectorAll(`[data-k="${key}"]`).forEach(c => c.onclick = () => { d[key].splice(+c.dataset.i, 1); drawWizard(); });
    };
    wire("principles"); wire("capabilities");
  } else {
    const names = state.runtimes || (state.runtimes = []);
    body.innerHTML = `<div class="wiz-sub">选择执行体——换引擎不换大脑，之后随时可换绑</div>
      <div class="radio-list">${(names.length ? names : Object.keys(RUNTIME_CAPTIONS).map(n => ({ name: n }))).map(r =>
        `<label class="radio-item ${d.runtime === r.name ? "on" : ""}">
          <input type="radio" name="rt" value="${r.name}" ${d.runtime === r.name ? "checked" : ""} />
          <b>${r.name}</b><small>${RUNTIME_CAPTIONS[r.name] || ""}${r.ok === false ? " · ❌ 未检测到" : ""}</small></label>`).join("")}</div>
      <div class="field" style="margin-top:14px"><label>模型（llm 执行体使用；LiteLLM 格式）</label>
        <input type="text" id="f-model" value="${d.model}" /></div>
      <p class="hint">CLI 执行体（zcode/kimi-code 等）在工作目录白名单内执行，危险指令需你在聊天中批准。</p>`;
    body.querySelectorAll("input[name=rt]").forEach(r => r.onchange = () => { d.runtime = r.value; drawWizard(); });
    $("#f-model").oninput = e => d.model = e.target.value.trim();
  }
}

$("#wiz-prev").onclick = () => { if (wiz.step > 1) { wiz.step--; drawWizard(); } };
$("#wiz-next").onclick = async () => {
  const d = wiz.data;
  if (wiz.step === 2 && !d.name) { alert("先给伙伴起个名字"); return; }
  if (wiz.step < 5) { wiz.step++; drawWizard(); return; }
  try {
    const exists = state.souls.some(s => s.name === d.name);
    const payload = { emoji: d.emoji, persona: d.persona || "", principles: d.principles, capabilities: d.capabilities, model: d.model, runtime: d.runtime, memory_enabled: d.memory_enabled };
    if (exists) await api.patch(`/api/souls/${d.name}`, payload);
    else await api.post("/api/souls", { name: d.name, ...payload });
    closeWizard(); await renderMates();
  } catch (e) { alert("保存失败：" + e.message); }
};
$("#wiz-mask").addEventListener("click", e => { if (e.target.id === "wiz-mask") closeWizard(); });

/* ---------- 聊天 ---------- */
async function renderChat(soulName) {
  const view = $("#view");
  const souls = state.souls.length ? state.souls : (state.souls = await api.get("/api/souls"));
  const name = soulName && souls.some(s => s.name === soulName) ? soulName : (souls[0] && souls[0].name);
  if (!name) { view.innerHTML = `<div class="notice">还没有伙伴，先去 <a href="#/mates">伙伴页</a> 创建一位 →</div>`; return; }
  const soul = souls.find(s => s.name === name);
  state.chat = { soul: name, sessionId: null, approved: new Set() };
  view.innerHTML = `
    <div class="page-head"><h1>聊天</h1><span class="en">Chat</span><span class="spacer"></span>
      <select id="pick-soul">${souls.map(s => `<option ${s.name === name ? "selected" : ""}>${s.name}</option>`).join("")}</select>
      <button class="btn" id="new-session">新会话</button></div>
    <div class="chat-wrap">
      <div class="chat-head"><div class="avatar">${soul.emoji}</div>
        <div><b>${soul.name}</b> <small>执行体 ${soul.runtime} · ${soul.model}</small></div>
        <span class="spacer" style="flex:1"></span><small id="session-tag"></small></div>
      <div class="msgs" id="msgs"></div>
      <div class="approval" id="approval" style="display:none"></div>
      <div class="chat-input"><input id="chat-in" placeholder="给 ${soul.name} 发消息，回车发送…" />
        <button class="btn primary" id="send">发送 →</button></div>
    </div>`;
  $("#pick-soul").onchange = e => { location.hash = `#/chat/${e.target.value}`; };
  $("#new-session").onclick = () => { state.chat.sessionId = null; $("#msgs").innerHTML = ""; $("#session-tag").textContent = "新会话"; };
  $("#send").onclick = send;
  $("#chat-in").onkeydown = e => { if (e.key === "Enter") send(); };
  $("#chat-in").focus();
}

async function send() {
  const input = $("#chat-in"), text = input.value.trim();
  if (!text) return;
  input.value = "";
  const msgs = $("#msgs");
  msgs.insertAdjacentHTML("beforeend", `<div class="msg user"></div>`);
  msgs.lastElementChild.textContent = text;
  const holder = document.createElement("div");
  holder.className = "msg assistant";
  holder.innerHTML = `<div class="who">${state.chat.soul}</div><span class="typing">…</span>`;
  msgs.appendChild(holder); msgs.scrollTop = msgs.scrollHeight;
  try {
    const r = await api.post("/api/chat", {
      soul: state.chat.soul, message: text,
      session_id: state.chat.sessionId,
      approved_dangerous: [...state.chat.approved],
    });
    state.chat.sessionId = r.session_id;
    $("#session-tag").textContent = `会话 ${r.session_id.slice(0, 8)}`;
    holder.classList.toggle("err", r.reply.startsWith("⚠️"));
    holder.innerHTML = `<div class="who">${state.chat.soul}</div>`;
    typeWriter(holder, r.reply, () => maybeApproval(r.reply));
  } catch (e) {
    holder.classList.add("err"); holder.innerHTML = `<div class="who">错误</div>${e.message}`;
  }
  msgs.scrollTop = msgs.scrollHeight;
}

function typeWriter(el, text, done) {  // 打字机（服务端暂非流式，前端呈现流式感）
  const p = document.createElement("span"); el.appendChild(p);
  let i = 0;
  const tick = () => { p.textContent = text.slice(0, i += 3); el.parentElement.scrollTop = 1e9; if (i < text.length) setTimeout(tick, 12); else done && done(); };
  tick();
}

async function maybeApproval(reply) {  // 权限审批入口（VG-403）：CLI 危险操作被拒时出现
  if (!reply.startsWith("⚠️") || !reply.includes("危险操作")) return;
  const labels = await api.get("/api/dangerous-labels");
  const box = $("#approval");
  box.style.display = "flex";
  box.innerHTML = `<span>⚠️ 指令含危险操作被拒。勾选放行项后重新发送：</span>` +
    labels.map(l => `<span class="chip ${state.chat.approved.has(l) ? "on" : ""}" data-l="${l}">${l}</span>`).join("");
  box.querySelectorAll(".chip").forEach(c => c.onclick = () => {
    const l = c.dataset.l;
    state.chat.approved.has(l) ? state.chat.approved.delete(l) : state.chat.approved.add(l);
    c.classList.toggle("on");
  });
}

/* ---------- 任务台账 ---------- */
let taskTimer = null;
async function renderTasks() {
  const view = $("#view");
  view.innerHTML = `<div class="page-head"><h1>任务台账</h1><span class="en">Ledger</span><span class="spacer"></span>
    <input type="text" id="task-in" placeholder="协作任务，如：调研 X 并写摘要" style="border:1px solid var(--line);border-radius:999px;padding:8px 14px" />
    <button class="btn primary" id="task-go">运行 →</button></div>
    <div id="task-area"><div class="loading">加载中…</div></div>`;
  $("#task-go").onclick = async () => {
    const t = $("#task-in").value.trim(); if (!t) return;
    const r = await api.post("/api/crew/run", { task: t });
    if (taskTimer) clearInterval(taskTimer);
    taskTimer = setInterval(async () => { await drawTasks(); const d = await api.get(`/api/tasks/${r.task_id}`); if (["done", "failed"].includes(d.task.status)) clearInterval(taskTimer); }, 1200);
  };
  await drawTasks();
}
async function drawTasks() {
  const tasks = await api.get("/api/tasks");
  const area = $("#task-area");
  if (!tasks.length) { area.innerHTML = `<div class="notice">暂无协作任务。输入任务描述并运行——产出 → 复核 → 汇总，全过程落台账。</div>`; return; }
  area.innerHTML = `<table class="list"><tr><th>ID</th><th>模式</th><th>状态</th><th>描述</th><th>更新</th></tr>` +
    tasks.map(t => `<tr data-id="${t.task_id}"><td>${t.task_id}</td><td>${t.mode}</td>
      <td><span class="st-badge ${t.status}">${t.status}</span></td><td>${t.description.slice(0, 40)}</td><td>${t.updated_at.slice(0, 19)}</td></tr>`).join("") + `</table>`;
  area.querySelectorAll("tr[data-id]").forEach(tr => tr.onclick = () => renderTaskDetail(tr.dataset.id));
}
async function renderTaskDetail(id) {
  const { task, stages } = await api.get(`/api/tasks/${id}`);
  $("#view").innerHTML = `<div class="page-head"><h1>任务 ${task.task_id}</h1>
    <span class="st-badge ${task.status}">${task.status}</span><span class="spacer"></span>
    <button class="btn" onclick="location.hash='#/tasks'">← 返回</button></div>
    <div class="notice" style="margin-bottom:16px"><b>${task.description}</b><br />模式 ${task.mode} · 创建 ${task.created_at}</div>
    <div class="sect"><span class="num">01</span><b>阶段产物</b><span class="en">Stages</span></div>
    ${stages.map(s => `<div class="stage"><div class="meta"><b>${s.stage}</b><small>${s.agent} · ${s.created_at}</small></div><pre>${escapeHtml(s.output)}</pre></div>`).join("") || '<div class="loading">暂无阶段记录</div>'}`;
}
const escapeHtml = (s) => s.replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

/* ---------- 执行体 ---------- */
async function renderRuntimes() {
  const runtimes = await api.get("/api/runtimes");
  state.runtimes = runtimes;
  $("#view").innerHTML = `<div class="page-head"><h1>执行体</h1><span class="en">Runtimes</span></div>
    <div class="rt-grid">${runtimes.map(r => `
      <div class="card"><div class="who"><div class="avatar">${r.ok ? "✅" : "❌"}</div>
        <div><b>${r.name}</b><small>${r.ok ? "可用" : "未检测到"}</small></div></div>
        <div class="persona">${r.detail}</div></div>`).join("")}</div>
    <div class="notice" style="margin-top:18px">桌面版内置 CLI 不在 PATH 时，在 <code>.env</code> 设置 <code>VIBE_&lt;执行体&gt;_BIN</code> 指向实际二进制。</div>`;
}

/* ---------- 设置 ---------- */
function renderSettings() {
  $("#view").innerHTML = `
    <div class="page-head"><h1>设置</h1><span class="en">Settings</span></div>
    <div class="sect"><span class="num">01</span><b>版本</b><span class="en">Version</span></div>
    <div class="notice">当前版本 <b>${state.ver}</b>。升级：<code>uv tool upgrade vibegoing --reinstall</code>（或重新 <code>uv tool install .</code>）。</div>
    <div class="sect"><span class="num">02</span><b>隐私边界</b><span class="en">Local First</span></div>
    <div class="notice"> Soul、记忆、会话快照、任务台账全部存于本机 <code>VIBE_HOME</code>；本服务仅监听 <code>127.0.0.1</code>；CLI 伙伴受目录白名单与危险指令审批保护（红线，见 ADR-0007/评审记录）。</div>
    <div class="sect"><span class="num">03</span><b>快捷入口</b><span class="en">CLI</span></div>
    <div class="notice">终端同样可用：<code>vibegoing</code> 对话 · <code>vibegoing crew run "任务"</code> 协作 · <code>vibegoing memory list</code> 记忆 · <code>vibegoing runtime check zcode</code> 健康检查。</div>`;
}

/* ---------- 启动 ---------- */
(async function init() {
  const health = await api.get("/api/health");
  state.ver = health.version;
  $("#ver").textContent = "v" + health.version;
  if (!location.hash) location.hash = "#/mates";
  nav();
})();

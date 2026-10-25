import { postChatTurn } from "./api/post-chat-turn.js";
import { appendBubble, renderTranscript } from "./chat/render-transcript.js";
import { chatRequest } from "./chat/send-turn.js";
import { appendTurn } from "./chat/transcript-store.js";
import { STORAGE_NOTICE } from "./notice/storage-notice.js";
import { discardPassages } from "./passages/discard-passages.js";
import { renderPassages } from "./passages/render-passages.js";
import { labFromRows, mayStore, rowFromFields } from "./redaction-client/accept-lab-json.js";
import { requestAnonymisation } from "./redaction-client/request-anonymisation.js";
import { FIXED_MESSAGE, PDF_MESSAGE, UNDERAGE_MESSAGE, UNREADABLE_MESSAGE, URGENT_MESSAGE } from "./refusal/fixed-message.js";
import { renderCards, renderUncertainties } from "./results/render-cards.js";
import { labForChat, mentionsPotassium, prepareReport } from "./rules/apply-context.js";
import { encryptJson, decryptJson } from "./storage/aes-gcm.js";
import { deleteAll } from "./storage/delete-all.js";
import { deleteFile } from "./storage/delete-file.js";
import { getAllRecords, putRecord } from "./storage/indexed-db.js";
import { stamp } from "./storage/last-used.js";
import { purgeExpired, purgeUnreadable } from "./storage/purge.js";
import { createSessionKey, loadSessionKey } from "./storage/session-key.js";
import { otherTabIsOpen, startLockHeartbeat } from "./storage/tab-lock.js";
import { downloadSummary } from "./summary/download-summary.js";
import { discardOriginal } from "./upload/discard-original.js";
import { EXAMPLE_REPORT } from "./upload/example-report.js";
import { fetchCatalog, fetchFixture, fixtureIdFromName } from "./upload/fixture-drop.js";
import { classifyFile, sizeProblem } from "./upload/select-document.js";

const state = {
  key: null,
  heartbeat: null,
  preview: null,
  openId: null,
  payload: null,
  library: [],
  shells: [],
  hints: null,
};

const screens = ["upload", "check", "context", "decline", "results"];

function $(id) {
  return document.getElementById(id);
}

function show(name) {
  for (const screen of screens) {
    $(`screen-${screen}`).hidden = screen !== name;
  }
  $("screen-other").hidden = true;
  const step = { upload: "1", check: "2", context: "3", decline: "2", results: "4" }[name];
  for (const item of document.querySelectorAll("#steps [data-step]")) {
    item.setAttribute("aria-current", item.dataset.step === step ? "step" : "false");
  }
  const heading = document.querySelector(`#screen-${name} h1`);
  heading?.focus();
}

function showOtherTab() {
  for (const screen of screens) $(`screen-${screen}`).hidden = true;
  $("screen-other").hidden = false;
  $("screen-other").querySelector("h1").focus();
}

document.querySelectorAll("#storage-notice, #storage-notice-again").forEach((node) => {
  node.textContent = STORAGE_NOTICE;
});

$("report-file").addEventListener("change", onFile);
$("example-report").addEventListener("click", () => openPreview(structuredClone(EXAMPLE_REPORT)));
$("drop-zone").addEventListener("dragover", onDragOver);
$("drop-zone").addEventListener("dragleave", () => $("drop-zone").classList.remove("dragover"));
$("drop-zone").addEventListener("drop", onDrop);
document.addEventListener("dragover", (event) => event.preventDefault());
document.addEventListener("drop", (event) => event.preventDefault());
$("check-again").addEventListener("click", boot);
$("discard-preview").addEventListener("click", () => {
  state.preview = null;
  show("upload");
});
$("decline-back").addEventListener("click", () => show("upload"));
$("confirm-read").addEventListener("change", () => {
  $("confirm-continue").disabled = !$("confirm-read").checked;
});
$("check-form").addEventListener("submit", onConfirm);
$("context-form").addEventListener("submit", onContext);
$("chat-form").addEventListener("submit", onSend);
$("download-summary").addEventListener("click", () => {
  if (state.payload) downloadSummary(currentReport());
});
$("upload-another").addEventListener("click", () => show("upload"));
$("delete-one").addEventListener("click", onDeleteOne);
$("delete-all").addEventListener("click", onDeleteAll);

async function boot() {
  if (state.heartbeat) clearInterval(state.heartbeat);
  state.key = await loadSessionKey();
  if (!state.key && otherTabIsOpen()) {
    showOtherTab();
    return;
  }
  state.heartbeat = startLockHeartbeat();
  state.library = await loadLibrary();
  await renderFixtureList();
  if (!state.key) {
    await purgeUnreadable();
    state.shells = [];
    state.openId = null;
    state.payload = null;
    renderSavedList();
    show("upload");
    return;
  }
  await loadShells();
  renderSavedList();
  if (!state.shells.length) {
    show("upload");
    return;
  }
  await openShell(state.shells[state.shells.length - 1].id);
}

async function loadLibrary() {
  try {
    const response = await fetch("/corpus/passages.json");
    if (!response.ok) return [];
    const data = await response.json();
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}

async function onFile(event) {
  const holder = { file: event.target.files?.[0] || null };
  event.target.value = "";
  await takeFile(holder);
}

function onDragOver(event) {
  event.preventDefault();
  $("drop-zone").classList.add("dragover");
}

async function onDrop(event) {
  event.preventDefault();
  $("drop-zone").classList.remove("dragover");
  const named = fixtureIdFromName(event.dataTransfer?.getData("application/x-carepath-fixture"));
  if (named) {
    await takeFixture(named);
    return;
  }
  const file = event.dataTransfer?.files?.[0];
  if (file) await takeFile({ file });
}

async function takeFile(holder) {
  const status = $("upload-status");
  status.textContent = "";
  const named = fixtureIdFromName(holder.file?.name);
  if (named) {
    discardOriginal(holder);
    await takeFixture(named);
    return;
  }
  const kind = classifyFile(holder.file);
  if (kind === "rejected") {
    status.textContent = "Choose a PNG or JPEG photo, or a synthetic report such as S02.pdf.";
    discardOriginal(holder);
    return;
  }
  if (kind === "pdf") {
    status.textContent = PDF_MESSAGE;
    discardOriginal(holder);
    return;
  }
  const problem = sizeProblem(holder.file);
  if (problem === "empty") {
    status.textContent = "That file is empty. Nothing was uploaded.";
    discardOriginal(holder);
    return;
  }
  if (problem === "large") {
    status.textContent = "That photo is over 5 MB. Nothing was uploaded.";
    discardOriginal(holder);
    return;
  }
  status.textContent = "Reading the photo. Personal details are removed before you see a preview.";
  try {
    const lab = await requestAnonymisation(holder.file);
    discardOriginal(holder);
    openPreview(lab);
  } catch (error) {
    discardOriginal(holder);
    status.textContent =
      error.reason === "unreadable"
        ? UNREADABLE_MESSAGE
        : error.reason === "large"
          ? "That photo is too large. Nothing was saved."
          : "CarePath could not read that photo, so it will not guess. Nothing was saved.";
  }
}

async function takeFixture(id) {
  const status = $("upload-status");
  status.textContent = `Reading ${id}. Only the printed results are used.`;
  try {
    const fixture = await fetchFixture(id);
    openPreview(fixture.lab, { ageBand: fixture.ageBand, context: fixture.context });
  } catch (error) {
    status.textContent =
      error.reason === "unreadable"
        ? UNREADABLE_MESSAGE
        : "That synthetic report could not be read. Nothing was saved.";
  }
}

async function renderFixtureList() {
  const list = $("fixture-list");
  const fixtures = await fetchCatalog();
  list.replaceChildren();
  for (const fixture of fixtures) {
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.draggable = true;
    const title = document.createElement("span");
    title.textContent = fixture.label;
    const detail = document.createElement("small");
    detail.textContent = fixture.detail;
    button.append(title, detail);
    button.addEventListener("click", () => takeFixture(fixture.id));
    button.addEventListener("dragstart", (event) => {
      event.dataTransfer.setData("application/x-carepath-fixture", fixture.id);
      event.dataTransfer.setData("text/plain", fixture.fileName || fixture.id);
    });
    item.append(button);
    list.append(item);
  }
}

function openPreview(lab, hints = null) {
  state.preview = lab;
  state.hints = hints;
  $("confirm-read").checked = false;
  $("confirm-continue").disabled = true;
  const age = hints?.ageBand || "unset";
  const ageInput = $("check-form").querySelector(`input[name="age"][value="${age}"]`);
  if (ageInput) ageInput.checked = true;
  $("check-status").textContent = "";
  renderPreview(lab);
  show("check");
}

function renderPreview(lab) {
  const root = $("preview-rows");
  root.replaceChildren();
  const unsure = lab.results.some((row) => row.needsCheck || !String(row.unit || "").trim());
  $("check-status").textContent = unsure
    ? "Some of this was hard to read. Please correct the highlighted rows so they match your report. Nothing is stored until you tick the box."
    : "";
  lab.results.forEach((row, index) => {
    const block = document.createElement("div");
    block.className = "preview-row";
    if (row.needsCheck || !String(row.unit || "").trim()) block.classList.add("needs-check");
    block.dataset.index = String(index);
    block.append(
      field("Test", "testName", row.testName, "text"),
      field("Value", "value", String(row.value), "number"),
      field("Unit", "unit", row.unit, "text", block.classList.contains("needs-check") ? "From your report" : ""),
      field("Range low", "low", row.referenceRange ? String(row.referenceRange.low) : "", "number"),
      field("Range high", "high", row.referenceRange ? String(row.referenceRange.high) : "", "number"),
    );
    const flag = document.createElement("p");
    flag.className = "flag";
    block.append(flag);
    const refresh = (fromUser) => {
      const edited = readRow(block);
      if (fromUser && !edited.error) block.classList.remove("needs-check");
      flag.textContent = block.classList.contains("needs-check")
        ? "Please match this to your report."
        : edited.error
          ? edited.error
          : `On the report: ${labelFlag(edited.flag)}`;
      if (fromUser && !$("preview-rows").querySelector(".needs-check")) $("check-status").textContent = "";
    };
    block.addEventListener("input", () => refresh(true));
    refresh(false);
    root.append(block);
  });
}

function field(label, name, value, type, placeholder = "") {
  const wrap = document.createElement("label");
  wrap.textContent = label;
  const input = document.createElement("input");
  input.name = name;
  input.type = type;
  input.value = value;
  input.autocomplete = "off";
  if (placeholder) input.placeholder = placeholder;
  if (type === "number") input.step = "any";
  wrap.append(input);
  return wrap;
}

function readRow(block) {
  const valueOf = (name) => block.querySelector(`[name="${name}"]`).value;
  return rowFromFields({
    testName: valueOf("testName"),
    value: valueOf("value"),
    unit: valueOf("unit"),
    low: valueOf("low"),
    high: valueOf("high"),
  });
}

function labelFlag(flag) {
  if (flag === "low") return "low";
  if (flag === "high") return "high";
  if (flag === "normal") return "inside the printed range";
  return "no range to compare";
}

async function onConfirm(event) {
  event.preventDefault();
  const status = $("check-status");
  if (!mayStore($("confirm-read").checked)) {
    status.textContent = "Tick the box after you have checked the numbers. Nothing has been stored.";
    return;
  }
  const rows = [];
  for (const block of $("preview-rows").querySelectorAll(".preview-row")) {
    const row = readRow(block);
    if (row.error) {
      status.textContent = row.error;
      return;
    }
    rows.push(row);
  }
  const lab = labFromRows(rows);
  if (lab.error) {
    status.textContent = lab.error;
    return;
  }
  const ageBand = new FormData($("check-form")).get("age");
  if (ageBand === "under-18") {
    state.preview = null;
    $("decline-copy").textContent = UNDERAGE_MESSAGE;
    show("decline");
    return;
  }
  try {
    state.key = await createSessionKey();
    state.openId = crypto.randomUUID();
    state.payload = {
      version: 1,
      lab,
      context: { ageBand, duffyNull: "unset", pregnant: "unset", hormones: "unset" },
      contextComplete: false,
      transcript: [],
    };
    state.preview = null;
    await persist();
  } catch {
    state.preview = lab;
    status.textContent = "CarePath could not store this report in the browser. Nothing was saved on the server.";
    return;
  }
  resetContextForm();
  show("context");
}

function resetContextForm() {
  const hints = state.hints?.context || {};
  for (const name of ["pregnant", "hormones", "duffy"]) {
    const value = hints[name] || "unset";
    const input = $("context-form").querySelector(`input[name="${name}"][value="${value}"]`);
    if (input) input.checked = true;
  }
}

async function onContext(event) {
  event.preventDefault();
  const form = new FormData(event.target);
  state.payload.context = {
    ...state.payload.context,
    pregnant: form.get("pregnant"),
    hormones: form.get("hormones"),
    duffyNull: form.get("duffy"),
  };
  state.payload.contextComplete = true;
  await persist();
  showResults();
}

function currentReport() {
  return prepareReport(state.payload.lab, state.payload.context, state.library);
}

function showResults() {
  const prepared = currentReport();
  const banner = $("urgent-banner");
  if (prepared.cards.some((card) => card.urgent)) {
    banner.hidden = false;
    banner.textContent = `${URGENT_MESSAGE} This notice was chosen by a fixed rule, not by the explanation model.`;
  } else {
    banner.hidden = true;
    banner.textContent = "";
  }
  renderUncertainties($("uncertainties"), prepared.uncertainties);
  renderCards($("cards"), prepared.cards);
  renderTranscript($("transcript"), state.payload.transcript);
  $("chat-status").textContent = "";
  $("delete-status").textContent = "";
  show("results");
}

async function onSend(event) {
  event.preventDefault();
  const question = $("question").value.trim();
  const status = $("chat-status");
  if (!question) {
    status.textContent = "Write a question first.";
    return;
  }
  if (question.length > 2000) {
    status.textContent = "Please shorten that question to 2000 characters.";
    return;
  }
  const button = $("send-question");
  button.disabled = true;
  status.textContent = "";
  const prepared = currentReport();
  let posted = false;
  try {
    state.payload.transcript = appendTurn(state.payload.transcript, "user", question);
    appendBubble($("transcript"), "user", question);
    $("question").value = "";
    let reply;
    if (prepared.cards.some((card) => card.urgent) && mentionsPotassium(question)) {
      reply = { covered: false, explanation: URGENT_MESSAGE, passages: [] };
    } else {
      const lab = labForChat(prepared);
      if (!lab) {
        reply = { covered: false, explanation: FIXED_MESSAGE, passages: [] };
      } else {
        reply = await postChatTurn(chatRequest(lab, question, state.payload.transcript.slice(0, -1)));
      }
    }
    posted = true;
    const content = reply.covered ? reply.explanation : reply.explanation || FIXED_MESSAGE;
    const item = appendBubble($("transcript"), "assistant", content);
    const shown = reply.covered ? renderPassages(reply.passages) : null;
    if (shown) item.append(shown);
    discardPassages(reply);
    state.payload.transcript = appendTurn(state.payload.transcript, "assistant", content);
    await persist();
  } catch (error) {
    if (!posted) {
      state.payload.transcript = state.payload.transcript.slice(0, -1);
      $("transcript").lastElementChild?.remove();
      status.textContent =
        error.reason === "unavailable" || error.reason === "unreachable"
          ? "The explanation service is unavailable. This question was not saved on the server."
          : "CarePath could not send that question. Nothing from it was saved on the server.";
    } else {
      status.textContent = "The reply is on screen, but this browser could not save it.";
    }
  } finally {
    button.disabled = false;
  }
}

async function persist() {
  const packed = await encryptJson(state.key, state.payload);
  const record = {
    id: state.openId,
    lastUsed: stamp(),
    iv: packed.iv,
    ciphertext: packed.ciphertext,
  };
  await putRecord(record);
  const existing = state.shells.find((shell) => shell.id === record.id);
  if (existing) existing.lastUsed = record.lastUsed;
  else state.shells.push({ id: record.id, lastUsed: record.lastUsed });
  renderSavedList();
}

async function loadShells() {
  const records = await getAllRecords();
  const removed = await purgeExpired(records);
  state.shells = records
    .filter((record) => !removed.includes(record.id))
    .map((record) => ({ id: record.id, lastUsed: record.lastUsed }))
    .sort((a, b) => a.lastUsed - b.lastUsed);
}

async function openShell(id) {
  const records = await getAllRecords();
  const record = records.find((item) => item.id === id);
  if (!record) return;
  try {
    state.payload = await decryptJson(state.key, record.iv, record.ciphertext);
  } catch {
    await deleteFile(id);
    state.shells = state.shells.filter((shell) => shell.id !== id);
    renderSavedList();
    show("upload");
    $("upload-status").textContent = "One saved report could not be read, so it was deleted.";
    return;
  }
  state.openId = id;
  if (!state.payload.contextComplete) {
    resetContextForm();
    show("context");
    return;
  }
  showResults();
}

function renderSavedList() {
  const list = $("saved-reports");
  const wrap = $("saved-list");
  list.replaceChildren();
  wrap.hidden = state.shells.length === 0;
  for (const shell of state.shells) {
    const item = document.createElement("li");
    const label = document.createElement("span");
    const when = new Date(shell.lastUsed).toLocaleString();
    label.textContent = `Report saved ${when}`;
    const open = document.createElement("button");
    open.type = "button";
    open.className = "secondary";
    open.textContent = shell.id === state.openId ? "Open again" : "Open";
    open.addEventListener("click", () => openShell(shell.id));
    item.append(label, open);
    list.append(item);
  }
}

async function onDeleteOne() {
  if (!state.openId) return;
  const gone = await deleteFile(state.openId);
  state.shells = state.shells.filter((shell) => shell.id !== state.openId);
  state.openId = null;
  state.payload = null;
  renderSavedList();
  show("upload");
  $("upload-status").textContent = gone
    ? "Checked. That report is gone."
    : "CarePath could not confirm the delete. Try Delete all.";
}

async function onDeleteAll() {
  const clear = await deleteAll();
  state.key = null;
  state.shells = [];
  state.openId = null;
  state.payload = null;
  renderSavedList();
  show("upload");
  $("upload-status").textContent = clear
    ? "Checked. No saved reports remain in this tab."
    : "CarePath could not confirm that every report was removed.";
}

boot().catch(() => {
  $("upload-status").textContent = "CarePath could not open browser storage.";
  show("upload");
});

const form = document.querySelector("#job-form");
const submitButton = document.querySelector("#submit");
const jobsEl = document.querySelector("#jobs");
const refreshButton = document.querySelector("#refresh");
const imageInput = document.querySelector("#image");
const fileLabel = document.querySelector("#file-label");
const examplesEl = document.querySelector("#examples");
const resetParamsButton = document.querySelector("#reset-params");

let activeJobId = null;
let pollTimer = null;

function fmtTime(ts) {
  if (!ts) return "";
  return new Date(ts * 1000).toLocaleString();
}

function stateClass(status) {
  return ["done", "failed", "running", "queued"].includes(status) ? status : "";
}

function statusLabel(status) {
  const labels = {
    queued: "排队中",
    running: "运行中",
    done: "完成",
    failed: "失败",
  };
  return labels[status] || status;
}

function escapeHtml(value) {
  return String(value || "").replace(/[&<>"']/g, (char) => {
    const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" };
    return map[char];
  });
}

function renderStages(job) {
  const stages = job.stages || [];
  return `
    <div class="stage-list">
      ${stages
        .map(
          (stage) => `
            <span class="stage-chip ${stage.state}">
              <span class="stage-dot"></span>
              ${escapeHtml(stage.label)}
            </span>
          `
        )
        .join("")}
    </div>
  `;
}

function applyParams(params) {
  if (!params) return;
  Object.entries(params).forEach(([key, value]) => {
    const input = form.elements.namedItem(key);
    if (input) input.value = value;
  });
}

function renderProgress(job) {
  const progress = Math.max(0, Math.min(100, Number(job.progress || 0)));
  return `
    <div class="progress-wrap" aria-label="progress">
      <div class="progress-meta">
        <span>${escapeHtml(job.stage_label || job.stage || "")}</span>
        <span>${progress}%</span>
      </div>
      <div class="progress-track">
        <div class="progress-bar ${job.status === "failed" ? "failed" : ""}" style="width: ${progress}%"></div>
      </div>
    </div>
  `;
}

function renderJob(job) {
  const status = job.status || "unknown";
  const previews = job.outputs?.previews || {};
  const params = job.params || {};
  const viewNames = ["front", "right", "back", "left"];
  const viewLabels = { front: "正面", right: "右侧", back: "背面", left: "左侧" };
  const previewHtml = viewNames
    .filter((name) => previews[name])
    .map(
      (name) => `
        <figure>
          <img src="${previews[name]}?t=${job.updated_at || Date.now()}" alt="${name}" />
          <figcaption>${viewLabels[name] || name}</figcaption>
        </figure>
      `
    )
    .join("");

  const actions = job.outputs
    ? `
      <div class="actions">
        <a href="${job.outputs.blend}">下载 .blend</a>
        <a href="${job.outputs.input}">输入图</a>
        <a href="${job.outputs.rgb}">裁剪图</a>
      </div>
    `
    : "";

  const error = job.error ? `<p class="meta error-text">错误：${escapeHtml(job.error)}</p>` : "";

  return `
    <article class="job" data-id="${job.id}">
      <div class="job-top">
        <div>
          <h3>${escapeHtml(job.filename || job.id)}</h3>
          <div class="meta">
            ID ${escapeHtml(job.id)} · ${fmtTime(job.created_at)}<br />
            随机种子 ${params.seed}，采样步数 ${params.steps}，引导 ${params.cfg}，裁剪 ${params.crop}，密度 ${params.upsample}<br />
            解码分块 ${params.decode_chunks || 10}
          </div>
        </div>
        <div class="state ${stateClass(status)}">${escapeHtml(statusLabel(status))}</div>
      </div>
      ${renderProgress(job)}
      ${renderStages(job)}
      ${error}
      ${previewHtml ? `<div class="previews">${previewHtml}</div>` : ""}
      ${actions}
    </article>
  `;
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return response.json();
}

async function refreshJobs() {
  if (activeJobId) {
    const job = await fetchJson(`/api/jobs/${activeJobId}`);
    jobsEl.innerHTML = renderJob(job);
    if (job.status === "done" || job.status === "failed") {
      activeJobId = null;
      clearInterval(pollTimer);
      pollTimer = null;
      await refreshJobs();
    }
    return;
  }

  const data = await fetchJson("/api/jobs");
  jobsEl.innerHTML = data.jobs.length
    ? data.jobs.map((job) => renderJob(job)).join("")
    : `<p class="meta">暂无任务。</p>`;
}

imageInput.addEventListener("change", () => {
  fileLabel.textContent = imageInput.files[0]?.name || "选择或拖入人像图片";
});

resetParamsButton?.addEventListener("click", () => {
  Array.from(form.elements).forEach((element) => {
    if (!element.name || element.type === "file") return;
    if ("defaultValue" in element) element.value = element.defaultValue;
  });
});

async function loadExamples() {
  if (!examplesEl) return;
  try {
    const data = await fetchJson("/api/examples");
    examplesEl.innerHTML = data.examples.length
      ? data.examples
          .map(
            (example) => `
              <button
                class="example-thumb"
                type="button"
                data-name="${escapeHtml(example.name)}"
                data-url="${example.url}"
                data-params="${escapeHtml(JSON.stringify(example.params || {}))}"
              >
                <img src="${example.url}" alt="${escapeHtml(example.name)}" />
                <span>${escapeHtml(example.name)}</span>
              </button>
            `
          )
          .join("")
      : `<p class="meta">没有找到示例图片。</p>`;
  } catch (error) {
    examplesEl.innerHTML = `<p class="meta">${escapeHtml(error.message)}</p>`;
  }
}

examplesEl?.addEventListener("click", async (event) => {
  const button = event.target.closest(".example-thumb");
  if (!button) return;
  const name = button.dataset.name;
  const url = button.dataset.url;
  const params = JSON.parse(button.dataset.params || "{}");
  const response = await fetch(url);
  if (!response.ok) {
    alert(`示例图片读取失败：${name}`);
    return;
  }
  const blob = await response.blob();
  const file = new File([blob], name, { type: blob.type || "image/png" });
  const transfer = new DataTransfer();
  transfer.items.add(file);
  imageInput.files = transfer.files;
  fileLabel.textContent = `已选择示例：${name}`;
  applyParams(params);
  document.querySelectorAll(".example-thumb.selected").forEach((node) => node.classList.remove("selected"));
  button.classList.add("selected");
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  submitButton.disabled = true;
  submitButton.textContent = "已提交";
  try {
    const body = new FormData(form);
    const created = await fetchJson("/api/jobs", { method: "POST", body });
    activeJobId = created.id;
    await refreshJobs();
    pollTimer = setInterval(refreshJobs, 2000);
  } catch (error) {
    alert(error.message);
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = "开始生成";
  }
});

refreshButton.addEventListener("click", refreshJobs);
loadExamples();
refreshJobs().catch((error) => {
  jobsEl.innerHTML = `<p class="meta">${escapeHtml(error.message)}</p>`;
});

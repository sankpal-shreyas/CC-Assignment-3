// Talks to the API Gateway endpoints set up in assignment step 4.
// We use fetch() directly so the page works without bundling the
// generated JS SDK. The SDK is still generated and committed under
// /front-end/apigClient/ to satisfy step 4.e.

const cfg = window.PHOTO_APP_CONFIG || {};

const $ = (id) => document.getElementById(id);

function setStatus(el, msg, kind) {
  el.textContent = msg || "";
  el.className = "status" + (kind ? " " + kind : "");
}

async function search(q) {
  const url = `${cfg.API_BASE}/search?q=${encodeURIComponent(q)}`;
  const res = await fetch(url, {
    method: "GET",
    headers: { "x-api-key": cfg.API_KEY },
  });
  if (!res.ok) throw new Error(`search failed: ${res.status}`);
  return res.json();
}

async function upload(file, customLabels) {
  // PUT directly to the API Gateway S3 proxy. The API maps
  // /photos/{bucket}/{key} -> S3 PutObject and forwards the
  // x-amz-meta-customLabels header through to the object.
  const safeKey = encodeURIComponent(file.name);
  const url = `${cfg.API_BASE}/photos/${cfg.PHOTOS_BUCKET}/${safeKey}`;
  const headers = {
    "x-api-key": cfg.API_KEY,
    "Content-Type": file.type || "application/octet-stream",
  };
  if (customLabels) headers["x-amz-meta-customLabels"] = customLabels;

  const res = await fetch(url, { method: "PUT", headers, body: file });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`upload failed: ${res.status} ${text}`);
  }
}

function render(results) {
  const root = $("results");
  root.innerHTML = "";
  if (!results.length) {
    root.innerHTML = '<p class="status">no matches.</p>';
    return;
  }
  for (const r of results) {
    const card = document.createElement("div");
    card.className = "result";
    card.innerHTML = `
      <img src="${r.url}" alt="" loading="lazy">
      <div class="labels">${(r.labels || []).join(", ")}</div>
    `;
    root.appendChild(card);
  }
}

$("search-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = $("q").value.trim();
  if (!q) return;
  const status = $("search-status");
  setStatus(status, "searching...");
  try {
    const data = await search(q);
    setStatus(status, `${(data.results || []).length} result(s)`, "ok");
    render(data.results || []);
  } catch (err) {
    setStatus(status, err.message, "error");
  }
});

$("upload-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const file = $("file").files[0];
  if (!file) return;
  const labels = $("labels").value.trim();
  const status = $("upload-status");
  const btn = e.target.querySelector("button");
  btn.disabled = true;
  setStatus(status, "uploading...");
  try {
    await upload(file, labels);
    setStatus(status, `uploaded ${file.name}. give it a few seconds to index, then search.`, "ok");
    e.target.reset();
  } catch (err) {
    setStatus(status, err.message, "error");
  } finally {
    btn.disabled = false;
  }
});

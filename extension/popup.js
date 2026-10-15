const token = document.querySelector("#token");
const project = document.querySelector("#project");
const result = document.querySelector("#result");
chrome.storage.local.get(["token","project"], v => {
  token.value = v.token || "";
  project.value = v.project || "";
});
document.querySelector("#save").onclick = () =>
  chrome.storage.local.set({token:token.value.trim(),project:project.value.trim()}, () => {
    result.textContent = "Settings saved locally.";
  });
async function call(path, body) {
  const v = await chrome.storage.local.get(["token","project"]);
  if (!v.token) throw new Error("Enter your local agent token first.");
  const options = {headers:{"Authorization":"Bearer "+v.token}};
  if (body) {
    options.method = "POST";
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const r = await fetch("http://127.0.0.1:43127"+path, options);
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || "Request failed");
  return data;
}
document.querySelector("#health").onclick = async () => {
  try { result.textContent = JSON.stringify(await call("/health"),null,2); }
  catch(e) { result.textContent = e.message; }
};
document.querySelector("#diagnostics").onclick = async () => {
  try {
    const v = await chrome.storage.local.get(["project"]);
    result.textContent = JSON.stringify(await call("/diagnostics",{project:v.project}),null,2);
  } catch(e) { result.textContent = e.message; }
};

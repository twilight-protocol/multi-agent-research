// 统一带状态码检查：后端没起来时 fetch 会 resolve 一个 500/502，直接 .json() 会抛异常，
// 调用方拿不到数组 → 页面白屏。这里改成失败返回空数组，UI 至少还能用
async function getJson(url, init) {
  const res = await fetch(url, init);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function listSessions() {
  try {
    return await getJson("/api/sessions");
  } catch {
    return [];
  }
}

export async function getMessages(id) {
  try {
    return await getJson(`/api/sessions/${id}`);
  } catch {
    return [];
  }
}

export const delSession = (id) =>
  fetch(`/api/sessions/${id}`, { method: "DELETE" });

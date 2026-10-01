// SSE over POST 客户端。
// 为什么不用 EventSource：EventSource 只支持 GET，而后端 /stream 与 /resume 都是 POST。
// 事件名与 backend/api/research.py 的 sse_frame() 一一对应：
// progress | interrupt | done | error

/**
 * 发起一次研究流，按事件名回调。
 * @param {string} path  接口路径，如 "/api/research/stream"
 * @param {object} body  请求体
 * @param {{progress?:Function, interrupt?:Function, done?:Function, error?:Function}} on
 */
export async function streamResearch(path, body, on) {
  const res = await fetch(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(body),
  });

  // 限流器返回 429 或后端 500 时，这里拿到的是 JSON 而不是流
  if (!res.ok) {
    throw new Error(`HTTP ${res.status} ${await res.text()}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    // stream:true 是必需的：中文是多字节，chunk 边界可能把一个字劈成两半
    buf += decoder.decode(value, { stream: true });

    // 后端以 "\n\n" 分包；data 里的换行已被 json.dumps 转义成 \n，所以不会误切
    let idx;
    while ((idx = buf.indexOf("\n\n")) !== -1) {
      const frame = parseFrame(buf.slice(0, idx));
      buf = buf.slice(idx + 2);
      if (frame) on[frame.event]?.(frame.data);
    }
  }
}

// 一帧长这样：event:progress\ndata:{"node":"write","label":"正在撰写报告"}
function parseFrame(raw) {
  let event = "message";
  const data = [];
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).trim());
  }
  if (!data.length) return null;
  return { event, data: JSON.parse(data.join("\n")) };
}

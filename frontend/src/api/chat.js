export async function streamChat({
  message,
  threadId,
  onDelta,
  onDone,
  onError,
  signal,
}) {
  const res = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, thread_id: threadId }),
    signal,
  });
  if (!res.ok || !res.body) {
    onError?.(`HTTP ${res.status}`);
    return;
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const frames = buf.split("\n\n");
    buf = frames.pop();
    for (const frame of frames) {
      dispatch(frame, { onDelta, onDone, onError });
    }
  }
  buf += decoder.decode();
  if (buf.trim()) dispatch(buf, { onDelta, onDone, onError });
}

function dispatch(frame, { onDelta, onDone, onError }) {
  let event = "message";
  const dataLines = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }
  if (!dataLines.length) return;
  const raw = dataLines.join("\n");
  let payload;
  try {
    payload = JSON.parse(raw);
  } catch {
    console.warn("[SSE]无法解析的帧: ", raw);
    return;
  }
  if (event === "message") onDelta?.(payload.delta ?? "");
  else if (event === "done") onDone?.(payload.thread_id);
  else if (event === "error") onError?.(payload.detail);
}

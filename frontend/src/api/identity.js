// 匿名用户标识：首次访问生成一个随机 id 存 localStorage，之后所有请求用 X-User-Id 带上。
//
// 为什么不用 crypto.randomUUID()：它是 [SecureContext] 限定的 API，
// 而线上是 http://<IP>:8001（非 https、非 localhost），在那个上下文里它是 undefined。
// getRandomValues 没有这个限制，所以在 http 下也能用。
//
// 注意：这不是登录，id 是客户端自报的 —— 换一个 id 就能看到另一份数据。
// 定位是「数据隔离」而不是「权限隔离」，见 面试台账.md §5.3.3。

const KEY = "mar_user_id";

function randomId() {
  const buf = new Uint8Array(16);
  crypto.getRandomValues(buf);
  return Array.from(buf, (b) => b.toString(16).padStart(2, "0")).join("");
}

export function getUserId() {
  let id = localStorage.getItem(KEY);
  if (!id) {
    id = randomId();
    localStorage.setItem(KEY, id);
  }
  return id;
}

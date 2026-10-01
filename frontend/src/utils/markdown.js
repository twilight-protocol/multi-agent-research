// 极简 Markdown → HTML。覆盖报告实际会出现的语法：
// ## 标题 / - 列表 / **加粗** / 出处引用。
//
// 有意的取舍：不引 marked + DOMPurify（多两个依赖、多一层构建风险），
// 先把在线地址跑起来；真要支持表格/代码块再换库。
// 代价：语法支持不全；收益是零依赖 + 正则可完全预测。

const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;" };

// 一条出处：本地文档 [文件名 第N页] 或网页 [web: url]。
// 页码可能是范围（第1-2页），连接号有 - – — ~ 至 多种写法，全都要认：
// Prompt 要求「原样照抄笔记」，模型就会把笔记里的各种写法原样抄进来
const DOC_REF = /^(.+?)\s*(第\s*\d+\s*(?:[-–—~至]\s*\d+\s*)?页)$/;
const WEB_REF = /^web:\s*(\S+)$/i;
// 一条 finding 的 evidence 若被模型用分号拼成一条，这里按分号拆开
const SPLIT_REF = /\s*[；;、]\s*/;

export function renderMarkdown(md) {
  if (!md) return "";

  const out = [];
  let inList = false;

  for (const line of md.split("\n")) {
    const t = line.trim();

    const li = t.match(/^[-*]\s+(.+)$/);
    if (li) {
      if (!inList) {
        out.push("<ul>");
        inList = true;
      }
      out.push(`<li>${inline(li[1])}</li>`);
      continue;
    }
    if (inList) {
      out.push("</ul>");
      inList = false;
    }
    if (!t) continue;

    const h = t.match(/^(#{1,4})\s+(.+)$/);
    if (h) {
      const lv = h[1].length;
      out.push(`<h${lv}>${inline(h[2])}</h${lv}>`);
      continue;
    }
    out.push(`<p>${inline(t)}</p>`);
  }

  if (inList) out.push("</ul>");
  return out.join("\n");
}

function inline(s) {
  // 顺序不能反：先转义，再插标签；否则 <b> 会被一起转义掉
  return s
    .replace(/[&<>]/g, (c) => ESC[c])
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\[([^\[\]]+)\]/g, renderBracket);
}

// 把 [a；b；c] 拆成三个独立小标签。
// 为什么必须拆：后端 evidence 字段是 list，但 _render_report 用空格拼成一行，
// 模型又常把多条出处用「；」塞进同一个元素——一起渲染就成了一个大方块，
// 读不出到底有几条出处（也看不出哪些是页码范围）。
function renderBracket(whole, inner) {
  const chips = inner.split(SPLIT_REF).map(refChip).filter(Boolean);
  if (chips.length) return chips.join("");

  // 不是出处的方括号 = 模型自己加的批注（如 [analysis note: ...]）。
  // 标成弱化样式让它一眼不像正文；真正的修法是 Prompt 里禁掉（见 node.py）
  if (inner.includes(":") || inner.includes("：")) {
    return `<span class="mnote">${inner}</span>`;
  }
  return whole;
}

function refChip(part) {
  const web = part.match(WEB_REF);
  if (web) {
    const url = web[1];
    // 只认 http/https：锚点 href 来自模型输出，放行 javascript: 就是 XSS
    if (!/^https?:\/\//i.test(url)) return `<cite>${part}</cite>`;
    let host = url;
    try {
      // 只显示域名：一条 finding 常有 3~4 个出处，贴全 URL 会撑爆版面
      host = new URL(url).host;
    } catch {
      /* URL 解析失败就退回原文 */
    }
    return `<cite class="web"><a href="${url}" target="_blank" rel="noopener noreferrer">${host}</a></cite>`;
  }
  const doc = part.match(DOC_REF);
  if (doc) return `<cite>${doc[1]} ${doc[2]}</cite>`;
  return null;
}

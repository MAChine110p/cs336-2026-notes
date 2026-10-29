from __future__ import annotations

import ast
import html
import re
from pathlib import Path


ROOT = Path(__file__).parent
SOURCE = ROOT / "lectures" / "lecture_01.py"
OUTPUT = ROOT / "index.html"
ASSET_ROOT = ROOT / "lectures" / "images"
REFERENCE_SOURCE = ROOT / "lectures" / "references.py"


def load_reference_urls() -> dict[str, str]:
    if not REFERENCE_SOURCE.exists():
        return {}
    source = REFERENCE_SOURCE.read_text(encoding="utf-8")
    return {
        name: url
        for name, url in re.findall(
            r"^(\w+)\s*=\s*(?:url_reference|Reference)\(\s*[\"'](https?://[^\"']+)",
            source,
            flags=re.MULTILINE,
        )
    }


def literal(node: ast.AST | None, references: dict[str, str]) -> str | int | None:
    if node is None:
        return None
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return references.get(node.id, node.id)
    if isinstance(node, ast.JoinedStr):
        return "".join(str(literal(value.value, references)) for value in node.values)
    return None


def collect_blocks(source: str) -> list[tuple[str, str]]:
    tree = ast.parse(source)
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    references = load_reference_urls()
    blocks: list[tuple[str, str]] = []

    def visit_statements(statements: list[ast.stmt]) -> None:
        for statement in statements:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if isinstance(statement, (ast.For, ast.While, ast.If, ast.With, ast.Try)):
                for body in (
                    getattr(statement, "body", []),
                    getattr(statement, "orelse", []),
                    getattr(statement, "finalbody", []),
                ):
                    visit_statements(body)
                for handler in getattr(statement, "handlers", []):
                    visit_statements(handler.body)
                continue
            if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
                continue
            call = statement.value
            name = call.func.id if isinstance(call.func, ast.Name) else ""
            if name in {"text", "image", "link", "article_link", "post_link", "video_link"}:
                args = [literal(argument, references) for argument in call.args]
                keywords = {
                    keyword.arg: literal(keyword.value, references)
                    for keyword in call.keywords
                    if keyword.arg
                }
                if name == "text" and args and isinstance(args[0], str):
                    blocks.append(("text", args[0]))
                elif name == "image" and args and isinstance(args[0], str):
                    blocks.append(("image", args[0]))
                elif name in {"article_link", "post_link", "video_link"} and args:
                    blocks.append(("link", str(args[0])))
                elif name == "link":
                    url = keywords.get("url") or (args[0] if args else None)
                    title = keywords.get("title") or "参考资料"
                    if isinstance(url, str):
                        blocks.append(("link", f"{title}\t{url}"))
            elif name in functions:
                visit_statements(functions[name].body)

    main = functions.get("main")
    if main:
        visit_statements(main.body)
    return blocks


def inline_markdown(value: str) -> str:
    escaped = html.escape(value, quote=False)
    escaped = re.sub(
        r"\[([^]]+)\]\((https?://[^)]+)\)",
        r'<a href="\2" target="_blank" rel="noreferrer">\1</a>',
        escaped,
    )
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    return escaped


def render_content(blocks: list[tuple[str, str]]) -> str:
    output: list[str] = []
    in_list = False
    section = 0

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            output.append("</ul>")
            in_list = False

    for kind, value in blocks:
        if kind == "text":
            if value.startswith("## "):
                close_list()
                if section:
                    output.append("</section>")
                section += 1
                title = inline_markdown(value[3:])
                output.append(
                    f'<section class="note-section" id="section-{section}">'
                    f"<h2>{title}</h2>"
                )
                continue
            if value.startswith("### "):
                close_list()
                output.append(f"<h3>{inline_markdown(value[4:])}</h3>")
                continue
            if value.startswith("- "):
                if not in_list:
                    output.append("<ul>")
                    in_list = True
                output.append(f"<li>{inline_markdown(value[2:])}</li>")
                continue
            close_list()
            output.append(f"<p>{inline_markdown(value)}</p>")
        elif kind == "image":
            close_list()
            source = value if value.startswith(("http://", "https://")) else f"lectures/{value}"
            output.append(
                f'<figure><img src="{html.escape(source, quote=True)}" '
                f'alt="讲义插图" loading="lazy"></figure>'
            )
        elif kind == "link":
            close_list()
            title, url = value.split("\t", 1) if "\t" in value else ("参考资料", value)
            output.append(
                f'<p class="resource"><a href="{html.escape(url, quote=True)}" '
                f'target="_blank" rel="noreferrer">↗ {html.escape(title)}</a></p>'
            )
    close_list()
    if section:
        output.append("</section>")
    return "\n".join(output)


def build() -> None:
    blocks = collect_blocks(SOURCE.read_text(encoding="utf-8"))
    content = render_content(blocks)
    page = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="CS336 从零开始构建语言模型：第一讲笔记">
  <title>CS336 · 第一讲笔记</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <header class="hero">
    <div class="hero-inner">
      <p class="eyebrow">CS336 · SPRING 2026</p>
      <h1>从零开始构建语言模型</h1>
      <p class="subtitle">第一讲：概览与分词</p>
      <div class="hero-meta"><span>可执行讲义</span><span>学习笔记</span><span>中文整理</span></div>
    </div>
  </header>
  <button class="outline-trigger" type="button" aria-expanded="false" aria-controls="toc">☰ <span>章节大纲</span></button>
  <div class="outline-backdrop" aria-hidden="true"></div>
  <div class="layout">
    <aside class="sidebar" aria-label="章节大纲">
      <button class="sidebar-toggle" type="button" aria-expanded="false" aria-controls="toc">
        <span class="toggle-icon" aria-hidden="true">‹</span>
        <span class="toggle-label">关闭大纲</span>
      </button>
      <div class="sidebar-title">LECTURE 01</div>
      <nav id="toc" aria-label="章节导航"></nav>
      <a class="source-link" href="https://github.com/stanford-cs336/lectures" target="_blank" rel="noreferrer">查看课程源仓库 ↗</a>
    </aside>
    <main class="content">
      <div class="intro">
        <p>这是一份从 Python 可执行讲义直接渲染的阅读版笔记。沿着章节阅读，文中的论文、视频和课程资料链接会在新标签页打开。</p>
      </div>
      {content}
      <footer>CS336 · Language Modeling from Scratch · Spring 2026</footer>
    </main>
  </div>
  <script>
    const sidebar = document.querySelector('.sidebar');
    const trigger = document.querySelector('.outline-trigger');
    const backdrop = document.querySelector('.outline-backdrop');
    const toggle = document.querySelector('.sidebar-toggle');
    const toc = document.querySelector('#toc');
    const setSidebarState = (open) => {{
      sidebar.classList.toggle('sidebar-open', open);
      backdrop.classList.toggle('backdrop-visible', open);
      trigger.setAttribute('aria-expanded', String(open));
      toggle.setAttribute('aria-expanded', String(open));
      toggle.querySelector('.toggle-label').textContent = '关闭大纲';
      localStorage.setItem('cs336-sidebar-open', String(open));
    }};
    trigger.addEventListener('click', () => setSidebarState(true));
    toggle.addEventListener('click', () => setSidebarState(false));
    backdrop.addEventListener('click', () => setSidebarState(false));
    document.addEventListener('keydown', (event) => {{
      if (event.key === 'Escape') setSidebarState(false);
    }});
    document.querySelectorAll('.note-section').forEach((section) => {{
      const link = document.createElement('a');
      link.href = '#' + section.id;
      link.textContent = section.querySelector('h2').textContent;
      toc.appendChild(link);
    }});
    setSidebarState(localStorage.getItem('cs336-sidebar-open') === 'true');
  </script>
</body>
</html>
"""
    OUTPUT.write_text(page, encoding="utf-8")
    print(f"Rendered {len(blocks)} blocks to {OUTPUT}")


if __name__ == "__main__":
    build()

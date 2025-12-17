import MarkdownIt from 'markdown-it';
import mk from 'markdown-it-katex';
import hljs from 'highlight.js';

function highlightCode(code: string, lang: string): string {
    if (lang && hljs.getLanguage(lang)) {
        return `<pre><code class="hljs">${hljs.highlight(code, { language: lang, ignoreIllegals: true }).value}</code></pre>`;
    }
    return `<pre><code class="hljs">${MarkdownIt().utils.escapeHtml(code)}</code></pre>`;
}

const md: MarkdownIt = new MarkdownIt({
    html: false,
    linkify: true,
    highlight: highlightCode,
}).use(mk);

export function renderMarkdown(text: string): string {
    return md.render(text);
}

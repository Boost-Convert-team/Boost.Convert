import { createServer } from "node:http";
import { readFileSync, existsSync } from "node:fs";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL(".", import.meta.url));
const workspaceRoot = fileURLToPath(new URL("..", import.meta.url));
const templatesDir = join(root, "front_end", "templates");
const staticDir = join(root, "front_end", "static");
const projectPhotosDir = join(workspaceRoot, "fotos projeto");
const port = Number(process.env.PORT || 5173);

const routes = {
    "home.home": "/",
    "home.tools": "/tools",
    "home.conta": "/conta",
    "home.sobre": "/sobre",
    "main.planos": "/planos",
    "auth.login": "/login",
    "auth.registrar": "/registrar",
    "auth.logout": "/logout",
    "auth.google_login": "/login",
    "webhook.payment_webhook": "/checkout",
    "ai_tools.mp4_to_text": "/mp4-to-text",
    "ai_tools.mp4_to_text_download": "/download/mp4-to-text.txt",
    "ai_tools.youtube_analyzer": "/youtube-analyzer",
    "youtube_downloads.download_youtube": "/youtube-download"
};

const tools = [
    { name: "Juntar PDF", slug: "pdf-merge", category: "PDF", icon: "combine", accept: ".pdf" },
    { name: "Dividir PDF", slug: "pdf-split", category: "PDF", icon: "scissors", accept: ".pdf" },
    { name: "Comprimir PDF", slug: "pdf-compress", category: "PDF", icon: "minimize-2", accept: ".pdf" },
    { name: "PDF para DOCX", slug: "pdf-to-docx", category: "PDF", icon: "file-type", accept: ".pdf" },
    { name: "JPG para PNG", slug: "jpg-to-png", category: "Imagem", icon: "image", accept: ".jpg,.jpeg" },
    { name: "PNG para WEBP", slug: "png-to-webp", category: "Imagem", icon: "image", accept: ".png" },
    { name: "MP4 para MP3", slug: "mp4-to-mp3", category: "Video", icon: "music", accept: ".mp4" },
    { name: "MP3 para WAV", slug: "mp3-to-wav", category: "Audio", icon: "audio-waveform", accept: ".mp3" },
    { name: "YouTube Analyzer", slug: "youtube-analyzer", category: "AI", icon: "bot", accept: "URL" }
];

const toolSearchIndex = tools.map((tool) => ({
    label: tool.name,
    category: tool.category,
    icon: tool.icon,
    url: `/tools/${tool.slug}`,
    aliases: tool.slug.replaceAll("-", " ")
}));

function htmlPage(title, content) {
    let base = readFileSync(join(templatesDir, "base.html"), "utf8");
    base = base.replace(/{% block title %}[\s\S]*?{% endblock %}/, title);
    base = base.replace(/{% block content %}[\s\S]*?{% endblock %}/, content);
    return processJinja(base);
}

function renderTemplate(name) {
    const source = readFileSync(join(templatesDir, name), "utf8");
    const title = source.match(/{% block title %}([\s\S]*?){% endblock %}/)?.[1]?.trim() || "Boost.Convert";
    const content = source.match(/{% block content %}([\s\S]*?){% endblock %}/)?.[1] || "";
    return htmlPage(title, content);
}

function processJinja(html) {
    return html
        .replace(/{% if current_user\.is_authenticated %}[\s\S]*?{% else %}([\s\S]*?){% endif %}/g, "$1")
        .replace(/{{\s*tool_search_index\|default\(\[\], true\)\|tojson\s*}}/g, JSON.stringify(toolSearchIndex))
        .replace(/{{\s*url_for\('static',\s*filename='([^']+)'\)\s*}}/g, "/static/$1")
        .replace(/{{\s*url_for\('home\.converter_tool',\s*slug='([^']+)'\)\s*}}/g, "/tools/$1")
        .replace(/{{\s*url_for\('([^']+)'\)\s*}}/g, (_, endpoint) => routes[endpoint] || "#")
        .replace(/{#[\s\S]*?#}/g, "")
        .replace(/{%[\s\S]*?%}/g, "")
        .replace(/{{[\s\S]*?}}/g, "");
}

function renderTools() {
    const groups = Map.groupBy(tools, (tool) => tool.category);
    const sidebar = [...groups].map(([category, items], index) => {
        const id = category.toLowerCase().replaceAll(" ", "-");
        return `<a href="#${id}" class="${index === 0 ? "is-active" : ""}"><span>${category}</span><span>${items.length}</span></a>`;
    }).join("");
    const sections = [...groups].map(([category, items]) => {
        const id = category.toLowerCase().replaceAll(" ", "-");
        const cards = items.map((tool, index) => `
            <article class="tool-card tool-card-${id} ${index < 2 ? "is-featured" : ""}">
                <div class="tool-card-top">
                    <span class="tool-icon"><i data-lucide="${tool.icon}" aria-hidden="true"></i></span>
                    ${index === 0 ? '<span class="tool-badge">Mais usado</span>' : ""}
                </div>
                <h3 class="tool-title">${tool.name}</h3>
                <p class="tool-accept">Aceita ${tool.accept} &middot; preview local</p>
                <a class="tool-link" href="/tools/${tool.slug}">Converter <i data-lucide="arrow-right" aria-hidden="true"></i></a>
            </article>`).join("");
        return `<section class="tools-section" id="${id}">
            <div class="section-header"><div><h2>${category}</h2><p>${items.length} ferramentas dispon&iacute;veis</p></div></div>
            <div class="tools-grid">${cards}</div>
        </section>`;
    }).join("");

    return htmlPage("Ferramentas - BoostConvert AI", `
        <main class="page-section tools-page">
            <div class="section-heading reveal">
                <div class="eyebrow"><i data-lucide="wand-sparkles" aria-hidden="true"></i> Biblioteca de convers&otilde;es</div>
                <h1>Escolha uma ferramenta e envie seus arquivos.</h1>
                <p>Preview local do front-end com as rotas principais funcionando.</p>
            </div>
            <div class="tools-layout reveal">
                <aside class="tools-sidebar reveal" aria-label="Categorias">${sidebar}<a href="#ocr"><span>OCR</span><span>em breve</span></a></aside>
                <div class="tools-content">${sections}</div>
            </div>
        </main>`);
}

function renderTool(slug) {
    const tool = tools.find((item) => item.slug === slug) || {
        name: slug.split("-").map((part) => part[0]?.toUpperCase() + part.slice(1)).join(" "),
        slug,
        accept: "*",
        icon: "file"
    };

    return htmlPage(`${tool.name} - Boost.Convert`, `
        <main class="page-section converter-page">
            <div class="section-heading reveal">
                <div class="eyebrow"><i data-lucide="${tool.icon}" aria-hidden="true"></i> Conversor</div>
                <h1>${tool.name}</h1>
                <p>Preview local da interface. O processamento real depende do backend Flask/API.</p>
            </div>
            <form class="converter-form reveal" data-loading-form>
                <label class="upload-zone">
                    <input type="file" accept="${tool.accept}" multiple>
                    <span class="upload-icon"><i data-lucide="upload-cloud" aria-hidden="true"></i></span>
                    <strong>Arraste arquivos ou clique para selecionar</strong>
                    <small class="upload-note">Aceita ${tool.accept}</small>
                    <ul class="file-preview-list"></ul>
                </label>
                <button class="button button-primary" type="submit">Converter <i data-lucide="arrow-right" aria-hidden="true"></i></button>
            </form>
        </main>`);
}

function serveStatic(pathname, response) {
    const relativePath = pathname.replace(/^\/static\//, "");
    const fullPath = normalize(join(staticDir, relativePath));
    if (!fullPath.startsWith(staticDir) || !existsSync(fullPath)) return false;
    const contentTypes = {
        ".css": "text/css; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".svg": "image/svg+xml"
    };
    response.writeHead(200, { "Content-Type": contentTypes[extname(fullPath)] || "application/octet-stream" });
    response.end(readFileSync(fullPath));
    return true;
}

function serveProjectPhoto(pathname, response) {
    const decodedPath = decodeURIComponent(pathname);
    if (!decodedPath.startsWith("/fotos projeto/")) return false;
    const relativePath = decodedPath.replace(/^\/fotos projeto\//, "");
    const fullPath = normalize(join(projectPhotosDir, relativePath));
    if (!fullPath.startsWith(projectPhotosDir) || !existsSync(fullPath)) return false;
    response.writeHead(200, { "Content-Type": "image/png" });
    response.end(readFileSync(fullPath));
    return true;
}

createServer((request, response) => {
    const { pathname } = new URL(request.url, `http://${request.headers.host}`);
    if (pathname.startsWith("/static/") && serveStatic(pathname, response)) return;
    if (serveProjectPhoto(pathname, response)) return;

    let body;
    if (pathname === "/") body = renderTemplate("home.html");
    else if (pathname === "/tools") body = renderTools();
    else if (pathname.startsWith("/tools/")) body = renderTool(pathname.split("/").pop());
    else if (pathname === "/planos") body = renderTemplate("planos.html");
    else if (pathname === "/sobre") body = renderTemplate("sobre.html");
    else if (pathname === "/login") body = renderTemplate("login.html");
    else if (pathname === "/registrar") body = renderTemplate("registrar.html");
    else body = renderTemplate("home.html");

    response.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    response.end(body);
}).listen(port, () => {
    console.log(`Boost.Convert preview running at http://localhost:${port}`);
});

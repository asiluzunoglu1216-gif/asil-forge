from __future__ import annotations

import json
from html import escape
from urllib.parse import urlencode

from content import SERVICES, SHOWCASE_ITEMS, t


def e(value: object) -> str:
    return escape("" if value is None else str(value), quote=True)


def path_with_lang(path: str, lang: str) -> str:
    joiner = "&" if "?" in path else "?"
    return f"{path}{joiner}{urlencode({'lang': lang})}"


def hidden_common(csrf_token: str) -> str:
    return f'<input type="hidden" name="csrf_token" value="{e(csrf_token)}">'


def hidden_captcha(captcha: dict[str, str]) -> str:
    return (
        f'<input type="hidden" name="captcha_token" value="{e(captcha["token"])}">'
        f'<label><span>{e(captcha["label"])}</span><input name="captcha_answer" type="text" required></label>'
    )


def flash_html(flash: dict[str, str] | None) -> str:
    if not flash or not flash.get("message"):
        return ""
    return f'<div class="flash flash-{e(flash.get("level", "info"))}">{e(flash["message"])}</div>'


def status_badge(status: str, lang: str) -> str:
    labels = {
        "pending": t(lang, "status_pending"),
        "in_progress": t(lang, "status_in_progress"),
        "completed": t(lang, "status_completed"),
        "rejected": t(lang, "status_rejected"),
        "new": t(lang, "status_new"),
        "replied": t(lang, "status_replied"),
        "verified": t(lang, "status_verified"),
        "unverified": t(lang, "status_unverified"),
    }
    return f'<span class="status-badge status-{e(status)}">{e(labels.get(status, status.title()))}</span>'


def shell_layout(
    *,
    title: str,
    body: str,
    lang: str,
    base_url: str,
    current_path: str,
    user: dict | None,
    meta_description: str = "",
    flash: dict[str, str] | None = None,
    section_nav: str = "",
) -> str:
    auth_links = []
    if user:
      auth_links.append(f'<a href="/dashboard">{e(t(lang, "nav_dashboard"))}</a>')
      if user.get("role") == "admin":
          auth_links.append(f'<a href="/admin">{e(t(lang, "nav_admin"))}</a>')
      auth_links.append(
          '<form method="post" action="/auth/logout" class="inline-form">'
          '<input type="hidden" name="csrf_token" value="{{csrf_placeholder}}">'
          f'<button type="submit" class="ghost-link">{e(t(lang, "nav_logout"))}</button>'
          "</form>"
      )
    else:
      auth_links.append(f'<a href="/login">{e(t(lang, "nav_login"))}</a>')
      auth_links.append(f'<a href="/register" class="btn btn-primary btn-small">{e(t(lang, "nav_register"))}</a>')

    work_active = current_path == "/showcase" or current_path.startswith("/projects/")
    nav = (
        f'<a href="/"{" class=\"active\"" if current_path == "/" else ""}>{e(t(lang, "nav_home"))}</a>'
        f'<a href="/about"{" class=\"active\"" if current_path == "/about" else ""}>{e(t(lang, "nav_about"))}</a>'
        f'<a href="/services"{" class=\"active\"" if current_path == "/services" else ""}>{e(t(lang, "nav_services"))}</a>'
        f'<a href="/showcase"{" class=\"active\"" if work_active else ""}>{e(t(lang, "nav_work"))}</a>'
        f'<a href="/contact"{" class=\"active\"" if current_path == "/contact" else ""}>{e(t(lang, "nav_contact"))}</a>'
    )

    canonical_url = f"{base_url.rstrip('/')}{current_path}"
    page_title = "Asil Forge" if title.strip().lower() == "asil forge" else f"{title} | Asil Forge"
    description = meta_description or "Asil Forge builds premium software systems, automation flows, and digital platforms for modern companies."
    org_json = json.dumps(
        {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": "Asil Forge",
            "url": base_url.rstrip("/"),
            "logo": f"{base_url.rstrip('/')}/static/logo-mark.png",
        }
    )

    return f"""<!DOCTYPE html>
<html lang="{e(lang)}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{e(page_title)}</title>
  <meta name="description" content="{e(description)}">
  <meta property="og:title" content="{e(page_title)}">
  <meta property="og:description" content="{e(description)}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{e(canonical_url)}">
  <meta property="og:image" content="{e(base_url.rstrip('/'))}/static/logo-mark.png">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{e(page_title)}">
  <meta name="twitter:description" content="{e(description)}">
  <link rel="canonical" href="{e(canonical_url)}">
  <link rel="icon" href="/favicon.ico" sizes="any">
  <link rel="icon" type="image/png" sizes="96x96" href="/static/site-icon.png">
  <link rel="apple-touch-icon" href="/static/logo-mark.png">
  <link rel="stylesheet" href="/static/styles.css">
  <script type="application/ld+json">{org_json}</script>
</head>
<body>
  <div class="app-shell">
    <header class="topbar">
      <div class="container topbar-inner">
        <a class="brand" href="/">
          <span class="brand-mark" aria-hidden="true">
            <img src="/static/logo-mark.png" alt="">
          </span>
          <span class="brand-copy">
            <strong>Asil Forge</strong>
            <small>{e(t(lang, "brand_tag"))}</small>
          </span>
        </a>
        <button class="menu-toggle" id="menuToggle" type="button" aria-expanded="false" aria-controls="siteNav">
          <span></span><span></span><span></span>
        </button>
        <nav class="nav" id="siteNav">{nav}</nav>
        <div class="topbar-actions">
          <div class="lang-switch">
            <a href="{e(path_with_lang(current_path, 'tr'))}" class="lang-link{' active' if lang == 'tr' else ''}">TR</a>
            <a href="{e(path_with_lang(current_path, 'en'))}" class="lang-link{' active' if lang == 'en' else ''}">EN</a>
          </div>
          <div class="auth-links">{''.join(auth_links)}</div>
        </div>
      </div>
    </header>
    <main>
      <div class="container">
        {flash_html(flash)}
      </div>
      {section_nav}
      {body}
    </main>
    <footer class="footer">
      <div class="container footer-inner">
        <span>{e(t(lang, "footer_copy"))}</span>
        <div class="footer-links">
          <a href="/contact">{e(t(lang, "nav_contact"))}</a>
          <a href="/services">{e(t(lang, "nav_services"))}</a>
          <a href="/showcase">{e(t(lang, "nav_work"))}</a>
        </div>
      </div>
    </footer>
  </div>
  <script src="/static/app.js"></script>
</body>
</html>"""


def apply_csrf(html_content: str, csrf_token: str) -> str:
    return html_content.replace("{{csrf_placeholder}}", e(csrf_token))


def page_section(title: str, intro: str, inner: str, eyebrow: str = "") -> str:
    eyebrow_html = f'<span class="eyebrow">{e(eyebrow)}</span>' if eyebrow else ""
    return (
        '<section class="page-section"><div class="container">'
        f'<div class="section-heading">{eyebrow_html}<h1>{e(title)}</h1><p>{e(intro)}</p></div>'
        f"{inner}</div></section>"
    )


def render_project_card(item: dict, lang: str, *, with_tag: bool = False) -> str:
    tag = f'<span class="project-tag">{e(t(lang, "showcase_tag"))}</span>' if with_tag else ""
    status = item.get("status", {}).get(lang, "") if isinstance(item.get("status"), dict) else item.get("status", "")
    status_html = f'<span class="project-status-note">{e(status)}</span>' if status else ""
    body = f'{tag}<h3>{e(item["title"][lang])}</h3>{status_html}<p>{e(item["text"][lang])}</p>'
    href = item.get("url")
    if href:
        label = "Incele" if lang == "tr" else "View"
        return f'<a class="panel project-card project-card-link" href="{e(href)}">{body}<span class="project-arrow">{e(label)}</span></a>'
    return f'<article class="panel project-card">{body}</article>'


def render_home(lang: str, user: dict | None, stats: dict[str, int]) -> str:
    stats_html = (
        '<div class="stats-grid">'
        f'<article class="panel stat-card"><span>{e(t(lang, "stat_users"))}</span><strong>{stats["users"]}</strong></article>'
        f'<article class="panel stat-card"><span>{e(t(lang, "stat_projects"))}</span><strong>{stats["projects"]}</strong></article>'
        f'<article class="panel stat-card"><span>{e(t(lang, "stat_messages"))}</span><strong>{stats["messages"]}</strong></article>'
        "</div>"
    )
    services = "".join(
        f'<article class="panel feature-card"><h3>{e(item["title"][lang])}</h3><p>{e(item["text"][lang])}</p></article>'
        for item in SERVICES
    )
    showcase = "".join(render_project_card(item, lang, with_tag=True) for item in SHOWCASE_ITEMS)
    primary_link = "/dashboard" if user else "/register"
    hero = f"""
    <section class="hero">
      <div class="container hero-grid">
        <div class="hero-copy">
          <span class="eyebrow">Asil Forge</span>
          <h1>{e(t(lang, "home_title"))}</h1>
          <p>{e(t(lang, "home_text"))}</p>
          <div class="hero-actions">
            <a class="btn btn-primary" href="{e(primary_link)}">{e(t(lang, "cta_primary"))}</a>
            <a class="btn btn-secondary" href="/services">{e(t(lang, "cta_secondary"))}</a>
          </div>
          <div class="hero-points">
            <span>{e(t(lang, "hero_point_1"))}</span>
            <span>{e(t(lang, "hero_point_2"))}</span>
            <span>{e(t(lang, "hero_point_3"))}</span>
          </div>
        </div>
        <div class="panel hero-panel">
          <div class="hero-panel-head">
            <strong>{e(t(lang, "stats_title"))}</strong>
            <span class="live-pill">Live</span>
          </div>
          {stats_html}
        </div>
      </div>
    </section>
    """
    capabilities = page_section(
        t(lang, "services_title"),
        t(lang, "about_text"),
        f'<div class="card-grid">{services}</div>',
        t(lang, "section_capabilities"),
    )
    process = page_section(
        t(lang, "section_process"),
        t(lang, "contact_text"),
        (
            '<div class="card-grid">'
            f'<article class="panel process-card"><h3>{e(t(lang, "process_1_title"))}</h3><p>{e(t(lang, "process_1_text"))}</p></article>'
            f'<article class="panel process-card"><h3>{e(t(lang, "process_2_title"))}</h3><p>{e(t(lang, "process_2_text"))}</p></article>'
            f'<article class="panel process-card"><h3>{e(t(lang, "process_3_title"))}</h3><p>{e(t(lang, "process_3_text"))}</p></article>'
            "</div>"
        ),
        t(lang, "section_process"),
    )
    selected_work = page_section(
        t(lang, "section_showcase"),
        t(lang, "dashboard_text"),
        f'<div class="card-grid">{showcase}</div>',
        t(lang, "section_showcase"),
    )
    return hero + capabilities + process + selected_work


def render_about(lang: str) -> str:
    inner = (
        '<div class="split-grid">'
        f'<article class="panel prose-card"><h3>{e(t(lang, "about_title"))}</h3><p>{e(t(lang, "about_text"))}</p>'
        '<p>We treat the public-facing website as the trust layer, the client dashboard as the workspace, and the delivery flow as the operating system.</p></article>'
        '<article class="panel prose-card"><h3>System Thinking</h3><p>Professional software companies do not stop at visuals. They connect request intake, authentication, notifications, and delivery tracking into one system.</p></article>'
        "</div>"
    )
    return page_section(t(lang, "about_title"), t(lang, "about_text"), inner, t(lang, "nav_about"))


def render_services(lang: str) -> str:
    cards = "".join(
        f'<article class="panel feature-card"><h3>{e(item["title"][lang])}</h3><p>{e(item["text"][lang])}</p></article>'
        for item in SERVICES
    )
    return page_section(t(lang, "services_title"), t(lang, "contact_text"), f'<div class="card-grid">{cards}</div>', t(lang, "nav_services"))


def render_showcase(lang: str, blog_posts: list[dict]) -> str:
    items = "".join(render_project_card(item, lang) for item in SHOWCASE_ITEMS)
    insights = "".join(
        f'<article class="panel feature-card"><h3>{e(post["title"])}</h3><p>{e(post["excerpt"])}</p></article>'
        for post in blog_posts
    )
    return (
        page_section(t(lang, "section_showcase"), t(lang, "dashboard_text"), f'<div class="card-grid">{items}</div>', t(lang, "section_showcase"))
        + page_section(t(lang, "section_insights"), "Product thinking and delivery logic.", f'<div class="card-grid">{insights}</div>', t(lang, "section_insights"))
    )


def render_asil_ofisi(lang: str, download_ready: bool) -> str:
    if lang == "tr":
        copy = {
            "eyebrow": "Asil Forge urunu",
            "title": "Asil Ofisi",
            "lead": "Operasyon, dosya, gorev ve ekip akisini tek karanlik, hizli ve profesyonel masaustu deneyiminde toplamak icin tasarlanan dijital ofis.",
            "primary": "Asil Ofisi EXE Indir",
            "secondary": "Proje Detaylarini Incele",
            "status_ready": "Indirme hazir. Butona basinca dosya bu site uzerinden iner.",
            "status_waiting": "Indirme dosyasi henuz baglanmadi. Dosya eklenince ayni buton direkt indirme baslatacak.",
            "download_title": "Windows kurulum dosyasi",
            "download_text": "Tek tikla indirme akisi. Kullaniciyi baska bir sayfaya tasimadan kurulum dosyasina ulastirmak icin hazirlandi.",
            "size_note": "500 MB civari surumlerde dosyayi GitHub yerine depolama alanina koymak gerekir.",
            "feature_1": "Tek merkez operasyon",
            "feature_1_text": "Gorev, dosya, not ve ekip akislari sade bir kontrol yuzeyinde birlesir.",
            "feature_2": "Premium karanlik arayuz",
            "feature_2_text": "Koyu tema, keskin kartlar ve yazilim odakli panel duzeniyle ciddi bir urun hissi verir.",
            "feature_3": "Masaustu indirme",
            "feature_3_text": "EXE paketi icin hazir rota, surum yayinlandiginda direkt indirme deneyimi sunar.",
            "preview_title": "Urun deneyimi",
            "preview_1": "Akilli proje ve is takibi",
            "preview_2": "Dosya ve not alanlari",
            "preview_3": "Yerel masaustu kullanimi",
            "preview_4": "Gelecek surumlere hazir indirme altyapisi",
        }
    else:
        copy = {
            "eyebrow": "Asil Forge product",
            "title": "Asil Office",
            "lead": "A dark, fast, professional desktop experience designed to organize operations, files, tasks, and team flow in one digital office.",
            "primary": "Download Asil Office EXE",
            "secondary": "View Product Details",
            "status_ready": "Download is ready. The file starts from this site when you press the button.",
            "status_waiting": "The download file is not connected yet. Once added, the same button will start the download directly.",
            "download_title": "Windows installer",
            "download_text": "A one-click download flow built to deliver the installer without sending users through another page.",
            "size_note": "For versions around 500 MB, the file should live in object storage instead of GitHub.",
            "feature_1": "Central operations",
            "feature_1_text": "Tasks, files, notes, and team workflows come together in one clean control surface.",
            "feature_2": "Premium dark interface",
            "feature_2_text": "Dark theme, sharp cards, and software-focused panels create a serious product feel.",
            "feature_3": "Desktop download",
            "feature_3_text": "The EXE route is ready to deliver a direct download experience when the release is published.",
            "preview_title": "Product experience",
            "preview_1": "Smart project and task tracking",
            "preview_2": "File and note spaces",
            "preview_3": "Local desktop usage",
            "preview_4": "Download infrastructure ready for future releases",
        }
    status_class = "download-ready" if download_ready else "download-waiting"
    status_text = copy["status_ready"] if download_ready else copy["status_waiting"]
    return f"""
    <section class="product-hero">
      <div class="container product-hero-grid">
        <div class="product-copy">
          <span class="eyebrow">{e(copy["eyebrow"])}</span>
          <h1>{e(copy["title"])}</h1>
          <p>{e(copy["lead"])}</p>
          <div class="hero-actions">
            <a class="btn btn-primary" href="/downloads/asil-ofisi.exe" download>{e(copy["primary"])}</a>
            <a class="btn btn-secondary" href="#details">{e(copy["secondary"])}</a>
          </div>
          <div class="product-status {status_class}">{e(status_text)}</div>
        </div>
        <div class="panel product-preview">
          <div class="product-window-bar">
            <span></span><span></span><span></span>
            <strong>Asil Ofisi</strong>
          </div>
          <div class="product-window-body">
            <div class="product-sidebar">
              <span>Dashboard</span>
              <span>Projects</span>
              <span>Files</span>
              <span>Notes</span>
            </div>
            <div class="product-canvas">
              <div class="product-metric"><small>Open Tasks</small><strong>24</strong></div>
              <div class="product-metric"><small>Files</small><strong>128</strong></div>
              <div class="product-line wide"></div>
              <div class="product-line"></div>
              <div class="product-line short"></div>
            </div>
          </div>
        </div>
      </div>
    </section>
    <section class="page-section" id="details">
      <div class="container product-shell">
        <div class="card-grid">
          <article class="panel feature-card"><h3>{e(copy["feature_1"])}</h3><p>{e(copy["feature_1_text"])}</p></article>
          <article class="panel feature-card"><h3>{e(copy["feature_2"])}</h3><p>{e(copy["feature_2_text"])}</p></article>
          <article class="panel feature-card"><h3>{e(copy["feature_3"])}</h3><p>{e(copy["feature_3_text"])}</p></article>
        </div>
        <div class="download-grid">
          <article class="panel download-panel">
            <span class="project-tag">EXE</span>
            <h2>{e(copy["download_title"])}</h2>
            <p>{e(copy["download_text"])}</p>
            <a class="btn btn-primary" href="/downloads/asil-ofisi.exe" download>{e(copy["primary"])}</a>
            <p class="muted-note">{e(copy["size_note"])}</p>
          </article>
          <article class="panel product-list-card">
            <h2>{e(copy["preview_title"])}</h2>
            <div class="product-checks">
              <span>{e(copy["preview_1"])}</span>
              <span>{e(copy["preview_2"])}</span>
              <span>{e(copy["preview_3"])}</span>
              <span>{e(copy["preview_4"])}</span>
            </div>
          </article>
        </div>
      </div>
    </section>
    """


def render_contact(lang: str, csrf_token: str, captcha: dict[str, str]) -> str:
    form = f"""
    <div class="form-wrap panel">
      <form method="post" action="/contact" class="app-form">
        {hidden_common(csrf_token)}
        <label><span>{e(t(lang, "field_name"))}</span><input name="name" type="text" required></label>
        <label><span>{e(t(lang, "field_email"))}</span><input name="email" type="email" required></label>
        <label><span>{e(t(lang, "field_subject"))}</span><input name="subject" type="text" required></label>
        <label><span>{e(t(lang, "field_message"))}</span><textarea name="message" rows="6" required></textarea></label>
        {hidden_captcha(captcha)}
        <button class="btn btn-primary" type="submit">{e(t(lang, "btn_send"))}</button>
      </form>
    </div>
    """
    return page_section(t(lang, "contact_title"), t(lang, "contact_text"), form, t(lang, "section_contact"))


def render_login(lang: str, csrf_token: str) -> str:
    form = f"""
    <div class="auth-grid">
      <article class="panel form-wrap">
        <form method="post" action="/auth/login" class="app-form">
          {hidden_common(csrf_token)}
          <label><span>{e(t(lang, "field_email"))}</span><input name="email" type="email" required></label>
          <label><span>{e(t(lang, "field_password"))}</span><input name="password" type="password" required></label>
          <button class="btn btn-primary" type="submit">{e(t(lang, "btn_login"))}</button>
        </form>
        <div class="form-links">
          <a href="/forgot-password">Forgot password?</a>
          <a href="/register">{e(t(lang, "btn_register"))}</a>
        </div>
      </article>
      <article class="panel prose-card">
        <h3>{e(t(lang, "login_title"))}</h3>
        <p>{e(t(lang, "dashboard_text"))}</p>
      </article>
    </div>
    """
    return page_section(t(lang, "login_title"), t(lang, "about_text"), form, t(lang, "nav_login"))


def render_register(lang: str, csrf_token: str, captcha: dict[str, str]) -> str:
    form = f"""
    <div class="auth-grid">
      <article class="panel form-wrap">
        <form method="post" action="/auth/register" class="app-form">
          {hidden_common(csrf_token)}
          <label><span>{e(t(lang, "field_name"))}</span><input name="name" type="text" required></label>
          <label><span>{e(t(lang, "field_email"))}</span><input name="email" type="email" required></label>
          <label><span>{e(t(lang, "field_password"))}</span><input name="password" type="password" required></label>
          <label><span>{e(t(lang, "field_password_confirm"))}</span><input name="password_confirm" type="password" required></label>
          {hidden_captcha(captcha)}
          <label class="inline-check"><input name="human_check" type="checkbox" value="1" required><span>{e(t(lang, "field_robot"))}</span></label>
          <button class="btn btn-primary" type="submit">{e(t(lang, "btn_register"))}</button>
        </form>
      </article>
      <article class="panel prose-card">
        <h3>{e(t(lang, "register_title"))}</h3>
        <p>{e(t(lang, "contact_text"))}</p>
      </article>
    </div>
    """
    return page_section(t(lang, "register_title"), t(lang, "about_text"), form, t(lang, "nav_register"))


def render_forgot(lang: str, csrf_token: str, captcha: dict[str, str]) -> str:
    form = f"""
    <div class="form-wrap panel">
      <form method="post" action="/auth/forgot-password" class="app-form">
        {hidden_common(csrf_token)}
        <label><span>{e(t(lang, "field_email"))}</span><input name="email" type="email" required></label>
        {hidden_captcha(captcha)}
        <button class="btn btn-primary" type="submit">{e(t(lang, "btn_reset"))}</button>
      </form>
    </div>
    """
    return page_section(t(lang, "forgot_title"), t(lang, "outbox_note"), form, t(lang, "verify_title"))


def render_reset(lang: str, csrf_token: str, raw_token: str) -> str:
    form = f"""
    <div class="form-wrap panel">
      <form method="post" action="/auth/reset-password" class="app-form">
        {hidden_common(csrf_token)}
        <input type="hidden" name="token" value="{e(raw_token)}">
        <label><span>{e(t(lang, "field_password"))}</span><input name="password" type="password" required></label>
        <label><span>{e(t(lang, "field_password_confirm"))}</span><input name="password_confirm" type="password" required></label>
        <button class="btn btn-primary" type="submit">{e(t(lang, "btn_reset"))}</button>
      </form>
    </div>
    """
    return page_section(t(lang, "reset_title"), t(lang, "security_section"), form, t(lang, "verify_title"))


def dashboard_nav(current_path: str, lang: str) -> str:
    return (
        '<section class="subnav"><div class="container subnav-inner">'
        f'<a href="/dashboard"{" class=\"active\"" if current_path == "/dashboard" else ""}>Overview</a>'
        f'<a href="/dashboard/projects"{" class=\"active\"" if current_path == "/dashboard/projects" else ""}>Projects</a>'
        f'<a href="/dashboard/profile"{" class=\"active\"" if current_path == "/dashboard/profile" else ""}>{e(t(lang, "profile_section"))}</a>'
        f'<a href="/dashboard/activity"{" class=\"active\"" if current_path == "/dashboard/activity" else ""}>{e(t(lang, "table_activity"))}</a>'
        "</div></section>"
    )


def admin_nav(current_path: str) -> str:
    return (
        '<section class="subnav"><div class="container subnav-inner">'
        f'<a href="/admin"{" class=\"active\"" if current_path == "/admin" else ""}>Overview</a>'
        f'<a href="/admin/users"{" class=\"active\"" if current_path == "/admin/users" else ""}>Users</a>'
        f'<a href="/admin/projects"{" class=\"active\"" if current_path == "/admin/projects" else ""}>Projects</a>'
        f'<a href="/admin/messages"{" class=\"active\"" if current_path == "/admin/messages" else ""}>Messages</a>'
        f'<a href="/admin/outbox"{" class=\"active\"" if current_path == "/admin/outbox" else ""}>Outbox</a>'
        "</div></section>"
    )


def render_dashboard_home(lang: str, user: dict, stats: dict[str, int]) -> str:
    body = f"""
    <section class="page-section compact">
      <div class="container">
        <div class="section-heading">
          <span class="eyebrow">{e(t(lang, "dashboard_title"))}</span>
          <h1>{e(user["name"])}</h1>
          <p>{e(t(lang, "dashboard_text"))}</p>
        </div>
        <div class="stats-grid">
          <article class="panel stat-card"><span>{e(t(lang, "stat_projects"))}</span><strong>{stats["projects"]}</strong></article>
          <article class="panel stat-card"><span>{e(t(lang, "table_activity"))}</span><strong>{stats["activities"]}</strong></article>
          <article class="panel stat-card"><span>Email</span><strong>{e(user["email"])}</strong></article>
        </div>
      </div>
    </section>
    """
    return body


def render_dashboard_profile(lang: str, user: dict, csrf_token: str) -> str:
    profile = f"""
    <div class="dashboard-grid">
      <article class="panel form-wrap">
        <h3>{e(t(lang, "profile_section"))}</h3>
        <form method="post" action="/dashboard/profile" class="app-form">
          {hidden_common(csrf_token)}
          <label><span>{e(t(lang, "field_name"))}</span><input name="name" type="text" value="{e(user['name'])}" required></label>
          <label><span>{e(t(lang, "field_email"))}</span><input name="email" type="email" value="{e(user['email'])}" required></label>
          <label><span>{e(t(lang, "field_locale"))}</span>
            <select name="locale">
              <option value="tr"{' selected' if user.get('locale') == 'tr' else ''}>TR</option>
              <option value="en"{' selected' if user.get('locale') == 'en' else ''}>EN</option>
            </select>
          </label>
          <button class="btn btn-primary" type="submit">{e(t(lang, "btn_save"))}</button>
        </form>
      </article>
      <article class="panel form-wrap">
        <h3>{e(t(lang, "security_section"))}</h3>
        <form method="post" action="/dashboard/password" class="app-form">
          {hidden_common(csrf_token)}
          <label><span>Current Password</span><input name="current_password" type="password" required></label>
          <label><span>{e(t(lang, "field_password"))}</span><input name="password" type="password" required></label>
          <label><span>{e(t(lang, "field_password_confirm"))}</span><input name="password_confirm" type="password" required></label>
          <button class="btn btn-secondary" type="submit">{e(t(lang, "btn_change_password"))}</button>
        </form>
      </article>
    </div>
    """
    return page_section(t(lang, "profile_section"), t(lang, "security_section"), profile, t(lang, "profile_section"))


def render_dashboard_projects(lang: str, user_projects: list[dict], csrf_token: str) -> str:
    rows = "".join(
        f"<tr><td>{e(item['title'])}</td><td>{status_badge(item['status'], lang)}</td><td>{e(item.get('budget') or '-')}</td><td>{e(item.get('deadline') or '-')}</td><td>{e(item.get('admin_notes') or '-')}</td></tr>"
        for item in user_projects
    ) or f'<tr><td colspan="5">{e(t(lang, "project_empty"))}</td></tr>'
    request_form = f"""
    <article class="panel form-wrap">
      <h3>{e(t(lang, "request_section"))}</h3>
      <form method="post" action="/dashboard/projects/new" class="app-form">
        {hidden_common(csrf_token)}
        <label><span>{e(t(lang, "field_project_title"))}</span><input name="title" type="text" required></label>
        <label><span>{e(t(lang, "field_description"))}</span><textarea name="description" rows="5" required></textarea></label>
        <div class="two-col">
          <label><span>{e(t(lang, "field_budget"))}</span><input name="budget" type="text"></label>
          <label><span>{e(t(lang, "field_deadline"))}</span><input name="deadline" type="date"></label>
        </div>
        <button class="btn btn-primary" type="submit">{e(t(lang, "btn_request"))}</button>
      </form>
    </article>
    """
    table = f"""
    <article class="panel table-panel">
      <div class="table-head"><h3>{e(t(lang, "table_projects"))}</h3></div>
      <div class="table-wrap">
        <table class="app-table">
          <thead><tr><th>Title</th><th>Status</th><th>Budget</th><th>Deadline</th><th>Admin Note</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </article>
    """
    return page_section(t(lang, "table_projects"), t(lang, "dashboard_text"), f'<div class="dashboard-grid">{request_form}{table}</div>', t(lang, "table_projects"))


def render_dashboard_activity(lang: str, activities: list[dict]) -> str:
    rows = "".join(
        f"<tr><td>{e(item['created_at'])}</td><td>{e(item['action'])}</td><td>{e(item['details'])}</td></tr>"
        for item in activities
    ) or f'<tr><td colspan="3">{e(t(lang, "activity_empty"))}</td></tr>'
    table = (
        '<article class="panel table-panel"><div class="table-wrap"><table class="app-table">'
        '<thead><tr><th>Date</th><th>Action</th><th>Details</th></tr></thead>'
        f"<tbody>{rows}</tbody></table></div></article>"
    )
    return page_section(t(lang, "table_activity"), t(lang, "dashboard_text"), table, t(lang, "table_activity"))


def render_admin_home(lang: str, stats: dict[str, int]) -> str:
    cards = (
        '<div class="stats-grid">'
        f'<article class="panel stat-card"><span>{e(t(lang, "stat_users"))}</span><strong>{stats["users"]}</strong></article>'
        f'<article class="panel stat-card"><span>{e(t(lang, "stat_projects"))}</span><strong>{stats["projects"]}</strong></article>'
        f'<article class="panel stat-card"><span>{e(t(lang, "stat_messages"))}</span><strong>{stats["messages"]}</strong></article>'
        f'<article class="panel stat-card"><span>Queued Emails</span><strong>{stats["notifications"]}</strong></article>'
        "</div>"
    )
    return page_section(t(lang, "admin_title"), t(lang, "admin_text"), cards, "Admin")


def render_admin_users(lang: str, users: list[dict], csrf_token: str) -> str:
    cards = []
    for item in users:
        if item["role"] == "admin":
            action_note = "<p class=\"muted-note\">Primary admin account is protected from deletion.</p>"
            delete_button = ""
        else:
            action_note = ""
            delete_button = f'<button class="btn btn-danger btn-small" name="intent" value="delete">{e(t(lang, "btn_delete"))}</button>'
        cards.append(
            '<article class="panel admin-card"><div class="admin-card-head">'
            f'<h3>{e(item["name"])}</h3><div>{status_badge("verified" if item["is_verified"] else "unverified", lang)}</div></div>'
            f'<p>{e(item["email"])}</p>'
            '<form method="post" action="/admin/users/update" class="app-form">'
            f'{hidden_common(csrf_token)}'
            f'<input type="hidden" name="user_id" value="{item["id"]}">'
            '<div class="two-col">'
            f'<label><span>{e(t(lang, "field_role"))}</span><select name="role"><option value="user"{" selected" if item["role"] == "user" else ""}>user</option><option value="admin"{" selected" if item["role"] == "admin" else ""}>admin</option></select></label>'
            f'<label><span>Status</span><select name="is_active"><option value="1"{" selected" if item["is_active"] else ""}>active</option><option value="0"{" selected" if not item["is_active"] else ""}>inactive</option></select></label>'
            "</div>"
            '<div class="button-row">'
            f'<button class="btn btn-secondary btn-small" name="intent" value="update">{e(t(lang, "btn_update"))}</button>'
            f"{delete_button}</div>{action_note}</form></article>"
        )
    return page_section(t(lang, "table_users"), t(lang, "admin_text"), f'<div class="card-grid">{ "".join(cards) }</div>', t(lang, "table_users"))


def render_admin_projects(lang: str, projects: list[dict], csrf_token: str) -> str:
    cards = []
    for item in projects:
        cards.append(
            '<article class="panel admin-card">'
            f'<div class="admin-card-head"><h3>{e(item["title"])}</h3>{status_badge(item["status"], lang)}</div>'
            f'<p>{e(item["description"])}</p>'
            f'<p><strong>User:</strong> {e(item.get("user_email") or "deleted user")}</p>'
            '<form method="post" action="/admin/projects/update" class="app-form">'
            f'{hidden_common(csrf_token)}'
            f'<input type="hidden" name="project_id" value="{item["id"]}">'
            f'<label><span>{e(t(lang, "field_status"))}</span><select name="status">'
            f'<option value="pending"{" selected" if item["status"] == "pending" else ""}>pending</option>'
            f'<option value="in_progress"{" selected" if item["status"] == "in_progress" else ""}>in_progress</option>'
            f'<option value="completed"{" selected" if item["status"] == "completed" else ""}>completed</option>'
            f'<option value="rejected"{" selected" if item["status"] == "rejected" else ""}>rejected</option>'
            '</select></label>'
            f'<label><span>{e(t(lang, "field_notes"))}</span><textarea name="admin_notes" rows="4">{e(item.get("admin_notes") or "")}</textarea></label>'
            f'<button class="btn btn-secondary btn-small" type="submit">{e(t(lang, "btn_update"))}</button>'
            '</form></article>'
        )
    cards_markup = "".join(cards) or f'<article class="panel empty-card">{e(t(lang, "project_empty"))}</article>'
    return page_section(t(lang, "table_projects"), t(lang, "admin_text"), f'<div class="card-grid">{cards_markup}</div>', t(lang, "table_projects"))


def render_admin_messages(lang: str, messages: list[dict], csrf_token: str) -> str:
    cards = []
    for item in messages:
        cards.append(
            '<article class="panel admin-card">'
            f'<div class="admin-card-head"><h3>{e(item["subject"])}</h3>{status_badge(item["status"], lang)}</div>'
            f'<p><strong>{e(item["name"])}</strong> - {e(item["email"])}</p>'
            f'<p>{e(item["message"])}</p>'
            '<form method="post" action="/admin/messages/update" class="app-form">'
            f'{hidden_common(csrf_token)}'
            f'<input type="hidden" name="message_id" value="{item["id"]}">'
            '<div class="two-col">'
            f'<label><span>{e(t(lang, "field_status"))}</span><select name="status"><option value="new"{" selected" if item["status"] == "new" else ""}>new</option><option value="replied"{" selected" if item["status"] == "replied" else ""}>replied</option></select></label>'
            '</div>'
            f'<label><span>{e(t(lang, "btn_reply"))}</span><textarea name="admin_reply" rows="4">{e(item.get("admin_reply") or "")}</textarea></label>'
            f'<button class="btn btn-secondary btn-small" type="submit">{e(t(lang, "btn_reply"))}</button>'
            '</form></article>'
        )
    cards_markup = "".join(cards) or f'<article class="panel empty-card">{e(t(lang, "message_empty"))}</article>'
    return page_section(t(lang, "table_messages"), t(lang, "admin_text"), f'<div class="card-grid">{cards_markup}</div>', t(lang, "table_messages"))


def render_admin_outbox(lang: str, notifications: list[dict]) -> str:
    cards = "".join(
        '<article class="panel admin-card">'
        f"<div class=\"admin-card-head\"><h3>{e(item['subject'])}</h3><span class=\"project-tag\">{e(item['kind'])}</span></div>"
        f"<p><strong>{e(item['email'])}</strong></p>"
        f"<p class=\"muted-note\">{e(item['created_at'])}</p>"
        f"<pre class=\"notification-body\">{e(item['body'])}</pre>"
        "</article>"
        for item in notifications
    ) or '<article class="panel empty-card">No queued notifications.</article>'
    return page_section(t(lang, "table_notifications"), t(lang, "outbox_note"), f'<div class="card-grid single-col">{cards}</div>', t(lang, "table_notifications"))

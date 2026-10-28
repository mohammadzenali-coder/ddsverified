"""Generate static product, category, collection, campaign and blog pages.

Reads products_data.json and posts/*.md. Re-run when data changes:
python generate_pages.py. The homepage is maintained separately.
"""
import json
import os
import re
from urllib.parse import quote

BASE = "https://ddsverified.ir"
WORDMARK = f"{BASE}/logo-wordmark.webp"
SQUARE_LOGO = f"{BASE}/logo-wordmark-square.webp"
CONTACT_NUMBER = "+989999587786"
FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

# URL slugs per shape key (locked — do not change after indexing)
SLUGS = {
    "needle": "needle-burs",
    "flat_cylinder": "fissure-burs",
    "taper_round_edge": "taper-round-edge-burs",
    "round_taper": "round-taper-burs",
    "taper_flat": "taper-flat-burs",
    "flame": "flame-burs",
    "flame_long": "flame-long-shank-burs",
    "round": "round-diamond-burs",
    "round_long": "round-long-shank-burs",
    "torpedo": "torpedo-burs",
    "football": "football-burs",
    "inverted_cone": "inverted-cone-burs",
    "barrel": "double-barrel-burs",
    "depth_veneer": "depth-cut-veneer-burs",
    "pointed_cylinder": "chamfer-burs",
    "round_end_cylinder": "round-end-fissure-burs",
    "carbide": "endoz-carbide-burs",
    "bundle": "campaign-bundle",
}

# Persian display overrides (owner-confirmed naming; falls back to SHAPE_MAP value)
SHAPE_OVERRIDE = {
    "pointed_cylinder": {"fa": "فرز دندانپزشکی شمفر استوانه ایی"},
}

GRIT_ORDER = ["K⚫", "G🟢", "B🔵", "R🔴", "Y🟡", "W⚪"]  # coarsest → finest
GRIT_LABELS = {"K⚫": "مشکی", "G🟢": "سبز", "B🔵": "آبی", "R🔴": "قرمز", "Y🟡": "زرد", "W⚪": "سفید"}


def fa(n) -> str:
    return str(n).translate(FA_DIGITS)


def load_data() -> dict:
    return json.load(open("products_data.json", encoding="utf-8"))


def shape_fa(key: str, data: dict) -> str:
    return SHAPE_OVERRIDE.get(key, {}).get("fa") or data["shapes"].get(key, key)


def anchor_id(model: str) -> str:
    # "ENDO-Z TI" -> "endoz-ti": drop spaces, keep hyphens as separators
    return "".join(c for c in model.lower().replace(" ", "") if c.isalnum() or c == "-")


def grit_sort_key(p: dict) -> tuple:
    grit = p.get("grit", "-")
    return (GRIT_ORDER.index(grit) if grit in GRIT_ORDER else len(GRIT_ORDER), p["model"])


def group_by_page(data: dict) -> dict:
    groups = {}
    for p in sorted(data["products"], key=lambda x: x["model"]):
        groups.setdefault(p["shape"], []).append(p)
    for products in groups.values():
        products.sort(key=grit_sort_key)
    return groups


def cat_url(shape_key: str) -> str:
    return f"category/{SLUGS[shape_key]}/"


def product_page_url(model: str) -> str:
    """Static per-product page path (Torob/Emalls-friendly, crawlable URL)."""
    return f"product/{anchor_id(model)}/"


def img_rel(model: str) -> str:
    """Absolute image path — safe from any page depth (/category/<slug>/ included)."""
    filename = "endo-z-ti" if model == "ENDO-Z TI" else model.lower()
    return quote(f"{BASE}/images/{filename}.webp", safe="/:")


def fmt_price(price: int) -> str:
    return f"{price:,}".replace(",", "،")


def product_price(p: dict, data: dict) -> int:
    """Sticker price in toman from the product override or the catalog default."""
    return int(p["price"] if p.get("price") is not None else data["price_per_bur"])


TRUST_HTML = '<div class="trust">🔍 انتخاب بر اساس کیفیت ساخت و مشخصات فنی &nbsp;·&nbsp; 🎨 تنوع شکل و دور فرز &nbsp;·&nbsp; 📦 ارسال سراسر ایران</div>'


# Curated clinical collections are landing pages, not marketplace categories.
COLLECTIONS = {
    "fixed_prostho": {
        "slug": "fixed-prostho",
        "title": "فرز های مناسب پروتز ثابت",
        "short_title": "مناسب پروتز ثابت",
        "description": "مجموعه فرزهای مناسب پروتز ثابت شامل مدل‌های انتخاب‌شده با سایز و مشخصات موجود هر مدل.",
        "intro_note": "این مجموعه مدل‌های مناسب پروتز ثابت را همراه با سایز، دور، کد ISO و معادل USA نشان می‌دهد.",
    },
    "restorative": {
        "slug": "restorative-specialists",
        "title": "برای متخصصان ترمیمی",
        "short_title": "مناسب متخصصان ترمیمی",
        "description": "مجموعه فرزهای مناسب متخصصان ترمیمی شامل فرزهای نیدل، فلیم و تخم‌مرغی، به‌همراه SF-41 و BR-49.",
        "intro_note": "این مجموعه مدل‌های مناسب کانتورینگ اکلوزال، فرم‌دهی و پرداخت ترمیمی را همراه با سایز، دور، کد ISO و معادل USA نشان می‌دهد.",
    },
}


def collection_url(collection_key: str) -> str:
    return f"collection/{COLLECTIONS[collection_key]['slug']}/"


def collection_products(data: dict, collection_key: str) -> list:
    if collection_key == "restorative":
        products = [
            p for p in data["products"]
            if p.get("shape") in {"needle", "flame", "flame_long", "football"}
            or p.get("model") in {"SF-41", "BR-49"}
        ]
    else:
        products = [p for p in data["products"] if p.get("collection") == collection_key]
    return sorted(products, key=grit_sort_key)


# ---------------------------------------------------------------- intros ----
INTROS = {
    "needle": "فرز دندانپزشکی نیدل (سوزنی) با نوک ظریف و کشیده برای کارهای دقیق بین‌دندانی و دسترسی به نواحی محدود کاربرد دارد. مدل‌ها در اندازه و دورهای مختلف عرضه می‌شوند؛ برای انتخاب، مشخصات فنی هر مدل را بررسی کنید.",
    "flat_cylinder": "فرز فیشور (استوانه‌ای تخت) برای ایجاد دیواره‌های صاف و کف مشخص در ترمیم‌های اکلوزالی کاربرد دارد. این خانواده انتخاب اول برای آماده‌سازی باکس اکلوزال و حذف دقیق نسج است.",
    "taper_round_edge": "فرز تیپر روند اند (مخروطی با لبه گرد) ترکیبی از دیواره مخروطی و نوک گرد است که برای شیاردهی، آماده‌سازی اولیه حفره و ایجاد همگرایی دیواره‌ها استفاده می‌شود؛ بدون ایجاد زاویه تیز در گوشه‌های داخلی.",
    "round_taper": "فرز تیپر روند اند سری RS با طراحی مخروطی لبه‌گرد، مناسب شکستن تماس بین دندانی و آماده‌سازی اولیه ترمیم‌های کامپوزیتی و سرامیکی است.",
    "taper_flat": "فرز تیپر فلت اند (مخروطی با انتهای تخت) برای ایجاد سطح اکلوزال صاف همراه با شیب دیواره‌ها به کار می‌رود؛ گزینه رایج در آماده‌سازی روکش و ترمیم‌های بزرگ.",
    "flame": "فرز فلیم (شعله‌ای) با بدنه باریک و کشیده، ابزار اصلی شکل‌دهی سولکوس، آماده‌سازی مارجین و کارهای لثه‌محور در پروتز و ترمیم است.",
    "flame_long": "فرز فلیم شنک بلند برای دسترسی به نواحی عمق‌دار و مواردی که طول فرز معمولی کافی نیست طراحی شده است.",
    "round": "فرز روند الماسی توربین، فرز کلاسیک حذف پوسیدگی و ایجاد حفرات گرد است؛ نوک کروی آن امکان کنترل دقیق عمق را می‌دهد.",
    "round_long": "فرز روند شنک بلند (شبیه فرز میولر) برای دسترسی عمقی‌تر با همان عملکرد فرز روند ساخته شده است.",
    "torpedo": "فرز تورپیدو با بدنه دوکی‌شکل، مناسب شیاردهی، اصلاح آناتومی اکلوزال و تراش تدریجی نسج است.",
    "football": "فرز فوتبالی (تخم‌مرغی) انتخاب اصلی برای کاهش و فرم‌دهی سطوح اکلوزالی، پرداخت کامپوزیت و شکل‌دهی کاسپ‌ها است.",
    "inverted_cone": "فرز اینورتد (معکوس) با نوک پهن و بدنه باریک‌شونده، برای ایجاد سطوح تخت اکلوزال و زیربرش (undercut) استفاده می‌شود.",
    "barrel": "فرز دابل برل (بشکه‌ای) برای تراش‌های وسیع اکلوزالی و کاهش سریع نسج با کنترل بالا کاربرد دارد.",
    "depth_veneer": "فرز دپس کات (Depth Cut) مجموعه استاندارد ونیر است؛ سه عمق ۰.۳، ۰.۴ و ۰.۵ میلی‌متر برای ایجاد کویینت‌سنت عمقی دقیق و یکنواخت روی سطح لبینی پیش از تراش کامل ونیر.",
    "pointed_cylinder": "فرز شمفر استوانه‌ای برای ایجاد شلف (shoulder) و مارجین‌های شمفردی در آماده‌سازی روکش و لمینت به کار می‌رود.",
    "round_end_cylinder": "فرز فیشور روند اند (استوانه‌ای ته گرد) دیواره‌های موازی با انتهای گرد دارد و برای تراش‌های کنترل‌شده با کف گرد مناسب است.",
    "carbide": "فرز EndoZ کارباید تیتانیومی با نوک غیر‌بُرنده و تیغه‌های جانبی برای اصلاح دیواره‌های حفره دسترسی اندودانتیک و برداشت سقف اتاقک پالپ طراحی شده است؛ استفاده کنترل‌شده و پرهیز از تماس با کف پالپ ضروری است.",
}

FAQS = {
    "_common": [
        ("چطور مدل مناسب را انتخاب کنم؟", "شکل، اندازه، دور (گریت) و کدهای ISO و USA هر مدل در همین صفحه درج شده‌اند. مدل‌ها را بر اساس کاربرد موردنظر و مشخصات فنی مقایسه کنید."),
        ("ارسال چگونه است؟", "ارسال به سراسر ایران انجام می‌شود؛ هزینه و شرایط ارسال هنگام ثبت سفارش مشخص می‌شود."),
        ("قیمت هر مدل را کجا ببینم؟", "قیمت هر مدل در کنار مشخصات همان محصول درج شده است. قیمت نهایی سفارش را هنگام ثبت خرید بررسی کنید."),
    ],
}

def build_collection_page(collection_key: str, data: dict) -> str:
    collection = COLLECTIONS[collection_key]
    products = collection_products(data, collection_key)
    title = collection["title"]
    slug_url = collection_url(collection_key)
    n_models = fa(len(products))
    intro = collection["description"]
    blocks = "".join(_model_block(p, collection["short_title"], data) for p in products)
    ld_items = [{
        "@type": "ListItem", "position": i + 1,
        "item": {
            "@type": "Product",
            "name": f"فرز {collection['short_title']} {p['model']}",
            "image": img_rel(p["model"]),
            "sku": p["model"],
            "brand": {"@type": "Brand", "name": "DDSVerified"},
            "offers": {
                "@type": "Offer", "priceCurrency": "IRR",
                "price": product_price(p, data) * 10,  # IRR; catalog prices are toman
                "availability": "https://schema.org/InStock" if p["inventory"] > 0 else "https://schema.org/OutOfStock",
            },
        },
    } for i, p in enumerate(products)]
    ld_itemlist = json.dumps({"@context": "https://schema.org", "@type": "ItemList", "itemListElement": ld_items}, ensure_ascii=False)
    ld_bc = json.dumps({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "خانه", "item": f"{BASE}/"},
        {"@type": "ListItem", "position": 2, "name": title, "item": f"{BASE}/{slug_url}"},
    ]}, ensure_ascii=False)
    extra = (f'<script type="application/ld+json">{ld_itemlist}</script>\n'
             f'<script type="application/ld+json">{ld_bc}</script>')
    body = f"""
<p class="collection-note">اگر مدل مدنظر شما اینجا نیست، در <a href="{BASE}/">صفحه اصلی ddsverified.ir</a> مشاهده کنید.</p>
<h1>{title}</h1>
<div class="intro"><p>{intro}</p>
<p>{collection["intro_note"]}</p></div>
<h2>مدل‌های موجود ({n_models} مدل)</h2>
{blocks}
<p><a class="cta" href="{BASE}/">← بازگشت به فروشگاه و مشاهده همه فرزها</a></p>
{TRUST_HTML}"""
    crumbs = f'<a href="/">خانه</a> › {title}'
    return _layout(f"{title} | DDSVerified", intro, slug_url, crumbs, body, extra)


# ---------------------------------------------------------------- blog md ----
def _inline_md(text: str) -> str:
    """Inline markdown: **bold**, *italic*, `code`, [text](url), ![alt](url)."""
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)",
                  lambda m: f'<img src="{m.group(2)}" alt="{m.group(1)}" loading="lazy">',
                  text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


def md_to_html(md: str) -> str:
    """Tiny zero-dependency markdown → HTML (headings, lists, tables, paragraphs)."""
    lines = md.replace("\r\n", "\n").split("\n")
    out, i = [], 0
    in_list, list_tag = False, None
    while i < len(lines):
        line = lines[i]
        # table: | a | b | followed by |---|---|
        if line.strip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|[\s\-|:]+\|\s*$", lines[i + 1]):
            if in_list:
                out.append(f"</{list_tag}>"); in_list, list_tag = False, None
            header = [c.strip() for c in line.strip().strip("|").split("|")]
            rows, i = [], i + 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            th = "".join(f"<th>{_inline_md(c)}</th>" for c in header)
            trs = "".join("<tr>" + "".join(f"<td>{_inline_md(c)}</td>" for c in r) + "</tr>" for r in rows)
            out.append(f'<div style="overflow-x:auto"><table class="md-t">{th and f"<tr>{th}</tr>"}{trs}</table></div>')
            continue
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            if in_list:
                out.append(f"</{list_tag}>"); in_list, list_tag = False, None
            level = max(2, len(m.group(1)))  # h1 is the page title; # and ## both become h2 sections
            out.append(f"<h{level}>{_inline_md(m.group(2))}</h{level}>")
            i += 1
            continue
        m = re.match(r"^\s*[-*]\s+(.*)", line)
        if m:
            if not in_list or list_tag != "ul":
                if in_list: out.append(f"</{list_tag}>")
                out.append("<ul>"); in_list, list_tag = True, "ul"
            out.append(f"<li>{_inline_md(m.group(1))}</li>"); i += 1
            continue
        m = re.match(r"^\s*\d+[.)]\s+(.*)", line)
        if m:
            if not in_list or list_tag != "ol":
                if in_list: out.append(f"</{list_tag}>")
                out.append("<ol>"); in_list, list_tag = True, "ol"
            out.append(f"<li>{_inline_md(m.group(1))}</li>"); i += 1
            continue
        if line.strip().startswith("```"):
            if in_list:
                out.append(f"</{list_tag}>"); in_list, list_tag = False, None
            code, i = [], i + 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i]); i += 1
            i += 1
            out.append(f"<pre dir=\"ltr\">{'&#10;'.join(code)}</pre>")
            continue
        if line.strip() == "":
            if in_list:
                out.append(f"</{list_tag}>"); in_list, list_tag = False, None
            i += 1
            continue
        if in_list:
            out.append(f"</{list_tag}>"); in_list, list_tag = False, None
        out.append(f"<p>{_inline_md(line.strip())}</p>")
        i += 1
    if in_list:
        out.append(f"</{list_tag}>")
    return "\n".join(out)


def parse_post(path: str) -> dict:
    """Parse posts/<file>.md with a tiny YAML-ish front matter:
    ---
    title: ...
    slug: ...
    date: 2026-08-29
    description: ...
    image: images/blog/foo.webp   (optional, used for og:image)
    ---
    """
    raw = open(path, encoding="utf-8").read()
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)", raw, re.S)
    meta, body_md = {}, raw
    if m:
        for line in m.group(1).split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip().lower()] = v.strip()
        body_md = m.group(2)
    slug = meta.get("slug") or os.path.splitext(os.path.basename(path))[0]
    return {
        "file": path,
        "title": meta.get("title", slug),
        "slug": re.sub(r"[^a-z0-9-]", "", slug.lower()),
        "date": meta.get("date", ""),
        "description": meta.get("description", ""),
        "image": meta.get("image", ""),
        "tags": [t.strip() for t in meta.get("tags", "").split(",") if t.strip()],
        "body": body_md,
    }


def load_posts() -> list:
    if not os.path.isdir("posts"):
        return []
    posts = [parse_post(os.path.join("posts", f)) for f in sorted(os.listdir("posts"))
             if f.endswith(".md") and not f.startswith("_")]
    return sorted(posts, key=lambda p: p["date"], reverse=True)


BLOG_CSS = """
.post{background:#fff;border:1px solid #dce3ec;border-radius:12px;padding:16px;font-size:.92rem}
.post h2{margin-top:20px}.post h3{font-size:.98rem;color:#1565c0;margin:16px 0 8px}
.post p{margin:8px 0}.post img{max-width:100%;height:auto;border-radius:8px;margin:10px 0}
.post ul,.post ol{margin:8px 20px;padding:0}.post li{margin:4px 0}
.post pre{background:#263238;color:#eceff1;border-radius:8px;padding:12px;overflow-x:auto;font-size:.8rem}
.post code{background:#eceff1;border-radius:4px;padding:1px 5px;font-size:.85em}
.md-t{border-collapse:collapse;font-size:.84rem;margin:10px 0;width:100%}
.md-t th,.md-t td{border:1px solid #dce3ec;padding:6px 10px;text-align:right}
.md-t th{background:#e3f2fd;color:#0d47a1}
.pdate{font-size:.75rem;color:#78909c}
.cards{display:flex;flex-direction:column;gap:10px}
.card{background:#fff;border:1px solid #dce3ec;border-radius:12px;padding:14px}
.card h3{font-size:1rem;margin-bottom:6px}.card h3 a{color:#1565c0;text-decoration:none}
.card p{font-size:.84rem;color:#455a64;margin:0 0 8px}.card .pdate{display:block;margin-bottom:6px}
.readmore{font-size:.82rem;color:#fff;background:#1565c0;border-radius:8px;padding:6px 14px;text-decoration:none;display:inline-block}
"""


def build_post_page(p) -> str:
    url = f"blog/{p['slug']}/"
    article_body = p["body"]
    title = f"{p['title']} | DDSVerified"
    article_img = f"{BASE}/{p['image']}" if p["image"] else SQUARE_LOGO
    date_fa = p["date"]
    crumbs = f'<a href="/">خانه</a> › <a href="/blog/">وبلاگ</a> › {p["title"]}'
    body = f"""
<h1>{p['title']}</h1>
<span class="pdate">📅 {date_fa} · DDSVerified</span>
<article class="post">
{md_to_html(article_body)}
</article>
{TRUST_HTML}
<p><a class="cta" href="/">🛒 مشاهده و خرید فرزهای دندانپزشکی</a></p>"""
    ld_article = json.dumps({"@context": "https://schema.org", "@type": "Article",
                             "headline": p["title"], "description": p["description"],
                             "image": article_img, "datePublished": p["date"],
                             "author": {"@type": "Organization", "name": "DDSVerified"},
                             "publisher": {"@type": "Organization", "name": "DDSVerified"},
                             "mainEntityOfPage": f"{BASE}/{url}"}, ensure_ascii=False)
    ld_bc = json.dumps({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "خانه", "item": f"{BASE}/"},
        {"@type": "ListItem", "position": 2, "name": "وبلاگ", "item": f"{BASE}/blog/"},
        {"@type": "ListItem", "position": 3, "name": p["title"], "item": f"{BASE}/{url}"}]}, ensure_ascii=False)
    extra = (f'<style>{BLOG_CSS}</style>\n'
             f'<script type="application/ld+json">{ld_article}</script>\n'
             f'<script type="application/ld+json">{ld_bc}</script>')
    return _layout(title, p["description"], url, crumbs, body, extra)


def build_blog_index(posts: list) -> str:
    title = "وبلاگ DDSVerified — راهنمای خرید فرز دندانپزشکی"
    desc = "راهنماهای خرید فرز دندانپزشکی، آموزش انتخاب فرز بر اساس رنگ دور، کد ISO و شکل فرز."
    if posts:
        cards = "".join(
            f"""<div class="card">
<span class="pdate">📅 {p['date']}</span>
<h3><a href="/blog/{p['slug']}/">{p['title']}</a></h3>
<p>{p['description']}</p>
<a class="readmore" href="/blog/{p['slug']}/">ادامه مطلب ←</a>
</div>""" for p in posts)
        posts_html = f'<div class="cards">{cards}</div>'
    else:
        posts_html = ""
    body = f"""
<h1>راهنمای فرزهای دندانپزشکی</h1>
<div class="intro"><p>در این بخش راهنماهای جامع انتخاب و خرید فرز دندانپزشکی منتشر می‌شود: معنی رنگ دور فرزها، مفهوم کد ISO، انتخاب فرز مناسب هر کار کلینیکی و مقایسه خانواده‌های مختلف فرز الماسی.</p>
<p>برای مشاهده و خرید محصولات، به <a href="/">صفحه اصلی فروشگاه</a> مراجعه کنید.</p></div>
{posts_html}"""
    crumbs = '<a href="/">خانه</a> › وبلاگ'
    return _layout(title, desc, "blog/", crumbs, body, f"<style>{BLOG_CSS}</style>")


# ------------------------------------------------------------ campaign ----
CAMPAIGN_SLUG = "pack-400"


def campaign_page_url() -> str:
    """Landing page for the temporary 400-bur campaign bundle."""
    return f"campaign/{CAMPAIGN_SLUG}/"


CAMPAIGN_CSS = (
    '.cmp-price{font-size:1.5rem;font-weight:800;color:#ef6c00;margin:10px 0 4px}'
    '.cmp-price small{font-weight:400;font-size:.75rem;color:#78909c}'
    '.cmp-bullets{margin:12px 0 12px 20px;line-height:2}'
    '.cmp-contents{background:#fff;border:1px solid #dce3ec;border-radius:10px;padding:12px 14px;font-size:.88rem;margin:14px 0}'
    '.cmp-contents ul{margin:8px 0 8px 20px;line-height:2}'
    '.hero-img-wrap{width:100%;margin:0 0 14px;border-radius:var(--radius);overflow:hidden;box-shadow:var(--shadow-lg);border:1px solid var(--border);line-height:0}'
    '.hero-img-wrap img{width:100%;height:auto;display:block}'
)


def build_campaign_page(p: dict, data: dict) -> bool:
    """Landing page for the limited-time 400-bur bundle.

    Rendered only while the PRODUCTS row carries a truthy `bundle` flag; remove
    the flag and the page disappears from regeneration (cleanup in main()).
    Deliberately NOT a /product/ page: the offer is temporary and bought
    traffic only (short link /x1/), so it stays out of the sitemap, Torob and
    the Emalls feed.
    """
    if not p.get("bundle"):
        return False
    model = p["model"]
    price = int(p["price"])  # bundle total is its own JSON product price, not the per-bur default
    quantity = int(p.get("multiplier") or 400)
    standard_total = quantity * int(data["price_per_bur"])
    savings_percent = round(100 * (1 - price / standard_total)) if standard_total > price else 0
    title = p.get("card_title") or "بسته فرزهای پرمصرف"
    slug = campaign_page_url()
    d = os.path.join("campaign", CAMPAIGN_SLUG)
    os.makedirs(d, exist_ok=True)
    intro = f"بسته {fa(quantity)} عددی با ترکیبی از مدل‌های پرمصرف برای کارهای ترمیمی، اندو و پروتز ثابت؛ مدل‌ها و تعداد هر کدام را پیش از خرید بررسی کنید."

    bullets = [
        "✅ ترکیبی از شکل‌ها و دورهای مختلف برای کاربردهای متنوع",
        "✅ مشخصات مدل‌ها برای انتخاب دقیق‌تر",
        "✅ مناسب کارهای ترمیمی، اندو و پروتز ثابت",
    ]
    if p.get("free_shipping"):
        bullets.append("✅ ارسال رایگان بسته")
    faqs = [
        ("چه فرزهایی در این بسته هست؟",
         "این بسته ترکیبی از شکل‌های پرمصرف برای کارهای ترمیمی، اندو و پروتز ثابت است. "
         "پیش از خرید، تصویر محتویات بسته و مشخصات مدل‌ها را بررسی کنید."),
        ("قیمت بسته چطور تعیین می‌شود؟",
         "قیمت کل بسته در همین صفحه درج شده و بر اساس قیمت ثبت‌شده برای این محصول است؛ "
         "قیمت هر عدد نیز از تقسیم قیمت بسته بر تعداد فرزها محاسبه می‌شود."),
        ("ارسال بسته چگونه است؟",
         "شرایط ارسال این بسته در همین صفحه و هنگام ثبت سفارش نمایش داده می‌شود."),
    ]
    faq_html = "".join(
        f'<details open><summary>{q}</summary><div>{a}</div></details>' for q, a in faqs)
    bullets_html = "\n".join(f"<li>{b}</li>" for b in bullets)

    ld_product = json.dumps({"@context": "https://schema.org", "@type": "Product",
                             "name": title,
                             "image": [img_rel("400-ferez-1")],
                             "description": intro,
                             "sku": model,
                             "brand": {"@type": "Brand", "name": "DDSVerified"},
                             "url": f"{BASE}/{slug}",
                             "offers": {"@type": "Offer",
                                        "url": f"{BASE}/{slug}",
                                        "priceCurrency": "IRR",
                                        "price": price * 10,  # IRR; displayed prices are toman
                                        "itemCondition": "https://schema.org/NewCondition",
                                        "availability": "https://schema.org/InStock" if p.get("inventory", 0) > 0 else "https://schema.org/OutOfStock"}},
                            ensure_ascii=False)
    ld_faq = json.dumps({"@context": "https://schema.org", "@type": "FAQPage",
                         "mainEntity": [{"@type": "Question", "name": q,
                                         "acceptedAnswer": {"@type": "Answer", "text": a}}
                                        for q, a in faqs]}, ensure_ascii=False)

    extra = (f'<script type="application/ld+json">{ld_product}</script>\n'
             f'<script type="application/ld+json">{ld_faq}</script>\n'
             f'<style>{CAMPAIGN_CSS}</style>')

    hero_img = img_rel("400-ferez-1")

    body = f"""
<figure class="hero-img-wrap"><img src="{hero_img}" srcset="{hero_img} 770w, {hero_img} 1540w" sizes="(max-width:768px) 100vw, 1256w" alt="{title}" width="1540" height="866" fetchpriority="high" decoding="async"></figure>
<h1>{title}</h1>
<div class="intro"><p>{intro}</p></div>
<div class="cmp-price">{fmt_price(price)} تومان <small>({fmt_price(price // quantity)} تومان به ازای هر عدد فرز)</small></div>
<p>{f'حدود {fa(savings_percent)}٪ کمتر از خرید {fa(quantity)} فرز معمولی با قیمت پایه' if savings_percent else 'مجموعه‌ای از مدل‌های متنوع در یک بسته'}</p>
<ul class="cmp-bullets">
{bullets_html}
</ul>
<figure class="bp-figure"><img src="{img_rel(p.get('details_img') or model)}" alt="تصویر محتویات بسته {fa(quantity)} عددی" loading="lazy" decoding="async"></figure>
<div class="cmp-contents">
<h2>چه فرزهایی در این بسته هست؟</h2>
<p>مدل‌های مختلف برای کارهای ترمیمی، اندو و پروتز ثابت در این بسته گردآوری شده‌اند.</p>
<ul>
<li><b>ترمیمی:</b> نیدل و نیدل پرداخت، فلیم و فلیم پرداخت، فلیم شنک بلند نازک، فوتبالی و فوتبالی پرداخت، فیشور کوتاه، تیپر کوتاه و بلند روند اند، روند و ...</li>
<li><b>اندو:</b> فیشور بلند، روند بلند، روند کوتاه، تیپر روند اند، نیدل و ...</li>
<li><b>پروتز ثابت:</b> تیپر فلت اند، چمفر، تورپیدو سیلندری، روند اند تیپر، فیشور بلند و ...</li>
</ul>
<p>برای اطمینان از تناسب مدل‌ها و تعداد هر مدل با نیاز خود، تصویر محتویات بسته را بررسی کنید.</p>
</div>
<h2>پرسشهای متداول</h2>
<div class="faq">{faq_html}</div>
<a class="cta" href="/index.html#{quote(model)}">🛒 خرید {title} — افزودن به سبد خرید</a>
{TRUST_HTML}"""

    crumbs = f'<a href="/">خانه</a> › {title}'
    html = _layout(title, intro, slug, crumbs, body, extra)
    with open(os.path.join(d, "index.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    return True
def build_sitemap(data, posts=None) -> str:
    urls = [("", "1.0"), ("blog/", "0.6")]
    for collection_key in COLLECTIONS:
        if collection_products(data, collection_key):
            urls.append((collection_url(collection_key), "0.9"))
    for key in group_by_page(data):
        if key == "bundle":
            continue  # temporary campaign bundle: not for search engines
        urls.append((cat_url(key), "0.9"))
    for p in sorted(data["products"], key=lambda x: x["model"]):
        if p.get("bundle"):
            continue  # campaign landing page is noindex (short-link traffic only)
        urls.append((product_page_url(p["model"]), "0.8"))
    for p in (posts or []):
        urls.append((f"blog/{p['slug']}/", "0.7"))
    today = __import__("datetime").date.today().isoformat()
    entries = "\n".join(
        f"  <url>\n    <loc>{BASE}/{path}</loc>\n    <lastmod>{today}</lastmod>\n    <priority>{pri}</priority>\n  </url>"
        for path, pri in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{entries}\n</urlset>\n'
CSS = """*{box-sizing:border-box;margin:0}body{font-family:'Vazirmatn',Tahoma,Arial,sans-serif;line-height:1.7;background:#f5f7fa;color:#263238}
.wrap{max-width:880px;margin:0 auto;padding:14px}.crumbs{font-size:.78rem;margin-bottom:12px;color:#78909c}
.crumbs a{color:#1565c0;text-decoration:none}h1{font-size:1.3rem;color:#0d47a1;margin:.4rem 0 .6rem}
.intro{background:#fff;border:1px solid #dce3ec;border-radius:10px;padding:12px 14px;font-size:.9rem;margin-bottom:14px}
.grits{display:flex;gap:6px;flex-wrap:wrap;font-size:.78rem;margin:10px 0}.grits span{background:#fff;border:1px solid #dce3ec;border-radius:20px;padding:2px 10px}
h2{font-size:1.05rem;color:#0d47a1;margin:18px 0 10px}
.model-block{background:#fff;border:1px solid #dce3ec;border-radius:12px;padding:14px;margin-bottom:14px;scroll-margin-top:12px}
.model-head{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap}
.model-head h3{font-size:1rem;color:#1565c0}.stock{font-size:.72rem;font-weight:700;border-radius:14px;padding:2px 10px}
.stock.in{background:#e8f5e9;color:#2e7d32}.stock.out{background:#ffebee;color:#c62828}
.mbody{display:flex;gap:14px;margin-top:10px;flex-wrap:wrap}.mbody img{width:120px;height:180px;object-fit:contain;background:#e3f2fd;border-radius:8px;padding:6px;flex-shrink:0}
.bp-figure{margin:14px 0}.bp-figure img{width:100%;height:auto;border-radius:10px;display:block}.bp-figure figcaption{font-size:.75rem;color:#78909c;text-align:center;margin-top:6px}
.specs-t{flex:1;min-width:230px;font-size:.84rem}.specs-t td{padding:3px 8px;border-bottom:1px dashed #eceff1}
.specs-t td:first-child{color:#78909c;width:90px}
.price{font-size:1.15rem;font-weight:800;color:#ef6c00;margin-top:10px}.price small{font-weight:400;font-size:.72rem;color:#78909c}
.cta{display:block;background:#1565c0;color:#fff;text-align:center;padding:11px;border-radius:10px;text-decoration:none;font-weight:700;font-size:.9rem;margin-top:10px}
.faq details{background:#fff;border:1px solid #dce3ec;border-radius:10px;padding:10px 14px;margin-bottom:8px;font-size:.88rem}
.faq summary{cursor:pointer;font-weight:700;color:#37474f}.related a{display:inline-block;background:#fff;border:1px solid #dce3ec;border-radius:20px;padding:4px 12px;margin:3px;text-decoration:none;color:#1565c0;font-size:.82rem}
.trust{display:flex;gap:10px;font-size:.75rem;color:#455a64;margin:16px 0;flex-wrap:wrap}
.endo-z-reasons{background:linear-gradient(135deg,#e3f2fd,#fff);border:1px solid #90caf9;border-right:5px solid #1565c0;border-radius:14px;padding:18px 20px;margin:18px 0;box-shadow:0 6px 18px rgba(21,101,192,.12)}
.endo-z-reasons h2{margin:0 0 8px;color:#0d47a1}.endo-z-reasons p{margin-bottom:6px}.endo-z-reasons ol{padding-right:22px}.endo-z-reasons li{padding:4px 0}.endo-z-reasons a{color:#1565c0;font-weight:700;text-decoration:none}.endo-z-reasons a:hover{text-decoration:underline}
header{background:#fffefa;color:#071b41;border-bottom:1px solid #e1ded6}header .wrap{display:flex;align-items:center;gap:16px;flex-wrap:wrap;padding:12px 14px}
header a{color:#071b41;text-decoration:none;font-weight:800;font-size:.95rem}.brand img{display:block;width:185px;max-width:100%;height:auto}
.site-search{display:flex;flex:1;min-width:220px;max-width:420px;gap:6px}.site-search input{min-width:0;flex:1;padding:8px 10px;border:1px solid #dce3ec;border-radius:8px;font:inherit}
.site-search button{padding:8px 14px;border:0;border-radius:8px;background:#fff;color:#0d47a1;font:inherit;font-weight:700;cursor:pointer}
.model-head h3 a{color:#1565c0;text-decoration:none}
footer{text-align:center;font-size:.78rem;color:#455a64;padding:18px}footer .contact-links{display:flex;justify-content:center;flex-wrap:wrap;gap:8px;margin:0 auto 12px}
footer .contact-links a{display:inline-flex;align-items:center;gap:5px;padding:5px 9px;border:1px solid #dce3ec;border-radius:8px;color:#1565c0;background:#fff;text-decoration:none}
footer .contact-links svg{width:20px;height:20px;flex:none}footer p{margin:4px 0}"""


CONTACT_LINKS = f"""<nav class="contact-links" aria-label="راه‌های ارتباطی">
<a href="tel:{CONTACT_NUMBER}"><svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 3h4l1 5-2 2a16 16 0 0 0 5 5l2-2 5 1v4c0 2-2 3-4 3A18 18 0 0 1 3 7c0-2 1-4 3-4z"/></svg>تماس: {fa(CONTACT_NUMBER)}</a>
<a href="sms:{CONTACT_NUMBER}"><svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 4h18v14H8l-5 3V4z"/><path d="M7 9h10M7 13h7"/></svg>پیامک</a>
<a href="https://t.me/ddsverified_admin" target="_blank" rel="noopener noreferrer"><svg viewBox="0 0 24 24" aria-hidden="true" fill="#229ED9"><path d="M22 3 2 11l7 2 2 7 3.5-5 4.5 3L22 3zM10 13l9-7-7 9-1 3-1-5z"/></svg>تلگرام</a>
<a href="https://ble.ir/ddsverified_admin" target="_blank" rel="noopener noreferrer"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="1" y="1" width="22" height="22" rx="7" fill="#29a87d"/><path d="M6 6h6c5 0 5 5 2 6 4 1 3 6-2 6H6V6zm3 3v2h3c2 0 2-2 0-2H9zm0 5v2h3c2 0 2-2 0-2H9z" fill="#fff"/></svg>بله</a>
<a href="https://rubika.ir/ddsverified_admin" target="_blank" rel="noopener noreferrer"><svg viewBox="0 0 24 24" aria-hidden="true" fill="none"><path d="M12 1 23 12 12 23 1 12 12 1z" fill="#eb3758"/><path d="m10 7 8 5-8 5V7z" fill="#fff"/></svg>روبیکا</a>
</nav>"""


def _layout(title, description, canonical_path, crumbs_html, body_html, extra_head=""):
    canon = f"{BASE}/{canonical_path}"
    return f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="{description}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{canon}">
<link rel="icon" type="image/webp" href="{SQUARE_LOGO}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:type" content="website">
<meta property="og:url" content="{canon}">
<meta property="og:image" content="{SQUARE_LOGO}">
<meta property="og:site_name" content="DDSVerified">
<meta property="og:locale" content="fa_IR">
<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>
<link href="https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/Vazirmatn-font-face.css" rel="stylesheet">
<style>{CSS}</style>
<!-- GA4 — deferred to preserve page performance -->
<script>window.gaId='G-DW63K5FG8M';addEventListener('load',function(){{var s=document.createElement('script');s.src='https://www.googletagmanager.com/gtag/js?id='+window.gaId;s.async=true;document.head.appendChild(s);window.dataLayer=window.dataLayer||[];function g(){{dataLayer.push(arguments)}}window.gtag=g;g('js',new Date());g('config',window.gaId)}});</script>
{extra_head}
</head>
<body>
<header><div class="wrap"><a class="brand" href="/" aria-label="DDSVerified — صفحه اصلی"><img src="{WORDMARK}" alt="DDSVerified" width="185" height="60"></a><form class="site-search" action="/" method="get" role="search"><input type="search" name="q" aria-label="جستجوی فرزها" placeholder="جستجوی مدل یا نوع فرز" required><button type="submit">جستجو</button></form></div></header>
<div class="wrap">
<nav class="crumbs">{crumbs_html}</nav>
{body_html}
</div>
<footer>{CONTACT_LINKS}<p>DDSVerified © · تنوع مدل و دور فرز برای انتخاب متناسب با نیاز شما · ddsverified.ir</p></footer>
</body>
</html>"""


# ------------------------------------------------------------ builders -----
def _model_block(p, shape_name_short, data):
    model = p["model"]
    in_stock = p["inventory"] > 0
    grit_fa = data["grits"].get(p["grit"], GRIT_LABELS.get(p["grit"], "-"))
    pack_note = ("تک‌فروشی یا بسته ۶ عددی" if p.get("pack_size") else "فروش تکی") if p.get("multiplier") == 1 else f"بسته {fa(data['burs_per_pack'])} عددی"
    price = product_price(p, data)
    length_td = f'<tr><td>طول</td><td>{fa(p["length"])} mm</td></tr>' if p["length"] != "-" else ""
    dia_td = f'<tr><td>قطر</td><td>{fa(p["diameter"])}</td></tr>' if p["diameter"] != "-" else ""
    alt = f"فرز {shape_name_short} {model}"
    stock_badge = '<span class="stock in">موجود</span>' if in_stock else '<span class="stock out">ناموجود</span>'
    return f"""
<section class="model-block" id="{anchor_id(model)}">
  <div class="model-head"><h3><a href="/{product_page_url(model)}">فرز {shape_name_short} مدل {model}</a></h3>{stock_badge}</div>
  <div class="mbody">
    <img src="{img_rel(model)}" alt="{alt}" width="267" height="400" loading="lazy">
    <table class="specs-t">
      {dia_td}{length_td}
      <tr><td>دور (گریت)</td><td>{grit_fa}</td></tr>
      <tr><td>کد ISO</td><td dir="ltr">{p.get('iso', '−')}</td></tr>
      <tr><td>کد USA</td><td dir="ltr">{p.get('usa', '−')}</td></tr>
      <tr><td>بسته‌بندی</td><td>{pack_note}</td></tr>
    </table>
  </div>
  <p class="price">{fmt_price(price)} تومان <small>/ هر عدد</small></p>
  <a class="cta" href="/index.html#{quote(model)}">🛒 خرید فرز {model} — افزودن به سبد خرید</a>
</section>"""


def build_category_page(shape_key, data):
    products = group_by_page(data)[shape_key]
    sname = shape_fa(shape_key, data)
    # short display name for headings (strip the common prefix "فرز دندانپزشکی ")
    short = sname.replace("فرز دندانپزشکی ", "").replace("فرز ", "", 1) if sname.startswith("فرز") else sname
    slug_url = cat_url(shape_key)
    n_models = fa(len(products))

    title = f"فرز {short} | {n_models} مدل باکیفیت | DDSVerified"
    desc = f"فرز دندانپزشکی {short} در {n_models} مدل با اندازه‌ها و گریت‌های مختلف؛ مشخصات فنی و کد ISO و USA برای انتخاب دقیق و ارسال به سراسر ایران."
    intro = INTROS.get(shape_key, f"{sname} در مدل‌ها و دورهای مختلف عرضه می‌شود. مشخصات فنی هر مدل را برای انتخاب متناسب با نیاز خود بررسی کنید.")

    grit_strip = "".join(f"<span>{data['grits'].get(g_, GRIT_LABELS[g_])}</span>" for g_ in GRIT_ORDER)
    blocks = "".join(_model_block(p, short, data) for p in products)

    faq_items = FAQS.get(shape_key, []) + FAQS["_common"]
    faq_html = "".join(f"<details><summary>{q}</summary><p>{a}</p></details>" for q, a in faq_items)

    related_keys = [k for k in group_by_page(data) if k != shape_key][:4]
    related_html = "".join(f'<a href="/{cat_url(k)}">{shape_fa(k, data)}</a>' for k in related_keys)

    ld_items = [{"@type": "ListItem", "position": i + 1,
                 "item": {"@type": "Product", "name": f"فرز {short} {p['model']}",
                          "image": img_rel(p["model"]),
                          "sku": p["model"],
                          "brand": {"@type": "Brand", "name": "DDSVerified"},
                          "offers": {"@type": "Offer", "priceCurrency": "IRR",
                                     "price": product_price(p, data) * 10,  # IRR; catalog prices are toman
                                     "availability": "https://schema.org/InStock" if p["inventory"] > 0 else "https://schema.org/OutOfStock"}}}
                for i, p in enumerate(products)]
    ld_itemlist = json.dumps({"@context": "https://schema.org", "@type": "ItemList", "itemListElement": ld_items}, ensure_ascii=False)
    ld_bc = json.dumps({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "خانه", "item": f"{BASE}/"},
        {"@type": "ListItem", "position": 2, "name": short, "item": f"{BASE}/{slug_url}"}]}, ensure_ascii=False)
    ld_faq = json.dumps({"@context": "https://schema.org", "@type": "FAQPage",
                         "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq_items]}, ensure_ascii=False)
    extra = (f'<script type="application/ld+json">{ld_itemlist}</script>\n'
             f'<script type="application/ld+json">{ld_bc}</script>\n'
             f'<script type="application/ld+json">{ld_faq}</script>')

    body = f"""
<h1>خرید {short}</h1>
<div class="intro"><p>{intro}</p>
<p class="grits">ترتیب سختی دور فرز از سخت‌ترین به نرم‌ترین: {grit_strip}</p></div>
<h2>مدل‌های موجود ({n_models} مدل)</h2>
{blocks}
<h2>پرسش‌های متداول درباره {short}</h2>
<div class="faq">{faq_html}</div>
<h2>خانواده‌های دیگر</h2>
<div class="related">{related_html}</div>
{TRUST_HTML}"""
    crumbs = f'<a href="/">خانه</a> › {short}'
    return _layout(title, desc, slug_url, crumbs, body, extra)


def build_product_page(p, data) -> str:
    """Per-product static page (Option A): full spec content, Product JSON-LD,
    self-canonical /product/<model>/ — the crawlable URL Torob/Emalls fetchers need."""
    model = p["model"]
    shape_key = p["shape"]
    sname = shape_fa(shape_key, data)
    short = sname.replace("فرز دندانپزشکی ", "").replace("فرز ", "", 1) if sname.startswith("فرز") else sname
    slug = anchor_id(model)
    page_path = product_page_url(model)
    cat_path = cat_url(shape_key)
    price = product_price(p, data)
    in_stock = p["inventory"] > 0
    grit_fa = data["grits"].get(p["grit"], GRIT_LABELS.get(p["grit"], "-"))

    # --- unique spec-driven sentences (only fields this product actually has) ---
    spec_bits = []
    if p.get("diameter") not in (None, "", "-"):
        spec_bits.append(f"قطر سر کاری {fa(p['diameter'])} میلی‌متر (استاندارد ISO {fa(p['diameter'])})")
    if p.get("length") not in (None, "", "-"):
        spec_bits.append(f"طول شنک {fa(p['length'])} میلی‌متر")
    if grit_fa != "-":
        spec_bits.append(f"دور الماسی {grit_fa}")
    if p.get("usa"):
        spec_bits.append(f"معادل کد آمریکا {p['usa']}")
    if p.get("flutes"):
        spec_bits.insert(0, f"پیکربندی {fa(p['flutes'])} فلوت")
    spec_sentence = "به‌همراه " + "، ".join(spec_bits) + " است." if spec_bits else ""
    if p.get("flutes"):
        remaining_specs = "، ".join(spec_bits[1:])
        spec_sentence = f"دارای پیکربندی {fa(p['flutes'])} فلوت است" + (f" و به‌همراه {remaining_specs} است." if remaining_specs else ".")
    pack_note = ("تک‌فروشی (هر عدد جداگانه) یا بسته ۶ عددی" if p.get("pack_size") else "تک‌فروشی (هر عدد جداگانه)") if p.get("multiplier") == 1 else f"بسته {fa(data['burs_per_pack'])} عددی"
    clinical = p.get("desc") or INTROS.get(shape_key, f"{sname} یکی از خانواده‌های پرکاربرد فرزهای دندانپزشکی است.")
    clinical_lead = "" if clinical.startswith("فرز") else "این فرز "
    endo_z_reasons = """
<div class="endo-z-reasons">
  <h2>چرا باید فرز اندو زد بگیرید؟</h2>
  <p>چون:</p>
  <ol>
    <li>سرعت کار شما را سریع‌تر می‌کند. <a href="https://pmc.ncbi.nlm.nih.gov/articles/PMC8378494/" target="_blank" rel="noopener noreferrer">منبع پژوهش</a></li>
    <li>دیواره صاف‌تر و smooth‌تر به شما می‌دهد. <a href="https://pmc.ncbi.nlm.nih.gov/articles/PMC8378494/" target="_blank" rel="noopener noreferrer">منبع پژوهش</a></li>
    <li>ریسک پرفوریشن به حداقل می‌رسد. <a href="https://www.nature.com/articles/s41415-025-8442-8" target="_blank" rel="noopener noreferrer">منبع پژوهش</a></li>
    <li>فرز استاندارد در تهیه حفره دسترسی است. <a href="https://www.nature.com/articles/s41415-025-8442-8" target="_blank" rel="noopener noreferrer">منبع پژوهش</a></li>
  </ol>
</div>
""" if model == "ENDO-Z TI" else ""

    siblings = [q for q in group_by_page(data)[shape_key] if q["model"] != model]
    sib_html = "".join(
        f'<a href="/{product_page_url(q["model"])}">{q["model"]}</a>' for q in siblings)
    stock_badge = '<span class="stock in">موجود در انبار</span>' if in_stock else '<span class="stock out">ناموجود</span>'

    title = f"فرز {short} {model} | مشخصات و کیفیت | DDSVerified"
    desc = (f"فرز دندانپزشکی {short} مدل {model} — {spec_bits[0] if spec_bits else sname}، "
            f"گریت و مشخصات فنی، کد ISO و USA؛ انتخاب دقیق مدل و ارسال به سراسر ایران.")
    # optional full-width technical drawing (details_img on the PRODUCTS row)
    blueprint_html = ""
    if p.get("details_img"):
        d_img = p["details_img"]
        blueprint_html = (
            f'<figure class="bp-figure"><picture>'
            f'<source media="(max-width:600px)" srcset="{img_rel(d_img + "-700")}">'
            f'<img src="{img_rel(d_img)}" width="1280" height="898" loading="lazy" decoding="async" '
            f'alt="نقشه فنی فرز {model} — شنک کارباید تنگستن، فلوت مارپیچ، نوک غیربرنده">'
            f'</picture><figcaption>نقشه فنی فرز {model}: شنک کارباید تنگستن، فلوت مارپیچ دوهلیکس، نوک غیربرنده</figcaption></figure>')
    body = f"""
<h1>فرز {short} مدل {model}</h1>
<div class="intro"><p>{sname} مدل <strong>{model}</strong> {spec_sentence} {clinical_lead}{clinical.strip()}</p>
<p>برای انتخاب مدل متناسب با نیاز خود، شکل، دور فرز و مشخصات فنی درج‌شده در جدول را بررسی کنید.</p></div>
{endo_z_reasons}
<section class="model-block">
  <div class="model-head"><h3>مشخصات فنی فرز {model}</h3>{stock_badge}</div>
  <div class="mbody">
    <img src="{img_rel(model)}" alt="فرز {short} مدل {model} دندانپزشکی" width="267" height="400" loading="lazy">
    <table class="specs-t">
      <tr><td>مدل</td><td dir="ltr">{model}</td></tr>
      <tr><td>خانواده</td><td><a href="/{cat_path}">{sname}</a></td></tr>
      {'<tr><td>قطر</td><td>' + fa(p['diameter']) + '</td></tr>' if p.get("diameter") not in (None, "", "-") else ''}
      {'<tr><td>طول</td><td>' + fa(p['length']) + ' mm</td></tr>' if p.get("length") not in (None, "", "-") else ''}
      <tr><td>دور (گریت)</td><td>{grit_fa}</td></tr>
      <tr><td>کد ISO</td><td dir="ltr">{p.get('iso', '−')}</td></tr>
      <tr><td>کد USA</td><td dir="ltr">{p.get('usa', '−')}</td></tr>
      {'<tr><td>تعداد فلوت</td><td>' + fa(p['flutes']) + ' فلوت</td></tr>' if p.get('flutes') else ''}
      <tr><td>بسته‌بندی</td><td>{pack_note}</td></tr>
    </table>
  </div>
  {blueprint_html}
  <p class="price">{fmt_price(price)} تومان <small>/ هر عدد</small></p>
  <a class="cta" href="/index.html#{quote(model)}">🛒 خرید فرز {model} — افزودن به سبد خرید</a>
</section>
{TRUST_HTML}
<h2>سایر مدل‌های {short}</h2>
<div class="related">{sib_html}</div>
<p><a class="cta" href="/{cat_path}">← مشاهده همه مدل‌های {short}</a></p>"""

    ld_product = json.dumps({"@context": "https://schema.org", "@type": "Product",
                             "name": f"فرز {short} مدل {model}",
                             "image": [img_rel(model)] + ([img_rel(p["details_img"])] if p.get("details_img") else []),
                             "description": desc,
                             "sku": model,
                             "brand": {"@type": "Brand", "name": "DDSVerified"},
                             "url": f"{BASE}/{page_path}",
                             "offers": {"@type": "Offer",
                                        "url": f"{BASE}/{page_path}",
                                        "priceCurrency": "IRR",
                                        "price": price * 10,  # IRR; displayed prices are toman
                                        "itemCondition": "https://schema.org/NewCondition",
                                        "availability": "https://schema.org/InStock" if in_stock else "https://schema.org/OutOfStock"}},
                            ensure_ascii=False)
    ld_bc = json.dumps({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "خانه", "item": f"{BASE}/"},
        {"@type": "ListItem", "position": 2, "name": short, "item": f"{BASE}/{cat_path}"},
        {"@type": "ListItem", "position": 3, "name": f"فرز {short} {model}", "item": f"{BASE}/{page_path}"}]},
        ensure_ascii=False)
    extra = (f'<script type="application/ld+json">{ld_product}</script>\n'
             f'<script type="application/ld+json">{ld_bc}</script>')
    crumbs = f'<a href="/">خانه</a> › <a href="/{cat_path}">{short}</a> › {model}'
    return _layout(title, desc, page_path, crumbs, body, extra)


# ------------------------------------------------- homepage Drs Choice slider ----
# Markers inside index.html that delimit the auto-managed slider block.
HOME_SLIDER_START = "<!-- BLOG:DRS-CHOICE-START -->"
HOME_SLIDER_END = "<!-- BLOG:DRS-CHOICE-END -->"

DRS_CHOICE_TAG = "Drs' Choice"

SLIDER_CSS_MARK = "/* BLOG:SLIDER-CSS */"

HOME_SLIDER_CSS = SLIDER_CSS_MARK + """
.blogs-strip{margin:14px 0}
.blogs-strip-head{display:flex;align-items:center;gap:8px;margin-bottom:8px}
.blogs-strip-head h2{font-size:.95rem;color:var(--primary-dark);margin:0}
.blogs-strip-head .blogs-tag{font-size:.6rem;font-weight:700;color:#b45309;background:#fef3c7;border:1px solid #fcd34d;border-radius:20px;padding:2px 10px}
.pushbox{position:relative;height:58px;overflow:hidden}
.push-item{position:absolute;left:0;right:0;top:0;bottom:0;display:flex;align-items:center;justify-content:center;gap:8px;background:var(--card,#fff);border:1px solid var(--border,#dce3ec);border-radius:12px;padding:6px 16px;text-decoration:none;font-size:.8rem;font-weight:700;color:var(--primary-dark,#0d47a1);box-shadow:var(--shadow-sm,0 1px 4px rgba(0,0,0,.06));opacity:0;transform:translateX(-115%);line-height:1.5;text-align:center;overflow:hidden}
.push-item .bc-arrow{color:#1565c0;font-weight:400;flex-shrink:0}
.blogs-strip:hover .push-item,.blogs-strip:focus-within .push-item{animation-play-state:paused}
@media (prefers-reduced-motion: reduce){.push-item{animation:none!important}.push-item:not(:first-child){display:none}.push-item:first-child{opacity:1!important;transform:none!important}}
"""


def build_home_slider(posts: list) -> str:
    """Push rotator: one title bar at a time; next title pushes the current one out.
    Pure CSS (per-item animation-delay). No-op HTML if no post tagged DRS_CHOICE_TAG."""
    featured = [p for p in posts if DRS_CHOICE_TAG in p.get("tags", [])]
    if not featured:
        return ""
    n = len(featured)
    seg = 5.5                      # seconds each title stays
    total = round(seg * n, 2)
    # keyframe stops (percent of total cycle): each item is active during its seg window
    a, b, c = round(100 / n * 0.06, 2), round(100 / n * 0.80, 2), round(100 / n * 0.96, 2)
    kf = (f"@keyframes pushCycle{{0%{{opacity:0;transform:translateX(-115%)}}"
          f"{a}%{{opacity:1;transform:translateX(0)}}"
          f"{b}%{{opacity:1;transform:translateX(0)}}"
          f"{c}%{{opacity:0;transform:translateX(115%)}}"
          f"100%{{opacity:0;transform:translateX(115%)}}}}")
    items = "".join(
        f"""<a class="push-item" style="--i:{i}" href="/blog/{p['slug']}/">{p['title']}<span class="bc-arrow">←</span></a>"""
        for i, p in enumerate(featured))
    return f"""{HOME_SLIDER_START}
<section class="blogs-strip" aria-label="مطالب منتخب دندانپزشکان">
<style>.push-item{{animation:pushCycle {total}s linear infinite;animation-delay:calc(var(--i)*{seg}s)}}{kf}</style>
<div class="blogs-strip-head">
<h2>بخونین:</h2>
<span class="blogs-tag">Drs' Choice</span>
</div>
<div class="pushbox">{items}</div>
</section>
{HOME_SLIDER_END}"""


def inject_home_slider(html: str, slider_html: str) -> str:
    """Replace (or remove) the marked slider block inside index.html."""
    if slider_html:
        if HOME_SLIDER_START in html and HOME_SLIDER_END in html:
            start = html.index(HOME_SLIDER_START)
            end = html.index(HOME_SLIDER_END) + len(HOME_SLIDER_END)
            return html[:start] + slider_html + html[end:]
        # first run: insert after the Telegram join box in the hero column
        anchor = '</a>\n      <div class="hero-cert-row">'
        if anchor in html:
            return html.replace(anchor, '</a>\n' + slider_html + '\n      <div class="hero-cert-row">', 1)
        print("WARN: no slider markers and no hero anchor found in index.html — slider not injected")
        return html
    # no featured posts: strip existing block
    if HOME_SLIDER_START in html and HOME_SLIDER_END in html:
        start = html.index(HOME_SLIDER_START)
        end = html.index(HOME_SLIDER_END) + len(HOME_SLIDER_END)
        return html[:start] + html[end:]
    return html


def main():
    data = load_data()
    posts = load_posts()
    n = 0
    for collection_key in COLLECTIONS:
        if collection_products(data, collection_key):
            d = os.path.join("collection", COLLECTIONS[collection_key]["slug"])
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "index.html"), "w", encoding="utf-8", newline="\n") as f:
                f.write(build_collection_page(collection_key, data))
            n += 1
    for key in group_by_page(data):
        if key == "bundle":
            continue  # temporary bundle: no category page (not for search/marketplaces)
        d = f"category/{SLUGS[key]}"
        os.makedirs(d, exist_ok=True)
        with open(f"{d}/index.html", "w", encoding="utf-8", newline="\n") as f:
            f.write(build_category_page(key, data))
        n += 1
    os.makedirs("product", exist_ok=True)
    for p in sorted(data["products"], key=lambda x: x["model"]):
        if p.get("bundle"):
            if build_campaign_page(p, data):
                n += 1
            continue  # landing page instead of a spec product page (no Torob/Emalls)
        d = f"product/{anchor_id(p['model'])}"
        os.makedirs(d, exist_ok=True)
        with open(f"{d}/index.html", "w", encoding="utf-8", newline="\n") as f:
            f.write(build_product_page(p, data))
        n += 1
    os.makedirs("blog", exist_ok=True)
    with open("blog/index.html", "w", encoding="utf-8", newline="\n") as f:
        f.write(build_blog_index(posts))
    n += 1
    # The homepage is maintained separately; regeneration must not overwrite it.
    for p in posts:
        d = f"blog/{p['slug']}"
        os.makedirs(d, exist_ok=True)
        with open(f"{d}/index.html", "w", encoding="utf-8", newline="\n") as f:
            f.write(build_post_page(p))
        n += 1
    # drop the campaign landing page when no bundle row is flagged anymore
    import shutil
    cdir = os.path.join("campaign", CAMPAIGN_SLUG)
    if not any(p.get("bundle") for p in data["products"]) and os.path.isdir(cdir):
        shutil.rmtree(cdir)
        print("removed stale campaign landing page")
    with open("sitemap.xml", "w", encoding="utf-8", newline="\n") as f:
        f.write(build_sitemap(data, posts))
    print(f"Generated {n} pages + sitemap ({len(group_by_page(data))} categories, {len(posts)} blog posts)")


if __name__ == "__main__":
    main()

"""Static category-page generator for ddsverified.ir — Phase 1 architecture.

Reads products_data.json (extracted from index.html via tools/extract_products.py)
and emits one static, zero-JS HTML page per bur SHAPE under /category/<slug>/.
Re-run any time data changes: python3 generate_pages.py
"""
import json
import os
from urllib.parse import quote

BASE = "https://ddsverified.ir"
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
}

# Persian display overrides (owner-confirmed naming; falls back to SHAPE_MAP value)
SHAPE_OVERRIDE = {
    "pointed_cylinder": {"fa": "فرز دندانپزشکی شمفر استوانه ایی"},
}

GRIT_ORDER = ["K⚫", "G🟢", "B🔵", "Y🟡", "R🔴"]  # hardest → softest


def fa(n) -> str:
    return str(n).translate(FA_DIGITS)


def load_data() -> dict:
    return json.load(open("products_data.json", encoding="utf-8"))


def shape_fa(key: str, data: dict) -> str:
    return SHAPE_OVERRIDE.get(key, {}).get("fa") or data["shapes"].get(key, key)


def anchor_id(model: str) -> str:
    # "ENDO-Z TI" -> "endoz-ti": drop spaces, keep hyphens as separators
    return "".join(c for c in model.lower().replace(" ", "") if c.isalnum() or c == "-")


def group_by_page(data: dict) -> dict:
    groups = {}
    for p in sorted(data["products"], key=lambda x: x["model"]):
        groups.setdefault(p["shape"], []).append(p)
    return groups


def cat_url(shape_key: str) -> str:
    return f"category/{SLUGS[shape_key]}/"


def img_rel(model: str) -> str:
    """Absolute image path — safe from any page depth (/category/<slug>/ included)."""
    return quote(f"{BASE}/images/{model.lower()}.webp", safe="/:")


def fmt_price(price: int) -> str:
    return f"{price:,}".replace(",", "،")


# ---------------------------------------------------------------- intros ----
INTROS = {
    "needle": "فرز نیدل (سوزنی) به دلیل نوک بسیار ظریف و بلند خود، ابزار اصلی دسترسی به حفرات عمقی دندانی، آماده‌سازی کانال‌های ریشه و ترمیم‌های دقیق بین دندانی است. فرزهای الماسی نیدل DDSVerified پیش از ارسال توسط دندانپزشک تست و بررسی و آزمایش شده تا از کیفیت الماسی و عدم لرزش روی هد توربین مطمئن شوید.",
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
    "carbide": "فرز EndoZ کارباید تیتانیومی ساخت انگلیس، مخصوص برداشت گاتاپرکا و مواد داخل کانال پس از درمان ریشه است؛ تیغات مثبت آن مواد را خارج می‌کند و ریسک نفوذ به عاج را کمینه می‌سازد.",
}

FAQS = {
    "_common": [
        ("آیا فرزها اصل و تست‌شده هستند؟", "بله؛ تمام فرزهای DDSVerified پیش از ارسال شخصاً توسط دندانپزشک تست و بررسی و آزمایش شده و دارای گواهی TÜV Rheinland آلمان و ISO هستند."),
        ("ارسال چگونه است؟", "ارسال به سراسر ایران با پست انجام می‌شود. هزینه پست ۱۹۰,۰۰۰ تومان است که به‌صورت شفاف در تسویه محاسبه می‌شود؛ سفارش‌های بالای ۱۵۰ عدد ارسال رایگان دارند."),
        ("تخفیف عمده چگونه محاسبه می‌شود؟", "به ازای هر ۵ عدد فرز، ۰.۱٪ تخفیف پلکانی دریافت می‌کنید تا سقف ۱۰٪."),
    ],
}

# ---------------------------------------------------------------- layout ----
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
.specs-t{flex:1;min-width:230px;font-size:.84rem}.specs-t td{padding:3px 8px;border-bottom:1px dashed #eceff1}
.specs-t td:first-child{color:#78909c;width:90px}
.price{font-size:1.15rem;font-weight:800;color:#ef6c00;margin-top:10px}.price small{font-weight:400;font-size:.72rem;color:#78909c}
.cta{display:block;background:#1565c0;color:#fff;text-align:center;padding:11px;border-radius:10px;text-decoration:none;font-weight:700;font-size:.9rem;margin-top:10px}
.faq details{background:#fff;border:1px solid #dce3ec;border-radius:10px;padding:10px 14px;margin-bottom:8px;font-size:.88rem}
.faq summary{cursor:pointer;font-weight:700;color:#37474f}.related a{display:inline-block;background:#fff;border:1px solid #dce3ec;border-radius:20px;padding:4px 12px;margin:3px;text-decoration:none;color:#1565c0;font-size:.82rem}
.trust{display:flex;gap:10px;font-size:.75rem;color:#455a64;margin:16px 0;flex-wrap:wrap}
header{background:#1565c0;color:#fff}header .wrap{padding:12px 14px}header a{color:#fff;text-decoration:none;font-weight:800;font-size:.95rem}
footer{text-align:center;font-size:.72rem;color:#78909c;padding:18px}"""


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
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:type" content="website">
<meta property="og:url" content="{canon}">
<meta property="og:image" content="{BASE}/logo.webp">
<meta property="og:site_name" content="DDSVerified">
<meta property="og:locale" content="fa_IR">
<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>
<link href="https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/Vazirmatn-font-face.css" rel="stylesheet">
<style>{CSS}</style>
{extra_head}
</head>
<body>
<header><div class="wrap"><a href="/">DDSVerified — مرکز تخصصی فرزهای دندانپزشکی</a></div></header>
<div class="wrap">
<nav class="crumbs">{crumbs_html}</nav>
{body_html}
</div>
<footer>DDSVerified © — قبل از بیمار شما، اول ما امتحانش کردیم · ddsverified.ir</footer>
</body>
</html>"""


# ------------------------------------------------------------ builders -----
def _model_block(p, shape_name_short, data):
    model = p["model"]
    in_stock = p["inventory"] > 0
    grit_fa = data["grits"].get(p["grit"], "-")
    pack_note = "فروش تکی" if p.get("multiplier") == 1 else f"بسته {fa(data['burs_per_pack'])} عددی"
    price = p.get("price") or data["price_per_bur"]
    length_td = f'<tr><td>طول</td><td>{fa(p["length"])} mm</td></tr>' if p["length"] != "-" else ""
    dia_td = f'<tr><td>قطر</td><td>{fa(p["diameter"])}</td></tr>' if p["diameter"] != "-" else ""
    alt = f"فرز {shape_name_short} {model}"
    stock_badge = '<span class="stock in">موجود</span>' if in_stock else '<span class="stock out">ناموجود</span>'
    return f"""
<section class="model-block" id="{anchor_id(model)}">
  <div class="model-head"><h3>فرز {shape_name_short} مدل {model}</h3>{stock_badge}</div>
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

    title = f"خرید {short} | قیمت {n_models} مدل | DDSVerified"
    desc = f"خرید انواع {short} با تضمین کیفیت، تست‌شده توسط دندانپزشک. {n_models} مدل موجود با کد ISO و USA، قیمت روز و ارسال به سراسر ایران."
    intro = INTROS.get(shape_key, f"{sname} یکی از خانواده‌های پرکاربرد فرزهای دندانپزشکی است که در DDSVerified با تضمین کیفیت عرضه می‌شود.")

    grit_strip = "".join(f"<span>{data['grits'].get(g_, g_)}</span>" for g_ in GRIT_ORDER if g_ in data["grits"])
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
                                     "price": p.get("price") or data["price_per_bur"],
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
<div class="trust">✅ تست توسط دندانپزشک &nbsp;·&nbsp; 🇩🇪 گواهی TÜV Rheinland آلمان &nbsp;·&nbsp; 📦 ارسال سراسر ایران &nbsp;·&nbsp; 💰 تخفیف پلکانی تا ۱۰٪</div>"""
    crumbs = f'<a href="/">خانه</a> › {short}'
    return _layout(title, desc, slug_url, crumbs, body, extra)


def build_blog_index():
    title = "وبلاگ DDSVerified — راهنمای خرید فرز دندانپزشکی"
    desc = "راهنماهای خرید فرز دندانپزشکی، آموزش انتخاب فرز بر اساس رنگ دور، کد ISO و شکل فرز."
    body = """
<h1>راهنمای فرزهای دندانپزشکی</h1>
<div class="intro"><p>در این بخش راهنماهای جامع انتخاب و خرید فرز دندانپزشکی منتشر می‌شود: معنی رنگ دور فرزها، مفهوم کد ISO، انتخاب فرز مناسب هر کار کلینیکی و مقایسه خانواده‌های مختلف فرز الماسی.</p>
<p>برای مشاهده و خرید محصولات، به <a href="/">صفحه اصلی فروشگاه</a> مراجعه کنید.</p></div>"""
    crumbs = '<a href="/">خانه</a> › وبلاگ'
    return _layout(title, desc, "blog/", crumbs, body)


def build_sitemap(data):
    urls = [("", "1.0"), ("blog/", "0.6")]
    for key in group_by_page(data):
        urls.append((cat_url(key), "0.9"))
    today = __import__("datetime").date.today().isoformat()
    entries = "\n".join(
        f"  <url>\n    <loc>{BASE}/{path}</loc>\n    <lastmod>{today}</lastmod>\n    <priority>{pri}</priority>\n  </url>"
        for path, pri in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{entries}\n</urlset>\n'


def main():
    data = load_data()
    n = 0
    for key in group_by_page(data):
        d = f"category/{SLUGS[key]}"
        os.makedirs(d, exist_ok=True)
        with open(f"{d}/index.html", "w", encoding="utf-8", newline="\n") as f:
            f.write(build_category_page(key, data))
        n += 1
    os.makedirs("blog", exist_ok=True)
    with open("blog/index.html", "w", encoding="utf-8", newline="\n") as f:
        f.write(build_blog_index())
    n += 1
    with open("sitemap.xml", "w", encoding="utf-8", newline="\n") as f:
        f.write(build_sitemap(data))
    print(f"Generated {n} pages + sitemap ({len(group_by_page(data))} categories)")


if __name__ == "__main__":
    main()

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

BRAND_ROW = '<tr><td>برند</td><td class="brand-cell">AZDENT <img src="/images/azdent-logo.svg" alt="AZDENT" width="70" height="11" loading="lazy"></td></tr>'

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
    """Discounted per-bur price in toman (bundle rows have their own total)."""
    return int(p["price"] if p.get("price") is not None else data["price_per_bur"])


def product_old_price(p: dict, data: dict) -> int | None:
    """Previous per-bur price, or the bundle's previous total, when discounted."""
    old = p.get("old_price")
    if old is None and not p.get("bundle"):
        old = data.get("old_price_per_bur")
    if old is None:
        return None
    old = int(old)
    return old if old > product_price(p, data) else None


def price_html(p: dict, data: dict, *, campaign: bool = False) -> str:
    """Visible toman price with a reference price and rounded discount label."""
    price = product_price(p, data)
    old = product_old_price(p, data)
    reference = ""
    if old is not None:
        percent = round(100 * (old - price) / old)
        reference = (f' <del class="old-price">{fmt_price(old)} تومان</del>'
                     f' <span class="discount-badge">{fa(percent)}٪ تخفیف</span>')
    unit = "" if campaign else " <small>/ هر عدد</small>"
    return f"{fmt_price(price)} تومان{unit}{reference}"


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

# ------------------------------------------------------- evidence (PubMed) ----
# Every claim below was checked against the PubMed abstract of the cited paper.
# Keep findings faithful to the abstract; add new papers to SOURCES first.
EVIDENCE_REVIEWED = "2026-10-29"

SOURCES = {
    "goodacre2001": {"authors": "Goodacre CJ, Campagni WV, Aquilino SA", "title": "Tooth preparations for complete crowns: an art form based on scientific principles", "journal": "J Prosthet Dent", "year": "2001", "cite": "85(4):363-76", "pmid": "11319534", "type": "مرور متون"},
    "yu2019": {"authors": "Yu H, Chen YH, Cheng H, Sawase T", "title": "Finish-line designs for ceramic crowns: A systematic review and meta-analysis", "journal": "J Prosthet Dent", "year": "2019", "cite": "122(1):22-30", "pmid": "30782459", "type": "مرور سیستماتیک و متاآنالیز"},
    "pal2025": {"authors": "Pál A, Papócsi P, Kelemen K, et al.", "title": "Impact of finish line designs on the adaptation of ceramic fixed dental prostheses: a systematic review and network meta-analysis", "journal": "BMC Oral Health", "year": "2025", "cite": "25(1):1085", "pmid": "40611068", "type": "مرور سیستماتیک و متاآنالیز شبکه‌ای"},
    "gavara2023": {"authors": "Gavara SG, Jain S, Gupta H, et al.", "title": "Comparative Effect of No Finish Line, Heavy Chamfer, and Shoulder Marginal Designs on the Fracture Resistance of Zirconia (Cercon) Ceramic Restoration: An In Vitro Study", "journal": "Cureus", "year": "2023", "cite": "15(5):e39009", "pmid": "37323304", "type": "مطالعه آزمایشگاهی"},
    "potiket2004": {"authors": "Potiket N, Chiche G, Finger IM", "title": "In vitro fracture strength of teeth restored with different all-ceramic crown systems", "journal": "J Prosthet Dent", "year": "2004", "cite": "92(5):491-5", "pmid": "15523339", "type": "مطالعه آزمایشگاهی"},
    "abad2024": {"authors": "Abad-Coronel C, Villacís Manosalvas J, Palacio Sarmiento C, et al.", "title": "Clinical outcomes of the biologically oriented preparation technique (BOPT) in fixed dental prostheses: A systematic review", "journal": "J Prosthet Dent", "year": "2024", "cite": "132(3):502-508", "pmid": "36192194", "type": "مرور سیستماتیک"},
    "loi2013": {"authors": "Loi I, Di Felice A", "title": "Biologically oriented preparation technique (BOPT): a new approach for prosthetic restoration of periodontically healthy teeth", "journal": "Eur J Esthet Dent", "year": "2013", "cite": "8(1):10-23", "pmid": "23390618", "type": "گزارش تکنیک بالینی"},
    "mohammad2023": {"authors": "Mohammad A, Abraham S, Nada A", "title": "The effect of biologically oriented and subgingival horizontal preparation techniques on periodontal health: A double-blind randomized controlled clinical trial", "journal": "Saudi Dent J", "year": "2023", "cite": "35(6):727-733", "pmid": "37817795", "type": "کارآزمایی بالینی تصادفی"},
    "badar2019": {"authors": "Badar SB, Ghafoor R, Hameed MH, Anwer N", "title": "Assessment of iatrogenic damage to adjacent teeth during crown and bridge preparation", "journal": "Indian J Dent Res", "year": "2019", "cite": "30(1):107-111", "pmid": "30900667", "type": "مطالعه آینده‌نگر"},
    "moopnar1991": {"authors": "Moopnar M, Faulkner KD", "title": "Accidental damage to teeth adjacent to crown-prepared abutment teeth", "journal": "Aust Dent J", "year": "1991", "cite": "36(2):136-40", "pmid": "1678936", "type": "مطالعه مشاهده‌ای"},
    "lussi2003": {"authors": "Lussi A, Kronenberg O, Megert B", "title": "The effect of magnification on the iatrogenic damage to adjacent tooth surfaces during class II preparation", "journal": "J Dent", "year": "2003", "cite": "31(4):291-6", "pmid": "12735924", "type": "مطالعه آزمایشگاهی"},
    "lenters2006": {"authors": "Lenters M, van Amerongen WE, Mandari GJ", "title": "Iatrogenic damage to the adjacent surfaces of primary molars, in three different ways of cavity preparation", "journal": "Eur Arch Paediatr Dent", "year": "2006", "cite": "7(1):6-10", "pmid": "17140521", "type": "مطالعه بالینی"},
    "jung1997": {"authors": "Jung M", "title": "Surface roughness and cutting efficiency of composite finishing instruments", "journal": "Oper Dent", "year": "1997", "cite": "22(3):98-104", "pmid": "9484147", "type": "مطالعه آزمایشگاهی"},
    "ferreira2004": {"authors": "Ferreira Rde S, Lopes GC, Baratieri LN", "title": "Direct posterior resin composite restorations: considerations on finishing/polishing. Clinical procedures", "journal": "Quintessence Int", "year": "2004", "cite": "35(5):359-66", "pmid": "15130074", "type": "مقاله بالینی"},
    "siegel2000": {"authors": "Siegel SC, von Fraunhofer JA", "title": "Cutting efficiency of three diamond bur grit sizes", "journal": "J Am Dent Assoc", "year": "2000", "cite": "131(12):1706-10", "pmid": "11143734", "type": "مطالعه آزمایشگاهی"},
    "vonfraunhofer2000": {"authors": "von Fraunhofer JA, Siegel SC, Feldman S", "title": "Handpiece coolant flow rates and dental cutting", "journal": "Oper Dent", "year": "2000", "cite": "25(6):544-8", "pmid": "11203868", "type": "مطالعه آزمایشگاهی"},
    "zarpellon2021": {"authors": "Zarpellon DC, Runnacles P, Maucoski C, et al.", "title": "In Vivo Pulp Temperature Changes During Class V Cavity Preparation and Resin Composite Restoration in Premolars", "journal": "Oper Dent", "year": "2021", "cite": "46(4):374-384", "pmid": "34370040", "type": "مطالعه in vivo"},
    "rues2017": {"authors": "Rues S, Schwindling FS, Meyer A, Rammelsberg P, Schmitter M", "title": "Fracture resistance of zirconia-based all-ceramic crowns after bur adjustment", "journal": "Eur J Oral Sci", "year": "2017", "cite": "125(4):310-313", "pmid": "28597965", "type": "مطالعه آزمایشگاهی"},
    "barros2020": {"authors": "Barros MMAF, De Queiroz Rodrigues MI, Muniz FWMG, Rodrigues LKA", "title": "Selective, stepwise, or nonselective removal of carious tissue: which technique offers lower risk for the treatment of dental caries in permanent teeth? A systematic review and meta-analysis", "journal": "Clin Oral Investig", "year": "2020", "cite": "24(2):521-532", "pmid": "31773371", "type": "مرور سیستماتیک و متاآنالیز"},
    "neves2011": {"authors": "Neves Ade A, Coutinho E, De Munck J, Van Meerbeek B", "title": "Caries-removal effectiveness and minimal-invasiveness potential of caries-excavation techniques: a micro-CT investigation", "journal": "J Dent", "year": "2011", "cite": "39(2):154-62", "pmid": "21111770", "type": "مطالعه آزمایشگاهی (میکروسی‌تی)"},
    "alhelou2023": {"authors": "Al-Helou N, Zaki AA, Al Agha M, Moawad E, Jarad F", "title": "Which endodontic access cavity is best? A literature review", "journal": "Br Dent J", "year": "2023", "cite": "234(5):335-339", "pmid": "36899249", "type": "مرور متون"},
    "shabbir2021": {"authors": "Shabbir J, Zehra T, Najmi N, et al.", "title": "Access Cavity Preparations: Classification and Literature Review of Traditional and Minimally Invasive Endodontic Access Cavity Designs", "journal": "J Endod", "year": "2021", "cite": "47(8):1229-1244", "pmid": "34058252", "type": "مرور متون"},
    "zogheib2021": {"authors": "Zogheib C, Roumi R, Bourbouze G, Naaman A, Khalil I, Plotino G", "title": "Effects of ultrasonic refinement on endodontic access cavity walls: A microcomputed tomography analysis", "journal": "J Conserv Dent", "year": "2021", "cite": "24(1):29-35", "pmid": "34475676", "type": "مطالعه آزمایشگاهی (میکروسی‌تی)"},
    "souza2023": {"authors": "Souza PHF, Oliveira Santos-Junior A, Pinto JC, et al.", "title": "Effect of Endo-Z bur or Bladesonic ultrasonic tip on the adaptation of filling material. A micro-CT study", "journal": "Braz Dent J", "year": "2023", "cite": "34(5):29-35", "pmid": "38133470", "type": "مطالعه آزمایشگاهی (میکروسی‌تی)"},
    "henry1956": {"authors": "Henry EE", "title": "The influence of design factors on the performance of the inverted cone bur", "journal": "J Dent Res", "year": "1956", "cite": "35(5):704-13", "pmid": "13367288", "type": "مطالعه آزمایشگاهی کلاسیک"},
    "cherukara2002": {"authors": "Cherukara GP, Seymour KG, Samarawickrama DY, Zou L", "title": "A study into the variations in the labial reduction of teeth prepared to receive porcelain veneers--a comparison of three clinical techniques", "journal": "Br Dent J", "year": "2002", "cite": "192(7):401-4", "pmid": "12017460", "type": "مطالعه آزمایشگاهی"},
    "gurel2013": {"authors": "Gurel G, Sesma N, Calamita MA, Coachman C, Morimoto S", "title": "Influence of enamel preservation on failure rates of porcelain laminate veneers", "journal": "Int J Periodontics Restorative Dent", "year": "2013", "cite": "33(1):31-9", "pmid": "23342345", "type": "مطالعه بالینی گذشته‌نگر (۱۲ ساله)"},
    "gao2022": {"authors": "Gao J, He J, Fan L, Lu J, Xie C, Yu H", "title": "Accuracy of Reduction Depths of Tooth Preparation for Porcelain Laminate Veneers Assisted by Different Tooth Preparation Guides: An In Vitro Study", "journal": "J Prosthodont", "year": "2022", "cite": "31(7):593-600", "pmid": "34859537", "type": "مطالعه آزمایشگاهی"},
}

# Reusable evidence findings (Persian summary of each abstract's result)
_E = {
    "goodacre_crown": ("همگرایی کلی اکلوزالی ۱۰ تا ۲۰ درجه، حداقل ارتفاع ۴ میلی‌متر برای مولرها و ۳ میلی‌متر برای سایر دندان‌ها و گرد بودن زوایای داخلی، از اصول علمی تراش روکش کامل است.", "goodacre2001"),
    "goodacre_finish": ("انتخاب نوع مارجین باید بر اساس نوع روکش، نیاز زیبایی و سهولت ایجاد آن باشد؛ برتری تطابق مارجینال یک طرح خاص در پژوهش‌های جدید تأیید نشده و مارجین بالای لثه قابل‌قبول‌تر است.", "goodacre2001"),
    "yu_finish": ("در متاآنالیز ۱۶ مطالعه، روکش‌های سرامیکی با شولدر گرد تطابق مارجینال کمی بهتر و با شمفر تطابق داخلی بهتری داشتند؛ تفاوت مارجینال از نظر بالینی کوچک بود.", "yu2019"),
    "pal_chamfer": ("متاآنالیز شبکه‌ای ۲۰۲۵ (۳۴ مطالعه کمّی) تفاوت معناداری در تطابق مارجینال بین شمفر، شولدر، شولدر گرد و تراش عمودی نیافت، اما شمفر تطابق داخلی بهتری داشت و برای استفاده بالینی توصیه شد.", "pal2025"),
    "gavara_zr": ("در یک مطالعه آزمایشگاهی روی روکش زیرکونیا، مقاومت به شکست با مارجین شمفر عمیق به‌طور معناداری بیشتر از مارجین شولدر بود.", "gavara2023"),
    "rues_grit": ("در اصلاح داخل‌دهانی روکش زیرکونیا، با ریزتر شدن گریت فرز مقاومت به شکست افزایش یافت؛ استفاده از فرز درشت در مرحله نهایی پیش از پالیش توصیه نمی‌شود.", "rues2017"),
    "jung_finish": ("برای حذف اضافات و کانتور کامپوزیت (به‌ویژه سطح لینگوال قدامی و اکلوزال خلفی)، فرز الماسی پرداخت ۱۵ تا ۴۰ میکرون پیشنهاد شده و سپس فرز کارباید سطح صاف‌تری ایجاد می‌کند.", "jung1997"),
    "lussi_adj": ("در تراش حفرات کلاس II، ۹۷٪ سطوح دندان مجاور دچار ترومای تراش شدند و استفاده از لوپ به‌تنهایی این آسیب را کاهش نداد.", "lussi2003"),
    "coolant": ("افزایش جریان آب خنک‌کننده هندپیس (از ۱۵ تا ۴۴ میلی‌لیتر در دقیقه) سرعت برش فرز الماسی را افزایش داد.", "vonfraunhofer2000"),
    "pulp_temp": ("در یک مطالعه in vivo روی پرمولرها، تراش حفره کلاس V با عمق ۲ میلی‌متر با فرز الماسی توربین زیر اسپری آب‌وهوا، دمای پالپ را تا حد خطرناک بالا نبرد.", "zarpellon2021"),
    "alhelou_access": ("مرور متون ۲۰۲۳ حفره دسترسی سنتی (straight-line access) را برای یافتن قابل‌پیش‌بینی دهانه کانال‌ها، شست‌وشوی مؤثر و پرکردن بهتر توصیه می‌کند.", "alhelou2023"),
    "shabbir_access": ("مرور ۴۹ مقاله نشان داد طرح‌های بسیار محافظه‌کارانه حفره دسترسی مزیت روشنی ندارند و می‌توانند ضدعفونی، پرکردن و ترمیم دندان را دشوارتر کنند.", "shabbir2021"),
    "abad_bopt": ("در مرور سیستماتیک تکنیک BOPT، افزایش عمق پروب بیش از ۳ میلی‌متر در ۲٫۳٪، تحلیل لثه در ۱٫۷٪ و شکست مکانیکی یا بیولوژیک در ۴٫۴٪ دندان‌ها تا ۵ سال گزارش شد؛ نویسندگان کارآزمایی‌های بلندمدت بیشتری را لازم می‌دانند.", "abad2024"),
    "cherukara_dimple": ("در مقایسه سه روش کنترل عمق تراش ونیر، ایجاد گودی راهنما با فرز روند کوچک (قطر ۰۰۱ تا ۰۱۲) با زاویه ۴۵ درجه بیشترین تعداد تراش را در محدوده هدف ۰٫۴ تا ۰٫۶ میلی‌متر ایجاد کرد.", "cherukara2002"),
}

EVIDENCE = {
    "needle": {
        "meta": "فرز نیدل (سوزنی) برای شکستن تماس پروگزیمال و تراش بین‌دندانی در آماده‌سازی روکش و بریج؛ کاربرد بالینی مبتنی بر شواهد با منابع PubMed.",
        "lead": "فرز نیدل با قطر کم و بدنه مخروطیِ نوک‌تیز طراحی شده تا از تماس بین‌دندانی عبور کند و دیواره پروگزیمال را بدون تراش اضافه باز کند. مهم‌ترین چالش این مرحله آسیب ناخواسته به دندان مجاور است؛ مطالعات نشان می‌دهند این آسیب بسیار شایع است و انتخاب فرز باریک همراه با تکنیک محافظتی اهمیت زیادی دارد.",
        "uses": [
            "شکستن تماس پروگزیمال (proximal slicing) در شروع تراش روکش و بریج",
            "تراش اولیه دیواره‌های بین‌دندانی پیش از استفاده از فرزهای مخروطی بزرگ‌تر",
            "مدل‌های EF (ریز): پرداخت امبرژرها و نواحی بین‌دندانی ترمیم‌های کامپوزیت",
        ],
        "evidence": [
            ("در بررسی ۱۵۰ کست، آسیب به سطح پروگزیمال دندان مجاور در ۷۸٪ سطوح مزیال و ۶۰٫۶٪ سطوح دیستال تراش روکش و بریج دیده شد؛ بیشتر آسیب‌ها از نوع خراش خفیف بودند.", "badar2019"),
            ("بررسی ۶۵۲ سطح پروگزیمال مجاور تراش روکش نیز شیوع بالای آسیب به بافت سخت دندان مجاور را گزارش کرده است.", "moopnar1991"),
            _E["lussi_adj"],
            ("محافظت از سطح دندان مجاور، برای مثال با جداسازی به‌وسیله ماتریکس‌باند، برای کاهش این آسیب توصیه شده است.", "lenters2006"),
            _E["jung_finish"],
        ],
        "caution": "برای کاهش آسیب به دندان مجاور، فرز را درون ساختار دندانِ در حال تراش نگه دارید و از ماتریکس‌باند فلزی یا وج محافظ استفاده کنید.",
    },
    "flat_cylinder": {
        "meta": "فرز فیشور (استوانه‌ای تخت) برای تراش حفره کلاس I و II، باکس پروگزیمال و گروو کمکی روکش؛ کاربرد بالینی مبتنی بر شواهد با منابع PubMed.",
        "lead": "فرز فیشور با دیواره‌های موازی و انتهای تخت، کف صاف و دیواره‌های عمود ایجاد می‌کند. این هندسه آن را برای آماده‌سازی حفرات اکلوزال و باکس پروگزیمال و همچنین ایجاد گروو و باکس کمکی برای افزایش مقاومت در تراش روکش مناسب می‌کند.",
        "uses": [
            "آماده‌سازی حفره کلاس I و باکس پروگزیمال کلاس II",
            "ایجاد گروو محوری و باکس کمکی برای افزایش مقاومت در تراش‌های کوتاه روکش",
            "مدل‌های کوتاه (مانند SF-41 و SF-31C): تراش کنترل‌شده در حفرات کوچک و کم‌عمق",
        ],
        "evidence": [
            ("مرور اصول علمی تراش روکش توصیه می‌کند وقتی ارتفاع یا همگرایی دیواره‌ها کافی نیست، از گروو محوری یا باکس — ترجیحاً در سطوح پروگزیمال — برای افزایش مقاومت استفاده شود و زوایای داخلی گرد شوند.", "goodacre2001"),
            _E["lussi_adj"],
            _E["coolant"],
            _E["pulp_temp"],
        ],
        "caution": "انتهای تخت فرز فیشور گوشه‌های داخلی تیز ایجاد می‌کند؛ در تراش روکش سرامیکی این زوایا را گرد کنید.",
    },
    "taper_round_edge": {
        "meta": "فرز تیپر روند اند (مخروطی با لبه گرد) برای کاهش محوری روکش با همگرایی ۱۰ تا ۲۰ درجه و ایجاد شولدر گرد یا شمفر؛ مبتنی بر شواهد PubMed.",
        "lead": "فرز تیپر روند اند با دیواره مخروطی و لبه گرد، هم‌زمان دیواره محوری را با شیب کنترل‌شده تراش می‌دهد و در انتها مارجین شولدر گرد (rounded shoulder) یا شمفر عمیق ایجاد می‌کند. قطر بزرگ‌تر این سری (۰۱۸ و ۰۱۹) برای کاهش محوری سریع در دندان‌های خلفی مناسب است.",
        "uses": [
            "کاهش محوری (axial reduction) در تراش روکش تمام‌سرامیک و متال‌سرامیک",
            "ایجاد مارجین شولدر با زاویه داخلی گرد یا شمفر عمیق",
            "تنظیم همگرایی دیواره‌ها برای گیر و مقاومت روکش",
        ],
        "evidence": [_E["goodacre_crown"], _E["yu_finish"], _E["pal_chamfer"]],
        "caution": "",
    },
    "round_taper": {
        "meta": "فرز تیپر روند اند برای ایجاد مارجین شمفر در تراش روکش زیرکونیا و سرامیکی و کاهش محوری؛ کاربرد بالینی مبتنی بر شواهد با منابع PubMed.",
        "lead": "نوک گرد این فرز وقتی تا نیمی از قطرش در لبه لثه‌ای قرار گیرد، مارجین شمفر ایجاد می‌کند و بدنه مخروطی آن هم‌زمان دیواره محوری را با همگرایی مناسب تراش می‌دهد. شواهد فعلی شمفر را از نظر تطابق داخلی روکش‌های سرامیکی مطلوب نشان می‌دهد.",
        "uses": [
            "ایجاد مارجین شمفر و شمفر عمیق (heavy chamfer) در روکش زیرکونیا، لیتیوم دی‌سیلیکات و متال‌سرامیک",
            "کاهش محوری با همگرایی کنترل‌شده",
            "مدل‌های EF: صاف کردن و پرداخت مارجین و دیواره‌ها پس از تراش با گریت درشت‌تر",
        ],
        "evidence": [_E["pal_chamfer"], _E["gavara_zr"], _E["goodacre_crown"], _E["rues_grit"]],
        "caution": "",
    },
    "taper_flat": {
        "meta": "فرز تیپر فلت اند (مخروطی ته تخت) برای ایجاد مارجین شولدر در روکش تمام‌سرامیک و کاهش محوری؛ کاربرد بالینی مبتنی بر شواهد با منابع PubMed.",
        "lead": "انتهای تخت این فرز مارجین شولدر با عرض یکنواخت ایجاد می‌کند و دیواره مخروطی آن همگرایی لازم برای گیر روکش را فراهم می‌کند. شولدر به‌طور سنتی برای روکش‌های تمام‌سرامیک و لبه پرسلنی روکش‌های متال‌سرامیک قدامی استفاده می‌شود.",
        "uses": [
            "ایجاد مارجین شولدر حدود ۱ میلی‌متر در روکش تمام‌سرامیک",
            "شولدر لبه پرسلنی (porcelain butt margin) در روکش متال‌سرامیک قدامی",
            "کاهش محوری و ایجاد سطح اکلوزال صاف",
        ],
        "evidence": [
            ("در مطالعه‌ای روی سانترال‌های ماگزیلا با شولدر ۱ میلی‌متری و زاویه داخلی گرد، روکش‌های تمام‌سرامیک (آلومینا و زیرکونیا) مقاومت به شکستی مشابه روکش متال‌سرامیک داشتند.", "potiket2004"),
            _E["goodacre_finish"],
            _E["yu_finish"],
            ("در روکش زیرکونیای خلفی، شمفر عمیق مقاومت به شکست بیشتری از شولدر نشان داد؛ بنابراین برای زیرکونیای خلفی، شمفر عمیق گزینه قابل‌توجهی است.", "gavara2023"),
        ],
        "caution": "زاویه داخلی شولدر را گرد کنید تا تمرکز تنش در سرامیک کاهش یابد.",
    },
    "flame": {
        "meta": "فرز فلیم (شعله‌ای) برای تراش عمودی (feather-edge و BOPT)، پرداخت مارجین زیر لثه و کانتور کامپوزیت؛ کاربرد مبتنی بر شواهد با منابع PubMed.",
        "lead": "فرز فلیم با نوک باریک و بدنه شعله‌ای امکان کار دقیق در ناحیه سالکوس و مارجین را فراهم می‌کند. کاربرد اصلی این شکل در تراش عمودی (vertical / feather-edge) و تکنیک BOPT است و مدل‌های EF آن برای پرداخت مارجین و کانتور ترمیم‌های کامپوزیت استفاده می‌شوند.",
        "uses": [
            "تراش عمودی بدون خط خاتمه مشخص (feather-edge) و تکنیک BOPT",
            "پرداخت و صاف کردن مارجین زیر لثه پس از تراش اولیه",
            "مدل‌های EF: کانتور و پرداخت سطوح لینگوال و امبرژرهای ترمیم کامپوزیت",
        ],
        "evidence": [
            ("تکنیک BOPT بر پایه تراش عمودی (feather-edge) بدون فلپ برای دندان‌های با پریودنشیوم سالم معرفی شده و پایداری بافت نرم در پیگیری بالینی تا ۱۵ سال گزارش شده است.", "loi2013"),
            _E["abad_bopt"],
            ("در یک کارآزمایی بالینی تصادفی دوسوکور (۱۰۰ بیمار، طرح split-mouth)، BOPT در پیگیری دوساله ثبات مارجین و رفتار پریودنتال مطلوبی نشان داد.", "mohammad2023"),
            _E["jung_finish"],
        ],
        "caution": "",
    },
    "flame_long": {
        "meta": "فرز فلیم شنک بلند (EF) برای پرداخت مارجین و کانتور کامپوزیت در نواحی عمیق و کم‌دسترس؛ کاربرد بالینی مبتنی بر شواهد با منابع PubMed.",
        "lead": "این فرز همان هندسه شعله‌ای را با گردن بلندتر ارائه می‌کند تا در نواحی عمیق، دندان‌های خلفی و امبرژرهای تنگ دید و دسترسی بهتری فراهم شود. گریت بسیار ریز (EF) آن را برای مرحله پرداخت مناسب می‌کند، نه برداشت حجیم نسج.",
        "uses": [
            "پرداخت مارجین تراش‌های عمودی و شمفر در نواحی کم‌دسترس",
            "کانتور و پرداخت ترمیم‌های کامپوزیت در امبرژرها و سطوح پروگزیمال",
            "صاف کردن سطوح پس از تراش با فرز درشت‌تر",
        ],
        "evidence": [
            _E["jung_finish"],
            _E["rues_grit"],
            ("در متاآنالیز شبکه‌ای ۲۰۲۵، تراش عمودی کمترین گپ مارجینال را در روکش‌های سرامیکی داشت؛ هرچند تفاوت با سایر طرح‌ها معنادار نبود.", "pal2025"),
            _E["abad_bopt"],
        ],
        "caution": "",
    },
    "round": {
        "meta": "فرز روند الماسی توربین برای دسترسی به پوسیدگی، شروع حفره دسترسی اندو و ایجاد گودی‌های راهنمای عمق در تراش ونیر؛ مبتنی بر شواهد PubMed.",
        "lead": "نوک کروی فرز روند امکان نفوذ کنترل‌شده و تراش یکنواخت در همه جهات را می‌دهد. شواهد علمی کاربرد آن را در سه حوزه پشتیبانی می‌کنند: دسترسی به ضایعه پوسیدگی، شروع حفره دسترسی درمان ریشه و ایجاد گودی‌های راهنمای عمق (depth dimples) در تراش ونیر.",
        "uses": [
            "باز کردن مینا و دسترسی به ضایعه پوسیدگی",
            "شروع حفره دسترسی اندودانتیک و برداشت سقف اتاقک پالپ",
            "ایجاد گودی‌های راهنمای عمق روی سطح لبیال پیش از تراش ونیر (به‌ویژه سایزهای کوچک مانند BR-49)",
        ],
        "evidence": [
            _E["cherukara_dimple"],
            ("مرور سیستماتیک و متاآنالیز نشان داد برداشت انتخابی بافت پوسیده (selective removal) نسبت به برداشت کامل، موفقیت بیشتری در حفظ سلامت پالپ و خطر کمتر اکسپوز پالپ دارد.", "barros2020"),
            ("در بررسی میکروسی‌تی، روش‌های چرخشی برداشت پوسیدگی کارایی خوبی داشتند اما تمایل به برداشت بیش از حد عاج سالم دیده شد؛ این خطر با استفاده از فرز کارباید کمتر بود.", "neves2011"),
            _E["alhelou_access"],
        ],
        "caution": "فرز الماسی توربین برای باز کردن مینا و تراش کنترل‌شده مناسب است؛ برای برداشت عاج نرم پوسیده نزدیک پالپ، ابزارهای انتخابی‌تر مانند فرز کارباید با دور کم یا اکسکاواتور توصیه می‌شوند.",
    },
    "round_long": {
        "meta": "فرز روند شنک بلند برای کار در عمق اتاقک پالپ، برداشت سقف پالپ و یافتن دهانه کانال با دید بهتر؛ کاربرد مبتنی بر شواهد با منابع PubMed.",
        "lead": "گردن بلند این فرز سر هندپیس را از دندان دور نگه می‌دارد تا در عمق حفره دسترسی، دید مستقیم به نوک فرز حفظ شود. این ویژگی در برداشت کامل سقف اتاقک پالپ، حذف کلسیفیکاسیون‌ها و یافتن دهانه کانال‌ها کاربرد دارد.",
        "uses": [
            "برداشت کامل سقف اتاقک پالپ و شاخ‌های پالپی",
            "حذف کلسیفیکاسیون و دنتیکل در عمق اتاقک پالپ",
            "دسترسی به دهانه کانال‌ها در دندان‌های خلفی و تاج‌های بلند",
        ],
        "evidence": [
            ("حفره دسترسی باید امکان حذف موانع اتاقک پالپ، یافتن همه دهانه‌های کانال و پاک‌سازی کامل سیستم کانال را با کمترین برداشت نسج فراهم کند؛ روش سنتی دسترسی پیش‌بینی‌پذیرتر گزارش شده است.", "alhelou2023"),
            _E["shabbir_access"],
            _E["coolant"],
        ],
        "caution": "شواهد مقایسه‌ای مستقیم درباره فرزهای روند شنک بلند محدود است؛ کاربرد آن بر پایه اصول حفره دسترسی مطرح‌شده در منابع است.",
    },
    "torpedo": {
        "meta": "فرز تورپیدو برای ایجاد مارجین شمفر سبک یا نایف‌اج و کاهش محوری محافظه‌کارانه در تراش روکش؛ کاربرد مبتنی بر شواهد با منابع PubMed.",
        "lead": "فرز تورپیدو با بدنه استوانه‌ای و نوک دوکی‌شکل، مارجینی بین شمفر سبک و لبه چاقویی (knife-edge) ایجاد می‌کند و برای کاهش محوری با برداشت کم نسج در ناحیه سرویکال مناسب است.",
        "uses": [
            "ایجاد مارجین شمفر سبک یا knife-edge در روکش‌های فلزی، متال‌سرامیک و زیرکونیای مونولیتیک",
            "کاهش محوری محافظه‌کارانه در ناحیه سرویکال",
            "شکل‌دهی شیارها و اصلاح آناتومی اکلوزال",
        ],
        "evidence": [_E["pal_chamfer"], _E["yu_finish"], _E["goodacre_finish"], _E["gavara_zr"]],
        "caution": "",
    },
    "football": {
        "meta": "فرز فوتبالی (تخم‌مرغی) برای کاهش لینگوال قدامی، فرم‌دهی آناتومی اکلوزال و کانتور کامپوزیت؛ کاربرد مبتنی بر شواهد با منابع PubMed.",
        "lead": "شکل بیضوی این فرز با تقعر سطح لینگوال دندان‌های قدامی و شیب کاسپ‌ها هم‌خوانی دارد؛ به همین دلیل برای کاهش لینگوال در تراش روکش قدامی، فرم‌دهی آناتومی اکلوزال و کانتور ترمیم‌های کامپوزیت استفاده می‌شود.",
        "uses": [
            "کاهش سطح لینگوال (تقعر) دندان‌های قدامی در تراش روکش",
            "کاهش آناتومیک سطح اکلوزال و شکل‌دهی کاسپ‌ها",
            "مدل‌های EF: کانتور و پرداخت اکلوزال ترمیم کامپوزیت و اصلاح اکلوژن",
        ],
        "evidence": [
            _E["jung_finish"],
            ("اصلاح اکلوزال روکش‌های زیرکونیا با فرز ریزتر، مقاومت به شکست بیشتری نسبت به فرز درشت ایجاد کرد.", "rues2017"),
            ("پرداخت ترمیم‌های کامپوزیت خلفی مزایایی دارد اما ممکن است شکست مارجینال و سایش را افزایش دهد؛ پیشنهاد شده سطوح پرداخت‌شده با رزین سیل شوند.", "ferreira2004"),
            _E["goodacre_crown"],
        ],
        "caution": "",
    },
    "inverted_cone": {
        "meta": "فرز اینورتد (معکوس) برای ایجاد زیربرش گیر، صاف کردن کف حفره و آماده‌سازی حفره کلاس V؛ کاربرد بالینی با منابع PubMed و سطح شواهد.",
        "lead": "فرز اینورتد کن با سر پهن و بدنه باریک‌شونده، کف صاف و زاویه زیربرش (undercut) در دیواره‌های حفره ایجاد می‌کند. این شکل به‌طور سنتی برای گیر مکانیکی ترمیم‌های آمالگام و آماده‌سازی حفرات سرویکال استفاده می‌شود.",
        "uses": [
            "ایجاد زیربرش و گیر مکانیکی در حفرات ترمیم‌های غیرچسبنده",
            "صاف کردن کف پالپال حفره",
            "آماده‌سازی حفره کلاس V",
        ],
        "evidence": [
            ("پژوهش کلاسیک نشان داد عوامل طراحی (هندسه سر و تیغه‌ها) بر عملکرد برش فرز اینورتد کن اثرگذار است.", "henry1956"),
            _E["pulp_temp"],
            _E["coolant"],
        ],
        "caution": "در ترمیم‌های چسبنده (کامپوزیت)، گیر عمدتاً از باندینگ تأمین می‌شود و ایجاد زیربرش اضافی معمولاً ضرورتی ندارد. شواهد مقایسه‌ای جدید درباره این شکل فرز محدود است.",
    },
    "barrel": {
        "meta": "فرز دابل برل (بشکه‌ای) برای کاهش سریع و یکنواخت سطح اکلوزال و تراش‌های وسیع؛ کاربرد بالینی مبتنی بر شواهد با منابع PubMed.",
        "lead": "فرز دابل برل با قطر بزرگ (۰۳۲) و بدنه بشکه‌ای، سطح تماس زیادی با دندان دارد و برای کاهش سریع و یکنواخت سطح اکلوزال، برداشت حجیم و شکل‌دهی سطوح وسیع طراحی شده است.",
        "uses": [
            "کاهش اکلوزال در تراش روکش، انله و آنله",
            "برداشت حجیم و یکنواخت در سطوح وسیع",
            "شکل‌دهی اولیه کانتور ترمیم‌های بزرگ کامپوزیت پیش از پرداخت",
        ],
        "evidence": [
            _E["goodacre_crown"],
            ("فرزهای الماسی درشت‌تر برای کاهش حجیم دندان سرعت برش خود را در طول کار بهتر حفظ کردند، اما نویسندگان درباره اثر گریت درشت بر کیفیت سطح، تولید حرارت و آسیب مینا هشدار می‌دهند.", "siegel2000"),
            _E["coolant"],
        ],
        "caution": "در کاهش اکلوزال مراقب ارتفاع باقی‌مانده تاج باشید؛ کاهش بیش از حد، گیر و مقاومت روکش را کم می‌کند.",
    },
    "depth_veneer": {
        "meta": "فرز دپس کات ونیر (۰٫۳، ۰٫۴ و ۰٫۵ میلی‌متر) برای کنترل عمق تراش لمینت و حفظ مینا؛ کاربرد بالینی مبتنی بر شواهد با منابع PubMed.",
        "lead": "فرز دپس کات با حلقه‌های برش با عمق مشخص، شیارهای راهنمای افقی روی سطح لبیال ایجاد می‌کند تا تراش ونیر در عمق برنامه‌ریزی‌شده و در محدوده مینا باقی بماند. حفظ مینا از مهم‌ترین عوامل شناخته‌شده در بقای لمینت‌های پرسلنی است.",
        "uses": [
            "ایجاد شیارهای راهنمای عمق ۰٫۳، ۰٫۴ یا ۰٫۵ میلی‌متر روی سطح لبیال",
            "کنترل یکنواختی تراش لمینت و ونیر سرامیکی",
            "حفظ تراش در محدوده مینا برای باندینگ قابل‌اعتماد",
        ],
        "evidence": [
            ("در پیگیری تا ۱۲ سال روی ۵۸۰ لمینت، بقای ونیرهایی که تراش آن‌ها در مینا مانده بود ۹۹٪ بود و ونیرهای باندشده به عاج حدود ۱۰ برابر بیشتر در معرض شکست بودند.", "gurel2013"),
            ("تراش ونیر با راهنما دقیق‌تر از تراش آزاد بود؛ خطای میانگین تراش آزاد ۰٫۱۹ تا ۰٫۲۷ میلی‌متر گزارش شد که نسبت به ضخامت مینای لبیال قابل‌توجه است.", "gao2022"),
            ("حتی با تکنیک‌های کنترل عمق، تراش یک اپراتور واحد تفاوت قابل‌توجهی با عمق ایده‌آل داشت؛ بنابراین بررسی عمق تراش پس از شیارگذاری اهمیت دارد.", "cherukara2002"),
        ],
        "caution": "عمق انتخاب‌شده را با ضخامت مینای ناحیه تطبیق دهید؛ مینا در ناحیه سرویکال نازک‌تر است.",
    },
    "pointed_cylinder": {
        "meta": "فرز شمفر استوانه‌ای برای ایجاد مارجین شمفر و کاهش محوری در تراش روکش و لمینت؛ کاربرد بالینی مبتنی بر شواهد با منابع PubMed.",
        "lead": "این فرز با بدنه استوانه‌ای و نوک شیب‌دار، مارجین شمفر با عرض کنترل‌شده ایجاد می‌کند. شواهد مرور سیستماتیک، شمفر را از نظر تطابق داخلی روکش‌های سرامیکی مطلوب نشان می‌دهد.",
        "uses": [
            "ایجاد مارجین شمفر در روکش زیرکونیا، لیتیوم دی‌سیلیکات و متال‌سرامیک",
            "کاهش محوری با دیواره‌های کنترل‌شده",
            "تعریف مارجین در تراش لمینت و روکش‌های قدامی",
        ],
        "evidence": [_E["pal_chamfer"], _E["yu_finish"], _E["gavara_zr"], _E["goodacre_crown"]],
        "caution": "",
    },
    "round_end_cylinder": {
        "meta": "فرز فیشور روند اند (استوانه‌ای ته گرد) برای ایجاد شولدر گرد و شمفر عمیق با دیواره‌های موازی؛ کاربرد مبتنی بر شواهد با منابع PubMed.",
        "lead": "فرز فیشور روند اند دیواره‌های موازی با انتهای گرد دارد؛ در تراش روکش، مارجین شولدر گرد یا شمفر عمیق با زاویه داخلی گرد ایجاد می‌کند و در حفرات ترمیمی، کف حفره را بدون گوشه تیز شکل می‌دهد.",
        "uses": [
            "ایجاد مارجین شولدر گرد (rounded shoulder) و شمفر عمیق",
            "تراش باکس و حفرات ترمیمی با زوایای داخلی گرد",
            "کاهش محوری کنترل‌شده در نواحی کم‌ارتفاع",
        ],
        "evidence": [
            _E["yu_finish"],
            ("در متاآنالیز شبکه‌ای ۲۰۲۵، شولدر گرد کمترین ناهمخوانی مطلق مارجینال (AMD) را داشت؛ هرچند تفاوت‌های مارجینال بین طرح‌ها معنادار نبود.", "pal2025"),
            _E["goodacre_crown"],
            ("روکش‌های تمام‌سرامیک روی تراش با شولدر ۱ میلی‌متری و زاویه داخلی گرد، مقاومت به شکستی مشابه روکش متال‌سرامیک داشتند.", "potiket2004"),
        ],
        "caution": "",
    },
    "carbide": {
        "meta": "فرز Endo-Z کارباید با نوک غیربرنده برای صاف کردن دیواره‌های حفره دسترسی اندو و برداشت سقف پالپ؛ کاربرد مبتنی بر شواهد با منابع PubMed.",
        "lead": "فرز Endo-Z یک فرز کارباید مخروطی با تیغه‌های جانبی و نوک غیربرنده (safe-ended) است. تیغه‌های جانبی دیواره‌های حفره دسترسی را صاف و واگرا می‌کنند و نوک غیربرنده برای کاهش احتمال برش کف اتاقک پالپ طراحی شده است.",
        "uses": [
            "برداشت باقیمانده سقف اتاقک پالپ و صاف کردن دیواره‌ها پس از ورود اولیه با فرز روند",
            "ایجاد دسترسی مستقیم (straight-line access) به دهانه کانال‌ها",
            "رزکسیون انتهای ریشه (apicoectomy) در جراحی اندو، طبق گزارش آزمایشگاهی",
        ],
        "evidence": [
            ("در مطالعه میکروسی‌تی روی ۳۰ مولر، دیواره‌های داخلی حفره دسترسی پس از اصلاح با Endo-Z صاف‌تر از نوک اولتراسونیک بود و زمان کار کوتاه‌تر بود؛ تعداد ترک‌های جدید بین دو گروه تفاوت معناداری نداشت.", "zogheib2021"),
            ("در رزکسیون ۳ میلی‌متر انتهای ریشه، Endo-Z سریع‌تر از نوک اولتراسونیک Bladesonic بود و هر دو روش به یک اندازه بر فصل مشترک ماده پرکننده و عاج اثر گذاشتند.", "souza2023"),
            _E["alhelou_access"],
            _E["shabbir_access"],
        ],
        "caution": "نوک غیربرنده جایگزین دقت اپراتور نیست؛ فرز را با فشار سبک و در امتداد دیواره‌ها حرکت دهید و از تماس فعال با کف پالپ پرهیز کنید.",
    },
}


def pubmed_url(pmid: str) -> str:
    return f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"


def _evidence_refs(shape_key: str) -> list:
    """Source keys in first-citation order for one category page."""
    refs = []
    for _, key in EVIDENCE.get(shape_key, {}).get("evidence", []):
        if key not in refs:
            refs.append(key)
    return refs


def build_evidence_html(shape_key: str, short: str) -> str:
    ev = EVIDENCE.get(shape_key)
    if not ev:
        return ""
    refs = _evidence_refs(shape_key)
    num = {k: i + 1 for i, k in enumerate(refs)}
    uses = "".join(f"<li>{u}</li>" for u in ev["uses"])
    findings = "".join(_finding_li(text, key, num[key]) for text, key in ev["evidence"])
    caution = f'<p class="ev-note">⚠️ {ev["caution"]}</p>' if ev.get("caution") else ""
    ref_items = "".join(_ref_li(k, num[k]) for k in refs)
    return f"""
<section class="evidence" id="clinical-evidence">
<h2>فرز {short} برای چه کاری استفاده می‌شود؟</h2>
<p>{ev["lead"]}</p>
<h3>کاربردهای بالینی اصلی</h3>
<ul>{uses}</ul>
<h3>شواهد علمی چه می‌گویند؟</h3>
<ul class="ev-list">{findings}</ul>
{caution}
<h3>منابع علمی (PubMed)</h3>
<ol class="refs">{ref_items}</ol>
<p class="ev-meta">آخرین بازبینی منابع: {fa(EVIDENCE_REVIEWED)} · این محتوا جنبه آموزشی دارد و جایگزین قضاوت بالینی دندانپزشک نیست.</p>
</section>"""


# --------------------------------------------- per-product evidence brief ----
# ISO 6360 colour codes for diamond grit classes
GRIT_CLASS = {"K⚫": "فوق‌درشت", "G🟢": "درشت", "B🔵": "متوسط", "R🔴": "ریز", "Y🟡": "خیلی ریز، EF", "W⚪": "فوق‌ریز"}

# Pin the first finding to the paper that matches the chosen use (use keyword -> source)
USE_SOURCE = {
    "round": {"گودی": "cherukara2002", "پوسیدگی": "barros2020", "حفره دسترسی": "alhelou2023"},
    "flat_cylinder": {"گروو": "goodacre2001", "کلاس": "lussi2003"},
}

# Grit-specific findings (Siegel 2000 compared medium/coarse/super-coarse; Rues 2017 & Jung 1997 cover fine finishing)
GRIT_FINDINGS = {
    "K⚫": [("در آزمایش برش، فرز فوق‌درشت در برش طولانی سریع‌تر از گریت متوسط بود (کاهش سرعت برش ۲۵٪ در برابر ۵۰٪)؛ نویسندگان درباره اثر گریت درشت بر کیفیت سطح، حرارت و آسیب مینا هشدار می‌دهند.", "siegel2000")],
    "G🟢": [("فرز گریت درشت در برش طولانی سرعت برش خود را بهتر از گریت متوسط حفظ کرد (کاهش ۳۵٪ در برابر ۵۰٪) و برای تراش حجیم مناسب است؛ اما گریت درشت کیفیت سطح را کاهش می‌دهد.", "siegel2000")],
    "B🔵": [("در آزمایش برش، فرز گریت متوسط در طول کار حدود ۵۰٪ از سرعت برش خود را از دست داد (درشت ۳۵٪)؛ در مقابل، گریت درشت‌تر بر کیفیت سطح و حرارت اثر نامطلوب‌تری دارد.", "siegel2000")],
    "Y🟡": [_E["rues_grit"], _E["jung_finish"]],
}


def _fa_num(x) -> str:
    s = str(x)
    s = s[:-2] if s.endswith(".0") else s
    return fa(s).replace(".", "٫")


def _strip_use(u: str) -> str:
    u = u.split(": ", 1)[1] if ": " in u else u
    return re.sub(r"\s*\(به‌ویژه[^)]*\)", "", u)


def product_evidence(p: dict, data: dict) -> dict:
    """Short, model-specific clinical summary + 2 PubMed-cited findings.
    Siblings rotate through the category's verified findings so pages stay unique."""
    shape = p["shape"]
    ev = EVIDENCE.get(shape)
    if not ev:
        return {}
    siblings = [q["model"] for q in group_by_page(data)[shape]]
    i = siblings.index(p["model"]) if p["model"] in siblings else 0
    dia = str(p.get("diameter", "-"))
    size_mm = int(dia) / 10 if re.fullmatch(r"\d{3}", dia) else None
    big_round = shape == "round" and size_mm is not None and size_mm > 1.2  # Cherukara tested 001–012

    grit = p.get("grit")
    grit_opts = GRIT_FINDINGS.get(grit, [])
    grit_f = grit_opts[i % len(grit_opts)] if grit_opts else None
    pool = [f for f in ev["evidence"]
            if (not grit_f or f[1] != grit_f[1]) and not (big_round and f[1] == "cherukara2002")]
    ef_uses = [u for u in ev["uses"] if u.startswith("مدل‌های EF")]
    named = [u for u in ev["uses"] if ": " in u and p["model"] in u.split(": ", 1)[0]]
    general = [u for u in ev["uses"] if ": " not in u and not (big_round and "گودی" in u)]
    if shape == "depth_veneer":
        use = "ایجاد شیار راهنمای عمق روی سطح لبیال و کنترل یکنواختی تراش لمینت و ونیر سرامیکی"
    elif grit == "Y🟡" and ef_uses:
        use = _strip_use(ef_uses[0])
    elif named:
        use = _strip_use(named[0])
    else:
        use = _strip_use(general[i % len(general)])

    first = pool[i % len(pool)]
    for word, src in USE_SOURCE.get(shape, {}).items():
        if word in use:
            first = next((f for f in pool if f[1] == src), first)
            break
    rest = [f for f in pool if f[1] != first[1]]
    findings = [first, grit_f if grit_f else rest[i % len(rest)]]

    spec = []
    if shape == "depth_veneer":
        spec.append(f"عمق برش {_fa_num(dia)} میلی‌متر")
    elif size_mm is not None:
        spec.append(f"قطر سر {_fa_num(size_mm)} میلی‌متر (سایز ISO {fa(dia)})")
    if shape != "carbide" and p.get("length") not in (None, "", "-"):
        spec.append(f"طول بخش کاری {_fa_num(p['length'])} میلی‌متر")
    if grit in GRIT_CLASS:
        spec.append(f"گریت {GRIT_LABELS[grit]} ({GRIT_CLASS[grit]})")
    if p.get("flutes"):
        spec.append(f"{fa(p['flutes'])} تیغه جانبی و نوک غیربرنده")
    return {"use": use, "spec": "، ".join(spec), "findings": findings}


def _finding_li(text: str, key: str, n: int) -> str:
    return (f'<li>{text} <sup><a href="#ref-{n}" aria-label="منبع {fa(n)}">[{fa(n)}]</a></sup>'
            f' <span class="ev-type">({SOURCES[key]["type"]})</span></li>')


def _ref_li(key: str, n: int) -> str:
    s = SOURCES[key]
    return (f'<li id="ref-{n}" dir="ltr">{s["authors"]}. {s["title"]}. <i>{s["journal"]}</i>. '
            f'{s["year"]};{s["cite"]}. <a href="{pubmed_url(s["pmid"])}" target="_blank" rel="noopener">'
            f'PubMed PMID: {s["pmid"]}</a></li>')


def _citation_ld(keys: list) -> list:
    return [{
        "@type": "ScholarlyArticle", "name": SOURCES[k]["title"],
        "author": SOURCES[k]["authors"], "datePublished": SOURCES[k]["year"],
        "isPartOf": {"@type": "Periodical", "name": SOURCES[k]["journal"]},
        "url": pubmed_url(SOURCES[k]["pmid"]),
        "identifier": {"@type": "PropertyValue", "propertyID": "PMID", "value": SOURCES[k]["pmid"]},
    } for k in keys]


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
            "brand": {"@type": "Brand", "name": "AZDENT"},
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
    def _link(m):
        url = m.group(2)
        ext = ' target="_blank" rel="noopener"' if url.startswith("http") else ""
        return f'<a href="{url}"{ext}>{m.group(1)}</a>'
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _link, text)
    # citation markers [1] -> superscript link to the numbered source list
    text = re.sub(r"\[(\d{1,2})\](?!\()",
                  r'<sup class="cite"><a href="#ref-\1" aria-label="منبع \1">[\1]</a></sup>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


FAQ_HEADING = "پرسش‌های متداول"


def extract_faq(md: str):
    """Split the '## پرسش‌های متداول' section (### question + answer lines) out of a post body.

    Returns (items, remaining_md); items is a list of (question, answer_md)."""
    lines = md.replace("\r\n", "\n").split("\n")
    start = next((i for i, l in enumerate(lines)
                  if re.match(r"^##\s+" + re.escape(FAQ_HEADING) + r"\s*$", l)), None)
    if start is None:
        return [], md
    end = next((j for j in range(start + 1, len(lines)) if re.match(r"^#{1,2}\s", lines[j])), len(lines))
    items, q, a = [], None, []
    for l in lines[start + 1:end]:
        m = re.match(r"^###\s+(.*)", l)
        if m:
            if q:
                items.append((q, "\n".join(a).strip()))
            q, a = m.group(1).strip(), []
        elif q is not None:
            a.append(l)
    if q:
        items.append((q, "\n".join(a).strip()))
    return items, "\n".join(lines[:start] + lines[end:])


def _plain(html: str) -> str:
    html = re.sub(r"<sup[^>]*>.*?</sup>", "", html)
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()
    return re.sub(r"\s+([.،؛:؟!)])", r"\1", text)


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
        if re.match(r"^-{3,}\s*$", line):
            out.append("<hr>")
            i += 1
            continue
        if line.lstrip().startswith(">"):
            quote = []
            while i < len(lines) and lines[i].lstrip().startswith(">"):
                quote.append(lines[i].lstrip()[1:].strip())
                i += 1
            out.append("<blockquote>" + "".join(f"<p>{_inline_md(q)}</p>" for q in quote if q) + "</blockquote>")
            continue
        m = re.match(r"^\[(\d{1,2})\]\s+(.*)", line.strip())
        if m:  # numbered source entry in the Sources section
            out.append(f'<p class="ref" id="ref-{m.group(1)}" dir="ltr">[{m.group(1)}] {_inline_md(m.group(2))}</p>')
            i += 1
            continue
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
        "updated": meta.get("updated", ""),
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
.post .faq{margin:0 0 18px;padding-bottom:6px;border-bottom:1px solid #eceff1}.post .faq h2{margin-top:0}
.post .faq details{background:#f8fafc}.post .faq details>div p{margin:6px 0}
.post sup.cite a{color:#1565c0;text-decoration:none;font-weight:700;font-size:.8em;padding:0 1px}
.post .ref{direction:ltr;text-align:left;font-size:.78rem;color:#455a64;word-break:break-word;margin:6px 0}
.post .ref a{color:#1565c0}
.post blockquote{background:#fff8e1;border:1px solid #ffe082;border-right:4px solid #f9a825;border-radius:8px;padding:6px 12px;margin:12px 0}
.post hr{border:0;border-top:1px solid #dce3ec;margin:16px 0}
.post em.cap{display:block;font-size:.78rem;color:#78909c;font-style:normal}
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
    updated = p.get("updated", "")
    date_line = f"📅 {date_fa}" + (f" · به‌روزرسانی: {updated}" if updated and updated != date_fa else "")
    crumbs = f'<a href="/">خانه</a> › <a href="/blog/">وبلاگ</a> › {p["title"]}'
    faq_items, article_body = extract_faq(article_body)
    faq_html, ld_faq = "", ""
    if faq_items:
        details = "".join(
            f'<details open><summary>{_inline_md(q)}</summary><div>{md_to_html(a)}</div></details>'
            for q, a in faq_items)
        faq_html = f'<section class="faq" id="faq"><h2>{FAQ_HEADING}</h2>{details}</section>\n'
        ld_faq = json.dumps({"@context": "https://schema.org", "@type": "FAQPage",
                             "mainEntity": [{"@type": "Question", "name": _plain(_inline_md(q)),
                                             "acceptedAnswer": {"@type": "Answer",
                                                                "text": _plain(md_to_html(a))}}
                                            for q, a in faq_items]}, ensure_ascii=False)
    body = f"""
<h1>{p['title']}</h1>
<span class="pdate">{date_line} · DDSVerified</span>
<article class="post">
{faq_html}{md_to_html(article_body)}
</article>
{TRUST_HTML}
<p><a class="cta" href="/">🛒 مشاهده و خرید فرزهای دندانپزشکی</a></p>"""
    ld_article = json.dumps({"@context": "https://schema.org", "@type": "Article",
                             "headline": p["title"], "description": p["description"],
                             "image": article_img, "datePublished": p["date"],
                             "dateModified": updated or p["date"], "inLanguage": "fa-IR",
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
    if ld_faq:
        extra += f'\n<script type="application/ld+json">{ld_faq}</script>'
    return _layout(title, p["description"], url, crumbs, body, extra)


def build_blog_index(posts: list) -> str:
    title = "وبلاگ DDSVerified — راهنمای خرید فرز دندانپزشکی"
    desc = "مقالات تخصصی و یافته‌های Drs' Choice: راهنمای گریت و کد ISO فرز، شواهد سایش فرز الماسه و زیرکونیا، مصرف فرز و درخت تصمیم بلیچینگ؛ همراه با پرسش‌های متداول و منابع."
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
<div class="intro"><p>مقالات تخصصی و یافته‌های Drs' Choice: راهنمای گریت و کد ISO فرزها، شواهد سایش فرز الماسه و برش زیرکونیا، برآورد مصرف فرز در مطب و درخت تصمیم بلیچینگ. هر مقاله با پرسش‌های متداول شروع می‌شود و ادعاهای آن با شماره به فهرست منابع (PubMed، استاندارد ISO یا کتاب مرجع) در انتهای همان مقاله ارجاع داده شده است.</p>
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
    '.cmp-price .old-price{font-size:1rem;font-weight:400;color:#78909c}'
    '.cmp-price .discount-badge{font-size:.85rem;color:#fff;background:#cc3333;border-radius:12px;padding:2px 8px}'
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
                             "brand": {"@type": "Brand", "name": "AZDENT"},
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
<div class="cmp-price">{price_html(p, data, campaign=True)} <small>({fmt_price(price // quantity)} تومان به ازای هر عدد فرز)</small></div>
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
.price .old-price{font-size:.85rem;font-weight:400;color:#78909c}.price .discount-badge{font-size:.75rem;color:#fff;background:#cc3333;border-radius:12px;padding:2px 8px}
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
.brand-cell{display:flex;align-items:center;gap:8px}.brand-cell img{display:block;width:70px;height:auto}
footer{text-align:center;font-size:.78rem;color:#455a64;padding:18px}footer .contact-links{display:flex;justify-content:center;flex-wrap:wrap;gap:8px;margin:0 auto 12px}
footer .contact-links a{display:inline-flex;align-items:center;gap:5px;padding:5px 9px;border:1px solid #dce3ec;border-radius:8px;color:#1565c0;background:#fff;text-decoration:none}
footer .contact-links svg{width:20px;height:20px;flex:none}footer p{margin:4px 0}"""

EVIDENCE_CSS = """.evidence{background:#fff;border:1px solid #dce3ec;border-right:4px solid #1565c0;border-radius:12px;padding:14px 16px;margin:0 0 16px;font-size:.88rem}
.evidence h2{margin-top:0}.evidence h3{font-size:.95rem;color:#1565c0;margin:14px 0 6px}.evidence p{margin:6px 0}
.evidence ul,.evidence ol{padding-right:20px;margin:6px 0}.evidence li{margin:5px 0}
.evidence sup a{color:#1565c0;text-decoration:none;font-weight:700}.ev-type{font-size:.72rem;color:#78909c}
.ev-note{background:#fff8e1;border:1px solid #ffe082;border-radius:8px;padding:8px 10px}
.evidence .refs{direction:ltr;text-align:left;padding:0 0 0 22px;font-size:.76rem;color:#455a64}.evidence .refs a{color:#1565c0;word-break:break-word}
.ev-meta{font-size:.72rem;color:#78909c}"""


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
<footer>{CONTACT_LINKS}<p>📍 آدرس: سعادت آباد، بهزادی جنوبی</p><p>مسئول علمی مجموعه : دکتر محمد رضا زینلی DMD DDS</p><p>DDSVerified © · تنوع مدل و دور فرز برای انتخاب متناسب با نیاز شما · ddsverified.ir</p></footer>
</body>
</html>"""


# ------------------------------------------------------------ builders -----
def _model_block(p, shape_name_short, data):
    model = p["model"]
    in_stock = p["inventory"] > 0
    grit_fa = data["grits"].get(p["grit"], GRIT_LABELS.get(p["grit"], "-"))
    pack_note = ("تک‌فروشی یا بسته ۶ عددی" if p.get("pack_size") else "فروش تکی") if p.get("multiplier") == 1 else f"بسته {fa(data['burs_per_pack'])} عددی"
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
      {BRAND_ROW}
    </table>
  </div>
  <p class="price">{price_html(p, data)}</p>
  <a class="cta" href="/index.html#{quote(model)}">🛒 خرید فرز {model} — افزودن به سبد خرید</a>
</section>"""


def build_category_page(shape_key, data):
    products = group_by_page(data)[shape_key]
    sname = shape_fa(shape_key, data)
    # short display name for headings (strip the common prefix "فرز دندانپزشکی ")
    short = sname.replace("فرز دندانپزشکی ", "").replace("فرز ", "", 1) if sname.startswith("فرز") else sname
    slug_url = cat_url(shape_key)
    n_models = fa(len(products))

    ev = EVIDENCE.get(shape_key)
    title = f"فرز {short} | کاربرد بالینی مبتنی بر شواهد و {n_models} مدل | DDSVerified"
    desc = ev["meta"] if ev else f"فرز دندانپزشکی {short} در {n_models} مدل با اندازه‌ها و گریت‌های مختلف؛ مشخصات فنی و کد ISO و USA برای انتخاب دقیق و ارسال به سراسر ایران."
    intro = (f"{sname} در {n_models} مدل با اندازه و گریت‌های مختلف موجود است. در ادامه، کاربرد بالینی این فرز بر پایه مقالات علمی نمایه‌شده در PubMed خلاصه شده و منبع هر یافته لینک شده است."
             if ev else INTROS.get(shape_key, f"{sname} در مدل‌ها و دورهای مختلف عرضه می‌شود. مشخصات فنی هر مدل را برای انتخاب متناسب با نیاز خود بررسی کنید."))
    evidence_html = build_evidence_html(shape_key, short)

    grit_strip = "".join(f"<span>{data['grits'].get(g_, GRIT_LABELS[g_])}</span>" for g_ in GRIT_ORDER)
    blocks = "".join(_model_block(p, short, data) for p in products)

    ev_faqs = []
    if ev:
        ev_faqs = [
            (f"فرز {short} برای چه کاری استفاده می‌شود؟", "، ".join(ev["uses"]) + "."),
            (f"شواهد علمی درباره کاربرد فرز {short} چه می‌گویند؟",
             f"{ev['evidence'][0][0]} (منبع: {SOURCES[ev['evidence'][0][1]]['journal']} {SOURCES[ev['evidence'][0][1]]['year']}، PMID {SOURCES[ev['evidence'][0][1]]['pmid']})"),
        ]
    faq_items = ev_faqs + FAQS.get(shape_key, []) + FAQS["_common"]
    faq_html = "".join(f"<details><summary>{q}</summary><p>{a}</p></details>" for q, a in faq_items)

    related_keys = [k for k in group_by_page(data) if k != shape_key][:4]
    related_html = "".join(f'<a href="/{cat_url(k)}">{shape_fa(k, data)}</a>' for k in related_keys)

    ld_items = [{"@type": "ListItem", "position": i + 1,
                 "item": {"@type": "Product", "name": f"فرز {short} {p['model']}",
                          "image": img_rel(p["model"]),
                          "sku": p["model"],
                          "brand": {"@type": "Brand", "name": "AZDENT"},
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
    if ev:
        ld_page = json.dumps({
            "@context": "https://schema.org", "@type": "CollectionPage",
            "name": f"فرز {short}: کاربرد بالینی مبتنی بر شواهد",
            "description": desc, "url": f"{BASE}/{slug_url}", "inLanguage": "fa-IR",
            "lastReviewed": EVIDENCE_REVIEWED,
            "about": {"@type": "Thing", "name": sname},
            "publisher": {"@type": "Organization", "name": "DDSVerified", "url": f"{BASE}/"},
            "citation": [{
                "@type": "ScholarlyArticle", "name": SOURCES[k]["title"],
                "author": SOURCES[k]["authors"], "datePublished": SOURCES[k]["year"],
                "isPartOf": {"@type": "Periodical", "name": SOURCES[k]["journal"]},
                "url": pubmed_url(SOURCES[k]["pmid"]),
                "identifier": {"@type": "PropertyValue", "propertyID": "PMID", "value": SOURCES[k]["pmid"]},
            } for k in _evidence_refs(shape_key)],
        }, ensure_ascii=False)
        extra += f'\n<script type="application/ld+json">{ld_page}</script>\n<style>{EVIDENCE_CSS}</style>'

    body = f"""
<h1>فرز {short}: کاربرد بالینی مبتنی بر شواهد و خرید</h1>
<div class="intro"><p>{intro}</p>
<p class="grits">ترتیب سختی دور فرز از سخت‌ترین به نرم‌ترین: {grit_strip}</p></div>
{evidence_html}
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
    pev = product_evidence(p, data)
    ev_keys = list(dict.fromkeys(k for _, k in pev.get("findings", [])))
    if pev:
        num = {k: n + 1 for n, k in enumerate(ev_keys)}
        intro_html = f"<p><strong>{sname} مدل {model}</strong> با {pev['spec']}، برای {pev['use']} کاربرد دارد.</p>"
        evidence_html = f"""
<section class="evidence" id="clinical-evidence">
<h2>کاربرد فرز {model} بر پایه شواهد علمی</h2>
<ul class="ev-list">{"".join(_finding_li(t, k, num[k]) for t, k in pev["findings"])}</ul>
<ol class="refs">{"".join(_ref_li(k, num[k]) for k in ev_keys)}</ol>
<p class="ev-meta"><a href="/{cat_path}#clinical-evidence">شواهد کامل و منابع بیشتر درباره فرز {short}</a> · آخرین بازبینی منابع: {fa(EVIDENCE_REVIEWED)}</p>
</section>"""
    else:
        clinical = p.get("desc") or INTROS.get(shape_key, f"{sname} یکی از خانواده‌های پرکاربرد فرزهای دندانپزشکی است.")
        intro_html = f"<p>{sname} مدل <strong>{model}</strong> {spec_sentence} {clinical.strip()}</p>"
        evidence_html = ""
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

    if pev:
        title = f"فرز {short} {model} | کاربرد مبتنی بر شواهد و مشخصات | DDSVerified"
        use_plain = re.sub(r"\s*\([^)]*\)", "", pev["use"])
        lead = f"فرز {short} مدل {model}؛ {pev['spec'].split('، ')[0]}، برای "
        tail = ". کاربرد بالینی با منابع PubMed."
        for sep in (" در ", " و "):
            if len(lead + use_plain + tail) > 160:
                use_plain = use_plain.split(sep)[0]
        desc = lead + use_plain + tail
    else:
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
<div class="intro">{intro_html}</div>
{endo_z_reasons}
{evidence_html}
<section class="model-block">
  <div class="model-head"><h3>مشخصات فنی فرز {model}</h3>{stock_badge}</div>
  <div class="mbody">
    <img src="{img_rel(model)}" alt="فرز {short} مدل {model} دندانپزشکی" width="267" height="400" loading="lazy">
    <table class="specs-t">
      <tr><td>مدل</td><td dir="ltr">{model}</td></tr>
      {BRAND_ROW}
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
  <p class="price">{price_html(p, data)}</p>
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
                             "brand": {"@type": "Brand", "name": "AZDENT"},
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
    if pev:
        ld_page = json.dumps({"@context": "https://schema.org", "@type": "ItemPage",
                              "name": f"فرز {short} مدل {model}", "description": desc,
                              "url": f"{BASE}/{page_path}", "inLanguage": "fa-IR",
                              "lastReviewed": EVIDENCE_REVIEWED,
                              "citation": _citation_ld(ev_keys)}, ensure_ascii=False)
        extra += f'\n<script type="application/ld+json">{ld_page}</script>\n<style>{EVIDENCE_CSS}</style>'
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
.blogs-head-link{display:flex;align-items:center;gap:8px;text-decoration:none;color:inherit}
.blogs-head-link:hover h2,.blogs-head-link:focus-visible h2{text-decoration:underline}
.blogs-head-link .bc-all{font-size:.7rem;color:#1565c0;font-weight:700}
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
<a class="blogs-head-link" href="/blog/" aria-label="مشاهده همه مقالات تخصصی و یافته‌ها (Drs' Choice)">
<h2>مقالات تخصصی و یافته‌ها</h2>
<span class="blogs-tag">Drs' Choice</span>
<span class="bc-all">همه مقالات ←</span>
</a>
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

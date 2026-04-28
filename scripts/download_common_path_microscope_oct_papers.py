#!/usr/bin/env python
from __future__ import annotations

import argparse
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)


@dataclass
class Lead:
    key: str
    title: str
    year: str
    authors: str = ""
    priority: str = "B"
    category: str = ""
    urls: list[str] = field(default_factory=list)


LEADS: list[Lead] = [
    Lead(
        "krstajic-2011-common-path-fdoct-multiple-reflections",
        "Common path Fourier domain optical coherence tomography based on multiple reflections within the sample arm",
        "2011",
        "Krstajic and Matcher",
        "A",
        "CP-OCT microscope objective",
        ["https://eprints.whiterose.ac.uk/id/eprint/43092/2/WRRO_43092.pdf"],
    ),
    Lead(
        "carrasco-zevallos-2016-live-volumetric-4d-mioct",
        "Live volumetric (4D) visualization and guidance of in vivo human ophthalmic surgery with intraoperative optical coherence tomography",
        "2016",
        "Carrasco-Zevallos et al.",
        "A",
        "MIOCT",
        ["https://www.nature.com/articles/srep31689"],
    ),
    Lead(
        "zhang-2022-microscope-integrated-iocta",
        "显微集成术中光学相干断层血流造影术",
        "2022",
        "张子艺等",
        "A",
        "Chinese MIOCT/OCTA",
        ["https://www.researching.cn/ArticlePdf/m00001/2022/49/15/1507301.pdf"],
    ),
    Lead(
        "vakhtin-2003-common-path-interferometer-fd-oct",
        "Common-path interferometer for frequency-domain optical coherence tomography",
        "2003",
        "Vakhtin et al.",
        "A",
        "CP-OCT foundation",
        ["https://opg.optica.org/ao/fulltext.cfm?uri=ao-42-34-6953"],
    ),
    Lead(
        "kang-2010-common-path-oct-review",
        "Common-Path Optical Coherence Tomography for Biomedical Imaging and Sensing",
        "2010",
        "Kang et al.",
        "A",
        "CP-OCT review",
        ["https://pmc.ncbi.nlm.nih.gov/articles/PMC2907894/"],
    ),
    Lead(
        "tan-2009-in-fiber-common-path-oct",
        "In-fiber common-path optical coherence tomography using a conical-tip fiber",
        "2009",
        "Tan et al.",
        "A",
        "Fiber CP-OCT",
        ["https://opg.optica.org/vjbo/fulltext.cfm?uri=oe-17-4-2375"],
    ),
    Lead(
        "sharma-2007-side-viewing-bare-fiber-cp-oct",
        "Common-path optical coherence tomography with side-viewing bare fiber probe for endoscopic optical coherence tomography",
        "2007",
        "Sharma and Kang",
        "A",
        "Fiber CP-OCT",
        ["https://pure.johnshopkins.edu/en/publications/common-path-optical-coherence-tomography-with-side-viewing-bare-f/"],
    ),
    Lead(
        "lee-2019-high-index-epoxy-lensed-fiber-cp-oct",
        "Common-path all-fiber optical coherence tomography probe based on high-index elliptical epoxy-lensed fiber",
        "2019",
        "Lee et al.",
        "A",
        "Fiber CP-OCT",
        [
            "https://pure.johnshopkins.edu/en/publications/common-path-all-fiber-optical-coherence-tomography-probe-based-on/",
            "https://www.spiedigitallibrary.org/journals/optical-engineering/volume-58/issue-2/026116/Common-path-all-fiber-optical-coherence-tomography-probe-based-on/10.1117/1.OE.58.2.026116.short",
        ],
    ),
    Lead(
        "wang-2016-mems-endoscopic-common-path-oct",
        "Common-path optical coherence tomography using a MEMS-based endoscopic probe",
        "2016",
        "Wang et al.",
        "A",
        "Endoscopic CP-OCT",
        ["https://opg.optica.org/ao/fulltext.cfm?uri=ao-55-25-6930"],
    ),
    Lead(
        "guo-2023-cost-effective-free-hand-cp-sd-oct",
        "Implementation of Cost-effective Common Path Spectral Domain Free-hand Scanning OCT System",
        "2023",
        "Guo et al.",
        "A",
        "Free-hand CP-SD-OCT",
        ["https://opg.optica.org/abstract.cfm?uri=copp-7-2-176"],
    ),
    Lead(
        "sharma-2005-all-fiber-cp-oct-sensitivity",
        "All-fiber common-path optical coherence tomography: sensitivity optimization and system analysis",
        "2005",
        "Sharma, Fried, and Kang",
        "A",
        "CP-OCT SNR",
        [
            "https://www.researchgate.net/publication/3409982_All-fiber_common-path_optical_coherence_tomography_Sensitivity_optimization_and_system_analysis"
        ],
    ),
    Lead(
        "li-2008-snr-analysis-all-fiber-cp-oct",
        "Signal-to-noise ratio analysis of all-fiber common-path optical coherence tomography",
        "2008",
        "Li et al.",
        "A",
        "CP-OCT SNR",
        ["https://opg.optica.org/ao/fulltext.cfm?uri=ao-47-27-4833"],
    ),
    Lead(
        "liu-2008-fiber-optic-fourier-domain-cp-oct",
        "Fiber-optic Fourier-domain common-path OCT",
        "2008",
        "Liu et al.",
        "A",
        "FD CP-OCT",
        ["https://www.researching.cn/ArticlePdf/m00005/2008/6/12/COL06120899.pdf"],
    ),
    Lead(
        "huang-2012-motion-compensated-handheld-cp-fd-oct",
        "Motion-compensated hand-held common-path Fourier-domain optical coherence tomography probe",
        "2012",
        "Huang et al.",
        "B",
        "Handheld CP-OCT",
        ["https://pure.johnshopkins.edu/en/publications/motion-compensated-hand-held-common-path-fourier-domain-optical-c-2"],
    ),
    Lead(
        "balicki-2009-single-fiber-oct-microsurgical-instruments",
        "Single Fiber Optical Coherence Tomography Microsurgical Instruments for Computer and Robot-Assisted Retinal Surgery",
        "2009",
        "Balicki et al.",
        "B",
        "CP-OCT microsurgery",
        ["https://link.springer.com/chapter/10.1007/978-3-642-04268-3_14"],
    ),
    Lead(
        "ehlers-2011-integration-sd-oct-surgical-microscope",
        "Integration of a spectral domain optical coherence tomography system into a surgical microscope for intraoperative imaging",
        "2011",
        "Ehlers et al.",
        "A",
        "MIOCT",
        ["https://pmc.ncbi.nlm.nih.gov/articles/PMC3109021/"],
    ),
    Lead(
        "hahn-2013-high-resolution-mioct",
        "Preclinical evaluation and intraoperative human retinal imaging with a high-resolution microscope-integrated spectral domain optical coherence tomography device",
        "2013",
        "Hahn et al.",
        "A",
        "MIOCT",
        ["https://pubmed.ncbi.nlm.nih.gov/23538579/"],
    ),
    Lead(
        "tao-2014-mioct-etl-hud",
        "Microscope-integrated intraoperative OCT with electrically tunable focus and heads-up display for imaging of ophthalmic surgical maneuvers",
        "2014",
        "Tao et al.",
        "A",
        "MIOCT focus/HUD",
        ["https://opg.optica.org/boe/abstract.cfm?uri=boe-5-6-1877"],
    ),
    Lead(
        "ehlers-2014-integrative-advances-oct-guided-surgery",
        "Integrative Advances for OCT-Guided Ophthalmic Surgery and Intraoperative OCT: Microscope Integration, Surgical Instrumentation, and Heads-Up Display Surgeon Feedback",
        "2014",
        "Ehlers et al.",
        "A",
        "MIOCT prototype",
        ["https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0105224"],
    ),
    Lead(
        "carrasco-zevallos-2017-intraoperative-oct-review",
        "Review of intraoperative optical coherence tomography: technology and applications",
        "2017",
        "Carrasco-Zevallos et al.",
        "B",
        "iOCT review",
        ["https://pmc.ncbi.nlm.nih.gov/articles/PMC5480568/"],
    ),
    Lead(
        "xu-2020-microscope-integrated-ss-oct-canaloplasty",
        "Feasibility of microscope-integrated swept-source optical coherence tomography in canaloplasty",
        "2020",
        "Xu et al.",
        "A",
        "SS-MIOCT",
        ["https://atm.amegroups.org/article/view/58297/html"],
    ),
    Lead(
        "posarelli-2020-impact-microscope-integrated-ioct",
        "What Is the Impact of Intraoperative Microscope-Integrated OCT in Ophthalmic Surgery? Relevant Applications and Outcomes. A Systematic Review",
        "2020",
        "Posarelli et al.",
        "B",
        "MIOCT review",
        ["https://www.mdpi.com/2077-0383/9/6/1682"],
    ),
    Lead(
        "draxinger-2024-mhz-microscope-integrated-oct",
        "Microscope integrated MHz optical coherence tomography for in vivo human neurosurgery",
        "2024",
        "Draxinger et al.",
        "B",
        "MHz MIOCT",
        ["https://pmc.ncbi.nlm.nih.gov/articles/PMC11482179/"],
    ),
    Lead(
        "han-2020-ocm-technology-applications",
        "光学相干层析显微成像的技术与应用",
        "2020",
        "韩涛等",
        "A",
        "Chinese OCM review",
        ["https://www.researching.cn/ArticlePdf/m00001/2020/47/2/0207004.pdf"],
    ),
    Lead(
        "zhou-2010-integrated-oct-microscopy-breast",
        "Integrated Optical Coherence Tomography and Microscopy for Ex Vivo Multiscale Evaluation of Human Breast Tissues",
        "2010",
        "Zhou et al.",
        "B",
        "OCT/OCM",
        ["https://pmc.ncbi.nlm.nih.gov/articles/PMC3028517/"],
    ),
    Lead(
        "lee-2010-integrated-oct-and-microscopy-thesis",
        "Integrated optical coherence tomography and microscopy",
        "2010",
        "H. C. Lee",
        "A",
        "Thesis OCT/OCM",
        ["https://dspace.mit.edu/bitstream/handle/1721.1/58530/Lee-2010-Integrated%20optical%20coherence.pdf?isAllowed=y&sequence=1"],
    ),
    Lead(
        "handheld-ocm-endoscope-2011",
        "Design of a handheld optical coherence microscopy endoscope",
        "2011",
        "Korde et al.",
        "B",
        "OCM endoscope",
        ["https://pmc.ncbi.nlm.nih.gov/articles/PMC3144968/"],
    ),
    Lead(
        "ntu-2022-ff-oct-thesis",
        "國立臺灣大學電機資訊學院光電工程學研究所碩士論文",
        "2022",
        "",
        "A",
        "FF-OCT thesis",
        ["https://tdr.lib.ntu.edu.tw/jspui/bitstream/123456789/88397/1/ntu-111-2.pdf"],
    ),
    Lead(
        "dubois-2002-linnik-full-field-oct",
        "High-resolution full-field optical coherence tomography with a Linnik microscope",
        "2002",
        "Dubois et al.",
        "A",
        "Linnik FF-OCT",
        ["https://www.nature.com/articles/nbt1202-1265"],
    ),
    Lead(
        "lu-2013-immersion-mirau-ff-oct",
        "Full-field optical coherence tomography using immersion Mirau interference microscope",
        "2013",
        "Lu, Chang, and Kao",
        "A",
        "Mirau FF-OCT",
        ["https://opg.optica.org/vjbo/abstract.cfm?uri=ao-52-18-4400"],
    ),
    Lead(
        "anna-2011-high-resolution-ff-ocm-mirau",
        "High-resolution full-field optical coherence microscopy using a Mirau interferometer",
        "2011",
        "Anna et al.",
        "A",
        "Mirau FFOCM",
        ["https://opg.optica.org/abstract.cfm?uri=boe-2-9-2510"],
    ),
    Lead(
        "mazlin-2020-common-path-ff-sd-oct-cornea-limbus",
        "Real-time non-contact cellular imaging and angiography of human cornea and limbus with common-path full-field/SD OCT",
        "2020",
        "Mazlin et al.",
        "A",
        "Common-path FF/SD-OCT",
        ["https://www.nature.com/articles/s41467-020-15792-x"],
    ),
    Lead(
        "monfort-2023-dynamic-ff-oct-module-commercial-microscopes",
        "Dynamic full-field optical coherence tomography module adapted to commercial microscopes allows longitudinal in vitro cell culture study",
        "2023",
        "Monfort et al.",
        "A",
        "D-FFOCT microscope module",
        ["https://www.nature.com/articles/s42003-023-05378-w"],
    ),
    Lead(
        "graf-2010-coherence-gate-curvature-high-na",
        "Correction of coherence gate curvature in high numerical aperture optical coherence imaging",
        "2010",
        "Graf, Adie, and Boppart",
        "A",
        "High-NA OCM error",
        ["https://opg.optica.org/abstract.cfm?uri=ol-35-18-3120"],
    ),
    Lead(
        "aguirre-2003-high-resolution-ocm-in-vivo-cellular",
        "High-resolution optical coherence microscopy for high-speed, in vivo cellular imaging",
        "2003",
        "Aguirre et al.",
        "A",
        "OCM",
        ["https://opg.optica.org/ol/abstract.cfm?uri=ol-28-21-2064"],
    ),
    Lead(
        "joo-2008-spectral-domain-ocpm-thesis",
        "Spectral-domain optical coherence phase microscopy for quantitative biological studies",
        "2008",
        "Chulmin Joo",
        "A",
        "OCPM thesis",
        ["https://dspace.mit.edu/handle/1721.1/43142"],
    ),
    Lead(
        "mirau-line-field-confocal-oct-2020",
        "Mirau-based line-field confocal optical coherence tomography",
        "2020",
        "Dubois and Ogien",
        "B",
        "Line-field Mirau OCT",
        ["https://m.researching.cn/articles/OJbeaac4e368b32347/referenceandcitations"],
    ),
    Lead(
        "he-2024-mirau-ff-oct-system",
        "基于Mirau干涉结构的全场光学相干层析系统",
        "2024",
        "何豪等",
        "A",
        "Chinese Mirau FF-OCT",
        ["https://www.researchgate.net/publication/383542956_jiyuMirauganshejiegoudequanchangguangxuexianggancengxixitong"],
    ),
    Lead(
        "liu-2024-ocm-endoscopic-review-cn",
        "光学相干层析显微内窥成像技术研究进展",
        "2024",
        "刘德军等",
        "B",
        "Chinese OCT microendoscopy review",
        ["https://cofs.szu.edu.cn/ziyi.pdf"],
    ),
    Lead(
        "intraoperative-oct-fundus-surgery-cn",
        "术中OCT在眼底手术中的应用",
        "",
        "",
        "B",
        "Chinese iOCT review",
        ["https://cjeo-journal.org/wp-content/uploads/2023/09/%E6%9C%AF%E4%B8%ADOCT%E5%9C%A8%E7%9C%BC%E5%BA%95%E6%89%8B%E6%9C%AF%E4%B8%AD%E7%9A%84%E5%BA%94%E7%94%A8.pdf"],
    ),
    Lead(
        "mou-full-field-oct-3d-imaging-cn",
        "全场光学相干层析三维成像技术研究",
        "",
        "牟宁等",
        "B",
        "Chinese FF-OCT",
        ["https://www.joconline.com.cn/rc-pub/front/front-article/download/59714121/lowqualitypdf/%E5%85%A8%E5%9C%BA%E5%85%89%E5%AD%A6%E7%9B%B8%E5%B9%B2%E5%B1%82%E6%9E%90%E4%B8%89%E7%BB%B4%E6%88%90%E5%83%8F%E6%8A%80%E6%9C%AF%E7%A0%94%E7%A9%B6.pdf"],
    ),
    Lead(
        "wei-2022-oct-ophthalmic-surgical-guidance-thesis",
        "Optical Coherence Tomography Ophthalmic Surgical Guidance",
        "2022",
        "Shuwen Wei",
        "A",
        "Thesis OCT surgical guidance",
        ["https://jscholarship.library.jhu.edu/bitstream/handle/1774.2/67837/WEI-DISSERTATION-2022.pdf?sequence=1"],
    ),
    Lead(
        "cheon-2016-oct-distal-sensor-thesis",
        "Optical Coherence Tomography Distal Sensor for Microsurgery",
        "2016",
        "G. W. Cheon",
        "A",
        "Thesis CP-SSOCT",
        ["https://jscholarship.library.jhu.edu/bitstreams/61a4fe79-9d2c-45af-bea3-b1e4fb11776d/download"],
    ),
    Lead(
        "modi-2024-real-time-surgeon-control-ioct-thesis",
        "Real-Time Surgeon Control of Intraoperative Optical Coherence Tomography",
        "2024",
        "M. A. Modi",
        "A",
        "Thesis MIOCT",
        ["https://dukespace.lib.duke.edu/items/9d8e353b-b974-4592-a324-066aeb9ef8dd"],
    ),
    Lead(
        "jd-li-2024-intraoperative-oct-ophthalmic-microsurgery-thesis",
        "Development of Intraoperative Optical Coherence Tomography Imaging for Ophthalmic Microsurgery",
        "2024",
        "JD Li",
        "A",
        "Thesis iOCT",
        ["https://dukespace.lib.duke.edu/items/1b5b99ac-5501-4c21-8e9e-02e75c46cd7b"],
    ),
    Lead(
        "kapeller-2023-stereoscopic-4d-mioct-thesis",
        "Stereoscopic Visualization of Intraoperative 4D-miOCT in Ophthalmic Surgery",
        "2023",
        "Florian Kapeller",
        "B",
        "Thesis 4D-miOCT",
        ["https://repositum.tuwien.at/bitstream/20.500.12708/176743/1/Kapeller%20Florian%20-%202023%20-%20Stereoscopic%20Visualiation%20of%20Intraoperative%204D-miOCT...pdf"],
    ),
    Lead(
        "acharya-2012-all-fiber-td-common-path-oct-thesis",
        "All-fiber time-domain common-path optical coherence tomography speckle reduction",
        "2012",
        "Megha N. Acharya",
        "B",
        "Thesis CP-OCT",
        ["https://etd.ohiolink.edu/acprod/odb_etd/r/etd/search/10?clear=10&p10_accession_num=akron1353336847"],
    ),
    Lead(
        "marrese-thesis-ultrathin-probes-common-path-oct",
        "Ultrathin probes for common-path optical coherence tomography",
        "",
        "M. Marrese",
        "B",
        "Thesis CP-OCT probes",
        ["https://research.vu.nl/ws/files/121567411/M%20%20Marrese%20-%20thesis.pdf"],
    ),
    Lead(
        "ubc-combined-multiphoton-microscopy-oct-thesis",
        "Design and application of combined multiphoton microscopy and optical coherence tomography",
        "",
        "",
        "B",
        "Thesis multimodal microscope/OCT",
        ["https://open.library.ubc.ca/soa/cIRcle/collections/ubctheses/24/items/1.0073160"],
    ),
    Lead(
        "manitoba-full-field-oct-thesis",
        "Design and Implementation of Full-Field Optical Coherence Tomography",
        "",
        "Rahul Thakur",
        "B",
        "Thesis FF-OCT",
        ["https://mspace.lib.umanitoba.ca/bitstream/handle/1993/32664/thakur_rahul.pdf?sequence=1"],
    ),
]


def normalize_text(value: str) -> str:
    text = value.casefold()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def slugify(value: str, max_len: int = 90) -> str:
    text = value.casefold()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    if not text:
        text = "paper"
    return text[:max_len].strip("-") or "paper"


def filename_for(lead: Lead) -> str:
    prefix = f"{lead.year}-" if lead.year else ""
    return f"{prefix}{slugify(lead.title)}.pdf"


def absolute_url(base: str, href: str) -> str:
    return urllib.parse.urljoin(base, html.unescape(href.strip()))


def request_url(url: str, timeout: int = 35) -> tuple[bytes, str, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/pdf,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read(), response.headers.get("content-type", ""), response.geturl()


def looks_like_pdf(payload: bytes, content_type: str) -> bool:
    head = payload[:2048].lstrip()
    return head.startswith(b"%PDF") or "application/pdf" in content_type.casefold()


def bad_html_reason(payload: bytes) -> str:
    text = payload[:20000].decode("utf-8", "ignore").casefold()
    if "captcha" in text:
        return "html captcha/anti-bot page"
    if "access denied" in text:
        return "html access denied page"
    return "html page without confirmed pdf"


def extract_pdf_candidates(base_url: str, payload: bytes) -> list[str]:
    text = payload.decode("utf-8", "ignore")
    candidates: list[str] = []

    meta_patterns = [
        r'<meta[^>]+name=["\']citation_pdf_url["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']citation_pdf_url["\']',
        r'<meta[^>]+property=["\']citation_pdf_url["\'][^>]+content=["\']([^"\']+)["\']',
    ]
    for pattern in meta_patterns:
        for match in re.finditer(pattern, text, flags=re.I):
            candidates.append(absolute_url(base_url, match.group(1)))

    for match in re.finditer(r'href=["\']([^"\']+)["\']', text, flags=re.I):
        href = html.unescape(match.group(1))
        lowered = href.casefold()
        if any(
            token in lowered
            for token in (
                ".pdf",
                "/pdf/",
                "pdf?",
                "download",
                "bitstream",
                "bitstreams",
                "article/file",
                "type=printable",
            )
        ):
            candidates.append(absolute_url(base_url, href))

    parsed = urllib.parse.urlparse(base_url)
    if "nature.com" in parsed.netloc and "/articles/" in parsed.path and not parsed.path.endswith(".pdf"):
        candidates.append(urllib.parse.urlunparse(parsed._replace(path=parsed.path.rstrip("/") + ".pdf", query="")))

    if "mdpi.com" in parsed.netloc:
        candidates.append(base_url.rstrip("/") + "/pdf")

    if "journals.plos.org" in parsed.netloc and "id=" in parsed.query:
        qs = urllib.parse.parse_qs(parsed.query)
        article_id = qs.get("id", [""])[0]
        if article_id:
            candidates.append(
                urllib.parse.urlunparse(
                    parsed._replace(path=parsed.path.replace("/article", "/article/file"), query=f"id={article_id}&type=printable")
                )
            )

    seen: set[str] = set()
    unique: list[str] = []
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


def openalex_candidates(title: str, polite_email: str = "") -> list[str]:
    params = {"search": title, "per-page": "5"}
    if polite_email:
        params["mailto"] = polite_email
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
    try:
        payload, _content_type, _final = request_url(url, timeout=25)
        data = json.loads(payload.decode("utf-8", "ignore"))
    except Exception:
        return []

    candidates: list[str] = []
    for work in data.get("results", []):
        display_name = work.get("display_name") or ""
        if title_similarity(title, display_name) < 0.55:
            continue
        locations: list[dict[str, Any]] = []
        best = work.get("best_oa_location")
        if isinstance(best, dict):
            locations.append(best)
        locations.extend(loc for loc in work.get("locations") or [] if isinstance(loc, dict))
        for location in locations:
            pdf_url = location.get("pdf_url")
            landing_url = location.get("landing_page_url")
            if pdf_url:
                candidates.append(str(pdf_url))
            if landing_url:
                candidates.append(str(landing_url))

    seen: set[str] = set()
    unique: list[str] = []
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def attempt_download(lead: Lead, output_dir: Path, polite_email: str, sleep_sec: float) -> dict[str, Any]:
    row: dict[str, Any] = {
        "key": lead.key,
        "title": lead.title,
        "year": lead.year,
        "authors": lead.authors,
        "priority": lead.priority,
        "category": lead.category,
        "status": "failed",
        "attempts": [],
    }
    target = output_dir / filename_for(lead)
    candidate_urls = list(lead.urls)
    if polite_email is not None:
        candidate_urls.extend(openalex_candidates(lead.title, polite_email))

    seen: set[str] = set()
    queue: list[str] = []
    for url in candidate_urls:
        if url and url not in seen:
            seen.add(url)
            queue.append(url)

    idx = 0
    while idx < len(queue):
        url = queue[idx]
        idx += 1
        attempt: dict[str, Any] = {"url": url}
        try:
            payload, content_type, final_url = request_url(url)
            attempt["final_url"] = final_url
            attempt["content_type"] = content_type
            attempt["bytes"] = len(payload)
            if looks_like_pdf(payload, content_type):
                target.write_bytes(payload)
                row.update(
                    {
                        "status": "downloaded",
                        "pdf_path": str(target),
                        "source_url": final_url,
                        "bytes": len(payload),
                    }
                )
                row["attempts"].append(attempt)
                return row
            new_candidates = extract_pdf_candidates(final_url, payload)
            for candidate in new_candidates:
                if candidate not in seen:
                    seen.add(candidate)
                    queue.append(candidate)
            attempt["reason"] = bad_html_reason(payload)
            if new_candidates:
                attempt["discovered_pdf_candidates"] = new_candidates[:10]
        except urllib.error.HTTPError as exc:
            attempt["error"] = f"HTTP {exc.code}: {exc.reason}"
        except urllib.error.URLError as exc:
            attempt["error"] = f"URL error: {exc.reason}"
        except Exception as exc:
            attempt["error"] = repr(exc)
        row["attempts"].append(attempt)
        if sleep_sec > 0:
            time.sleep(sleep_sec)

    return row


def write_reports(results: list[dict[str, Any]], run_dir: Path) -> None:
    manifest = run_dir / "download_manifest.json"
    manifest.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    overrides = {}
    for row in results:
        if row.get("status") != "downloaded":
            continue
        pdf_path = Path(row["pdf_path"])
        overrides[pdf_path.name] = {
            "title": row["title"],
            "year": row.get("year") or "1900",
            "authors": row.get("authors", ""),
        }
    (run_dir / "metadata_overrides.json").write_text(
        json.dumps(overrides, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    ok = [row for row in results if row.get("status") == "downloaded"]
    failed = [row for row in results if row.get("status") != "downloaded"]
    lines = [
        "# Common-path / microscope-integrated OCT PDF download run",
        "",
        f"- Timestamp: `{datetime.now():%Y-%m-%d %H:%M:%S}`",
        f"- Downloaded: `{len(ok)}`",
        f"- Failed or access-limited: `{len(failed)}`",
        "",
        "## Downloaded",
        "",
    ]
    for row in ok:
        lines.append(f"- [{row['priority']}] {row['year']} {row['title']} -> `{row['pdf_path']}`")
    lines.extend(["", "## Failed / access-limited", ""])
    for row in failed:
        first_error = ""
        for attempt in row.get("attempts", []):
            first_error = attempt.get("error") or attempt.get("reason") or first_error
            if first_error:
                break
        lines.append(f"- [{row['priority']}] {row['year']} {row['title']} :: {first_error or 'no PDF found'}")
    (run_dir / "download_manifest.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--run-label", default="common-path-microscope-oct")
    parser.add_argument("--openalex-mailto", default="")
    parser.add_argument("--sleep-sec", type=float, default=0.5)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    output_root = Path(args.output_root).resolve()
    run_dir = output_root / "literature-downloads" / f"{datetime.now():%Y-%m-%d_%H%M%S}_{slugify(args.run_label, 40)}"
    pdf_dir = run_dir / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    leads = LEADS[: args.limit] if args.limit > 0 else LEADS
    results = []
    for lead in leads:
        print(f"[{lead.priority}] {lead.title}", flush=True)
        results.append(attempt_download(lead, pdf_dir, args.openalex_mailto, args.sleep_sec))

    write_reports(results, run_dir)
    print(str(run_dir))


if __name__ == "__main__":
    main()

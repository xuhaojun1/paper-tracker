# arxiv_tracker/extractors.py
import re
from typing import Dict, Optional, List
from urllib.parse import urlparse

# 常见顶会关键词（可继续扩充）
CONF_PAT = re.compile(
    r'\b('
    r'CVPR|ICCV|ECCV|NeurIPS|NIPS|ICLR|ICML|AAAI|IJCAI|ACL|EMNLP|NAACL|COLING|'
    r'KDD|WWW|The\s*Web\s*Conference|WSDM|SIGIR|SIGGRAPH(?:\s*Asia)?|ICME|ICASSP|WACV|'
    r'ACM\s*MM|MM|MICCAI|ISBI|CoRL|RSS|IROS|ICRA'
    r')\b(?:\s*20\d{2})?',
    flags=re.IGNORECASE
)

# 角色识别更丰富
ROLE_PAT = re.compile(
    r'\b(Oral(?:\s*Presentation)?|Spotlight|Poster|Highlight|Long|Short|Best\s*Paper|Honorable\s*Mention)\b',
    re.IGNORECASE
)

# 更稳健的 URL 提取（避免吃到右括号/方括号/引号等）
URL_PAT = re.compile(r'https?://[^\s)\]>\'"]+', re.IGNORECASE)

# 需要剔除的 URL 末尾常见标点
TRAILING_CHARS = '.,;:?!)]}>\'"'

# 常见代码托管主机（含子域名）
CODE_HOSTS = (
    'github.com',
    'gitlab.com',
    'bitbucket.org',
    'codeberg.org',
    'gitee.com',
    'huggingface.co',
    'sourceforge.net',
    'sr.ht',
    'git.sr.ht',
)

def _clean_url(u: str) -> str:
    """去掉 URL 末尾的标点等尾巴（如句点）"""
    while u and u[-1] in TRAILING_CHARS:
        u = u[:-1]
    return u

def _host_of(u: str) -> str:
    try:
        h = urlparse(u).netloc.lower()
    except Exception:
        return ''
    if h.startswith('www.'):
        h = h[4:]
    return h

def _is_code_host(h: str) -> bool:
    return any(h == ch or h.endswith('.' + ch) for ch in CODE_HOSTS)

def _is_project_like(u: str, h: str) -> bool:
    # 顶级域名或路径特征：常见项目页/学术主页
    if re.search(r'\.(?:io|ai|ml)$', h):
        return True
    if 'sites.google.com' in h:
        return True
    # 常见系所/实验室域名（可按需扩充）
    if any(t in h for t in ('.cs.', '.vision.', '.ee.', '.cv.', '.ml.')):
        return True
    # 常见项目/团队/论文页路径
    if re.search(r'/(project|projects|page|pages|people|lab|group|research|paper|papers)(/|$)', u, re.IGNORECASE):
        return True
    return False

def _dedup_keep_order(lst: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for x in lst:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out

def extract_venue_info(text: str) -> Optional[str]:
    if not text:
        return None
    m = CONF_PAT.search(text)
    if not m:
        return None
    conf = m.group(0).strip()
    role = None
    mr = ROLE_PAT.search(text)
    if mr:
        role = mr.group(0).strip()
    return f"{conf}{(' ' + role) if role else ''}"

def extract_urls(text: str) -> Dict[str, List[str]]:
    raw = URL_PAT.findall(text or "")
    cleaned = [_clean_url(u) for u in raw if u]

    code, proj, others = [], [], []
    for u in cleaned:
        h = _host_of(u)
        if not h:
            continue
        if _is_code_host(h):
            code.append(u)
        elif _is_project_like(u, h):
            proj.append(u)
        else:
            others.append(u)

    return {
        "all_urls": _dedup_keep_order(cleaned),
        "code_urls": _dedup_keep_order(code),
        "project_urls": _dedup_keep_order(proj),
    }

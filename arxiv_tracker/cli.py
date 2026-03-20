# -*- coding: utf-8 -*-
import os, re, sys, traceback, time, pathlib, click, json
from .config import Settings
from .notify.output import save_json, save_markdown
from .notify.email_template import render_email_html
from .pipeline import (
    fetch_papers, augment_links, score_and_filter,
    fetch_html_content, generate_summaries, translate_items,
)
from .utils.state import load_seen_ids, save_seen_ids
from .utils.logging import setup_logging

# 进程级防重：本进程内只允许发送一次
_SENT_EMAIL = False


def _split_categories(values):
    out = []
    for v in values or []:
        if not v:
            continue
        parts = re.split(r'\s*,\s*|\s*;\s*|/', v.strip())
        out.extend([p for p in parts if p])
    return out


def _split_keywords(values):
    out = []
    for v in values or []:
        if not v:
            continue
        parts = re.split(r'\s*,\s*|\s*;\s*', v.strip())
        out.extend([p for p in parts if p])
    return out


def _load_raw_cfg(maybe_path):
    import yaml
    path = maybe_path or "config.yaml"
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _extract_stamp_from_path(path: str) -> str:
    """从 outputs/arxiv_YYYYMMDD_HHMMSS.json 推断快照 stamp；兜底为当天日期"""
    try:
        name = os.path.basename(path or "")
        m = re.search(r"arxiv_(\d{8}_\d{6})", name)
        if m:
            return m.group(1)
    except Exception:
        pass
    return time.strftime("%Y%m%d")


def _norm_addr(s: str) -> str:
    return re.sub(r"\s+", "", (s or "")).lower()


def _dedup_addrs(seq):
    seen = set()
    out = []
    for x in seq or []:
        k = _norm_addr(x)
        if k and k not in seen:
            out.append(k)
            seen.add(k)
    return out


@click.group()
def cli():
    """arxiv-tracker CLI"""
    pass


@cli.command("run")
@click.option("--config", "config_path", type=click.Path(exists=True), help="配置文件路径（YAML）")
@click.option("--categories", multiple=True, help="学科分类，可多次或逗号分隔")
@click.option("--keywords", multiple=True, help="关键词，可多次或逗号分隔")
@click.option("--exclude-keywords", multiple=True, help="排除关键词，可多次或逗号分隔") 
@click.option("--logic", type=click.Choice(["AND", "OR"], case_sensitive=False), default=None)
@click.option("--max-results", type=int, default=None)
@click.option("--sort-by", type=click.Choice(["submittedDate", "lastUpdatedDate"]), default=None)
@click.option("--sort-order", type=click.Choice(["ascending", "descending"]), default=None)
@click.option("--lang", type=click.Choice(["zh", "en", "both"]), default=None, help="输出语言")
@click.option("--summary-mode", type=click.Choice(["none", "heuristic", "llm"]), default=None)
@click.option("--summary-scope", type=click.Choice(["tldr", "full", "both"]), default=None)
@click.option("--email", "email_enabled", is_flag=True, default=None, help="启用邮件发送（覆盖配置）")
@click.option("--email-detail", type=click.Choice(["simple", "full"]), default=None, help="邮件内容详略")
@click.option("--email-max-items", type=int, default=None, help="邮件最多包含的条目数")
@click.option("--out-dir", default="outputs", help="输出目录")
@click.option("--verbose", is_flag=True, help="打印详细运行日志")
@click.option("--translate", "translate_enabled", is_flag=True, default=None, help="启用 LLM 中文翻译（覆盖配置）")
@click.option("--translate-lang", type=click.Choice(["zh"]), default=None, help="翻译目标语言")
@click.option("--site-dir", default=None, help="输出静态站点目录（如 docs）")
@click.option("--site-url", default=None, help="站点首页 URL（用于邮件正文链接）")
@click.option("--no-email", is_flag=True, help="跳过邮件发送（用于重试）")

def run(config_path, categories, keywords, exclude_keywords, logic, max_results, sort_by, sort_order,
        lang, summary_mode, summary_scope, email_enabled, email_detail, email_max_items,
        out_dir, verbose, translate_enabled, translate_lang, no_email: bool,
        site_dir, site_url):
    try:
        setup_logging(verbose=verbose)

        if verbose:
            click.echo("[Run] Start")

        # ── 1) 载入设置 ──
        cfg = Settings.from_file(config_path) if config_path else Settings()
        cats = _split_categories(categories)
        keys = _split_keywords(keywords)
        ex_keys = _split_keywords(exclude_keywords)
        cfg.merge_cli(categories=cats or None,
                      keywords=keys or None,
                      exclude_keywords=ex_keys or None,
                      logic=(logic or cfg.logic),
                      max_results=(max_results or cfg.max_results),
                      sort_by=(sort_by or cfg.sort_by),
                      sort_order=(sort_order or cfg.sort_order))

        raw_cfg = _load_raw_cfg(config_path)
        lang = lang or raw_cfg.get("lang", "both")

        summary_cfg = raw_cfg.get("summary", {}) or {}
        llm_cfg = raw_cfg.get("llm", {}) or {}
        mode = summary_mode or summary_cfg.get("mode", "none")
        scope = summary_scope or summary_cfg.get("scope", "both")

        trans_cfg = (raw_cfg.get("translate", {}) or {}).copy()
        if translate_enabled is not None:
            trans_cfg["enabled"] = translate_enabled
        if translate_lang:
            trans_cfg["lang"] = translate_lang
        if "fields" not in trans_cfg:
            trans_cfg["fields"] = ["title", "summary"]

        email_cfg = (raw_cfg.get("email", {}) or {}).copy()
        if email_enabled is not None:
            email_cfg["enabled"] = bool(email_enabled)
        if email_detail:
            email_cfg["detail"] = email_detail
        if email_max_items is not None:
            email_cfg["max_items"] = int(email_max_items)
        if no_email:
            email_cfg["enabled"] = False
        email_cfg.setdefault("enabled", False)
        email_cfg.setdefault("detail", "full")
        email_cfg.setdefault("max_items", 50)

        fresh_cfg = raw_cfg.get("freshness") or {}
        unique_only = bool(fresh_cfg.get("unique_only", False))
        state_path = fresh_cfg.get("state_path", ".state/seen.json")

        if verbose:
            click.echo(f"[Run] categories: {cfg.categories}")
            click.echo(f"[Run] keywords  : {cfg.keywords}")
            click.echo(f"[Run] summary   : {mode}/{scope}")
            click.echo(f"[Run] lang      : {lang}")
            click.echo(f"[Run] translate : {trans_cfg.get('enabled', False)} -> {trans_cfg.get('lang', 'zh')}")
            click.echo(f"[Run] email     : enabled={email_cfg.get('enabled', False)}, detail={email_cfg.get('detail')}, max_items={email_cfg.get('max_items')}")

        # ── 2) 搜索论文（分页 + 时间窗 + 去重）──
        items = fetch_papers(cfg, raw_cfg, verbose=verbose)

        # ── 3) 补全代码/项目链接 ──
        augment_links(items, raw_cfg, verbose=verbose)

        # ── 4) LLM 重要度打分 + 排序 + 筛选 top_k ──
        items, score_map = score_and_filter(items, raw_cfg, verbose=verbose)

        # ── 5) 抓取 HTML 全文（为选中论文提供富上下文）──
        rich_contexts = fetch_html_content(items, raw_cfg, verbose=verbose)

        # ── 6) 生成结构化摘要（优先使用 HTML 全文）──
        summaries_zh = generate_summaries(
            items, rich_contexts, raw_cfg,
            mode=mode, lang=lang, scope=scope, verbose=verbose,
        )
        summaries_en = {}

        # ── 7) 翻译（中文）──
        translations = translate_items(items, raw_cfg, trans_cfg, verbose=verbose)

        # ── 8) 终端预览 ──
        if not items:
            click.echo("（本周暂无新增）")
        for idx, it in enumerate(items, 1):
            title = it.get("title", "")
            venue = it.get("venue_inferred") or (it.get("journal_ref") or "")
            score = it.get("importance_score", "—")
            reason = it.get("importance_reason", "")
            click.echo(f"{idx:02d}. [{score}] {title}")
            if reason:
                click.echo(f"    reason: {reason}")
            if venue:
                click.echo(f"    Venue: {venue}")
            click.echo(f"    Time: {it.get('published', '—')}  ->  {it.get('updated', '—')}")
            if it.get("pdf_url"):
                click.echo(f"    PDF : {it['pdf_url']}")
            sid = it.get("id") or ""
            tx = translations.get(sid)
            if tx and tx.get("title_zh"):
                click.echo(f"    标题(中): {tx['title_zh']}")
            click.echo("")

        # ── 9) 保存文件 ──
        json_path = save_json(items, out_dir)
        md_path   = save_markdown(items, out_dir, summaries_zh, summaries_en, lang=lang, translations=translations)
        click.echo(f"Saved: {json_path}")
        click.echo(f"Saved: {md_path}")

        # ── 10) 生成站点 ──
        page_url = None
        site_generated = False
        try:
            from .notify.sitegen import generate_site
            site_cfg = raw_cfg.get("site") or {}
            sd = site_dir or site_cfg.get("dir")
            if sd and (site_cfg.get("enabled", False) or site_dir is not None):
                keep = int(site_cfg.get("keep_runs", 60))
                title = site_cfg.get("title", "arXiv Results")
                theme = site_cfg.get("theme", "light")
                accent = site_cfg.get("accent", "#2563eb")
                site_res = generate_site(
                    items=items,
                    summaries_zh=summaries_zh or {},
                    summaries_en=summaries_en or {},
                    translations=translations or {},
                    site_dir=sd, site_title=title, keep_runs=keep,
                    theme=theme, accent=accent
                )
                click.echo(f"Saved: {site_res['index_path']}")
                page_url = site_url or site_cfg.get("url")
                if page_url and not page_url.endswith("/"):
                    page_url += "/"
                site_generated = True
        except Exception as e:
            click.secho(f"[Site] 生成失败: {e}", fg="red")

        # ── 11) 邮件发送 ──
        email_sent = False
        if email_cfg.get("enabled"):
            try:
                global _SENT_EMAIL
                if _SENT_EMAIL:
                    click.secho("[Email] 已在本进程发送过，跳过（process guard）", fg="yellow")
                    email_cfg["enabled"] = False

                try:
                    stamp = _extract_stamp_from_path(json_path)
                except Exception:
                    stamp = time.strftime("%Y%m%d")

                flag_dir = pathlib.Path(out_dir or "outputs")
                flag_dir.mkdir(parents=True, exist_ok=True)
                flag_path = flag_dir / f"email_sent_{stamp}.flag"
                if email_cfg.get("enabled") and flag_path.exists():
                    click.secho(f"[Email] 本次快照({stamp})已发送过，跳过（file guard）", fg="yellow")
                    email_cfg["enabled"] = False

                if email_cfg.get("enabled"):
                    email_addr = os.getenv("EMAIL_ADDR", "")
                    env_to = os.getenv("EMAIL_TO", "") or email_addr
                    to_list = [x.strip() for x in re.split(r"[;,]", env_to) if x.strip()] if env_to else (email_cfg.get("to") or [])
                    sender_env = os.getenv("EMAIL_SENDER", "") or email_addr
                    sender = sender_env or (email_cfg.get("sender") or "")
                    server  = os.getenv("SMTP_SERVER", "") or email_cfg.get("smtp_server") or "smtp.qq.com"
                    port    = int(os.getenv("SMTP_PORT", "") or email_cfg.get("smtp_port") or 465)
                    user_env= os.getenv("SMTP_USER", "") or email_addr
                    user    = user_env or (email_cfg.get("smtp_user") or sender)
                    pass_env= email_cfg.get("smtp_pass_env") or "SMTP_PASS"
                    passwd  = os.getenv(pass_env, "")
                    subject = email_cfg.get("subject") or "[arXiv] Digest"
                    tls_mode= email_cfg.get("tls", "auto")
                    debug   = bool(email_cfg.get("debug", False))
                    detail  = email_cfg.get("detail", "full")
                    max_items = int(email_cfg.get("max_items", 50))

                    to_list = _dedup_addrs(to_list)

                    if not (to_list and sender and passwd):
                        click.secho("[Email] 配置不完整，跳过发送（需要 EMAIL_TO / EMAIL_SENDER / SMTP_PASS）", fg="yellow")
                    else:
                        html_body = ""
                        if page_url:
                            html_body += f'<div style="margin-bottom:10px">Web 版：<a href="{page_url}">{page_url}</a></div>'
                        if not items:
                            html_body += "<p>本周暂无新增命中。</p>"
                        else:
                            html_body += render_email_html(
                                items=items, lang=lang, translations=translations,
                                summaries_zh=summaries_zh, summaries_en=summaries_en,
                                detail=detail, max_items=max_items,
                                title=subject.replace("[arXiv]", "arXiv")
                            )
                        from .notify.mailer import send_email
                        attach = []
                        if email_cfg.get("attach_md", False) and md_path:
                            attach.append(md_path)

                        click.echo(f"[Email] will send: detail={detail} to={len(to_list)} recipient(s)")
                        send_email(
                            sender=sender, to_list=to_list, subject=subject, html_body=html_body,
                            smtp_server=server, smtp_port=port, smtp_user=user, smtp_pass=passwd,
                            tls_mode=tls_mode, attachments=attach, debug=debug, timeout=20
                        )
                        _SENT_EMAIL = True
                        email_sent = True
                        try:
                            flag_path.touch()
                        except Exception:
                            pass
                        click.echo("[Email] 已发送")
            except Exception as e:
                click.secho("[Email] 发送失败: {}".format(e), fg="red")

        # ── 12) 持久化去重状态 ──
        try:
            seen_ids = load_seen_ids(state_path) if unique_only and state_path else set()
            if unique_only and state_path and items and (site_generated or email_sent):
                all_seen = set(seen_ids)
                for it in items:
                    aid = it.get("id")
                    if aid:
                        all_seen.add(aid)
                save_seen_ids(state_path, all_seen)
                click.echo(f"[Freshness] 更新去重状态，共 {len(all_seen)} 条 -> {state_path}")
            elif unique_only and items:
                click.echo("[Freshness] 未写入去重状态（本次既未成功发邮件也未生成站点）")
        except Exception as e:
            click.secho(f"[Freshness] 保存去重状态失败: {e}", fg="yellow")

        if verbose:
            click.echo("[Run] Done")

    except Exception as e:
        click.secho("[Run] ERROR: {}".format(e), fg="red")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    cli()

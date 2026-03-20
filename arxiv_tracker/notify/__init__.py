# -*- coding: utf-8 -*-
"""
输出与通知：邮件发送、邮件模板、站点生成、JSON/MD 输出、PDF 导出。
"""
from .mailer import send_email
from .output import save_json, save_markdown
from .email_template import render_email_html

__all__ = [
    "send_email",
    "save_json",
    "save_markdown",
    "render_email_html",
]

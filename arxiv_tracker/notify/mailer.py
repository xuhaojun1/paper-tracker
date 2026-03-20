# -*- coding: utf-8 -*-
import os, smtplib, ssl, mimetypes
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional

def _attach_file(msg: MIMEMultipart, filepath: str):
    ctype, encoding = mimetypes.guess_type(filepath)
    if ctype is None or encoding is not None:
        ctype = "application/octet-stream"
    maintype, subtype = ctype.split("/", 1)
    with open(filepath, "rb") as f:
        part = MIMEBase(maintype, subtype)
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{os.path.basename(filepath)}"')
    msg.attach(part)

def _send_ssl(smtp_server, smtp_port, smtp_user, smtp_pass, msg, debug, timeout):
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context, timeout=timeout) as server:
        if debug: server.set_debuglevel(1)
        server.login(smtp_user, smtp_pass)
        server.sendmail(msg["From"], msg["To"].split(", "), msg.as_string())

def _send_starttls(smtp_server, smtp_port, smtp_user, smtp_pass, msg, debug, timeout):
    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_server, smtp_port, timeout=timeout) as server:
        if debug: server.set_debuglevel(1)
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(smtp_user, smtp_pass)
        server.sendmail(msg["From"], msg["To"].split(", "), msg.as_string())

def send_email(
    sender: str,
    to_list: List[str],
    subject: str,
    html_body: str,
    smtp_server: str,
    smtp_port: int,
    smtp_user: str,
    smtp_pass: str,
    tls_mode: str = "auto",              # "ssl" | "starttls" | "auto"
    attachments: Optional[List[str]] = None,
    debug: bool = False,
    timeout: int = 20,
):
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = ", ".join(to_list)
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    for fp in (attachments or []):
        if fp and os.path.exists(fp):
            _attach_file(msg, fp)

    # 发送逻辑
    if tls_mode == "ssl":
        _send_ssl(smtp_server, smtp_port, smtp_user, smtp_pass, msg, debug, timeout)
    elif tls_mode == "starttls":
        _send_starttls(smtp_server, smtp_port, smtp_user, smtp_pass, msg, debug, timeout)
    else:
        # auto: 先 SSL（465），失败则 STARTTLS（587）
        try:
            _send_ssl(smtp_server, smtp_port, smtp_user, smtp_pass, msg, debug, timeout)
        except Exception:
            alt_port = 587 if smtp_port == 465 else smtp_port
            _send_starttls(smtp_server, alt_port, smtp_user, smtp_pass, msg, debug, timeout)

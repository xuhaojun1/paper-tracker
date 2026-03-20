# -*- coding: utf-8 -*-
"""
统一日志模块：替代 pipeline 中散落的 click.echo / click.secho。
cli.py 启动时调用 setup_logging() 配置输出方式。
"""
import logging

_logger = logging.getLogger("arxiv_tracker")

# 默认 handler（避免 "No handlers" 警告）
if not _logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("[%(levelname).1s] %(message)s"))
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)


def setup_logging(verbose: bool = False):
    """由 cli.py 在启动时调用，配置日志级别"""
    _logger.setLevel(logging.DEBUG if verbose else logging.INFO)


def log_info(msg: str):
    _logger.info(msg)


def log_warn(msg: str):
    _logger.warning(msg)


def log_error(msg: str):
    _logger.error(msg)


def log_debug(msg: str):
    _logger.debug(msg)

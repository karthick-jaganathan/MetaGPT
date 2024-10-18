#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2023/6/1 12:41
@Author  : alexanderwu
@File    : logs.py
"""
import sys
import os
from datetime import datetime
from loguru import logger as _logger
from metagpt.const import METAGPT_ROOT

_print_level = "INFO"

# Custom format for logging
# LOG_FORMAT = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
LOG_FORMAT = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <level>{message}</level>"


def define_log_level(print_level="INFO", logfile_level="DEBUG", name: str = None):
    """Adjust the log level to above level"""
    global _print_level
    _print_level = print_level

    current_date = datetime.now()
    formatted_date = current_date.strftime("%Y%m%d")
    log_name = f"{name}_{formatted_date}" if name else formatted_date  # name a log with prefix name

    _logger.remove()

    # Add stderr log with custom format
    _logger.add(sys.stderr, level=print_level, format=LOG_FORMAT)

    # Add file log with custom format
    _logger.add(METAGPT_ROOT / f"logs/{log_name}.txt", level=logfile_level, format=LOG_FORMAT)

    return _logger


logger = define_log_level(os.environ.get("LOG_LEVEL", "INFO"))


def log_llm_stream(msg):
    _llm_stream_log(msg)


def set_llm_stream_logfunc(func):
    global _llm_stream_log
    _llm_stream_log = func


LOG_LLM_OUTPUT = os.environ.get("LOG_LLM_OUTPUT") == "1"


def _llm_stream_log(msg):
    if LOG_LLM_OUTPUT:
        print(msg, end="")

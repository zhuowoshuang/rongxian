# -*- coding: utf-8 -*-
"""
统一数据状态枚举 —— 与 frontend_contract/stock-data-types.ts 完全一致

OK:       数据完整，可直接使用
PARTIAL:  部分字段缺失，已尽力补齐
EMPTY:    数据源无此数据
ERROR:    接口调用失败
"""

from enum import Enum


class DataStatus(str, Enum):
    OK = "OK"
    PARTIAL = "PARTIAL"
    EMPTY = "EMPTY"
    ERROR = "ERROR"

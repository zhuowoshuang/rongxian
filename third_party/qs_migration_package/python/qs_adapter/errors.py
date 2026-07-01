# -*- coding: utf-8 -*-
"""
清数智算适配层异常类型

所有适配器抛出的异常均继承自 QSAdapterError，
方便清数智算 backend 统一捕获。
"""


class QSAdapterError(Exception):
    """适配层基础异常"""
    pass


class DataNotAvailableError(QSAdapterError):
    """数据不可用（接口返回空或网络超时）"""
    pass


class NormalizationError(QSAdapterError):
    """字段归一化失败（格式异常、类型错误等）"""
    pass

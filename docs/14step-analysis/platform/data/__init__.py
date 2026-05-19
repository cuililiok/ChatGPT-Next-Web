"""
数据层

包含：
  - provider: 数据提供者接口
  - akshare_provider: AKShare 数据提供者
  - sina_provider: 新浪数据提供者
  - cache: 数据缓存
  - validator: 数据验证
"""

from .provider import DataProvider
from .cache import DataCache
from .validator import DataValidator

# 条件导入：akshare 不一定安装
try:
    from .akshare_provider import AKShareProvider
except ImportError:
    AKShareProvider = None

try:
    from .sina_provider import SinaProvider
except ImportError:
    SinaProvider = None

__all__ = [
    'DataProvider',
    'AKShareProvider',
    'SinaProvider',
    'DataCache',
    'DataValidator'
]

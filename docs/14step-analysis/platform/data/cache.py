"""
数据缓存

提供数据缓存功能，支持：
1. 文件缓存
2. 内存缓存
3. 过期策略
4. 缓存清理
"""

import os
import json
import pickle
import hashlib
import logging
from pathlib import Path
from typing import Any, Optional, Dict
from datetime import datetime, timedelta
from dataclasses import dataclass
import threading

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: datetime
    expires_at: Optional[datetime]
    access_count: int = 0
    last_accessed: Optional[datetime] = None


class DataCache:
    """
    数据缓存管理器

    功能：
    1. 双层缓存（内存 + 文件）
    2. TTL 过期策略
    3. LRU 淘汰策略
    4. 缓存统计
    """

    def __init__(
        self,
        cache_dir: str = "~/.cache/investment-research",
        max_memory_items: int = 1000,
        default_ttl_hours: int = 24
    ):
        """
        初始化缓存管理器

        Args:
            cache_dir: 缓存目录
            max_memory_items: 内存缓存最大条目数
            default_ttl_hours: 默认 TTL（小时）
        """
        self.cache_dir = Path(cache_dir).expanduser()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.max_memory_items = max_memory_items
        self.default_ttl = timedelta(hours=default_ttl_hours)

        # 内存缓存
        self._memory_cache: Dict[str, CacheEntry] = {}
        self._lock = threading.Lock()

        # 统计
        self._stats = {
            "hits": 0,
            "misses": 0,
            "memory_hits": 0,
            "file_hits": 0,
            "writes": 0,
            "evictions": 0
        }

    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值，如果不存在或过期则返回 None
        """
        # 1. 检查内存缓存
        entry = self._memory_cache.get(key)
        if entry:
            if self._is_valid(entry):
                entry.access_count += 1
                entry.last_accessed = datetime.now()
                self._stats["hits"] += 1
                self._stats["memory_hits"] += 1
                return entry.value
            else:
                # 过期，删除
                del self._memory_cache[key]

        # 2. 检查文件缓存
        file_path = self._get_file_path(key)
        if file_path.exists():
            try:
                with open(file_path, 'rb') as f:
                    entry = pickle.load(f)

                if self._is_valid(entry):
                    # 加载到内存缓存
                    self._add_to_memory(key, entry)
                    entry.access_count += 1
                    entry.last_accessed = datetime.now()
                    self._stats["hits"] += 1
                    self._stats["file_hits"] += 1
                    return entry.value
                else:
                    # 过期，删除文件
                    file_path.unlink()
            except Exception as e:
                logger.warning(f"读取缓存文件失败: {e}")

        self._stats["misses"] += 1
        return None

    def set(
        self,
        key: str,
        value: Any,
        ttl_hours: Optional[float] = None
    ):
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl_hours: TTL（小时），None 使用默认值
        """
        ttl = timedelta(hours=ttl_hours) if ttl_hours else self.default_ttl

        entry = CacheEntry(
            key=key,
            value=value,
            created_at=datetime.now(),
            expires_at=datetime.now() + ttl
        )

        # 1. 添加到内存缓存
        self._add_to_memory(key, entry)

        # 2. 写入文件缓存
        try:
            file_path = self._get_file_path(key)
            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, 'wb') as f:
                pickle.dump(entry, f)

            self._stats["writes"] += 1
        except Exception as e:
            logger.warning(f"写入缓存文件失败: {e}")

    def delete(self, key: str):
        """
        删除缓存

        Args:
            key: 缓存键
        """
        # 从内存删除
        self._memory_cache.pop(key, None)

        # 从文件删除
        file_path = self._get_file_path(key)
        if file_path.exists():
            file_path.unlink()

    def clear(self, older_than_hours: Optional[int] = None):
        """
        清理缓存

        Args:
            older_than_hours: 清理多少小时前的缓存，None 清理全部
        """
        # 清理内存缓存
        if older_than_hours:
            cutoff = datetime.now() - timedelta(hours=older_than_hours)
            keys_to_delete = [
                k for k, v in self._memory_cache.items()
                if v.created_at < cutoff
            ]
        else:
            keys_to_delete = list(self._memory_cache.keys())

        for key in keys_to_delete:
            del self._memory_cache[key]

        # 清理文件缓存
        for file_path in self.cache_dir.rglob("*.cache"):
            try:
                if older_than_hours:
                    file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    cutoff = datetime.now() - timedelta(hours=older_than_hours)
                    if file_time < cutoff:
                        file_path.unlink()
                else:
                    file_path.unlink()
            except Exception as e:
                logger.warning(f"删除缓存文件失败: {e}")

        logger.info(f"已清理缓存: {len(keys_to_delete)} 个条目")

    def _add_to_memory(self, key: str, entry: CacheEntry):
        """添加到内存缓存"""
        with self._lock:
            # 如果达到上限，淘汰最久未访问的
            if len(self._memory_cache) >= self.max_memory_items:
                self._evict_lru()

            self._memory_cache[key] = entry

    def _evict_lru(self):
        """淘汰最久未访问的条目"""
        if not self._memory_cache:
            return

        # 按最后访问时间排序
        sorted_keys = sorted(
            self._memory_cache.keys(),
            key=lambda k: self._memory_cache[k].last_accessed or self._memory_cache[k].created_at
        )

        # 淘汰最旧的 10%
        evict_count = max(1, len(sorted_keys) // 10)
        for key in sorted_keys[:evict_count]:
            del self._memory_cache[key]
            self._stats["evictions"] += 1

    def _is_valid(self, entry: CacheEntry) -> bool:
        """检查缓存条目是否有效"""
        if entry.expires_at and datetime.now() > entry.expires_at:
            return False
        return True

    def _get_file_path(self, key: str) -> Path:
        """获取缓存文件路径"""
        # 使用 key 的 hash 作为文件名
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.cache"

    def generate_key(self, *args, **kwargs) -> str:
        """
        生成缓存键

        Args:
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            缓存键
        """
        key_parts = [str(arg) for arg in args]
        key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
        key_str = "|".join(key_parts)
        return hashlib.md5(key_str.encode()).hexdigest()

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计

        Returns:
            统计信息
        """
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total_requests if total_requests > 0 else 0

        return {
            "memory_items": len(self._memory_cache),
            "total_requests": total_requests,
            "hit_rate": f"{hit_rate:.1%}",
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "memory_hits": self._stats["memory_hits"],
            "file_hits": self._stats["file_hits"],
            "writes": self._stats["writes"],
            "evictions": self._stats["evictions"]
        }

    def print_stats(self):
        """打印缓存统计"""
        stats = self.get_stats()
        print("\n" + "=" * 40)
        print("缓存统计")
        print("=" * 40)
        for key, value in stats.items():
            print(f"{key}: {value}")
        print("=" * 40)


class MemoryCache:
    """
    纯内存缓存

    适用于临时数据或不需要持久化的场景。
    """

    def __init__(self, max_items: int = 100):
        """
        初始化内存缓存

        Args:
            max_items: 最大条目数
        """
        self.max_items = max_items
        self._cache: Dict[str, Any] = {}
        self._access_order: list = []

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        if key in self._cache:
            # 更新访问顺序
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
            return self._cache[key]
        return None

    def set(self, key: str, value: Any):
        """设置缓存值"""
        if len(self._cache) >= self.max_items:
            # 淘汰最久未访问的
            oldest_key = self._access_order.pop(0)
            del self._cache[oldest_key]

        self._cache[key] = value
        if key not in self._access_order:
            self._access_order.append(key)

    def delete(self, key: str):
        """删除缓存"""
        self._cache.pop(key, None)
        if key in self._access_order:
            self._access_order.remove(key)

    def clear(self):
        """清空缓存"""
        self._cache.clear()
        self._access_order.clear()

    def __len__(self):
        return len(self._cache)

    def __contains__(self, key: str):
        return key in self._cache

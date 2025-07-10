from cachetools import LRUCache
from cachetools import TLRUCache

import threading
from src.common.logger_handler import logger

# 缓存用户最近会话
# 创建一个线程安全的 LRU 缓存，最大容量为 500
lru_cache = LRUCache(maxsize=500)
# 创建一个线程锁
lru_lock = threading.Lock()


def get_conversation_id_lru(key_id, conversation_id):
    """
    该函数使用 LRU 缓存获取用户信息
    :param user_id: 用户 ID
    :return: 用户信息
    """
    with lru_lock:
        if key_id in lru_cache:
            logger.info(f"从 LRU 缓存中获取用户 {key_id} 的信息")
            return lru_cache[key_id]
        else:
            if len(conversation_id) != 0:
                lru_cache[key_id] = conversation_id
                logger.info(f"第一次缓存 {key_id} {conversation_id} 的信息")
            return ""


def del_conversation_id_lru(key_id):
    with lru_lock:
        if key_id in lru_cache:
            logger.info(f"从 LRU 缓存中删除用户 {key_id} 的信息")
            del lru_cache[key_id]


class GlobalVars:
    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            # Dify 相关配置;
            cls._instance.dify_api_url = "http://172.20.22.43/v1"
            cls._instance.dify_api_token = "app-iZRWkNMmWaAdoBTehffXRSWp"
            # 群中@昵称
            cls._instance._self_nickname = "高新成"
        return cls._instance

    def get_dify_api_url(self):
        return self.dify_api_url

    def get_dify_api_token(self):
        return self.dify_api_token

    def get_self_nickname(self):
        return self._self_nickname

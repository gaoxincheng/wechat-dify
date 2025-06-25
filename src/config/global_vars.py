from cachetools import LRUCache
import threading
from src.common.logger_handler import logger

# 缓存用户最近会话
# 创建一个线程安全的 LRU 缓存，最大容量为 500
lru_cache = LRUCache(maxsize=500)
# 创建一个线程锁
lru_lock = threading.Lock()


def get_conversation_id_lru(openid, conversation_id):
    """
    该函数使用 LRU 缓存获取用户信息
    :param user_id: 用户 ID
    :return: 用户信息
    """
    with lru_lock:
        if openid in lru_cache:
            logger.info(f"从 LRU 缓存中获取用户 {openid} 的信息")
            return lru_cache[openid]
        else:
            if len(conversation_id) != 0:
                lru_cache[openid] = conversation_id
                logger.info(f"第一次缓存 {openid} {conversation_id} 的信息")
            return ""


class GlobalVars:
    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            # Dify 相关配置;
            cls._instance.dify_api_url = "http://172.20.22.43/v1"
            cls._instance.dify_api_token = ""
        return cls._instance

    def get_dify_api_url(self):
        return self.dify_api_url

    def get_dify_api_token(self):
        return self.dify_api_token

import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional
import requests
from src.config.global_vars import (
    GlobalVars,
    del_conversation_id_lru,
    get_conversation_id_lru,
)
from src.common.utils import remove_at_info, remove_tags_regex
from src.common.logger_handler import logger


class HTTPRequest:
    """HTTP请求对象，封装请求参数"""

    def __init__(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 120,
        request_id: Optional[str] = None,
    ):
        self.method = method
        self.url = url
        self.params = params
        self.data = data
        self.json = json
        self.headers = headers
        self.timeout = timeout
        self.request_id = request_id or f"req-{id(self)}"


class HTTPResponse:
    """HTTP响应对象，封装响应结果"""

    def __init__(
        self,
        request_id: str,
        success: bool,
        status_code: Optional[int] = None,
        content: Optional[Any] = None,
        error: Optional[str] = None,
    ):
        self.request_id = request_id
        self.success = success
        self.status_code = status_code
        self.content = content
        self.error = error


class HTTPRequestHandler:
    """HTTP请求处理器，负责执行实际请求"""

    def process(self, request: HTTPRequest) -> HTTPResponse:
        try:
            logger.info(f"开始Dify请求: {request.request_id}")
            response = requests.request(
                method=request.method,
                url=request.url,
                params=request.params,
                data=request.data,
                json=request.json,
                headers=request.headers,
                timeout=request.timeout,
            )
            response.raise_for_status()  # 检查状态码
            return HTTPResponse(
                request_id=request.request_id,
                success=True,
                status_code=response.status_code,
                content=(
                    response.json()
                    if response.headers.get("Content-Type") == "application/json"
                    else response.text
                ),
            )
        except Exception as e:
            return HTTPResponse(
                request_id=request.request_id, success=False, error=str(e)
            )


class QueueMsg:
    """HTTP响应对象，封装响应结果"""

    def __init__(self, http_response: HTTPResponse, session_name: str, sender: str):
        self.http_response = http_response
        self.session_name = session_name
        self.sender = sender


class HTTPRequestManager:
    """HTTP请求管理器，协调线程池和结果队列"""

    def __init__(self, max_workers: int = 5):
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        self.response_queue = queue.Queue()  # 存储HTTP响应的队列
        self.handler = HTTPRequestHandler()
        self._shutdown_event = threading.Event()

    def submit_request(
        self, request: HTTPRequest, session_name: str, sender: str
    ) -> None:
        """提交HTTP请求到线程池"""
        if self._shutdown_event.is_set():
            raise RuntimeError("Request manager is shut down")

        future = self.thread_pool.submit(self.handler.process, request)
        future.add_done_callback(
            lambda f: self._handle_result(f, request.request_id, session_name, sender)
        )

    def _handle_result(
        self, future, request_id: str, session_name: str, sender: str
    ) -> None:
        """处理请求结果并放入响应队列"""
        try:
            logger.info(f"完成Dify请求: {request_id}")
            response = future.result()
            self.response_queue.put(QueueMsg(response, session_name, sender))
        except Exception as e:
            logger.info(f"Dify请求返回处理异常: {request_id}")
            self.response_queue.put(
                QueueMsg(
                    HTTPResponse(
                        request_id=request_id,
                        success=False,
                        error=f"Unexpected error: {str(e)}",
                    ),
                    session_name,
                    sender,
                )
            )

    def get_response(
        self, block: bool = True, timeout: Optional[float] = None
    ) -> Optional[HTTPResponse]:
        """从响应队列获取结果"""
        try:
            return self.response_queue.get(block=block, timeout=timeout)
        except queue.Empty:
            return None

    def shutdown(self, wait: bool = True) -> None:
        """关闭线程池"""
        self._shutdown_event.set()
        self.thread_pool.shutdown(wait=wait)


# 示例使用
# if __name__ == "__main__":
#     # 创建请求管理器（最多5个工作线程）
#     manager = HTTPRequestManager(max_workers=5)

#     # 提交多个HTTP请求
#     manager.submit_request(
#         HTTPRequest("GET", "https://jsonplaceholder.typicode.com/todos/1")
#     )
#     manager.submit_request(
#         HTTPRequest("GET", "https://jsonplaceholder.typicode.com/posts/1")
#     )
#     manager.submit_request(HTTPRequest("GET", "https://invalid-url-example.com"))

#     # 主线程从队列获取响应
#     while True:
#         queue_msg = manager.get_response(block=True, timeout=1)
#         if queue_msg:
#             print(f"收到响应 (ID: {queue_msg.http_response.request_id})")
#             if queue_msg.http_response.success:
#                 print(f"  状态码: {queue_msg.http_response.status_code}")
#                 print(f"  内容: {queue_msg.http_response.content[:50]}...")
#             else:
#                 print(f"  错误: {queue_msg.http_response.error}")

#         # 如果所有任务完成且队列为空，则退出
#         if manager.thread_pool._work_queue.empty() and manager.response_queue.empty():
#             break

#     # 关闭请求管理器
#     manager.shutdown()

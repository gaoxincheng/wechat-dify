import logging
import sys


class UnbufferedStreamHandler(logging.StreamHandler):
    def emit(self, record):
        super().emit(record)
        self.stream.flush()  # 强制刷新缓冲区


# 创建 Logger 对象
logger = logging.getLogger("console_logger")
logger.setLevel(logging.DEBUG)  # 设置最低日志级别为 DEBUG

# 创建 StreamHandler（默认输出到控制台）
stream_handler = UnbufferedStreamHandler(sys.stdout)

# 创建 Formatter，定义日志消息的格式
formatter = logging.Formatter(
    "%(asctime)s[%(thread)d][%(levelname)s] - %(message)s-%(filename)s -%(lineno)d"
)

# 将 Formatter 添加到 Handler
stream_handler.setFormatter(formatter)
# 将 Handler 添加到 Logger
logger.addHandler(stream_handler)

# 记录日志
# logger.debug('这是一个调试信息')
# logger.info('这是一个普通信息')
# logger.warning('这是一个警告信息')
# logger.error('这是一个错误信息')
# logger.critical('这是一个严重错误信息')

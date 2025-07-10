import sys
import os
import time
import signal

# 获取项目的根路径
project_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# 将项目根路径添加到sys.path
if project_path not in sys.path:
    sys.path.append(project_path)

from datetime import datetime
from wxauto.msgs import *
from wxauto.utils import *
from src.common.logger_handler import logger
from src.common.utils import ParseWeChatTime
from src.handler.wechat_handle import WXHandle, on_recv_message

# 可配置参数
CHECK_INTERVAL = 1  # 轮询间隔（秒）
LISTEN_FRIENDS = []  # 要监听的好友昵称列表
LISTEN_GROUPS = [
    # "群消息测试"
]  # 要监听的群列表
FILTER_SESSIONS = {
    "订阅号",
    "服务号",
    "服务通知",
    "小程序客服消息",
    "微信支付",
    "微信团队",
    "文件传输助手",
}  # 过滤的会话
SELF_NICKNAME = "B7"  # 自己在群中的昵称


def signal_handler(sig, frame):
    logger.info("\n程序已中断 (Ctrl+C)")
    # 执行清理操作（如关闭文件、释放资源）
    WXHandle().wx().StopListening()
    sys.exit(0)


# 注册信号处理函数
signal.signal(signal.SIGINT, signal_handler)


def restart():
    logger.info("Restarting program...")
    os.execv(sys.executable, [sys.executable] + sys.argv)  # 原地重启


def poll_messages() -> None:
    """轮询获取新消息"""
    while True:
        try:
            # 处理消息响应
            # logger.info(
            #     f"消息响应队列长度： {WXHandle().http_manager().response_queue.qsize()}"
            # )
            while not WXHandle().http_manager().response_queue.empty():
                queue_msg = (
                    WXHandle().http_manager().get_response(block=False, timeout=1)
                )
                WXHandle().handle_response(queue_msg)

            sessions = WXHandle().wx().GetSession()
            for session in sessions:
                if not session.time:
                    continue
                if not session.name:
                    continue
                if session.name in WXHandle().wx().listen:
                    continue
                time_str = ParseWeChatTime(session.time)
                if not time_str:
                    continue
                session_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                now = datetime.now()
                delta = now - session_time
                if delta.seconds > 60:
                    continue
                # 新会话消息处理
                logger.info(
                    f"检测到会话更新：{session.name} | {session.content} | {session.time} | {session.new_count}"
                )
                WXHandle().add_new_session(session.name)
            # 等待下一次轮询
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            logger.info(f"轮询异常：{str(e)}")
            time.sleep(5)  # 出错后延长等待时间
            restart()


def main_run() -> None:
    """主函数：初始化并启动轮询"""
    WXHandle().wx().SwitchToChat()

    logger.info(f"微信消息轮询监听已启动")
    logger.info(f"过滤会话：{FILTER_SESSIONS}")
    logger.info(f"目标好友：{LISTEN_FRIENDS}")
    logger.info(f"目标群：{LISTEN_GROUPS}")

    # 预先打开一次聊天窗口（可选）
    for friend in LISTEN_FRIENDS:
        try:
            WXHandle().wx().AddListenChat(nickname=friend, callback=on_recv_message)
            time.sleep(0.5)
            WXHandle().handle_chat_last_msg(who=friend)
            logger.info(f"监听 {friend} 的聊天窗口")
        except Exception as e:
            logger.info(f"打开 {friend} 聊天窗口失败：{str(e)}")
            # 切到会话页，防止搜索残留输入影响
            WXHandle().wx().SwitchToChat()

    for group in LISTEN_GROUPS:
        try:
            WXHandle().wx().AddListenChat(nickname=group, callback=on_recv_message)
            time.sleep(0.5)
            WXHandle().wx().handle_chat_last_msg(who=group)
            logger.info(f"监听 {group} 的群聊天窗口")
        except Exception as e:
            logger.info(f"打开 {group} 群聊天窗口失败：{str(e)}")
            # 切到会话页，防止搜索残留输入影响
            WXHandle().wx().SwitchToChat()

    time.sleep(1)

    # 启动轮询任务
    WXHandle().wx().StartListening()
    # WXHandle().wx().KeepRunning()
    poll_messages()


if __name__ == "__main__":
    # 确保微信已登录
    logger.info("请确保微信已登录并处于活动状态...")
    time.sleep(3)  # 等待3秒，给用户时间切换到微信

    # 启动异步事件循环
    try:
        main_run()
    except KeyboardInterrupt:
        WXHandle().wx().StopListening()
        logger.info("\n程序已停止")

import sys
import os

# 获取项目的根路径
project_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# 将项目根路径添加到sys.path
if project_path not in sys.path:
    sys.path.append(project_path)

from datetime import datetime
from wxauto import WeChat
import time
from src.handler.handle import wechat_msg_reply
from src.handler.handle import handle_message
from src.handler.handle import handle_group_message
from src.handler.handle import async_http_request
from src.common.logger_handler import logger
from src.common.sessions_manger import SessionManager
import asyncio

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

# 以下内容无需配置
MAIN_SESSIONS = []  # 当前面板会话
AUTO_LISTEN_SESSIONS = []  # 自动添加的会话
MAX_OPEN_SESSIONS = 4  # 最大打开会话数量

sessionManager = SessionManager()


def restart():
    logger.info("Restarting program...")
    os.execv(sys.executable, [sys.executable] + sys.argv)  # 原地重启


async def handle_chat_last_msg(wx: WeChat, who):
    chat = wx.listen[who]
    if not chat:
        return
    msgs = chat.GetAllMessage()
    if len(msgs) == 0:
        return

    for message in reversed(msgs):
        if message.type == "time":
            msg_time = datetime.strptime(message.time, "%Y-%m-%d %H:%M:%S")
            sessionManager.update_session(who, msg_time)
            now = datetime.now()
            delta = now - msg_time
            if delta.seconds > 60:
                logger.info(
                    f"会话不是最近的消息，最后一条消息时间：{msg_time}，当前时间 ：{now},时间差：{delta.seconds}秒"
                )
                return
    msg = msgs[-1]
    if msg.type != "friend":
        logger.info(f"会话最近一条消息不是来着好友的消息")
        return
    logger.info(f"处理新增会话最新消息： {who} 的消息 ：{msg.content} | {msg.info}")
    # 发送昵称与窗口一致则认为是单聊
    if msg.sender == who:
        asyncio.create_task(handle_message(chat.who, msg.content, chat))
    else:
        asyncio.create_task(
            handle_group_message(who, msg.sender, msg.content, chat, SELF_NICKNAME)
        )


async def poll_messages(wx: WeChat) -> None:
    """轮询获取新消息"""
    while True:
        try:
            await check_new_seesion(wx)
            # 获取当前聊天窗口的所有消息
            msgs = wx.GetListenMessage()
            for chat in msgs:
                who = chat.who
                logger.info(f"监听到来自 {who} 的消息")
                one_msgs = msgs.get(chat)  # 获取消息内容
                for msg in one_msgs:
                    if msg.type != "friend":
                        continue
                    sessionManager.update_session(who, datetime.now())
                    # 发送昵称与窗口一致则认为是单聊
                    if msg.sender == who:
                        asyncio.create_task(handle_message(chat.who, msg.content, chat))
                    else:
                        asyncio.create_task(
                            handle_group_message(
                                who, msg.sender, msg.content, chat, SELF_NICKNAME
                            )
                        )

            # 等待下一次轮询
            await asyncio.sleep(CHECK_INTERVAL)
        except Exception as e:
            logger.info(f"轮询异常：{str(e)}")
            restart()
            # await asyncio.sleep(5)  # 出错后延长等待时间


def get_friend_list(wx: WeChat):
    friends = wx.GetAllFriends()
    global count
    count = 0
    for friend in friends:
        try:
            count += 1
            logger.info(f"好友{count}: {friend} ")
            if friend["nickname"] in LISTEN_FRIENDS:
                continue
            LISTEN_FRIENDS.append(friend["nickname"])
            # wx.AddListenChat(who=friend["nickname"], savepic=False)
        except Exception as e:
            logger.info(f"好友 {friend} 信息输出失败：{str(e)}")


def check_new_friend(wx: WeChat):
    newFriendsList = wx.GetNewFriends()
    for friend in newFriendsList:
        try:
            logger.info(f"新好友申请: {friend} ")
            # LISTEN_FRIENDS.append(friend["nickname"])
            # wx.AddListenChat(who=friend["nickname"], savepic=False)
            # friend.Accept()
        except Exception as e:
            logger.info(f"好友 {friend} 信息输出失败：{str(e)}")


def get_session_list(wx: WeChat) -> list:
    sessions = wx.GetSession()
    session_names = [session.name for session in sessions if session.name]
    return session_names


async def close_session(wx: WeChat, session_name) -> bool:
    try:
        if session_name in wx.listen:
            chat = wx.listen[session_name]
            chat.UiaAPI.SendKeys("{Esc}")
            wx.RemoveListenChat(who=session_name)
            sessionManager.remove_session(session_name)
            logger.info(f"关闭会话：{session_name}")
            return True
    except Exception as e:
        logger.info(f"关闭会话失败：{str(e)}")
    return False


async def check_session_count(wx: WeChat):
    global AUTO_LISTEN_SESSIONS
    cur_listen_count = len(wx.listen)
    if cur_listen_count < MAX_OPEN_SESSIONS:
        return

    while True:
        oldest_id, oldest_time = sessionManager.get_oldest_session()
        if not oldest_id:
            break
        ok = await close_session(wx, oldest_id)
        sessionManager.remove_session(oldest_id)
        if ok:
            AUTO_LISTEN_SESSIONS.remove(oldest_id)
            break


async def check_new_seesion(wx):
    global MAIN_SESSIONS
    global AUTO_LISTEN_SESSIONS
    global FILTER_SESSIONS
    cur_sessions = get_session_list(wx)
    diff_sessions = [x for x in cur_sessions if x not in MAIN_SESSIONS]
    # if len(diff_sessions) > 0:
    #     logger.info(f"当前会话列表：{cur_sessions}")
    #     logger.info(f"上次会话列表：{MAIN_SESSIONS}")
    #     logger.info(f"新增会话列表：{diff_sessions}")

    new_session_list = []
    failed_list = []
    for session in diff_sessions:
        try:
            # logger.info(f"会话: {session.name} | {session.content} | {session.isnew}")
            if (
                session
                and session not in FILTER_SESSIONS
                and session not in LISTEN_FRIENDS
                and session not in LISTEN_GROUPS
                and session not in AUTO_LISTEN_SESSIONS
            ):
                # logger.info(f"新的会话: {session} ")
                new_session_list.append(session)
        except Exception as e:
            logger.info(f"会话 {session} 信息输出失败：{str(e)}")
    if len(new_session_list) > 0:
        logger.info(f"监听新增会话：{new_session_list}")
    else:
        return
    await check_session_count(wx)
    for session in reversed(new_session_list):
        try:
            wx.AddListenChat(who=session)
            chat = wx.ChatWith(session)
            if chat:
                await handle_chat_last_msg(wx, who=session)
                AUTO_LISTEN_SESSIONS.append(session)
        except Exception as e:
            logger.info(f"打开 {session} 会话失败：{str(e)}")
            # 切到会话页，防止搜索残留输入影响
            wx.SwitchToChat()
            new_session_list.remove(session)
            failed_list.append(session)
        await asyncio.sleep(1)
    # 更新当前会话,不包括失败的，下次继续尝试
    now_sessions = get_session_list(wx)
    MAIN_SESSIONS = [x for x in now_sessions if x not in failed_list]


def get_all_msgs(wx):
    msgs = wx.GetAllNewMessage()
    for msg in msgs:
        try:
            logger.info(f"消息: {msg}")
            # wx.AddListenChat(who=session.name, savepic=False)
        except Exception as e:
            logger.info(f"消息 {msg} 信息输出失败：{str(e)}")


async def main_async() -> None:
    global MAIN_SESSIONS
    """主函数：初始化并启动轮询"""
    wx = WeChat()
    # wx.B_Search.SendKeys("{Ctrl}a{Delete}", waitTime=1.5)
    wx.SwitchToChat()

    logger.info(f"微信消息轮询监听已启动")
    logger.info(f"目标好友：{LISTEN_FRIENDS}")
    logger.info(f"目标群：{LISTEN_GROUPS}")

    # 预先打开一次聊天窗口（可选）
    for friend in LISTEN_FRIENDS:
        try:
            wx.AddListenChat(who=friend, savepic=False)
            wx.ChatWith(friend)
            await asyncio.sleep(0.5)
            await handle_chat_last_msg(wx, who=friend)
            logger.info(f"监听 {friend} 的聊天窗口")
        except Exception as e:
            logger.info(f"打开 {friend} 聊天窗口失败：{str(e)}")
            # 切到会话页，防止搜索残留输入影响
            wx.SwitchToChat()

    for group in LISTEN_GROUPS:
        try:
            wx.AddListenChat(who=group)
            wx.ChatWith(group)
            await asyncio.sleep(0.5)
            await handle_chat_last_msg(wx, who=group)
            logger.info(f"监听 {group} 的群聊天窗口")
        except Exception as e:
            logger.info(f"打开 {group} 群聊天窗口失败：{str(e)}")
            # 切到会话页，防止搜索残留输入影响
            wx.SwitchToChat()

    await check_new_seesion(wx)

    await asyncio.sleep(3)
    # 在会话列表变化后再调用
    # MAIN_SESSIONS = get_session_list(wx)
    logger.info(f"当前会话：{MAIN_SESSIONS}")

    # 启动轮询任务
    await poll_messages(wx)


if __name__ == "__main__":
    # 确保微信已登录
    logger.info("请确保微信已登录并处于活动状态...")
    time.sleep(3)  # 等待3秒，给用户时间切换到微信

    # 启动异步事件循环
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("\n程序已停止")

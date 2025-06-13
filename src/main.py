import sys
import os

# 获取项目的根路径
project_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# 将项目根路径添加到sys.path
if project_path not in sys.path:
    sys.path.append(project_path)

from wxauto import WeChat
import time
from src.handler.handle import wechat_msg_reply
from src.handler.handle import handle_message
from src.handler.handle import handle_group_message
from src.handler.handle import async_http_request
import asyncio

CHECK_INTERVAL = 1  # 轮询间隔（秒）
TARGET_FRIENDS = ["高新成"]  # 要监听的好友昵称列表
TARGET_GROUPS = ["群消息测试"]  # 要监听的群列表
SELF_NICKNAME = "B7"  # 自己在群中的昵称


async def poll_messages(wx) -> None:
    """轮询获取新消息"""
    while True:
        try:
            # 获取当前聊天窗口的所有消息
            msgs = wx.GetListenMessage()
            for chat in msgs:
                who = chat.who
                print(f"监听到来自 {who} 的消息")

                if who in TARGET_FRIENDS:
                    one_msgs = msgs.get(chat)  # 获取消息内容
                    for msg in one_msgs:
                        if msg.type == "friend":
                            asyncio.create_task(
                                handle_message(chat.who, msg.content, chat)
                            )
                if who in TARGET_GROUPS:
                    one_msgs = msgs.get(chat)  # 获取消息内容
                    for msg in one_msgs:
                        if msg.type == "friend":
                            asyncio.create_task(
                                handle_group_message(
                                    who, msg.sender, msg.content, chat, SELF_NICKNAME
                                )
                            )
            # 等待下一次轮询
            await asyncio.sleep(CHECK_INTERVAL)
        except Exception as e:
            print(f"轮询异常：{str(e)}")
            await asyncio.sleep(5)  # 出错后延长等待时间


def main():
    print("Hello from wechat-dify!")
    # 获取微信窗口对象
    wx = WeChat()
    # 输出 > 初始化成功，获取到已登录窗口：xxxx
    print(wx.VERSION)
    # 设置监听列表
    # 循环添加监听对象
    for i in TARGET_FRIENDS:
        wx.AddListenChat(who=i, savepic=True)

    # 持续监听消息，并且收到消息后回复“收到”
    wait = 1  # 设置1秒查看一次是否有新消息
    while True:
        msgs = wx.GetListenMessage()
        for chat in msgs:
            who = chat.who  # 获取聊天窗口名（人或群名）
            one_msgs = msgs.get(chat)  # 获取消息内容
            # 回复收到
            for msg in one_msgs:
                msgtype = msg.type  # 获取消息类型
                content = msg.content  # 获取消息内容，字符串类型的消息内容
                print(f"【{who}】：{content}")

                if msgtype == "friend":
                    wechat_msg_reply(msg, chat)  # 回复收到
        time.sleep(wait)


async def main_async() -> None:
    """主函数：初始化并启动轮询"""
    wx = WeChat()

    print(f"微信消息轮询监听已启动")
    print(f"目标好友：{TARGET_FRIENDS}")
    print(f"目标群：{TARGET_GROUPS}")
    # 预先打开一次聊天窗口（可选）
    for friend in TARGET_FRIENDS:
        try:
            wx.AddListenChat(who=friend, savepic=True)
            wx.ChatWith(friend)
            print(f"已打开 {friend} 的聊天窗口")
        except Exception as e:
            print(f"打开 {friend} 聊天窗口失败：{str(e)}")

    for group in TARGET_GROUPS:
        try:
            wx.AddListenChat(who=group)
            wx.ChatWith(group)
            print(f"已打开 {group} 的群聊天窗口")
        except Exception as e:
            print(f"打开 {group} 群聊天窗口失败：{str(e)}")
    # 启动轮询任务
    await poll_messages(wx)


if __name__ == "__main__":

    # 确保微信已登录
    print("请确保微信已登录并处于活动状态...")
    time.sleep(3)  # 等待3秒，给用户时间切换到微信

    # 启动异步事件循环
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n程序已停止")
    # main()

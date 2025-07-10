from wxauto import WeChat
from wxauto import Chat
from wxauto.msgs import *
from wxauto.utils import *

from datetime import datetime
from src.common.sessions_manger import SessionManager
from src.common.logger_handler import logger
from src.handler.http_manager import (
    HTTPRequestManager,
    HTTPRequest,
    QueueMsg,
)
from src.common.utils import remove_at_info, remove_tags_regex
from src.config.global_vars import (
    GlobalVars,
    del_conversation_id_lru,
    get_conversation_id_lru,
)


MAX_OPEN_SESSIONS = 4  # 最大打开会话数量


def on_recv_message(msg, chat: Chat):
    if not isinstance(msg, FriendMessage):
        return
    logger.info(f"收到消息 {chat.who}：{msg}")
    WXHandle().handle_recv_message(msg, chat)


class WXHandle:
    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            # WeChat 相关配置;
            cls._instance._wx = WeChat()
            cls._instance._sessionManager = SessionManager()
            cls._instance._http_manager = HTTPRequestManager(max_workers=5)
        return cls._instance

    def wx(self) -> WeChat:
        return self._wx

    def http_manager(self):
        return self._http_manager

    def handle_chat_last_msg(self, who: str, check_time=True):
        chat, _ = self._wx.listen[who]
        if not chat:
            return
        msgs = chat.GetAllMessage()
        if len(msgs) == 0:
            return
        if check_time:
            for message in reversed(msgs):
                if isinstance(message, TimeMessage):
                    msg_time = datetime.strptime(message.time, "%Y-%m-%d %H:%M:%S")
                    self._sessionManager.update_session(who, msg_time)
                    now = datetime.now()
                    delta = now - msg_time
                    if delta.seconds > 60:
                        logger.info(
                            f"会话不是最近的消息，最后一条消息时间：{msg_time}，当前时间 ：{now},时间差：{delta.seconds}秒"
                        )
                        return
        msg = msgs[-1]
        if not isinstance(msg, FriendMessage):
            logger.info(f"会话最近一条消息不是来着好友的消息")
            return
        logger.info(f"处理新增会话最新消息： {who} 的消息 ：{msg.content}")
        self.handle_recv_message(msg, chat)

    def handle_response(self, msg: QueueMsg):
        try:
            if not msg:
                return
            if not msg.http_response:
                return
            data = msg.http_response.content
            answer = ""
            if msg.http_response.status_code == 200:
                answer = remove_tags_regex(data["answer"], ["think", "details"]).strip()
                logger.info(
                    f"{msg.session_name}.{msg.sender} ->请求dify_chat成功 : {datetime.now()}"
                )
                get_conversation_id_lru(msg.sender, data["conversation_id"])
            elif msg.http_response.status_code == 404:
                logger.info(
                    f"请求失败,请稍后再试，状态码: {msg.http_response.status_code},{msg.http_response.error}"
                )
                del_conversation_id_lru(msg.sender)
                answer = f"请求失败,请稍后再试，状态码: {msg.http_response.status_code}，msg: {msg.http_response.error}"
            else:
                logger.info(
                    f"请求失败,请稍后再试，状态码: {msg.http_response.status_code},{msg.http_response.error}"
                )
                answer = f"请求失败,请稍后再试，状态码: {msg.http_response.status_code}，msg: {msg.http_response.error}"
            if msg.session_name == msg.sender:
                self._wx.SendMsg(answer, msg.session_name)
            else:
                self._wx.SendMsg(answer, msg.session_name, at=msg.sender)
        except Exception as e:
            logger.info(f"处理消息失败：{str(e)}")

    def add_new_session(self, session_name):
        self.check_session_count()
        if self._wx.AddListenChat(nickname=session_name, callback=on_recv_message):
            time.sleep(1)
            self.handle_chat_last_msg(who=session_name, check_time=False)

    def handle_recv_message(self, msg, chat: Chat):
        self._sessionManager.update_session(chat.who, datetime.now())
        headers = {
            "Authorization": f"Bearer {GlobalVars().get_dify_api_token()}",
            "Content-Type": "application/json",
        }
        # 发送昵称与窗口一致则认为是单聊
        if msg.sender == chat.who:
            data = {
                "inputs": {},
                "query": remove_at_info(msg.content),
                "response_mode": "blocking",
                "conversation_id": f"{get_conversation_id_lru(chat.who,'')}",
                "user": chat.who,
            }
            self._http_manager.submit_request(
                HTTPRequest(
                    "POST",
                    f"{GlobalVars().get_dify_api_url()}/chat-messages",
                    json=data,
                    headers=headers,
                ),
                session_name=chat.who,
                sender=msg.sender,
            )
        else:
            if f"@{GlobalVars().get_self_nickname()}" not in msg.content:
                logger.info(f"非@{GlobalVars().get_self_nickname()} 的群消息不处理")
                return
            data = {
                "inputs": {},
                "query": remove_at_info(msg.content),
                "response_mode": "blocking",
                "conversation_id": f"{get_conversation_id_lru(f"{chat.who}.{msg.sender}",'')}",
                "user": msg.sender,
            }
            self._http_manager.submit_request(
                HTTPRequest(
                    "POST",
                    f"{GlobalVars().get_dify_api_url()}/chat-messages",
                    json=data,
                    headers=headers,
                ),
                session_name=chat.who,
                sender=msg.sender,
            )
        logger.info(f"消息已投递 {chat.who}：{msg.content}")

    def close_session(self, session_name) -> bool:
        try:
            ok = self._wx.RemoveListenChat(nickname=session_name, close_window=True)
            self._sessionManager.remove_session(session_name)
            logger.info(f"关闭会话：{session_name}")
            return ok
        except Exception as e:
            logger.info(f"关闭会话 {session_name} 失败：{str(e)}")
        return False

    def check_session_count(self):
        cur_listen_count = len(self._wx.listen)
        if cur_listen_count < MAX_OPEN_SESSIONS:
            return

        while True:
            oldest_id, oldest_time = self._sessionManager.get_oldest_session()
            if not oldest_id:
                break
            ok = self.close_session(oldest_id)
            self._sessionManager.remove_session(oldest_id)
            if ok:
                break

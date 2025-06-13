# -*- coding: utf-8 -*-
# filename: handle.py

import requests
import datetime
import asyncio
import re
from wxauto import WeChat
import aiohttp
import time
from src.config.global_vars import GlobalVars
from src.config.global_vars import get_conversation_id_lru


def remove_tags_regex(xml_str, tags):
    """删除指定标签及其内容（正则实现）"""
    for tag in tags:
        # 匹配开始标签<tag>到结束标签</tag>的所有内容
        pattern = re.compile(rf"<{tag}[^>]*?>.*?</{tag}>", re.DOTALL)
        xml_str = pattern.sub("", xml_str)
    return xml_str


def remove_at_info(text):
    """剔除字符串中的@用户名信息"""
    # 匹配@后面跟随任意非空白字符（直到遇到空格或结束）
    pattern = r"@\S+\s?"
    return re.sub(pattern, "", text).strip()


def request_dify_chat(open_id, from_user_name, question):
    url = f"{GlobalVars().get_dify_api_url()}/chat-messages"
    headers = {
        "Authorization": f"Bearer {GlobalVars().get_dify_api_token()}",
        "Content-Type": "application/json",
    }
    data = {
        "inputs": {},
        "query": f"{question}",
        "response_mode": "blocking",
        "conversation_id": f"{get_conversation_id_lru(open_id,'')}",
        "user": f"{from_user_name}",
    }
    try:
        print(f"dify_chat url : {url}")
        response = requests.post(url, json=data, headers=headers)
        # print(f"dify_chat response : {response.text}")
        if response.status_code == 200:
            data = response.json()
            print(f"请求dify_chat成功 : {data},{datetime.datetime.now()}")
            get_conversation_id_lru(open_id, data["conversation_id"])
            return remove_tags_regex(data["answer"], ["think", "details"])
        else:
            print(f"请求失败，状态码: {response.status_code}")
            return f"请求失败，状态码: {response.status_code}"
    except requests.RequestException as e:
        print(f"请求发生错误: {e}")
        return f"请求发生错误: {e}"


def wechat_msg_reply(msg, chat):
    response = request_dify_chat(msg.sender, msg.sender, msg.content)
    chat.SendMsg(response)


async def async_http_request(conversation_id, from_user_name, question):
    """异步HTTP请求函数"""
    timeout = aiohttp.ClientTimeout(total=60)
    headers = {
        "Authorization": f"Bearer {GlobalVars().get_dify_api_token()}",
        "Content-Type": "application/json",
    }
    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
        try:
            url = f"{GlobalVars().get_dify_api_url()}/chat-messages"

            data = {
                "inputs": {},
                "query": f"{question}",
                "response_mode": "blocking",
                "conversation_id": f"{get_conversation_id_lru(conversation_id,'')}",
                "user": f"{from_user_name}",
            }
            print(f"开始请求Dify.....")
            # 此处需用‘json’字段接收数据，否则报400；
            async with session.post(url, json=data) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"请求dify_chat成功 : {data},{datetime.datetime.now()}")
                    get_conversation_id_lru(conversation_id, data["conversation_id"])
                    return remove_tags_regex(data["answer"], ["think", "details"])
                else:
                    print(f"请求失败，状态码: {response.status},{response.reason}")
                    return f"请求失败，状态码: {response.status}"
            # return await response.text()
        except Exception as e:
            print(f"HTTP请求失败: {str(e)}")
            return "网络请求失败，请稍后再试"


async def handle_message(sender, content, chat):
    """异步消息处理函数"""
    # sender = chat.who
    # content = msg.content
    print(f"收到好友[{sender}]的消息: {content}")

    # 发起异步HTTP请求
    response_text = await async_http_request(sender, sender, remove_at_info(content))

    # 异步回复消息（确保在wxauto允许的线程中执行）
    try:
        # msg.quote(reply_message)
        chat.SendMsg(response_text.strip())
        print(f"已回复[{sender}]: {response_text.strip()}")
    except Exception as e:
        print(f"回复好友消息失败: {str(e)}")


async def handle_group_message(group, sender, content, chat, self_nickname):
    """异步消息处理函数"""
    # sender = chat.who
    # content = msg.content
    print(f"收到群[{group}][{sender}]的消息: {content}")
    if f"@{self_nickname}" not in content:
        print(f"非@{self_nickname}的群消息不处理")
        return
    # 发起异步HTTP请求
    response_text = await async_http_request(
        f"{group}.{sender}", sender, remove_at_info(content)
    )

    # 异步回复消息（确保在wxauto允许的线程中执行）
    try:
        # msg.quote(reply_message)
        chat.SendMsg(msg=f" {response_text.strip()}", at=sender)
        print(f"已回复[{sender}]: {response_text.strip()}")
    except Exception as e:
        print(f"回复群消息失败: {str(e)}")


def sync_callback_wrapper(msg, chat):
    """同步回调包装器，用于兼容wxauto的同步回调机制"""
    asyncio.run_coroutine_threadsafe(
        handle_message(msg, chat), asyncio.get_event_loop()
    )

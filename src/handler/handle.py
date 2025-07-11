# -*- coding: utf-8 -*-
# filename: handle.py

import datetime
import asyncio
import re
from wxauto import WeChat
import aiohttp

from src.config.global_vars import (
    GlobalVars,
    del_conversation_id_lru,
    get_conversation_id_lru,
)
from src.common.logger_handler import logger


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
                "query": question,
                "response_mode": "blocking",
                "conversation_id": f"{get_conversation_id_lru(conversation_id,'')}",
                "user": from_user_name,
            }
            logger.info("开始请求Dify.....")
            # 此处需用‘json’字段接收数据，否则报400；
            async with session.post(url, json=data) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"请求dify_chat成功 : {datetime.datetime.now()}")
                    get_conversation_id_lru(conversation_id, data["conversation_id"])
                    return remove_tags_regex(data["answer"], ["think", "details"])
                elif response.status == 404:
                    logger.info(
                        f"请求失败,请稍后再试，状态码: {response.status},{response.reason}"
                    )
                    del_conversation_id_lru(conversation_id)
                    return f"请求失败,请稍后再试，状态码: {response.status}，msg: {response.reason}"
                else:
                    logger.info(
                        f"请求失败,请稍后再试，状态码: {response.status},{response.reason}"
                    )
                    return f"请求失败,请稍后再试，状态码: {response.status}，msg: {response.reason}"
        except Exception as e:
            logger.info(f"HTTP请求失败: {str(e)}")
            return "网络请求失败，请稍后再试"


async def handle_message(sender, content, wx: WeChat):
    """异步消息处理函数"""
    # sender = chat.who
    # content = msg.content
    logger.info(f"收到好友[{sender}]的消息: {content}")

    # 发起异步HTTP请求
    response_text = await async_http_request(sender, sender, remove_at_info(content))

    # 异步回复消息（确保在wxauto允许的线程中执行）
    try:
        # msg.quote(reply_message)
        wx.SendMsg(msg=response_text.strip(), who=sender)
        logger.info(f"已回复[{sender}]: {response_text.strip()}")
    except Exception as e:
        logger.info(f"回复好友消息失败: {str(e)}")


async def handle_group_message(group, sender, content, wx: WeChat, self_nickname):
    """异步消息处理函数"""
    # sender = chat.who
    # content = msg.content
    logger.info(f"收到群[{group}][{sender}]的消息: {content}")
    if f"@{self_nickname}" not in content:
        logger.info(f"非@{self_nickname}的群消息不处理")
        return
    # 发起异步HTTP请求
    response_text = await async_http_request(
        f"{group}.{sender}", sender, remove_at_info(content)
    )

    # 异步回复消息（确保在wxauto允许的线程中执行）
    try:
        # msg.quote(reply_message)
        wx.SendMsg(msg=f" {response_text.strip()}", who=group, at=sender)
        logger.info(f"已回复[{sender}]")
    except Exception as e:
        logger.info(f"回复群消息失败: {str(e)}")


def sync_callback_wrapper(msg, chat):
    """同步回调包装器，用于兼容wxauto的同步回调机制"""
    asyncio.run_coroutine_threadsafe(
        handle_message(msg, chat), asyncio.get_event_loop()
    )

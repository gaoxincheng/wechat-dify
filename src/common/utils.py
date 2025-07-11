from datetime import datetime, timedelta

import re


def ParseWeChatTime(time_str):
    """
    时间格式转换函数

    Args:
        time_str: 输入的时间字符串

    Returns:
        转换后的时间字符串
    """

    match = re.match(r"^(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})$", time_str)
    if match:
        month, day, hour, minute, second = match.groups()
        current_year = datetime.now().year
        return datetime(
            current_year, int(month), int(day), int(hour), int(minute), int(second)
        ).strftime("%Y-%m-%d %H:%M:%S")

    match = re.match(r"^(\d{1,2}):(\d{1,2})$", time_str)
    if match:
        hour, minute = match.groups()
        return datetime.now().strftime("%Y-%m-%d") + f" {hour}:{minute}:00"

    match = re.match(r"^昨天 (\d{1,2}):(\d{1,2})$", time_str)
    if match:
        hour, minute = match.groups()
        yesterday = datetime.now() - timedelta(days=1)
        return yesterday.strftime("%Y-%m-%d") + f" {hour}:{minute}:00"

    match = re.match(r"^昨天$", time_str)
    if match:
        yesterday = datetime.now() - timedelta(days=1)
        return yesterday.strftime("%Y-%m-%d") + " 00:00:00"

    match = re.match(r"^星期([一二三四五六日]) (\d{1,2}):(\d{1,2})$", time_str)
    if match:
        weekday, hour, minute = match.groups()
        weekday_num = ["一", "二", "三", "四", "五", "六", "日"].index(weekday)
        today_weekday = datetime.now().weekday()
        delta_days = (today_weekday - weekday_num) % 7
        target_day = datetime.now() - timedelta(days=delta_days)
        return target_day.strftime("%Y-%m-%d") + f" {hour}:{minute}:00"

    match = re.match(r"^星期([一二三四五六日])$", time_str)
    if match:
        weekday = match.group(1)
        weekday_num = ["一", "二", "三", "四", "五", "六", "日"].index(weekday)
        today_weekday = datetime.now().weekday()
        delta_days = (today_weekday - weekday_num) % 7
        target_day = datetime.now() - timedelta(days=delta_days)
        return target_day.strftime("%Y-%m-%d") + " 00:00:00"

    match = re.match(r"^(\d{4})年(\d{1,2})月(\d{1,2})日 (\d{1,2}):(\d{1,2})$", time_str)
    if match:
        year, month, day, hour, minute = match.groups()
        return datetime(*[int(i) for i in [year, month, day, hour, minute]]).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{1,2})$", time_str)
    if match:
        return (
            datetime.strptime(time_str, "%y/%m/%d").strftime("%Y-%m-%d") + " 00:00:00"
        )


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

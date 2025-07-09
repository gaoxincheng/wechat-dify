from datetime import datetime


class SessionManager:
    def __init__(self):
        self.session_map = {}

    def update_session(self, session_id, dt):
        self.session_map[session_id] = dt

    def get_oldest_session(self):
        """获取最早的会话ID和时间"""
        if not self.session_map:
            return None, None

        # 初始化最早时间为当前时间（最大可能值）
        oldest_time = datetime.now()
        oldest_id = None

        # 遍历查找最早的会话
        for sid, time in self.session_map.items():
            if time < oldest_time:
                oldest_time = time
                oldest_id = sid

        return oldest_id, oldest_time

    def remove_session(self, session_id):
        if session_id in self.session_map:
            del self.session_map[session_id]

    def clear_sessions(self):
        self.session_map.clear()

class Message:
    def __init__(self, msg: str, final_msg: bool = False):
        self.final_msg = final_msg
        self.msg = msg

    def final_msg(self) -> bool:
        return self.final_msg

    def get_body(self) -> str:
        return self.msg

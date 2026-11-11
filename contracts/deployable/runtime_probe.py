# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *

class RuntimeProbe(gl.Contract):
    owner: Address
    def __init__(self):
        self.owner = gl.message.sender_address

    @gl.public.view
    def get_runtime(self) -> dict:
        return {"owner": str(self.owner), "runner": "1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6"}

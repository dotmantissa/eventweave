# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
import json
import hashlib
from datetime import datetime, timezone

class StorageProbe(gl.Contract):
    owner: Address
    values: TreeMap[str, str]
    history: DynArray[str]
    count: u32

    def __init__(self):
        self.owner = gl.message.sender_address
        self.count = u32(0)

    @gl.public.view
    def get_state(self) -> dict:
        return {'owner': str(self.owner), 'count': int(self.count)}

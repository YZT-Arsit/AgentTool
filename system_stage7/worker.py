from __future__ import annotations

import os

from .durable_oram import CrashInjected,DurablePathORAM

def durable_oram_worker(root,domain,commands,results):
    oram=DurablePathORAM.open_existing(root,domain=domain)
    while True:
        command=commands.get()
        if command["op"]=="stop":return
        if command["op"]=="peek":results.put({"value":oram.peek(command["block_id"]),"pid":os.getpid()});continue
        try:
            oram.access(command["block_id"],command.get("operation","read"),command.get("value"),command.get("crash"));results.put({"status":"ok","pid":os.getpid()})
        except CrashInjected:
            os._exit(91)

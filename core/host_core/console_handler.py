import asyncio
import queue

from core.comms_core.proto.terminalez import terminalez_pb2
from core.host_core.runner import Runner


async def get_terminal_read(read_pipe: queue.Queue):
    while True:
        if read_pipe._qsize() > 0:
            data = read_pipe.get_nowait()
            read_pipe.task_done()
            return data
        await asyncio.sleep(0.5)

async def set_terminal_write(write_pipe: queue.Queue, data: str):
    if data is None:
        return False
    write_pipe.put_nowait(data)
    return True


class ConsoleHandler:
    def __init__(self, shells_output_queue: queue.Queue):
        self.number_of_terminals = 0
        self.terminals = dict()
        self.terminal_writes = dict()
        self.terminal_reads = dict()
        self.output_pipe = shells_output_queue


    def add_terminal(self,sid: int, terminal_path: str=""):
        runner = Runner()
        runner.create_terminal(terminal_path=terminal_path)
        self.terminal_writes[sid] = runner.get_write_pipe()
        self.terminal_reads[sid] = runner.get_read_pipe()

    # TODO: Implement sync process as well, refer sshx->runner->shell_task
    async def shell_task(self, sid: int, terminal_path: str=""):
        self.add_terminal(sid=sid, terminal_path=terminal_path)

        seq: int = 0

        while True:
            if self.terminal_reads.get(sid, None) is None:
                break
            done, pending = await asyncio.wait(asyncio.create_task(get_terminal_read(self.terminal_reads[sid]))
                         ,return_when=asyncio.ALL_COMPLETED)

            content = done.pop().result()

            seq += len(content)
            data = terminalez_pb2.TerminalOutput(shell_id=sid, seq_num=seq, data=content.encode("utf-8"))
            self.output_pipe.put_nowait(data)

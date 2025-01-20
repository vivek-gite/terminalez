# import os
# from typing import Tuple
#
# import pywintypes
# import win32console
# import win32file
# import win32pipe
# import win32process
# import win32security
# import win32con
# import win32event
# import win32api
# import asyncio
#
# async def list_available_terminals():
#     """Lists common terminals available on Windows with their paths."""
#
#     terminals = {}
#
#     # Common terminal executables and their locations
#     common_terminals = {
#         "Command Prompt": os.path.join(os.environ["WINDIR"], "System32", "cmd.exe"),
#         "PowerShell": os.path.join(os.environ["WINDIR"], "System32", "WindowsPowerShell", "v1.0", "powershell.exe"),
#         "Windows Terminal": os.path.join(os.getenv("LOCALAPPDATA"), "Microsoft", "WindowsApps", "wt.exe"),
#         # Location for Windows Terminal
#         "Git Bash": "C:\\Program Files\\Git\\bin\\bash.exe"  # Default location for Git Bash
#     }
#
#     # Check for common executables
#     for name, path in common_terminals.items():
#         if os.path.exists(path):
#             terminals[name] = path
#
#     return terminals
#
#
# class Terminal:
#     def __init__(self, shell_path=None):
#         self.shell_path = shell_path
#         # self.stdin_read = None
#         # self.stdin_write = None
#         # self.stdout_read = None
#         # self.stdout_write = None
#         self.read_pipe = None
#         self.write_pipe = None
#         self.process_information = None
#         self.win_size = (0,0)
#         # self.read_overlapped = pywintypes.OVERLAPPED()
#         # self.read_event = win32event.CreateEvent(None, 0, 0, None)
#         # self.read_overlapped.hEvent = self.read_event
#         # self.write_overlapped = pywintypes.OVERLAPPED()
#         # self.write_event = win32event.CreateEvent(None, 0, 0, None)
#         # self.write_overlapped.hEvent = self.write_event
#
#
#     async def create_pipes(self):
#         """Creates read and write pipes for the pseudo-terminal."""
#         security_attributes = win32security.SECURITY_ATTRIBUTES()
#         security_attributes.bInheritHandle = True
#
#         # self.stdin_read, self.stdin_write = win32pipe.CreatePipe(security_attributes, 0)
#         # self.stdout_read, self.stdout_write = win32pipe.CreatePipe(security_attributes, 0)
#         read_pipe_name = r"\\.\pipe\sshpyx_read_pipe"
#         write_pipe_name = r"\\.\pipe\sshpyx_write_pipe"
#
#         self.read_pipe = win32pipe.CreateNamedPipe(
#             read_pipe_name,
#             win32con.PIPE_ACCESS_INBOUND | win32con.FILE_FLAG_OVERLAPPED,
#             win32con.PIPE_TYPE_BYTE | win32con.PIPE_WAIT,
#             win32pipe.PIPE_UNLIMITED_INSTANCES,
#             0,
#             0,
#             0,
#             security_attributes
#         )
#
#         self.write_pipe = win32pipe.CreateNamedPipe(
#             write_pipe_name,
#             win32con.PIPE_ACCESS_OUTBOUND | win32con.FILE_FLAG_OVERLAPPED,
#             win32con.PIPE_TYPE_BYTE | win32con.PIPE_WAIT,
#             win32pipe.PIPE_UNLIMITED_INSTANCES,
#             0,
#             0,
#             0,
#             security_attributes
#         )
#
#
#     async def create_pty(self):
#         """Creates a pseudo-terminal with a specific shell."""
#         command_line = self.shell_path
#
#         await self.create_pipes()
#
#          # Ensure the child process can inherit the handles
#         win32api.SetHandleInformation(self.stdin_write, win32con.HANDLE_FLAG_INHERIT, 0)
#         win32api.SetHandleInformation(self.stdout_read, win32con.HANDLE_FLAG_INHERIT, 0)
#
#         startup_info = win32process.STARTUPINFO()
#         startup_info.dwFlags = win32process.STARTF_USESTDHANDLES
#         startup_info.hStdInput = self.stdin_read
#         startup_info.hStdOutput = self.stdout_write
#         startup_info.hStdError = self.stdout_write
#
#         # Create the pseudo-terminal process
#         creation_flags = win32con.CREATE_NEW_CONSOLE
#
#         self.process_information = win32process.CreateProcess(
#             None,
#             command_line,
#             None,
#             None,
#             True,
#             creation_flags,
#             None,
#             None,
#             startup_info
#         )
#
#         if not self.process_information:
#             win32api.CloseHandle(self.stdin_read)
#             win32api.CloseHandle(self.stdout_write)
#             raise Exception(f"Error creating process: {win32api.GetLastError()}")
#
#         print("Connected to read pipe")
#
#
#
#
#     def get_winsize(self) -> Tuple[int, int]:
#         """Get the window size of the TTY."""
#         return self.win_size
#
#     def set_winsize(self, rows: int, cols: int) -> None:
#         """Set the window size of the TTY."""
#
#         # Resize the console buffer
#         handle = win32api.GetStdHandle(win32api.STD_OUTPUT_HANDLE)
#         csbi = win32console.PyConsoleScreenBufferType(handle).GetConsoleScreenBufferInfo()
#         max_size = csbi["MaximumWindowSize"]
#
#         # Ensure that the size does not exceed max size.
#         rows = min(rows, max_size.Y)
#         cols = min(cols, max_size.X)
#
#         new_rect = win32console.PySMALL_RECTType(0, 0, cols - 1, rows - 1)
#         win32console.PyConsoleScreenBufferType(handle).SetConsoleWindowInfo(True, new_rect)
#
#         self.win_size = (rows, cols)
#
#     async def read(self, size: int = 1024) -> bytes:
#         """Read data from the terminal."""
#
#         output = b""
#         while True:
#             try:
#                 hr, data = win32file.ReadFile(self.stdout_read, size)
#                 if hr == 0:
#                     print(data)
#                     output+=data
#                 elif hr == 997: # ERROR_IO_PENDING
#                     win32event.WaitForSingleObject(self.read_event, win32event.INFINITE)
#                     output+=win32file.GetOverlappedResult(self.stdout_read, self.read_overlapped, True)
#                 elif hr == 234:
#                     break
#                 else:
#                     raise Exception(f"Error in reading from pipe: {win32api.GetLastError()}")
#
#             except pywintypes.error as e:
#                 # Handle ERROR_BROKEN_PIPE gracefully
#                 if e.winerror == 109:
#                     return b""
#                 else:
#                     raise
#
#         return output
#
#     async def write(self, data: bytes) -> None:
#         """Write data to the terminal."""
#         try:
#             hr, _ = win32file.WriteFile(self.stdin_write, data, self.write_overlapped)
#             if hr == 0:
#                 return
#             elif hr == 997: # ERROR_IO_PENDING
#                 win32event.WaitForSingleObject(self.write_event, win32event.INFINITE)
#                 return win32file.GetOverlappedResult(self.stdin_write, self.write_overlapped, True)
#             else:
#                 raise Exception(f"Error in writing to pipe: {win32api.GetLastError()}")
#         except pywintypes.error as e:
#             # Handle ERROR_BROKEN_PIPE gracefully
#             if e.winerror == 109:
#                 return
#             else:
#                 raise
#
#     async def close(self):
#         """Close the terminal and the PTY."""
#         if self.process_information:
#             win32api.TerminateProcess(self.process_information[0], 0)
#         if self.stdout_read:
#             win32file.CloseHandle(self.stdout_read)
#         if self.stdin_write:
#             win32file.CloseHandle(self.stdin_write)
#
#
# async def main():
#     shell = await list_available_terminals()
#     terminal = Terminal(shell["Command Prompt"])
#     await terminal.create_pty()
#
#
#     terminal.set_winsize(24, 80)
#     # Example of sending a command and reading output:
#     await terminal.write(b"dir\r\n")
#
#     while True:
#         output = await terminal.read()
#         if output:
#             print(output.decode(errors='ignore'), end='')
#         else:
#             break
#     await terminal.close()
#
#
# if __name__ == "__main__":
#     asyncio.run(main())
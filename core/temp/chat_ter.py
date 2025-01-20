import asyncio
import win32pipe
import win32file
import win32con
import win32process
import win32security
import pywintypes
import os
import win32api

def create_pseudo_console():
    security_attributes = win32security.SECURITY_ATTRIBUTES()
    security_attributes.bInheritHandle = True

    pipe_in_read, pipe_in_write = win32pipe.CreatePipe(security_attributes, 0)
    pipe_out_read, pipe_out_write = win32pipe.CreatePipe(security_attributes, 0)

     # Ensure the child process can inherit the handles
    win32api.SetHandleInformation(pipe_in_write, win32con.HANDLE_FLAG_INHERIT, 0)
    win32api.SetHandleInformation(pipe_out_read, win32con.HANDLE_FLAG_INHERIT, 0)

    startup_info = win32process.STARTUPINFO()
    startup_info.dwFlags = win32process.STARTF_USESTDHANDLES
    startup_info.hStdInput = pipe_in_read
    startup_info.hStdOutput = pipe_out_write
    startup_info.hStdError = pipe_out_write



    process_info = win32process.CreateProcess(
        None,                # Application name
        os.path.join(os.environ["WINDIR"], "System32", "cmd.exe"),          # Command line
        None,                # Process security attributes
        None,                # Thread security attributes
        True,                # Inherit handles
        win32process.CREATE_NEW_CONSOLE,  # Creation flags
        None,                # Environment
        None,                # Current directory
        startup_info         # STARTUPINFO
    )

    win32file.CloseHandle(pipe_in_read)
    win32file.CloseHandle(pipe_out_write)

    return pipe_in_write, pipe_out_read, process_info

async def write_to_console(pipe_in_write):
    try:
        while True:
            user_input = await asyncio.to_thread(input, "CMD> ")
            sanitized_input = user_input.replace("\n", " ").strip()  # Sanitize input
            if sanitized_input.lower() == "exit":
                break
            try:
                hr,_ = win32file.WriteFile(pipe_in_write, sanitized_input.encode('utf-8') + b"\n")
                print(f"WriteFile result: {hr}")
                if hr == 0:
                    win32file.FlushFileBuffers(pipe_in_write)  # Ensure data is flushed
                elif hr == 997:
                    print("Operation pending, retrying...")
                    continue
            except pywintypes.error as e:
                print(f"Error writing to console: {e}")
                break
    finally:
        if pipe_in_write:
            win32file.CloseHandle(pipe_in_write)


async def read_from_console(pipe_out_read, process_info):
    try:
        while True:
            # Check if the child process is still running
            exit_code = win32process.GetExitCodeProcess(process_info[0])
            if exit_code != win32con.STILL_ACTIVE:
                print("Child process terminated.")
                break

            # Check if there is data available to read from the pipe
            hr, available, _ = win32pipe.PeekNamedPipe(pipe_out_read, 0)
            if available > 0:
                try:
                    # Attempt to read from the pipe
                    hr, data = win32file.ReadFile(pipe_out_read, 4096)
                    if hr == 0:
                        print(data.decode('utf-8'), end="")
                    elif hr == 997:
                        continue # Pending operation, retry
                    elif hr == 234:
                        print("More data available, partial read.")
                        continue
                except pywintypes.error as e:
                    if e.winerror in [109]:  # Handle pipe closure
                        print("Pipe has been closed.")
                        break
                    else:
                        print(f"Error reading from pipe: {e}")
                        break
    finally:
        if pipe_out_read:
            win32file.CloseHandle(pipe_out_read)

async def main():
    pipe_in_write, pipe_out_read, process_info = create_pseudo_console()

    try:
        await asyncio.gather(
            write_to_console(pipe_in_write),
            read_from_console(pipe_out_read, process_info)
        )
    finally:
        if process_info[0]:
            win32process.TerminateProcess(process_info[0], 0)
            win32file.CloseHandle(process_info[0])
        if pipe_in_write:
            win32file.CloseHandle(pipe_in_write)



if __name__ == "__main__":
    asyncio.run(main())
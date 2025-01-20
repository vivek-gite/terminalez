import win32api
import win32con
import win32event
import win32file
import win32pipe
import win32process
import os
import threading
import sys

import win32security


def read_output(handle, encoding):
    """Continuously reads output from the child process."""
    while True:
        try:
            err, data = win32file.ReadFile(handle, 4096)
            if not data:
                break  # Pipe closed
            try:
                decoded_data = data.decode(encoding)
                print(decoded_data, end='', flush=True)
            except UnicodeDecodeError:
                print(f"Warning: Could not decode output using {encoding}. Raw bytes: {data!r}")
        except win32api.error as e:
            if e.winerror == 109:  # Pipe has been ended
                break
            else:
                print(f"Error reading from pipe: {e}")
                break

def write_input(handle):
    """Continuously reads user input and writes it to the child process."""
    while True:
        try:
            user_input = input() + '\n'  # Add newline for command execution
            win32file.WriteFile(handle, user_input.encode())
        except BrokenPipeError:
            break
        except EOFError:  # Handle Ctrl+D
            break
        except Exception as e:
            print(f"Error writing to pipe: {e}")
            break

def main():
    # Create pipes for stdin, stdout, and stderr redirection
    sa = win32security.SECURITY_ATTRIBUTES()
    sa.bInheritHandle = True

    # Output pipe (child's stdout)
    read_stdout, write_stdout = win32pipe.CreatePipe(sa, 0)
    # Input pipe (child's stdin)
    read_stdin, write_stdin = win32pipe.CreatePipe(sa, 0)
    # Error pipe (child's stderr) - Optional, but good practice
    read_stderr, write_stderr = win32pipe.CreatePipe(sa, 0)

    # Configure startup info for the child process
    startup_info = win32process.STARTUPINFO()
    startup_info.dwFlags |= win32process.STARTF_USESTDHANDLES
    startup_info.hStdInput = read_stdin
    startup_info.hStdOutput = write_stdout
    startup_info.hStdError = write_stderr

    # Create the child process (cmd.exe)
    command = "cmd.exe"
    try:
        process_information = win32process.CreateProcess(
            None,  # No application name
            command,
            None,  # Process security attributes
            None,  # Thread security attributes
            True,  # Inherit handles
            win32con.CREATE_NEW_CONSOLE,     # Creation flags (0 for a normal console application)
            None,  # Environment
            os.environ["USERPROFILE"],  # Current directory
            startup_info
        )
        print(f"Started process {command} with PID \n {process_information}")
    except win32api.error as e:
        print(f"Error creating process: {e}")
        return

    h_process = process_information[0]
    h_thread = process_information[1]

    # Close unused handles in the parent process
    win32file.CloseHandle(write_stdout)
    win32file.CloseHandle(read_stdin)
    win32file.CloseHandle(write_stderr)

    # Determine the encoding of the console
    encoding = sys.stdout.encoding

    # Start threads for asynchronous reading and writing
    output_thread = threading.Thread(target=read_output, args=(read_stdout, encoding))
    input_thread = threading.Thread(target=write_input, args=(write_stdin,))

    output_thread.daemon = True  # Allow the main thread to exit even if this is running
    input_thread.daemon = True

    output_thread.start()
    input_thread.start()

    # Wait for the child process to exit
    win32event.WaitForSingleObject(h_process, win32event.INFINITE)

    # Clean up handles
    win32file.CloseHandle(h_process)
    win32file.CloseHandle(h_thread)
    win32file.CloseHandle(read_stdout)
    win32file.CloseHandle(write_stdin)
    win32file.CloseHandle(read_stderr)

if __name__ == "__main__":
    main()
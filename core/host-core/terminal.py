import win32api
import win32con
import win32file
import win32pipe
import win32process
import os
import queue

import win32security

class Terminal:
    def __init__(self, shell_path: str, write_queue: queue.Queue):
        self.shell_path = shell_path
        self.read_stdout = None
        self.write_stdin = None
        self.process_information = None
        self.write_queue = write_queue

    def read_output(self, handle, encoding):
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

    def write_input(self, handle):
        """Continuously reads user input and writes it to the child process."""
        while True:
            try:
                if self.write_queue.empty():
                    continue

                user_input = self.write_queue.get() + "\n"
                win32file.WriteFile(handle, user_input.encode())
            except BrokenPipeError:
                break
            except EOFError:  # Handle Ctrl+D
                break
            except Exception as e:
                print(f"Error writing to pipe: {e}")
                break

    def create_pipes(self) -> tuple:
        # Create pipes for stdin, stdout redirection
        sa = win32security.SECURITY_ATTRIBUTES()
        sa.bInheritHandle = True

        # Output pipe (child's stdout)
        self.read_stdout, write_stdout = win32pipe.CreatePipe(sa, 0)
        # Input pipe (child's stdin)
        read_stdin, self.write_stdin = win32pipe.CreatePipe(sa, 0)

        return read_stdin, write_stdout

    def spawn_new_shell(self):
        read_stdin, write_stdout = self.create_pipes()

        # Configure startup info for the child process
        startup_info = win32process.STARTUPINFO()
        startup_info.dwFlags |= win32process.STARTF_USESTDHANDLES
        startup_info.hStdInput = read_stdin
        startup_info.hStdOutput = write_stdout
        startup_info.hStdError = write_stdout

        current_directory = os.environ.get("USERPROFILE") or os.getcwd()
        # Create the child process
        try:
            self.process_information = win32process.CreateProcess(
                None,  # No application name
                self.shell_path,
                None,  # Process security attributes
                None,  # Thread security attributes
                True,  # Inherit handles
                win32con.NORMAL_PRIORITY_CLASS | win32con.CREATE_NEW_CONSOLE | win32con.CREATE_NO_WINDOW,  # Creation flags
                None,  # Environment
                current_directory,  # Current directory
                startup_info
            )
        except win32api.error as e:
            print(f"Error creating process: {e}")
            return

        # Close unused handles in the parent process
        win32file.CloseHandle(write_stdout)
        win32file.CloseHandle(read_stdin)


    def shutdown_gracefully(self):
        h_process = self.process_information[0]
        h_thread = self.process_information[1]

        # Clean up handles
        win32file.CloseHandle(h_process)
        win32file.CloseHandle(h_thread)
        win32file.CloseHandle(self.read_stdout)
        win32file.CloseHandle(self.write_stdin)
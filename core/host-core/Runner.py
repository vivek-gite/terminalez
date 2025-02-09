import os
import queue
import sys
import threading

import win32event

from terminal import Terminal


class Runner:
    def __init__(self):
        self.usr_terminal: str = ""
        self.write_pipe: queue.Queue = queue.Queue()

    @staticmethod
    async def list_available_terminals() -> dict:
        """Lists common terminals available on Windows with their paths."""

        terminals = {}

        # Common terminal executables and their locations
        common_terminals = {
            "Command Prompt": os.path.join(os.environ["WINDIR"], "System32", "cmd.exe"),
            "PowerShell": os.path.join(os.environ["WINDIR"], "System32", "WindowsPowerShell", "v1.0", "powershell.exe"),
            "Windows Terminal": os.path.join(os.getenv("LOCALAPPDATA"), "Microsoft", "WindowsApps", "wt.exe"),
            # Location for Windows Terminal
            "Git Bash": "C:\\Program Files\\Git\\bin\\bash.exe"  # Default location for Git Bash
        }

        # Check for common executables
        for name, path in common_terminals.items():
            if os.path.exists(path):
                terminals[name] = path

        return terminals

    async def select_terminal(self) -> str:
        """ Lists available terminals and prompts the user to select one. """
        terminals = await self.list_available_terminals()
        print("Available terminals:")
        for index, name in enumerate(terminals.keys()):
            print(f"{index + 1}. {name}")

        choice: int = -1
        try:
            choice = int(input("Enter the number of the terminal you want to open: ")) - 1
            # make sure that the choice is within the range of available terminals and the input is not a character or string
            while choice not in range(len(terminals)):
                choice = int(input("Invalid choice. Please enter a valid number: ")) - 1
        except ValueError:
            print("Invalid choice. Please enter a valid number.")
            await self.select_terminal()

        # Storing the selected terminal name
        self.usr_terminal = list(terminals.keys())[choice]

        # Returning the path of the selected terminal
        return terminals[self.usr_terminal]

    @staticmethod
    async def start_process_and_handle_io(terminal: Terminal) -> None:
        # Spawn a new shell process
        terminal.spawn_new_shell()

        # Determine the encoding of the console
        encoding = sys.stdout.encoding

        # Start threads for asynchronous reading and writing
        output_thread = threading.Thread(target=terminal.read_output, args=(terminal.read_stdout, encoding))
        input_thread = threading.Thread(target=terminal.write_input, args=(terminal.write_stdin,))

        output_thread.daemon = True  # Allow the main thread to exit even if this is running
        input_thread.daemon = True

        output_thread.start()
        input_thread.start()

        h_process = terminal.process_information[0]

        # Wait for the child process to exit
        win32event.WaitForSingleObject(h_process, win32event.INFINITE)

        # Clean up handles
        terminal.shutdown_gracefully()

    async def create_terminal(self) -> None:
        """Creates a new terminal process."""
        terminal_path = await self.select_terminal()
        print(f"Opening terminal: {terminal_path}")

        # Create a new terminal process
        terminal = Terminal(terminal_path, self.write_pipe)
        await self.start_process_and_handle_io(terminal)

    async def run_command(self, command: str):
        """Runs a command in the selected terminal."""
        self.write_pipe.put(command)

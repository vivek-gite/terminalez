from core.host_core.Runner import Runner


class ConsoleHandler:
    def __init__(self):
        self.number_of_terminals = 0
        self.terminals = dict()
        self.terminal_writes = dict()

    def start_terminal(self):
        start_term = Runner()
        start_term.create_terminal()
        while True:

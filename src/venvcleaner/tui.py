from curses import wrapper


# MARK: TUI main routine
def tui(stdscr):
    stdscr.clear()
    for i in range(10, -1, -1):
        stdscr.addstr(i, 0, f'10 divided by {i} is {10/i}')
        stdscr.refresh()
        stdscr.getkey()


# MARK: Main Function
def main(dir_path):
    wrapper(tui)

import argparse
import sys
import os
import pickle
import atexit
from datetime import datetime, timedelta
from typing import Optional, List, Iterable

DATA_FILENAME = ".todo.pickle"          # Sets file.
def _default_path() -> str:
    base = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()   # Set dir.
    return os.path.join(base, DATA_FILENAME)

class Task:
    """Representation of a task."""
    _id_counter = 1                                 # ID

    def __init__(self, name: str, priority: int = 1, due_date: Optional[datetime] = None):
        """Creates all necessary variables."""
        self.created: datetime = datetime.now()
        self.completed: Optional[datetime] = None
        self.name: str = name
        self.unique_id: int = Task._id_counter
        Task._id_counter += 1                       # Raises ID_counter because we are preparing for the next task.
        self.priority: int = priority if priority in (1, 2, 3) else 1
        self.due_date: Optional[datetime] = due_date

    def mark_completed(self) -> None:
        """Marks a task as done."""
        self.completed = datetime.now()

class Tasks:
    """A list of `Task` objects."""
    def __init__(self, filepath: Optional[str] = None):
        self.filepath = filepath or _default_path()             # chooses a storage path (filepath or _default_path())/
        self.tasks: List[Task] = []
        self._load()
        atexit.register(self.pickle_tasks)                      # schedules an automatic save of the tasks to disk.

    def _atomic_dump(self, data, path):
        """Creates a temporary path to pickle items. """
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp, path)

    def pickle_tasks(self) -> None:
        """Saves current tasks to disk."""
        last_id = max((t.unique_id for t in self.tasks), default=0)
        os.makedirs(os.path.dirname(self.filepath) or ".", exist_ok=True)
        self._atomic_dump((self.tasks, last_id), self.filepath)

    def _load(self) -> None:
        """If the pickle file doesn't exist, it creates an empty list, otherwise it pickle.loads a tuple and sets self.tasks to that list."""
        if not os.path.exists(self.filepath):
            self.tasks = []
            return
        try:
            self.tasks, last_id = pickle.load(open(self.filepath, "rb"))
            Task._id_counter = max(Task._id_counter, last_id + 1)
            self.tasks.sort(key=lambda t: t.created)
        except Exception:
            self.tasks = []

    def add(self, name: str, priority: int = 1, due_date: Optional[datetime] = None) -> Task:
        """Adding a task to the list and then sorting the list."""
        t = Task(name, priority, due_date)
        self.tasks.append(t)
        self.tasks.sort(key=lambda x: x.created)
        self.pickle_tasks()
        return t

    def delete(self, task_id: int) -> bool:
        """Deleting a task using a task_id and a for loop."""
        for i, t in enumerate(self.tasks):
            if t.unique_id == task_id:
                del self.tasks[i]
                self.pickle_tasks()
                return True
        return False

    def done(self, task_id: int) -> bool:
        """Sets a task as done by using a for loop and checking if something is already completed."""
        for t in self.tasks:
            if t.unique_id == task_id:
                if t.completed is None:
                    t.mark_completed()
                    self.pickle_tasks()
                return True
        return False

    def list(self, include_completed: bool = True) -> List[Task]:
        """Returns a list of all the tasks that have yet to be completed."""
        return (list(self.tasks) 
                if include_completed
                else [t for t in self.tasks
                        if t.completed is None]            
    )

    def query(self, *, texts: Optional[List[str]] = None, priority: Optional[int] = None,
              due_before: Optional[datetime] = None, due_after: Optional[datetime] = None,
              completed: Optional[bool] = None) -> List[Task]:
        """If any of the given text appears in the list of tasks, the tasks are given to the user. """
        results: Iterable[Task] = self.tasks
        if texts:
            lowers = [t.lower() for t in texts]                     # lowers all the task decriptions. 
            results = (t for t in results if any(s in t.name.lower() for s in lowers))
        if priority in (1, 2, 3):                                              # sorts the rest of it. 
            results = (t for t in results if t.priority == priority)
        if due_before:
            results = (t for t in results if t.due_date and t.due_date <= due_before)
        if due_after:
            results = (t for t in results if t.due_date and t.due_date >= due_after)
        if completed is not None:
            results = (t for t in results if (t.completed is not None) == completed)
        return list(results)

    def report(self) -> dict:
        """Reports all important information like total tasks, total completed tasks and uncompleted tasks."""
        total = len(self.tasks)
        done = sum(t.completed is not None for t in self.tasks)
        open_ = total - done
        by_priority = {1: 0, 2: 0, 3: 0}
        for t in self.tasks:
            by_priority[t.priority] += 1
        return {"total": total, "open": open_, "completed": done, "by_priority": by_priority}
    
    def reset(self):
        """Delete all tasks and remove the data file."""
        self.tasks = []
        Task._id_counter = 1
        if os.path.exists(self.filepath):
            os.remove(self.filepath)

def _fmt_due(dt: Optional[datetime]) -> str:
    """Formats due date."""
    if not dt:
        return "-"
    return f"{dt.month}/{dt.day}/{dt.year}" 

def _age_days(created_dt: datetime) -> int:
    """Formats the age between dates."""
    return (datetime.now().date() - created_dt.date()).days

def _fmt_full(dt: Optional[datetime]) -> str:
    """Full format of time periods."""
    if not dt:
        return "-"
    loc = dt.astimezone()
    return f"{loc.strftime('%a %b')} {loc.day} {loc.strftime('%H:%M:%S %Z %Y')}"

def _sort_open(tasks: List[Task]) -> List[Task]:
    """Seperates tasks with due dates and those without due dates. Organizes them and them adds them back together."""
    with_due = [t for t in tasks if t.due_date]
    without_due = [t for t in tasks if not t.due_date]
    with_due.sort(key=lambda t: (t.due_date, t.priority, t.created))
    without_due.sort(key=lambda t: (t.priority, t.created))
    return with_due + without_due

def _print_open_table(items: List[Task]) -> None:
    """Creates the format for the open tasks not yet completed."""
    print(f"{'ID':<3} {'Age':<4} {'Due Date':<10} {'Priority':<8} Task")
    print(f"{'--':<3} {'---':<4} {'--------':<10} {'--------':<8} {'----'}")
    for t in items:
        age = f"{_age_days(t.created)}d"            # Formates the ages and the due dates with previous functions.
        due = _fmt_due(t.due_date)
        print(f"{t.unique_id:<3} {age:<4} {due:<10} {t.priority:<8} {t.name}")

def _print_report_table(items: List[Task]) -> None:
    """Creates the format for all of the tasks done or not for report."""
    ordered = _sort_open(items) 
    print(f"{'ID':<3} {'Age':<4} {'Due Date':<10} {'Priority':<8} {'Task':<18} {'Created':<28} {'Completed':<20}")
    print(f"{'--':<3} {'---':<4} {'--------':<10} {'--------':<8} {'----':<18} {'-'*28} {'-'*12}")
    for t in ordered:
        age = f"{_age_days(t.created)}d"            # Formats the days with a d at the end.
        due = _fmt_due(t.due_date)                  # Formates the ages, creation dates and the due dates with previous functions.
        created_s = _fmt_full(t.created)
        completed_s = _fmt_full(t.completed)
        print(f"{t.unique_id:<3} {age:<4} {due:<10} {t.priority:<8} {t.name:<18} {created_s:<28} {completed_s}")

def parse_due(raw: Optional[str]) -> Optional[datetime]:
    """Creative parser for due dates if any."""
    if not raw:                                         # Returns nothing because given no due date.
        return None
    
    s = raw.strip().lower()
    now = datetime.now()

    if s in ("none", "no", "na", "n/a", "-"):           # Returns nothing because all of these mean no due date.
        return None
    if s == "today":                                    # If given today, it makes it due at the end of the day.
        return now.replace(hour=23, minute=59, second=59, microsecond=0)
    if s == "tomorrow":                                 # If given tomorrow, it makes it due at the end of the following day.
        d = now + timedelta(days=1)
        return d.replace(hour=23, minute=59, second=59, microsecond=0)
    weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    if s in weekdays:
        target = weekdays.index(s)
        delta = (target - now.weekday()) % 7
        if delta == 0:                                  # Takes the target day of the week, minus today's weekday to determine how many days out.
            delta = 7                                   # Plus seven if it's the same day.
        d = now + timedelta(days=delta)
        return d.replace(hour=23, minute=59, second=59, microsecond=0)          # Makes it due the next weekday assigned.

    fmts = ["%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"]
    for fmt in fmts:                                    # Formats everything. 
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            pass
    raise ValueError(f"Unrecognized due date: {raw!r}")

def print_task_line(t: Task):
    """Shows due date if it has it, completion date if possible and all other attributes of a task in one line."""
    due = t.due_date.date() if t.due_date else "-"
    done = t.completed.strftime("%Y-%m-%d %H:%M") if t.completed else "-"
    print(f"[{t.unique_id}] (p{t.priority}) {t.name} | created {t.created:%Y-%m-%d} | due {due} | completed {done}")

def build_parser() -> argparse.ArgumentParser:
    """Creates a parser with all necessary arguments as listed above."""
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--reset", action="store_true")
    g.add_argument("--add")
    g.add_argument("--delete", type=int)
    g.add_argument("--list", action="store_true")
    g.add_argument("--report", action="store_true")
    g.add_argument("--query", nargs="+")
    g.add_argument("--done", type=int)
    p.add_argument("--priority", type=int, choices=[1, 2, 3], default=1)
    p.add_argument("--due")
    p.add_argument("--due-before")
    p.add_argument("--due-after")
    return p

def main(argv=None) -> int:
    """Helps define the arguments for the parser."""
    aliases = {"list": "--list", "report": "--report", "add": "--add", "query": "--query",      # All the arguments that has to be fully defined for the parser. 
               "done": "--done", "delete": "--delete", "reset": "--reset"}
    if len(sys.argv) > 1 and sys.argv[1] in aliases:
        sys.argv[1] = aliases[sys.argv[1]]

    args = build_parser().parse_args(argv)
    tasks = Tasks()

    if args.add is not None:                                    # Will not run if the argument is not used.
        try:
            title = args.add.strip()                            # Trim whitespace from the description.
            if not title or title.isdigit():
                raise ValueError("Task description must be a non-empty string.") # Error handling.
            due_dt = parse_due(args.due) if args.due else None
            t = tasks.add(title, priority=args.priority, due_date=due_dt)        # Creates tasks and then clarifies to user it was made.
            print(f"Created task {t.unique_id}")
            return 0
        except Exception:
            print('There was an error in creating your task. Run "todo -h" for usage instructions.')        # Error.
            return 1

    if args.delete is not None:                                 # Will not run if the argument is not used.
        ok = tasks.delete(args.delete)                          # Deletes task.
        print(f"Deleted task {args.delete}" if ok else "Task not found. ")  # Calrification.
        return 0 if ok else 1

    if args.done is not None:                                   # Will not run if the argument is not used.
        ok = tasks.done(args.done)                              # Runs done.
        print(f"Completed task {args.done}" if ok else "Task not found. ")  # Clarification
        return 0 if ok else 1

    if args.list:                                               # Will not run if the argument is not used.
        open_items = tasks.list(include_completed=False)        # Runs list. 
        if not open_items:
            print("no tasks ")                                  # Prints no tasks if no tasks.
            return 0
        _print_open_table(_sort_open(open_items))               # sorts.
        return 0

    if args.report:                                             # Will not run if the argument is not used.
        all_items = list(tasks.list(include_completed=True))    # Runs list but with a true include_completed argument which makes every task returned. 
        if not all_items:
            print("no tasks ")                                  # Prints no tasks if no tasks. 
            return 0
        _print_report_table(all_items)                          # Runs it.
        return 0

    if args.query is not None:                                  # Will not run if the argument is not used.
        due_before = parse_due(args.due_before) if args.due_before else None        # Organizes the list.
        due_after = parse_due(args.due_after) if args.due_after else None
        results = tasks.query(
            texts=args.query,                                                       # Sets important variables.
            priority=args.priority if "--priority" in sys.argv else None,
            due_before=due_before,
            due_after=due_after,
            completed=False, 
        )
        if not results:
            print("(no matches)")                                  # Prints no matches if the string does not appear at all.
            return 0
        _print_open_table(_sort_open(results))                      # Shows results.
        return 0
    
    if args.reset:                                              # Will not run if the argument is not used.
        tasks.reset()
        print("All tasks deleted.")                             # Simply deletes all tasks. Easiliest of all actions.
        return 0

    return 0

if __name__ == "__main__":
    raise SystemExit(main())

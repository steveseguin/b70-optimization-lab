You maintain the Python library in /app/more_itertools (its tests are in /app/tests). There is a queue
of 43 tickets. Run the command `next` to receive the next ticket; each ticket is printed once.

- A BUG ticket names a function that gives wrong results and the test class that shows it. Find the cause in the
  library, fix it, and check with `t TestClass` (it runs that class and prints the end of the output). Each bug is a
  small mistake in the named function (or in a method of the named class). Then fetch the next ticket.
- A NOTICE ticket is an instruction from the maintainer that holds from that ticket on, for every later ticket,
  until the queue is empty. There is nothing to fix for a NOTICE; fetch the next ticket.

Rules for the whole job:
- Never change anything under /app/tests. The tests are right; the library is wrong.
- Do not look for the tickets on disk; work through them with `next`, in order, one at a time.
- Use `t` for tests (one or a few classes); do not run the whole suite.
- Work from the code in /app only: do not fetch, install or copy any other copy of this library.
- When `next` says the queue is empty, the job is done.

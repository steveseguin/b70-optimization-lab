set pagination off
set confirm off
set print thread-events off
handle SIGINT nostop pass
handle SIGTERM nostop pass
catch throw
commands
silent
printf "=== throw ===\n"
bt 16
continue
end
run
printf "=== final stop ===\n"
bt 24

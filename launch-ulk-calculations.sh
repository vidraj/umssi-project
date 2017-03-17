#!/bin/sh

# Launch jobs in parallel, waiting on them to finish.
# If any job fails, return 1, else return 0

for PREFIX in "$@"; do
	make -C universal-knowledge/code "lang=$PREFIX" run &
	PIDS="$PIDS $!"
done


RESULT=0

for PID in $PIDS; do
	wait "$PID" || RESULT=1
done


exit "$RESULT"

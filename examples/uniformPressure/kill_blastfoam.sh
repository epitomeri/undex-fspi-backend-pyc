#!/bin/bash

# Find and kill all blastFoam processes
PIDS=$(pgrep -f "mpirun -np")

if [ -z "$PIDS" ]; then
    echo "No blastFoam processes found."
else
    echo "Killing blastFoam processes:"
    echo "$PIDS" | xargs kill -9
    echo "Processes killed."
fi

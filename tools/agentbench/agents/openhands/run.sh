#!/bin/sh
# OpenHands (software-agent-sdk), headless, through oh_run.py; conversation events in /logs/agent/openhands/.
exec /opt/agent/bin/python -I /opt/agentbench/oh_run.py "$1" < /dev/null > /logs/agent/openhands-console.txt 2>&1

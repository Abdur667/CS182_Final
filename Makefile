SHELL := /bin/bash

# options options
OPTS_DEBUG=--terrain debug --numbers debug --ports preset --pieces debug --players debug
OPTS_DEBUG_NO_PREGAME=$(OPTS_DEBUG) --pregame off
OPTS_PROD=--terrain empty --numbers empty --ports preset --pieces preset --players preset
OPTS_DEMO=--terrain random --numbers random --ports preset --pieces preset --players preset

OPTS=$(OPTS_DEMO)

all: relaunch

logs:
	cat log/buffer.log

launch:
	@mkdir -p log
	python3 main.py $(OPTS) &>log/buffer.log & echo $$! > log/running.pid
	@cat log/running.pid
	@echo "Follow logs: tail -f log/buffer.log, or make logs"

tail:
	tail -f -n 30 log/buffer.log

relaunch:
	@mkdir -p log
	-mv log/buffer.log log/spectator-launch-`date +"%Y-%m-%d_%H-%M-%S"`.log
	-cat log/running.pid | xargs kill
	python3 main.py $(OPTS) &>log/buffer.log & echo $$! > log/running.pid
	cat log/running.pid
	tail -f -n 30 log/buffer.log

demo:
	@mkdir -p log
	-mv log/buffer.log log/spectator-launch-`date +"%Y-%m-%d_%H-%M-%S"`.log
	-cat log/running.pid | xargs kill
	python3 main.py $(OPTS_DEMO) &>log/buffer.log & echo $$! > log/running.pid
	cat log/running.pid

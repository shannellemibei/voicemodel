run:
	@python3 english.py 2>/dev/null

# Silent run
swahili:
	@python3 swahili.py 2>/dev/null

debug:
	@python3 done2.py

# Clean bytecode and cache
clean:
	@rm -rf __pycache__ *.pyc

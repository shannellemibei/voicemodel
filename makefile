run:
	@python3 main.py 2>/dev/null

# Silent run
swahili:
	@python3 main.py 2>/dev/null

debug:
	@python3 main.py

clean:
	@rm -rf __pycache__ *.pyc

.PHONY: test init audit doctor
test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v
init:
	PYTHONPATH=src python3 -m qimenllm init
audit:
	PYTHONPATH=src python3 -m qimenllm audit
doctor:
	python3 scripts/doctor.py

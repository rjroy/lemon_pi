#!/usr/bin/python3

import argparse
import os
from lemonlib.pi import Config, PiHole
from lemonlib.os import load_lemon_data

def main(args, cfg):
	pi = PiHole(Config(args.mode, cfg), args.test)
	if not pi.is_valid:
		exit(1)

	if not args.test:
		pi.update()

	if not pi.refresh():
		exit(1)

	pi.finalize()

if __name__ == "__main__":
	cfg = load_lemon_data('config', os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data'))

	parser = argparse.ArgumentParser()
	parser.add_argument("-t", "--test", help="do not commit. only test the script", action="store_true")
	parser.add_argument("--mode", help="set the firebog mode", default=cfg['parameter']['firebog_type'], choices=["tick","nocross","all"])

	args = parser.parse_args()
	main(args, cfg)
	

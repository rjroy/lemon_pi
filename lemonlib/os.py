import os
import json

def validate_access(path: str):
	if os.path.exists(path):
		print(f'[i] Path {path} verified exists.')
	else:
		print(f'[E] Path {path} was not found.')
		return False

	if os.access(path, os.X_OK | os.W_OK):
		print(f'[i] Write access to {path} verified.')
	else:
		print(f'[E] Write access to {path} is not available.  Please run as root or other privileged user.')
		return False

	return True

def load_lemon_data(name: str, dir_path: str):
	json_file = os.path.join(dir_path, f'{name}.json')
	with open(json_file) as f:
		return json.load(f)

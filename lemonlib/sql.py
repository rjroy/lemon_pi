import os
import sqlite3

class Database(object):
	def __init__(self, db_path: str):
		# path to the SQLite3 datbase
		self.__db_path = db_path
		# Active connection
		self.__db_conn = None
		# Active cursor
		self.__cursor = None
		# Is the database in debug mode?
		self.__is_debug = False

	def __del__(self):
		self.close()

	@property
	def is_debug(self):
		return self.__is_debug

	@is_debug.setter
	def is_debug(self, is_debug: bool):
		self.__is_debug = is_debug
		print(f'[d] DB {self.__db_path} set to {"Rollback" if self.__is_debug else "Commit"}')

	@property
	def cursor(self):
		if not self.__db_conn:
			self.open()
		if not self.__cursor:
			print('[i] Open DB cursor')
			self.__cursor = self.__db_conn.cursor()
		return self.__cursor

	def open(self):
		if not os.path.isfile(self.__db_path) or os.path.getsize(self.__db_path) == 0:
			print(f'[E] DB {self.__db_path} was expected to exist.')
			return False

		print(f'[i] connecting to {self.__db_path}')

		try:
			self.__db_conn = sqlite3.connect(self.__db_path)
			self.__db_conn.row_factory = sqlite3.Row
			return True
		except sqlite3.Error as e:
			print(f'[E] Error connecting to db {self.__db_path}:{e}')
			return False

	def close(self):
		if self.__cursor:
			self.finalize()
		if self.__db_conn:
			self.__db_conn.close()
			self.__db_conn = None

	def finalize(self):
		if not self.__cursor:
			print('[E] No cursor to finalize')
		else:
			if self.__is_debug:
				self.__db_conn.rollback()
				print('[d] rollback')
			else:
				self.__db_conn.commit()
				print('[i] commit')
			self.__cursor = None

	def dump_schema(self):
		if not self.cursor:
			print('[E] DB invalid')
			return
		
		self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
		tables_result = self.cursor.fetchall()
		table_names = set()
		table_names.update([x[0] for x in tables_result])

		print()
		for table in table_names:
			try:
				self.cursor.execute(f"SELECT * FROM '{table}' LIMIT 1")
				print(f'[d] table({table}) columns({self.cursor.fetchall()[0].keys()})')
			except:
				print(f'[E] table({table}) error printing')
		print()


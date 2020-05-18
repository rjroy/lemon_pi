from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

class Remote(object):
	def __init__(self, url: str):
		self.__url = url
		self.__data = None
		self.__string_set = None
		self.__host_set = None

	@property
	def data(self):
		return self.fetch_data()

	@property
	def string_set(self):
		return self.fetch_string_set()

	@property
	def host_set(self):
		return self.fetch_host_set()

	def fetch_data(self):
		if self.__data:
			return self.__data

		if not self.__url:
			return None

		headers = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win74; x64; rv:71.0) Gecko/20100101 Firefox/71.0' }
	
		print('[i] Fetching:', self.__url)

		try:
			data = urlopen(Request(self.__url, headers=headers))
		except HTTPError as e:
			print('[E] HTTP Error:', e.code, 'whilst fetching', self.__url)
			return None
		except URLError as e:
			print('[E] URL Error:', e.code, 'whilst fetching', self.__url)
			return None

		# Read and decode
		data = data.read().decode('UTF-8').replace('\r\n', '\n')

		# Abort if there is no data
		if not data:
			print(f'[E] {self.__url} was empty.')
			return None

		# Return the page data
		self.__data = data
		return self.__data

	def fetch_string_set(self):
		if self.__string_set:
			return self.__string_set

		if not self.__data:
			if not self.fetch_data():
				return None

		# Strip leading and trailing whitespace
		data = '\n'.join(x.strip() for x in self.__data.splitlines())
		# Add strings to set and remove comments
		self.__string_set = set()
		self.__string_set.update(x for x in map(str.strip, data.splitlines()) if x and x[:1] != '#')

		# Return the strings
		return self.__string_set

	def fetch_host_set(self):
		if self.__host_set:
			return self.__host_set

		if not self.__string_set:
			if not self.fetch_string_set():
				return None
		
		# Extract the hosts from a set of URLs
		self.__host_set = set()
		self.__host_set.update([x.replace('/',':').split(':')[3] for x in self.__string_set])

		# Return the hosts
		return self.__host_set


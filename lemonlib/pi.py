import os
import subprocess
from .sql import Database
from .os import validate_access
from .url import Remote


class Config(object):
	def __init__(self, firebog_type: str, cfg: dict):
		self.firebog_type = firebog_type
		self.url_regexs = cfg['blacklist']['regexs']
		self.blocklist = cfg['blacklist']['custom']
		self.url_adlist = cfg['blacklist']['adlist'].format(firebog_type=firebog_type)
		self.path_pihole = cfg['path']['pihole']
		self.path_pihole_db = os.path.join(self.path_pihole, cfg['parameter']['gravity'])
		self.allowlist = cfg['whitelist']
		self.groups = cfg['groups']


class PiHole(object):
	class DomainType(object):
		exact_allowlist = 0
		exact_blocklist = 1
		regex_allowlist = 2
		regex_blocklist = 3

	def __init__(self, cfg: Config, is_testing: bool = False):
		self.cfg = cfg
		self.__db = Database(self.cfg.path_pihole_db)
		self.__db.is_debug = is_testing
		self.__regexs = Remote(self.cfg.url_regexs)
		self.__regexs_comment = '/'.join(self.cfg.url_regexs.replace('/',':').split(':')[3:5])
		self.__adlist = Remote(self.cfg.url_adlist)
		self.__adlist_comment = f"{self.cfg.url_adlist.replace('/',':').split(':')[3]}: {self.cfg.firebog_type}"
		self.__valid = validate_access(self.cfg.path_pihole)
		self.__updated = False

		if is_testing:
			self.__db.dump_schema()

	@property
	def is_valid(self):
		return self.__valid

	def finalize(self):
		self.__db.close()
		if self.__updated and self.__valid:
			print('[i] Restarting Pi-hole')
			subprocess.call(['pihole', '-g', 'restartdns', 'reload'])
			self.__updated = False

	def update(self):
		if self.__valid:
			print('[i] Updating Pi-hole')
			subprocess.call(['pihole', '-up'])
			print('[i] Updating cloudflared')
			subprocess.call(['cloudflared', 'update'])
			print('[i] Restart cloudflared')
			subprocess.call(['systemctl', 'restart', 'cloudflared'])

	def refresh(self):
		if not self.__valid:
			return False

		updated_any = False
		if self.__update_domain_list(PiHole.DomainType.regex_blocklist, self.__regexs.string_set, self.__regexs_comment):
			updated_any = True
		if self.__update_domain_list(PiHole.DomainType.exact_allowlist, self.__adlist.host_set, f'for: {self.__adlist_comment}'):
			updated_any = True
			self.__update_adlist_list(self.__adlist.string_set, self.__adlist_comment)
		
		for comment,string_set in self.cfg.blocklist['regexs'].items():
			if self.__update_domain_list(PiHole.DomainType.regex_blocklist, string_set, comment):
				updated_any = True
		for comment,string_set in self.cfg.blocklist['exact'].items():
			if self.__update_domain_list(PiHole.DomainType.exact_blocklist, string_set, comment):
				updated_any = True

		for comment,string_set in self.cfg.allowlist['regexs'].items():
			if self.__update_domain_list(PiHole.DomainType.regex_allowlist, string_set, comment):
				updated_any = True
		for comment,string_set in self.cfg.allowlist['exact'].items():
			if self.__update_domain_list(PiHole.DomainType.exact_allowlist, string_set, comment):
				updated_any = True

		if self.__update_groups(self.cfg.groups.keys(), 'Lemon Pi Groups'):
			all_comments = set()
			for group_name,string_set in self.cfg.groups.items():
				self.__link_domains(group_name, string_set)
				all_comments.update([x for x in string_set])
			for group_name,string_set in self.cfg.groups.items():
				self.__unlink_domains(group_name, all_comments.difference(string_set))

		return updated_any

	def __update_groups(self, groups: set, install_comment: str):
		if not self.__valid:
			return False

		if not groups:
			return False

		if not self.__db.cursor:
			return False

		print(f'[i] Adding / updating groups comment({install_comment})')
		sorted_groups = sorted(groups)
		self.__db.cursor.executemany('INSERT OR IGNORE INTO \'group\' (enabled, name, description) ' 
									'VALUES(1, ?, ?)', 
									[(x, install_comment) for x in sorted_groups])
		self.__db.cursor.executemany('UPDATE \'group\' ' 
									'SET description = ? WHERE name in (?) AND description != ?', 
									[(install_comment, x, install_comment) for x in sorted_groups])
		self.__db.finalize()

		print(f'[i] removing obsolete groups')
		# fetch existing
		self.__db.cursor.execute('SELECT name FROM \'group\' WHERE description = ?', (install_comment,))
		groups_local_result = self.__db.cursor.fetchall()
		groups_local = set()
		groups_local.update([x[0] for x in groups_local_result])
		# remove any local that do not exist in the fetched list
		groups_remove = groups_local.difference(groups)

		if groups_remove:
			self.__db.cursor.executemany('DELETE FROM \'group\' WHERE name in(?)', [(x,) for x in groups_remove])
		self.__db.finalize()

		if not self.__db.is_debug:
			self.__updated = True
		return True

	def __link_domains(self, group_name: str, domain_comments: set):
		if not self.__valid:
			return False

		if not group_name or not domain_comments:
			return False

		if not self.__db.cursor:
			return False

		print(f'[i] Fetch group({group_name})')
		self.__db.cursor.execute('SELECT id FROM \'group\' WHERE name = ?', [group_name])
		group_result = self.__db.cursor.fetchall()
		group_ids = [x[0] for x in group_result]
		if not group_ids:
			print(f'[E] Group({group_name}) not found')
			return False
		group_id = group_ids[0]

		print(f'[i] Linking domains group({group_name})')
		self.__db.cursor.executemany('INSERT OR IGNORE INTO domainlist_by_group (group_id, domainlist_id) '
									'SELECT ?, id '
									'FROM domainlist WHERE comment in(?)',
									[(group_id, comment) for comment in domain_comments])
		self.__db.finalize()

		if not self.__db.is_debug:
			self.__updated = True
		return True

	def __unlink_domains(self, group_name: str, domain_comments: set):
		if not self.__valid:
			return False

		if not group_name or not domain_comments:
			return False

		if not self.__db.cursor:
			return False

		print(f'[i] Fetch group({group_name})')
		self.__db.cursor.execute('SELECT id FROM \'group\' WHERE name = ?', [group_name])
		group_result = self.__db.cursor.fetchall()
		group_ids = [x[0] for x in group_result]
		if not group_ids:
			print(f'[E] Group({group_name}) not found')
			return False
		group_id = group_ids[0]

		print(f'[i] Unlinking domains group({group_name})')
		self.__db.cursor.executemany('DELETE FROM domainlist_by_group '
									'WHERE group_id = ? AND domainlist_id in('
										'SELECT id FROM domainlist WHERE comment in(?)'
									')',
									[(group_id, comment) for comment in domain_comments])
		self.__db.finalize()

		if not self.__db.is_debug:
			self.__updated = True
		return True

	def __update_domain_list(self, domain_type: int, domains_remote: set, install_comment: str):
		if not self.__valid:
			return False

		if not domains_remote:
			return False

		if not self.__db.cursor:
			return False

		print(f'[i] Adding / updating type({domain_type}) comment({install_comment})')
		sorted_domains = sorted(domains_remote)
		self.__db.cursor.executemany('INSERT OR IGNORE INTO domainlist (type, domain, enabled, comment) '
									'VALUES(?, ?, 1, ?)',
									[(domain_type, x, install_comment) for x in sorted_domains])
		self.__db.cursor.executemany('UPDATE domainlist '
									'SET comment = ? WHERE domain in (?) AND comment != ?',
									[(install_comment, x, install_comment) for x in sorted_domains])

		self.__db.finalize()

		print(f'[i] removing obsolete type({domain_type})')
		# fetch existing
		self.__db.cursor.execute('SELECT domain FROM domainlist WHERE type = ? AND comment = ?', (domain_type, install_comment,))
		domains_local_results = self.__db.cursor.fetchall()
		domains_local = set()
		domains_local.update([x[0] for x in domains_local_results])
		# remove any local that do not exist in the fetched list
		domains_remove = domains_local.difference(domains_remote)

		if domains_remove:
			self.__db.cursor.executemany('DELETE FROM domainlist WHERE type = ? AND domain in(?)', [(domain_type, x,) for x in domains_remove])
		self.__db.finalize()

		if not self.__db.is_debug:
			self.__updated = True
		return True

	def __update_adlist_list(self, adlist_list_remote: set, install_comment: str):
		if not self.__valid:
			return False

		if not adlist_list_remote:
			return False

		if not self.__db.cursor:
			return False

		print('[i] Adding / updating adlist')
		sorted_adlist = sorted(adlist_list_remote)
		self.__db.cursor.executemany('INSERT OR IGNORE INTO adlist (address, enabled, comment) '
									'VALUES(?, 1, ?)',
									[(x, install_comment) for x in sorted_adlist])
		self.__db.cursor.executemany('UPDATE adlist '
									'SET comment = ? WHERE address in (?) AND comment != ?',
									[(install_comment, x, install_comment) for x in sorted_adlist])
		self.__db.finalize()

		print('[i] removing obsolete adlist')
		# fetch existing
		self.__db.cursor.execute('SELECT address FROM adlist WHERE comment = ?', (install_comment,))
		adlist_list_local_results = self.__db.cursor.fetchall()
		adlist_list_local = set()
		adlist_list_local.update([x[0] for x in adlist_list_local_results])
		# remove any local that do not exist in the fetched list
		adlist_list_remove = adlist_list_local.difference(adlist_list_remote)
	
		if adlist_list_remove:
			self.__db.cursor.executemany('DELETE FROM adlist WHERE address in(?)', [(x,) for x in adlist_list_remove])
		self.__db.finalize()

		if not self.__db.is_debug:
			self.__updated = True
		return True


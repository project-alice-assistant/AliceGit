#  Copyright (c) 2021
#
#  This file, Git.py, is part of Project Alice.
#
#  Project Alice is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>
#
#  Last modified: 2021.11.15 at 14:35:51 CET
from __future__ import annotations

import os
import re
import requests
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Callable, List, Tuple, Union

from .Exceptions import AlreadyGitRepository, DirtyRepository, InvalidUrl, NotGitRepository, PathNotFoundException, RemoteAlreadyExists


class Repository(object):

	def __init__(self, directory: Union[str, Path], makeDir: bool = False, init: bool = False, url: str = '', raiseIfExisting: bool = False, quiet: bool = True):
		if isinstance(directory, str):
			directory = Path(directory)

		if not directory.exists() and not makeDir:
			raise PathNotFoundException(directory)

		if directory.exists() and not Path(directory, '.git').exists() and not init:
			raise NotGitRepository(directory)

		directory.mkdir(parents=True, exist_ok=True)

		self.path      = directory
		self._quiet    = quiet
		self.url       = url

		isRepository = self.isRepository(directory=directory)
		if init:
			if not isRepository:
				self.execute(f'git init')
			else:
				if raiseIfExisting:
					raise AlreadyGitRepository
		else:
			if not isRepository:
				raise NotGitRepository


	@property
	def tags(self):
		return set(self.execute('git tag')[0].split('\n'))

	@property
	def branches(self):
		return set(self.execute('git branch')[0].split('\n'))

	@property
	def remote(self) -> dict[Remote]:
		remotes = self.execute('git remote -v')[0]
		if len(remotes) > 0:
			return dict((rem.user, rem) for rem in [Remote(repository=self, remoteString=r) for r in remotes.split('\n')])
		else:
			return dict()


	@classmethod
	def clone(cls, url: str, directory: Union[str, Path], branch: str = 'master', makeDir: bool = False, force: bool = False, quiet: bool = True) -> Repository:
		if isinstance(directory, str):
			directory = Path(directory)

		response = requests.get(url)
		if response.status_code != 200:
			raise InvalidUrl(url)

		if not directory.exists() and not makeDir:
			raise PathNotFoundException(directory)

		if cls.isRepository(directory=directory):
			if not force:
				raise AlreadyGitRepository(directory)
			else:
				shutil.rmtree(str(directory), onerror=cls.fixPermissions)

		directory.mkdir(parents=True, exist_ok=True)
		cmd = f'git clone {url} {str(directory)} --branch {branch} --recurse-submodules'
		if quiet:
			cmd = f'{cmd} --quiet'
		subprocess.run(cmd, shell=True, capture_output=True, text=True)
		return Repository(directory=directory, url=url, quiet=quiet)


	@staticmethod
	def isRepository(directory: Union[str, Path]) -> bool:
		if directory and isinstance(directory, str):
			directory = Path(directory)

		gitDir = directory / '.git'
		if not gitDir.exists():
			return False

		expected = [
			'hooks',
			'info',
			'objects',
			'refs',
			'config',
			'description',
			'HEAD'
		]

		for item in expected:
			if not Path(gitDir, item).exists():
				return False
		return True


	def checkout(self, branch: str = 'master', tag: str = '', force: bool = False):
		if tag:
			target = f'tags/{tag} -B Branch_{tag}'
		else:
			target = branch

		if not target:
			raise Exception('Checkout target cannot be empty§')

		if self.isDirty():
			if not force:
				raise DirtyRepository()
			else:
				self.revert()

		self.execute(f'git checkout {target} --recurse-submodules')


	def status(self) -> Status:
		return Status(directory=self.path)


	def isDirty(self) -> bool:
		status = self.status()
		return status.isDirty()


	def isUpToDate(self) -> bool:
		status = self.status()
		return status.isUpToDate()


	def revert(self):
		self.reset()
		self.clean()
		self.execute('git checkout HEAD')


	def listStash(self) -> List[str]:
		result = self.execute(f'git stash list')[0]
		return result.split('\n')


	def stash(self) -> int:
		self.execute(f'git stash push {str(self.path)}/')
		return len(self.listStash()) - 1


	def dropStash(self, index: Union[int, str] = -1) -> List[str]:
		if index == 'all':
			self.execute(f'git stash clear')
			return list()
		else:
			self.execute(f'git stash drop {index}')
			return self.listStash()


	def pull(self, force: bool = False, pullSubmodules: bool = False):
		if self.isDirty():
			if not force:
				raise DirtyRepository()
			else:
				self.revert()

		self.execute('git pull')

		if pullSubmodules:
			self.pullSubmodules(force=force)


	def pullSubmodules(self, force: bool = False):
		if force:
			self.execcute('git submodule foreach git stash')

		self.execute('git submodule foreach git pull')


	def fetch(self, fetchSubmodules: bool = False):
		self.execute('git fetch')

		if fetchSubmodules:
			self.fetchSubmodules()


	def fetchSubmodules(self):
		self.execute('git submodule foreach git fetch')


	def reset(self):
		self.execute('git reset --hard')


	def clean(self, removeUntrackedFiles: bool = True, removeUntrackedDirectory: bool = True, removeIgnored: bool = False):
		options = ''
		if removeUntrackedFiles:
			options += 'f'
		if removeUntrackedDirectory:
			options += 'd'
		if removeIgnored:
			options += 'x'
		if options:
			options = f'-{options}'

		self.execute(f'git clean {options}')


	def restore(self):
		self.execute(f'git restore {str(self.path)}', noDashCOption=True)


	def destroy(self):
		shutil.rmtree(self.path, onerror=self.fixPermissions)


	@staticmethod
	def fixPermissions(func: Callable, path: Path, *_args):
		if not os.access(path, os.W_OK):
			os.chmod(path, stat.S_IWUSR)
			func(path)
		else:
			raise # NOSONAR


	def execute(self, command: str, noDashCOption: bool = False) -> Tuple[str, str]:
		if not command.startswith('git -C') and not noDashCOption:
			command = command.replace('git', f'git -C {str(self.path)}', 1)

		if self._quiet \
				and 'remote' not in command\
				and 'add' not in command:
			command = f'{command} --quiet'

		result = subprocess.run(command, capture_output=True, text=True, shell=True)
		return result.stdout.strip(), result.stderr.strip()


	def add(self):
		self.execute('git add --all')


	def commit(self, message: str = '', autoAdd: bool = False) -> bool:
		"""
		commit all changes in the tree
		:param message:
		:param autoAdd: add --all before committing
		:return: True if there was something to commit, and it succeeds
		"""
		if not message:
			message = 'Commit by ProjectAliceBot'

		if autoAdd:
			out, err = self.execute('git add --all')
			if err:
				return False

		cmd = f'git commit -m "{message}"'
		out, err = self.execute(cmd)
		if err or 'nothing to commit' in out:
			return False
		else:
			return True


	def push(self, repository: str = 'AliceSK', upstream: str = 'AliceSK', branch: str = 'master') -> Tuple[str, str]:
		out, err = self.execute(f'git push --repo={repository} --set-upstream {upstream} {branch}')
		return out, err


	def config(self, key: str, value: str, isGlobal: bool = False):
		mode = '--global' if isGlobal else '--local'
		self.execute(f'git config {mode} {key} {value}')


	def remoteAdd(self, url: str, name: str = 'origin') -> bool:
		self.url = url
		out, err = self.execute(f'git remote add {name} {url}')
		if 'already exists' in err:
			raise RemoteAlreadyExists(name=name)
		if err:
			return False
		else:
			return True


	def file(self, filePath: Union[str, Path]) -> Path:
		if isinstance(filePath, str):
			filePath = Path(filePath)

		return self.path / filePath


	@property
	def quiet(self) -> bool:
		return self._quiet


	@quiet.setter
	def quiet(self, value: bool):
		self._quiet = value


class Status(object):

	def __init__(self, directory: Union[str, Path]):
		if isinstance(directory, str):
			directory = Path(directory)

		self._directory = directory


	def isDirty(self) -> bool:
		status = subprocess.run(f'git -C {str(self._directory)} status', capture_output=True, text=True, shell=True).stdout.strip()
		if 'working tree clean' not in status:
			return True
		revList = subprocess.run(f'git -C {str(self._directory)} rev-list --count origin/master..HEAD', capture_output=True, text=True, shell=True).stdout.strip()
		try:
			if int(revList) > 0:
				return True
		except ValueError as e:
			print(f'VALUE ERROR: {str(e)}')
			return True
		return False


	def isUpToDate(self) -> bool:
		subprocess.run(f'git -C {str(self._directory)} fetch origin', shell=True)
		status = subprocess.run(f'git -C {str(self._directory)} status', capture_output=True, text=True, shell=True).stdout.strip()
		return 'Your branch is up to date with' in status


	def changes(self) -> dict:
		"""
		get changed files with their type (unstaged, modified etc.)
		:return:
		"""
		changes = dict()
		status = subprocess.run(f'git -C {str(self._directory)} status --porcelain', capture_output=True, text=True, shell=True).stdout.strip()
		for line in status.split('\n'):
			element = line.strip().split(' ')
			if len(element) > 1:
				changes[element[1]] = element[0]
		return changes



class Remote(object):

	def __init__(self, repository: Repository, name: str = None, url: str = None, user: str = None, type: str = '', remoteString: str = None):
		"""
		:param name:
		:param url:
		:param user: if not supplied is extracted from url/statusString
		:param statusString: e.g. "origin  https://github.com/project-alice-assistant/skill_AliceCore.git (push)"
		"""
		self.repository: Repository = repository
		self.name = name
		self.url = url
		self.user = user
		self.type = type

		if remoteString:
			rest, self.type = remoteString.split(' ')
			self.name, self.url = rest.split('\t')

		if not self.user:
			match = re.search('github.com/(.+?)/', self.url)
			if match:
				self.user = match.group(1)


	def getCommitCount(self, branch: str = 'master', ahead: bool = True) -> int:
		"""
		Returns the number of commits the current HEAD is in front of the given branch
		:param branch:
		:param ahead: True: get the number the remote is ahead of HEAD; False: get the commits, remote is behind of HEAD
		:return:
		"""
		subprocess.run(f'git -C {str(self.repository.path)} fetch', shell=True)
		ref = f'{self.name}/{branch}..HEAD' if ahead else f'HEAD..{self.name}/{branch}'
		proc = subprocess.run(f'git -C {str(self.repository.path)} rev-list --count {ref}', shell=True, capture_output=True, text=True)
		if not proc.stdout:
			return proc.stderr

		return int(proc.stdout.strip())

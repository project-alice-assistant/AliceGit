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

import json
import requests
from pathlib import Path
from typing import Dict, Optional, Tuple

from .Exceptions import GithubAlreadyForked, GithubCreateFailed, GithubForkFailed, GithubRateLimit, GithubRepoNotFound, GithubUserNotFound


class Github(object):

	def __init__(self, username: str = '', token: str = '', repositoryName: str = '', createRepository: bool = False, options: Dict = None, officialUser: str = 'project-alice-assistant'):
		if not username or not token or not repositoryName:
			raise Exception('Please provide username, token and repository name!')

		self.token = token
		self.auth = (username, token)
		self.repositoryName = repositoryName

		self.username = username
		self.officialUser = officialUser

		self.usersUrl = f'https://{self.username}:{self.token}@github.com/{self.username}/{self.repositoryName}.git'
		self.officialUrl = f'https://github.com/{self.officialUser}/{self.repositoryName}.git'

		self.checkUsers()

		# first get the status/remotes for all repositories - set to none if not existing
		self.usersRemote: Optional[Remote] = self.getRemote(url=self.usersUrl)
		self.officialRemote: Optional[Remote] = self.getRemote(url=self.officialUrl)

		# only creation of users repositories is possible
		if createRepository:
			self.handleCreation(options=options)

		# if both repositories don't exist we have a problem.
		if self.usersRemote is None and self.officialRemote is None:
			raise GithubRepoNotFound(repositoryName=repositoryName)

	def handleCreation(self, options: Dict = None):
		"""
		Checks if the users repository is missing, if so either forks from official or creates a new repository
		:return:
		"""
		if self.usersRemote is None:
			# if there is no official repository, create a users repository from scratch!
			if self.officialRemote is None:
				self.usersRemote = self.createRepository(repositoryName=self.repositoryName, options=options)
			# else, fork the repository!
			else:
				self.usersRemote = self.officialRemote.fork()


	def checkUsers(self):
		"""
		check both supplied users for their existence and raise the corresponding exception.
		:return:
		"""
		response = requests.get(f'https://github.com/{self.username}')
		if response.status_code != 200:
			raise GithubUserNotFound(username=self.username)

		response = requests.get(f'https://github.com/{self.officialUser}')
		if response.status_code != 200:
			raise GithubUserNotFound(username=self.officialUser)

	def getRemote(self, url: str) -> Remote:
		"""
		get the remote for a given url using the objects auth
		:param url:
		:return: None when the repo not exists, else a Remote Object
		"""
		try:
			self.getStatusForUrl(url)
			return Remote(url=url, apiAuth=self.auth)
		except GithubRepoNotFound:
			return None

	@staticmethod
	def getStatusForUrl(url: str, silent: bool = False):
		response = requests.get(url)
		if response.status_code != 200:
			if silent:
				return False
			else:
				raise GithubRepoNotFound(repositoryName=url)
		return response

	def createRepository(self, repositoryName: str, repositoryDescription: str = '', options: Dict = None) -> Remote:
		"""
		Creates a repository on Github
		:param repositoryName:
		:param repositoryDescription:
		:param options:
		:return:
		"""
		if not options:
			options = {
				'name'       : repositoryName,
				'description': repositoryDescription,
				'has-issues' : True
			}

		response = requests.post('https://api.github.com/user/repos', data=json.dumps(options), auth=self.auth)

		if response.status_code == 429:
			raise GithubRateLimit(username=self.username)
		elif response.status_code not in [200, 201]:
			raise GithubCreateFailed(repositoryName=repositoryName, statusCode=response.status_code)
		else:
			return Remote(url=self.usersUrl, apiAuth=self.auth)


class Remote(object):
	def __init__(self, url: str, apiAuth: Tuple[str, str]):
		self.auth = apiAuth
		self.url = url


	def fork(self):
		owner = Path(self.url).parent.stem
		repo = Path(self.url).stem

		if str(owner).lower() == self.auth[0].lower():
			raise Exception('Cannot fork own repository')

		url = f'https://github.com/{self.auth[0]}/{repo}.git'
		response = requests.get(url)
		if response.status_code != 404:
			raise GithubAlreadyForked(repository=repo)

		response = requests.post(
			url=f'https://api.github.com/repos/{owner}/{repo}/forks',
			auth=self.auth
		)

		if response.status_code == 429:
			raise GithubRateLimit(username=self.auth[0])
		elif response.status_code != 202:
			raise GithubForkFailed(repository=repo)
		else:
			return Remote(url=url, apiAuth=self.auth)

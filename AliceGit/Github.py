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

	def __init__(self, username: str = '', token: str = '', repositoryName: str = '', useUrlInstead: str = '', createRepository: bool = False, options: Dict = None, officialUser: str = 'project-alice-assistant'):
		if not useUrlInstead and (not username or not token or not repositoryName):
			raise Exception('Please provide username, token and repository name if you are not using useUrlInstead')
		elif useUrlInstead and createRepository:
			raise Exception('createRepository is not compatible with useUrlInstead')
		elif useUrlInstead and (not username or not token):
			raise Exception('Please provide your Github username and token')

		self.username = username
		self.token = token
		self.auth = (username, token)
		self.remote: Optional[Remote] = None

		if not useUrlInstead:
			self.officialUrl = f'https://github.com/{officialUser}/{repositoryName}.git'
			self.repositoryName = repositoryName

			response = requests.get(f'https://github.com/{username}')
			if response.status_code != 200:
				raise GithubUserNotFound(username=username)

			# first try the user specific repository!
			self.usersUrl = f'https://github.com/{username}/{repositoryName}.git'
			response = requests.get(self.usersUrl)
			if response.status_code != 200 and not createRepository:
				# check if at least the official repository exists
				response = requests.get(self.officialUrl)
				if response.status_code != 200:
					raise GithubRepoNotFound(repositoryName=repositoryName)
				else:
					self.usersUrl = None
			elif response.status_code != 200 and createRepository:
				self.remote = self.createRepository(repositoryName=repositoryName, options=options)
			else:
				self.remote = Remote(url=self.usersUrl, apiAuth=self.auth)
		else:
			self.officialUrl = None
			self.usersUrl = useUrlInstead
			self.repositoryName = Path(self.usersUrl).stem
			response = requests.get(self.usersUrl)
			if response.status_code != 200:
				raise GithubRepoNotFound(repositoryName=repositoryName)

			self.remote = Remote(url=self.usersUrl, apiAuth=self.auth)

	@property
	def url(self):
		"""
		property to keep the old .url alive even with two remotes
		:return:
		"""
		return self.usersUrl

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
		elif response.status_code != 200:
			raise GithubCreateFailed(repositoryName=repositoryName, statusCode=response.status_code)
		else:
			return Remote(url=self.url, apiAuth=self.auth)


	def repositoryExists(self) -> bool:
		self.url = f'https://github.com/{self.username}/{self.repositoryName}.git'
		response = requests.get(self.url)
		return response.status_code == 200


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

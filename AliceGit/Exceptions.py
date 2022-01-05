from pathlib import Path


class PathNotFoundException(Exception):
	def __init__(self, path: Path):
		super().__init__(f'Path "{path}" does not exist')


class NotGitRepository(Exception):
	def __init__(self, path: Path):
		super().__init__(f'Directory "{path}" is not a git repository')


class AlreadyGitRepository(Exception):
	def __init__(self, path: Path):
		super().__init__(f'Directory "{path}" is already a git repository')


class InvalidUrl(Exception):
	def __init__(self, url: str):
		super().__init__(f'The provided url "{url}" is not valid')


class DirtyRepository(Exception):
	def __init__(self):
		super().__init__(f'The repository is dirty. Either use the force option or stash your changes before trying again')


class GithubUserNotFound(Exception):
	def __init__(self, username: str):
		super().__init__(f"User {username} doesn't seem to exist on Github")


class GithubRepoNotFound(Exception):
	def __init__(self, repositoryName: str):
		super().__init__(f"Repository {repositoryName} doesn't seem to exist on Github")


class GithubCreateFailed(Exception):
	def __init__(self, repositoryName: str, statusCode: int):
		super().__init__(f"Failed creating {repositoryName} on Github with status code {statusCode}")


class GithubRateLimit(Exception):
	def __init__(self, username: str):
		super().__init__(f"You've reached the API rate limit for user {username}")


class GithubForkFailed(Exception):
	def __init__(self, repository: str):
		super().__init__(f'Failed forking {repository}')


class GithubAlreadyForked(Exception):
	def __init__(self, repository: str):
		super().__init__(f'The repository {repository} is already forked')


class RemoteAlreadyExists(Exception):
	def __init__(self, name: str):
		super().__init__(f'The remote {name} is already defined')


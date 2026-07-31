"""Custom exceptions for the AFM core engine."""


class AFMError(Exception):
    """Base class for all AFM-related errors."""


class ProjectAlreadyExistsError(AFMError):
    """Raised when trying to init a project on a folder that is already an AFM project."""


class ProjectNotFoundError(AFMError):
    """Raised when project_config.yaml cannot be found / is invalid."""


class StepNotFoundError(AFMError):
    """Raised when a referenced step does not exist in the project."""


class StepAlreadyExistsError(AFMError):
    """Raised when trying to create a step that already exists."""


class VersionNotFoundError(AFMError):
    """Raised when a referenced version id / name cannot be found."""


class VersionAlreadyExistsError(AFMError):
    """Raised when the generated version folder name collides with an existing one."""


class InvalidNamingRuleError(AFMError):
    """Raised when a naming-rule definition is invalid (e.g. all components disabled)."""


class InvalidFolderRuleError(AFMError):
    """Raised when a folder rule is missing a required folder (data / outputs)."""

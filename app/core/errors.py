class ContentError(Exception):
    """Base content-layer error."""


class NotFoundError(ContentError):
    """Raised when a repository entity is not found."""


class ValidationError(ContentError):
    """Raised when content validation fails."""


class LicensePolicyError(ContentError):
    """Raised when source license policy fails."""


class ReviewRequiredError(ContentError):
    """Raised when canonical promotion lacks required human review."""


class PublicationConstraintError(ContentError):
    """Raised when a canonical rendering fails publication constraints."""


class GenerationError(ContentError):
    """Raised when local-model generation or orchestration fails."""


class ReleaseValidationError(ContentError):
    """Raised when release validation fails required policy gates."""

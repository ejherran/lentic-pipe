"""
Permission helpers.

System roles (User.system_role):
  admin      — full access to all resources and user management
  researcher — can create experiments and run models
  viewer     — read-only access to own resources and collaborations

Experiment roles (ExperimentCollaborator.role):
  owner  — full control including collaborator management and deletion
  editor — can add datasets, create runs, predictions, simulations
  viewer — read-only on all experiment resources
"""
from src.api.models.experiment import CollaboratorRole
from src.api.models.user import SystemRole

# Ordered hierarchy for experiment roles (higher index = more permissions)
_EXPERIMENT_ROLE_RANK = {
    CollaboratorRole.viewer: 0,
    CollaboratorRole.editor: 1,
    CollaboratorRole.owner: 2,
}


def experiment_role_gte(actual: CollaboratorRole, required: CollaboratorRole) -> bool:
    return _EXPERIMENT_ROLE_RANK[actual] >= _EXPERIMENT_ROLE_RANK[required]


def is_admin(system_role: SystemRole) -> bool:
    return system_role == SystemRole.admin


def can_create_experiments(system_role: SystemRole) -> bool:
    return system_role in (SystemRole.admin, SystemRole.researcher)

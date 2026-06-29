"""Shared OpenAPI response descriptors — reused across all routers."""

HTTP_401 = {401: {"description": "Missing or invalid Bearer token."}}
HTTP_403 = {403: {"description": "Authenticated but not authorized for this resource."}}
HTTP_404 = {404: {"description": "Resource not found."}}
HTTP_409 = {409: {"description": "Conflict — resource already exists."}}
HTTP_422 = {422: {"description": "Validation error in request body or query parameters."}}
HTTP_429 = {429: {"description": "Rate limit exceeded. Retry after the stated interval."}}

# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""HTTP route handlers — thin wrappers around bundle/server and social/server."""

from peerpedia_core.transport.routes.articles import ROUTES as ARTICLE_ROUTES
from peerpedia_core.transport.routes.users import ROUTES as USER_ROUTES

ALL_ROUTES = ARTICLE_ROUTES + USER_ROUTES

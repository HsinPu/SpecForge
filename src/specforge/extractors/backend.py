from __future__ import annotations

import ast
import json
import io
import re
import tokenize
import xml.etree.ElementTree as ET
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

from specforge.extractors.dart import dart_api_route_map
from specforge.models import (
    ApiRouteFact,
    BackendSurfaceFact,
    Evidence,
    FileFact,
    FrameworkFact,
    RequestParamFact,
    SymbolFact,
)


EXPRESS_ROUTE_RE = re.compile(
    r"\b(?:app|router|server)\.(?P<method>get|post|put|delete|patch|options|head|all)"
    r"\(\s*['\"`](?P<path>/[^'\"`]*|\*)['\"`]\s*(?:,\s*(?P<handler>[A-Za-z_$][\w$.\[\]]+))?",
    re.IGNORECASE,
)
EXPRESS_LOCAL_IMPORT_RE = re.compile(
    r"\bimport\s+(?P<name>[A-Za-z_$][\w$]*)\s+from\s*['\"](?P<module>\.[^'\"]+)['\"]",
    re.MULTILINE,
)
EXPRESS_LOCAL_REQUIRE_RE = re.compile(
    r"\b(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*require\(\s*['\"](?P<module>\.[^'\"]+)['\"]\s*\)",
    re.MULTILINE,
)
EXPRESS_ROUTER_CHAIN_RE = re.compile(
    r"\b(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*Router\(\)(?P<chain>[\s\S]*?);",
    re.MULTILINE,
)
EXPRESS_CHAIN_USE_RE = re.compile(r"\.use\(\s*(?P<target>[A-Za-z_$][\w$]*)\s*\)")
EXPRESS_MOUNT_USE_RE = re.compile(
    r"\b(?:Router\(\)|[A-Za-z_$][\w$]*)\.use\(\s*['\"`](?P<prefix>/[^'\"`]*)['\"`]\s*,\s*(?P<target>[A-Za-z_$][\w$]*)",
    re.IGNORECASE,
)
HONO_APP_RE = re.compile(
    r"\b(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*"
    r"(?:new\s+(?:Hono|OpenAPIHono)\b|createRouter\s*\()",
    re.IGNORECASE,
)
HONO_TYPED_RECEIVER_RE = re.compile(r"\b(?P<name>[A-Za-z_$][\w$]*)\s*:\s*(?:AppOpenAPI|OpenAPIHono|Hono)\b")
HONO_ROUTE_RE = re.compile(
    r"\b(?P<receiver>[A-Za-z_$][\w$]*)\.(?P<method>get|post|put|delete|patch|all|on|doc)"
    r"\(\s*['\"`](?P<path>[^'\"`]+)['\"`](?P<args>[\s\S]{0,1200}?)\)",
    re.IGNORECASE,
)
HONO_CHAIN_ROUTE_RE = re.compile(
    r"^\s*\.(?P<method>get|post|put|delete|patch|all|on|doc)"
    r"\(\s*['\"`](?P<path>[^'\"`]+)['\"`](?P<args>[\s\S]{0,1200}?)\)",
    re.IGNORECASE | re.MULTILINE,
)
HONO_MOUNT_RE = re.compile(
    r"\b(?P<receiver>[A-Za-z_$][\w$]*)\.route\(\s*['\"`](?P<prefix>[^'\"`]+)['\"`]\s*,\s*(?P<child>[A-Za-z_$][\w$]*)",
    re.IGNORECASE,
)
HONO_CHAIN_MOUNT_RE = re.compile(
    r"^\s*\.route\(\s*['\"`](?P<prefix>[^'\"`]+)['\"`]\s*,\s*(?P<child>[A-Za-z_$][\w$]*)",
    re.IGNORECASE | re.MULTILINE,
)
HONO_LOCAL_IMPORT_RE = re.compile(
    r"\bimport\s+(?:(?P<default>[A-Za-z_$][\w$]*)\s*,?\s*)?(?:\{\s*(?P<named>[^}]+)\s*\}\s*)?"
    r"from\s*['\"](?P<module>\.[^'\"]+)['\"]",
    re.MULTILINE,
)
HONO_OPENAPI_ROUTE_DECL_RE = re.compile(
    r"(?:export\s+)?const\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*createRoute\s*\(",
    re.IGNORECASE,
)
HONO_STATUS_CODE_NAMES = {
    "OK": "200",
    "CREATED": "201",
    "ACCEPTED": "202",
    "NO_CONTENT": "204",
    "BAD_REQUEST": "400",
    "UNAUTHORIZED": "401",
    "FORBIDDEN": "403",
    "NOT_FOUND": "404",
    "CONFLICT": "409",
    "UNPROCESSABLE_ENTITY": "422",
    "INTERNAL_SERVER_ERROR": "500",
}
FRESH_HANDLER_RE = re.compile(r"\bexport\s+const\s+handler\b[\s\S]{0,120}?=\s*(?:define\.handlers\()?\s*\{", re.MULTILINE)
FRESH_HANDLER_METHOD_RE = re.compile(r"^\s*(?:async\s+)?(?P<method>GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s*(?:\(|:)", re.MULTILINE)
ELYSIA_ROUTE_RE = re.compile(
    r"\.(?P<method>get|post|put|patch|delete|options|head|all)"
    r"\(\s*['\"`](?P<path>/[^'\"`]*|\*)['\"`](?P<args>[\s\S]{0,900}?)\)",
    re.IGNORECASE,
)
ELYSIA_PREFIX_RE = re.compile(r"\bnew\s+Elysia\s*\(\s*\{[\s\S]{0,240}?\bprefix\s*:\s*['\"`](?P<prefix>/[^'\"`]*)['\"`]", re.IGNORECASE)
ELYSIA_GROUP_RE = re.compile(r"\.group\(\s*['\"`](?P<prefix>/[^'\"`]*)['\"`]", re.IGNORECASE)
QWIK_CITY_HANDLER_RE = re.compile(r"\bexport\s+const\s+(?P<name>on(?:Request|Get|Post|Put|Delete|Patch|Head|Options))\b", re.IGNORECASE)
KOA_ROUTE_RE = re.compile(
    r"\brouter\.(?P<method>get|post|put|del|delete|patch|options|head|all)"
    r"\(\s*['\"`](?P<path>[^'\"`]+)['\"`](?P<args>[^\n;]*)",
    re.IGNORECASE,
)
KOA_MOUNT_RE = re.compile(r"\brouter\.use\(\s*['\"`](?P<prefix>/[^'\"`]*)['\"`]\s*,\s*[A-Za-z_$][\w$]*\.routes\(\)")
HAPI_METHOD_RE = re.compile(
    r"\bmethod\s*:\s*(?:['\"`](?P<method>GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD|ANY)['\"`]|\[(?P<methods>[^\]]+)\])",
    re.IGNORECASE | re.DOTALL,
)
HAPI_PATH_RE = re.compile(r"\bpath\s*:\s*['\"`](?P<path>[^'\"`]+)['\"`]", re.IGNORECASE)
HAPI_HANDLER_RE = re.compile(r"\bhandler\s*:\s*(?P<handler>[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)", re.IGNORECASE)
HAPI_INLINE_HANDLER_RE = re.compile(
    r"\bhandler\s*:\s*(?:async\s*)?(?:function\b|\([^)]*\)\s*=>|[A-Za-z_$][\w$]*\s*=>)",
    re.IGNORECASE | re.DOTALL,
)
HAPI_AUTH_RE = re.compile(r"\bauth\s*:\s*['\"`](?P<auth>[^'\"`]+)['\"`]", re.IGNORECASE)
HAPI_VALIDATE_RE = re.compile(r"\bvalidate\s*:\s*(?P<validate>[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)", re.IGNORECASE)
HAPI_RESPONSE_RE = re.compile(r"\bresponse\s*:\s*(?P<response>[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)", re.IGNORECASE)
HAPI_PLUGIN_PREFIX_RE = re.compile(
    r"register\s*:\s*['\"]\./api['\"][\s\S]{0,500}?routes\s*:\s*\{[\s\S]{0,160}?prefix\s*:\s*['\"`](?P<prefix>/[^'\"`]*)['\"`]",
    re.IGNORECASE,
)
ADONIS_ROUTE_RE = re.compile(
    r"\bRoute\.(?P<method>get|post|put|patch|delete|options|head|any)"
    r"\(\s*['\"`](?P<path>[^'\"`]*)['\"`]\s*,\s*['\"`](?P<handler>[^'\"`]+)['\"`]",
    re.IGNORECASE,
)
ADONIS_RESOURCE_RE = re.compile(
    r"\bRoute\.resource\(\s*['\"`](?P<path>[^'\"`]*)['\"`]\s*,\s*['\"`](?P<handler>[^'\"`]+)['\"`]\s*\)(?P<chain>[^\n;]*)",
    re.IGNORECASE,
)
SAILS_ROUTE_KEY_RE = re.compile(
    r"['\"](?:(?P<method>GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD|ALL)\s+)?(?P<path>/[^'\"]*)['\"]\s*:",
    re.IGNORECASE,
)
SAILS_ACTION_RE = re.compile(r"\baction\s*:\s*['\"`](?P<action>[^'\"`]+)['\"`]", re.IGNORECASE)
SAILS_VIEW_RE = re.compile(r"\bview\s*:\s*['\"`](?P<view>[^'\"`]+)['\"`]", re.IGNORECASE)
LOOPBACK_ROUTE_RE = re.compile(
    r"@\s*(?P<method>get|post|put|patch|del|delete|head|options)\s*"
    r"\(\s*['\"`](?P<path>[^'\"`]+)['\"`]",
    re.IGNORECASE,
)
LOOPBACK_METHOD_RE = re.compile(
    r"(?:(?:public|private|protected|static|async)\s+)*"
    r"(?P<name>[A-Za-z_$][\w$]*)\s*\(",
    re.MULTILINE,
)
FEATHERS_SERVICE_USE_RE = re.compile(
    r"\bapp\.use\(\s*['\"`](?P<path>/[^'\"`]+)['\"`](?P<args>[^\n;]*)",
    re.IGNORECASE,
)
FEATHERS_APP_MOUNT_RE = re.compile(
    r"\b(?:[A-Za-z_$][\w$]*|express\s*\(\s*\))\.use\(\s*['\"`](?P<prefix>/[^'\"`]*)['\"`]\s*,\s*(?P<app>[A-Za-z_$][\w$]*)\s*\)",
    re.IGNORECASE,
)
FEATHERS_SERVICE_METHODS = {
    "find": ("GET", ""),
    "get": ("GET", "{id}"),
    "create": ("POST", ""),
    "update": ("PUT", "{id}"),
    "patch": ("PATCH", "{id}"),
    "remove": ("DELETE", "{id}"),
}
STRAPI_CORE_ROUTER_RE = re.compile(
    r"\bcreateCoreRouter\(\s*['\"`](?P<uid>api::[^'\"`]+)['\"`]",
    re.IGNORECASE,
)
STRAPI_METHOD_RE = re.compile(r"\bmethod\s*:\s*['\"`](?P<method>GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)['\"`]", re.IGNORECASE)
STRAPI_PATH_RE = re.compile(r"\bpath\s*:\s*['\"`](?P<path>/[^'\"`]+)['\"`]", re.IGNORECASE)
STRAPI_HANDLER_RE = re.compile(r"\bhandler\s*:\s*['\"`](?P<handler>[^'\"`]+)['\"`]", re.IGNORECASE)
FASTIFY_ROUTE_CALL_RE = re.compile(r"\b(?:fastify|server|app)\.route\(\s*\{", re.IGNORECASE)
FASTIFY_SHORTHAND_ROUTE_RE = re.compile(
    r"\b(?:fastify|server|app)\.(?P<method>get|post|put|delete|patch|options|head|all)"
    r"\(\s*['\"`](?P<path>[^'\"`]+)['\"`]\s*(?:,\s*(?P<handler>[A-Za-z_$][\w$.\[\]]+))?",
    re.IGNORECASE,
)
FASTIFY_AUTOPREFIX_RE = re.compile(
    r"\b(?:export\s+)?const\s+autoPrefix\s*=\s*['\"`](?P<prefix>/[^'\"`]*)['\"`]",
    re.IGNORECASE,
)
FASTIFY_METHOD_RE = re.compile(
    r"\bmethod\s*:\s*(?:['\"`](?P<method>[A-Za-z]+)['\"`]|\[(?P<methods>[^\]]+)\])",
    re.IGNORECASE | re.DOTALL,
)
FASTIFY_PATH_RE = re.compile(r"\b(?:path|url)\s*:\s*['\"`](?P<path>[^'\"`]+)['\"`]", re.IGNORECASE)
FASTIFY_HANDLER_RE = re.compile(r"\bhandler\s*:\s*(?P<handler>[A-Za-z_$][\w$.\[\]]*)", re.IGNORECASE)
ACTIX_SCOPE_RE = re.compile(r"\bweb::scope\(\s*['\"](?P<path>[^'\"]*)['\"]")
ACTIX_RESOURCE_RE = re.compile(r"\bweb::resource\(\s*['\"](?P<path>[^'\"]*)['\"]")
ACTIX_ROUTE_METHOD_RE = re.compile(
    r"\.route\(\s*web::(?P<method>get|post|put|delete|patch|head|options)\(\)\."
    r"(?:to|to_async)\(\s*(?P<handler>[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*)",
    re.IGNORECASE,
)
ACTIX_TO_RE = re.compile(r"\.(?:to|to_async)\(\s*(?P<handler>[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*)")
ACTIX_ATTR_ROUTE_RE = re.compile(
    r"#\[\s*(?P<method>get|post|put|delete|patch|head|options)\(\s*['\"](?P<path>[^'\"]+)['\"]",
    re.IGNORECASE,
)
ROCKET_ATTR_ROUTE_RE = re.compile(
    r"#\[\s*(?P<method>get|post|put|delete|patch|head|options)\(\s*['\"](?P<path>[^'\"]+)['\"](?P<args>[^\]]*)\)\s*\]",
    re.IGNORECASE,
)
ROCKET_MOUNT_RE = re.compile(r"\.mount\(\s*['\"](?P<prefix>[^'\"]*)['\"]\s*,\s*routes!\s*\[", re.DOTALL)
WARP_PATH_ROUTE_RE = re.compile(
    r"warp::path!\((?P<path>[^)]*)\)(?P<chain>[\s\S]{0,700}?)"
    r"\.(?:map_async|and_then|map)\(\s*(?P<handler>[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*)",
    re.MULTILINE,
)
TAURI_COMMAND_RE = re.compile(
    r"#\s*\[\s*(?P<qualified>tauri::)?command(?:\((?P<args>[^\]]*)\))?\s*\]\s*"
    r"(?:#\[[^\]]+\]\s*)*"
    r"(?:pub(?:\([^)]*\))?\s+)?"
    r"(?:async\s+)?fn\s+(?P<name>[A-Za-z_]\w*)"
    r"\s*(?:<[^>{}]*>)?\s*"
    r"\((?P<params>[\s\S]{0,900}?)\)\s*"
    r"(?:->\s*(?P<return>[^{]+?))?\s*\{",
    re.MULTILINE,
)
TAURI_MACRO_COMMAND_RE = re.compile(
    r"\b(?P<macro>getter|setter)!\s*\((?P<body>[\s\S]{0,260}?)\)\s*;",
    re.MULTILINE,
)
EXPRESS_GRAPHQL_RE = re.compile(
    r"\b(?:app|router|server)\.use\(\s*(?P<path>['\"`][^'\"`]+['\"`]|[A-Za-z_$][\w$.]*)\s*,\s*graphqlHTTP\b",
    re.IGNORECASE,
)
SSE_EXPRESS_ROUTE_RE = re.compile(
    r"\b(?:app|router|server)\.get\(\s*['\"`](?P<path>[^'\"`]+)['\"`](?P<args>[^\n;]*)",
    re.IGNORECASE,
)
PARTICLE_EVENT_STREAM_RE = re.compile(r"\bgetEventStream\(\s*\{(?P<body>[\s\S]{0,700}?)\}\s*\)", re.IGNORECASE)
PARTICLE_PUBLISH_EVENT_RE = re.compile(r"\bpublishEvent\(\s*\{(?P<body>[\s\S]{0,700}?)\}\s*\)", re.IGNORECASE)
OBJECT_NAME_RE = re.compile(r"\bname\s*:\s*(?P<value>['\"][^'\"]*['\"]|[A-Za-z_$][\w$]*)", re.IGNORECASE)
PRIMITIVE_TYPES = {
    "str",
    "int",
    "float",
    "bool",
    "bytes",
    "Any",
    "None",
    "uuid.UUID",
    "UUID",
    "datetime",
    "datetime.datetime",
    "date",
    "datetime.date",
    "Decimal",
    "EmailStr",
    "SecretStr",
    "AnyUrl",
    "HttpUrl",
    "IPvAnyAddress",
}
FASTAPI_ROUTE_RE = re.compile(
    r"@(?P<receiver>[A-Za-z_]\w*)\.(?P<method>get|post|put|delete|patch|options|head)"
    r"\(\s*['\"](?P<path>[^'\"]+)['\"]",
    re.IGNORECASE,
)
FASTAPI_API_ROUTER_RE = re.compile(
    r"(?m)^\s*(?P<name>[A-Za-z_]\w*)\s*=\s*APIRouter\s*\((?P<args>[^)]*)\)",
    re.DOTALL,
)
FASTAPI_INCLUDE_ROUTER_RE = re.compile(
    r"\b(?P<receiver>[A-Za-z_]\w*)\.include_router\s*\(\s*(?P<router>[A-Za-z_][\w.]*)(?P<args>[^)]*)\)",
    re.DOTALL,
)
FASTAPI_PREFIX_ARG_RE = re.compile(
    r"\bprefix\s*=\s*(?P<value>[^,\n)]+)",
    re.DOTALL,
)
NINJA_ADD_ROUTER_RE = re.compile(
    r"\b(?P<receiver>[A-Za-z_]\w*)\.add_router\s*\(\s*['\"](?P<prefix>[^'\"]*)['\"]\s*,\s*(?P<target>[^)\n]+)",
    re.DOTALL,
)
NINJA_API_ROOT_RE = re.compile(
    r"\bpath\s*\(\s*['\"](?P<prefix>[^'\"]*)['\"]\s*,\s*(?P<api>[A-Za-z_]\w*)\.urls\b",
    re.DOTALL,
)
FLASK_ROUTE_RE = re.compile(
    r"@(?:app|blueprint|bp)\.route\(\s*['\"](?P<path>[^'\"]+)['\"](?P<args>[^)]*)\)",
    re.IGNORECASE | re.DOTALL,
)
PY_CLASS_RE = re.compile(
    r"(?m)^(?P<indent>[ \t]*)class\s+(?P<name>[A-Za-z_]\w*)\s*(?:\((?P<bases>[^)]*)\))?:"
)
FLASK_APPBUILDER_EXPOSE_RE = re.compile(r"(?m)^(?P<indent>[ \t]*)@expose\s*\(")
PY_CLASS_STRING_ATTR_RE = re.compile(
    r"(?m)^[ \t]+(?P<name>route_base|resource_name)\s*=\s*['\"](?P<value>[^'\"]+)['\"]"
)
FLASK_APPBUILDER_API_BASES = {"BaseSupersetApi", "BaseSupersetModelRestApi", "ModelRestApi", "BaseApi"}
FLASK_APPBUILDER_VIEW_BASES = {"BaseSupersetView", "BaseView", "IndexView"}
PY_FUNCTION_SEARCH_WINDOW = 2000
GIN_GROUP_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z_]\w*)\s*:?=\s*(?P<parent>[A-Za-z_]\w*)\.Group\(\s*['\"](?P<prefix>/[^'\"]*)['\"]",
    re.MULTILINE,
)
GIN_ROUTE_RE = re.compile(
    r"\b(?P<receiver>[A-Za-z_]\w*)\.(?P<method>GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD|Get|Post|Put|Delete|Patch|Options|Head|Any)"
    r"\(\s*['\"](?P<path>[^'\"]*)['\"]\s*(?:,\s*(?P<handler>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?))?",
)
GO_FUNC_RE = re.compile(r"\bfunc\s+(?P<name>[A-Za-z_]\w*)\s*\((?P<params>[^)]*)\)\s*\{", re.MULTILINE)
GO_GIN_GROUP_PARAM_RE = re.compile(r"\b(?P<name>[A-Za-z_]\w*)\s+\*gin\.RouterGroup\b")
GO_GIN_MOUNT_GROUP_CALL_RE = re.compile(
    r"\b(?:[A-Za-z_]\w*\.)?(?P<name>[A-Za-z_]\w*)\s*\(\s*"
    r"(?P<receiver>[A-Za-z_]\w*)\.Group\(\s*['\"](?P<path>[^'\"]*)['\"]\s*\)",
)
GO_GIN_MOUNT_VAR_CALL_RE = re.compile(r"\b(?:[A-Za-z_]\w*\.)?(?P<name>[A-Za-z_]\w*)\s*\(\s*(?P<group>[A-Za-z_]\w*)\s*\)")
LARAVEL_ROUTE_RE = re.compile(
    r"\bRoute::(?P<method>get|post|put|delete|patch|options|any|resource|apiResource)"
    r"\(\s*['\"](?P<path>[^'\"]+)['\"](?P<args>[^)]*)\)",
    re.IGNORECASE | re.DOTALL,
)
LARAVEL_MATCH_ROUTE_RE = re.compile(
    r"\bRoute::match\(\s*\[(?P<methods>[^\]]+)\]\s*,\s*['\"](?P<path>[^'\"]+)['\"](?P<args>[^)]*)\)",
    re.IGNORECASE | re.DOTALL,
)
WORDPRESS_REST_RE = re.compile(
    r"\bregister_rest_route\(\s*['\"](?P<namespace>[^'\"]+)['\"]\s*,\s*['\"](?P<path>[^'\"]+)['\"]\s*,\s*(?P<args>.*?)\)\s*;",
    re.IGNORECASE | re.DOTALL,
)
WORDPRESS_REST_CALL_RE = re.compile(r"\bregister_rest_route\s*\(", re.IGNORECASE)
WORDPRESS_REWRITE_CALL_RE = re.compile(r"\badd_rewrite_rule\s*\(", re.IGNORECASE)
WORDPRESS_METHOD_RE = re.compile(r"['\"]methods['\"]\s*=>\s*(?:['\"](?P<method>[A-Z]+)['\"]|WP_REST_Server::(?P<constant>[A-Z_]+))", re.IGNORECASE)
WORDPRESS_PROPERTY_RE = re.compile(
    r"\b(?:protected|private|public)\s+\$(?P<name>namespace|rest_base)\s*=\s*['\"](?P<value>[^'\"]+)['\"]",
    re.IGNORECASE,
)
WORDPRESS_CONST_RE = re.compile(r"\bconst\s+(?P<name>[A-Z_]+)\s*=\s*['\"](?P<value>[^'\"]+)['\"]", re.IGNORECASE)
RAILS_ROUTE_RE = re.compile(
    r"^\s*(?P<method>get|post|put|patch|delete)\s+['\"](?P<path>[^'\"]+)['\"](?P<args>.*)$",
    re.IGNORECASE | re.MULTILINE,
)
SINATRA_ROUTE_RE = re.compile(
    r"(?m)^\s*(?P<method>get|post|put|patch|delete|options|head)\s+['\"](?P<path>[^'\"]+)['\"](?P<args>[^\n]*)"
)
SINATRA_CLASS_RE = re.compile(r"(?m)^\s*class\s+(?P<name>[A-Za-z_]\w*)\s*<\s*Sinatra::Base\b")
GRAPE_CLASS_RE = re.compile(r"(?m)^\s*class\s+(?P<name>[A-Za-z_]\w*)\s*<\s*Grape::API\b")
GRAPE_ROUTE_LINE_RE = re.compile(
    r"^\s*(?P<method>get|post|put|patch|delete|options|head)(?:\s+(?P<path>[^#\n]+?))?\s+do\b",
    re.IGNORECASE,
)
GRAPE_SCOPE_LINE_RE = re.compile(r"^\s*(?P<kind>namespace|resource|resources|route_param)\s+(?P<path>[^#\n]+?)\s+do\b")
GRAPE_PREFIX_LINE_RE = re.compile(r"^\s*prefix\s+(?P<path>['\"][^'\"]+['\"]|:[A-Za-z_]\w*)")
GRAPE_VERSION_PATH_LINE_RE = re.compile(r"^\s*version\s+['\"](?P<path>[^'\"]+)['\"][^\n]*\busing:\s*:path\b")
GRAPE_PARAM_LINE_RE = re.compile(r"^\s*(?P<kind>requires|optional)\s+:(?P<name>[A-Za-z_]\w*)(?P<rest>[^\n]*)")
RAILS_SCOPE_PATH_RE = re.compile(r"^scope\s+path:\s*['\"](?P<path>[^'\"]+)['\"]")
RAILS_QUOTED_SCOPE_RE = re.compile(r"^scope\s+['\"](?P<path>[^'\"]+)['\"]")
RAILS_SCOPE_RE = re.compile(r"^scope\s+:?(?P<name>[A-Za-z_]\w*)\b(?!\s*:)")
RAILS_SCOPE_MODULE_RE = re.compile(r"^scope\s+module:\s*(?::[A-Za-z_]\w*|['\"][A-Za-z_]\w*['\"])")
RAILS_NAMESPACE_RE = re.compile(r"^namespace\s+:?(?P<name>[A-Za-z_]\w*)")
RAILS_BLOCK_SCOPE_RE = re.compile(r"^(?P<kind>collection|member)\s+do$")
RAILS_INLINE_BLOCK_ROUTE_RE = re.compile(
    r"^(?P<scope>collection|member)\s*\{\s*"
    r"(?P<method>get|post|put|patch|delete)\s+['\"](?P<path>[^'\"]+)['\"](?P<args>.*?)\s*\}\s*$",
    re.IGNORECASE,
)
RAILS_RESOURCES_RE = re.compile(r"^(?P<kind>resources?|resource)\s+:?(?P<name>[A-Za-z_]\w*)(?P<args>.*)$")
RAILS_SYMBOL_ROUTE_RE = re.compile(r"^(?P<method>get|post|put|patch|delete)\s+:?(?P<name>[A-Za-z_]\w*)(?P<args>.*)$", re.IGNORECASE)
RAILS_DEVISE_TOKEN_AUTH_RE = re.compile(r"^mount_devise_token_auth_for\b(?P<args>.*)$", re.IGNORECASE)
RAILS_DEVISE_FOR_RE = re.compile(r"^devise_for\s+:?(?P<name>[A-Za-z_]\w*)(?P<args>.*)$", re.IGNORECASE)
PHOENIX_ROUTE_RE = re.compile(
    r"^\s*(?P<method>get|post|put|patch|delete)\s*\(?\s*['\"](?P<path>/[^'\"]*)['\"]\s*,\s*"
    r"(?P<controller>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)"
    r"(?:\s*,\s*:(?P<action>[A-Za-z_]\w*))?",
    re.IGNORECASE | re.MULTILINE,
)
PHOENIX_LINE_ROUTE_RE = re.compile(
    r"^\s*(?P<method>get|post|put|patch|delete)\s*\(?\s*['\"](?P<path>/[^'\"]*)['\"]\s*,\s*"
    r"(?P<controller>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)"
    r"(?:\s*,\s*:(?P<action>[A-Za-z_]\w*))?",
    re.IGNORECASE,
)
PHOENIX_LIVE_RE = re.compile(
    r"^\s*live\s*\(?\s*['\"](?P<path>/[^'\"]*)['\"]\s*,\s*"
    r"(?P<liveview>on_ee\([^)]*\)|[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)"
    r"(?:\s*,\s*:(?P<action>[A-Za-z_]\w*))?",
    re.IGNORECASE,
)
PHOENIX_LIVE_DASHBOARD_RE = re.compile(
    r"^\s*live_dashboard\s*\(?\s*['\"](?P<path>/[^'\"]*)['\"]",
    re.IGNORECASE,
)
PHOENIX_FORWARD_RE = re.compile(
    r"^\s*forward\s*\(?\s*['\"](?P<path>/[^'\"]*)['\"]\s*,\s*(?P<plug>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)",
    re.IGNORECASE,
)
PHOENIX_SCOPE_RE = re.compile(r"^\s*scope\s*\(?\s*['\"](?P<path>/[^'\"]*)['\"]", re.IGNORECASE)
PHOENIX_SCOPE_NAMED_PATH_RE = re.compile(r"^\s*scope\b[^\n#]*\bpath:\s*['\"](?P<path>/[^'\"]*)['\"]", re.IGNORECASE)
PHOENIX_RESOURCES_RE = re.compile(
    r"^\s*resources\s*\(?\s*['\"](?P<path>/[^'\"]*)['\"]\s*,\s*(?P<controller>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)(?P<args>[^\n]*)",
    re.IGNORECASE | re.MULTILINE,
)
PHOENIX_LINE_RESOURCES_RE = re.compile(
    r"^\s*resources\s*\(?\s*['\"](?P<path>/[^'\"]*)['\"]\s*,\s*(?P<controller>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)(?P<args>[^\n]*)",
    re.IGNORECASE,
)
PLAY_ROUTE_LINE_RE = re.compile(
    r"^\s*(?P<method>GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\s+"
    r"(?P<path>/\S*)\s+"
    r"(?P<handler>[A-Za-z_][\w.]*)(?:\((?P<args>[^)]*)\))?",
    re.IGNORECASE,
)
CLOJURE_COMPOJURE_ROUTE_RE = re.compile(
    r"^\s*\((?P<method>GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD|ANY)\s+['\"](?P<path>/[^'\"]*)['\"](?P<rest>[^\n]*)",
    re.IGNORECASE | re.MULTILINE,
)
CLOJURE_REITIT_ROUTE_RE = re.compile(r"\[\s*['\"](?P<path>/[^'\"]*)['\"]\s+\{(?P<body>[^}\]]+)\}", re.DOTALL)
CLOJURE_REITIT_METHOD_RE = re.compile(r":(?P<method>get|post|put|patch|delete)\b", re.IGNORECASE)
CLOJURE_NS_RE = re.compile(
    r"\(ns\s+(?:\^[^\s()]+\s+|\^\{[\s\S]{0,300}?\}\s+)*(?P<namespace>[A-Za-z0-9_.-]+)(?P<body>[\s\S]{0,500})",
    re.MULTILINE,
)
CLOJURE_NS_DOC_PREFIX_RE = re.compile(
    r"\(ns\s+(?:\^[^\s()]+\s+|\^\{[\s\S]{0,300}?\}\s+)*[A-Za-z0-9_.-]+\s+\"(?P<doc>[^\"]*/api[^\"]*)\"",
    re.MULTILINE,
)
CLOJURE_API_PREFIX_RE = re.compile(r"(?P<prefix>/api(?:/[A-Za-z0-9_.:-]+)*)")
CLOJURE_ROUTE_MAP_ENTRY_RE = re.compile(r'"(?P<prefix>/[^"]+)"\s+(?P<target>[^\n}]+)')
CLOJURE_NAMESPACE_TARGET_RE = re.compile(r"'?(?P<namespace>metabase(?:-enterprise)?[A-Za-z0-9_.-]+)(?:/[A-Za-z0-9_.!\-?]+)?")
CLOJURE_NS_HANDLER_DOC_RE = re.compile(
    r"\"(?P<doc>/api[^\"]*)\"[\s\S]{0,500}?api\.macros/ns-handler\s+'(?P<namespace>metabase(?:-enterprise)?[A-Za-z0-9_.-]+)",
    re.IGNORECASE,
)
CLOJURE_DEFENDPOINT_RE = re.compile(
    r"\((?:api\.macros/)?defendpoint\s+:(?P<method>get|post|put|patch|delete|options|head)\s+\"(?P<path>[^\"]*)\"",
    re.IGNORECASE,
)
ASPNET_CLASS_RE = re.compile(
    r"(?P<attrs>(?:^\s*\[[^\]]+\]\s*\n)*)"
    r"^\s*(?:public\s+|internal\s+)?(?:partial\s+)?class\s+(?P<name>[A-Za-z_]\w*)",
    re.MULTILINE,
)
ASPNET_METHOD_RE = re.compile(
    r"(?P<attrs>(?:^\s*\[[\s\S]*?\]\s*\n)+)"
    r"^\s*(?:(?:public|private|protected|internal|static|async|virtual|override)\s+)+"
    r"(?P<return>[\w<>,>.?[\]\s]+?)\s+(?P<name>[A-Za-z_]\w*)\s*\(",
    re.MULTILINE,
)
ASPNET_METHOD_SIGNATURE_RE = re.compile(
    r"^\s*(?:(?:public|private|protected|internal|static|async|virtual|override)\s+)+"
    r"(?P<return>[\w<>,>.?[\]\s]+?)\s+(?P<name>[A-Za-z_]\w*)\s*\(",
    re.MULTILINE,
)
ASPNET_ROUTE_ATTR_RE = re.compile(
    r"\[\s*(?P<name>Route|HttpGet|HttpPost|HttpPut|HttpDelete|HttpPatch|HttpHead|HttpOptions)"
    r"(?:\s*\(\s*(?:['\"](?P<path>[^'\"]*)['\"]|Name\s*=\s*['\"][^'\"]+['\"])?[^)]*\))?"
    r"(?:\s*,[^\]]*)?\]",
    re.IGNORECASE,
)
ASPNET_MAP_GROUP_RE = re.compile(
    r"\b(?:var\s+)?(?P<name>[A-Za-z_]\w*)\s*=\s*(?P<parent>[A-Za-z_]\w*)\.MapGroup\(\s*['\"](?P<path>[^'\"]*)['\"]",
    re.MULTILINE,
)
ASPNET_MINIMAL_MAP_RE = re.compile(
    r"\b(?P<receiver>[A-Za-z_]\w*)\.Map(?P<method>Get|Post|Put|Delete|Patch|Head|Options|Methods)\(\s*(?P<args>[^\n;)]*)",
    re.IGNORECASE,
)
ASPNET_MAP_CONTROLLER_ROUTE_RE = re.compile(
    r"\b(?P<receiver>[A-Za-z_]\w*)\.MapControllerRoute\s*\(",
    re.IGNORECASE,
)
ASPNET_MAP_DYNAMIC_CONTROLLER_ROUTE_RE = re.compile(
    r"\b(?P<receiver>[A-Za-z_]\w*)\.MapDynamicControllerRoute\s*<\s*(?P<transformer>[^>]+)\s*>\s*\(",
    re.IGNORECASE,
)
ASPNET_LOCAL_STRING_RE = re.compile(
    r"^\s*(?:(?:const\s+)?string|var)\s+(?P<name>[A-Za-z_]\w*)\s*=\s*(?P<value>[$@]{0,2}\"[^\n;]*\")\s*;",
    re.MULTILINE,
)
ASPNET_AREA_ATTR_RE = re.compile(r"\[\s*Area\s*\(\s*(?P<value>[^)]*)\)\s*\]", re.IGNORECASE)
ASPNET_ACTION_NAME_RE = re.compile(r"\[[^\]]*\bActionName\s*\(\s*['\"](?P<name>[^'\"]+)['\"]\s*\)[^\]]*\]", re.IGNORECASE)
NEST_CONTROLLER_RE = re.compile(
    r"@Controller(?:\s*\((?P<args>.*?)\))?\s*(?:export\s+)?class\s+(?P<name>[A-Za-z_]\w*)",
    re.DOTALL,
)
NEST_ROUTE_RE = re.compile(
    r"@(?P<decorator>Get|Post|Put|Delete|Patch|Options|Head)(?:\s*\((?P<args>.*?)\))?",
    re.DOTALL,
)
NEST_GRAPHQL_OPERATION_RE = re.compile(
    r"@(?P<decorator>Query|Mutation|Subscription)\b",
)
TS_METHOD_RE = re.compile(
    r"(?:(?:public|private|protected|static|readonly|async)\s+)*"
    r"(?P<name>[A-Za-z_$][\w$]*)\s*\(",
    re.MULTILINE,
)
DJANGO_PATH_RE = re.compile(
    r"\bpath\(\s*['\"](?P<path>[^'\"]*)['\"]\s*,\s*(?P<handler>[A-Za-z_][\w.]+)?",
    re.DOTALL,
)
DJANGO_URL_RE = re.compile(
    r"\b(?:re_path|url)\(\s*r?['\"]\^?(?P<path>[^'\"]*)['\"]\s*,\s*(?P<handler>[A-Za-z_][\w.]+)?",
    re.DOTALL,
)
DRF_REGISTER_RE = re.compile(
    r"\b(?P<router>[A-Za-z_]\w*)\.register\(\s*r?['\"](?P<path>[^'\"]+)['\"]\s*,\s*(?P<handler>[A-Za-z_]\w*)",
    re.DOTALL,
)
DJANGO_ROUTE_CALL_RE = re.compile(r"\b(?P<fn>path|re_path|url)\s*\(", re.MULTILINE)
PYTHON_LIST_ASSIGN_RE = re.compile(r"(?m)^(?P<name>[A-Za-z_]\w*)\s*=\s*\[")
AXUM_ROUTE_RE = re.compile(
    r"\.route\(\s*['\"](?P<path>/[^'\"]*)['\"]\s*,\s*(?P<chain>[^\n;]+)",
    re.DOTALL,
)
AXUM_METHOD_CALL_RE = re.compile(r"(?:^|\.)\s*(?P<method>get|post|put|delete|patch|options|head)\s*\(\s*(?P<handler>[A-Za-z_:]\w*(?:::\w+)*)?", re.IGNORECASE)
HYPER_MATCH_ROUTE_RE = re.compile(
    r"\(\s*&?Method::(?P<method>GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\s*,\s*['\"](?P<path>/[^'\"]*)['\"]\s*\)\s*=>\s*\{",
    re.MULTILINE,
)
RUST_QUALIFIED_CALL_RE = re.compile(r"\b(?P<handler>[a-zA-Z_]\w*(?:::[a-zA-Z_]\w*)+)\s*\(")
RUST_FUNCTION_CALL_RE = re.compile(r"\b(?P<handler>[a-zA-Z_]\w*)\s*\(")
DART_SIMPLE_SERVER_ROUTE_RE = re.compile(
    r"\brouter\.(?P<method>get|post|put|delete|patch)\s*\(\s*(?P<target>ApiRoute\.[A-Za-z_]\w*\.v[12]|['\"][^'\"]+['\"])",
    re.IGNORECASE,
)
VAPOR_API_COLLECTION_RE = re.compile(
    r"\.init\s*\(\s*method\s*:\s*\.(?P<method>get|post|put|delete|patch|options|head)\s*,\s*"
    r"paths\s*:\s*\[(?P<paths>[^\]]*)\]\s*,\s*closure\s*:\s*(?P<handler>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)",
    re.IGNORECASE | re.DOTALL,
)
VAPOR_DIRECT_ROUTE_RE = re.compile(
    r"\b(?P<receiver>app|application|routes|router)\.(?P<method>get|post|put|delete|patch|options|head)\s*"
    r"(?:\((?P<args>[^)]*)\))?\s*\{",
    re.IGNORECASE,
)
VAPOR_ON_ROUTE_RE = re.compile(
    r"\b(?P<receiver>app|application|routes|router)\.on\s*\(\s*\.(?P<method>GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\s*,"
    r"(?P<args>[\s\S]{0,260}?)(?:,\s*use\s*:\s*(?P<handler>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?))?\s*\)",
    re.IGNORECASE,
)
ASTRO_API_EXPORT_RE = re.compile(
    r"\bexport\s+(?:const|async\s+function|function)\s+(?P<method>GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD|ALL)\b",
    re.MULTILINE,
)
SVELTEKIT_SERVER_METHOD_RE = re.compile(
    r"\bexport\s+(?:(?:async\s+)?function\s+(?P<fn>GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\b|const\s+(?P<const>GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\b)",
    re.MULTILINE,
)
SVELTEKIT_LOAD_RE = re.compile(r"\bexport\s+(?:(?:async\s+)?function\s+load\b|const\s+load\b)", re.MULTILINE)
SVELTEKIT_ACTIONS_RE = re.compile(r"\bexport\s+const\s+actions\s*=\s*\{", re.MULTILINE)
NITRO_ROUTE_HANDLER_RE = re.compile(r"\b(?:defineEventHandler|eventHandler)\b|\bexport\s+default\b")
NITRO_METHODS = {
    "connect": "CONNECT",
    "delete": "DELETE",
    "get": "GET",
    "head": "HEAD",
    "options": "OPTIONS",
    "patch": "PATCH",
    "post": "POST",
    "put": "PUT",
    "trace": "TRACE",
}
REACT_ROUTER_DATA_EXPORT_RE = re.compile(
    r"\bexport\s+(?:(?:async\s+)?function|const)\s+(?P<name>loader|action)\b",
    re.MULTILINE,
)
SYMFONY_CLASS_RE = re.compile(
    r"(?P<attrs>(?:^\s*#\[[^\n]*\]\s*\n)*)^\s*(?:final\s+|abstract\s+)?class\s+(?P<name>[A-Za-z_]\w*)",
    re.MULTILINE,
)
SYMFONY_METHOD_RE = re.compile(
    r"(?P<attrs>(?:^\s*#\[[^\n]*\]\s*\n)+)"
    r"^\s*(?:(?:public|private|protected|static|final|abstract)\s+)*function\s+(?P<name>[A-Za-z_]\w*)",
    re.MULTILINE,
)
SYMFONY_ROUTE_ATTR_RE = re.compile(r"#\[Route\((?P<args>[^\n]*?)\)(?:,\s*[^\n]*?)?\]")
SYMFONY_DOC_ROUTE_RE = re.compile(r"@Route\((?P<args>.*?)\)", re.DOTALL)
PHP_CLASS_RE = re.compile(r"\b(?:final\s+|abstract\s+)?class\s+(?P<name>[A-Za-z_]\w*)")
PHP_FUNCTION_RE = re.compile(r"\bfunction\s+(?P<name>[A-Za-z_]\w*)\s*\(")
SPRING_ROUTE_RE = re.compile(
    r"@(?P<annotation>GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping|RequestMapping)"
    r"(?:\s*\((?P<args>.*?)\))?",
    re.DOTALL,
)
SPRING_METHOD_RE = re.compile(r"(?:RequestMethod\.)?(?P<method>GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\b")
SPRING_PATH_RE = re.compile(r"""(?:\b(?:value|path)\s*=\s*(?:\{\s*)?)?["'](?P<path>[^"']*)["']""")
JAVA_CLASS_RE = re.compile(
    r"\b(?:(?:public|protected|private|abstract|final|static)\s+)*"
    r"(?P<kind>class|interface|enum)\s+"
    r"(?P<name>[A-Za-z_]\w*)"
    r"(?P<rest>[^{;]*)\{",
    re.MULTILINE,
)
JAVA_METHOD_DECL_RE = re.compile(
    r"(?:@\w+(?:\s*\([^)]*\))?\s*)*"
    r"(?:(?:public|protected|private)\s+)?"
    r"(?:(?:static|final|synchronized)\s+)*"
    r"(?P<return>[\w<>, ?\[\].]+?)\s+"
    r"(?P<name>[A-Za-z_]\w*)\s*\(",
    re.MULTILINE,
)
WEB_SERVLET_RE = re.compile(r"@WebServlet(?:\s*\((?P<args>.*?)\))?", re.DOTALL)
QUOTED_PATH_RE = re.compile(r"""["'](?P<path>/[^"']*)["']""")
PY_FUNCTION_AFTER_DECORATOR_RE = re.compile(r"\n\s*(?:async\s+)?def\s+(?P<name>[A-Za-z_]\w*)")
OPENAPI_METHODS = {"get", "post", "put", "delete", "patch", "options", "head"}
PROTO_PACKAGE_RE = re.compile(r"^\s*package\s+(?P<package>[A-Za-z_][\w.]*)\s*;", re.MULTILINE)
PROTO_SERVICE_RE = re.compile(r"\bservice\s+(?P<name>[A-Za-z_]\w*)\s*\{", re.MULTILINE)
PROTO_RPC_RE = re.compile(
    r"\brpc\s+(?P<name>[A-Za-z_]\w*)\s*\(\s*(?P<request>stream\s+)?(?P<request_type>[A-Za-z_.]\w*)\s*\)"
    r"\s*returns\s*\(\s*(?P<response>stream\s+)?(?P<response_type>[A-Za-z_.]\w*)\s*\)",
    re.MULTILINE,
)
GRAPHQL_BLOCK_RE = re.compile(r"\b(?:extend\s+)?type\s+(?P<type>[A-Za-z_]\w*)(?:\s+[^{]+)?\s*\{(?P<body>.*?)\}", re.DOTALL)
GRAPHQL_TYPE_RE = re.compile(r"\b(?:extend\s+)?type\s+(?P<type>[A-Za-z_]\w*)\b")
GRAPHQL_FIELD_RE = re.compile(
    r"^(?P<name>[A-Za-z_]\w*)\s*(?:\((?P<args>.*)\))?\s*:\s*"
    r"(?P<return>[!\[\]A-Za-z_][!\[\]A-Za-z_0-9\s]*)(?:\s+@.*)?$"
)
GRAPHQL_SCHEMA_BLOCK_RE = re.compile(r"\bschema\s*\{(?P<body>.*?)\}", re.DOTALL)
GRAPHQL_SCHEMA_ROOT_RE = re.compile(r"\b(?P<kind>query|mutation|subscription)\s*:\s*(?P<type>[A-Za-z_]\w*)", re.IGNORECASE)
GRAPHQL_TEMPLATE_RE = re.compile(r"gql\s*(?:\(\s*)?`(?P<body>[\s\S]*?)`", re.MULTILINE)
TRPC_PROCEDURE_RE = re.compile(
    r"(?m)^\s*(?P<name>[A-Za-z_$][\w$]*)\s*:\s*"
    r"(?P<body>(?:[A-Za-z_$][\w$]*Procedure|t\.procedure|procedure)[\s\S]{0,1600}?)"
    r"\.(?P<kind>query|mutation|subscription)\s*\(",
    re.IGNORECASE,
)
SOCKET_EVENT_RE = re.compile(r"\b(?:io|socket)\.on\(\s*['\"](?P<event>[^'\"]+)['\"]", re.IGNORECASE)
WEBSOCKET_EVENT_RE = re.compile(r"\b(?:wss|ws|socket|client)\.on\(\s*['\"](?P<event>connection|message|close|error|open)['\"]", re.IGNORECASE)
WEBSOCKET_PATH_RE = re.compile(r"\bpath\s*:\s*['\"](?P<path>/[^'\"]+)['\"]", re.IGNORECASE)
ELECTRON_IPC_MAIN_RE = re.compile(
    r"\bipcMain\.(?P<kind>on|once|handle|handleOnce)\(\s*['\"`](?P<channel>[^'\"`]+)['\"`]",
    re.IGNORECASE,
)
KAFKA_TOPIC_RE = re.compile(r"\btopic\s*:\s*['\"](?P<topic>[^'\"]+)['\"]", re.IGNORECASE)
KAFKA_TOPICS_ARRAY_RE = re.compile(r"\btopics\s*:\s*\[(?P<topics>[^\]]+)\]", re.IGNORECASE | re.DOTALL)
RABBIT_ARG = r"(?P<{name}>['\"][^'\"]*['\"]|[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)?)"
RABBIT_SEND_RE = re.compile(r"\bsendToQueue\(\s*" + RABBIT_ARG.format(name="queue"), re.IGNORECASE)
RABBIT_CONSUME_RE = re.compile(r"\bconsume\(\s*" + RABBIT_ARG.format(name="queue"), re.IGNORECASE)
RABBIT_PUBLISH_RE = re.compile(
    r"\bpublish\(\s*" + RABBIT_ARG.format(name="exchange") + r"\s*,\s*" + RABBIT_ARG.format(name="routing_key"),
    re.IGNORECASE,
)
BULL_QUEUE_RE = re.compile(r"\bnew\s+Queue\(\s*['\"](?P<queue>[^'\"]+)['\"]", re.IGNORECASE)
BULL_WORKER_RE = re.compile(r"\bnew\s+Worker\(\s*['\"](?P<queue>[^'\"]+)['\"]", re.IGNORECASE)
REDIS_PUBLISH_RE = re.compile(r"\.publish\(\s*['\"](?P<channel>[^'\"]+)['\"]", re.IGNORECASE)
REDIS_SUBSCRIBE_RE = re.compile(r"\.(?:subscribe|pSubscribe)\(\s*['\"](?P<channel>[^'\"]+)['\"]", re.IGNORECASE)
KTOR_ROUTE_CALL_RE = re.compile(
    r"(?<![\w.])(?P<call>route|get|post|put|delete|patch|options|head|webSocket)"
    r"\s*(?P<generic><[^>{}()]+>)?\s*(?:\((?P<args>[^)]*)\))?\s*\{",
    re.IGNORECASE,
)
KTOR_RESOURCE_RE = re.compile(
    r"@\s*Resource\s*\(\s*['\"](?P<path>[^'\"]+)['\"]\s*\)"
    r"[\s\S]{0,240}?\b(?:data\s+)?class\s+(?P<name>[A-Za-z_]\w*)",
    re.MULTILINE,
)
KTOR_METHODS = {
    "get": "GET",
    "post": "POST",
    "put": "PUT",
    "delete": "DELETE",
    "patch": "PATCH",
    "options": "OPTIONS",
    "head": "HEAD",
    "websocket": "WS",
}


def extract_backend_facts(
    root: Path,
    files: list[FileFact],
    symbols: list[SymbolFact],
    frameworks: list[FrameworkFact],
) -> tuple[list[ApiRouteFact], list[BackendSurfaceFact]]:
    routes: list[ApiRouteFact] = []
    go_framework_fallback = _go_framework_fallback(frameworks)
    ktor_resources = _ktor_resource_paths(root, files)
    for file_fact in files:
        if file_fact.role in {"test", "sample", "generated"}:
            continue
        normalized = file_fact.path.replace("\\", "/")
        if file_fact.language == "play-routes" or normalized.lower().endswith("/conf/routes") or normalized.lower() == "conf/routes":
            routes.extend(_extract_play_routes(root, file_fact))
        elif file_fact.language in {"typescript", "javascript"}:
            routes.extend(_extract_fresh_routes(root, file_fact))
            routes.extend(_extract_qwik_city_routes(root, file_fact))
            routes.extend(_extract_hono_routes(root, file_fact))
            routes.extend(_extract_elysia_routes(root, file_fact))
            routes.extend(_extract_express_routes(root, file_fact))
            routes.extend(_extract_koa_routes(root, file_fact))
            routes.extend(_extract_hapi_routes(root, file_fact))
            routes.extend(_extract_adonis_routes(root, file_fact))
            routes.extend(_extract_sails_routes(root, file_fact))
            routes.extend(_extract_loopback_routes(root, file_fact))
            routes.extend(_extract_feathers_routes(root, file_fact))
            routes.extend(_extract_strapi_routes(root, file_fact))
            routes.extend(_extract_fastify_routes(root, file_fact))
            routes.extend(_extract_graphql_routes(root, file_fact))
            routes.extend(_extract_graphql_schema_routes(root, file_fact))
            routes.extend(_extract_nestjs_graphql_resolver_routes(root, file_fact))
            routes.extend(_extract_astro_api_routes(root, file_fact))
            routes.extend(_extract_nitro_server_routes(root, file_fact))
            routes.extend(_extract_react_router_data_routes(root, file_fact))
            routes.extend(_extract_next_api_routes(root, file_fact, symbols))
            routes.extend(_extract_nestjs_routes(root, file_fact))
            routes.extend(_extract_trpc_routes(root, file_fact))
            routes.extend(_extract_sveltekit_backend_routes(root, file_fact))
            routes.extend(_extract_socketio_events(root, file_fact))
            routes.extend(_extract_websocket_routes(root, file_fact))
            routes.extend(_extract_electron_ipc_routes(root, file_fact))
            routes.extend(_extract_sse_routes(root, file_fact))
            routes.extend(_extract_message_queue_routes(root, file_fact))
        elif file_fact.language == "graphql":
            routes.extend(_extract_graphql_schema_routes(root, file_fact))
        elif file_fact.language == "protobuf":
            routes.extend(_extract_proto_routes(root, file_fact))
        elif file_fact.language == "python":
            routes.extend(_extract_python_backend_routes(root, file_fact))
            routes.extend(_extract_django_ninja_routes(root, file_fact))
            routes.extend(_extract_django_routes(root, file_fact))
        elif file_fact.language == "java":
            routes.extend(_extract_spring_routes(root, file_fact))
            routes.extend(_extract_web_servlet_routes(root, file_fact))
        elif file_fact.language == "kotlin":
            routes.extend(_extract_ktor_routes(root, file_fact, ktor_resources))
        elif file_fact.language == "xml" and normalized.endswith("WEB-INF/web.xml"):
            routes.extend(_extract_web_xml_routes(root, file_fact))
        elif file_fact.language in {"yaml", "yml"}:
            if normalized.endswith(".routing.yml") or normalized.endswith(".routing.yaml"):
                routes.extend(_extract_drupal_routes(root, file_fact))
            routes.extend(_extract_symfony_yaml_routes(root, file_fact))
            routes.extend(_extract_openapi_routes(root, file_fact))
        elif file_fact.language == "json":
            routes.extend(_extract_openapi_routes(root, file_fact))
        elif file_fact.language == "go":
            routes.extend(_extract_go_http_routes(root, file_fact, go_framework_fallback))
        elif file_fact.language == "dart":
            routes.extend(_extract_dart_simple_server_routes(root, file_fact))
        elif file_fact.language == "swift":
            routes.extend(_extract_vapor_routes(root, file_fact))
        elif file_fact.language == "php":
            routes.extend(_extract_slim_routes(root, file_fact))
            routes.extend(_extract_laravel_routes(root, file_fact))
            routes.extend(_extract_wordpress_routes(root, file_fact))
            routes.extend(_extract_symfony_routes(root, file_fact))
            routes.extend(_extract_yii_routes(root, file_fact))
        elif file_fact.language == "ruby":
            routes.extend(_extract_grape_routes(root, file_fact))
            routes.extend(_extract_sinatra_routes(root, file_fact))
            routes.extend(_extract_rails_routes(root, file_fact))
        elif file_fact.language == "elixir":
            routes.extend(_extract_phoenix_routes(root, file_fact))
        elif file_fact.language == "clojure":
            routes.extend(_extract_clojure_routes(root, file_fact))
        elif file_fact.language == "csharp":
            routes.extend(_extract_aspnet_routes(root, file_fact))
        elif file_fact.language == "rust":
            routes.extend(_extract_axum_routes(root, file_fact))
            routes.extend(_extract_hyper_match_routes(root, file_fact))
            routes.extend(_extract_actix_routes(root, file_fact))
            routes.extend(_extract_rocket_routes(root, file_fact))
            routes.extend(_extract_warp_routes(root, file_fact))
            routes.extend(_extract_tauri_commands(root, file_fact))

    go_files = [
        file_fact
        for file_fact in files
        if file_fact.language == "go" and file_fact.role not in {"test", "sample", "generated"}
    ]
    mounted_go_routes = _extract_go_mounted_routes(root, go_files, go_framework_fallback)
    if mounted_go_routes:
        routes = _replace_go_relative_registration_routes(routes, mounted_go_routes)
        routes.extend(mounted_go_routes)

    django_files = [
        file_fact
        for file_fact in files
        if file_fact.language == "python"
        and file_fact.role not in {"test", "sample", "generated"}
        and _looks_like_django_route_module(root, file_fact)
    ]
    mounted_django_routes = _extract_django_mounted_routes(root, django_files)
    if mounted_django_routes:
        routes = _replace_django_relative_routes(routes, mounted_django_routes)
        routes.extend(mounted_django_routes)

    routes = _apply_rocket_mount_prefixes(root, files, routes)
    routes = _apply_express_mount_prefixes(root, files, routes)
    routes = _apply_koa_mount_prefixes(root, files, routes)
    routes = _apply_hapi_mount_prefixes(root, files, routes)
    routes = _apply_feathers_mount_prefixes(root, files, routes)
    routes = _apply_fastapi_include_prefixes(root, files, routes)
    routes = _apply_django_ninja_mount_prefixes(root, files, routes)

    spring_openapi_routes = _extract_spring_openapi_operation_routes(root, files, routes)
    if spring_openapi_routes:
        routes.extend(spring_openapi_routes)
        routes = _dedupe_routes(routes)

    surfaces = _build_backend_surfaces(routes, symbols, frameworks)
    return routes, surfaces


def _extract_fresh_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    normalized = file_fact.path.replace("\\", "/")
    if "/routes/" not in f"/{normalized}" or "export const handler" not in source:
        return []
    route_path = _fresh_route_path(normalized, source)
    if route_path is None:
        return []
    routes: list[ApiRouteFact] = []
    for handler_match in FRESH_HANDLER_RE.finditer(source):
        open_brace = source.find("{", handler_match.start())
        close_brace = _find_matching_brace(source, open_brace)
        if close_brace is None:
            continue
        body = source[open_brace + 1 : close_brace]
        for method_match in FRESH_HANDLER_METHOD_RE.finditer(body):
            method = method_match.group("method").upper()
            absolute_offset = open_brace + 1 + method_match.start()
            line = _line_for_offset(source, absolute_offset)
            method_body = body[method_match.start() : method_match.start() + 1200]
            routes.append(
                ApiRouteFact(
                    method=method,
                    path=route_path,
                    handler=f"handler.{method}",
                    framework="fresh",
                    kind="fresh-handler-route",
                    evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                    parameters=_fresh_path_parameters(route_path, file_fact.path, line),
                    request_body="json" if re.search(r"\b(?:req|ctx\.req)\.json\s*\(", method_body) else None,
                    response_type="Response" if "new Response" in method_body or "Response." in method_body else None,
                )
            )
    return routes


def _fresh_route_path(path: str, source: str) -> str | None:
    override = re.search(r"\brouteOverride\s*:\s*['\"](?P<route>[^'\"]+)['\"]", source)
    if override:
        return _normalize_fresh_backend_route(override.group("route"))
    route_part = _path_after_marker(path.replace("\\", "/"), "/routes/")
    if route_part is None and path.startswith("routes/"):
        route_part = path.removeprefix("routes/")
    if route_part is None or _fresh_non_route_path(route_part):
        return None
    return _fresh_page_route(_clean_fresh_backend_route_part(route_part.rsplit(".", 1)[0]))


def _fresh_non_route_path(route_part: str) -> bool:
    stem = route_part.rsplit(".", 1)[0]
    return any(part.startswith("_") for part in stem.split("/")) or stem.endswith(("_test", ".test"))


def _extract_qwik_city_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    normalized = file_fact.path.replace("\\", "/")
    if "/src/routes/" not in f"/{normalized}" or "export const on" not in source:
        return []
    route_path = _qwik_city_route_path(normalized)
    if route_path is None:
        return []
    routes: list[ApiRouteFact] = []
    for match in QWIK_CITY_HANDLER_RE.finditer(source):
        if _offset_is_comment_line(source, match.start()):
            continue
        line = _line_for_offset(source, match.start())
        method = _qwik_city_method(match.group("name"))
        context = source[match.start() : min(len(source), match.start() + 1000)]
        routes.append(
            ApiRouteFact(
                method=method,
                path=route_path,
                handler=match.group("name"),
                framework="qwik-city",
                kind="qwik-city-route-handler",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                parameters=_qwik_city_path_parameters(route_path, file_fact.path, line),
                request_body="body" if method in {"POST", "PUT", "PATCH"} or "parseBody" in context else None,
                response_type=_qwik_city_response_type(context),
            )
        )
    return _dedupe_routes(routes)


def _qwik_city_route_path(path: str) -> str | None:
    route_part = _path_after_marker(path.replace("\\", "/"), "/src/routes/")
    if route_part is None and path.startswith("src/routes/"):
        route_part = path.removeprefix("src/routes/")
    if route_part is None or _qwik_city_non_route_path(route_part):
        return None
    return _fresh_page_route(_clean_qwik_city_route_part(route_part.rsplit(".", 1)[0]))


def _qwik_city_non_route_path(route_part: str) -> bool:
    stem = route_part.rsplit(".", 1)[0]
    name = Path(stem).name
    return (
        any(part.startswith("_") for part in stem.split("/"))
        or name.lower().rstrip("!") in {"service-worker", "entry", "root"}
        or stem.endswith(("_test", ".test", ".spec"))
    )


def _clean_qwik_city_route_part(route: str) -> str:
    parts: list[str] = []
    for raw_part in route.split("/"):
        part = raw_part.rstrip("!")
        if "@" in part:
            part = part.split("@", 1)[0] or "index"
        if part in {"index", ""}:
            parts.append(part)
        elif part == "layout":
            parts.append("index")
        elif part.startswith("(") and part.endswith(")"):
            continue
        elif part.startswith("[...") and part.endswith("]"):
            parts.append(f"{{{part[4:-1]}*}}")
        elif part.startswith("[") and part.endswith("]"):
            parts.append(f"{{{part[1:-1]}}}")
        else:
            part = re.sub(r"\[\.\.\.([^\]]+)\]", r"{\1*}", part)
            part = re.sub(r"\[([^\]]+)\]", r"{\1}", part)
            parts.append(part)
    return "/".join(parts)


def _qwik_city_method(name: str) -> str:
    suffix = name.removeprefix("on").upper()
    return "ANY" if suffix == "REQUEST" else suffix


def _qwik_city_path_parameters(path: str, file_path: str, line: int) -> list[RequestParamFact]:
    return [
        RequestParamFact(
            name=name.strip("*"),
            source="path",
            type=None,
            required=True,
            evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
        )
        for name in re.findall(r"\{([^}]+)\}", path)
        if name.strip("*")
    ]


def _qwik_city_response_type(context: str) -> str | None:
    if re.search(r"\bjson\s*\(", context):
        return "json"
    if re.search(r"\btext\s*\(", context):
        return "text"
    if re.search(r"\bhtml\s*\(", context):
        return "html"
    if re.search(r"\bredirect\s*\(", context):
        return "redirect"
    if re.search(r"\bsend\s*\(", context):
        return "send"
    return None


def _clean_fresh_backend_route_part(route: str) -> str:
    parts: list[str] = []
    for part in route.split("/"):
        if part in {"index", ""}:
            parts.append(part)
        elif part.startswith("[...") and part.endswith("]"):
            parts.append(f"{{{part[4:-1]}*}}")
        elif part.startswith("[") and part.endswith("]"):
            parts.append(f"{{{part[1:-1]}}}")
        else:
            parts.append(part)
    return "/".join(parts)


def _fresh_page_route(route: str) -> str:
    cleaned = route.strip("/")
    if cleaned in {"", "index"}:
        return "/"
    if cleaned.endswith("/index"):
        cleaned = cleaned.removesuffix("/index")
    return _ensure_slash(cleaned)


def _normalize_fresh_backend_route(route: str) -> str:
    normalized = _ensure_slash(route)
    normalized = re.sub(r":([A-Za-z_$][\w$]*)\*", r"{\1*}", normalized)
    normalized = re.sub(r":([A-Za-z_$][\w$]*)", r"{\1}", normalized)
    return normalized


def _fresh_path_parameters(path: str, file_path: str, line: int) -> list[RequestParamFact]:
    return [
        RequestParamFact(
            name=name.strip("*"),
            source="path",
            type=None,
            required=True,
            evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
        )
        for name in re.findall(r"\{([^}]+)\}", path)
        if name.strip("*")
    ]


def _extract_hono_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    if not _looks_like_hono_source(source):
        return []
    routes: list[ApiRouteFact] = []
    openapi_routes = _extract_hono_openapi_routes(file_fact, source)
    hono_receivers = _hono_receiver_names(source)
    if not hono_receivers:
        return _dedupe_routes(_hono_apply_external_mounts(root, file_fact, openapi_routes))

    route_specs: list[dict[str, object]] = []
    for match in HONO_ROUTE_RE.finditer(source):
        receiver = match.group("receiver")
        if receiver not in hono_receivers:
            continue
        open_paren = source.find("(", match.start())
        close_paren = _find_matching_paren(source, open_paren)
        call_args = source[open_paren + 1 : close_paren] if close_paren is not None else match.group("args")
        raw_method = match.group("method").lower()
        method = raw_method.upper()
        if method == "ON":
            method = "ANY"
        elif method == "DOC":
            method = "GET"
        path = _hono_route_path(match.group("path"))
        line = _line_for_offset(source, match.start())
        route_specs.append(
            {
                "receiver": receiver,
                "method": method,
                "path": path,
                "handler": _hono_handler_name(receiver, raw_method),
                "line": line,
                "request_body": "json" if re.search(r"\bc\.req\.json(?:\s*<[^>]+>)?\s*\(", call_args) else None,
                "response_type": "openapi" if raw_method == "doc" else _hono_response_type(call_args),
            }
        )
    for match in HONO_CHAIN_ROUTE_RE.finditer(source):
        receiver = _hono_chained_receiver_name(source, match.start(), hono_receivers)
        if not receiver:
            continue
        open_paren = source.find("(", match.start())
        close_paren = _find_matching_paren(source, open_paren)
        call_args = source[open_paren + 1 : close_paren] if close_paren is not None else match.group("args")
        raw_method = match.group("method").lower()
        method = raw_method.upper()
        if method == "ON":
            method = "ANY"
        elif method == "DOC":
            method = "GET"
        path = _hono_route_path(match.group("path"))
        line = _line_for_offset(source, match.start())
        route_specs.append(
            {
                "receiver": receiver,
                "method": method,
                "path": path,
                "handler": _hono_handler_name(receiver, raw_method),
                "line": line,
                "request_body": "json" if re.search(r"\bc\.req\.json(?:\s*<[^>]+>)?\s*\(", call_args) else None,
                "response_type": "openapi" if raw_method == "doc" else _hono_response_type(call_args),
            }
        )

    mounted_children = {match.group("child") for match in HONO_MOUNT_RE.finditer(source) if match.group("receiver") in hono_receivers}
    direct_routes: list[ApiRouteFact] = []
    for spec in route_specs:
        if spec["receiver"] in mounted_children:
            continue
        direct_routes.append(_hono_route_fact(file_fact, spec, str(spec["path"])))

    for mount in HONO_MOUNT_RE.finditer(source):
        if mount.group("receiver") not in hono_receivers or mount.group("child") not in hono_receivers:
            continue
        prefix = _hono_route_path(mount.group("prefix"))
        for spec in route_specs:
            if spec["receiver"] != mount.group("child"):
                continue
            mounted_path = _join_paths(prefix, str(spec["path"]))
            routes.append(_hono_route_fact(file_fact, spec, mounted_path))
    routes.extend(_hono_apply_external_mounts(root, file_fact, openapi_routes + direct_routes))
    return _dedupe_routes(routes)


def _hono_receiver_names(source: str) -> set[str]:
    receivers = {match.group("name") for match in HONO_APP_RE.finditer(source)}
    receivers.update(match.group("name") for match in HONO_TYPED_RECEIVER_RE.finditer(source))
    return receivers


def _hono_chained_receiver_name(source: str, offset: int, hono_receivers: set[str]) -> str | None:
    candidate: str | None = None
    for match in HONO_APP_RE.finditer(source):
        if match.start() > offset:
            break
        name = match.group("name")
        if name in hono_receivers:
            candidate = name
    return candidate


def _extract_hono_openapi_routes(file_fact: FileFact, source: str) -> list[ApiRouteFact]:
    routes: list[ApiRouteFact] = []
    named_call_starts: set[int] = set()
    for match in HONO_OPENAPI_ROUTE_DECL_RE.finditer(source):
        call_start = source.find("createRoute", match.start())
        if call_start < 0:
            continue
        named_call_starts.add(call_start)
        route = _hono_openapi_route_from_call(file_fact, source, call_start, match.group("name"))
        if route:
            routes.append(route)

    for match in re.finditer(r"\bcreateRoute\s*\(", source):
        if match.start() in named_call_starts:
            continue
        route = _hono_openapi_route_from_call(file_fact, source, match.start(), "inline-openapi")
        if route:
            routes.append(route)
    return _dedupe_routes(routes)


def _hono_openapi_route_from_call(
    file_fact: FileFact,
    source: str,
    call_start: int,
    route_name: str,
) -> ApiRouteFact | None:
    open_paren = source.find("(", call_start)
    if open_paren < 0:
        return None
    object_start = source.find("{", open_paren, min(len(source), open_paren + 240))
    if object_start < 0:
        return None
    object_end = _find_matching_brace(source, object_start)
    if object_end is None:
        return None
    body = source[object_start + 1 : object_end]
    method = _hono_openapi_string_property(body, "method")
    raw_path = _hono_openapi_string_property(body, "path")
    if not method or not raw_path:
        return None
    line = _line_for_offset(source, call_start)
    path = _hono_route_path(raw_path)
    return ApiRouteFact(
        method=method.upper(),
        path=path,
        handler=route_name,
        framework="hono",
        kind="hono-openapi-route",
        evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
        parameters=_hono_path_parameters(path, file_fact.path, line),
        request_body=_hono_openapi_request_body(body),
        response_type=_hono_openapi_response_type(body),
    )


def _hono_openapi_string_property(body: str, name: str) -> str | None:
    match = re.search(rf"\b{name}\s*:\s*['\"`](?P<value>[^'\"`]+)['\"`]", body)
    return match.group("value") if match else None


def _hono_openapi_request_body(body: str) -> str | None:
    request_match = re.search(r"\brequest\s*:\s*\{(?P<body>[\s\S]*?)\n\s*\}", body)
    request_source = request_match.group("body") if request_match else body
    if re.search(r"\bbody\s*:", request_source):
        return "body"
    return None


def _hono_openapi_response_type(body: str) -> str | None:
    codes = _hono_openapi_status_codes(body)
    if codes:
        return "responses:" + ",".join(codes)
    if re.search(r"\bresponses\s*:", body):
        return "responses:unknown"
    return None


def _hono_openapi_status_codes(body: str) -> list[str]:
    codes: list[str] = []
    for name in re.findall(r"\bHttpStatusCodes\.([A-Z][A-Z0-9_]*)", body):
        codes.append(HONO_STATUS_CODE_NAMES.get(name, name))
    for code in re.findall(r"(?:^|[\s,{\[])([1-5]\d\d)\s*[]}]?\s*:", body):
        codes.append(code)
    return _dedupe_values(codes)


def _hono_route_fact(file_fact: FileFact, spec: dict[str, object], path: str) -> ApiRouteFact:
    line = int(spec["line"])
    return ApiRouteFact(
        method=str(spec["method"]),
        path=path,
        handler=str(spec["handler"]),
        framework="hono",
        kind="hono-route",
        evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
        parameters=_hono_path_parameters(path, file_fact.path, line),
        request_body=spec["request_body"] if isinstance(spec["request_body"], str) else None,
        response_type=spec["response_type"] if isinstance(spec["response_type"], str) else None,
    )


def _hono_apply_external_mounts(root: Path, file_fact: FileFact, routes: list[ApiRouteFact]) -> list[ApiRouteFact]:
    if not routes:
        return []
    prefixes = _hono_external_mount_prefixes(str(root), file_fact.path.replace("\\", "/"))
    if not prefixes:
        return routes
    prefixed_routes: list[ApiRouteFact] = []
    for prefix in prefixes:
        for route in routes:
            path = _join_paths(prefix, route.path)
            line = route.evidence.line_start or 1
            prefixed_routes.append(
                replace(
                    route,
                    path=path,
                    parameters=_hono_path_parameters(path, route.evidence.file, line),
                )
            )
    return prefixed_routes


@lru_cache(maxsize=512)
def _hono_external_mount_prefixes(root_text: str, target_path: str) -> tuple[str, ...]:
    root = Path(root_text)
    target = (root / target_path).resolve()
    prefixes: list[str] = []
    for candidate in root.rglob("*"):
        if not candidate.is_file() or candidate.suffix.lower() not in {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts"}:
            continue
        normalized = candidate.relative_to(root).as_posix()
        if _is_noisy_hono_import_scan_path(normalized) or candidate.resolve() == target:
            continue
        source = candidate.read_text(encoding="utf-8", errors="ignore")
        if ".route(" not in source or "import" not in source:
            continue
        imported_symbols = _hono_imported_symbols_for_target(root, candidate, source, target)
        if not imported_symbols:
            continue
        receivers = _hono_receiver_names(source)
        for mount in HONO_MOUNT_RE.finditer(source):
            if receivers and mount.group("receiver") not in receivers:
                continue
            if mount.group("child") in imported_symbols:
                prefixes.append(_hono_route_path(mount.group("prefix")))
        for mount in HONO_CHAIN_MOUNT_RE.finditer(source):
            if mount.group("child") in imported_symbols:
                prefixes.append(_hono_route_path(mount.group("prefix")))
    return tuple(_dedupe_values(prefixes))


def _is_noisy_hono_import_scan_path(path: str) -> bool:
    parts = set(path.replace("\\", "/").split("/")[:-1])
    return bool(parts & {"node_modules", ".git", "dist", "build", ".next", ".svelte-kit", "coverage"})


def _hono_imported_symbols_for_target(root: Path, importer: Path, source: str, target: Path) -> set[str]:
    symbols: set[str] = set()
    for match in HONO_LOCAL_IMPORT_RE.finditer(source):
        resolved = _resolve_hono_local_import(root, importer.parent, match.group("module"))
        if resolved is None or resolved.resolve() != target:
            continue
        default_name = match.group("default")
        if default_name:
            symbols.add(default_name)
        symbols.update(_hono_named_import_symbols(match.group("named") or ""))
    return symbols


def _resolve_hono_local_import(root: Path, importer_dir: Path, module: str) -> Path | None:
    raw = (importer_dir / module).resolve()
    code_suffixes = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts")
    candidates: list[Path]
    if raw.suffix and raw.suffix.lower() in code_suffixes:
        candidates = [raw]
    elif raw.suffix:
        candidates = [
            raw,
            *(Path(f"{raw}{suffix}") for suffix in code_suffixes),
        ]
    else:
        candidates = [
            *(raw.with_suffix(suffix) for suffix in code_suffixes),
            *(raw / f"index{suffix}" for suffix in code_suffixes),
        ]
    root_resolved = root.resolve()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            resolved.relative_to(root_resolved)
        except ValueError:
            continue
        if candidate.exists() and candidate.is_file():
            return resolved
    return None


def _hono_named_import_symbols(named_source: str) -> set[str]:
    symbols: set[str] = set()
    for raw_part in named_source.split(","):
        part = raw_part.strip()
        if not part:
            continue
        alias_match = re.match(r"(?P<name>[A-Za-z_$][\w$]*)\s+as\s+(?P<alias>[A-Za-z_$][\w$]*)$", part)
        if alias_match:
            symbols.add(alias_match.group("alias"))
            continue
        name_match = re.match(r"(?P<name>[A-Za-z_$][\w$]*)$", part)
        if name_match:
            symbols.add(name_match.group("name"))
    return symbols


def _looks_like_hono_source(source: str) -> bool:
    return (
        "from 'hono'" in source
        or 'from "hono"' in source
        or "new Hono" in source
        or "new OpenAPIHono" in source
        or "OpenAPIHono" in source
        or "AppOpenAPI" in source
        or "createRoute(" in source
        or "@hono/" in source
        or "hono/" in source
    )


def _looks_like_fresh_source(source: str) -> bool:
    return (
        "from 'fresh'" in source
        or 'from "fresh"' in source
        or "from '$fresh" in source
        or 'from "$fresh' in source
        or "define.handlers" in source
        or ".fsRoutes()" in source
        or re.search(r"\bnew\s+App\s*\(", source) is not None
    )


def _extract_elysia_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    if not _looks_like_elysia_source(source):
        return []
    routes: list[ApiRouteFact] = []
    for match in ELYSIA_ROUTE_RE.finditer(source):
        if _offset_is_comment_line(source, match.start()):
            continue
        open_paren = source.find("(", match.start())
        close_paren = _find_matching_paren(source, open_paren)
        call_args = source[open_paren + 1 : close_paren] if close_paren is not None else match.group("args") or ""
        raw_path = match.group("path")
        line = _line_for_offset(source, match.start())
        app_start = _elysia_app_start(source, match.start())
        app_prefix = _elysia_app_prefix(source, app_start)
        group_prefix = _elysia_group_prefix(source, match.start(), app_start)
        path = _join_paths(_join_paths(app_prefix or "", group_prefix or ""), _elysia_route_path(raw_path))
        routes.append(
            ApiRouteFact(
                method=match.group("method").upper(),
                path=path,
                handler=_elysia_handler_name(match.group("args") or ""),
                framework="elysia",
                kind="elysia-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                parameters=_elysia_path_parameters(path, file_fact.path, line),
                request_body=_elysia_request_body(match.group("method"), call_args),
                response_type=_elysia_response_type(call_args),
            )
        )
    return _dedupe_routes(routes)


def _looks_like_elysia_source(source: str) -> bool:
    return (
        "from 'elysia'" in source
        or 'from "elysia"' in source
        or "new Elysia" in source
        or re.search(r"\bElysia\b", source) is not None and re.search(r"\.(?:get|post|put|patch|delete|all)\s*\(\s*['\"`]/", source) is not None
    )


def _elysia_app_start(source: str, offset: int) -> int:
    start = source.rfind("new Elysia", 0, offset)
    if start < 0:
        return 0
    return start


def _elysia_app_prefix(source: str, start: int) -> str | None:
    if start < 0:
        return None
    match = ELYSIA_PREFIX_RE.search(source[start : min(len(source), start + 400)])
    return match.group("prefix") if match else None


def _elysia_group_prefix(source: str, offset: int, app_start: int) -> str | None:
    start = max(app_start, offset - 1600)
    matches = [match for match in ELYSIA_GROUP_RE.finditer(source[start:offset]) if not _offset_is_comment_line(source, start + match.start())]
    if not matches:
        return None
    return matches[-1].group("prefix")


def _elysia_route_path(path: str) -> str:
    normalized = _ensure_slash(path)
    normalized = re.sub(r"\$\{([A-Za-z_$][\w$]*)\}", r"{\1}", normalized)
    normalized = re.sub(r":([A-Za-z_$][\w$]*)", r"{\1}", normalized)
    return normalized


def _elysia_path_parameters(path: str, file_path: str, line: int) -> list[RequestParamFact]:
    return [
        RequestParamFact(
            name=name.strip("*"),
            source="path",
            type=None,
            required=True,
            evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
        )
        for name in re.findall(r"\{([^}]+)\}", path)
        if name.strip("*")
    ]


def _elysia_handler_name(args: str) -> str | None:
    parts = _split_params(args)
    if len(parts) < 2:
        return None
    candidate = parts[1].strip()
    if re.fullmatch(r"[A-Za-z_$][\w$.\[\]]*", candidate):
        return candidate
    return None


def _elysia_request_body(method: str, args: str) -> str | None:
    if re.search(r"\bbody\s*:", args):
        return "schema"
    if method.lower() in {"post", "put", "patch"} and re.search(r"\bbody\b", args):
        return "body"
    return None


def _elysia_response_type(args: str) -> str | None:
    if "new Response" in args:
        return "Response"
    if re.search(r"\bredirect\s*\(", args):
        return "redirect"
    if re.search(r"=>\s*['\"`]", args):
        return "string"
    return None


def _hono_route_path(path: str) -> str:
    normalized = path if path.startswith("/") else f"/{path}"
    normalized = re.sub(r":([A-Za-z_$][\w$]*)\{[^}]+\}", r"{\1}", normalized)
    normalized = re.sub(r":([A-Za-z_$][\w$]*)", r"{\1}", normalized)
    normalized = normalized.replace("*", "{*}")
    return normalized


def _hono_handler_name(receiver: str, method: str) -> str:
    return f"{receiver}.{method.lower()}"


def _hono_response_type(args: str) -> str | None:
    if re.search(r"\bc\.json\s*\(", args):
        return "json"
    if re.search(r"\bc\.text\s*\(", args):
        return "text"
    if "new Response" in args:
        return "Response"
    return None


def _hono_path_parameters(path: str, file_path: str, line: int) -> list[RequestParamFact]:
    return [
        RequestParamFact(
            name=name.strip("*"),
            source="path",
            type=None,
            required=True,
            evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
        )
        for name in re.findall(r"\{([^}]+)\}", path)
        if name.strip("*")
    ]


def _extract_express_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    if _looks_like_koa_router_source(source) or _looks_like_hono_source(source) or _looks_like_fresh_source(source) or _looks_like_elysia_source(source):
        return []
    routes: list[ApiRouteFact] = []
    for match in EXPRESS_ROUTE_RE.finditer(source):
        if _offset_is_comment_line(source, match.start()):
            continue
        if _is_remix_express_catchall(source, match):
            continue
        line = _line_for_offset(source, match.start())
        path = match.group("path")
        routes.append(
            ApiRouteFact(
                method=match.group("method").upper(),
                path=path,
                handler=_express_route_handler(source, match.start(), match.group("handler")),
                framework="express",
                kind="express-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                parameters=_express_path_parameters(path, file_fact.path, line),
            )
        )
    return routes


def _express_route_handler(source: str, offset: int, fallback: str | None) -> str | None:
    open_index = source.find("(", offset)
    close_index = _find_matching_paren(source, open_index)
    if close_index is None:
        return fallback
    args = _split_params(source[open_index + 1 : close_index])
    for arg in reversed(args[1:]):
        stripped = arg.strip()
        if not stripped:
            continue
        if re.match(r"(?:async\s*)?(?:function\b|\([^)]*\)\s*=>|[A-Za-z_$][\w$]*\s*=>)", stripped):
            return "inline" if fallback is not None or len(args) > 2 else None
        identifier = re.match(r"(?P<name>[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)", stripped)
        if identifier:
            return identifier.group("name")
    return fallback


def _express_path_parameters(path: str, file_path: str, line: int) -> list[RequestParamFact]:
    return [
        RequestParamFact(
            name=name,
            source="path",
            type=None,
            required=True,
            evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
        )
        for name in re.findall(r":([A-Za-z_$][\w$]*)", path)
    ]


def _is_remix_express_catchall(source: str, match: re.Match[str]) -> bool:
    if match.group("method").lower() != "all" or match.group("path") != "*":
        return False
    if "createRequestHandler" not in source or "@remix-run/express" not in source:
        return False
    window = source[match.start() : match.end() + 1200]
    return "createRequestHandler" in window or "getReplayResponse" in window or "fly-replay" in window


def _apply_express_mount_prefixes(root: Path, files: list[FileFact], routes: list[ApiRouteFact]) -> list[ApiRouteFact]:
    prefixes = _express_mount_prefixes(root, files)
    if not prefixes:
        return routes
    result: list[ApiRouteFact] = []
    for route in routes:
        if route.framework != "express":
            result.append(route)
            continue
        route_prefixes = prefixes.get(route.evidence.file)
        if not route_prefixes:
            result.append(route)
            continue
        for prefix in route_prefixes:
            if route.path == prefix or route.path.startswith(f"{prefix.rstrip('/')}/"):
                mounted_path = route.path
            else:
                mounted_path = _join_paths(prefix, route.path)
            result.append(
                replace(
                    route,
                    path=mounted_path,
                    kind="express-mounted-route",
                    parameters=route.parameters or _express_path_parameters(mounted_path, route.evidence.file, route.evidence.line_start),
                )
            )
    return _dedupe_routes_with_handler(result)


def _express_mount_prefixes(root: Path, files: list[FileFact]) -> dict[str, list[str]]:
    prefixes: dict[str, list[str]] = {}
    edges: list[tuple[str, str, str]] = []
    for file_fact in files:
        if file_fact.language not in {"typescript", "javascript"} or file_fact.role in {"test", "sample", "generated"}:
            continue
        source = _read(root, file_fact)
        if ".use(" not in source:
            continue
        import_map = _express_local_imports(root, file_fact, source)
        if not import_map:
            continue
        chain_children: dict[str, list[str]] = {}
        for chain_match in EXPRESS_ROUTER_CHAIN_RE.finditer(source):
            children: list[str] = []
            for use_match in EXPRESS_CHAIN_USE_RE.finditer(chain_match.group("chain")):
                target_file = import_map.get(use_match.group("target"))
                if target_file:
                    children.append(target_file)
            if children:
                chain_children[chain_match.group("name")] = children
        for mount_match in EXPRESS_MOUNT_USE_RE.finditer(source):
            prefix = _ensure_slash(mount_match.group("prefix"))
            target = mount_match.group("target")
            target_files = chain_children.get(target) or ([import_map[target]] if target in import_map else [])
            for target_file in target_files:
                edges.append((file_fact.path, prefix, target_file))
    mounted_sources = {target_file for _, _, target_file in edges}
    for source_file, prefix, target_file in edges:
        if source_file in mounted_sources:
            continue
        _add_express_prefix(prefixes, target_file, prefix)
    changed = True
    while changed:
        changed = False
        for source_file, prefix, target_file in edges:
            for parent_prefix in prefixes.get(source_file, []):
                changed = _add_express_prefix(prefixes, target_file, _join_paths(parent_prefix, prefix)) or changed
    return prefixes


def _express_local_imports(root: Path, file_fact: FileFact, source: str) -> dict[str, str]:
    importer_dir = (root / file_fact.path).parent
    result: dict[str, str] = {}
    for match in [*EXPRESS_LOCAL_IMPORT_RE.finditer(source), *EXPRESS_LOCAL_REQUIRE_RE.finditer(source)]:
        resolved = _resolve_hono_local_import(root, importer_dir, match.group("module"))
        if resolved is None:
            continue
        try:
            result[match.group("name")] = resolved.relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
    return result


def _add_express_prefix(prefixes: dict[str, list[str]], target_file: str, prefix: str) -> bool:
    clean = _ensure_slash(prefix)
    prefixes.setdefault(target_file, [])
    if clean in prefixes[target_file]:
        return False
    prefixes[target_file].append(clean)
    return True


def _extract_koa_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    if not _looks_like_koa_router_source(source):
        return []
    routes: list[ApiRouteFact] = []
    for match in KOA_ROUTE_RE.finditer(source):
        line = _line_for_offset(source, match.start())
        routes.append(
            ApiRouteFact(
                method=_koa_method(match.group("method")),
                path=match.group("path"),
                handler=_koa_handler_from_args(match.group("args") or ""),
                framework="koa",
                kind="koa-router-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
            )
        )
    return _dedupe_routes(routes)


def _looks_like_koa_router_source(source: str) -> bool:
    return (
        "koa-router" in source
        or "@koa/router" in source
        or re.search(r"\bnew\s+Router\(", source) is not None and "koa" in source.lower()
    )


def _koa_method(method: str) -> str:
    normalized = method.upper()
    return "DELETE" if normalized == "DEL" else normalized


def _koa_handler_from_args(args: str) -> str | None:
    parts = [part.strip() for part in _split_params(args.lstrip(",")) if part.strip()]
    for part in reversed(parts):
        match = re.match(r"(?P<handler>[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\b", part)
        if match:
            return match.group("handler")
    return None


def _apply_koa_mount_prefixes(root: Path, files: list[FileFact], routes: list[ApiRouteFact]) -> list[ApiRouteFact]:
    prefix = _koa_mount_prefix(root, files)
    if not prefix:
        return routes
    updated: list[ApiRouteFact] = []
    for route in routes:
        if route.framework != "koa" or _path_has_prefix(route.path, prefix):
            updated.append(route)
            continue
        updated.append(replace(route, path=_join_paths(prefix, route.path)))
    return updated


def _koa_mount_prefix(root: Path, files: list[FileFact]) -> str | None:
    prefixes: list[str] = []
    for file_fact in files:
        if file_fact.language not in {"javascript", "typescript"} or file_fact.role in {"test", "sample", "generated"}:
            continue
        source = _read(root, file_fact)
        for match in KOA_MOUNT_RE.finditer(source):
            prefixes.append(match.group("prefix"))
    return prefixes[0] if len(set(prefixes)) == 1 else None


def _path_has_prefix(path: str, prefix: str) -> bool:
    normalized = prefix.rstrip("/")
    return path == normalized or path.startswith(f"{normalized}/")


def _extract_hapi_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    if not _looks_like_hapi_route_source(file_fact.path, source):
        return []

    routes: list[ApiRouteFact] = []
    seen_spans: set[tuple[int, int]] = set()
    for match in HAPI_METHOD_RE.finditer(source):
        span = _hapi_route_object_span(source, match.start())
        if span is None or span in seen_spans:
            continue
        seen_spans.add(span)
        body = source[span[0] + 1 : span[1]]
        route_path = _hapi_route_path(body)
        if not route_path:
            continue
        handler = _hapi_route_handler(body)
        line = _line_for_offset(source, span[0])
        validation_hint = _hapi_validation_hint(body)
        response_type = _hapi_response_hint(body)
        for method in _hapi_route_methods(body):
            routes.append(
                ApiRouteFact(
                    method=method,
                    path=route_path,
                    handler=handler,
                    framework="hapi",
                    kind="hapi-route",
                    evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                    parameters=_hapi_path_parameters(route_path, file_fact.path, line),
                    request_body=_hapi_request_body_hint(method, validation_hint),
                    response_type=response_type,
                )
            )
    return _dedupe_routes(routes)


def _looks_like_hapi_route_source(path: str, source: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    if "server.route(" in source:
        return True
    if not (normalized.endswith("/routes.js") or normalized.endswith("/routes.ts")):
        return False
    return "handler:" in source and "method:" in source and "path:" in source


def _hapi_route_object_span(source: str, offset: int) -> tuple[int, int] | None:
    call_span = _hapi_server_route_object_span(source, offset)
    if call_span is not None:
        return call_span

    open_index = source.rfind("{", 0, offset)
    while open_index >= 0:
        close_index = _find_matching_brace(source, open_index)
        if close_index is not None and close_index >= offset:
            body = source[open_index + 1 : close_index]
            if HAPI_METHOD_RE.search(body) and HAPI_PATH_RE.search(body) and _hapi_has_handler(body):
                return open_index, close_index
        open_index = source.rfind("{", 0, open_index)
    return None


def _hapi_server_route_object_span(source: str, offset: int) -> tuple[int, int] | None:
    for call in reversed(list(re.finditer(r"\bserver\.route\s*\(", source[: offset + 1]))):
        paren = source.find("(", call.start())
        open_index = _first_non_ws_index(source, paren + 1)
        if open_index is None or open_index >= len(source) or source[open_index] != "{":
            continue
        close_index = _find_matching_brace(source, open_index)
        if close_index is None or not (open_index <= offset <= close_index):
            continue
        body = source[open_index + 1 : close_index]
        if HAPI_METHOD_RE.search(body) and HAPI_PATH_RE.search(body) and _hapi_has_handler(body):
            return open_index, close_index
    return None


def _first_non_ws_index(source: str, start: int) -> int | None:
    for index in range(start, len(source)):
        if not source[index].isspace():
            return index
    return None


def _hapi_route_path(body: str) -> str | None:
    match = HAPI_PATH_RE.search(body)
    if not match:
        return None
    return _ensure_slash(match.group("path"))


def _hapi_has_handler(body: str) -> bool:
    return HAPI_HANDLER_RE.search(body) is not None or HAPI_INLINE_HANDLER_RE.search(body) is not None


def _hapi_route_handler(body: str) -> str | None:
    match = HAPI_HANDLER_RE.search(body)
    if match:
        return match.group("handler")
    if HAPI_INLINE_HANDLER_RE.search(body):
        return "inline-handler"
    return None


def _hapi_path_parameters(path: str, file_path: str, line: int) -> list[RequestParamFact]:
    return [
        RequestParamFact(
            name=name,
            source="path",
            type=None,
            required=True,
            evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
        )
        for name in re.findall(r"\{([A-Za-z_$][\w$]*)\}", path)
    ]


def _hapi_route_methods(body: str) -> list[str]:
    match = HAPI_METHOD_RE.search(body)
    if not match:
        return ["ANY"]
    if match.group("method"):
        return [_hapi_method(match.group("method"))]
    methods = re.findall(r"['\"`](GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD|ANY)['\"`]", match.group("methods") or "", re.IGNORECASE)
    return [_hapi_method(method) for method in methods] or ["ANY"]


def _hapi_method(value: str) -> str:
    method = value.upper()
    return "ANY" if method == "ALL" else method


def _hapi_validation_hint(body: str) -> str | None:
    match = HAPI_VALIDATE_RE.search(body)
    return match.group("validate") if match else None


def _hapi_response_hint(body: str) -> str | None:
    match = HAPI_RESPONSE_RE.search(body)
    return match.group("response") if match else None


def _hapi_request_body_hint(method: str, validation_hint: str | None) -> str | None:
    if not validation_hint:
        return None
    lower = validation_hint.lower()
    if method.upper() in {"POST", "PUT", "PATCH"} and "params" not in lower and "query" not in lower:
        return validation_hint
    return None


def _apply_hapi_mount_prefixes(root: Path, files: list[FileFact], routes: list[ApiRouteFact]) -> list[ApiRouteFact]:
    prefix = _hapi_mount_prefix(root, files)
    if not prefix:
        return routes
    updated: list[ApiRouteFact] = []
    for route in routes:
        if route.framework != "hapi" or _path_has_prefix(route.path, prefix):
            updated.append(route)
            continue
        normalized = route.evidence.file.replace("\\", "/").lower()
        if "/modules/api/" in normalized or normalized.endswith("/api/index.js") or normalized.endswith("/api/index.ts"):
            updated.append(replace(route, path=_join_paths(prefix, route.path)))
        else:
            updated.append(route)
    return updated


def _hapi_mount_prefix(root: Path, files: list[FileFact]) -> str | None:
    prefixes: list[str] = []
    for file_fact in files:
        normalized = file_fact.path.replace("\\", "/").lower()
        if file_fact.language not in {"javascript", "typescript"} or file_fact.role in {"test", "sample", "generated"}:
            continue
        if not (normalized.endswith("manifest.js") or normalized.endswith("manifest.ts") or "config" in normalized):
            continue
        source = _read(root, file_fact)
        for match in HAPI_PLUGIN_PREFIX_RE.finditer(source):
            prefixes.append(match.group("prefix"))
    return prefixes[0] if len(set(prefixes)) == 1 else None


def _extract_adonis_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    if not _looks_like_adonis_route_source(file_fact.path, source):
        return []
    group_prefixes = _adonis_group_prefixes(source)
    routes: list[ApiRouteFact] = []
    for match in ADONIS_ROUTE_RE.finditer(source):
        if _offset_is_comment_line(source, match.start()):
            continue
        method = _adonis_method(match.group("method"))
        path = _join_paths(_adonis_prefix_for_offset(group_prefixes, match.start()), match.group("path"))
        line = _line_for_offset(source, match.start())
        routes.append(
            ApiRouteFact(
                method=method,
                path=path,
                handler=match.group("handler"),
                framework="adonisjs",
                kind="adonis-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
            )
        )
    for match in ADONIS_RESOURCE_RE.finditer(source):
        if _offset_is_comment_line(source, match.start()):
            continue
        line = _line_for_offset(source, match.start())
        prefix = _adonis_prefix_for_offset(group_prefixes, match.start())
        routes.extend(_adonis_resource_routes(file_fact, match, prefix, line))
    return _dedupe_routes(routes)


def _looks_like_adonis_route_source(path: str, source: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return (
        "@ioc:Adonis/Core/Route" in source
        or normalized.endswith("start/routes.ts")
        or normalized.endswith("start/routes.js")
    ) and "Route." in source


def _adonis_group_prefixes(source: str) -> list[tuple[int, int, str]]:
    prefixes: list[tuple[int, int, str]] = []
    for match in re.finditer(r"\bRoute\.group\(\s*\(\s*\)\s*=>\s*\{", source):
        body_start = source.find("{", match.start())
        body_end = _find_matching_brace(source, body_start)
        if body_end is None:
            continue
        chain = source[body_end : body_end + 260]
        prefix_match = re.search(r"\.prefix\(\s*['\"`](?P<prefix>[^'\"`]*)['\"`]\s*\)", chain)
        prefixes.append((body_start, body_end, prefix_match.group("prefix") if prefix_match else ""))
    return prefixes


def _adonis_prefix_for_offset(prefixes: list[tuple[int, int, str]], offset: int) -> str:
    matched = [prefix for start, end, prefix in prefixes if start <= offset <= end and prefix]
    return matched[-1] if matched else ""


def _adonis_method(method: str) -> str:
    normalized = method.upper()
    return "ANY" if normalized == "ANY" else normalized


def _adonis_resource_routes(file_fact: FileFact, match: re.Match[str], prefix: str, line: int) -> list[ApiRouteFact]:
    base = _join_paths(prefix, match.group("path"))
    controller = match.group("handler")
    chain = match.group("chain") or ""
    api_only = ".apiOnly(" in chain or ".apiOnly()" in chain
    singleton = ".singleton(" in chain or ".singleton()" in chain
    param = f"{_singular_name(Path(base).name)}_id"
    member = base if singleton else _join_paths(base, f":{param}")
    templates = [
        ("GET", base, "index"),
        ("POST", base, "store"),
        ("GET", member, "show"),
        ("PUT", member, "update"),
        ("PATCH", member, "update"),
        ("DELETE", member, "destroy"),
    ]
    if not api_only:
        templates.insert(1, ("GET", _join_paths(base, "create"), "create"))
        templates.insert(4, ("GET", _join_paths(member, "edit"), "edit"))
    return [
        ApiRouteFact(
            method=method,
            path=path,
            handler=f"{controller}.{action}",
            framework="adonisjs",
            kind="adonis-resource-route",
            evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
        )
        for method, path, action in templates
    ]


def _singular_name(value: str) -> str:
    name = value.strip("/:{}") or "id"
    if name.endswith("ies"):
        return f"{name[:-3]}y"
    if name.endswith("s") and len(name) > 1:
        return name[:-1]
    return name


def _offset_is_comment_line(source: str, offset: int) -> bool:
    line_start = source.rfind("\n", 0, offset) + 1
    if source[line_start:offset].lstrip().startswith(("//", "*", "|", "/*")):
        return True
    block_starts = [match.start() for match in re.finditer(r"(?<!/)\/\*", source[:offset])]
    block_start = block_starts[-1] if block_starts else -1
    block_end = source.rfind("*/", 0, offset)
    return block_start > block_end


def _extract_sails_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    if not _looks_like_sails_routes_file(file_fact.path, source):
        return []
    routes: list[ApiRouteFact] = []
    for match in SAILS_ROUTE_KEY_RE.finditer(source):
        if _offset_is_comment_line(source, match.start()):
            continue
        line = _line_for_offset(source, match.start())
        value_source = _sails_route_value_source(source, match.end())
        handler = _sails_route_handler(value_source)
        kind = "sails-view-route" if handler and handler.startswith("view:") else "sails-route"
        routes.append(
            ApiRouteFact(
                method=(match.group("method") or "GET").upper().replace("ALL", "ANY"),
                path=_ensure_slash(match.group("path")),
                handler=handler,
                framework="sails",
                kind=kind,
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
            )
        )
    return _dedupe_routes(routes)


def _looks_like_sails_routes_file(path: str, source: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return normalized.endswith("config/routes.js") and "module.exports.routes" in source


def _sails_route_handler(value_source: str) -> str | None:
    action = SAILS_ACTION_RE.search(value_source)
    if action:
        return action.group("action")
    view = SAILS_VIEW_RE.search(value_source)
    if view:
        return f"view:{view.group('view')}"
    if re.match(r"\s*(?:async\s+)?function\b", value_source):
        return "inline"
    return None


def _sails_route_value_source(source: str, offset: int) -> str:
    cursor = offset
    while cursor < len(source) and source[cursor].isspace():
        cursor += 1
    if cursor < len(source) and source[cursor] == "{":
        end = _find_matching_brace(source, cursor)
        return source[cursor + 1 : end] if end is not None else source[cursor : cursor + 1200]
    comma = source.find(",\n", cursor)
    end = comma if comma >= 0 else min(len(source), cursor + 1200)
    return source[cursor:end]


def _extract_loopback_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    if not _looks_like_loopback_route_source(source):
        return []

    routes: list[ApiRouteFact] = []
    for match in LOOPBACK_ROUTE_RE.finditer(source):
        if _offset_is_comment_line(source, match.start()):
            continue
        line = _line_for_offset(source, match.start())
        decorator_end = _loopback_decorator_end(source, match.start())
        method_info = _loopback_method_info_after(source, decorator_end, file_fact.path, line)
        routes.append(
            ApiRouteFact(
                method=_loopback_method(match.group("method")),
                path=_ensure_slash(match.group("path")),
                handler=method_info["name"],
                framework="loopback",
                kind="loopback-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                parameters=method_info["parameters"],
                request_body=method_info["request_body"],
                response_type=method_info["response_type"],
            )
        )
    return _dedupe_routes(routes)


def _loopback_decorator_end(source: str, offset: int) -> int:
    open_paren = source.find("(", offset)
    close_paren = _find_matching_paren(source, open_paren)
    return close_paren + 1 if close_paren is not None else offset


def _looks_like_loopback_route_source(source: str) -> bool:
    return (
        "@loopback/rest" in source
        or "from '@loopback/rest'" in source
        or 'from "@loopback/rest"' in source
    ) and LOOPBACK_ROUTE_RE.search(source) is not None


def _loopback_method(method: str) -> str:
    normalized = method.upper()
    return "DELETE" if normalized in {"DEL", "DELETE"} else normalized


def _loopback_method_info_after(source: str, offset: int, file_path: str, line: int) -> dict[str, object]:
    start = _skip_typescript_decorators(source, offset)
    match = LOOPBACK_METHOD_RE.search(source[start : start + 1200])
    if not match:
        return {"name": None, "parameters": [], "request_body": None, "response_type": None}
    absolute_start = start + match.start()
    paren_start = source.find("(", absolute_start)
    paren_end = _find_matching_paren(source, paren_start)
    params_source = source[paren_start + 1 : paren_end] if paren_end is not None else ""
    parameters = _loopback_request_params(params_source, file_path, line)
    request_body = next((param.type or param.name for param in parameters if param.source == "body"), None)
    response_type = _typescript_return_type_after(source, paren_end or paren_start)
    return {
        "name": match.group("name"),
        "parameters": parameters,
        "request_body": request_body,
        "response_type": response_type,
    }


def _loopback_request_params(params_source: str, file_path: str, line: int) -> list[RequestParamFact]:
    params: list[RequestParamFact] = []
    for raw_param in _split_params(params_source):
        source = _loopback_param_source(raw_param)
        if source is None:
            continue
        param_name, type_name, required = _typescript_param_shape(raw_param)
        explicit_name = _loopback_param_name(raw_param)
        decorator_type = _loopback_param_type(raw_param)
        params.append(
            RequestParamFact(
                name=explicit_name or param_name or "body",
                source=source,
                type=decorator_type or type_name,
                required=True if source == "path" else required,
                evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
            )
        )
    return params


def _loopback_param_source(raw_param: str) -> str | None:
    match = re.search(r"@param\.(?P<source>path|query|header|cookie|body)\b", raw_param)
    if match:
        return match.group("source")
    if "@requestBody" in raw_param:
        return "body"
    return None


def _loopback_param_name(raw_param: str) -> str | None:
    match = re.search(r"@param\.[A-Za-z_$][\w$.]*\(\s*['\"`]([^'\"`]+)['\"`]", raw_param)
    return match.group(1) if match else None


def _loopback_param_type(raw_param: str) -> str | None:
    match = re.search(r"@param\.[A-Za-z_$][\w$]*\.(?P<type>[A-Za-z_$][\w$]*)\s*\(", raw_param)
    return match.group("type") if match else None


def _typescript_param_shape(raw_param: str) -> tuple[str | None, str | None, bool | None]:
    tail = _strip_inline_typescript_decorators(raw_param)
    match = re.search(r"\b(?P<name>[A-Za-z_$][\w$]*)(?P<optional>\?)?\s*:\s*(?P<type>.+?)\s*$", tail, re.DOTALL)
    if not match:
        return None, None, None
    type_name = " ".join(match.group("type").rstrip(",").split())
    required = False if match.group("optional") else None
    return match.group("name"), type_name, required


def _strip_inline_typescript_decorators(raw_param: str) -> str:
    tail = raw_param.strip()
    while tail.startswith("@"):
        match = re.match(r"@\s*[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)?(?:\([^)]*\))?\s*", tail, re.DOTALL)
        if not match:
            break
        tail = tail[match.end() :].strip()
    return tail


def _typescript_return_type_after(source: str, paren_end: int) -> str | None:
    if paren_end < 0:
        return None
    tail = source[paren_end + 1 : paren_end + 800]
    prefix = re.match(r"\s*:\s*", tail)
    if not prefix:
        return None
    index = prefix.end()
    start = index
    depths = {"<": 0, "{": 0, "(": 0, "[": 0}
    closing = {">": "<", "}": "{", ")": "(", "]": "["}
    quote: str | None = None
    escaped = False
    saw_type_token = False
    while index < len(tail):
        char = tail[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char in {"'", '"', "`"}:
            quote = char
            saw_type_token = True
            index += 1
            continue
        if char == "{" and not any(depths.values()) and saw_type_token:
            return " ".join(tail[start:index].strip().split()) or None
        if char in depths:
            depths[char] += 1
            saw_type_token = True
        elif char in closing:
            opener = closing[char]
            depths[opener] = max(0, depths[opener] - 1)
            saw_type_token = True
        elif char == ";" and not any(depths.values()):
            return " ".join(tail[start:index].strip().split()) or None
        elif not char.isspace():
            saw_type_token = True
        index += 1
    return None


def _extract_feathers_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    if not _looks_like_feathers_service_source(file_fact.path, source):
        return []

    routes: list[ApiRouteFact] = []
    for match in FEATHERS_SERVICE_USE_RE.finditer(source):
        if _offset_is_comment_line(source, match.start()):
            continue
        service_path = _ensure_slash(match.group("path"))
        line = _line_for_offset(source, match.start())
        methods = _feathers_service_methods(root, file_fact, source)
        for service_method in methods:
            method, suffix = FEATHERS_SERVICE_METHODS[service_method]
            route_path = _feathers_route_path(service_path, suffix)
            parameters = _feathers_route_parameters(route_path, file_fact.path, line)
            routes.append(
                ApiRouteFact(
                    method=method,
                    path=route_path,
                    handler=f"service.{service_method}",
                    framework="feathers",
                    kind="feathers-service-route",
                    evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                    parameters=parameters,
                    request_body="data" if service_method in {"create", "update", "patch"} else None,
                )
            )
    return _dedupe_routes(routes)


def _looks_like_feathers_service_source(path: str, source: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return (
        "/services/" in f"/{normalized}"
        and "app.use(" in source
        and (
            "feathers-" in source
            or "service.hooks" in source
            or "app.service(" in source
            or re.search(r"require\(['\"][^'\"]+\.class(?:\.js|\.ts)?['\"]\)", source) is not None
        )
    )


def _feathers_service_methods(root: Path, file_fact: FileFact, source: str) -> list[str]:
    if re.search(r"require\(['\"](?:feathers-mongoose|feathers-nedb|feathers-memory)['\"]\)", source):
        return list(FEATHERS_SERVICE_METHODS)
    class_source = _feathers_class_source(root, file_fact, source)
    if class_source:
        methods = [
            method
            for method in FEATHERS_SERVICE_METHODS
            if re.search(rf"\b(?:async\s+)?{re.escape(method)}\s*\(", class_source)
        ]
        if methods:
            return methods
    inline_methods = [
        method
        for method in FEATHERS_SERVICE_METHODS
        if re.search(rf"\b(?:async\s+)?{re.escape(method)}\s*\(", source)
    ]
    return inline_methods or list(FEATHERS_SERVICE_METHODS)


def _feathers_class_source(root: Path, file_fact: FileFact, source: str) -> str:
    match = re.search(r"require\(\s*['\"](?P<path>[^'\"]+\.class(?:\.js|\.ts)?)['\"]\s*\)", source)
    if not match:
        return ""
    service_dir = Path(file_fact.path).parent
    candidate = (root / service_dir / match.group("path")).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return ""
    if not candidate.exists():
        return ""
    return candidate.read_text(encoding="utf-8", errors="ignore")


def _feathers_route_path(service_path: str, suffix: str) -> str:
    if not suffix:
        return service_path
    return _join_paths(service_path, suffix)


def _feathers_route_parameters(path: str, file_path: str, line: int) -> list[RequestParamFact]:
    params: list[RequestParamFact] = []
    for name in re.findall(r":([A-Za-z_$][\w$]*)", path):
        params.append(
            RequestParamFact(
                name=name,
                source="path",
                type=None,
                required=True,
                evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
            )
        )
    for name in re.findall(r"\{([^}]+)\}", path):
        params.append(
            RequestParamFact(
                name=name,
                source="path",
                type=None,
                required=True,
                evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
            )
        )
    return params


def _apply_feathers_mount_prefixes(root: Path, files: list[FileFact], routes: list[ApiRouteFact]) -> list[ApiRouteFact]:
    prefix = _feathers_mount_prefix(root, files)
    if not prefix:
        return routes
    updated: list[ApiRouteFact] = []
    for route in routes:
        if route.framework != "feathers" or _path_has_prefix(route.path, prefix):
            updated.append(route)
            continue
        updated.append(replace(route, path=_join_paths(prefix, route.path)))
    return updated


def _feathers_mount_prefix(root: Path, files: list[FileFact]) -> str | None:
    prefixes: list[str] = []
    for file_fact in files:
        normalized = file_fact.path.replace("\\", "/").lower()
        if file_fact.language not in {"javascript", "typescript"} or file_fact.role in {"test", "sample", "generated"}:
            continue
        if "/services/" in f"/{normalized}":
            continue
        source = _read(root, file_fact)
        if not _looks_like_feathers_app_mount_source(source):
            continue
        for match in FEATHERS_APP_MOUNT_RE.finditer(source):
            prefix = match.group("prefix")
            if prefix != "/":
                prefixes.append(prefix)
    return prefixes[0] if len(set(prefixes)) == 1 else None


def _looks_like_feathers_app_mount_source(source: str) -> bool:
    return (
        "app.setup(" in source
        or "@feathersjs/express" in source
        or "require('./app')" in source
        or 'require("./app")' in source
    )


def _extract_strapi_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    if "createCoreRouter" not in source and not _looks_like_strapi_custom_route_source(file_fact.path, source):
        return []

    routes: list[ApiRouteFact] = []
    for match in STRAPI_CORE_ROUTER_RE.finditer(source):
        routes.extend(_strapi_core_router_routes(root, file_fact, source, match))
    routes.extend(_strapi_custom_routes(file_fact, source))
    return _dedupe_routes(routes)


def _looks_like_strapi_custom_route_source(path: str, source: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return (
        "/routes/" in f"/{normalized}"
        and normalized.endswith((".js", ".ts"))
        and "handler" in source
        and "method" in source
        and "path" in source
    )


def _strapi_core_router_routes(
    root: Path,
    file_fact: FileFact,
    source: str,
    match: re.Match[str],
) -> list[ApiRouteFact]:
    uid = match.group("uid")
    schema = _strapi_schema_for_uid(root, uid)
    info = _strapi_content_type_info(uid, schema)
    line = _line_for_offset(source, match.start())
    if info["kind"] == "singleType":
        specs = [
            ("GET", _join_paths("/api", info["singular"]), "find", None),
            ("PUT", _join_paths("/api", info["singular"]), "update", "data"),
            ("DELETE", _join_paths("/api", info["singular"]), "delete", None),
        ]
    else:
        collection_path = _join_paths("/api", info["plural"])
        member_path = _join_paths(collection_path, "{id}")
        specs = [
            ("GET", collection_path, "find", None),
            ("POST", collection_path, "create", "data"),
            ("GET", member_path, "findOne", None),
            ("PUT", member_path, "update", "data"),
            ("DELETE", member_path, "delete", None),
        ]

    routes: list[ApiRouteFact] = []
    for method, path, action, request_body in specs:
        routes.append(
            ApiRouteFact(
                method=method,
                path=path,
                handler=f"{info['singular']}.{action}",
                framework="strapi",
                kind="strapi-core-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                parameters=_strapi_route_parameters(path, file_fact.path, line),
                request_body=request_body,
                response_type=info["singular"],
            )
        )
    return routes


def _strapi_custom_routes(file_fact: FileFact, source: str) -> list[ApiRouteFact]:
    routes: list[ApiRouteFact] = []
    seen_spans: set[tuple[int, int]] = set()
    for match in STRAPI_METHOD_RE.finditer(source):
        span = _strapi_route_object_span(source, match.start())
        if span is None or span in seen_spans:
            continue
        seen_spans.add(span)
        body = source[span[0] + 1 : span[1]]
        method_match = STRAPI_METHOD_RE.search(body)
        path_match = STRAPI_PATH_RE.search(body)
        handler_match = STRAPI_HANDLER_RE.search(body)
        if not method_match or not path_match or not handler_match:
            continue
        line = _line_for_offset(source, span[0])
        method = method_match.group("method").upper()
        route_path = _strapi_api_path(
            path_match.group("path"),
            prefix=_strapi_custom_route_prefix(file_fact.path, source, body),
        )
        routes.append(
            ApiRouteFact(
                method=method,
                path=route_path,
                handler=handler_match.group("handler"),
                framework="strapi",
                kind="strapi-custom-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                parameters=_strapi_route_parameters(route_path, file_fact.path, line),
                request_body="data" if method in {"POST", "PUT", "PATCH"} else None,
            )
        )
    return routes


def _strapi_route_object_span(source: str, offset: int) -> tuple[int, int] | None:
    open_index = source.rfind("{", 0, offset)
    while open_index >= 0:
        close_index = _find_matching_brace(source, open_index)
        if close_index is not None and close_index >= offset:
            body = source[open_index + 1 : close_index]
            if STRAPI_METHOD_RE.search(body) and STRAPI_PATH_RE.search(body) and STRAPI_HANDLER_RE.search(body):
                return open_index, close_index
        open_index = source.rfind("{", 0, open_index)
    return None


@lru_cache(maxsize=512)
def _strapi_schema_for_uid(root: Path, uid: str) -> dict[str, object]:
    api_name, content_type = _strapi_uid_parts(uid)
    candidates = [
        root / "src" / "api" / api_name / "content-types" / content_type / "schema.json",
        root / "api" / "src" / "api" / api_name / "content-types" / content_type / "schema.json",
    ]
    for candidate in candidates:
        data = _read_strapi_schema(candidate)
        if data:
            return data
    for candidate in root.rglob("schema.json"):
        parts = [part.lower() for part in candidate.parts]
        if "node_modules" in parts or ".git" in parts:
            continue
        normalized = candidate.as_posix().lower()
        if f"/content-types/{content_type.lower()}/schema.json" not in normalized:
            continue
        data = _read_strapi_schema(candidate)
        if data:
            return data
    return {}


def _read_strapi_schema(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _strapi_uid_parts(uid: str) -> tuple[str, str]:
    value = uid.split("::", 1)[-1]
    if "." in value:
        api_name, content_type = value.split(".", 1)
        return api_name, content_type
    return value, value


def _strapi_content_type_info(uid: str, schema: dict[str, object]) -> dict[str, str]:
    _, fallback_name = _strapi_uid_parts(uid)
    info = schema.get("info") if isinstance(schema.get("info"), dict) else {}
    singular = _string_or_none(info.get("singularName")) or fallback_name
    plural = _string_or_none(info.get("pluralName")) or _simple_plural(singular)
    kind = _string_or_none(schema.get("kind")) or "collectionType"
    return {
        "singular": singular,
        "plural": plural,
        "kind": kind,
    }


def _simple_plural(value: str) -> str:
    if value.endswith("y") and value[-2:-1].lower() not in {"a", "e", "i", "o", "u"}:
        return f"{value[:-1]}ies"
    if value.endswith("s"):
        return value
    return f"{value}s"


def _strapi_api_path(path: str, prefix: str = "/api") -> str:
    route = path.split("?", 1)[0].strip()
    route = re.sub(r":([A-Za-z_$][\w$]*)", r"{\1}", route)
    route = _ensure_slash(route)
    if route == prefix or route.startswith(f"{prefix}/"):
        return route
    if route == "/api" or route.startswith("/api/") or route == "/admin" or route.startswith("/admin/"):
        return route
    return _join_paths(prefix, route)


def _strapi_custom_route_prefix(file_path: str, source: str, body: str) -> str:
    normalized = file_path.replace("\\", "/").lower()
    combined = f"{source}\n{body}"
    if re.search(r"\btype\s*:\s*['\"]admin['\"]", combined):
        return "/admin"
    if "/packages/core/admin/server/" in f"/{normalized}" or "/admin/server/" in f"/{normalized}":
        return "/admin"
    return "/api"


def _strapi_route_parameters(path: str, file_path: str, line: int) -> list[RequestParamFact]:
    params: list[RequestParamFact] = []
    for name in _dedupe([*re.findall(r"\{([^}]+)\}", path), *re.findall(r":([A-Za-z_$][\w$]*)", path)]):
        params.append(
            RequestParamFact(
                name=name,
                source="path",
                type=None,
                required=True,
                evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
            )
        )
    return params


def _extract_fastify_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    if not _looks_like_fastify_source(source):
        return []

    prefix = _fastify_auto_prefix(source)
    routes: list[ApiRouteFact] = []
    for match in FASTIFY_ROUTE_CALL_RE.finditer(source):
        brace_start = source.find("{", match.start())
        brace_end = _find_matching_brace(source, brace_start)
        if brace_end is None:
            continue
        body = source[brace_start + 1 : brace_end]
        route_path = _fastify_route_path(body)
        if not route_path:
            continue
        line = _line_for_offset(source, match.start())
        handler = _fastify_route_handler(body)
        for method in _fastify_route_methods(body):
            routes.append(
                ApiRouteFact(
                    method=method,
                    path=_join_paths(prefix, route_path),
                    handler=handler,
                    framework="fastify",
                    kind="fastify-route",
                    evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                )
            )

    for match in FASTIFY_SHORTHAND_ROUTE_RE.finditer(source):
        line = _line_for_offset(source, match.start())
        routes.append(
            ApiRouteFact(
                method=_fastify_method(match.group("method")),
                path=_join_paths(prefix, match.group("path")),
                handler=match.group("handler"),
                framework="fastify",
                kind="fastify-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
            )
        )
    return routes


def _looks_like_fastify_source(source: str) -> bool:
    return (
        "fastify.route(" in source
        or re.search(r"\bfastify\.(?:get|post|put|delete|patch|options|head|all)\s*\(", source, re.IGNORECASE) is not None
        or "from 'fastify'" in source
        or 'from "fastify"' in source
        or "require('fastify')" in source
        or 'require("fastify")' in source
        or "@fastify/" in source
        or "fastify-plugin" in source
    )


def _fastify_auto_prefix(source: str) -> str:
    match = FASTIFY_AUTOPREFIX_RE.search(source)
    return match.group("prefix") if match else ""


def _fastify_route_path(body: str) -> str | None:
    match = FASTIFY_PATH_RE.search(body)
    if not match:
        return None
    return _ensure_slash(match.group("path"))


def _fastify_route_handler(body: str) -> str | None:
    match = FASTIFY_HANDLER_RE.search(body)
    return match.group("handler") if match else None


def _fastify_route_methods(body: str) -> list[str]:
    match = FASTIFY_METHOD_RE.search(body)
    if not match:
        return ["ANY"]
    if match.group("method"):
        return [_fastify_method(match.group("method"))]
    found = re.findall(r"['\"`](GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD|ALL)['\"`]", match.group("methods") or "", re.IGNORECASE)
    return [_fastify_method(item) for item in found] or ["ANY"]


def _fastify_method(value: str) -> str:
    method = value.upper()
    return "ANY" if method == "ALL" else method


def _extract_next_api_routes(root: Path, file_fact: FileFact, symbols: list[SymbolFact]) -> list[ApiRouteFact]:
    normalized = file_fact.path.replace("\\", "/")
    route_path = _next_api_path(normalized)
    if route_path is None:
        return []

    file_symbols = [symbol for symbol in symbols if symbol.path == file_fact.path]
    methods = [
        symbol
        for symbol in file_symbols
        if symbol.name.upper() in {"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"}
    ]
    if not methods:
        return [
            ApiRouteFact(
                method="ANY",
                path=route_path,
                handler=None,
                framework="next",
                kind="next-api-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=1, line_end=1),
            )
        ]
    return [
        ApiRouteFact(
            method=symbol.name.upper(),
            path=route_path,
            handler=symbol.name,
            framework="next",
            kind="next-api-route",
            evidence=symbol.evidence,
        )
        for symbol in methods
    ]


def _extract_astro_api_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    normalized = file_fact.path.replace("\\", "/")
    route_part = _astro_api_route_part(normalized)
    if route_part is None:
        return []
    source = _read(root, file_fact)
    route_path = _astro_api_path(route_part)
    routes: list[ApiRouteFact] = []
    for match in ASTRO_API_EXPORT_RE.finditer(source):
        raw_method = match.group("method").upper()
        method = "ANY" if raw_method == "ALL" else raw_method
        line = _line_for_offset(source, match.start())
        routes.append(
            ApiRouteFact(
                method=method,
                path=route_path,
                handler=raw_method,
                framework="astro",
                kind="astro-api-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
            )
        )
    if not routes:
        if not _looks_like_astro_api_source(source):
            return []
        routes.append(
            ApiRouteFact(
                method="ANY",
                path=route_path,
                handler=None,
                framework="astro",
                kind="astro-api-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=1, line_end=1),
            )
        )
    return routes


def _looks_like_astro_api_source(source: str) -> bool:
    return (
        "APIRoute" in source
        or "from 'astro'" in source
        or 'from "astro"' in source
        or re.search(r"\bexport\s+(?:const|async\s+function|function)\s+(?:GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD|ALL)\b", source) is not None
    )


def _astro_api_route_part(path: str) -> str | None:
    normalized = path.replace("\\", "/")
    marker = "/pages/api/"
    if normalized.startswith("pages/api/"):
        return normalized.removeprefix("pages/")
    if marker in normalized:
        return normalized.split(marker, 1)[1].join(("api/", ""))
    return None


def _astro_api_path(route_part: str) -> str:
    stem = route_part.rsplit(".", 1)[0]
    if stem.endswith("/index"):
        stem = stem[: -len("/index")]
    parts: list[str] = []
    for part in stem.split("/"):
        if part.startswith("[...") and part.endswith("]"):
            parts.append(f":{part[4:-1]}*")
        elif part.startswith("[") and part.endswith("]"):
            parts.append(f":{part[1:-1]}")
        else:
            parts.append(part)
    return "/" + "/".join(part for part in parts if part)


def _extract_sveltekit_backend_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    normalized = file_fact.path.replace("\\", "/")
    route_info = _sveltekit_backend_route_for_path(normalized)
    if route_info is None:
        return []
    route_path, route_kind = route_info
    source = _read(root, file_fact)
    routes: list[ApiRouteFact] = []
    if route_kind == "sveltekit-endpoint":
        for match in SVELTEKIT_SERVER_METHOD_RE.finditer(source):
            method = (match.group("fn") or match.group("const") or "").upper()
            if not method:
                continue
            line = _line_for_offset(source, match.start())
            routes.append(
                ApiRouteFact(
                    method=method,
                    path=route_path,
                    handler=method,
                    framework="sveltekit",
                    kind="sveltekit-endpoint",
                    evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                    parameters=_sveltekit_path_parameters(route_path, file_fact.path, line),
                    request_body="request" if method in {"POST", "PUT", "PATCH"} and "request" in source else None,
                    response_type="Response",
                )
            )
        return _dedupe_routes(routes)

    load_match = SVELTEKIT_LOAD_RE.search(source)
    if load_match:
        line = _line_for_offset(source, load_match.start())
        routes.append(
            ApiRouteFact(
                method="LOAD",
                path=route_path,
                handler="load",
                framework="sveltekit",
                kind=route_kind,
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                parameters=_sveltekit_path_parameters(route_path, file_fact.path, line),
                response_type="PageServerLoad" if "+page.server." in normalized else "LayoutServerLoad",
            )
        )

    for action_name, action_source, line in _sveltekit_action_entries(source, file_fact.path):
        routes.append(
            ApiRouteFact(
                method="POST",
                path=_sveltekit_action_path(route_path, action_name),
                handler=f"actions.{action_name}",
                framework="sveltekit",
                kind="sveltekit-form-action",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                parameters=_sveltekit_path_parameters(route_path, file_fact.path, line),
                request_body="formData" if ".formData" in action_source else None,
                response_type=_sveltekit_action_response_type(action_source),
            )
        )
    return _dedupe_routes(routes)


def _sveltekit_backend_route_for_path(path: str) -> tuple[str, str] | None:
    normalized = path.replace("\\", "/")
    suffix_kind = (
        ("+server.js", "sveltekit-endpoint"),
        ("+server.ts", "sveltekit-endpoint"),
        ("+page.server.js", "sveltekit-page-server-load"),
        ("+page.server.ts", "sveltekit-page-server-load"),
        ("+layout.server.js", "sveltekit-layout-server-load"),
        ("+layout.server.ts", "sveltekit-layout-server-load"),
    )
    matched_suffix = next(((suffix, kind) for suffix, kind in suffix_kind if normalized.endswith(suffix)), None)
    if matched_suffix is None:
        return None
    suffix, kind = matched_suffix
    route_part = _path_after_marker(normalized, "/src/routes/")
    if route_part is None and normalized.startswith("src/routes/"):
        route_part = normalized.removeprefix("src/routes/")
    if route_part is None:
        route_part = _path_after_marker(normalized, "/routes/")
    if route_part is None:
        return None
    route = route_part.removesuffix(suffix).rstrip("/")
    return _page_route(_clean_sveltekit_route_part(route)), kind


def _clean_sveltekit_route_part(route: str) -> str:
    parts: list[str] = []
    for part in route.split("/"):
        if part in {"", "index"}:
            parts.append(part)
        elif part.startswith("[[...") and part.endswith("]]"):
            parts.append(f":{part[5:-2]}*")
        elif part.startswith("[...") and part.endswith("]"):
            parts.append(f":{part[4:-1]}*")
        elif part.startswith("[[") and part.endswith("]]"):
            parts.append(f":{part[2:-2]}")
        elif part.startswith("[") and part.endswith("]"):
            parts.append(f":{part[1:-1]}")
        else:
            parts.append(part)
    return "/".join(parts)


def _page_route(route: str) -> str:
    parts = [part for part in route.split("/") if not (part.startswith("(") and part.endswith(")"))]
    grouped = "/".join(parts)
    cleaned = "" if grouped == "index" else grouped.replace("/index", "")
    cleaned = cleaned.replace("[", ":").replace("]", "")
    return "/" + cleaned.strip("/") if cleaned.strip("/") else "/"


def _sveltekit_action_entries(source: str, file_path: str) -> list[tuple[str, str, int]]:
    entries: list[tuple[str, str, int]] = []
    for match in SVELTEKIT_ACTIONS_RE.finditer(source):
        open_index = source.find("{", match.start())
        close_index = _find_matching_brace(source, open_index)
        if close_index is None:
            continue
        body = source[open_index + 1 : close_index]
        body_start = open_index + 1
        for part in _split_top_level_commas(body):
            name_match = re.match(r"\s*(?P<name>[A-Za-z_$][\w$]*)\s*:", part)
            if not name_match:
                continue
            part_offset = body.find(part)
            absolute = body_start + part_offset + name_match.start("name") if part_offset >= 0 else match.start()
            entries.append((name_match.group("name"), part, _line_for_offset(source, absolute)))
    return entries


def _sveltekit_action_path(route_path: str, action_name: str) -> str:
    if action_name == "default":
        return route_path
    return f"{route_path}?/{action_name}" if route_path != "/" else f"/?/{action_name}"


def _sveltekit_action_response_type(source: str) -> str:
    hints = []
    if "redirect(" in source:
        hints.append("redirect")
    if "fail(" in source:
        hints.append("fail")
    if "return" in source:
        hints.append("return")
    return "ActionResult" + (f":{','.join(hints)}" if hints else "")


def _sveltekit_path_parameters(route_path: str, file_path: str, line: int) -> list[RequestParamFact]:
    return [
        RequestParamFact(
            name=name,
            source="path",
            type=None,
            required=True,
            evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
        )
        for name in re.findall(r":([A-Za-z_][\w-]*)\*?", route_path)
    ]


def _extract_nitro_server_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    normalized = file_fact.path.replace("\\", "/")
    route_info = _nitro_route_part(normalized)
    if route_info is None:
        return []

    route_part, prefix = route_info
    method, route_path = _nitro_method_and_path(route_part, prefix)
    source = _read(root, file_fact)
    handler_match = NITRO_ROUTE_HANDLER_RE.search(source)
    line = _line_for_offset(source, handler_match.start()) if handler_match else 1
    handler = "defineEventHandler" if "defineEventHandler" in source else "eventHandler" if "eventHandler" in source else "default"
    return [
        ApiRouteFact(
            method=method,
            path=route_path,
            handler=handler,
            framework="nuxt",
            kind="nuxt-server-route",
            evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
        )
    ]


def _nitro_route_part(path: str) -> tuple[str, str] | None:
    normalized = path.replace("\\", "/")
    for marker, prefix in (
        ("server/api/", "/api"),
        ("/server/api/", "/api"),
        ("server/routes/", ""),
        ("/server/routes/", ""),
    ):
        if normalized.startswith(marker):
            return normalized.removeprefix(marker), prefix
        if marker.startswith("/") and marker in normalized:
            return normalized.split(marker, 1)[1], prefix
    return None


def _nitro_method_and_path(route_part: str, prefix: str) -> tuple[str, str]:
    stem = route_part.rsplit(".", 1)[0]
    parts = stem.split("/")
    method = "ANY"
    if parts:
        name_parts = parts[-1].split(".")
        if len(name_parts) > 1 and name_parts[-1].lower() in NITRO_METHODS:
            method = NITRO_METHODS[name_parts[-1].lower()]
            parts[-1] = ".".join(name_parts[:-1])
    if parts and parts[-1] == "index":
        parts = parts[:-1]
    route_parts = [_nitro_route_segment(part) for part in parts if part]
    route_path = "/" + "/".join(route_parts)
    if prefix:
        route_path = _join_paths(prefix, route_path)
    return method, route_path or "/"


def _nitro_route_segment(part: str) -> str:
    if part.startswith("[[...") and part.endswith("]]"):
        return f":{part[5:-2]}*"
    if part.startswith("[...") and part.endswith("]"):
        return f":{part[4:-1]}*"
    if part.startswith("[[") and part.endswith("]]"):
        return f":{part[2:-2]}"
    if part.startswith("[") and part.endswith("]"):
        return f":{part[1:-1]}"
    return part


def _extract_react_router_data_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    normalized = file_fact.path.replace("\\", "/")
    route_path = _react_router_data_route_path(normalized)
    if route_path is None:
        return []
    source = _read(root, file_fact)
    framework = "remix" if _looks_like_remix_route_module(source) else "react-router"
    kind = "remix-data-route" if framework == "remix" else "react-router-data-route"
    routes: list[ApiRouteFact] = []
    for match in REACT_ROUTER_DATA_EXPORT_RE.finditer(source):
        name = match.group("name")
        method = "GET" if name == "loader" else "POST"
        line = _line_for_offset(source, match.start())
        handler_source = _react_router_handler_source(source, match.start())
        routes.append(
            ApiRouteFact(
                method=method,
                path=route_path,
                handler=name,
                framework=framework,
                kind=kind,
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                parameters=_react_router_route_parameters(route_path, file_fact.path, line),
                request_body="formData" if name == "action" and "request.formData" in handler_source else None,
                response_type=_react_router_response_type(handler_source),
            )
        )
    return routes


def _looks_like_remix_route_module(source: str) -> bool:
    return "@remix-run/" in source or "remix" in source.lower() and ("loader" in source or "action" in source)


def _react_router_handler_source(source: str, offset: int) -> str:
    next_match = REACT_ROUTER_DATA_EXPORT_RE.search(source, offset + 1)
    end = next_match.start() if next_match else len(source)
    return source[offset:end]


def _react_router_route_parameters(path: str, file_path: str, line: int) -> list[RequestParamFact]:
    return [
        RequestParamFact(
            name=name.rstrip("*"),
            source="path",
            type=None,
            required=True,
            evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
        )
        for name in re.findall(r":([A-Za-z_$][\w$]*\*?)", path)
    ]


def _react_router_response_type(handler_source: str) -> str | None:
    has_json = re.search(r"\bjson\s*\(", handler_source) is not None
    has_redirect = re.search(r"\bredirect\s*\(", handler_source) is not None
    if has_json and has_redirect:
        return "json|redirect"
    if has_json:
        return "json"
    if has_redirect:
        return "redirect"
    if re.search(r"\bnew\s+Response\s*\(", handler_source):
        return "Response"
    return None


def _react_router_data_route_path(path: str) -> str | None:
    normalized = path.replace("\\", "/")
    if not normalized.endswith((".tsx", ".ts", ".jsx", ".js")):
        return None
    route_part = _path_after_marker(normalized, "/app/routes/")
    if route_part is None and normalized.startswith("app/routes/"):
        route_part = normalized.removeprefix("app/routes/")
    if route_part is None:
        return None
    lowered = route_part.lower()
    if re.search(r"\.(?:server|client)\.(?:tsx|ts|jsx|js)$", lowered):
        return None
    if "/__tests__/" in f"/{lowered}/" or lowered.endswith((".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx")):
        return None
    stem = re.sub(r"\.(?:tsx|ts|jsx|js)$", "", route_part)
    parts: list[str] = []
    for raw_part in stem.split("/"):
        parts.extend(_react_router_route_part_tokens(raw_part))
    return "/" + "/".join(part for part in parts if part) if parts else "/"


def _path_after_marker(path: str, marker: str) -> str | None:
    if path.startswith(marker.lstrip("/")):
        return path[len(marker.lstrip("/")) :]
    if marker in path:
        return path.split(marker, 1)[1]
    return None


def _react_router_route_part_tokens(part: str) -> list[str]:
    if not part or part == "index":
        return []
    tokens = part.replace("[.]", "\0DOT\0").split(".")
    route_parts: list[str] = []
    for token in tokens:
        token = token.replace("\0DOT\0", ".")
        if not token or token in {"index", "route"}:
            continue
        if token.startswith("_"):
            continue
        if token.endswith("_"):
            token = token[:-1]
        if token == "$":
            route_parts.append(":splat*")
        elif token.startswith("$"):
            route_parts.append(f":{token[1:]}")
        else:
            route_parts.append(token)
    return route_parts


def _extract_graphql_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    if "graphqlHTTP" not in source and "express-graphql" not in source:
        return []
    routes: list[ApiRouteFact] = []
    for match in EXPRESS_GRAPHQL_RE.finditer(source):
        raw_path = match.group("path")
        path = _quoted_value(raw_path) or _graphql_endpoint_from_config(root, file_fact) or "unknown"
        line = _line_for_offset(source, match.start())
        routes.append(
            ApiRouteFact(
                method="ANY",
                path=path,
                handler="graphqlHTTP",
                framework="graphql",
                kind="graphql-http-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
            )
        )
    return routes


def _extract_python_backend_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    routes: list[ApiRouteFact] = []
    constants = _python_string_constants(source)
    router_prefixes = _fastapi_router_prefixes(source, constants)
    if _looks_like_fastapi_source(source):
        for match in FASTAPI_ROUTE_RE.finditer(source):
            line = _line_for_offset(source, match.start())
            receiver = match.group("receiver")
            path = _join_paths(router_prefixes.get(receiver, ""), match.group("path"))
            decorator_args = _python_call_args_at(source, source.find("(", match.start()))
            method_info = _fastapi_method_info(
                source,
                match.end(),
                file_fact.path,
                line,
                match.group("method").upper(),
                path,
                decorator_args,
            )
            routes.append(
                ApiRouteFact(
                    method=match.group("method").upper(),
                    path=path,
                    handler=method_info["name"] if isinstance(method_info["name"], str) else None,
                    framework="fastapi",
                    kind="fastapi-route",
                    evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                    class_prefix=receiver,
                    parameters=method_info["parameters"] if isinstance(method_info["parameters"], list) else [],
                    request_body=method_info["request_body"] if isinstance(method_info["request_body"], str) else None,
                    response_type=method_info["response_type"] if isinstance(method_info["response_type"], str) else None,
                )
            )
    for match in FLASK_ROUTE_RE.finditer(source):
        line = _line_for_offset(source, match.start())
        handler = _function_after(source, match.end())
        methods = _flask_methods(match.group("args"))
        for method in methods:
            routes.append(
                ApiRouteFact(
                    method=method,
                    path=match.group("path"),
                    handler=handler,
                    framework="flask",
                    kind="flask-route",
                    evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                )
            )
    routes.extend(_extract_flask_appbuilder_exposes(source, file_fact))
    return routes


def _extract_flask_appbuilder_exposes(source: str, file_fact: FileFact) -> list[ApiRouteFact]:
    if "@expose" not in source:
        return []
    if not _looks_like_flask_appbuilder_source(source):
        return []
    routes: list[ApiRouteFact] = []
    for class_info in _python_class_blocks(source):
        class_name, bases, body, body_offset = class_info
        if not _looks_like_flask_appbuilder_class(bases, body):
            continue
        class_prefix = _flask_appbuilder_class_prefix(class_name, bases, body)
        if class_prefix is None:
            continue
        for match in FLASK_APPBUILDER_EXPOSE_RE.finditer(body):
            args = _python_call_args_at(body, match.end() - 1)
            path_fragment = _first_python_string_arg(args)
            if path_fragment is None:
                continue
            line = _line_for_offset(source, body_offset + match.start())
            handler = _function_after(body, match.end())
            path = _join_paths(class_prefix, path_fragment)
            for method in _flask_methods(args):
                routes.append(
                    ApiRouteFact(
                        method=method,
                        path=path,
                        handler=handler,
                        framework="flask-appbuilder",
                        kind="flask-appbuilder-expose",
                        evidence=Evidence(
                            file=file_fact.path,
                            kind="backend-route",
                            line_start=line,
                            line_end=line,
                        ),
                        class_prefix=class_name,
                        parameters=_flask_style_path_parameters(path, file_fact.path, line),
                    )
                )
    return routes


def _looks_like_flask_appbuilder_source(source: str) -> bool:
    return (
        "flask_appbuilder" in source
        or "BaseSupersetApi" in source
        or "BaseSupersetView" in source
        or "ModelRestApi" in source
        or "BaseApi" in source
        or "IndexView" in source
    )


def _python_class_blocks(source: str) -> list[tuple[str, str, str, int]]:
    matches = list(PY_CLASS_RE.finditer(source))
    blocks: list[tuple[str, str, str, int]] = []
    for index, match in enumerate(matches):
        indent = len(match.group("indent").replace("\t", "    "))
        end = len(source)
        for next_match in matches[index + 1 :]:
            next_indent = len(next_match.group("indent").replace("\t", "    "))
            if next_indent <= indent:
                end = next_match.start()
                break
        body_start = match.end()
        blocks.append((match.group("name"), match.group("bases") or "", source[body_start:end], body_start))
    return blocks


def _looks_like_flask_appbuilder_class(bases: str, body: str) -> bool:
    base_names = _python_base_names(bases)
    return (
        any(base in FLASK_APPBUILDER_API_BASES | FLASK_APPBUILDER_VIEW_BASES for base in base_names)
        or any(base.endswith(("RestApi", "Api", "View")) for base in base_names)
        or "resource_name" in body
        or "route_base" in body
    )


def _flask_appbuilder_class_prefix(class_name: str, bases: str, body: str) -> str | None:
    attrs = {match.group("name"): match.group("value") for match in PY_CLASS_STRING_ATTR_RE.finditer(body)}
    if route_base := attrs.get("route_base"):
        return route_base
    if resource_name := attrs.get("resource_name"):
        return _join_paths("/api/v1", resource_name)
    base_names = _python_base_names(bases)
    if "IndexView" in base_names:
        return ""
    for base in base_names:
        if base not in FLASK_APPBUILDER_API_BASES and base.endswith(("RestApi", "Api")):
            inferred = _camel_to_snake(base).removesuffix("_rest_api").removesuffix("_api")
            return _join_paths("/api/v1", inferred)
    if any(base in FLASK_APPBUILDER_API_BASES for base in base_names):
        inferred = _camel_to_snake(class_name).removesuffix("_rest_api").removesuffix("_api")
        return _join_paths("/api/v1", inferred)
    if any(base in FLASK_APPBUILDER_VIEW_BASES or base.endswith("View") for base in base_names):
        return f"/{class_name.lower()}"
    return None


def _python_base_names(bases: str) -> list[str]:
    return [part.rsplit(".", 1)[-1] for part in re.findall(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", bases)]


def _first_python_string_arg(args: str) -> str | None:
    match = re.match(r"\s*(?:[rRuUbBfF]+)?['\"](?P<value>[^'\"]+)['\"]", args, flags=re.DOTALL)
    return match.group("value") if match else None


def _flask_style_path_parameters(path: str, file_path: str, line: int) -> list[RequestParamFact]:
    params: list[RequestParamFact] = []
    for match in re.finditer(r"<(?:(?P<type>[^:<>]+):)?(?P<name>[A-Za-z_]\w*)>", path):
        params.append(
            RequestParamFact(
                name=match.group("name"),
                source="path",
                type=match.group("type"),
                required=True,
                evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
            )
        )
    return params


def _fastapi_method_info(
    source: str,
    offset: int,
    file_path: str,
    line: int,
    method: str,
    path: str,
    decorator_args: str,
) -> dict[str, object]:
    function = _python_function_after(source, offset)
    if function is None:
        return {"name": None, "parameters": [], "request_body": None, "response_type": _fastapi_response_model(decorator_args)}
    name, params_source, return_type = function
    parameters, request_body = _fastapi_parameters(params_source, file_path, line, method, path)
    return {
        "name": name,
        "parameters": parameters,
        "request_body": request_body,
        "response_type": _fastapi_response_model(decorator_args) or return_type,
    }


def _python_function_after(source: str, offset: int) -> tuple[str, str, str | None] | None:
    match = re.search(r"\n\s*(?:async\s+)?def\s+(?P<name>[A-Za-z_]\w*)\s*\(", source[offset : offset + 1600])
    if not match:
        return None
    absolute_start = offset + match.start()
    paren_start = source.find("(", absolute_start)
    paren_end = _find_matching_paren(source, paren_start)
    if paren_end is None:
        return None
    return_type = _python_return_type_after(source, paren_end)
    return match.group("name"), source[paren_start + 1 : paren_end], return_type


def _python_return_type_after(source: str, paren_end: int) -> str | None:
    tail = source[paren_end + 1 : paren_end + 300]
    match = re.match(r"\s*->\s*(?P<type>[^:\n]+)\s*:", tail)
    return " ".join(match.group("type").split()) if match else None


def _python_call_args_at(source: str, open_paren: int) -> str:
    if open_paren < 0:
        return ""
    close = _find_matching_paren(source, open_paren)
    return source[open_paren + 1 : close] if close is not None else ""


def _fastapi_parameters(
    params_source: str,
    file_path: str,
    line: int,
    method: str,
    path: str,
) -> tuple[list[RequestParamFact], str | None]:
    path_params = set(_path_param_names(path, "{", "}"))
    params: list[RequestParamFact] = []
    request_body: str | None = None
    for raw_param in _split_args(params_source):
        cleaned = raw_param.strip()
        if not cleaned or cleaned in {"*", "/", "self", "request"} or cleaned.startswith("**"):
            continue
        name, annotation, default = _fastapi_param_shape(cleaned)
        if not name or name in {"self", "request"}:
            continue
        if _fastapi_is_dependency_param(name, annotation, default):
            continue
        if name in path_params:
            source_kind = "path"
        elif _fastapi_is_body_annotation(annotation, default):
            source_kind = "body"
            request_body = annotation or name
        else:
            source_kind = "query"
        params.append(
            RequestParamFact(
                name=name,
                source=source_kind,
                type=annotation or None,
                required=True if source_kind == "path" else _fastapi_required(default, annotation, source_kind),
                evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
            )
        )
    return _dedupe_request_params(params), request_body


def _fastapi_param_shape(source: str) -> tuple[str | None, str, str | None]:
    left, default = _split_default(source)
    if ":" not in left:
        name = left.strip()
        return (name if re.fullmatch(r"[A-Za-z_]\w*", name) else None), "", default
    name, annotation = left.split(":", 1)
    name = name.strip().lstrip("*").strip()
    return (name if re.fullmatch(r"[A-Za-z_]\w*", name) else None), " ".join(annotation.strip().split()), default


def _split_default(source: str) -> tuple[str, str | None]:
    depth = 0
    quote: str | None = None
    escaped = False
    for index, char in enumerate(source):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            continue
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth = max(0, depth - 1)
        elif char == "=" and depth == 0:
            return source[:index].strip(), source[index + 1 :].strip()
    return source.strip(), None


def _fastapi_is_dependency_param(name: str, annotation: str, default: str | None) -> bool:
    dependency_markers = ("Depends", "Security")
    if default and any(marker in default for marker in dependency_markers):
        return True
    if annotation and any(marker in annotation for marker in dependency_markers):
        return True
    dependency_names = {"session", "current_user", "request", "background_tasks", "security_scopes"}
    dependency_types = {"SessionDep", "CurrentUser", "Request", "BackgroundTasks", "SecurityScopes"}
    return name in dependency_names or annotation in dependency_types


def _fastapi_is_body_annotation(annotation: str, default: str | None) -> bool:
    if default and any(token in default for token in ("Body(", "File(", "Form(", "UploadFile(")):
        return True
    if not annotation:
        return False
    if any(token in annotation for token in ("Body(", "File(", "Form(", "UploadFile(")):
        return True
    if any(token in annotation for token in ("Query(", "Path(")):
        return False
    clean = annotation.replace("None", "").replace("Optional", "").replace("[", " ").replace("]", " ")
    tokens = [token.strip("\"'") for token in re.split(r"[|,\s]+", clean) if token.strip("\"'")]
    if not tokens:
        return False
    if all(token in PRIMITIVE_TYPES or token.startswith("Literal") for token in tokens):
        return False
    return any(token[:1].isupper() and token not in PRIMITIVE_TYPES for token in tokens)


def _fastapi_required(default: str | None, annotation: str, source_kind: str) -> bool | None:
    if default is not None or "None" in annotation or "| None" in annotation:
        return False
    return True if source_kind == "body" else None


def _fastapi_response_model(args: str) -> str | None:
    match = re.search(r"\bresponse_model\s*=\s*(?P<model>[A-Za-z_][\w.\[\]]*)", args)
    return match.group("model") if match else None


def _path_param_names(path: str, open_char: str, close_char: str) -> list[str]:
    pattern = re.escape(open_char) + r"([^" + re.escape(close_char) + r":]+)(?::[^" + re.escape(close_char) + r"]*)?" + re.escape(close_char)
    return [name.rstrip("?") for name in re.findall(pattern, path)]


def _looks_like_fastapi_source(source: str) -> bool:
    lower = source.lower()
    return "fastapi" in lower or "apirouter" in source or "FastAPI" in source


def _extract_django_ninja_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    if not _looks_like_django_ninja_source(source):
        return []
    routes: list[ApiRouteFact] = []
    constants = _python_string_constants(source)
    router_prefixes = _django_ninja_router_prefixes(source, constants)
    for match in FASTAPI_ROUTE_RE.finditer(source):
        receiver = match.group("receiver")
        if receiver not in router_prefixes and receiver != "api":
            continue
        line = _line_for_offset(source, match.start())
        handler = _function_after(source, match.end())
        path = _join_paths(router_prefixes.get(receiver, ""), match.group("path"))
        routes.append(
            ApiRouteFact(
                method=match.group("method").upper(),
                path=path,
                handler=handler,
                framework="django-ninja",
                kind="django-ninja-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                class_prefix=receiver,
                response_type=_django_ninja_response_type(source[match.start() : match.end() + 300]),
            )
        )
    return routes


def _looks_like_django_ninja_source(source: str) -> bool:
    return (
        "from ninja import" in source
        or "import ninja" in source
        or "NinjaAPI" in source
        or re.search(r"\bRouter\s*\(", source) is not None and "rest_framework.routers" not in source
    )


def _django_ninja_router_prefixes(source: str, constants: dict[str, str]) -> dict[str, str]:
    prefixes: dict[str, str] = {}
    for match in re.finditer(r"(?m)^\s*(?P<name>[A-Za-z_]\w*)\s*=\s*Router\s*\((?P<args>[^)]*)\)", source, re.DOTALL):
        prefixes[match.group("name")] = _fastapi_prefix_from_args(match.group("args"), constants) or ""
    for match in re.finditer(r"(?m)^\s*(?P<name>[A-Za-z_]\w*)\s*=\s*NinjaAPI\s*\(", source):
        prefixes.setdefault(match.group("name"), "")
    return prefixes


def _django_ninja_response_type(decorator_source: str) -> str | None:
    match = re.search(r"\bresponse\s*=\s*(?P<response>[A-Za-z_][\w.\[\]]*)", decorator_source)
    return match.group("response") if match else None


def _apply_fastapi_include_prefixes(
    root: Path,
    files: list[FileFact],
    routes: list[ApiRouteFact],
) -> list[ApiRouteFact]:
    prefixes = _fastapi_app_include_prefixes(root, files)
    if len(prefixes) != 1:
        return routes
    prefix = prefixes[0]
    if not prefix or prefix == "/":
        return routes

    mounted: list[ApiRouteFact] = []
    for route in routes:
        if route.framework != "fastapi" or route.class_prefix in {None, "app"}:
            mounted.append(route)
            continue
        if _path_has_prefix(route.path, prefix):
            mounted.append(route)
            continue
        mounted.append(replace(route, path=_join_paths(prefix, route.path)))
    return _dedupe_routes(mounted)


def _fastapi_app_include_prefixes(root: Path, files: list[FileFact]) -> list[str]:
    project_constants = _python_project_string_constants(root, files)
    prefixes: list[str] = []
    for file_fact in files:
        if file_fact.language != "python" or file_fact.role in {"test", "sample", "generated"}:
            continue
        source = _read(root, file_fact)
        if "include_router" not in source:
            continue
        constants = {**project_constants, **_python_string_constants(source)}
        for match in FASTAPI_INCLUDE_ROUTER_RE.finditer(source):
            if match.group("receiver") != "app":
                continue
            prefix = _fastapi_prefix_from_args(match.group("args"), constants)
            if prefix:
                prefixes.append(prefix)
    return _dedupe(prefixes)


def _fastapi_router_prefixes(source: str, constants: dict[str, str]) -> dict[str, str]:
    prefixes: dict[str, str] = {}
    if "APIRouter" not in source:
        return prefixes
    for match in FASTAPI_API_ROUTER_RE.finditer(source):
        prefix = _fastapi_prefix_from_args(match.group("args"), constants)
        if prefix:
            prefixes[match.group("name")] = prefix
    return prefixes


def _fastapi_prefix_from_args(args: str, constants: dict[str, str]) -> str | None:
    match = FASTAPI_PREFIX_ARG_RE.search(args)
    if not match:
        return None
    value = _python_string_expression_value(match.group("value"), constants)
    return _ensure_slash(value) if value else None


def _python_project_string_constants(root: Path, files: list[FileFact]) -> dict[str, str]:
    constants: dict[str, str] = {}
    for file_fact in files:
        if file_fact.language != "python" or file_fact.role in {"test", "sample", "generated"}:
            continue
        source = _read(root, file_fact)
        for name, value in _python_string_constants(source).items():
            constants.setdefault(name, value)
    return constants


def _python_string_expression_value(value: str, constants: dict[str, str]) -> str | None:
    cleaned = value.strip()
    literal = _python_string_literal(cleaned)
    if literal is not None:
        return _replace_python_format_parts(literal, constants)
    if cleaned in constants:
        return constants[cleaned]
    if "." in cleaned:
        tail = cleaned.rsplit(".", 1)[-1]
        if tail in constants:
            return constants[tail]
    return None


def _path_has_prefix(path: str, prefix: str) -> bool:
    normalized_path = _ensure_slash(path).rstrip("/") or "/"
    normalized_prefix = _ensure_slash(prefix).rstrip("/") or "/"
    return normalized_path == normalized_prefix or normalized_path.startswith(f"{normalized_prefix}/")


def _apply_django_ninja_mount_prefixes(
    root: Path,
    files: list[FileFact],
    routes: list[ApiRouteFact],
) -> list[ApiRouteFact]:
    if not any(route.framework == "django-ninja" for route in routes):
        return routes
    api_roots = _django_ninja_api_root_prefixes(root, files) or [("", None, None)]
    router_mounts = _django_ninja_router_mounts(root, files)
    if not router_mounts:
        return routes

    result: list[ApiRouteFact] = []
    for route in routes:
        if route.framework != "django-ninja":
            result.append(route)
            continue
        matching_mounts = [
            mount
            for mount in router_mounts
            if _django_ninja_target_matches_path(mount[2], route.evidence.file)
        ]
        if not matching_mounts:
            result.append(route)
            continue
        for mount_prefix, mount_file, target_tail, mount_line, target_name in matching_mounts:
            for api_root, root_file, root_line in api_roots:
                full_prefix = _join_paths(api_root, mount_prefix)
                child_line = route.evidence.line_start or 1
                evidence_file = root_file or mount_file
                evidence_line = root_line or mount_line
                note = (
                    f"ninja add_router {target_name}; child={route.evidence.file}:{child_line}; "
                    f"child_path={route.path}"
                )
                result.append(
                    replace(
                        route,
                        path=_join_paths(full_prefix, route.path),
                        kind="django-ninja-mounted-route",
                        evidence=Evidence(
                            file=evidence_file,
                            kind="backend-route",
                            line_start=evidence_line,
                            line_end=evidence_line,
                            note=note,
                        ),
                        class_prefix=full_prefix if full_prefix != "/" else None,
                    )
                )
    return _dedupe_routes(result)


def _django_ninja_api_root_prefixes(root: Path, files: list[FileFact]) -> list[tuple[str, str | None, int | None]]:
    prefixes: list[tuple[str, str | None, int | None]] = []
    for file_fact in files:
        normalized = file_fact.path.replace("\\", "/").lower()
        if file_fact.language != "python" or not normalized.endswith("urls.py"):
            continue
        source = _read(root, file_fact)
        constants = _python_string_constants(source)
        for match in NINJA_API_ROOT_RE.finditer(source):
            prefix = _django_path_from_arg(f"'{match.group('prefix')}'", constants)
            if prefix is None:
                continue
            line = _line_for_offset(source, match.start())
            prefixes.append((_ensure_slash(prefix) if prefix else "/", file_fact.path, line))
    return prefixes


def _django_ninja_router_mounts(root: Path, files: list[FileFact]) -> list[tuple[str, str, str, int, str]]:
    mounts: list[tuple[str, str, str, int, str]] = []
    for file_fact in files:
        if file_fact.language != "python" or file_fact.role in {"test", "sample", "generated"}:
            continue
        source = _read(root, file_fact)
        if "add_router" not in source:
            continue
        for match in NINJA_ADD_ROUTER_RE.finditer(source):
            target = match.group("target").strip().rstrip(",")
            target_tail = _django_ninja_target_tail(target)
            if not target_tail:
                continue
            line = _line_for_offset(source, match.start())
            mounts.append((_ensure_slash(match.group("prefix")), file_fact.path, target_tail, line, target))
    return mounts


def _django_ninja_target_tail(target: str) -> str | None:
    literal = _python_string_literal(target.strip())
    if not literal:
        return None
    module = literal.removesuffix(".router")
    parts = [
        part.strip()
        for part in module.split(".")
        if part.strip() and "{{" not in part and "}}" not in part
    ]
    if not parts:
        return None
    return "/".join(parts[-3:]) + ".py"


def _django_ninja_target_matches_path(target_tail: str, route_path: str) -> bool:
    normalized = route_path.replace("\\", "/").lower()
    return normalized.endswith(target_tail.lower())


def _extract_graphql_schema_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    schema_sources = [source] if file_fact.language == "graphql" else [match.group("body") for match in GRAPHQL_TEMPLATE_RE.finditer(source)]
    if file_fact.language in {"javascript", "typescript"} and not schema_sources and _looks_like_graphql_schema_source(file_fact.path, source):
        schema_sources = [source]
    if not schema_sources:
        return []
    routes: list[ApiRouteFact] = []
    for schema_source in schema_sources:
        routes.extend(_graphql_routes_from_schema(file_fact, source, schema_source))
    return routes


def _graphql_routes_from_schema(file_fact: FileFact, full_source: str, schema_source: str) -> list[ApiRouteFact]:
    routes: list[ApiRouteFact] = []
    root_types = _graphql_root_types(schema_source)
    schema_offset = full_source.find(schema_source)
    if schema_offset < 0:
        schema_offset = 0
    for type_name, body, body_start_offset in _graphql_type_blocks(schema_source):
        kind = root_types.get(type_name) or _graphql_root_kind_from_type(type_name)
        if not kind:
            continue
        body_start_line = _line_for_offset(full_source, schema_offset + body_start_offset)
        for name, args, return_type, line_delta in _graphql_field_entries(body):
            if name.startswith("__"):
                continue
            line = body_start_line + line_delta - 1
            routes.append(
                ApiRouteFact(
                    method=kind.upper(),
                    path=f"/graphql#{kind}.{name}",
                    handler=name,
                    framework="graphql",
                    kind="graphql-schema-field",
                    evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                    class_prefix=type_name,
                    parameters=_graphql_request_params(args, file_fact.path, line),
                    response_type=" ".join(return_type.split()),
                )
            )
    return routes


def _graphql_type_blocks(schema_source: str) -> list[tuple[str, str, int]]:
    blocks: list[tuple[str, str, int]] = []
    for match in GRAPHQL_TYPE_RE.finditer(schema_source):
        open_index = _find_graphql_type_open_brace(schema_source, match.end())
        if open_index is None:
            continue
        close_index = _find_matching_graphql_brace(schema_source, open_index)
        if close_index is None:
            continue
        blocks.append((match.group("type"), schema_source[open_index + 1 : close_index], open_index + 1))
    return blocks


def _find_graphql_type_open_brace(source: str, start: int) -> int | None:
    index = start
    in_string = False
    in_description = False
    escape = False
    while index < len(source):
        if in_description:
            if source.startswith('"""', index):
                in_description = False
                index += 3
                continue
            index += 1
            continue
        if in_string:
            if escape:
                escape = False
            elif source[index] == "\\":
                escape = True
            elif source[index] == '"':
                in_string = False
            index += 1
            continue
        if source.startswith('"""', index):
            in_description = True
            index += 3
            continue
        char = source[index]
        if char == '"':
            in_string = True
        elif char == "{":
            return index
        elif char == "\n" and re.match(r"\s*(?:extend\s+)?type\s+[A-Za-z_]\w*\b", source[index + 1 : index + 120]):
            return None
        index += 1
    return None


def _find_matching_graphql_brace(source: str, open_index: int) -> int | None:
    depth = 0
    index = open_index
    in_string = False
    in_description = False
    escape = False
    while index < len(source):
        if in_description:
            if source.startswith('"""', index):
                in_description = False
                index += 3
                continue
            index += 1
            continue
        if in_string:
            if escape:
                escape = False
            elif source[index] == "\\":
                escape = True
            elif source[index] == '"':
                in_string = False
            index += 1
            continue
        if source.startswith('"""', index):
            in_description = True
            index += 3
            continue
        char = source[index]
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def _looks_like_graphql_schema_source(path: str, source: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    if not normalized.endswith((".js", ".jsx", ".ts", ".tsx")):
        return False
    if "type " not in source or "{" not in source:
        return False
    return (
        "graphql" in source.lower()
        or "schema/" in normalized
        or ".schema." in normalized
        or ".type." in normalized
        or "typeDefs" in source
        or "makeExecutableSchema" in source
        or "RootQuery" in source
        or "RootMutation" in source
    )


def _graphql_root_types(schema_source: str) -> dict[str, str]:
    roots = {
        "Query": "Query",
        "Mutation": "Mutation",
        "Subscription": "Subscription",
    }
    for block in GRAPHQL_SCHEMA_BLOCK_RE.finditer(schema_source):
        for match in GRAPHQL_SCHEMA_ROOT_RE.finditer(block.group("body")):
            roots[match.group("type")] = match.group("kind").capitalize()
    return roots


def _graphql_root_kind_from_type(type_name: str) -> str | None:
    normalized = type_name.lower()
    for suffix, kind in [
        ("query", "Query"),
        ("mutation", "Mutation"),
        ("subscription", "Subscription"),
    ]:
        if normalized.endswith(suffix):
            return kind
    return None


def _graphql_field_entries(body: str) -> list[tuple[str, str, str, int]]:
    entries: list[tuple[str, str, str, int]] = []
    buffer = ""
    depth = 0
    start_line = 1
    for line_number, line in _graphql_schema_lines_without_descriptions(body):
        stripped = line.split("#", 1)[0].strip()
        if not stripped or stripped.startswith(("@", "...")):
            continue
        if not buffer and not re.match(r"^[A-Za-z_]\w*\b", stripped):
            continue
        if not buffer:
            start_line = line_number
        buffer = f"{buffer} {stripped}".strip()
        depth += stripped.count("(") - stripped.count(")")
        if depth > 0:
            continue
        match = GRAPHQL_FIELD_RE.match(buffer)
        if match:
            entries.append((match.group("name"), match.group("args") or "", match.group("return"), start_line))
        buffer = ""
        depth = 0
    return entries


def _graphql_schema_lines_without_descriptions(body: str) -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = []
    in_block_description = False
    for line_number, line in enumerate(body.splitlines(), start=1):
        stripped = line.strip()
        if in_block_description:
            if '"""' in stripped:
                in_block_description = False
            continue
        if stripped.startswith('"""'):
            if stripped.count('"""') % 2 == 1:
                in_block_description = True
            continue
        if re.fullmatch(r'"[^"]*"', stripped):
            continue
        lines.append((line_number, line))
    return lines


def _graphql_request_params(args: str, file_path: str, line: int) -> list[RequestParamFact]:
    params: list[RequestParamFact] = []
    for match in re.finditer(r"\b(?P<name>[A-Za-z_]\w*)\s*:\s*(?P<type>[!\[\]A-Za-z_][!\[\]A-Za-z_0-9]*)", args):
        clean_name = match.group("name")
        type_name = match.group("type")
        params.append(
            RequestParamFact(
                name=clean_name,
                source="argument",
                type=type_name,
                required=type_name.endswith("!"),
                evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
            )
        )
    return params


def _extract_nestjs_graphql_resolver_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    if "@Resolver" not in source or not any(token in source for token in ("@Query", "@Mutation", "@Subscription")):
        return []
    routes: list[ApiRouteFact] = []
    resolver_name = _first_match(source, r"export\s+class\s+([A-Za-z_$][\w$]*)") or Path(file_fact.path).stem
    for match in NEST_GRAPHQL_OPERATION_RE.finditer(source):
        operation_kind = match.group("decorator")
        line = _line_for_offset(source, match.start())
        operation_args, operation_end = _typescript_decorator_args(source, match.end())
        method_info = _nestjs_graphql_method_info(source, operation_end, file_fact.path, line)
        handler = method_info["name"]
        if not isinstance(handler, str) or not handler:
            continue
        operation_name = _nestjs_graphql_operation_name(operation_args, handler)
        response_type = _nestjs_graphql_response_type(operation_args) or (
            method_info["response_type"] if isinstance(method_info["response_type"], str) else None
        )
        routes.append(
            ApiRouteFact(
                method=operation_kind.upper(),
                path=f"/graphql#{operation_kind}.{operation_name}",
                handler=handler,
                framework="graphql",
                kind="nestjs-graphql-resolver",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                class_prefix=resolver_name,
                parameters=method_info["parameters"] if isinstance(method_info["parameters"], list) else [],
                response_type=response_type,
            )
        )
    return routes


def _typescript_decorator_args(source: str, decorator_end: int) -> tuple[str, int]:
    index = decorator_end
    while index < len(source) and source[index].isspace():
        index += 1
    if index >= len(source) or source[index] != "(":
        return "", decorator_end
    close = _find_matching_paren(source, index)
    if close is None:
        return "", decorator_end
    return source[index + 1 : close], close + 1


def _nestjs_graphql_method_info(source: str, offset: int, file_path: str, line: int) -> dict[str, object]:
    start = _skip_typescript_decorators(source, offset)
    match = TS_METHOD_RE.search(source[start : start + 1200])
    if not match:
        return {"name": None, "parameters": [], "response_type": None}
    method_start = start + match.start()
    paren_start = source.find("(", method_start)
    paren_end = _find_matching_paren(source, paren_start)
    params_source = source[paren_start + 1 : paren_end] if paren_end is not None else ""
    return {
        "name": match.group("name"),
        "parameters": _nestjs_graphql_parameters(params_source, file_path, line),
        "response_type": _nestjs_graphql_response_type(source[offset:method_start]) or _typescript_return_type_after(source, paren_end or -1),
    }


def _nestjs_graphql_operation_name(args: str, fallback: str) -> str:
    explicit = (
        _first_match(args, r"\bname\s*:\s*['\"`]([^'\"`]+)['\"`]")
        or _first_match(args, r"^\s*['\"`]([^'\"`]+)['\"`]")
    )
    return explicit or fallback


def _nestjs_graphql_response_type(decorator_source: str) -> str | None:
    match = re.search(r"=>\s*(?:\[\s*(?P<list>[A-Za-z_$][\w$]*)\s*\]|(?P<single>[A-Za-z_$][\w$]*))", decorator_source)
    if not match:
        return None
    if match.group("list"):
        return f"[{match.group('list')}]"
    return match.group("single")


def _nestjs_graphql_parameters(params_source: str, file_path: str, line: int) -> list[RequestParamFact]:
    params: list[RequestParamFact] = []
    for raw_param in _split_params(params_source):
        decorators = " ".join(re.findall(r"@\w+(?:\([^)]*\))?", raw_param, re.DOTALL))
        if not re.search(r"@\s*Args\b", decorators):
            continue
        name, type_name, required = _typescript_param_shape(raw_param)
        if not name:
            continue
        explicit_name = _nestjs_graphql_arg_name(decorators)
        params.append(
            RequestParamFact(
                name=explicit_name or name,
                source="argument",
                type=type_name,
                required=False if "nullable: true" in decorators else required,
                evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
            )
        )
    return _dedupe_request_params(params)


def _nestjs_graphql_arg_name(decorators: str) -> str | None:
    return (
        _first_match(decorators, r"@\s*Args\s*\(\s*['\"`]([^'\"`]+)['\"`]")
        or _first_match(decorators, r"\bname\s*:\s*['\"`]([^'\"`]+)['\"`]")
    )


def _extract_proto_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    package_match = PROTO_PACKAGE_RE.search(source)
    package_name = package_match.group("package") if package_match else ""
    routes: list[ApiRouteFact] = []
    for service_match in PROTO_SERVICE_RE.finditer(source):
        service_name = service_match.group("name")
        service_end = _find_matching_brace(source, source.find("{", service_match.end() - 1))
        if service_end is None:
            continue
        service_body = source[service_match.end() : service_end]
        for rpc_match in PROTO_RPC_RE.finditer(service_body):
            line = _line_for_offset(source, service_match.end() + rpc_match.start())
            rpc_name = rpc_match.group("name")
            request_type = _proto_stream_type(rpc_match.group("request"), rpc_match.group("request_type"))
            response_type = _proto_stream_type(rpc_match.group("response"), rpc_match.group("response_type"))
            service_path = f"{package_name + '.' if package_name else ''}{service_name}"
            routes.append(
                ApiRouteFact(
                    method="RPC",
                    path=f"/{service_path}/{rpc_name}",
                    handler=rpc_name,
                    framework="grpc",
                    kind="grpc-proto-rpc",
                    evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                    class_prefix=service_path,
                    request_body=request_type,
                    response_type=response_type,
                )
            )
    return routes


def _extract_trpc_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    if "trpc" not in source.lower() and "procedure" not in source:
        return []
    router_name = _trpc_router_name(file_fact.path, source)
    routes: list[ApiRouteFact] = []
    for match in TRPC_PROCEDURE_RE.finditer(source):
        body = match.group("body")
        procedure_name = match.group("name")
        kind = match.group("kind").upper()
        line = _line_for_offset(source, match.start())
        routes.append(
            ApiRouteFact(
                method=kind,
                path=f"/trpc/{router_name}.{procedure_name}" if router_name else f"/trpc/{procedure_name}",
                handler=procedure_name,
                framework="trpc",
                kind="trpc-procedure",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                class_prefix=router_name or None,
                request_body="input" if re.search(r"\.input\s*\(", body) else None,
            )
        )
    return routes


def _extract_socketio_events(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    if not _looks_like_socketio_server_source(file_fact.path, source):
        return []
    routes: list[ApiRouteFact] = []
    for match in SOCKET_EVENT_RE.finditer(source):
        event = match.group("event")
        line = _line_for_offset(source, match.start())
        routes.append(
            ApiRouteFact(
                method="EVENT",
                path=f"socket.io#{event}",
                handler=event,
                framework="socketio",
                kind="socketio-event",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
            )
        )
    return routes


def _extract_websocket_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    if not _looks_like_raw_websocket_server_source(file_fact.path, source):
        return []
    routes: list[ApiRouteFact] = []
    for match in WEBSOCKET_PATH_RE.finditer(source):
        line = _line_for_offset(source, match.start())
        routes.append(
            ApiRouteFact(
                method="WS",
                path=match.group("path"),
                handler="WebSocketServer",
                framework="websocket",
                kind="websocket-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
            )
        )
    for match in WEBSOCKET_EVENT_RE.finditer(source):
        event = match.group("event").lower()
        line = _line_for_offset(source, match.start())
        routes.append(
            ApiRouteFact(
                method="EVENT",
                path=f"websocket#{event}",
                handler=event,
                framework="websocket",
                kind="websocket-event",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
            )
        )
    return _dedupe_routes(routes)


def _extract_electron_ipc_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    if "ipcMain" not in source or "electron" not in source:
        return []
    routes: list[ApiRouteFact] = []
    for match in ELECTRON_IPC_MAIN_RE.finditer(source):
        if _offset_is_comment_line(source, match.start()):
            continue
        line = _line_for_offset(source, match.start())
        routes.append(
            ApiRouteFact(
                method="IPC",
                path=f"ipc#{match.group('channel')}",
                handler=f"ipcMain.{match.group('kind')}",
                framework="electron",
                kind="electron-ipc-main",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
            )
        )
    return _dedupe_routes(routes)


def _extract_sse_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    if "text/event-stream" not in source and "EventSource" not in source and "subscribe" not in source and "getEventStream" not in source and "publishEvent" not in source:
        return []
    routes: list[ApiRouteFact] = []
    for match in EXPRESS_ROUTE_RE.finditer(source):
        route_context = source[match.start() : min(len(source), match.start() + 2200)]
        if "text/event-stream" not in route_context:
            continue
        line = _line_for_offset(source, match.start())
        routes.append(
            ApiRouteFact(
                method="STREAM",
                path=match.group("path"),
                handler=match.group("handler") or "sse-handler",
                framework="sse",
                kind="sse-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
            )
        )
    for match in SSE_EXPRESS_ROUTE_RE.finditer(source):
        path = match.group("path")
        args = match.group("args")
        if not _looks_like_sse_route_hint(path, args):
            continue
        line = _line_for_offset(source, match.start())
        routes.append(
            ApiRouteFact(
                method="STREAM",
                path=path,
                handler=_last_handler_name(args) or "sse-handler",
                framework="sse",
                kind="sse-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
            )
        )
    constants = _string_constants(source)
    for match in PARTICLE_EVENT_STREAM_RE.finditer(source):
        event_name = _event_name_from_object_body(match.group("body"), constants)
        if not event_name:
            continue
        line = _line_for_offset(source, match.start())
        routes.append(_event_route(file_fact.path, line, "CONSUME", f"sse#{event_name}", event_name, "sse", "particle-event-stream"))
    for match in PARTICLE_PUBLISH_EVENT_RE.finditer(source):
        event_name = _event_name_from_object_body(match.group("body"), constants)
        if not event_name:
            continue
        line = _line_for_offset(source, match.start())
        routes.append(_event_route(file_fact.path, line, "PRODUCE", f"sse#{event_name}", event_name, "sse", "particle-event-stream"))
    return _dedupe_routes(routes)


def _extract_message_queue_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    routes: list[ApiRouteFact] = []
    routes.extend(_extract_kafka_routes(file_fact, source))
    routes.extend(_extract_rabbitmq_routes(file_fact, source))
    routes.extend(_extract_bullmq_routes(file_fact, source))
    routes.extend(_extract_redis_pubsub_routes(file_fact, source))
    return _dedupe_routes(routes)


def _extract_kafka_routes(file_fact: FileFact, source: str) -> list[ApiRouteFact]:
    if not _looks_like_kafka_source(source):
        return []
    routes: list[ApiRouteFact] = []
    for match in KAFKA_TOPIC_RE.finditer(source):
        topic = match.group("topic")
        context = source[max(0, match.start() - 260) : min(len(source), match.end() + 260)].lower()
        methods = _kafka_methods_from_context(context)
        line = _line_for_offset(source, match.start())
        for method in methods:
            routes.append(_event_route(file_fact.path, line, method, f"kafka#{topic}", topic, "kafka", "kafka-topic"))
    for match in KAFKA_TOPICS_ARRAY_RE.finditer(source):
        context = source[max(0, match.start() - 260) : min(len(source), match.end() + 260)].lower()
        methods = _kafka_methods_from_context(context)
        line = _line_for_offset(source, match.start())
        for topic in _quoted_values(match.group("topics")):
            for method in methods:
                routes.append(_event_route(file_fact.path, line, method, f"kafka#{topic}", topic, "kafka", "kafka-topic"))
    return routes


def _extract_rabbitmq_routes(file_fact: FileFact, source: str) -> list[ApiRouteFact]:
    if not _looks_like_rabbitmq_source(source):
        return []
    routes: list[ApiRouteFact] = []
    constants = _string_constants(source)
    for match in RABBIT_SEND_RE.finditer(source):
        queue = _argument_value(match.group("queue"), constants)
        if not queue:
            continue
        line = _line_for_offset(source, match.start())
        routes.append(_event_route(file_fact.path, line, "PRODUCE", f"rabbitmq#{queue}", queue, "rabbitmq", "rabbitmq-queue"))
    for match in RABBIT_CONSUME_RE.finditer(source):
        queue = _argument_value(match.group("queue"), constants)
        if not queue:
            continue
        line = _line_for_offset(source, match.start())
        routes.append(_event_route(file_fact.path, line, "CONSUME", f"rabbitmq#{queue}", queue, "rabbitmq", "rabbitmq-queue"))
    for match in RABBIT_PUBLISH_RE.finditer(source):
        exchange = _argument_value(match.group("exchange"), constants) or "default"
        routing_key = _argument_value(match.group("routing_key"), constants) or "default"
        line = _line_for_offset(source, match.start())
        path = f"rabbitmq#{exchange}/{routing_key}"
        routes.append(_event_route(file_fact.path, line, "PRODUCE", path, routing_key, "rabbitmq", "rabbitmq-exchange"))
    return routes


def _extract_bullmq_routes(file_fact: FileFact, source: str) -> list[ApiRouteFact]:
    if not _looks_like_bullmq_source(source):
        return []
    routes: list[ApiRouteFact] = []
    for match in BULL_QUEUE_RE.finditer(source):
        queue = match.group("queue")
        line = _line_for_offset(source, match.start())
        routes.append(_event_route(file_fact.path, line, "PRODUCE", f"bullmq#{queue}", queue, "bullmq", "bullmq-queue"))
    for match in BULL_WORKER_RE.finditer(source):
        queue = match.group("queue")
        line = _line_for_offset(source, match.start())
        routes.append(_event_route(file_fact.path, line, "CONSUME", f"bullmq#{queue}", queue, "bullmq", "bullmq-worker"))
    return routes


def _looks_like_bullmq_source(source: str) -> bool:
    return (
        "bullmq" in source
        or "from 'bull'" in source
        or 'from "bull"' in source
        or "require('bull')" in source
        or 'require("bull")' in source
    )


def _extract_redis_pubsub_routes(file_fact: FileFact, source: str) -> list[ApiRouteFact]:
    if "redis" not in source.lower():
        return []
    routes: list[ApiRouteFact] = []
    for match in REDIS_PUBLISH_RE.finditer(source):
        channel = match.group("channel")
        line = _line_for_offset(source, match.start())
        routes.append(_event_route(file_fact.path, line, "PRODUCE", f"redis#{channel}", channel, "redis-pubsub", "redis-channel"))
    for match in REDIS_SUBSCRIBE_RE.finditer(source):
        channel = match.group("channel")
        line = _line_for_offset(source, match.start())
        routes.append(_event_route(file_fact.path, line, "CONSUME", f"redis#{channel}", channel, "redis-pubsub", "redis-channel"))
    return routes


def _event_route(
    file_path: str,
    line: int,
    method: str,
    path: str,
    handler: str,
    framework: str,
    kind: str,
) -> ApiRouteFact:
    return ApiRouteFact(
        method=method,
        path=path,
        handler=handler,
        framework=framework,
        kind=kind,
        evidence=Evidence(file=file_path, kind="backend-route", line_start=line, line_end=line),
    )


def _looks_like_raw_websocket_server_source(path: str, source: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    if "socket.io" in source or "socket.io-client" in source:
        return False
    return (
        "WebSocketServer" in source
        or "WebSocket.Server" in source
        or "require('ws')" in source
        or 'require("ws")' in source
        or "from 'ws'" in source
        or 'from "ws"' in source
        or normalized.startswith(("server/", "backend/", "api/"))
        and re.search(r"\bwss?\.on\(\s*['\"](?:connection|message)", source) is not None
    )


def _looks_like_kafka_source(source: str) -> bool:
    lower = source.lower()
    return (
        "kafkajs" in lower
        or "kafka-node" in lower
        or "node-rdkafka" in lower
        or "kafkaclient" in source
        or "kafka.producer" in lower
        or "kafka.consumer" in lower
    )


def _looks_like_sse_route_hint(path: str, args: str) -> bool:
    normalized = f"{path} {args}".lower()
    return (
        "event" in normalized
        and ("subscribe" in normalized or "sse" in normalized or "events." in normalized)
    )


def _last_handler_name(args: str) -> str | None:
    names = re.findall(r"\b([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)?)\s*(?:,|\))", args)
    return names[-1] if names else None


def _event_name_from_object_body(body: str, constants: dict[str, str]) -> str | None:
    match = OBJECT_NAME_RE.search(body)
    if not match:
        return None
    return _argument_value(match.group("value"), constants)


def _looks_like_rabbitmq_source(source: str) -> bool:
    lower = source.lower()
    return "amqplib" in lower or "amqp://" in lower or "rabbitmq" in lower or "sendtoqueue" in lower


def _kafka_methods_from_context(context: str) -> list[str]:
    methods: list[str] = []
    if "producer" in context or ".send" in context or "producerstream" in context:
        methods.append("PRODUCE")
    if "consumer" in context or "subscribe" in context or ".on(" in context:
        methods.append("CONSUME")
    return methods or ["EVENT"]


def _quoted_values(source: str) -> list[str]:
    return [match.group("value") for match in re.finditer(r"['\"](?P<value>[^'\"]+)['\"]", source)]


def _string_constants(source: str) -> dict[str, str]:
    constants: dict[str, str] = {}
    for match in re.finditer(
        r"\b(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*['\"](?P<value>[^'\"]*)['\"]",
        source,
    ):
        constants[match.group("name")] = match.group("value")
    return constants


def _argument_value(raw: str, constants: dict[str, str]) -> str | None:
    value = raw.strip()
    if len(value) >= 2 and value[0] in {"'", '"'} and value[-1] == value[0]:
        literal = value[1:-1]
        return literal or None
    if value in constants:
        return constants[value]
    if re.fullmatch(r"[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)?", value):
        return f"dynamic:{value}"
    return None


def _extract_ktor_routes(root: Path, file_fact: FileFact, resources: dict[str, str]) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    if not _looks_like_ktor_server_source(source):
        return []

    routes: list[ApiRouteFact] = []
    prefix_stack: list[tuple[str, int]] = []
    for match in KTOR_ROUTE_CALL_RE.finditer(source):
        if _offset_is_comment_line(source, match.start()):
            continue
        open_brace = source.rfind("{", match.start(), match.end())
        close_brace = _find_matching_brace(source, open_brace)
        if open_brace < 0 or close_brace is None:
            continue

        while prefix_stack and match.start() > prefix_stack[-1][1]:
            prefix_stack.pop()

        call = match.group("call").lower()
        current_prefix = prefix_stack[-1][0] if prefix_stack else ""
        args = match.group("args") or ""
        resource_path = _ktor_resource_path(match.group("generic") or "", resources)
        path_part = _ktor_path_from_args(args) or resource_path
        if call == "route":
            prefix = _join_paths(current_prefix, path_part) if path_part else current_prefix or "/"
            prefix_stack.append((prefix, close_brace))
            continue

        method = KTOR_METHODS.get(call)
        if method is None:
            continue
        path = _join_paths(current_prefix, path_part)
        line = _line_for_offset(source, match.start())
        body = source[open_brace + 1 : close_brace]
        routes.append(
            ApiRouteFact(
                method=method,
                path=path,
                handler=_ktor_handler_name(file_fact.path, source, match.start(), method, path),
                framework="ktor",
                kind="ktor-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                parameters=_ktor_route_parameters(path, body, file_fact.path, line),
                request_body=_ktor_request_body(body),
                response_type=_ktor_response_type(body),
            )
        )
    return routes


def _looks_like_ktor_server_source(source: str) -> bool:
    if "routing" not in source and not any(marker in source for marker in ("embeddedServer", "Application.")):
        return False
    server_markers = (
        "io.ktor.server",
        "io.ktor.application",
        "embeddedServer(",
        "fun Application.",
        "call.respond",
        "call.receive",
        "routing {",
    )
    return any(marker in source for marker in server_markers)


def _ktor_resource_paths(root: Path, files: list[FileFact]) -> dict[str, str]:
    resources: dict[str, str] = {}
    for file_fact in files:
        if file_fact.language != "kotlin" or file_fact.role in {"test", "sample", "generated"}:
            continue
        source = _read(root, file_fact)
        if "@Resource" not in source:
            continue
        for match in KTOR_RESOURCE_RE.finditer(source):
            resources.setdefault(match.group("name"), match.group("path"))
    return resources


def _ktor_resource_path(generic: str, resources: dict[str, str]) -> str:
    if not generic:
        return ""
    name = generic.strip("<> \t\r\n").split(".", 1)[-1]
    return resources.get(name, "")


def _ktor_path_from_args(args: str) -> str:
    cleaned = args.strip()
    if not cleaned:
        return ""
    literal = re.search(r"""['"](?P<path>[^'"]*)['"]""", cleaned)
    if literal:
        return literal.group("path")
    named_path = re.search(r"\bpath\s*=\s*(?P<value>[A-Za-z_]\w*)\b", cleaned)
    if named_path:
        return f"dynamic:{named_path.group('value')}"
    first_identifier = re.match(r"\s*(?P<value>[A-Za-z_]\w*)\s*(?:,|$)", cleaned)
    if first_identifier:
        return f"dynamic:{first_identifier.group('value')}"
    return ""


def _ktor_route_parameters(path: str, body: str, file_path: str, line: int) -> list[RequestParamFact]:
    params: list[RequestParamFact] = []
    for name in _ktor_path_parameter_names(path):
        params.append(
            RequestParamFact(
                name=name,
                source="path",
                type=None,
                required=True,
                evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
            )
        )
    for name in re.findall(r"\bcall\.request\.queryParameters\[\s*['\"]([^'\"]+)['\"]\s*\]", body):
        params.append(
            RequestParamFact(
                name=name,
                source="query",
                type=None,
                required=False,
                evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
            )
        )
    for name in re.findall(r"\bcall\.request\.queryParameters\.get\(\s*['\"]([^'\"]+)['\"]", body):
        params.append(
            RequestParamFact(
                name=name,
                source="query",
                type=None,
                required=False,
                evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
            )
        )
    return _dedupe_request_params(params)


def _ktor_path_parameter_names(path: str) -> list[str]:
    names: list[str] = []
    for raw in re.findall(r"\{([^}]+)\}", path):
        value = raw.strip().rstrip("?").removesuffix("...").lstrip("$")
        value = value.split(":", 1)[0].split("=", 1)[0]
        value = re.sub(r"[^A-Za-z0-9_.-]+", "", value)
        if value:
            names.append(value)
    return _dedupe(names)


def _ktor_request_body(body: str) -> str | None:
    typed_receive = re.search(r"\bcall\.receive\s*<\s*([A-Za-z_][\w.<>, ?]*)\s*>\s*\(", body)
    if typed_receive:
        return re.sub(r"\s+", "", typed_receive.group(1))
    if "call.receiveMultipart(" in body:
        return "multipart"
    if "call.receiveParameters(" in body:
        return "Parameters"
    if "call.receiveText(" in body:
        return "text"
    if re.search(r"\bcall\.receive\s*\(", body):
        return "unknown"
    return None


def _ktor_response_type(body: str) -> str | None:
    typed_respond = re.search(r"\bcall\.respond\s*<\s*([A-Za-z_][\w.<>, ?]*)\s*>\s*\(", body)
    if typed_respond:
        return re.sub(r"\s+", "", typed_respond.group(1))
    if "call.respondHtml" in body:
        return "html"
    if "call.respondText" in body:
        return "text"
    if "call.respondRedirect" in body:
        return "redirect"
    if "call.respond(" in body:
        return "response"
    return None


def _ktor_handler_name(file_path: str, source: str, offset: int, method: str, path: str) -> str:
    function_name = None
    for match in re.finditer(r"\bfun\s+(?:[A-Za-z_]\w*\.)?(?P<name>[A-Za-z_]\w*)\s*\(", source[:offset]):
        function_name = match.group("name")
    base = function_name or Path(file_path).stem
    return f"{base}.{method.lower()} {path}"


def _dedupe_request_params(params: list[RequestParamFact]) -> list[RequestParamFact]:
    seen: set[tuple[str, str]] = set()
    result: list[RequestParamFact] = []
    for param in params:
        key = (param.source, param.name)
        if key in seen:
            continue
        seen.add(key)
        result.append(param)
    return result


def _dedupe_values(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _dedupe_routes(routes: list[ApiRouteFact]) -> list[ApiRouteFact]:
    seen: set[tuple[str, str, str, str]] = set()
    result: list[ApiRouteFact] = []
    for route in routes:
        key = (route.method, route.path, route.framework, route.kind)
        if key in seen:
            continue
        seen.add(key)
        result.append(route)
    return result


def _dedupe_routes_with_handler(routes: list[ApiRouteFact]) -> list[ApiRouteFact]:
    seen: set[tuple[str, str, str, str, str | None]] = set()
    result: list[ApiRouteFact] = []
    for route in routes:
        key = (route.method, route.path, route.framework, route.kind, route.handler)
        if key in seen:
            continue
        seen.add(key)
        result.append(route)
    return result


def _proto_stream_type(stream_marker: str | None, type_name: str) -> str:
    return f"stream {type_name}" if stream_marker else type_name


def _trpc_router_name(path: str, source: str) -> str | None:
    match = re.search(r"\bconst\s+(?P<name>[A-Za-z_$][\w$]*Router)\s*=", source)
    if match:
        router_name = match.group("name").removesuffix("Router")
        return None if router_name == "app" else router_name
    stem = Path(path).stem
    if stem == "_app":
        return None
    if stem.endswith(".routes"):
        stem = stem.removesuffix(".routes")
    return re.sub(r"[^A-Za-z0-9_]+", ".", stem).strip(".") or None


def _looks_like_socketio_server_source(path: str, source: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return (
        ("socket.io" in source and "socket.io-client" not in source)
        or "socketio(" in source
        or "flask_socketio" in source
        or re.search(r"\bio\.on\(\s*['\"](?:connect|connection)", source) is not None
        or normalized.startswith(("server/", "backend/", "api/"))
    )


def _extract_nestjs_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    if "@Controller" not in source:
        return []
    routes: list[ApiRouteFact] = []
    for class_match in NEST_CONTROLLER_RE.finditer(source):
        class_start = source.find("{", class_match.end())
        if class_start == -1:
            continue
        class_end = _find_matching_brace(source, class_start)
        if class_end is None:
            continue
        prefix = _path_from_args(class_match.group("args") or "", default="")
        class_body = source[class_start:class_end]
        for route_match in NEST_ROUTE_RE.finditer(class_body):
            args = route_match.group("args") or ""
            absolute_route_start = class_start + route_match.start()
            line = _line_for_offset(source, absolute_route_start)
            method_info = _nestjs_method_info(source, class_start + route_match.end(), file_fact.path, line)
            route_path = _join_paths(prefix, _path_from_args(args, default="/"))
            parameters = _dedupe_request_params(
                list(method_info["parameters"]) + _nestjs_path_parameters(route_path, file_fact.path, line)
            )
            routes.append(
                ApiRouteFact(
                    method=route_match.group("decorator").upper(),
                    path=route_path,
                    handler=method_info["name"],
                    framework="nestjs",
                    kind="nestjs-route",
                    evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                    class_prefix=prefix or None,
                    parameters=parameters,
                    request_body=method_info["request_body"],
                    response_type=method_info["response_type"],
                )
            )
    return routes


def _nestjs_method_info(source: str, offset: int, file_path: str, route_line: int) -> dict[str, object]:
    start = _skip_typescript_decorators(source, offset)
    match = TS_METHOD_RE.search(source[start : start + 1200])
    if not match:
        return {"name": None, "parameters": [], "request_body": None, "response_type": None}
    method_start = start + match.start()
    paren_start = source.find("(", method_start)
    paren_end = _find_matching_paren(source, paren_start)
    decorator_source = source[offset:method_start]
    params_source = source[paren_start + 1 : paren_end] if paren_end is not None else ""
    parameters, request_body = _nestjs_route_parameters(params_source, file_path, route_line)
    return_type = _typescript_return_type_after(source, paren_end or -1)
    return {
        "name": match.group("name"),
        "parameters": parameters,
        "request_body": request_body,
        "response_type": _nestjs_response_type(decorator_source, return_type),
    }


def _nestjs_route_parameters(params_source: str, file_path: str, line: int) -> tuple[list[RequestParamFact], str | None]:
    params: list[RequestParamFact] = []
    request_body: str | None = None
    for raw_param in _split_params(params_source):
        decorators = " ".join(re.findall(r"@\w+(?:\([^)]*\))?", raw_param, re.DOTALL))
        name, type_name, required = _typescript_param_shape(raw_param)
        if not name:
            continue
        source_kind = _nestjs_parameter_source(decorators)
        explicit_name = _nestjs_parameter_name(decorators)
        if source_kind == "body":
            request_body = type_name or explicit_name or name
        if source_kind not in {"path", "query", "header", "body"}:
            continue
        params.append(
            RequestParamFact(
                name=explicit_name or name,
                source=source_kind,
                type=type_name,
                required=True if source_kind == "path" else required,
                evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
            )
        )
    return params, request_body


def _nestjs_path_parameters(path: str, file_path: str, line: int) -> list[RequestParamFact]:
    return [
        RequestParamFact(
            name=match.group("name"),
            source="path",
            type=None,
            required=True,
            evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
        )
        for match in re.finditer(r":(?P<name>[A-Za-z_][A-Za-z0-9_-]*)", path)
    ]


def _nestjs_parameter_source(decorators: str) -> str | None:
    decorator_map = {
        "Param": "path",
        "Query": "query",
        "Body": "body",
        "Headers": "header",
        "Header": "header",
    }
    for decorator, source in decorator_map.items():
        if re.search(rf"@\s*{decorator}\b", decorators):
            return source
    return None


def _nestjs_parameter_name(decorators: str) -> str | None:
    match = re.search(r"@\s*(?:Param|Query|Body|Headers|Header)\s*\(\s*['\"`]([^'\"`]+)['\"`]", decorators)
    return match.group(1) if match else None


def _nestjs_response_type(decorator_source: str, return_type: str | None) -> str | None:
    for match in re.finditer(r"@Api[A-Za-z]*Response\s*\(\s*\{(?P<body>[\s\S]*?)\}\s*\)", decorator_source):
        body = match.group("body")
        type_match = re.search(r"\btype\s*:\s*(?P<type>[A-Za-z_$][\w$]*)", body)
        if not type_match:
            continue
        type_name = type_match.group("type")
        return f"{type_name}[]" if re.search(r"\bisArray\s*:\s*true\b", body) else type_name
    return return_type


def _extract_django_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    normalized = file_fact.path.replace("\\", "/").lower()
    if not normalized.endswith("urls.py"):
        return []
    source = _read(root, file_fact)
    return _django_routes_for_file(file_fact, source)


def _looks_like_django_route_module(root: Path, file_fact: FileFact) -> bool:
    normalized = file_fact.path.replace("\\", "/").lower()
    if normalized.endswith("urls.py"):
        return True
    source = _read(root, file_fact)
    return "router.register" in source or "urlpatterns" in source or "include(" in source


def _django_routes_for_file(file_fact: FileFact, source: str) -> list[ApiRouteFact]:
    constants = _python_string_constants(source)
    route_lists = _django_route_lists(file_fact, source, constants)
    routes: list[ApiRouteFact] = []

    for start, end in _django_urlpattern_list_ranges(source):
        routes.extend(_django_routes_from_region(file_fact, source, start, end, constants))

    routes.extend(_django_local_include_routes(file_fact, source, route_lists, constants))
    routes.extend(_django_direct_router_routes(file_fact, source))
    return _dedupe_routes(routes)


def _extract_django_mounted_routes(root: Path, files: list[FileFact]) -> list[ApiRouteFact]:
    if not files:
        return []
    sources = {file_fact.path: _read(root, file_fact) for file_fact in files}
    routes_by_file = {
        file_fact.path: _django_routes_for_file(file_fact, sources[file_fact.path])
        for file_fact in files
    }
    module_files = _django_module_file_map(files)
    mounted: list[ApiRouteFact] = []

    for file_fact in files:
        source = sources[file_fact.path]
        constants = _python_string_constants(source)
        for mount in _django_include_mounts(source, constants):
            target_kind, target_name, prefix, line, child_hint = mount
            if target_kind != "module":
                continue
            target_file = module_files.get(target_name)
            if not target_file:
                continue
            for child in routes_by_file.get(target_file.path, []):
                mounted.append(
                    _django_mounted_route(
                        file_fact,
                        line,
                        prefix,
                        child,
                        child_hint or target_name,
                    )
                )
    return _dedupe_routes(mounted)


def _django_urlpattern_list_ranges(source: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    search_source = _python_code_mask(source)
    for match in re.finditer(r"(?m)^urlpatterns\s*(?:\+)?=\s*\[", search_source):
        open_index = source.find("[", match.start())
        close_index = _find_matching_square(source, open_index)
        if close_index is not None:
            ranges.append((open_index + 1, close_index))
    return ranges


def _django_route_lists(
    file_fact: FileFact,
    source: str,
    constants: dict[str, str],
) -> dict[str, list[ApiRouteFact]]:
    lists: dict[str, list[ApiRouteFact]] = {}
    search_source = _python_code_mask(source)
    for match in PYTHON_LIST_ASSIGN_RE.finditer(search_source):
        name = match.group("name")
        open_index = source.find("[", match.start())
        close_index = _find_matching_square(source, open_index)
        if close_index is None:
            continue
        lists[name] = _django_routes_from_region(file_fact, source, open_index + 1, close_index, constants)
    return lists


def _django_routes_from_region(
    file_fact: FileFact,
    source: str,
    start: int,
    end: int,
    constants: dict[str, str],
) -> list[ApiRouteFact]:
    routes: list[ApiRouteFact] = []
    for function_name, args, call_start in _django_route_calls(source, start, end):
        route = _django_route_from_call(file_fact, source, function_name, args, call_start, constants)
        if route:
            routes.append(route)
    return routes


def _django_route_calls(source: str, start: int = 0, end: int | None = None) -> list[tuple[str, str, int]]:
    limit = len(source) if end is None else end
    search_source = _python_code_mask(source)
    calls: list[tuple[str, str, int]] = []
    for match in DJANGO_ROUTE_CALL_RE.finditer(search_source, start, limit):
        open_index = source.find("(", match.start(), limit)
        close_index = _find_matching_paren(source, open_index)
        if close_index is None or close_index > limit:
            continue
        calls.append((match.group("fn"), source[open_index + 1 : close_index], match.start()))
    return calls

def _django_route_from_call(
    file_fact: FileFact,
    source: str,
    function_name: str,
    args: str,
    call_start: int,
    constants: dict[str, str],
) -> ApiRouteFact | None:
    parts = _split_params(args)
    if len(parts) < 2:
        return None
    if _django_include_target(parts[1]) is not None:
        return None
    path = _django_path_from_arg(parts[0], constants)
    if path is None:
        return None
    line = _line_for_offset(source, call_start)
    normalized_path = _django_normalize_path(path, function_name)
    return ApiRouteFact(
        method="ANY",
        path=normalized_path,
        handler=_django_handler_from_arg(parts[1]),
        framework="django",
        kind="django-path-route" if function_name == "path" else "django-regex-route",
        evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
        parameters=_django_path_parameters(normalized_path, file_fact.path, line),
    )


def _django_local_include_routes(
    file_fact: FileFact,
    source: str,
    route_lists: dict[str, list[ApiRouteFact]],
    constants: dict[str, str],
) -> list[ApiRouteFact]:
    routes: list[ApiRouteFact] = []
    for target_kind, target_name, prefix, line, child_hint in _django_include_mounts(source, constants):
        if target_kind == "list":
            children = route_lists.get(target_name, [])
        elif target_kind == "router":
            children = _django_router_routes(file_fact, source, target_name)
        else:
            continue
        for child in children:
            routes.append(_django_mounted_route(file_fact, line, prefix, child, child_hint or target_name))
    return routes


def _django_include_mounts(
    source: str,
    constants: dict[str, str],
) -> list[tuple[str, str, str, int, str | None]]:
    mounts: list[tuple[str, str, str, int, str | None]] = []
    for _function_name, args, call_start in _django_route_calls(source):
        parts = _split_params(args)
        if len(parts) < 2:
            continue
        target = _django_include_target(parts[1])
        if target is None:
            continue
        prefix = _django_path_from_arg(parts[0], constants)
        if prefix is None:
            continue
        line = _line_for_offset(source, call_start)
        mounts.append((target[0], target[1], _django_normalize_path(prefix, _function_name) if prefix else "/", line, target[2]))
    return mounts


def _django_include_target(arg: str) -> tuple[str, str, str | None] | None:
    include_index = arg.find("include")
    if include_index < 0:
        return None
    open_index = arg.find("(", include_index)
    if open_index < 0:
        return None
    close_index = _find_matching_paren(arg, open_index)
    if close_index is None:
        return None
    include_args = _split_params(arg[open_index + 1 : close_index])
    if not include_args:
        return None
    first = include_args[0].strip()
    if first.startswith("(") and first.endswith(")"):
        tuple_args = _split_params(first[1:-1])
        if tuple_args:
            first = tuple_args[0].strip()
    literal = _python_string_literal(first)
    if literal:
        return ("module", literal, literal)
    router_match = re.fullmatch(r"(?P<name>[A-Za-z_]\w*)\.urls", first)
    if router_match:
        return ("router", router_match.group("name"), first)
    if re.fullmatch(r"[A-Za-z_]\w*", first):
        return ("list", first, first)
    return None


def _django_direct_router_routes(file_fact: FileFact, source: str) -> list[ApiRouteFact]:
    return _django_router_routes(file_fact, source, None)


def _django_router_routes(
    file_fact: FileFact,
    source: str,
    router_name: str | None,
) -> list[ApiRouteFact]:
    routes: list[ApiRouteFact] = []
    for match in DRF_REGISTER_RE.finditer(source):
        if router_name and match.group("router") != router_name:
            continue
        line = _line_for_offset(source, match.start())
        routes.append(
            ApiRouteFact(
                method="ANY",
                path=_ensure_slash(match.group("path")),
                handler=match.group("handler"),
                framework="drf",
                kind="drf-router-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
            )
        )
    return routes


def _django_mounted_route(
    file_fact: FileFact,
    line: int,
    prefix: str,
    child: ApiRouteFact,
    include_target: str,
) -> ApiRouteFact:
    child_line = child.evidence.line_start or 1
    note = (
        f"include {include_target}; child={child.evidence.file}:{child_line}; "
        f"child_path={child.path}"
    )
    mounted_path = _join_paths(prefix, child.path)
    return ApiRouteFact(
        method=child.method,
        path=mounted_path,
        handler=child.handler,
        framework=child.framework,
        kind="drf-mounted-router-route" if child.framework == "drf" else "django-mounted-route",
        evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line, note=note),
        class_prefix=prefix if prefix != "/" else None,
        parameters=child.parameters or _django_path_parameters(mounted_path, file_fact.path, line),
        request_body=child.request_body,
        response_type=child.response_type,
    )


def _replace_django_relative_routes(
    routes: list[ApiRouteFact],
    mounted_routes: list[ApiRouteFact],
) -> list[ApiRouteFact]:
    mounted_children: set[tuple[str, str, str, str, int | None]] = set()
    for route in mounted_routes:
        note = route.evidence.note or ""
        child = re.search(r"child=(?P<file>[^:;]+):(?P<line>\d+); child_path=(?P<path>[^;]+)", note)
        if not child:
            continue
        mounted_children.add(
            (
                route.method,
                child.group("path"),
                route.framework,
                child.group("file"),
                int(child.group("line")),
            )
        )
    if not mounted_children:
        return routes
    result: list[ApiRouteFact] = []
    for route in routes:
        key = (
            route.method,
            route.path,
            route.framework,
            route.evidence.file,
            route.evidence.line_start,
        )
        if key in mounted_children:
            continue
        result.append(route)
    return result


def _django_module_file_map(files: list[FileFact]) -> dict[str, FileFact]:
    module_files: dict[str, FileFact] = {}
    for file_fact in files:
        normalized = file_fact.path.replace("\\", "/")
        if not normalized.endswith(".py"):
            continue
        module = normalized[:-3].replace("/", ".")
        parts = module.split(".")
        for index in range(len(parts)):
            name = ".".join(parts[index:])
            module_files.setdefault(name, file_fact)
    return module_files


def _django_path_from_arg(raw: str, constants: dict[str, str]) -> str | None:
    value = raw.strip()
    literal = _python_string_literal(value)
    if literal is not None:
        return _replace_python_format_parts(literal, constants)
    if value in constants:
        return constants[value]
    return "" if re.fullmatch(r"[A-Za-z_]\w*", value) else None


def _python_string_constants(source: str) -> dict[str, str]:
    constants: dict[str, str] = {}
    for match in re.finditer(
        r"(?m)^\s*(?P<name>[A-Za-z_]\w*)\s*(?::[^=\n]+)?=\s*(?P<raw>[rRuUbBfF]*['\"][^\n]*['\"])",
        source,
    ):
        literal = _python_string_literal(match.group("raw"))
        if literal is None:
            continue
        if "{" in literal and match.group("name") in constants:
            continue
        constants[match.group("name")] = _replace_python_format_parts(literal, constants)
    return constants


def _python_code_mask(source: str) -> str:
    masked = list(source)
    line_offsets = _line_offsets(source)
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for token in tokens:
            if token.type not in {tokenize.STRING, tokenize.COMMENT}:
                continue
            start = _position_offset(line_offsets, token.start)
            end = _position_offset(line_offsets, token.end)
            for index in range(start, min(end, len(masked))):
                if masked[index] not in "\r\n":
                    masked[index] = " "
    except tokenize.TokenError:
        return source
    return "".join(masked)


def _line_offsets(source: str) -> list[int]:
    offsets = [0]
    for match in re.finditer(r"\n", source):
        offsets.append(match.end())
    return offsets


def _position_offset(line_offsets: list[int], position: tuple[int, int]) -> int:
    line, column = position
    if line <= 0:
        return 0
    if line > len(line_offsets):
        return line_offsets[-1]
    return line_offsets[line - 1] + column


def _python_string_literal(raw: str) -> str | None:
    token_value = _python_concatenated_string_literal(raw)
    if token_value is not None:
        return token_value
    match = re.match(r"(?is)^[rRuUbBfF]*(?P<quote>['\"])(?P<value>.*)(?P=quote)$", raw.strip())
    return match.group("value") if match else None


def _python_concatenated_string_literal(raw: str) -> str | None:
    values: list[str] = []
    try:
        tokens = tokenize.generate_tokens(io.StringIO(raw).readline)
        for token in tokens:
            if token.type in {tokenize.ENCODING, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER}:
                continue
            if token.type != tokenize.STRING:
                return None
            try:
                value = ast.literal_eval(token.string)
            except (SyntaxError, ValueError):
                return None
            if not isinstance(value, str):
                return None
            values.append(value)
    except tokenize.TokenError:
        return None
    return "".join(values) if values else None


def _replace_python_format_parts(value: str, constants: dict[str, str]) -> str:
    def replacement(match: re.Match[str]) -> str:
        name = match.group(1).strip()
        return constants.get(name, "")

    return re.sub(r"\{([^{}]+)\}", replacement, value)


def _django_normalize_path(path: str, function_name: str) -> str:
    cleaned = path
    if function_name in {"re_path", "url"}:
        cleaned = cleaned.removeprefix("^").removesuffix("$")
        cleaned = re.sub(r"\(\?P<(?P<name>[A-Za-z_]\w*)>[^)]+\)", r":\g<name>", cleaned)
        cleaned = re.sub(r"\(\?:([^)]*)\)", r"\1", cleaned)
        cleaned = cleaned.replace("\\/", "/").replace("\\.", ".")
        cleaned = cleaned.replace("\\", "")
        cleaned = cleaned.replace("?", "")
    if cleaned not in {"", "/"}:
        cleaned = cleaned.rstrip("/")
    return _ensure_slash(cleaned)


def _django_path_parameters(path: str, file_path: str, line: int) -> list[RequestParamFact]:
    return [
        RequestParamFact(
            name=name,
            source="path",
            type=None,
            required=True,
            evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
        )
        for name in _dedupe_values(re.findall(r":([A-Za-z_]\w*)", path))
    ]


def _django_handler_from_arg(raw: str) -> str | None:
    value = raw.strip()
    match = re.match(r"(?P<handler>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)(?:\s*\(|\s*$)", value)
    return match.group("handler") if match else None


def _extract_go_http_routes(root: Path, file_fact: FileFact, framework_fallback: str | None = None) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    framework = _go_framework(source, framework_fallback)
    prefixes = _go_group_prefixes(source)
    routes: list[ApiRouteFact] = []
    for match in GIN_ROUTE_RE.finditer(source):
        path = _join_paths(prefixes.get(match.group("receiver"), ""), match.group("path"))
        method = match.group("method").upper()
        line = _line_for_offset(source, match.start())
        routes.append(
            ApiRouteFact(
                method=method,
                path=path,
                handler=match.group("handler"),
                framework=framework,
                kind=f"go-{framework}-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
            )
        )
    return routes


def _extract_dart_simple_server_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    if "router." not in source or "HttpRequest" not in source:
        return []
    api_routes = dart_api_route_map(root)
    routes: list[ApiRouteFact] = []
    for match in DART_SIMPLE_SERVER_ROUTE_RE.finditer(source):
        target = match.group("target").strip()
        path = _dart_simple_server_path(target, api_routes)
        if not path:
            continue
        line = _line_for_offset(source, match.start())
        routes.append(
            ApiRouteFact(
                method=match.group("method").upper(),
                path=path,
                handler=_dart_simple_server_handler(source, match.end()),
                framework="dart",
                kind="dart-simple-server-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
            )
        )
    return _dedupe_routes(routes)


def _dart_simple_server_path(target: str, api_routes: dict[tuple[str, str], str]) -> str | None:
    if target.startswith(("'", '"')):
        return _ensure_slash(target.strip("'\""))
    match = re.fullmatch(r"ApiRoute\.(?P<name>[A-Za-z_]\w*)\.(?P<version>v[12])", target)
    if not match:
        return None
    return api_routes.get((match.group("name"), match.group("version")))


def _dart_simple_server_handler(source: str, offset: int) -> str:
    window = source[offset : min(len(source), offset + 500)]
    match = re.search(r"\breturn\s+(?:await\s+)?(?P<handler>[_A-Za-z]\w*)\s*\(", window)
    return match.group("handler") if match else "inline-handler"


def _extract_vapor_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    if "Vapor" not in source and "APICollection" not in source and ".init(method:" not in source and ".on(" not in source:
        return []
    routes: list[ApiRouteFact] = []
    for match in VAPOR_API_COLLECTION_RE.finditer(source):
        method = match.group("method").upper()
        path = _vapor_path_from_components(match.group("paths"))
        line = _line_for_offset(source, match.start())
        routes.append(
            ApiRouteFact(
                method=method,
                path=path,
                handler=match.group("handler"),
                framework="vapor",
                kind="vapor-api-collection-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                parameters=_vapor_route_parameters(path, file_fact.path, line),
                request_body="content" if method in {"POST", "PUT", "PATCH"} else None,
                response_type="Response",
            )
        )
    for match in VAPOR_DIRECT_ROUTE_RE.finditer(source):
        method = match.group("method").upper()
        path = _vapor_path_from_args(match.group("args") or "")
        line = _line_for_offset(source, match.start())
        routes.append(
            ApiRouteFact(
                method=method,
                path=path,
                handler=_vapor_inline_handler(source, match.end()),
                framework="vapor",
                kind="vapor-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                parameters=_vapor_route_parameters(path, file_fact.path, line),
                request_body="content" if method in {"POST", "PUT", "PATCH"} else None,
            )
        )
    for match in VAPOR_ON_ROUTE_RE.finditer(source):
        method = match.group("method").upper()
        path = _vapor_path_from_args(match.group("args") or "")
        line = _line_for_offset(source, match.start())
        routes.append(
            ApiRouteFact(
                method=method,
                path=path,
                handler=match.group("handler") or _vapor_inline_handler(source, match.end()),
                framework="vapor",
                kind="vapor-on-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                parameters=_vapor_route_parameters(path, file_fact.path, line),
                request_body="content" if method in {"POST", "PUT", "PATCH"} else None,
            )
        )
    return _dedupe_routes(routes)


def _vapor_path_from_components(source: str) -> str:
    parts = _vapor_path_parts(source)
    return "/" + "/".join(part.strip("/") for part in parts if part.strip("/")) if parts else "/"


def _vapor_path_from_args(source: str) -> str:
    return _vapor_path_from_components(source)


def _vapor_path_parts(source: str) -> list[str]:
    parts: list[str] = []
    for match in re.finditer(r"\.(?P<kind>constant|parameter)\(\s*['\"](?P<value>[^'\"]+)['\"]\s*\)", source):
        value = match.group("value").strip("/")
        parts.append(f":{value}" if match.group("kind") == "parameter" and not value.startswith(":") else value)
    if parts:
        return parts
    for value in re.findall(r"['\"]([^'\"]+)['\"]", source):
        cleaned = value.strip().strip("/")
        if cleaned:
            parts.append(cleaned)
    return parts


def _vapor_inline_handler(source: str, offset: int) -> str:
    window = source[offset : min(len(source), offset + 500)]
    match = re.search(r"\b(?:try\s+)?(?P<handler>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)\s*\(", window)
    return match.group("handler") if match else "inline-handler"


def _vapor_route_parameters(path: str, file_path: str, line: int) -> list[RequestParamFact]:
    return [
        RequestParamFact(
            name=name,
            source="path",
            type=None,
            required=True,
            evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
        )
        for name in re.findall(r":([A-Za-z_]\w*)", path)
    ]


def _extract_go_mounted_routes(root: Path, files: list[FileFact], framework_fallback: str | None = None) -> list[ApiRouteFact]:
    templates: dict[str, list[ApiRouteFact]] = {}
    sources: dict[str, str] = {}
    for file_fact in files:
        source = _read(root, file_fact)
        sources[file_fact.path] = source
        for function_name, routes in _go_registration_route_templates(file_fact, source, framework_fallback).items():
            templates.setdefault(function_name, []).extend(routes)
    if not templates:
        return []

    mounted: list[ApiRouteFact] = []
    for file_fact in files:
        source = sources.get(file_fact.path) or _read(root, file_fact)
        prefixes = _go_group_prefixes(source)
        for match in GO_GIN_MOUNT_GROUP_CALL_RE.finditer(source):
            function_name = match.group("name")
            if function_name not in templates:
                continue
            prefix = _join_paths(prefixes.get(match.group("receiver"), ""), match.group("path"))
            mounted.extend(
                _go_mount_templates(
                    templates[function_name],
                    prefix,
                    file_fact.path,
                    _line_for_offset(source, match.start()),
                    function_name,
                )
            )
        for match in GO_GIN_MOUNT_VAR_CALL_RE.finditer(source):
            function_name = match.group("name")
            group_name = match.group("group")
            if function_name not in templates or group_name not in prefixes:
                continue
            mounted.extend(
                _go_mount_templates(
                    templates[function_name],
                    prefixes[group_name],
                    file_fact.path,
                    _line_for_offset(source, match.start()),
                    function_name,
                )
            )
    return _dedupe_routes(mounted)


def _go_registration_route_templates(
    file_fact: FileFact,
    source: str,
    framework_fallback: str | None = None,
) -> dict[str, list[ApiRouteFact]]:
    result: dict[str, list[ApiRouteFact]] = {}
    framework = _go_framework(source, framework_fallback)
    for function_match in GO_FUNC_RE.finditer(source):
        group_params = {
            match.group("name")
            for match in GO_GIN_GROUP_PARAM_RE.finditer(function_match.group("params"))
        }
        if not group_params:
            continue
        body_start = function_match.end() - 1
        body_end = _find_matching_brace(source, body_start)
        if body_end is None:
            continue
        body = source[body_start:body_end]
        prefixes = _go_group_prefixes(body)
        receivers = group_params | set(prefixes)
        routes: list[ApiRouteFact] = []
        for route_match in GIN_ROUTE_RE.finditer(body):
            if route_match.group("receiver") not in receivers:
                continue
            absolute_offset = body_start + route_match.start()
            route_path = _join_paths(prefixes.get(route_match.group("receiver"), ""), route_match.group("path"))
            routes.append(
                ApiRouteFact(
                    method=route_match.group("method").upper(),
                    path=route_path,
                    handler=route_match.group("handler"),
                    framework=framework,
                    kind=f"go-{framework}-registration-route",
                    evidence=Evidence(
                        file=file_fact.path,
                        kind="backend-route",
                        line_start=_line_for_offset(source, absolute_offset),
                        line_end=_line_for_offset(source, absolute_offset),
                    ),
                )
            )
        if routes:
            result[function_match.group("name")] = routes
    return result


def _go_group_prefixes(source: str) -> dict[str, str]:
    prefixes: dict[str, str] = {}
    for match in GIN_GROUP_RE.finditer(source):
        parent_prefix = prefixes.get(match.group("parent"), "")
        prefixes[match.group("name")] = _join_paths(parent_prefix, match.group("prefix"))
    return prefixes


def _go_mount_templates(
    templates: list[ApiRouteFact],
    prefix: str,
    mount_file: str,
    mount_line: int,
    function_name: str,
) -> list[ApiRouteFact]:
    routes: list[ApiRouteFact] = []
    for template in templates:
        routes.append(
            ApiRouteFact(
                method=template.method,
                path=_join_paths(prefix, template.path),
                handler=template.handler,
                framework=template.framework,
                kind=f"go-{template.framework}-mounted-route",
                evidence=Evidence(
                    file=mount_file,
                    kind="backend-route",
                    line_start=mount_line,
                    line_end=mount_line,
                    note=(
                        f"Mounted {function_name}; route template from "
                        f"{template.evidence.file}:{template.evidence.line_start or 1}"
                    ),
                ),
            )
        )
    return routes


def _replace_go_relative_registration_routes(
    routes: list[ApiRouteFact],
    mounted_routes: list[ApiRouteFact],
) -> list[ApiRouteFact]:
    mounted_keys = {
        (route.method, route.handler, route.framework)
        for route in mounted_routes
        if route.handler
    }
    if not mounted_keys:
        return routes
    result: list[ApiRouteFact] = []
    for route in routes:
        key = (route.method, route.handler, route.framework)
        if route.kind.startswith("go-") and route.handler and key in mounted_keys:
            continue
        result.append(route)
    return result


def _extract_slim_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    if not _looks_like_slim_source(source):
        return []
    imports = _php_use_imports(source)
    groups = _slim_route_groups(source)
    routes: list[ApiRouteFact] = []
    for offset, method, args in _slim_route_calls(source):
        parts = _split_top_level_commas(args)
        if len(parts) < 2:
            continue
        if method == "map":
            methods = _slim_map_methods(parts[0])
            path_expr = parts[1]
            handler_expr = parts[2] if len(parts) > 2 else ""
        else:
            methods = ["ANY"] if method == "any" else [method.upper()]
            path_expr = parts[0]
            handler_expr = parts[1]
        raw_path = _quoted_php_literal(path_expr.strip())
        if raw_path is None:
            continue
        prefix = _slim_prefix_for_offset(groups, offset)
        path = _join_paths(prefix, _slim_route_path(raw_path))
        handler = _slim_handler(handler_expr, imports)
        line = _line_for_offset(source, offset)
        for route_method in methods:
            routes.append(
                ApiRouteFact(
                    method=route_method,
                    path=path,
                    handler=handler,
                    framework="slim",
                    kind="slim-route",
                    parameters=_slim_path_params(path, file_fact.path, line),
                    evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                )
            )
    return _dedupe_routes(routes)


def _looks_like_slim_source(source: str) -> bool:
    lowered = source.lower()
    return (
        "slim\\app" in lowered
        or "slim\\factory\\appfactory" in lowered
        or "slim\\http\\request" in lowered
        or re.search(r"\$(?:app|this)->(?:group|get|post|put|patch|delete|options|any|map)\s*\(", source) is not None
    )


def _slim_route_calls(source: str) -> list[tuple[int, str, str]]:
    calls: list[tuple[int, str, str]] = []
    for match in re.finditer(r"\$(?:app|this)->(?P<method>get|post|put|patch|delete|options|any|map)\s*\(", source, re.IGNORECASE):
        method = match.group("method").lower()
        if method == "group":
            continue
        open_index = source.find("(", match.start())
        close_index = _find_matching_php_delimiter(source, open_index, "(", ")")
        if close_index is None:
            continue
        calls.append((match.start(), method, source[open_index + 1 : close_index]))
    return calls


def _slim_route_groups(source: str) -> list[tuple[int, int, str]]:
    groups: list[tuple[int, int, str]] = []
    for match in re.finditer(r"\$(?:app|this)->group\s*\(", source, re.IGNORECASE):
        open_index = source.find("(", match.start())
        close_index = _find_matching_php_delimiter(source, open_index, "(", ")")
        if close_index is None:
            continue
        args = source[open_index + 1 : close_index]
        parts = _split_top_level_commas(args)
        if not parts:
            continue
        prefix = _quoted_php_literal(parts[0].strip())
        if prefix is None:
            continue
        groups.append((match.start(), close_index, _slim_route_path(prefix)))
    return groups


def _slim_prefix_for_offset(groups: list[tuple[int, int, str]], offset: int) -> str:
    prefixes = [prefix for start, end, prefix in groups if start <= offset <= end]
    result = ""
    for prefix in prefixes:
        result = _join_paths(result, prefix)
    return result


def _slim_map_methods(expr: str) -> list[str]:
    methods = re.findall(r"['\"]([A-Za-z]+)['\"]", expr)
    return _dedupe([method.upper() for method in methods]) or ["ANY"]


def _slim_route_path(path: str) -> str:
    cleaned = path.strip()
    cleaned = re.sub(r"\[\s*([^\]]+)\s*\]", r"\1", cleaned)
    cleaned = re.sub(r":([A-Za-z_]\w*)", r"{\1}", cleaned)
    return _ensure_slash(cleaned)


def _slim_handler(expr: str, imports: dict[str, str]) -> str | None:
    if re.search(r"\bfunction\s*\(", expr) or re.search(r"\bfn\s*\(", expr):
        return "closure"
    class_method = re.search(r"(?P<class>[A-Za-z_\\][\w\\]*)::class\s*\.\s*['\"]:(?P<method>[A-Za-z_]\w*)['\"]", expr)
    if class_method:
        class_name = class_method.group("class").strip("\\")
        return f"{imports.get(class_name, class_name)}:{class_method.group('method')}"
    array_handler = re.search(r"\[\s*(?P<class>[A-Za-z_\\][\w\\]*)::class\s*,\s*['\"](?P<method>[A-Za-z_]\w*)['\"]", expr)
    if array_handler:
        class_name = array_handler.group("class").strip("\\")
        return f"{imports.get(class_name, class_name)}:{array_handler.group('method')}"
    invokable = re.search(r"(?P<class>[A-Za-z_\\][\w\\]*)::class", expr)
    if invokable:
        class_name = invokable.group("class").strip("\\")
        return imports.get(class_name, class_name)
    string_handler = _quoted_php_literal(expr.strip())
    if string_handler:
        return string_handler
    return None


def _php_use_imports(source: str) -> dict[str, str]:
    imports: dict[str, str] = {}
    for match in re.finditer(r"^\s*use\s+(?P<name>[A-Za-z_\\][\w\\]*)(?:\s+as\s+(?P<alias>[A-Za-z_]\w*))?\s*;", source, re.MULTILINE):
        full_name = match.group("name").strip("\\")
        alias = match.group("alias") or full_name.rsplit("\\", 1)[-1]
        imports[alias] = full_name
    return imports


def _slim_path_params(path: str, file_path: str, line: int) -> list[RequestParamFact]:
    return [
        RequestParamFact(
            name=name.strip("*"),
            source="path",
            type=None,
            required=True,
            evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
        )
        for name in re.findall(r"\{([^}]+)\}", path)
        if name.strip("*")
    ]


def _extract_laravel_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    normalized = file_fact.path.replace("\\", "/").lower()
    if "routes/" not in f"/{normalized}" and "/app/http/controllers/" not in f"/{normalized}":
        return []
    source = _read(root, file_fact)
    file_prefix = _laravel_file_prefix(root, file_fact.path)
    groups = _laravel_route_groups(source)
    routes: list[ApiRouteFact] = []
    for match in LARAVEL_MATCH_ROUTE_RE.finditer(source):
        route_prefix = _join_paths(file_prefix, _laravel_prefix_for_offset(groups, match.start()))
        name_prefix = _laravel_name_prefix_for_offset(groups, match.start())
        path = _join_paths(route_prefix, match.group("path"))
        handler = _laravel_handler_from_args(match.group("args"))
        route_tail = _php_statement_tail(source, match.end())
        route_name = _join_laravel_route_names(name_prefix, _laravel_route_name(match.group("args") + route_tail))
        line = _line_for_offset(source, match.start())
        for method in _laravel_match_methods(match.group("methods")):
            routes.append(_laravel_route(file_fact.path, line, method, path, handler, "laravel-route", route_name))
    for match in LARAVEL_ROUTE_RE.finditer(source):
        raw_method = match.group("method")
        route_prefix = _join_paths(file_prefix, _laravel_prefix_for_offset(groups, match.start()))
        name_prefix = _laravel_name_prefix_for_offset(groups, match.start())
        raw_path = match.group("path")
        handler = _laravel_handler_from_args(match.group("args"))
        route_tail = _php_statement_tail(source, match.end())
        line = _line_for_offset(source, match.start())
        if raw_method.lower() in {"resource", "apiresource"}:
            routes.extend(
                _laravel_resource_routes(
                    file_fact.path,
                    line,
                    route_prefix,
                    raw_path,
                    handler,
                    match.group("args") + route_tail,
                    name_prefix,
                    api_only=raw_method.lower() == "apiresource",
                )
            )
            continue
        method = "ANY" if raw_method.lower() == "any" else raw_method.upper()
        route_name = _join_laravel_route_names(name_prefix, _laravel_route_name(match.group("args") + route_tail))
        routes.append(_laravel_route(file_fact.path, line, method, _join_paths(route_prefix, raw_path), handler, "laravel-route", route_name))
    return routes


def _laravel_route(
    file_path: str,
    line: int,
    method: str,
    path: str,
    handler: str | None,
    kind: str,
    route_name: str | None = None,
) -> ApiRouteFact:
    normalized_path = _ensure_slash(path)
    return ApiRouteFact(
        method=method,
        path=normalized_path,
        handler=handler,
        framework="laravel",
        kind=kind,
        evidence=Evidence(
            file=file_path,
            kind="backend-route",
            line_start=line,
            line_end=line,
            note=f"laravel-route-name:{route_name}" if route_name else None,
        ),
        parameters=_laravel_path_parameters(normalized_path, file_path, line),
        request_body="request" if method in {"POST", "PUT", "PATCH"} else None,
    )


def _laravel_route_groups(source: str) -> list[tuple[int, int, str, str]]:
    groups: list[tuple[int, int, str, str]] = []
    for match in re.finditer(r"\bRoute::group\s*\(", source):
        open_index = source.find("(", match.start())
        brace_index = source.find("{", open_index, open_index + 500)
        if brace_index < 0:
            continue
        end = _find_matching_code_brace(source, brace_index)
        if end is None:
            continue
        head = source[open_index + 1 : brace_index]
        prefix, name_prefix = _laravel_group_attrs_from_group_head(head)
        if prefix or name_prefix:
            groups.append((brace_index, end, prefix, name_prefix))
    for match in re.finditer(r"->group\s*\(", source):
        statement_start = source.rfind(";", 0, match.start()) + 1
        route_start = source.find("Route::", statement_start, match.start())
        if route_start < 0:
            continue
        chain = source[route_start : match.end()]
        prefix, name_prefix = _laravel_group_attrs_from_fluent_chain(chain)
        if not prefix and not name_prefix:
            continue
        open_index = match.end() - 1
        brace_index = source.find("{", open_index, open_index + 500)
        if brace_index < 0:
            continue
        end = _find_matching_code_brace(source, brace_index)
        if end is not None:
            groups.append((brace_index, end, prefix, name_prefix))
    return sorted(set(groups), key=lambda item: item[0])


def _laravel_prefix_from_group_head(source: str) -> str:
    return _laravel_group_attrs_from_group_head(source)[0]


def _laravel_group_attrs_from_group_head(source: str) -> tuple[str, str]:
    prefix = ""
    name_prefix = ""
    prefix_match = re.search(r"['\"]prefix['\"]\s*=>\s*['\"](?P<prefix>[^'\"]+)['\"]", source)
    if prefix_match:
        prefix = prefix_match.group("prefix")
    name_match = re.search(r"['\"](?:as|name)['\"]\s*=>\s*['\"](?P<name>[^'\"]+)['\"]", source)
    if name_match:
        name_prefix = name_match.group("name")
    return prefix, name_prefix


def _laravel_prefix_from_fluent_chain(source: str) -> str:
    return _laravel_group_attrs_from_fluent_chain(source)[0]


def _laravel_group_attrs_from_fluent_chain(source: str) -> tuple[str, str]:
    prefix = ""
    name_prefix = ""
    for match in re.finditer(r"(?:Route::|->)prefix\(\s*['\"](?P<prefix>[^'\"]+)['\"]\s*\)", source):
        prefix = _join_paths(prefix, match.group("prefix"))
    for match in re.finditer(r"(?:Route::|->)(?:as|name)\(\s*['\"](?P<name>[^'\"]+)['\"]\s*\)", source):
        name_prefix = _join_laravel_route_names(name_prefix, match.group("name")) or ""
    return prefix, name_prefix


def _laravel_prefix_for_offset(groups: list[tuple[int, int, str, str]], offset: int) -> str:
    prefix = ""
    for start, end, value, _name_prefix in groups:
        if start < offset < end:
            prefix = _join_paths(prefix, value)
    return prefix


def _laravel_name_prefix_for_offset(groups: list[tuple[int, int, str, str]], offset: int) -> str:
    prefix = ""
    for start, end, _path_prefix, value in groups:
        if start < offset < end:
            prefix = _join_laravel_route_names(prefix, value) or ""
    return prefix


def _join_laravel_route_names(prefix: str | None, name: str | None) -> str | None:
    if not name:
        return None
    if not prefix:
        return name.strip(".")
    cleaned_prefix = prefix.strip(".")
    cleaned_name = name.strip(".")
    if not cleaned_prefix:
        return cleaned_name
    if not cleaned_name:
        return cleaned_prefix
    return f"{cleaned_prefix}.{cleaned_name}"


def _laravel_handler_from_args(args: str) -> str | None:
    array_handler = re.search(
        r"\[\s*(?P<class>[A-Za-z_\\][\w\\]*)::class\s*,\s*['\"](?P<method>[A-Za-z_]\w*)['\"]",
        args,
    )
    if array_handler:
        return f"{array_handler.group('class')}@{array_handler.group('method')}"
    invokable = re.search(r"(?P<class>[A-Za-z_\\][\w\\]*)::class", args)
    if invokable:
        return invokable.group("class")
    return (
        _first_match(args, r"([A-Za-z_\\][\w\\]+@[A-Za-z_]\w*)")
        or _first_match(args, r"['\"]([A-Za-z_\\][\w\\]+)['\"]")
    )


def _php_statement_tail(source: str, offset: int) -> str:
    end = source.find(";", offset)
    if end < 0:
        return ""
    return source[offset:end]


def _laravel_route_name(source: str) -> str | None:
    fluent = re.search(r"->name\(\s*['\"](?P<name>[^'\"]+)['\"]\s*\)", source)
    if fluent:
        return fluent.group("name")
    array_name = re.search(r"['\"](?:as|name)['\"]\s*=>\s*['\"](?P<name>[^'\"]+)['\"]", source)
    if array_name:
        return array_name.group("name")
    return None


def _laravel_match_methods(source: str) -> list[str]:
    methods = [method.upper() for method in re.findall(r"['\"]([A-Za-z]+)['\"]", source)]
    return [method for method in methods if method in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}]


def _laravel_resource_routes(
    file_path: str,
    line: int,
    prefix: str,
    resource: str,
    handler: str | None,
    args: str,
    name_prefix: str,
    *,
    api_only: bool,
) -> list[ApiRouteFact]:
    base = _laravel_resource_base(resource)
    parameter = _laravel_resource_parameter(base)
    item = _join_paths(base, f"{{{parameter}}}")
    action_templates = {
        "index": [("GET", base)],
        "create": [("GET", _join_paths(base, "create"))],
        "store": [("POST", base)],
        "show": [("GET", item)],
        "edit": [("GET", _join_paths(item, "edit"))],
        "update": [("PUT", item), ("PATCH", item)],
        "destroy": [("DELETE", item)],
    }
    actions = _laravel_resource_actions(args, api_only)
    kind = "laravel-api-resource-route" if api_only else "laravel-resource-route"
    routes: list[ApiRouteFact] = []
    for action in actions:
        for method, path in action_templates.get(action, []):
            route_name = _join_laravel_route_names(
                name_prefix,
                _laravel_resource_route_name(resource, action),
            )
            routes.append(
                _laravel_route(
                    file_path,
                    line,
                    method,
                    _join_paths(prefix, path),
                    f"{handler}@{action}" if handler and "@" not in handler else handler,
                    kind,
                    route_name,
                )
            )
    return routes


def _laravel_resource_route_name(resource: str, action: str) -> str:
    name_parts = [
        _laravel_resource_base(part)
        for part in resource.strip("/").split("/")
        if part and not part.startswith("{")
    ]
    base = ".".join(part.strip(".") for part in name_parts if part.strip("."))
    return f"{base}.{action}" if base else action


def _laravel_resource_actions(args: str, api_only: bool) -> list[str]:
    default_actions = ["index", "store", "show", "update", "destroy"] if api_only else [
        "index",
        "create",
        "store",
        "show",
        "edit",
        "update",
        "destroy",
    ]
    only = _laravel_option_items(args, "only")
    excepted = set(_laravel_option_items(args, "except"))
    actions = [action for action in default_actions if not only or action in only]
    return [action for action in actions if action not in excepted]


def _laravel_option_items(args: str, option: str) -> list[str]:
    match = re.search(
        rf"['\"]{re.escape(option)}['\"]\s*=>\s*(?P<value>\[[\s\S]*?\]|array\s*\([\s\S]*?\)|['\"][^'\"]+['\"])",
        args,
        re.IGNORECASE,
    )
    if not match:
        match = re.search(
            rf"->{re.escape(option)}\s*\(\s*(?P<value>\[[\s\S]*?\]|array\s*\([\s\S]*?\)|['\"][^'\"]+['\"])",
            args,
            re.IGNORECASE,
        )
    if not match:
        return []
    return re.findall(r"['\"]([A-Za-z_]\w*)['\"]", match.group("value"))


def _laravel_path_parameters(path: str, file_path: str, line: int) -> list[RequestParamFact]:
    params: list[RequestParamFact] = []
    for raw_name in re.findall(r"\{([^}:]+)(?::[^}]*)?\}", path):
        name = raw_name.rstrip("?")
        if not name:
            continue
        params.append(
            RequestParamFact(
                name=name,
                source="path",
                type=None,
                required=not raw_name.endswith("?"),
                evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
            )
        )
    return params


def _laravel_resource_base(resource: str) -> str:
    value = resource.strip("/")
    if "." not in value:
        return value
    pieces: list[str] = []
    parts = [part for part in value.split(".") if part]
    for index, part in enumerate(parts):
        pieces.append(part)
        if index < len(parts) - 1:
            pieces.append(f"{{{_singular_route_token(part)}}}")
    return "/".join(pieces)


def _laravel_resource_parameter(resource_base: str) -> str:
    for part in reversed([part for part in resource_base.split("/") if part]):
        if part.startswith("{") and part.endswith("}"):
            continue
        return _singular_route_token(part)
    return "id"


def _singular_route_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip("{}")).strip("_")
    if token.endswith("ies"):
        return token[:-3] + "y"
    if token.endswith(("ches", "shes", "xes", "ses")):
        return token[:-2]
    if token.endswith("s") and len(token) > 1:
        return token[:-1]
    return token or "id"


def _laravel_file_prefix(root: Path, file_path: str) -> str:
    normalized = file_path.replace("\\", "/")
    prefixes = _laravel_file_prefixes(str(root))
    prefix = prefixes.get(normalized)
    if prefix is None and normalized == "routes/api.php":
        prefix = "api"
    return _ensure_slash(prefix) if prefix else ""


@lru_cache(maxsize=16)
def _laravel_file_prefixes(root: str) -> dict[str, str]:
    root_path = Path(root)
    prefixes: dict[str, str] = {}
    for provider in _laravel_routing_config_paths(root_path):
        try:
            source = provider.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        prefixes.update(_laravel_bootstrap_routing_prefixes(source))
        prefixes.update(_laravel_required_route_prefixes(source))
        for match in re.finditer(r"->group\(\s*base_path\(\s*['\"](?P<file>routes/[^'\"]+)['\"]\s*\)\s*\)", source):
            prefix = _laravel_fluent_prefix_before(source, match.start(), root_path)
            if prefix is not None:
                prefixes[match.group("file").replace("\\", "/")] = prefix
    return prefixes


def _laravel_routing_config_paths(root: Path) -> list[Path]:
    paths: set[Path] = set()
    for directory in (
        root / "app" / "Providers",
        root / "app" / "App" / "Providers",
    ):
        if directory.exists():
            paths.update(path for path in directory.glob("*.php") if path.is_file())
    app_dir = root / "app"
    if app_dir.exists():
        paths.update(path for path in app_dir.rglob("*RouteServiceProvider*.php") if path.is_file())
    bootstrap = root / "bootstrap" / "app.php"
    if bootstrap.exists():
        paths.add(bootstrap)
    return sorted(paths)


def _laravel_required_route_prefixes(source: str) -> dict[str, str]:
    prefixes: dict[str, str] = {}
    for match in re.finditer(r"\bRoute::group\s*\(", source):
        open_index = source.find("(", match.start())
        close_index = _find_matching_paren(source, open_index)
        if close_index is None:
            continue
        body = source[open_index + 1 : close_index]
        for require_match in re.finditer(
            r"\brequire(?:_once)?\s+base_path\(\s*['\"](?P<file>routes/[^'\"]+)['\"]\s*\)",
            body,
        ):
            head = body[: require_match.start()]
            prefixes[require_match.group("file").replace("\\", "/")] = _laravel_prefix_from_group_head(head)
    return prefixes


def _laravel_bootstrap_routing_prefixes(source: str) -> dict[str, str]:
    prefixes: dict[str, str] = {}
    for match in re.finditer(r"\bwithRouting\s*\(", source):
        open_index = source.find("(", match.start())
        close_index = _find_matching_paren(source, open_index)
        if close_index is None:
            continue
        body = source[open_index + 1 : close_index]
        api_prefix = _laravel_with_routing_api_prefix(body)
        for route_match in re.finditer(
            r"\b(?P<kind>web|api)\s*:\s*(?:__DIR__\s*\.\s*)?['\"][^'\"]*(?P<file>routes/[^'\"]+)['\"]",
            body,
        ):
            kind = route_match.group("kind")
            prefixes[route_match.group("file").replace("\\", "/")] = api_prefix if kind == "api" else ""
    return prefixes


def _laravel_with_routing_api_prefix(body: str) -> str:
    match = re.search(r"\bapiPrefix\s*:\s*['\"](?P<prefix>[^'\"]*)['\"]", body)
    return match.group("prefix") if match else "api"


def _laravel_fluent_prefix_before(source: str, offset: int, root: Path) -> str | None:
    window = source[max(0, offset - 500) : offset]
    matches = list(re.finditer(r"(?:->|::)prefix\(\s*(?P<expr>config\([^)]+\)|[^)]+)\)", window))
    if not matches:
        return ""
    expr = matches[-1].group("expr").strip()
    literal = _quoted_php_literal(expr)
    if literal is not None:
        return literal
    config_match = re.search(r"config\(\s*['\"](?P<key>[^'\"]+)['\"]\s*\)", expr)
    if config_match:
        return _laravel_config_default(root, config_match.group("key")) or f"dynamic:{config_match.group('key')}"
    return None


def _quoted_php_literal(expr: str) -> str | None:
    match = re.match(r"['\"](?P<value>[^'\"]*)['\"]", expr.strip())
    return match.group("value") if match else None


def _laravel_config_default(root: Path, key: str) -> str | None:
    parts = key.split(".")
    if len(parts) != 2:
        return None
    config_file = root / "config" / f"{parts[0]}.php"
    try:
        source = config_file.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    pattern = rf"['\"]{re.escape(parts[1])}['\"]\s*=>\s*env\(\s*['\"][^'\"]+['\"]\s*,\s*['\"](?P<default>[^'\"]+)['\"]\s*\)"
    match = re.search(pattern, source)
    return match.group("default") if match else None


def _find_matching_code_brace(source: str, open_index: int) -> int | None:
    depth = 0
    quote: str | None = None
    escape = False
    line_comment = False
    block_comment = False
    index = open_index
    while index < len(source):
        char = source[index]
        nxt = source[index + 1] if index + 1 < len(source) else ""
        if line_comment:
            if char in "\r\n":
                line_comment = False
            index += 1
            continue
        if block_comment:
            if char == "*" and nxt == "/":
                block_comment = False
                index += 2
                continue
            index += 1
            continue
        if quote:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char == '"':
            quote = char
        elif char == "/" and nxt == "/":
            line_comment = True
            index += 1
        elif char == "/" and nxt == "*":
            block_comment = True
            index += 1
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def _extract_wordpress_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    if "register_rest_route" not in source and "add_rewrite_rule" not in source:
        return []
    routes: list[ApiRouteFact] = []
    context = _wordpress_route_context(file_fact.path, source)
    for match, args in _wordpress_rest_calls(source):
        parts = _split_top_level_commas(args)
        if len(parts) < 3:
            continue
        namespace = _wordpress_resolve_php_expr(parts[0], context)
        route_path = _wordpress_resolve_php_expr(parts[1], context)
        if not namespace or not route_path:
            continue
        line = _line_for_offset(source, match.start())
        path = _wordpress_rest_path(namespace, route_path)
        for method, handler in _wordpress_method_handlers(parts[2]):
            routes.append(
                ApiRouteFact(
                    method=method,
                    path=path,
                    handler=handler,
                    framework="wordpress",
                    kind="wordpress-rest-route",
                    evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                )
            )
    for match, args in _wordpress_rewrite_rule_calls(source):
        parts = _split_top_level_commas(args)
        if len(parts) < 2:
            continue
        rewrite_pattern = _wordpress_resolve_php_expr(parts[0], context)
        rewrite_target = _wordpress_resolve_php_expr(parts[1], context)
        if not rewrite_pattern:
            continue
        line = _line_for_offset(source, match.start())
        routes.append(
            ApiRouteFact(
                method="ANY",
                path=_wordpress_rewrite_path(rewrite_pattern),
                handler=f"rewrite:{rewrite_target}" if rewrite_target else None,
                framework="wordpress",
                kind="wordpress-rewrite-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
            )
        )
    return _dedupe_routes(routes)


def _wordpress_rest_calls(source: str) -> list[tuple[re.Match[str], str]]:
    calls: list[tuple[re.Match[str], str]] = []
    for match in WORDPRESS_REST_CALL_RE.finditer(source):
        open_index = source.find("(", match.start())
        if open_index < 0:
            continue
        close_index = _find_matching_wordpress_call_paren(source, open_index)
        if close_index is None:
            continue
        calls.append((match, source[open_index + 1 : close_index]))
    return calls


def _wordpress_rewrite_rule_calls(source: str) -> list[tuple[re.Match[str], str]]:
    calls: list[tuple[re.Match[str], str]] = []
    for match in WORDPRESS_REWRITE_CALL_RE.finditer(source):
        open_index = source.find("(", match.start())
        if open_index < 0:
            continue
        close_index = _find_matching_wordpress_call_paren(source, open_index)
        if close_index is None:
            continue
        calls.append((match, source[open_index + 1 : close_index]))
    return calls


def _wordpress_rewrite_path(pattern: str) -> str:
    cleaned = pattern.strip().strip("^").strip("$")
    cleaned = cleaned.replace("\\/", "/")
    cleaned = re.sub(r"/\?\s*$", "", cleaned)
    cleaned = re.sub(r"\(\?P<([A-Za-z_]\w*)>[^)]+\)", r"{\1}", cleaned)
    cleaned = re.sub(r"\([^)]*\)", "{param}", cleaned)
    cleaned = cleaned.replace("\\", "")
    cleaned = cleaned.rstrip("/")
    return _ensure_slash(cleaned)


def _wordpress_route_context(file_path: str, source: str) -> dict[str, str]:
    context = {match.group("name"): match.group("value") for match in WORDPRESS_PROPERTY_RE.finditer(source)}
    for match in WORDPRESS_CONST_RE.finditer(source):
        context[match.group("name")] = match.group("value")
    context.setdefault("namespace", _wordpress_namespace_from_path(file_path))
    if "rest_base" not in context:
        inferred = _wordpress_rest_base_from_path(file_path)
        if inferred:
            context["rest_base"] = inferred
    return context


def _wordpress_namespace_from_path(file_path: str) -> str:
    normalized = file_path.replace("\\", "/").lower()
    if "/version4/" in f"/{normalized}" or "/routes/v4/" in f"/{normalized}":
        return "wc/v4"
    if "/version3/" in f"/{normalized}":
        return "wc/v3"
    if "/version2/" in f"/{normalized}":
        return "wc/v2"
    if "/version1/" in f"/{normalized}":
        return "wc/v1"
    return ""


def _wordpress_rest_base_from_path(file_path: str) -> str | None:
    name = Path(file_path.replace("\\", "/")).name.lower()
    if not name.startswith("class-wc-rest-") or not name.endswith("-controller.php"):
        return None
    base = name.removeprefix("class-wc-rest-").removesuffix("-controller.php")
    base = re.sub(r"-v\d+$", "", base)
    return base or None


def _wordpress_resolve_php_expr(expr: str, context: dict[str, str]) -> str | None:
    parts = _split_php_concat(expr)
    if not parts:
        return None
    resolved: list[str] = []
    for part in parts:
        value = _wordpress_resolve_php_part(part, context)
        if value is None:
            return None
        resolved.append(value)
    return "".join(resolved)


def _wordpress_resolve_php_part(part: str, context: dict[str, str]) -> str | None:
    stripped = part.strip()
    literal = _quoted_php_literal(stripped)
    if literal is not None:
        return literal
    property_match = re.fullmatch(r"\$this->(?P<name>[A-Za-z_]\w*)", stripped)
    if property_match:
        return context.get(property_match.group("name"))
    const_match = re.fullmatch(r"(?:self|static)::(?P<name>[A-Z_]+)", stripped)
    if const_match:
        return context.get(const_match.group("name"))
    return None


def _split_php_concat(expr: str) -> list[str]:
    return _split_top_level(expr, ".")


def _split_top_level_commas(expr: str) -> list[str]:
    return _split_top_level(expr, ",")


def _split_top_level(expr: str, delimiter: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    quote: str | None = None
    escape = False
    for index, char in enumerate(expr):
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if quote:
            if char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            continue
        if char in "([{":
            depth += 1
            continue
        if char in ")]}":
            depth = max(0, depth - 1)
            continue
        if char == delimiter and depth == 0:
            parts.append(expr[start:index].strip())
            start = index + 1
    parts.append(expr[start:].strip())
    return [part for part in parts if part]


def _wordpress_rest_path(namespace: str, route_path: str) -> str:
    namespace = namespace.strip("/")
    route = re.split(r"(?<!\()\?", route_path, 1)[0].strip()
    route = re.sub(r"\(\?P<([A-Za-z_]\w*)>[^)]+\)", r"{\1}", route)
    route = re.sub(r":([A-Za-z_$][\w$]*)", r"{\1}", route)
    route = _ensure_slash(route)
    return _join_paths(f"/wp-json/{namespace}", route)


def _wordpress_callback(args: str) -> str | None:
    string_callback = _first_match(args, r"['\"]callback['\"]\s*=>\s*['\"]([^'\"]+)['\"]")
    if string_callback:
        return string_callback
    array_callback = _first_match(args, r"['\"]callback['\"]\s*=>\s*array\(\s*\$this\s*,\s*['\"]([^'\"]+)['\"]")
    if array_callback:
        return array_callback
    wrapped_callback = _first_match(args, r"['\"]callback['\"]\s*=>\s*\$this->[A-Za-z_]\w*\(\s*array\(\s*\$this\s*,\s*['\"]([^'\"]+)['\"]")
    return wrapped_callback


def _wordpress_method_handlers(args: str) -> list[tuple[str, str | None]]:
    pairs: list[tuple[str, str | None]] = []
    for body in _wordpress_array_bodies(args):
        if "methods" not in body or WORDPRESS_METHOD_RE.search(body) is None:
            continue
        if len(list(WORDPRESS_METHOD_RE.finditer(body))) > 1:
            continue
        handler = _wordpress_callback(body)
        for method in _wordpress_methods(body):
            pairs.append((method, handler))
    if not pairs:
        handler = _wordpress_callback(args)
        pairs = [(method, handler) for method in _wordpress_methods(args)]
    return _dedupe_wordpress_method_handlers(pairs)


def _dedupe_wordpress_method_handlers(pairs: list[tuple[str, str | None]]) -> list[tuple[str, str | None]]:
    result: list[tuple[str, str | None]] = []
    seen: set[tuple[str, str | None]] = set()
    for method, handler in pairs:
        key = (method, handler)
        if key in seen:
            continue
        seen.add(key)
        result.append(key)
    return result


def _wordpress_array_bodies(source: str) -> list[str]:
    bodies: list[str] = []
    for match in re.finditer(r"\barray\s*\(", source, re.IGNORECASE):
        open_index = source.find("(", match.start())
        if open_index < 0:
            continue
        close_index = _find_matching_wordpress_call_paren(source, open_index)
        if close_index is None:
            continue
        bodies.append(source[open_index + 1 : close_index])
    return bodies


def _extract_symfony_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    normalized = file_fact.path.replace("\\", "/").lower()
    if not normalized.startswith("src/controller/"):
        return []
    source = _read(root, file_fact)
    if "#[Route" not in source and "@Route(" not in source:
        return []
    routes: list[ApiRouteFact] = []
    routes.extend(_extract_symfony_attribute_routes(file_fact, source))
    routes.extend(_extract_symfony_doc_routes(file_fact, source))
    controller_prefix = _symfony_controller_import_prefix(root)
    if controller_prefix:
        routes = [replace(route, path=_join_paths(controller_prefix, route.path)) for route in routes]
    return _dedupe_routes(routes)


def _extract_symfony_attribute_routes(file_fact: FileFact, source: str) -> list[ApiRouteFact]:
    class_prefix = ""
    class_match = SYMFONY_CLASS_RE.search(source)
    if class_match:
        class_prefix = _symfony_first_route_path(class_match.group("attrs"))
    routes: list[ApiRouteFact] = []
    for method_match in SYMFONY_METHOD_RE.finditer(source):
        attrs = method_match.group("attrs")
        for route_attr in SYMFONY_ROUTE_ATTR_RE.finditer(attrs):
            args = route_attr.group("args")
            path = _join_paths(class_prefix, _path_from_args(args, default="/"))
            methods = _symfony_methods(args)
            line = _line_for_offset(source, method_match.start("attrs") + route_attr.start())
            for method in methods:
                routes.append(
                    ApiRouteFact(
                        method=method,
                        path=path,
                        handler=method_match.group("name"),
                        framework="symfony",
                        kind="symfony-attribute-route",
                        evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                        class_prefix=class_prefix or None,
                    )
                )
    return routes


def _extract_symfony_doc_routes(file_fact: FileFact, source: str) -> list[ApiRouteFact]:
    routes: list[ApiRouteFact] = []
    for match in SYMFONY_DOC_ROUTE_RE.finditer(source):
        args = match.group("args")
        line = _line_for_offset(source, match.start())
        handler = _symfony_doc_handler_after(source, match.end())
        for method in _symfony_methods(args):
            routes.append(
                ApiRouteFact(
                    method=method,
                    path=_path_from_args(args, default="/"),
                    handler=handler,
                    framework="symfony",
                    kind="symfony-annotation-route",
                    evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                )
            )
    return routes


def _extract_symfony_yaml_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    normalized = file_fact.path.replace("\\", "/").lower()
    if not (normalized == "config/routes.yaml" or normalized == "config/routes.yml" or normalized.startswith("config/routes/")):
        return []
    source = _read(root, file_fact)
    if "path:" not in source or "controller:" not in source:
        return []
    routes: list[ApiRouteFact] = []
    lines = source.splitlines()
    for block_name, start, block in _yaml_top_level_blocks(lines):
        path, path_line = _yaml_block_scalar(block, "path", start)
        controller, _ = _yaml_block_scalar(block, "controller", start)
        if not path or not controller:
            continue
        methods = _symfony_yaml_methods(block)
        for method in methods:
            routes.append(
                ApiRouteFact(
                    method=method,
                    path=path,
                    handler=controller,
                    framework="symfony",
                    kind="symfony-yaml-route",
                    evidence=Evidence(
                        file=file_fact.path,
                        kind="backend-route",
                        line_start=path_line,
                        line_end=path_line,
                        note=block_name,
                    ),
                )
            )
    return routes


def _extract_yii_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    if "UrlRule::class" not in source and "yii\\rest\\UrlRule" not in source and "yii/rest/UrlRule" not in source:
        return []
    module_id = _yii_module_id(file_fact.path)
    routes: list[ApiRouteFact] = []
    rule_blocks = _yii_url_rule_blocks(source)
    mapped_actions_by_controller = _yii_mapped_actions_by_controller(rule_blocks, module_id)
    for offset, block in rule_blocks:
        prefix = _yii_scalar_value(block, "prefix", module_id) or module_id
        controllers = _yii_controller_aliases(block, module_id)
        if not controllers:
            continue
        only = set(_yii_string_list(block, "only"))
        except_actions = set(_yii_string_list(block, "except"))
        line = _line_for_offset(source, offset)
        explicit_patterns = _yii_route_patterns(block, "patterns")
        extra_patterns = _yii_route_patterns(block, "extraPatterns")
        pattern_entries = explicit_patterns + extra_patterns
        for url_name, controller in controllers:
            controller_actions = _yii_controller_action_names(root, controller)
            mapped_actions = {action for _, _, action in pattern_entries} | mapped_actions_by_controller.get(controller, set())
            for methods, template, action in pattern_entries:
                if only and action not in only:
                    continue
                if action in except_actions:
                    continue
                if controller_actions and action not in controller_actions:
                    continue
                routes.extend(_yii_pattern_routes(file_fact, line, prefix, url_name, controller, methods, template, action))
            if explicit_patterns:
                continue
            for methods, template, action in _yii_default_rest_patterns():
                if action in mapped_actions:
                    continue
                if only and action not in only:
                    continue
                if action in except_actions:
                    continue
                if controller_actions and action not in controller_actions:
                    continue
                routes.extend(_yii_pattern_routes(file_fact, line, prefix, url_name, controller, methods, template, action))
    return _dedupe_routes(routes)


def _yii_url_rule_blocks(source: str) -> list[tuple[int, str]]:
    blocks: list[tuple[int, str]] = []
    for match in re.finditer(r"(?:\\?yii\\rest\\UrlRule|UrlRule)::class", source):
        start = source.rfind("[", 0, match.start())
        if start < 0:
            continue
        end = _find_matching_php_delimiter(source, start, "[", "]")
        if end is None:
            continue
        blocks.append((start, source[start + 1 : end]))
    return blocks


def _yii_mapped_actions_by_controller(rule_blocks: list[tuple[int, str]], module_id: str) -> dict[str, set[str]]:
    mapped: dict[str, set[str]] = {}
    for _, block in rule_blocks:
        actions = {action for _, _, action in (_yii_route_patterns(block, "patterns") + _yii_route_patterns(block, "extraPatterns"))}
        if not actions:
            continue
        for _, controller in _yii_controller_aliases(block, module_id):
            mapped.setdefault(controller, set()).update(actions)
    return mapped


def _yii_module_id(path: str) -> str:
    normalized = path.replace("\\", "/")
    match = re.search(r"(?:^|/)modules/([^/]+)/", normalized)
    return match.group(1) if match else ""


def _yii_scalar_value(block: str, key: str, module_id: str) -> str | None:
    match = re.search(rf"['\"]{re.escape(key)}['\"]\s*=>\s*(?P<expr>[^,\n]+)", block)
    if not match:
        return None
    return _yii_resolve_php_expr(match.group("expr"), module_id)


def _yii_controller_aliases(block: str, module_id: str) -> list[tuple[str, str]]:
    controller_array = _yii_array_for_key(block, "controller")
    if controller_array:
        aliases: list[tuple[str, str]] = []
        for match in re.finditer(r"['\"](?P<alias>[^'\"]+)['\"]\s*=>\s*(?P<expr>[^,\n\]]+)", controller_array):
            controller = _yii_resolve_php_expr(match.group("expr"), module_id)
            if controller:
                aliases.append((match.group("alias"), controller))
        if aliases:
            return aliases
    controller = _yii_scalar_value(block, "controller", module_id)
    return [(controller, controller)] if controller else []


def _yii_route_patterns(block: str, key: str) -> list[tuple[list[str], str, str]]:
    body = _yii_array_for_key(block, key)
    if not body:
        return []
    patterns: list[tuple[list[str], str, str]] = []
    for match in re.finditer(r"['\"](?P<pattern>[^'\"]*)['\"]\s*=>\s*['\"](?P<action>[^'\"]+)['\"]", body):
        methods, template = _yii_pattern_methods_and_path(match.group("pattern"), match.group("action"))
        patterns.append((methods, template, match.group("action")))
    return patterns


def _yii_pattern_methods_and_path(pattern: str, action: str) -> tuple[list[str], str]:
    cleaned = " ".join(pattern.split())
    if not cleaned:
        return (_yii_action_methods(action), "")
    parts = cleaned.split(" ", 1)
    if re.fullmatch(r"[A-Za-z,]+", parts[0]):
        return (_dedupe([method.upper() for method in parts[0].split(",") if method]), parts[1] if len(parts) > 1 else "")
    return (_yii_action_methods(action), cleaned)


def _yii_action_methods(action: str) -> list[str]:
    return {
        "index": ["GET", "HEAD"],
        "view": ["GET", "HEAD"],
        "create": ["POST"],
        "update": ["PUT", "PATCH"],
        "delete": ["DELETE"],
        "options": ["OPTIONS"],
    }.get(action, ["ANY"])


def _yii_default_rest_patterns() -> list[tuple[list[str], str, str]]:
    return [
        (["GET", "HEAD"], "", "index"),
        (["POST"], "", "create"),
        (["GET", "HEAD"], "{id}", "view"),
        (["PUT", "PATCH"], "{id}", "update"),
        (["DELETE"], "{id}", "delete"),
        (["OPTIONS"], "", "options"),
        (["OPTIONS"], "{id}", "options"),
    ]


def _yii_pattern_routes(
    file_fact: FileFact,
    line: int,
    prefix: str,
    url_name: str,
    controller: str,
    methods: list[str],
    template: str,
    action: str,
) -> list[ApiRouteFact]:
    path = _join_paths(_ensure_slash(prefix) if prefix else "", _join_paths(_ensure_slash(url_name), _yii_template_path(template)))
    return [
        ApiRouteFact(
            method=method,
            path=path,
            handler=f"{controller}#{action}",
            framework="yii2",
            kind="yii-rest-url-rule",
            parameters=_yii_path_params(path, file_fact.path, line),
            evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
        )
        for method in methods
    ]


def _yii_template_path(template: str) -> str:
    if not template:
        return ""
    cleaned = template.strip().strip("/")
    cleaned = re.sub(r"<([A-Za-z_]\w*)>", r"{\1}", cleaned)
    return "/" + cleaned if cleaned else ""


def _yii_path_params(path: str, file_path: str, line: int) -> list[RequestParamFact]:
    return [
        RequestParamFact(
            name=name.strip("*"),
            source="path",
            type=None,
            required=True,
            evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
        )
        for name in re.findall(r"\{([^}]+)\}", path)
        if name.strip("*")
    ]


def _yii_array_for_key(block: str, key: str) -> str | None:
    match = re.search(rf"['\"]{re.escape(key)}['\"]\s*=>\s*\[", block)
    if not match:
        return None
    open_index = block.find("[", match.start())
    close_index = _find_matching_php_delimiter(block, open_index, "[", "]")
    if close_index is None:
        return None
    return block[open_index + 1 : close_index]


def _yii_string_list(block: str, key: str) -> list[str]:
    body = _yii_array_for_key(block, key)
    if not body:
        return []
    return _dedupe(re.findall(r"['\"]([^'\"]+)['\"]", body))


def _yii_resolve_php_expr(expr: str, module_id: str) -> str | None:
    parts = _split_php_concat(expr)
    if not parts:
        return None
    values: list[str] = []
    for part in parts:
        stripped = part.strip()
        literal = _quoted_php_literal(stripped)
        if literal is not None:
            values.append(literal)
        elif stripped == "$this->id":
            values.append(module_id)
        else:
            return None
    return "".join(values)


def _yii_controller_action_names(root: Path, controller: str) -> set[str]:
    path = _yii_controller_path(root, controller)
    if path is None or not path.exists():
        return set()
    source = path.read_text(encoding="utf-8-sig", errors="ignore")
    actions = {_camel_to_kebab(name) for name in re.findall(r"\bpublic\s+function\s+action([A-Z][A-Za-z0-9_]*)\s*\(", source)}
    actions.update(re.findall(r"['\"]([A-Za-z][A-Za-z0-9_-]*)['\"]\s*=>\s*(?:\[|[A-Za-z_\\]+::class)", source))
    lowered = source.lower()
    if "extends activecontroller" in lowered or "extends \\yii\\rest\\activecontroller" in lowered or "extends yii\\rest\\activecontroller" in lowered:
        actions.update({"index", "view", "create", "update", "delete", "options"})
    if "extends controller" in lowered or "extends \\yii\\rest\\controller" in lowered or "extends yii\\rest\\controller" in lowered or "optionsaction" in lowered:
        actions.add("options")
    return actions


def _yii_controller_path(root: Path, controller: str) -> Path | None:
    normalized = controller.strip("/").replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    if not parts:
        return None
    controller_name = "".join(_kebab_to_camel(part) for part in parts[-1].split("-")) + "Controller.php"
    if len(parts) >= 2:
        candidate = root / "modules" / parts[0] / "controllers" / controller_name
        if candidate.exists():
            return candidate
    candidate = root / "controllers" / controller_name
    if candidate.exists():
        return candidate
    return None


def _kebab_to_camel(value: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in re.split(r"[-_]", value) if part)


def _camel_to_kebab(value: str) -> str:
    return re.sub(r"(?<!^)([A-Z])", r"-\1", value).replace("_", "-").lower()


def _camel_to_snake(value: str) -> str:
    return re.sub(r"(?<!^)([A-Z])", r"_\1", value).replace("-", "_").lower()


def _extract_drupal_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    routes: list[ApiRouteFact] = []
    current_name: str | None = None
    current_path: str | None = None
    current_controller: str | None = None
    current_path_line = 1
    for line_number, line in enumerate(source.splitlines(), start=1):
        route_name = re.match(r"^([A-Za-z0-9_.-]+):\s*$", line)
        if route_name:
            if current_path:
                routes.append(_drupal_route(file_fact, current_path, current_controller or current_name, current_path_line))
            current_name = route_name.group(1)
            current_path = None
            current_controller = None
            current_path_line = line_number
            continue
        path_match = re.match(r"^\s+path:\s*['\"](?P<path>/[^'\"]*)['\"]", line)
        if path_match:
            current_path = path_match.group("path")
            current_path_line = line_number
            continue
        controller_match = re.match(r"^\s+_controller:\s*['\"](?P<controller>[^'\"]+)['\"]", line)
        if controller_match:
            current_controller = controller_match.group("controller")
    if current_path:
        routes.append(_drupal_route(file_fact, current_path, current_controller or current_name, current_path_line))
    return routes


def _extract_grape_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    if not _looks_like_grape_source(source):
        return []
    global_prefix = _grape_global_prefix(root, file_fact.path)
    local_prefix = ""
    version_prefix = ""
    class_name = _grape_class_name(source) or Path(file_fact.path).stem
    scope_stack: list[tuple[int, str]] = []
    pending_params: list[dict[str, object]] = []
    routes: list[ApiRouteFact] = []
    lines = source.splitlines()

    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if stripped == "end":
            scope_stack = [entry for entry in scope_stack if entry[0] < indent]
            continue
        while scope_stack and scope_stack[-1][0] >= indent:
            scope_stack.pop()

        if prefix_match := GRAPE_PREFIX_LINE_RE.match(line):
            local_prefix = _grape_path_part(prefix_match.group("path"))
            continue
        if version_match := GRAPE_VERSION_PATH_LINE_RE.match(line):
            version_prefix = _grape_path_part(version_match.group("path"))
            continue
        if re.match(r"^\s*params\s+do\b", line):
            pending_params = _grape_params_from_block(lines, index)
            continue
        if scope_match := GRAPE_SCOPE_LINE_RE.match(line):
            scope_path = _grape_path_part(scope_match.group("path"))
            if scope_path:
                scope_stack.append((indent, scope_path))
            continue
        if route_match := GRAPE_ROUTE_LINE_RE.match(line):
            method = route_match.group("method").upper()
            raw_path = route_match.group("path") or ""
            route_part = _grape_path_part(raw_path)
            path = _grape_join_parts([global_prefix, local_prefix, version_prefix, *[entry[1] for entry in scope_stack], route_part])
            line_number = index + 1
            route_body = _grape_route_body(lines, index)
            params = _grape_route_params(path, pending_params, method, file_fact.path, line_number)
            routes.append(
                ApiRouteFact(
                    method=method,
                    path=path,
                    handler=class_name,
                    framework="grape",
                    kind="grape-route",
                    evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line_number, line_end=line_number),
                    parameters=params,
                    request_body="params" if _grape_has_body_params(params) else None,
                    response_type=_grape_response_type(source, route_body),
                )
            )
            pending_params = []
    return _dedupe_routes(routes)


def _looks_like_grape_source(source: str) -> bool:
    lower = source.lower()
    return "grape::api" in lower or "require 'grape" in lower or 'require "grape' in lower


def _grape_global_prefix(root: Path, current_path: str) -> str:
    current = current_path.replace("\\", "/")
    for path in sorted(root.rglob("*.rb")):
        relative = path.relative_to(root).as_posix()
        if relative == current or _grape_skip_path(relative):
            continue
        source = path.read_text(encoding="utf-8", errors="ignore")
        if "Grape::API" not in source or not re.search(r"(?m)^\s*mount\s+::?", source):
            continue
        for line in source.splitlines():
            if prefix_match := GRAPE_PREFIX_LINE_RE.match(line):
                return _grape_path_part(prefix_match.group("path"))
    return ""


def _grape_skip_path(path: str) -> bool:
    parts = path.replace("\\", "/").lower().split("/")
    if any(part in {".git", "vendor", "tmp", "log", "node_modules"} for part in parts):
        return True
    return any(part in {"spec", "test", "tests", "features", "samples", "examples"} for part in parts)


def _grape_class_name(source: str) -> str | None:
    modules: list[tuple[int, str]] = []
    for line in source.splitlines():
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if not stripped:
            continue
        if stripped == "end":
            modules = [entry for entry in modules if entry[0] < indent]
            continue
        while modules and modules[-1][0] >= indent:
            modules.pop()
        if module_match := re.match(r"^\s*module\s+([A-Za-z_]\w*)\b", line):
            modules.append((indent, module_match.group(1)))
            continue
        if class_match := GRAPE_CLASS_RE.match(line):
            parts = [name for _module_indent, name in modules]
            parts.append(class_match.group("name"))
            return "::".join(parts)
    return None


def _grape_params_from_block(lines: list[str], start_index: int) -> list[dict[str, object]]:
    params: list[dict[str, object]] = []
    start_indent = len(lines[start_index]) - len(lines[start_index].lstrip())
    for line in lines[start_index + 1 :]:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if stripped == "end" and indent <= start_indent:
            break
        if match := GRAPE_PARAM_LINE_RE.match(line):
            rest = match.group("rest")
            type_match = re.search(r"\btype:\s*([A-Za-z_:]\w*(?:::[A-Za-z_]\w*)*)", rest)
            source = "body" if re.search(r"param_type:\s*['\"]?body['\"]?", rest) else None
            params.append(
                {
                    "name": match.group("name"),
                    "type": type_match.group(1) if type_match else None,
                    "required": match.group("kind") == "requires",
                    "source": source,
                }
            )
    return params


def _grape_route_params(
    path: str,
    pending_params: list[dict[str, object]],
    method: str,
    file_path: str,
    line: int,
) -> list[RequestParamFact]:
    facts: list[RequestParamFact] = []
    path_names = {name for name in re.findall(r"\{([^}]+)\}", path)}
    for name in path_names:
        facts.append(
            RequestParamFact(
                name=name,
                source="path",
                type=None,
                required=True,
                evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
            )
        )
    for item in pending_params:
        name = str(item["name"])
        if name in path_names:
            continue
        source = str(item.get("source") or ("body" if method in {"POST", "PUT", "PATCH"} else "query"))
        facts.append(
            RequestParamFact(
                name=name,
                source=source,
                type=str(item["type"]) if item.get("type") else None,
                required=bool(item["required"]),
                evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
            )
        )
    return facts


def _grape_route_body(lines: list[str], route_index: int) -> str:
    route_indent = len(lines[route_index]) - len(lines[route_index].lstrip())
    body: list[str] = []
    depth = 1
    for line in lines[route_index + 1 :]:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if stripped == "end" and indent <= route_indent:
            depth -= 1
            if depth <= 0:
                break
        body.append(line)
        if re.match(r"^(?:if|unless|case|begin)\b", stripped) or re.search(r"\bdo\s*(?:\|[^|]*\|)?\s*$", stripped):
            depth += 1
    return "\n".join(body)


def _grape_has_body_params(params: list[RequestParamFact]) -> bool:
    return any(param.source == "body" for param in params)


def _grape_response_type(source: str, body: str) -> str | None:
    if "env['api.format'] = :binary" in body or 'env["api.format"] = :binary' in body:
        return "binary"
    if re.search(r"\bformat\s+:json\b", source):
        return "json"
    if re.search(r"\bcontent_type\s+:xml\b", source):
        return "xml"
    if re.search(r"\bpresent\b", body):
        return "entity"
    return None


def _grape_path_part(raw: str) -> str:
    value = raw.strip().rstrip(",")
    if not value:
        return ""
    if value.startswith(('"', "'")) and value.endswith(('"', "'")):
        value = value[1:-1]
    elif value.startswith(":"):
        value = value[1:]
    value = value.strip("/")
    value = re.sub(r":([A-Za-z_]\w*)", r"{\1}", value)
    return value


def _grape_join_parts(parts: list[str]) -> str:
    cleaned = [part.strip("/") for part in parts if part and part.strip("/")]
    return "/" + "/".join(cleaned) if cleaned else "/"


def _extract_sinatra_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    normalized = file_fact.path.replace("\\", "/").lower()
    if normalized == "config/routes.rb" or normalized.startswith("config/routes/"):
        return []
    source = _read(root, file_fact)
    if not _looks_like_sinatra_source(source):
        return []
    class_ranges = _sinatra_class_ranges(source)
    routes: list[ApiRouteFact] = []
    for match in SINATRA_ROUTE_RE.finditer(source):
        raw_path = match.group("path").strip()
        line = _line_for_offset(source, match.start())
        path = _sinatra_route_path(raw_path)
        method = match.group("method").upper()
        owner = _sinatra_owner_for_offset(class_ranges, match.start()) or "Sinatra::Application"
        window = _sinatra_route_body(source, match.end())
        routes.append(
            ApiRouteFact(
                method=method,
                path=path,
                handler=owner,
                framework="sinatra",
                kind="sinatra-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                parameters=_sinatra_path_params(path, file_fact.path, line),
                request_body="params" if method in {"POST", "PUT", "PATCH"} and re.search(r"\bparams\b", window) else None,
                response_type=_sinatra_response_type(window),
            )
        )
    return _dedupe_routes(routes)


def _sinatra_route_body(source: str, offset: int) -> str:
    line_end = source.find("\n", offset)
    if line_end == -1:
        return source[offset : min(len(source), offset + 500)]
    body_lines: list[str] = []
    depth = 1
    for line in source[line_end + 1 :].splitlines(keepends=True):
        stripped = line.strip()
        if stripped == "end":
            depth -= 1
            if depth == 0:
                break
            body_lines.append(line)
            continue
        body_lines.append(line)
        if re.match(r"^(?:if|unless|case|begin)\b", stripped) or re.search(r"\bdo\s*(?:\|[^|]*\|)?\s*$", stripped):
            depth += 1
    return "".join(body_lines)


def _looks_like_sinatra_source(source: str) -> bool:
    lower = source.lower()
    if "grape::api" in lower:
        return False
    return (
        "require 'sinatra" in lower
        or 'require "sinatra' in lower
        or "sinatra::base" in lower
        or "sinatra::application" in lower
        or re.search(r"(?m)^\s*(?:get|post|put|patch|delete|options|head)\s+['\"](?:/|\*)", source) is not None
    )


def _sinatra_class_ranges(source: str) -> list[tuple[int, int, str]]:
    matches = list(SINATRA_CLASS_RE.finditer(source))
    ranges: list[tuple[int, int, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        ranges.append((match.start(), end, match.group("name")))
    return ranges


def _sinatra_owner_for_offset(ranges: list[tuple[int, int, str]], offset: int) -> str | None:
    for start, end, name in ranges:
        if start <= offset <= end:
            return name
    return None


def _sinatra_route_path(path: str) -> str:
    if path == "*":
        return "*"
    cleaned = re.sub(r":([A-Za-z_]\w*)", r"{\1}", path.strip())
    return _ensure_slash(cleaned)


def _sinatra_path_params(path: str, file_path: str, line: int) -> list[RequestParamFact]:
    return [
        RequestParamFact(
            name=name,
            source="path",
            type=None,
            required=True,
            evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
        )
        for name in re.findall(r"\{([^}]+)\}", path)
        if name
    ]


def _sinatra_response_type(window: str) -> str | None:
    if ".to_json" in window or re.search(r"\bcontent_type\s+:json\b", window):
        return "json"
    if re.search(r"\bcontent_type\s+:html\b", window) or ".html" in window:
        return "html"
    return None


def _extract_rails_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    normalized = file_fact.path.replace("\\", "/").lower()
    if normalized != "config/routes.rb" and not (
        normalized.startswith("config/routes/") and normalized.endswith(".rb")
    ):
        return []
    source = _read(root, file_fact)
    routes: list[ApiRouteFact] = []
    stack: list[dict[str, object]] = []
    lines = source.splitlines(keepends=True)
    for index, raw_line in enumerate(lines):
        line_number = index + 1
        line = raw_line.rstrip()
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "end":
            stack = [entry for entry in stack if int(entry["indent"]) < indent]
            continue
        while stack and int(stack[-1]["indent"]) >= indent:
            stack.pop()

        base_collection = str(stack[-1]["collection"]) if stack else ""
        base_member = str(stack[-1]["member"]) if stack else ""

        if RAILS_SCOPE_MODULE_RE.match(stripped):
            continue

        if scope_path_match := RAILS_SCOPE_PATH_RE.match(stripped):
            path = _join_paths(base_member or base_collection, scope_path_match.group("path"))
            if stripped.endswith("do"):
                stack.append({"indent": indent, "collection": path, "member": path, "name": scope_path_match.group("path")})
            continue

        if quoted_scope_match := RAILS_QUOTED_SCOPE_RE.match(stripped):
            path = _join_paths(base_member or base_collection, quoted_scope_match.group("path"))
            if stripped.endswith("do"):
                stack.append({"indent": indent, "collection": path, "member": path, "name": quoted_scope_match.group("path")})
            continue

        if devise_match := RAILS_DEVISE_TOKEN_AUTH_RE.match(stripped):
            mount_path = _first_match(devise_match.group("args"), r"at:\s*['\"]([^'\"]+)['\"]") or "auth"
            routes.append(
                _rails_route(
                    file_fact,
                    "POST",
                    _join_paths(base_collection, f"{mount_path}/sign_in"),
                    "devise_token_auth#sign_in",
                    "rails-devise-token-auth-route",
                    line_number,
                )
            )
            routes.append(
                _rails_route(
                    file_fact,
                    "DELETE",
                    _join_paths(base_collection, f"{mount_path}/sign_out"),
                    "devise_token_auth#sign_out",
                    "rails-devise-token-auth-route",
                    line_number,
                )
            )
            routes.append(
                _rails_route(
                    file_fact,
                    "GET",
                    _join_paths(base_collection, f"{mount_path}/validate_token"),
                    "devise_token_auth#validate_token",
                    "rails-devise-token-auth-route",
                    line_number,
                )
            )
            continue

        if devise_for_match := RAILS_DEVISE_FOR_RE.match(stripped):
            statement = _rails_continued_statement(lines, index)
            routes.extend(_rails_devise_for_routes(file_fact, base_collection, devise_for_match.group("name"), statement, line_number))
            continue

        if namespace_match := RAILS_NAMESPACE_RE.match(stripped):
            path = _join_paths(base_member or base_collection, namespace_match.group("name"))
            if stripped.endswith("do"):
                stack.append({"indent": indent, "collection": path, "member": path, "name": namespace_match.group("name")})
            continue

        if scope_match := RAILS_SCOPE_RE.match(stripped):
            path = _join_paths(base_member or base_collection, scope_match.group("name"))
            if stripped.endswith("do"):
                stack.append({"indent": indent, "collection": path, "member": path, "name": scope_match.group("name")})
            continue

        if block_scope := RAILS_BLOCK_SCOPE_RE.match(stripped):
            if stripped.endswith("do"):
                stack.append(
                    {
                        "indent": indent,
                        "collection": base_collection,
                        "member": base_member,
                        "name": stack[-1]["name"] if stack else "",
                        "route_scope": block_scope.group("kind"),
                    }
                )
            continue

        if inline_block_route := RAILS_INLINE_BLOCK_ROUTE_RE.match(stripped):
            if inline_block_route.group("scope") == "collection":
                base = base_collection
            else:
                base = base_member or base_collection
            args = inline_block_route.group("args") or ""
            route_path = _join_paths(base, inline_block_route.group("path"))
            routes.append(
                _rails_route(
                    file_fact,
                    inline_block_route.group("method").upper(),
                    route_path,
                    _rails_route_handler(args, stack, inline_block_route.group("path")),
                    "rails-route",
                    line_number,
                )
            )
            continue

        resource_statement = _rails_continued_statement(lines, index)
        if resource_match := RAILS_RESOURCES_RE.match(resource_statement):
            name = resource_match.group("name")
            args = resource_match.group("args") or ""
            is_singular = resource_match.group("kind") == "resource"
            collection_path = _join_paths(base_member, name)
            member_param = _first_match(args, r"param:\s+:([A-Za-z_]\w*)") or "id"
            member_path = collection_path if is_singular else _join_paths(collection_path, f"{{{member_param}}}")
            routes.extend(
                _rails_resource_routes(
                    file_fact,
                    name,
                    is_singular,
                    collection_path,
                    member_path,
                    args,
                    line_number,
                )
            )
            if re.search(r"\bdo\s*(?:#.*)?$", resource_statement):
                stack.append({"indent": indent, "collection": collection_path, "member": member_path, "name": name})
            continue

        if symbol_route := RAILS_SYMBOL_ROUTE_RE.match(stripped):
            args = symbol_route.group("args") or ""
            route_scope = str(stack[-1].get("route_scope", "")) if stack else ""
            if "on: :collection" in args or route_scope == "collection":
                base = base_collection
            else:
                base = base_member or base_collection
            route_path = _join_paths(base, symbol_route.group("name"))
            handler = _first_match(args, r"to:\s*['\"]([^'\"]+)['\"]") or _rails_stack_handler(stack, symbol_route.group("name"))
            routes.append(_rails_route(file_fact, symbol_route.group("method").upper(), route_path, handler, "rails-route", line_number))
            continue

        if quoted_route := RAILS_ROUTE_RE.match(stripped):
            args = quoted_route.group("args") or ""
            route_scope = str(stack[-1].get("route_scope", "")) if stack else ""
            if "on: :collection" in args or route_scope == "collection":
                base = base_collection
            else:
                base = base_member or base_collection
            route_path = _join_paths(base, quoted_route.group("path"))
            routes.append(
                _rails_route(
                    file_fact,
                    quoted_route.group("method").upper(),
                    route_path,
                    _rails_route_handler(args, stack, quoted_route.group("path")),
                    "rails-route",
                    line_number,
                )
            )
    return _dedupe_routes(routes)


def _rails_resource_routes(
    file_fact: FileFact,
    name: str,
    is_singular: bool,
    collection_path: str,
    member_path: str,
    args: str,
    line: int,
) -> list[ApiRouteFact]:
    routes: list[ApiRouteFact] = []
    for action in _rails_resource_actions(args, is_singular):
        for method, path, kind in _rails_resource_action_routes(action, collection_path, member_path, is_singular):
            routes.append(
                _rails_route(
                    file_fact,
                    method,
                    path,
                    f"{_rails_resource_controller(name, args)}#{action}",
                    kind,
                    line,
                    request_body="params" if method in {"POST", "PUT", "PATCH"} else None,
                )
            )
    return routes


def _rails_resource_actions(args: str, is_singular: bool) -> list[str]:
    default_actions = ["show", "create", "update", "destroy"] if is_singular else ["index", "create", "show", "update", "destroy"]
    only = _rails_option_symbols(args, "only")
    excepted = set(_rails_option_symbols(args, "except"))
    actions = [action for action in default_actions if not only or action in only]
    return [action for action in actions if action not in excepted]


def _rails_option_symbols(args: str, option: str) -> list[str]:
    match = re.search(
        rf"\b{re.escape(option)}:\s*(?P<value>\[[^\]]+\]|%[iw]\[[^\]]+\]|:[A-Za-z_]\w*|['\"][A-Za-z_]\w*['\"])",
        args,
    )
    if not match:
        return []
    value = match.group("value")
    if value.startswith(":"):
        return [value[1:]]
    if value.startswith(("%i[", "%w[")):
        return [item for item in re.split(r"\s+", value[3:-1].strip()) if item]
    return [
        item
        for item in re.findall(r":([A-Za-z_]\w*)|['\"]([A-Za-z_]\w*)['\"]", value)
        for item in item
        if item
    ]


def _rails_resource_action_routes(
    action: str,
    collection_path: str,
    member_path: str,
    is_singular: bool,
) -> list[tuple[str, str, str]]:
    if is_singular:
        path = collection_path
        if action == "show":
            return [("GET", path, "rails-resource-route")]
        if action == "create":
            return [("POST", path, "rails-resource-route")]
        if action == "update":
            return [("PATCH", path, "rails-resource-route"), ("PUT", path, "rails-resource-route")]
        if action == "destroy":
            return [("DELETE", path, "rails-resource-route")]
        return []

    if action == "index":
        return [("GET", collection_path, "rails-resource-route")]
    if action == "create":
        return [("POST", collection_path, "rails-resource-route")]
    if action == "show":
        return [("GET", member_path, "rails-resource-member-route")]
    if action == "update":
        return [("PATCH", member_path, "rails-resource-member-route"), ("PUT", member_path, "rails-resource-member-route")]
    if action == "destroy":
        return [("DELETE", member_path, "rails-resource-member-route")]
    return []


def _rails_resource_controller(name: str, args: str) -> str:
    return _rails_option_value(args, "controller") or name


def _rails_devise_for_routes(
    file_fact: FileFact,
    base_collection: str,
    name: str,
    statement: str,
    line: int,
) -> list[ApiRouteFact]:
    mount_path = _first_match(statement, r"\bpath:\s*['\"]([^'\"]+)['\"]") or name
    sign_in_path = _rails_devise_path_name(statement, "sign_in", "sign_in")
    sign_out_path = _rails_devise_path_name(statement, "sign_out", "sign_out")
    controller = _rails_option_value(statement, "sessions") or "sessions"
    return [
        _rails_route(
            file_fact,
            "POST",
            _join_paths(base_collection, f"{mount_path}/{sign_in_path}"),
            f"{controller}#create",
            "rails-devise-route",
            line,
            request_body="params",
        ),
        _rails_route(
            file_fact,
            "DELETE",
            _join_paths(base_collection, f"{mount_path}/{sign_out_path}"),
            f"{controller}#destroy",
            "rails-devise-route",
            line,
        ),
    ]


def _rails_devise_path_name(statement: str, name: str, default: str) -> str:
    return _rails_option_value(statement, name) or default


def _rails_option_value(source: str, name: str) -> str | None:
    match = re.search(rf"\b{re.escape(name)}:\s*(?::(?P<symbol>[A-Za-z_]\w*)|['\"](?P<string>[^'\"]+)['\"])", source)
    if not match:
        return None
    return match.group("symbol") or match.group("string")


def _rails_continued_statement(lines: list[str], index: int) -> str:
    chunks = [lines[index].strip()]
    depth = _rails_delimiter_depth(chunks[0])
    needs_more = chunks[0].endswith(",") or depth > 0
    for raw_line in lines[index + 1 : index + 6]:
        if not needs_more:
            break
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            break
        chunks.append(stripped)
        depth += _rails_delimiter_depth(stripped)
        needs_more = stripped.endswith(",") or depth > 0
    return " ".join(chunks)


def _rails_delimiter_depth(source: str) -> int:
    return source.count("{") + source.count("[") + source.count("(") - source.count("}") - source.count("]") - source.count(")")


def _rails_route(
    file_fact: FileFact,
    method: str,
    path: str,
    handler: str | None,
    kind: str,
    line: int,
    *,
    parameters: list[RequestParamFact] | None = None,
    request_body: str | None = None,
) -> ApiRouteFact:
    normalized_path = _ensure_slash(path)
    return ApiRouteFact(
        method=method,
        path=normalized_path,
        handler=handler,
        framework="rails",
        kind=kind,
        evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
        parameters=parameters if parameters is not None else _rails_path_parameters(normalized_path, file_fact.path, line),
        request_body=request_body,
    )


def _rails_path_parameters(path: str, file_path: str, line: int) -> list[RequestParamFact]:
    names = [match.group("brace") or match.group("glob") for match in re.finditer(r"\{(?P<brace>[^}]+)\}|\(\*(?P<glob>[A-Za-z_]\w*)\)", path)]
    return [
        RequestParamFact(
            name=name,
            source="path",
            type=None,
            required=True,
            evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
        )
        for name in names
        if name
    ]


def _rails_route_handler(args: str, stack: list[dict[str, object]], path: str) -> str | None:
    return (
        _first_match(args, r"to:\s*['\"]([^'\"]+)['\"]")
        or _first_match(args, r"=>\s*['\"]([^'\"]+)['\"]")
        or _rails_stack_handler(stack, _rails_action_name_from_path(path))
    )


def _rails_action_name_from_path(path: str) -> str:
    name = path.strip("/").rsplit("/", 1)[-1]
    name = name.split(".", 1)[0]
    name = name.strip(":{}")
    return name.replace("-", "_")


def _rails_stack_handler(stack: list[dict[str, object]], action: str) -> str | None:
    if not stack:
        return None
    name = str(stack[-1]["name"])
    return f"{name}#{action}"


def _extract_play_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    routes: list[ApiRouteFact] = []
    for line_number, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("->"):
            continue
        match = PLAY_ROUTE_LINE_RE.match(line)
        if not match:
            continue
        method = match.group("method").upper()
        raw_path = match.group("path")
        path = _play_route_path(raw_path)
        handler = match.group("handler")
        args = match.group("args") or ""
        routes.append(
            ApiRouteFact(
                method=method,
                path=path,
                handler=handler,
                framework="playframework",
                kind="play-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line_number, line_end=line_number),
                parameters=_play_route_parameters(raw_path, args, file_fact.path, line_number),
                request_body="request" if method in {"POST", "PUT", "PATCH"} and "request" in args.lower() else None,
            )
        )
    return _dedupe_routes(routes)


def _play_route_path(path: str) -> str:
    normalized = re.sub(r":([A-Za-z_]\w*)", r"{\1}", path)
    normalized = re.sub(r"\*([A-Za-z_]\w*)", r"{\1}", normalized)
    return _ensure_slash(normalized)


def _play_route_parameters(path: str, args: str, file_path: str, line: int) -> list[RequestParamFact]:
    params: list[RequestParamFact] = []
    path_names = set(re.findall(r"[:*]([A-Za-z_]\w*)", path))
    for name in sorted(path_names):
        params.append(
            RequestParamFact(
                name=name,
                source="path",
                type=None,
                required=True,
                evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
            )
        )
    for arg in _split_args(args):
        cleaned = arg.strip()
        if not cleaned:
            continue
        match = re.match(r"(?P<name>[A-Za-z_]\w*)\s*(?::\s*(?P<type>[A-Za-z_][\w.\[\]]*))?(?:\s*\?=\s*(?P<default>.+))?$", cleaned)
        if not match:
            continue
        name = match.group("name")
        if name in path_names or name.lower() == "request":
            continue
        params.append(
            RequestParamFact(
                name=name,
                source="query" if match.group("default") is not None else "handler",
                type=match.group("type"),
                required=match.group("default") is None,
                evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
            )
        )
    return params


def _split_args(source: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    quote: str | None = None
    escaped = False
    for index, char in enumerate(source):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            continue
        if char in "([{":
            depth += 1
        elif char in ")]}" and depth:
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(source[start:index])
            start = index + 1
    parts.append(source[start:])
    return parts


def _extract_clojure_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    routes: list[ApiRouteFact] = []
    namespace = _clojure_namespace(source)
    api_prefix = _clojure_api_prefix(root, namespace, source)
    for match in CLOJURE_DEFENDPOINT_RE.finditer(source):
        line = _line_for_offset(source, match.start())
        route_path = _join_paths(api_prefix, match.group("path")) if api_prefix else match.group("path")
        routes.append(
            ApiRouteFact(
                method=match.group("method").upper(),
                path=_ensure_slash(route_path),
                handler=namespace,
                framework="clojure-ring",
                kind="metabase-defendpoint-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
            )
        )
    for match in CLOJURE_COMPOJURE_ROUTE_RE.finditer(source):
        line = _line_for_offset(source, match.start())
        raw_path = match.group("path")
        route_path = _clojure_route_path(raw_path)
        method = match.group("method").upper()
        routes.append(
            ApiRouteFact(
                method=method,
                path=route_path,
                handler=_clojure_compojure_handler(match.group("rest")),
                framework="clojure-ring",
                kind="compojure-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                parameters=_clojure_route_parameters(raw_path, file_fact.path, line),
                request_body="params" if method in {"POST", "PUT", "PATCH"} else None,
            )
        )
    for match in CLOJURE_REITIT_ROUTE_RE.finditer(source):
        line = _line_for_offset(source, match.start())
        for method_match in CLOJURE_REITIT_METHOD_RE.finditer(match.group("body")):
            routes.append(
                ApiRouteFact(
                    method=method_match.group("method").upper(),
                    path=match.group("path"),
                    handler=None,
                    framework="reitit",
                    kind="reitit-route",
                    evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                )
            )
    return routes


def _clojure_route_path(path: str) -> str:
    normalized = re.sub(r":([A-Za-z_][\w-]*)(?:\{[^}/]+\})?", r"{\1}", path)
    return _ensure_slash(normalized)


def _clojure_route_parameters(path: str, file_path: str, line: int) -> list[RequestParamFact]:
    names = re.findall(r":([A-Za-z_][\w-]*)(?:\{[^}/]+\})?", path)
    return [
        RequestParamFact(
            name=name,
            source="path",
            type=None,
            required=True,
            evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
        )
        for name in names
    ]


def _clojure_compojure_handler(rest: str) -> str | None:
    for pattern in (
        r"#'(?P<handler>[A-Za-z0-9_.-]+/[A-Za-z0-9_.!?-]+)",
        r"\b(?P<handler>[A-Za-z0-9_.-]+/[A-Za-z0-9_.!?-]+)\b",
    ):
        match = re.search(pattern, rest)
        if match:
            return match.group("handler")
    return None


def _clojure_namespace(source: str) -> str | None:
    match = CLOJURE_NS_RE.search(source)
    return match.group("namespace") if match else None


def _clojure_api_prefix(root: Path, namespace: str | None, source: str) -> str:
    prefix = _clojure_api_prefix_from_ns_doc(source)
    if prefix:
        return prefix
    if not namespace:
        return ""
    prefixes = _clojure_route_prefixes(str(root.resolve()))
    if namespace in prefixes:
        return prefixes[namespace]
    best_namespace = ""
    best_prefix = ""
    for candidate, candidate_prefix in prefixes.items():
        if namespace.startswith(f"{candidate}.") and len(candidate) > len(best_namespace):
            best_namespace = candidate
            best_prefix = candidate_prefix
    return best_prefix


def _clojure_api_prefix_from_ns_doc(source: str) -> str:
    match = CLOJURE_NS_DOC_PREFIX_RE.search(source)
    if not match:
        return ""
    return _clojure_api_prefix_from_text(match.group("doc"), require_leading=True)


def _clojure_api_prefix_from_text(text: str, *, require_leading: bool = False) -> str:
    cleaned = text.strip().strip("`")
    if require_leading and not cleaned.startswith("/api"):
        return ""
    prefix_match = CLOJURE_API_PREFIX_RE.search(cleaned)
    return prefix_match.group("prefix").rstrip("/") if prefix_match else ""


@lru_cache(maxsize=16)
def _clojure_route_prefixes(root_text: str) -> dict[str, str]:
    root = Path(root_text)
    prefixes: dict[str, str] = {}
    sources: list[tuple[str, str]] = []
    route_files = [
        (root / "src" / "metabase" / "api_routes" / "routes.clj", "/api"),
        (root / "enterprise" / "backend" / "src" / "metabase_enterprise" / "api_routes" / "routes.clj", "/api"),
    ]
    for routes_file, base_prefix in route_files:
        if not routes_file.exists():
            continue
        source = routes_file.read_text(encoding="utf-8", errors="ignore")
        ee_routes_start = source.find("ee-routes-map")
        for match in CLOJURE_ROUTE_MAP_ENTRY_RE.finditer(source):
            entry_base = "/api/ee" if base_prefix == "/api" and ee_routes_start != -1 and match.start() > ee_routes_start else base_prefix
            route_prefix = _join_paths(entry_base, match.group("prefix"))
            for namespace_match in CLOJURE_NAMESPACE_TARGET_RE.finditer(match.group("target")):
                prefixes.setdefault(namespace_match.group("namespace"), route_prefix)

    source_roots = [root / "src", root / "enterprise" / "backend" / "src"]
    for source_root in source_roots:
        if not source_root.exists():
            continue
        for candidate in source_root.rglob("*.clj"):
            try:
                source = candidate.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            namespace = _clojure_namespace(source)
            prefix = _clojure_api_prefix_from_ns_doc(source)
            if namespace and prefix:
                prefixes[namespace] = prefix
            if namespace:
                sources.append((namespace, source))
            for handler_match in CLOJURE_NS_HANDLER_DOC_RE.finditer(source):
                handler_prefix = _clojure_api_prefix_from_text(handler_match.group("doc"), require_leading=True)
                if handler_prefix:
                    prefixes[handler_match.group("namespace")] = handler_prefix

    for _ in range(3):
        changed = False
        for namespace, source in sources:
            parent_prefix = prefixes.get(namespace)
            if not parent_prefix:
                continue
            for match in CLOJURE_ROUTE_MAP_ENTRY_RE.finditer(source):
                target = match.group("target").strip()
                if target.startswith("{"):
                    continue
                route_prefix = _join_paths(parent_prefix, match.group("prefix"))
                for namespace_match in CLOJURE_NAMESPACE_TARGET_RE.finditer(target):
                    target_namespace = namespace_match.group("namespace")
                    if target_namespace not in prefixes:
                        prefixes[target_namespace] = route_prefix
                        changed = True
        if not changed:
            break
    return prefixes


def _extract_phoenix_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    normalized = file_fact.path.replace("\\", "/").lower()
    if not normalized.endswith("router.ex"):
        return []
    source = _read(root, file_fact)
    routes: list[ApiRouteFact] = []
    scope_stack: list[str | None] = []
    lines = source.splitlines()
    skip_until = -1
    for index, line in enumerate(lines):
        if index <= skip_until:
            continue
        line_number = index + 1
        stripped = line.strip()
        if stripped == "end":
            if scope_stack:
                scope_stack.pop()
            continue

        statement, statement_end = _phoenix_continued_statement(lines, index)
        skip_until = max(skip_until, statement_end)
        scope_path = _phoenix_scope_path(statement)
        if stripped.startswith("scope") and re.search(r"\bdo\s*(?:#.*)?$", statement):
            scope_stack.append(scope_path)
            continue

        prefix = _phoenix_current_scope(scope_stack)
        route_match = PHOENIX_LINE_ROUTE_RE.match(statement)
        if route_match:
            route_path = _join_paths(prefix, route_match.group("path"))
            method = route_match.group("method").upper()
            action = route_match.group("action")
            handler = route_match.group("controller") + (f":{action}" if action else "")
            routes.append(
                ApiRouteFact(
                    method=method,
                    path=route_path,
                    handler=handler,
                    framework="phoenix",
                    kind="phoenix-route",
                    evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line_number, line_end=line_number),
                    parameters=_phoenix_route_parameters(route_path, file_fact.path, line_number),
                    request_body="params" if method in {"POST", "PUT", "PATCH"} else None,
                )
            )
            continue

        live_match = PHOENIX_LIVE_RE.match(statement)
        if live_match:
            route_path = _join_paths(prefix, live_match.group("path"))
            action = live_match.group("action")
            handler = live_match.group("liveview") + (f":{action}" if action else "")
            routes.append(
                ApiRouteFact(
                    method="GET",
                    path=route_path,
                    handler=handler,
                    framework="phoenix",
                    kind="phoenix-live-route",
                    evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line_number, line_end=line_number),
                    parameters=_phoenix_route_parameters(route_path, file_fact.path, line_number),
                    response_type="LiveView",
                )
            )
            continue

        dashboard_match = PHOENIX_LIVE_DASHBOARD_RE.match(statement)
        if dashboard_match:
            route_path = _join_paths(prefix, dashboard_match.group("path"))
            routes.append(
                ApiRouteFact(
                    method="GET",
                    path=route_path,
                    handler="Phoenix.LiveDashboard",
                    framework="phoenix",
                    kind="phoenix-live-dashboard-route",
                    evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line_number, line_end=line_number),
                    parameters=_phoenix_route_parameters(route_path, file_fact.path, line_number),
                    response_type="LiveDashboard",
                )
            )
            continue

        forward_match = PHOENIX_FORWARD_RE.match(statement)
        if forward_match:
            route_path = _join_paths(prefix, forward_match.group("path"))
            routes.append(
                ApiRouteFact(
                    method="ANY",
                    path=route_path,
                    handler=forward_match.group("plug"),
                    framework="phoenix",
                    kind="phoenix-forward-route",
                    evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line_number, line_end=line_number),
                    parameters=_phoenix_route_parameters(route_path, file_fact.path, line_number),
                    response_type="Plug",
                )
            )
            continue

        resources_match = PHOENIX_LINE_RESOURCES_RE.match(statement)
        if resources_match:
            route_path = _join_paths(prefix, resources_match.group("path"))
            routes.extend(
                _phoenix_resource_route_facts(
                    route_path,
                    resources_match.group("controller"),
                    resources_match.group("args") or "",
                    file_fact.path,
                    line_number,
                )
            )
            if re.search(r"\bdo\s*(?:#.*)?$", statement):
                nested_param = f":{_singular_name(Path(route_path).name)}_id"
                scope_stack.append(_join_paths(resources_match.group("path"), nested_param))
            continue

        if re.search(r"\bdo\s*(?:#.*)?$", statement):
            scope_stack.append(None)
    return _dedupe_routes(routes)


def _phoenix_continued_statement(lines: list[str], index: int) -> tuple[str, int]:
    chunks = [lines[index].strip()]
    if not _phoenix_statement_can_continue(chunks[0]):
        return chunks[0], index
    if _phoenix_statement_complete(chunks[0]):
        return chunks[0], index
    end_index = index
    for offset, next_line in enumerate(lines[index + 1 : index + 7], start=1):
        stripped = next_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        end_index = index + offset
        chunks.append(stripped)
        joined = " ".join(chunks)
        if _phoenix_statement_complete(joined):
            break
    return " ".join(chunks), end_index


def _phoenix_statement_can_continue(line: str) -> bool:
    return bool(re.match(r"^(?:scope|(?:get|post|put|patch|delete|live|forward|resources)\b)", line.strip(), re.IGNORECASE))


def _phoenix_statement_complete(statement: str) -> bool:
    if re.match(r"^scope\b", statement, re.IGNORECASE):
        return re.search(r"\bdo\s*(?:#.*)?$", statement) is not None
    if re.match(r"^(?:live|(?:get|post|put|patch|delete|forward|resources)\b)", statement, re.IGNORECASE):
        return statement.count("(") <= statement.count(")") and not statement.rstrip().endswith(",")
    return True


def _phoenix_scope_path(statement: str) -> str | None:
    scope_match = PHOENIX_SCOPE_RE.match(statement)
    if scope_match:
        return scope_match.group("path")
    named_match = PHOENIX_SCOPE_NAMED_PATH_RE.match(statement)
    return named_match.group("path") if named_match else None


def _phoenix_resource_route_facts(route_path: str, controller: str, args: str, file_path: str, line: int) -> list[ApiRouteFact]:
    actions = _phoenix_resource_actions(args)
    templates = [
        ("index", "GET", route_path, None),
        ("create", "POST", route_path, "params"),
        ("new", "GET", _join_paths(route_path, "new"), None),
        ("show", "GET", _join_paths(route_path, ":id"), None),
        ("edit", "GET", _join_paths(route_path, ":id/edit"), None),
        ("update", "PATCH", _join_paths(route_path, ":id"), "params"),
        ("update", "PUT", _join_paths(route_path, ":id"), "params"),
        ("delete", "DELETE", _join_paths(route_path, ":id"), None),
    ]
    routes: list[ApiRouteFact] = []
    for action, method, path, request_body in templates:
        if action not in actions:
            continue
        routes.append(
            ApiRouteFact(
                method=method,
                path=path,
                handler=f"{controller}:{action}",
                framework="phoenix",
                kind="phoenix-resource-route",
                evidence=Evidence(file=file_path, kind="backend-route", line_start=line, line_end=line),
                parameters=_phoenix_route_parameters(path, file_path, line),
                request_body=request_body,
            )
        )
    return routes


def _phoenix_resource_actions(args: str) -> set[str]:
    default_order = ["index", "create", "new", "show", "edit", "update", "delete"]
    actions = set(default_order)
    only = _phoenix_option_atoms(args, "only")
    if only:
        actions = {action for action in default_order if action in only}
    except_actions = _phoenix_option_atoms(args, "except")
    if except_actions:
        actions -= except_actions
    return actions


def _phoenix_option_atoms(args: str, option: str) -> set[str]:
    match = re.search(rf"\b{re.escape(option)}\s*:\s*\[(?P<values>[^\]]*)\]", args)
    if not match:
        return set()
    return set(re.findall(r":([A-Za-z_]\w*)", match.group("values")))


def _phoenix_current_scope(scope_stack: list[str | None]) -> str:
    prefix = ""
    for scope in scope_stack:
        if scope:
            prefix = _join_paths(prefix, scope)
    return prefix


def _phoenix_route_parameters(path: str, file_path: str, line: int) -> list[RequestParamFact]:
    return [
        RequestParamFact(
            name=name,
            source="path",
            type=None,
            required=True,
            evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
        )
        for name in re.findall(r":([A-Za-z_]\w*)", path)
    ]


def _extract_aspnet_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    class_prefix = ""
    class_name = Path(file_fact.path).stem
    area = _aspnet_area_name(source)
    class_match = ASPNET_CLASS_RE.search(source)
    if class_match:
        class_name = class_match.group("name")
        class_attrs = class_match.group("attrs") or _csharp_attribute_block_before(source, class_match.start())
        class_prefix = _aspnet_route_path(class_attrs, class_name)

    routes: list[ApiRouteFact] = []
    routes.extend(_extract_aspnet_map_controller_routes(file_fact, source))
    for match in ASPNET_METHOD_SIGNATURE_RE.finditer(source):
        return_type = " ".join(match.group("return").split())
        if return_type == "class":
            continue
        attrs = _csharp_attribute_block_before(source, match.start())
        if not attrs or ASPNET_ROUTE_ATTR_RE.search(attrs) is None:
            continue
        action = _aspnet_action_name(attrs) or match.group("name")
        route_attrs = list(ASPNET_ROUTE_ATTR_RE.finditer(attrs))
        has_http_route = any(route_attr.group("name").lower() != "route" for route_attr in route_attrs)
        route_template = next(
            (
                route_attr.group("path")
                for route_attr in route_attrs
                if route_attr.group("name").lower() == "route" and route_attr.group("path") is not None
            ),
            None,
        )
        for route_attr in route_attrs:
            attr_name = route_attr.group("name").lower()
            if attr_name == "route" and has_http_route:
                continue
            method = "ANY" if attr_name == "route" else attr_name.removeprefix("http").upper()
            route_path = route_attr.group("path")
            if attr_name != "route" and route_path is None:
                route_path = route_template
            path = _join_paths(class_prefix, _aspnet_replace_tokens(route_path or "", class_name, action))
            path = _aspnet_replace_tokens(path, class_name, action)
            if not route_path and not class_prefix:
                path = _aspnet_conventional_action_path(file_fact.path, class_name, action, area)
            line = _line_for_offset(source, match.start())
            routes.append(
                ApiRouteFact(
                    method=method,
                    path=path or "/",
                    handler=action,
                    framework="aspnetcore",
                    kind="aspnetcore-route" if route_path or class_prefix else "aspnetcore-conventional-action",
                    evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                    class_prefix=class_prefix or None,
                    parameters=_aspnet_path_parameters(path, file_fact.path, line),
                    response_type=return_type or None,
                )
            )
    routes.extend(_extract_aspnet_minimal_routes(file_fact, source, class_name))
    return _dedupe_routes_with_handler(routes)


def _extract_aspnet_map_controller_routes(file_fact: FileFact, source: str) -> list[ApiRouteFact]:
    if "MapControllerRoute" not in source and "MapDynamicControllerRoute" not in source:
        return []
    string_values = _aspnet_local_string_values(source)
    routes: list[ApiRouteFact] = []
    for match in ASPNET_MAP_CONTROLLER_ROUTE_RE.finditer(source):
        open_index = source.find("(", match.start(), match.end() + 2)
        if open_index < 0:
            continue
        close_index = _find_matching_paren(source, open_index)
        if close_index is None:
            continue
        args_source = source[open_index + 1 : close_index]
        args = _split_params(args_source)
        pattern_value = _aspnet_named_arg(args, "pattern")
        if pattern_value is None and len(args) >= 2:
            pattern_value = args[1]
        pattern = _aspnet_route_pattern_value(pattern_value or "", string_values)
        if not pattern:
            continue
        controller = _aspnet_defaults_value(args_source, "controller")
        action = _aspnet_defaults_value(args_source, "action")
        route_path = _aspnet_route_pattern_path(pattern)
        line = _line_for_offset(source, match.start())
        routes.append(
            ApiRouteFact(
                method="ANY",
                path=route_path,
                handler=f"{controller}#{action}" if controller and action else None,
                framework="aspnetcore",
                kind="aspnetcore-map-controller-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                parameters=_aspnet_path_parameters(route_path, file_fact.path, line),
            )
        )
    for match in ASPNET_MAP_DYNAMIC_CONTROLLER_ROUTE_RE.finditer(source):
        open_index = source.find("(", match.start(), match.end() + 2)
        if open_index < 0:
            continue
        close_index = _find_matching_paren(source, open_index)
        if close_index is None:
            continue
        args = _split_params(source[open_index + 1 : close_index])
        if not args:
            continue
        pattern = _aspnet_route_pattern_value(args[0], string_values)
        if not pattern:
            continue
        route_path = _aspnet_route_pattern_path(pattern)
        line = _line_for_offset(source, match.start())
        routes.append(
            ApiRouteFact(
                method="ANY",
                path=route_path,
                handler=match.group("transformer").strip().split(".")[-1],
                framework="aspnetcore",
                kind="aspnetcore-map-dynamic-controller-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                parameters=_aspnet_path_parameters(route_path, file_fact.path, line),
            )
        )
    return routes


def _aspnet_named_arg(args: list[str], name: str) -> str | None:
    pattern = re.compile(rf"^\s*{re.escape(name)}\s*:\s*(?P<value>[\s\S]+)$", re.IGNORECASE)
    for arg in args:
        match = pattern.match(arg)
        if match:
            return match.group("value").strip()
    return None


def _aspnet_defaults_value(source: str, name: str) -> str | None:
    match = re.search(rf"\b{re.escape(name)}\s*=\s*(?P<value>[^,}}\n]+)", source)
    if not match:
        return None
    value = match.group("value").strip()
    if value == "AreaNames.ADMIN":
        return "Admin"
    if value.endswith(".ADMIN"):
        return "Admin"
    return _aspnet_string_value(value) or value.split(".")[-1].strip()


def _aspnet_string_value(value: str) -> str | None:
    stripped = value.strip()
    if not stripped:
        return None
    while stripped and stripped[0] in {"$", "@"}:
        stripped = stripped[1:].strip()
    if len(stripped) >= 2 and stripped[0] in {"'", '"'}:
        quote = stripped[0]
        end = stripped.rfind(quote)
        if end > 0:
            return stripped[1:end]
    return None


def _aspnet_local_string_values(source: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for match in ASPNET_LOCAL_STRING_RE.finditer(source):
        value = _aspnet_string_value(match.group("value"))
        if value is not None:
            values[match.group("name")] = value
    return values


def _aspnet_route_pattern_value(value: str, string_values: dict[str, str]) -> str | None:
    literal = _aspnet_string_value(value)
    if literal is not None:
        return literal
    stripped = value.strip()
    if re.fullmatch(r"[A-Za-z_]\w*", stripped):
        return string_values.get(stripped)
    return None


def _aspnet_route_pattern_path(pattern: str) -> str:
    normalized = pattern.strip()
    normalized = re.sub(r"\{GetLanguageRoutePattern\(\)\}", "{lang}", normalized)
    normalized = re.sub(
        r"\{+\s*NopRoutingDefaults\.RouteValue\.(?P<name>[A-Za-z_]\w*)(?:[:=][^{}]*)?\}+",
        lambda match: "{" + _aspnet_route_value_name(match.group("name")) + "}",
        normalized,
    )
    normalized = normalized.replace("{{", "{").replace("}}", "}")
    normalized = re.sub(r"\{([^}:=?]+)(?::[^}]+)?\??\}", r"{\1}", normalized)
    normalized = re.sub(r"\{([^}=]+)=[^}]+\}", r"{\1}", normalized)
    normalized = normalized.strip("/")
    return _ensure_slash(normalized)


def _aspnet_route_value_name(name: str) -> str:
    aliases = {
        "Language": "lang",
        "SeName": "seName",
        "CatalogSeName": "catalogSeName",
    }
    if name in aliases:
        return aliases[name]
    return name[:1].lower() + name[1:] if name else name


def _aspnet_area_name(source: str) -> str | None:
    match = ASPNET_AREA_ATTR_RE.search(source)
    if not match:
        return None
    value = match.group("value").strip()
    if value == "AreaNames.ADMIN" or value.endswith(".ADMIN"):
        return "Admin"
    return _aspnet_string_value(value)


def _aspnet_action_name(attrs: str) -> str | None:
    match = ASPNET_ACTION_NAME_RE.search(attrs)
    return match.group("name") if match else None


def _aspnet_conventional_action_path(file_path: str, class_name: str, action: str, area: str | None) -> str:
    controller = class_name.removesuffix("Controller")
    inferred_area = area or _aspnet_area_from_path(file_path)
    if inferred_area:
        return _join_paths(_join_paths("", inferred_area), f"{controller}/{action}")
    return _join_paths("", f"{controller}/{action}")


def _aspnet_area_from_path(file_path: str) -> str | None:
    normalized = file_path.replace("\\", "/")
    match = re.search(r"/Areas/([^/]+)/Controllers/", f"/{normalized}", re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"/(Admin)/Controllers/", f"/{normalized}", re.IGNORECASE)
    return match.group(1) if match else None


def _extract_aspnet_minimal_routes(file_fact: FileFact, source: str, class_name: str) -> list[ApiRouteFact]:
    if ".Map" not in source:
        return []
    group_prefixes = _aspnet_group_prefixes(source, class_name)
    routes: list[ApiRouteFact] = []
    for match in ASPNET_MINIMAL_MAP_RE.finditer(source):
        prefix = group_prefixes.get(match.group("receiver"))
        if prefix is None:
            if not _looks_like_aspnet_route_builder_receiver(source, match.group("receiver")):
                continue
            prefix = ""
        args = _split_params(match.group("args"))
        path, handler = _aspnet_minimal_path_and_handler(args)
        line = _line_for_offset(source, match.start())
        response_type = _aspnet_minimal_response_type(source, match.end())
        request_body = _aspnet_minimal_request_body(args)
        for method in _aspnet_minimal_methods(match.group("method"), args):
            routes.append(
                ApiRouteFact(
                    method=method,
                    path=_join_paths(prefix, path),
                    handler=handler or class_name,
                    framework="aspnetcore",
                    kind="aspnetcore-minimal-route",
                    evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                    class_prefix=prefix,
                    parameters=_aspnet_path_parameters(_join_paths(prefix, path), file_fact.path, line),
                    request_body=request_body,
                    response_type=response_type,
                )
            )
    return routes


def _looks_like_aspnet_route_builder_receiver(source: str, receiver: str) -> bool:
    if receiver in {"app", "endpoints", "routes", "builder"}:
        return True
    pattern = rf"\bIEndpointRouteBuilder\s+{re.escape(receiver)}\b"
    return re.search(pattern, source) is not None


def _aspnet_minimal_response_type(source: str, offset: int) -> str | None:
    chain = source[offset : offset + 500]
    match = re.search(r"\.Produces\s*<\s*(?P<type>[^>]+)\s*>\s*\(", chain)
    return " ".join(match.group("type").split()) if match else None


def _aspnet_minimal_request_body(args: list[str]) -> str | None:
    joined = " ".join(args[1:])
    match = re.search(r"\((?P<params>[^)]*)\)\s*=>", joined)
    if not match:
        return None
    for param in _split_params(match.group("params")):
        cleaned = re.sub(r"\[[^\]]+\]\s*", "", param).strip()
        pieces = cleaned.split()
        if len(pieces) < 2:
            continue
        type_name = pieces[-2].strip()
        if type_name in {"int", "long", "Guid", "string", "bool", "IRepository<CatalogItem>", "IResult"}:
            continue
        if type_name.endswith(("Request", "Command", "Dto", "DTO")):
            return type_name
    return None


def _aspnet_path_parameters(path: str, file_path: str, line: int) -> list[RequestParamFact]:
    return [
        RequestParamFact(
            name=name.split(":", 1)[0],
            source="path",
            type=None,
            required=True,
            evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
        )
        for name in re.findall(r"\{([^}]+)\}", path)
    ]


def _aspnet_group_prefixes(source: str, class_name: str) -> dict[str, str]:
    prefixes: dict[str, str] = {}
    for match in ASPNET_MAP_GROUP_RE.finditer(source):
        parent_prefix = prefixes.get(match.group("parent"), "")
        prefixes[match.group("name")] = _join_paths(parent_prefix, match.group("path"))
    if "IEndpointGroup" in source:
        for match in re.finditer(r"\bMap\s*\(\s*(?P<receiver>[A-Za-z_]\w*)\s+(?P<name>[A-Za-z_]\w*)\s*\)", source):
            prefixes[match.group("name")] = _aspnet_endpoint_group_prefix(source, class_name)
    return prefixes


def _aspnet_endpoint_group_prefix(source: str, class_name: str) -> str:
    override = re.search(r"\bRoutePrefix\s*=>\s*['\"](?P<path>/[^'\"]*)['\"]", source)
    if override:
        return override.group("path")
    return f"/api/{class_name}"


def _aspnet_minimal_path_and_handler(args: list[str]) -> tuple[str, str | None]:
    path = "/"
    handler: str | None = None
    remaining = args
    if args:
        quoted = _quoted_value(args[0])
        if quoted is not None:
            path = quoted or "/"
            remaining = args[1:]
    for item in remaining:
        candidate = item.strip()
        if not candidate or candidate.startswith("new[]") or candidate.startswith("new "):
            continue
        quoted = _quoted_value(candidate)
        if quoted is not None:
            path = quoted or "/"
            continue
        name_match = re.search(r"\b([A-Za-z_]\w*)\b", candidate)
        if name_match and handler is None:
            handler = name_match.group(1)
    return path, handler


def _aspnet_minimal_methods(method: str, args: list[str]) -> list[str]:
    if method.lower() != "methods":
        return [method.upper()]
    found: list[str] = []
    for item in args[1:2]:
        found.extend(re.findall(r"['\"](GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)['\"]", item, re.IGNORECASE))
    return [item.upper() for item in found] or ["ANY"]


def _extract_axum_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    if "axum" not in source and ".route(" not in source:
        return []
    routes: list[ApiRouteFact] = []
    for match in AXUM_ROUTE_RE.finditer(source):
        path = match.group("path")
        chain = match.group("chain")
        line = _line_for_offset(source, match.start())
        for method_match in AXUM_METHOD_CALL_RE.finditer(chain):
            routes.append(
                ApiRouteFact(
                    method=method_match.group("method").upper(),
                    path=path,
                    handler=method_match.group("handler"),
                    framework="axum",
                    kind="axum-route",
                    evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                )
            )
    return routes


def _extract_hyper_match_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    if "req.method()" not in source or "req.uri().path()" not in source or "Method::" not in source:
        return []
    routes: list[ApiRouteFact] = []
    for match in HYPER_MATCH_ROUTE_RE.finditer(source):
        if _offset_is_rust_inert(source, match.start()):
            continue
        block_start = source.find("{", match.end() - 1)
        block_end = _find_matching_brace(source, block_start)
        body = source[block_start + 1 : block_end] if block_start >= 0 and block_end is not None else source[match.end() : match.end() + 900]
        line = _line_for_offset(source, match.start())
        routes.append(
            ApiRouteFact(
                method=match.group("method").upper(),
                path=match.group("path"),
                handler=_hyper_match_handler(file_fact.path, body),
                framework="hyper",
                kind="hyper-match-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                request_body="body" if "req.into_body()" in body else None,
                response_type="Response" if "Response" in body or "into_response" in body else None,
            )
        )
    return _dedupe_routes(routes)


def _hyper_match_handler(file_path: str, body: str) -> str | None:
    for match in RUST_QUALIFIED_CALL_RE.finditer(body):
        handler = match.group("handler")
        if handler.startswith(("Ok::", "Err::", "Response::", "StatusCode::")):
            continue
        if any(part[:1].isupper() for part in handler.split("::")):
            continue
        return handler
    for match in RUST_FUNCTION_CALL_RE.finditer(body):
        handler = match.group("handler")
        if handler in {"Ok", "Err", "Some", "None", "Response", "return"}:
            continue
        return _rust_module_handler(file_path, handler)
    return None


def _extract_actix_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    if "actix_web" not in source and "web::resource" not in source and "web::scope" not in source:
        return []
    routes: list[ApiRouteFact] = []
    for match in ACTIX_RESOURCE_RE.finditer(source):
        path = _join_paths(_actix_scope_prefix(source, match.start()), match.group("path"))
        block = _actix_enclosing_service_block(source, match.start()) or source[match.start() : match.start() + 900]
        line = _line_for_offset(source, match.start())
        method_routes = 0
        for route_match in ACTIX_ROUTE_METHOD_RE.finditer(block):
            method_routes += 1
            routes.append(
                ApiRouteFact(
                    method=route_match.group("method").upper(),
                    path=path,
                    handler=route_match.group("handler"),
                    framework="actix-web",
                    kind="actix-resource-route",
                    evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                )
            )
        if method_routes == 0:
            to_match = ACTIX_TO_RE.search(block)
            if to_match:
                routes.append(
                    ApiRouteFact(
                        method="ANY",
                        path=path,
                        handler=to_match.group("handler"),
                        framework="actix-web",
                        kind="actix-resource-route",
                        evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                    )
                )
    for match in ACTIX_ATTR_ROUTE_RE.finditer(source):
        line = _line_for_offset(source, match.start())
        routes.append(
            ApiRouteFact(
                method=match.group("method").upper(),
                path=match.group("path"),
                handler=_actix_function_after(source, match.end()),
                framework="actix-web",
                kind="actix-attribute-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
            )
        )
    return _dedupe_routes(routes)


def _actix_scope_prefix(source: str, offset: int) -> str:
    prefix = ""
    for match in ACTIX_SCOPE_RE.finditer(source):
        if match.start() > offset:
            break
        span = _actix_enclosing_service_span(source, match.start())
        if span is not None and span[0] <= offset <= span[1]:
            prefix = _join_paths(prefix, match.group("path"))
    return prefix


def _actix_enclosing_service_block(source: str, offset: int) -> str | None:
    span = _actix_enclosing_service_span(source, offset)
    if span is None:
        return None
    return source[span[0] : span[1] + 1]


def _actix_enclosing_service_span(source: str, offset: int) -> tuple[int, int] | None:
    candidates: list[tuple[int, int]] = []
    for match in re.finditer(r"\.service\(", source):
        if match.start() > offset:
            break
        open_index = source.find("(", match.start())
        close_index = _find_matching_paren(source, open_index)
        if close_index is not None and match.start() <= offset <= close_index:
            candidates.append((match.start(), close_index))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])


def _actix_function_after(source: str, offset: int) -> str | None:
    match = re.search(r"\b(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?fn\s+(?P<name>[A-Za-z_]\w*)\b", source[offset:])
    return match.group("name") if match else None


def _extract_rocket_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    if "rocket" not in source and "#[get(" not in source and "#[post(" not in source:
        return []
    routes: list[ApiRouteFact] = []
    for match in ROCKET_ATTR_ROUTE_RE.finditer(source):
        handler = _actix_function_after(source, match.end())
        raw_path = match.group("path")
        line = _line_for_offset(source, match.start())
        path, parameters = _rocket_path_and_parameters(raw_path, file_fact.path, line)
        request_body = _rocket_request_body(match.group("args") or "")
        routes.append(
            ApiRouteFact(
                method=match.group("method").upper(),
                path=path,
                handler=_rust_module_handler(file_fact.path, handler) if handler else None,
                framework="rocket",
                kind="rocket-attribute-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                parameters=parameters,
                request_body=request_body,
            )
        )
    return _dedupe_routes(routes)


def _rocket_path_and_parameters(raw_path: str, file_path: str, line: int) -> tuple[str, list[RequestParamFact]]:
    path, _, query = raw_path.partition("?")
    parameters: list[RequestParamFact] = []
    for name in re.findall(r"<([A-Za-z_]\w*)>", path):
        parameters.append(
            RequestParamFact(
                name=name,
                source="path",
                type=None,
                required=True,
                evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
            )
        )
    for name in re.findall(r"<([A-Za-z_]\w*)\.\.>", query):
        parameters.append(
            RequestParamFact(
                name=name,
                source="query",
                type=None,
                required=False,
                evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
            )
        )
    return path or "/", parameters


def _rocket_request_body(args: str) -> str | None:
    match = re.search(r"\bdata\s*=\s*\"<(?P<name>[A-Za-z_]\w*)>\"", args)
    return match.group("name") if match else None


def _rust_module_handler(path: str, handler: str | None) -> str | None:
    if not handler:
        return None
    normalized = path.replace("\\", "/")
    if normalized.startswith("src/"):
        normalized = normalized.removeprefix("src/")
    elif "/src/" in f"/{normalized}":
        normalized = f"/{normalized}".split("/src/", 1)[1]
    normalized = normalized.removesuffix(".rs")
    if normalized.endswith("/mod"):
        normalized = normalized.removesuffix("/mod")
    modules = [part for part in normalized.split("/") if part and part not in {"lib", "main"}]
    return "::".join([*modules, handler]) if modules else handler


def _apply_rocket_mount_prefixes(root: Path, files: list[FileFact], routes: list[ApiRouteFact]) -> list[ApiRouteFact]:
    prefixes = _rocket_mount_prefixes(root, files)
    if not prefixes:
        return routes
    updated: list[ApiRouteFact] = []
    for route in routes:
        if route.framework != "rocket" or not route.handler:
            updated.append(route)
            continue
        prefix = prefixes.get(route.handler) or prefixes.get(route.handler.split("::")[-1])
        updated.append(replace(route, path=_join_paths(prefix, route.path)) if prefix else route)
    return updated


def _rocket_mount_prefixes(root: Path, files: list[FileFact]) -> dict[str, str]:
    prefixes: dict[str, str] = {}
    for file_fact in files:
        if file_fact.language != "rust" or file_fact.role in {"test", "sample", "generated"}:
            continue
        source = _read(root, file_fact)
        for match in ROCKET_MOUNT_RE.finditer(source):
            open_index = source.find("[", match.end() - 1)
            close_index = _find_matching_square(source, open_index)
            if close_index is None:
                continue
            prefix = _join_paths("", match.group("prefix"))
            body = source[open_index + 1 : close_index]
            for handler in re.findall(r"\b[A-Za-z_]\w*(?:::[A-Za-z_]\w*)+\b", body):
                prefixes[handler] = prefix
                prefixes[handler.split("::")[-1]] = prefix
    return prefixes


def _extract_warp_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    if "warp::path!" not in source and "warp::path::" not in source:
        return []
    routes: list[ApiRouteFact] = []
    for match in WARP_PATH_ROUTE_RE.finditer(source):
        path, parameters = _warp_path_and_parameters(match.group("path"), file_fact.path, _line_for_offset(source, match.start()))
        chain = match.group("chain")
        line = _line_for_offset(source, match.start())
        routes.append(
            ApiRouteFact(
                method=_warp_method(chain),
                path=path,
                handler=match.group("handler"),
                framework="warp",
                kind="warp-filter-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                parameters=[
                    *parameters,
                    *_warp_chain_parameters(chain, file_fact.path, line),
                ],
                request_body="json" if "warp::body::json" in chain else None,
            )
        )
    if re.search(r"\bwarp::path::end\(\)[\s\S]{0,160}\.map\(", source):
        match = re.search(r"\bwarp::path::end\(\)(?P<chain>[\s\S]{0,200}?)\.map\(\s*(?P<handler>[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*)", source)
        if match:
            line = _line_for_offset(source, match.start())
            routes.append(
                ApiRouteFact(
                    method="GET",
                    path="/",
                    handler=match.group("handler"),
                    framework="warp",
                    kind="warp-filter-route",
                    evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                )
            )
    return _dedupe_routes(routes)


def _extract_tauri_commands(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    if "command" not in source or not _looks_like_tauri_command_source(file_fact.path, source):
        return []
    routes: list[ApiRouteFact] = []
    plugin_namespace = _tauri_plugin_namespace(file_fact.path)
    for match in TAURI_COMMAND_RE.finditer(source):
        if _offset_is_rust_inert(source, match.start()):
            continue
        if not match.group("qualified") and not _unqualified_command_is_tauri(file_fact.path, source):
            continue
        line = _line_for_offset(source, match.start())
        command_name = _tauri_command_name(match.group("name"), match.group("args") or "")
        endpoint = f"plugin:{plugin_namespace}|{command_name}" if plugin_namespace else command_name
        routes.append(
            ApiRouteFact(
                method="TAURI",
                path=f"tauri#{endpoint}",
                handler=_rust_module_handler(file_fact.path, match.group("name")),
                framework="tauri",
                kind="tauri-plugin-command" if plugin_namespace else "tauri-command",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                parameters=_tauri_command_params(match.group("params") or "", file_fact.path, line),
                response_type=_clean_rust_return_type(match.group("return")),
            )
        )
    routes.extend(_extract_tauri_macro_commands(file_fact, source, plugin_namespace))
    return _dedupe_routes(routes)


def _extract_tauri_macro_commands(
    file_fact: FileFact,
    source: str,
    plugin_namespace: str | None,
) -> list[ApiRouteFact]:
    if not plugin_namespace or not {"getter!", "setter!"} & {token for token in ("getter!", "setter!") if token in source}:
        return []
    routes: list[ApiRouteFact] = []
    for match in TAURI_MACRO_COMMAND_RE.finditer(source):
        if _offset_is_rust_inert(source, match.start()):
            continue
        parts = _tauri_macro_parts(match.group("body"))
        if not parts or parts[0].startswith("$"):
            continue
        command_name = parts[0]
        line = _line_for_offset(source, match.start())
        macro = match.group("macro")
        response_type = _tauri_macro_response_type(macro, parts)
        routes.append(
            ApiRouteFact(
                method="TAURI",
                path=f"tauri#plugin:{plugin_namespace}|{command_name}",
                handler=_rust_module_handler(file_fact.path, command_name),
                framework="tauri",
                kind="tauri-plugin-macro-command",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                parameters=_tauri_macro_params(macro, parts, file_fact.path, line),
                response_type=response_type,
            )
        )
    return routes


def _tauri_macro_parts(body: str) -> list[str]:
    return [" ".join(part.strip().split()) for part in _split_top_level_commas(body) if part.strip()]


def _tauri_macro_response_type(macro: str, parts: list[str]) -> str | None:
    if macro == "getter":
        if len(parts) >= 3:
            return parts[2]
        if len(parts) == 2:
            return parts[1]
        return None
    return "crate::Result<()>"


def _tauri_macro_params(macro: str, parts: list[str], file_path: str, line: int) -> list[RequestParamFact]:
    if macro != "setter":
        return []
    type_hint: str | None = None
    if len(parts) >= 3:
        type_hint = parts[2]
    elif len(parts) == 2 and _looks_like_rust_type(parts[1]):
        type_hint = parts[1]
    if not type_hint:
        return []
    return [
        RequestParamFact(
            name="value",
            source="invoke-arg",
            type=type_hint,
            required=None,
            evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
        )
    ]


def _looks_like_rust_type(value: str) -> bool:
    return bool(
        value.startswith(("&", "Option<", "Vec<"))
        or value in {"bool", "String", "str", "usize", "u8", "u16", "u32", "u64", "i8", "i16", "i32", "i64", "f32", "f64"}
        or re.match(r"[A-Z][A-Za-z0-9_:<>]*(?:<.*>)?$", value) is not None
    )


def _looks_like_tauri_command_source(path: str, source: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return (
        "tauri::command" in source
        or "generate_handler!" in source
        or "tauri::Builder" in source
        or "TauriPlugin" in source
        or re.search(r"\buse\s+(?:tauri|crate)::?\s*[\s\S]{0,180}\bcommand\b", source) is not None
        or "/src-tauri/" in f"/{normalized}"
        or normalized.startswith("src-tauri/")
        or re.search(r"(?:^|/)tauri-plugin-[^/]+/", normalized) is not None
    )


def _unqualified_command_is_tauri(path: str, source: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return (
        re.search(r"\buse\s+(?:tauri|crate)::?\s*[\s\S]{0,180}\bcommand\b", source) is not None
        or "generate_handler!" in source
        or "TauriPlugin" in source
        or "/src-tauri/" in f"/{normalized}"
        or normalized.startswith("src-tauri/")
        or re.search(r"(?:^|/)tauri-plugin-[^/]+/", normalized) is not None
    )


def _tauri_command_name(function_name: str, args: str) -> str:
    rename = _first_match(args, r"\brename\s*=\s*['\"]([^'\"]+)['\"]")
    return rename or function_name


def _tauri_plugin_namespace(path: str) -> str | None:
    normalized = path.replace("\\", "/").lower()
    parts = [part for part in normalized.split("/") if part]
    if len(parts) >= 2 and parts[-1] == "plugin.rs" and parts[-2] not in {"src", "tauri"}:
        return parts[-2]
    plugin_match = re.search(r"(?:^|/)tauri-plugin-([^/]+)/", normalized)
    if plugin_match:
        return plugin_match.group(1)
    return None


def _tauri_command_params(params_source: str, file_path: str, line: int) -> list[RequestParamFact]:
    params: list[RequestParamFact] = []
    for raw_param in _split_top_level_commas(params_source):
        if ":" not in raw_param:
            continue
        name, type_hint = raw_param.split(":", 1)
        name = name.strip().removeprefix("mut ").strip()
        type_hint = " ".join(type_hint.strip().split())
        if not name or _tauri_param_is_runtime_injected(name, type_hint):
            continue
        params.append(
            RequestParamFact(
                name=name,
                source="invoke-arg",
                type=type_hint or None,
                required=None,
                evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
            )
        )
    return params


def _tauri_param_is_runtime_injected(name: str, type_hint: str) -> bool:
    if name in {"app", "handle", "window", "webview", "state", "manager"}:
        return True
    return any(token in type_hint for token in ("AppHandle", "Window", "Webview", "State<", "Manager", "Runtime"))


def _clean_rust_return_type(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = " ".join(value.split())
    cleaned = cleaned.split(" where ", 1)[0].strip()
    return cleaned or None


def _offset_is_rust_inert(source: str, offset: int) -> bool:
    index = 0
    line_comment = False
    block_depth = 0
    quote: str | None = None
    escaped = False
    raw_hashes: int | None = None
    while index < offset:
        char = source[index]
        next_char = source[index + 1] if index + 1 < len(source) else ""
        if line_comment:
            if char == "\n":
                line_comment = False
            index += 1
            continue
        if block_depth:
            if char == "/" and next_char == "*":
                block_depth += 1
                index += 2
                continue
            if char == "*" and next_char == "/":
                block_depth -= 1
                index += 2
                continue
            index += 1
            continue
        if raw_hashes is not None:
            if char == '"' and source.startswith("#" * raw_hashes, index + 1):
                index += raw_hashes + 1
                raw_hashes = None
                continue
            index += 1
            continue
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char == "/" and next_char == "/":
            line_comment = True
            index += 2
            continue
        if char == "/" and next_char == "*":
            block_depth = 1
            index += 2
            continue
        raw_match = re.match(r"r(#+)?\"", source[index : index + 18])
        if raw_match:
            raw_hashes = len(raw_match.group(1) or "")
            index += raw_hashes + 2
            continue
        if char == '"':
            quote = char
        index += 1
    return line_comment or block_depth > 0 or quote is not None or raw_hashes is not None


def _warp_path_and_parameters(raw_path: str, file_path: str, line: int) -> tuple[str, list[RequestParamFact]]:
    segments: list[str] = []
    parameters: list[RequestParamFact] = []
    param_index = 1
    for part in raw_path.split("/"):
        token = part.strip()
        if not token:
            continue
        quoted = _quoted_value(token)
        if quoted is not None:
            segments.append(quoted)
            continue
        type_name = token.split("::")[-1]
        name = f"param{param_index}"
        param_index += 1
        segments.append(f"{{{name}}}")
        parameters.append(
            RequestParamFact(
                name=name,
                source="path",
                type=type_name,
                required=True,
                evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
            )
        )
    return _join_paths("", "/".join(segments)), parameters


def _warp_chain_parameters(chain: str, file_path: str, line: int) -> list[RequestParamFact]:
    parameters: list[RequestParamFact] = []
    if "warp::query()" in chain:
        parameters.append(
            RequestParamFact(
                name="query",
                source="query",
                type=None,
                required=False,
                evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
            )
        )
    for header in re.findall(r"warp::header(?:::optional)?\(\s*['\"]([^'\"]+)['\"]\s*\)", chain):
        parameters.append(
            RequestParamFact(
                name=header,
                source="header",
                type=None,
                required="optional" not in chain,
                evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
            )
        )
    return parameters


def _warp_method(chain: str) -> str:
    match = re.search(r"warp::(get|post|put|delete|patch|head|options)\(\)", chain)
    return match.group(1).upper() if match else "ANY"


def _extract_spring_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    code = _java_mask_comments_preserving_offsets(source)
    routes: list[ApiRouteFact] = []
    for class_match in JAVA_CLASS_RE.finditer(code):
        class_body_start = class_match.end()
        class_body_end = _find_matching_brace(code, class_body_start - 1)
        if class_body_end is None:
            continue
        class_block = _annotation_block_before(code, class_match.start())
        if not _looks_like_spring_controller(class_block, code[class_body_start:class_body_end]):
            continue
        class_prefix = _spring_path_from_annotations(class_block)
        class_body = code[class_body_start:class_body_end]
        for route_match in SPRING_ROUTE_RE.finditer(class_body):
            absolute_start = class_body_start + route_match.start()
            absolute_end = class_body_start + route_match.end()
            args = route_match.group("args") or ""
            method_path = _spring_path_from_args(args)
            full_path = _join_paths(class_prefix, method_path)
            line = _line_for_offset(source, absolute_start)
            method_info = _java_method_after(source, absolute_end, file_fact.path, line)
            methods = _spring_methods(route_match.group("annotation"), args)
            for method in methods:
                routes.append(
                    ApiRouteFact(
                        method=method,
                        path=full_path,
                        handler=method_info["name"],
                        framework="spring",
                        kind="spring-route",
                        evidence=Evidence(
                            file=file_fact.path,
                            kind="backend-route",
                            line_start=line,
                            line_end=line,
                        ),
                        class_prefix=class_prefix or None,
                        parameters=method_info["parameters"],
                        request_body=method_info["request_body"],
                        response_type=method_info["response_type"],
                    )
                )
    return routes


def _extract_spring_openapi_operation_routes(
    root: Path,
    files: list[FileFact],
    routes: list[ApiRouteFact],
) -> list[ApiRouteFact]:
    openapi_routes = [
        route
        for route in routes
        if route.framework == "openapi" and route.handler and route.kind == "openapi-spec-route"
    ]
    if not openapi_routes:
        return []
    methods_by_name = _spring_controller_methods_by_name(root, files)
    synthetic: list[ApiRouteFact] = []
    for route in openapi_routes:
        matches = methods_by_name.get(route.handler or "")
        if not matches or len(matches) != 1:
            continue
        method_info = matches[0]
        full_path = _join_openapi_operation_path(method_info["class_prefix"], route.path)
        if any(
            existing.framework == "spring"
            and existing.method == route.method
            and existing.path == full_path
            for existing in routes
        ):
            continue
        handler_file = method_info["file"]
        handler_line = method_info["line"]
        synthetic.append(
            ApiRouteFact(
                method=route.method,
                path=full_path,
                handler=route.handler,
                framework="spring",
                kind="spring-openapi-operation-route",
                evidence=Evidence(
                    file=route.evidence.file,
                    kind="backend-route",
                    line_start=route.evidence.line_start,
                    line_end=route.evidence.line_end,
                    note=f"handler:{handler_file}:{handler_line}",
                ),
                class_prefix=method_info["class_prefix"] or None,
                parameters=route.parameters,
                request_body=route.request_body,
                response_type=method_info["response_type"] or route.response_type,
            )
        )
    return synthetic


def _spring_controller_methods_by_name(root: Path, files: list[FileFact]) -> dict[str, list[dict[str, object]]]:
    methods_by_name: dict[str, list[dict[str, object]]] = {}
    for file_fact in files:
        if file_fact.language != "java" or file_fact.role in {"test", "sample", "generated"}:
            continue
        source = _read(root, file_fact)
        code = _java_mask_comments_preserving_offsets(source)
        for class_match in JAVA_CLASS_RE.finditer(code):
            class_body_start = class_match.end()
            class_body_end = _find_matching_brace(code, class_body_start - 1)
            if class_body_end is None:
                continue
            class_block = _annotation_block_before(code, class_match.start())
            class_body = code[class_body_start:class_body_end]
            if not _looks_like_spring_controller(class_block, class_body):
                continue
            class_prefix = _spring_path_from_annotations(class_block)
            for method_info in _java_methods_in_range(source, class_body_start, class_body_end, file_fact.path):
                name = str(method_info["name"])
                methods_by_name.setdefault(name, []).append({**method_info, "class_prefix": class_prefix})
    return methods_by_name


def _java_methods_in_range(source: str, start: int, end: int, file_path: str) -> list[dict[str, object]]:
    methods: list[dict[str, object]] = []
    body = source[start:end]
    for match in JAVA_METHOD_DECL_RE.finditer(body):
        absolute_start = start + match.start()
        line = _line_for_offset(source, absolute_start)
        methods.append(_java_method_info_from_match(source, match, start, file_path, line))
    return methods


def _join_openapi_operation_path(prefix: object, path: str) -> str:
    prefix_text = str(prefix or "")
    normalized_prefix = _join_paths("", prefix_text) if prefix_text else ""
    normalized_path = _join_paths("", path)
    if normalized_prefix and (
        normalized_path == normalized_prefix or normalized_path.startswith(f"{normalized_prefix.rstrip('/')}/")
    ):
        return normalized_path
    return _join_paths(normalized_prefix, normalized_path)


def _extract_web_servlet_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    routes: list[ApiRouteFact] = []
    for match in WEB_SERVLET_RE.finditer(source):
        args = match.group("args") or ""
        paths = _dedupe(item.group("path") for item in QUOTED_PATH_RE.finditer(args))
        if not paths:
            continue
        class_match = re.search(r"\bclass\s+([A-Za-z_]\w*)", source[match.end() : match.end() + 500])
        handler = class_match.group(1) if class_match else Path(file_fact.path).stem
        line = _line_for_offset(source, match.start())
        for path in paths:
            routes.append(
                ApiRouteFact(
                    method="ANY",
                    path=path,
                    handler=handler,
                    framework="servlet",
                    kind="webservlet-route",
                    evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                )
            )
    return routes


def _extract_web_xml_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    path = root / file_fact.path
    source = path.read_text(encoding="utf-8", errors="ignore")
    try:
        document = ET.fromstring(source)
    except ET.ParseError:
        return []
    namespace = _namespace(document.tag)
    classes_by_name: dict[str, str | None] = {}
    for servlet in document.findall(f".//{namespace}servlet"):
        name = _find_text(servlet, namespace, "servlet-name")
        class_name = _find_text(servlet, namespace, "servlet-class")
        if name:
            classes_by_name[name] = class_name

    routes: list[ApiRouteFact] = []
    for mapping in document.findall(f".//{namespace}servlet-mapping"):
        name = _find_text(mapping, namespace, "servlet-name")
        if not name:
            continue
        for pattern in mapping.findall(f"{namespace}url-pattern"):
            if not pattern.text or not pattern.text.strip():
                continue
            route_path = pattern.text.strip()
            line = _line_for_text(source, route_path)
            routes.append(
                ApiRouteFact(
                    method="ANY",
                    path=route_path,
                    handler=classes_by_name.get(name) or name,
                    framework="servlet",
                    kind="web-xml-route",
                    evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                )
            )
    return routes


def _extract_openapi_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    if not _looks_like_openapi_spec(source):
        return []
    if file_fact.language == "json":
        return _extract_openapi_json_routes(file_fact, source)
    return _extract_openapi_yaml_routes(file_fact, source)


def _extract_openapi_json_routes(file_fact: FileFact, source: str) -> list[ApiRouteFact]:
    try:
        document = json.loads(source)
    except json.JSONDecodeError:
        return []
    if not isinstance(document, dict):
        return []
    paths = document.get("paths")
    if not isinstance(paths, dict):
        return []
    routes: list[ApiRouteFact] = []
    for api_path, path_item in paths.items():
        if not isinstance(api_path, str) or not isinstance(path_item, dict):
            continue
        inherited_parameters = path_item.get("parameters") if isinstance(path_item.get("parameters"), list) else []
        for raw_method, operation in path_item.items():
            method = str(raw_method).lower()
            if method not in OPENAPI_METHODS or not isinstance(operation, dict):
                continue
            line = _line_for_text(source, f'"{api_path}"')
            operation_parameters = operation.get("parameters") if isinstance(operation.get("parameters"), list) else []
            parameters = _openapi_json_parameters(
                [*inherited_parameters, *operation_parameters],
                file_fact.path,
                line,
            )
            routes.append(
                ApiRouteFact(
                    method=method.upper(),
                    path=api_path,
                    handler=_string_or_none(operation.get("operationId")),
                    framework="openapi",
                    kind="openapi-spec-route",
                    evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                    parameters=parameters,
                    request_body=_openapi_json_request_body(operation),
                    response_type=_openapi_json_response_summary(operation),
                )
            )
    return routes


def _extract_openapi_yaml_routes(file_fact: FileFact, source: str) -> list[ApiRouteFact]:
    lines = source.splitlines()
    routes: list[ApiRouteFact] = []
    in_paths = False
    current_path: str | None = None
    for index, line in enumerate(lines):
        if re.match(r"^paths:\s*$", line):
            in_paths = True
            continue
        if not in_paths:
            continue
        if line and not line.startswith((" ", "\t")) and not line.startswith("paths:"):
            break
        path_match = re.match(
            r"^\s{2}(?:(?P<quote>['\"])(?P<quoted>/[^'\"]+)(?P=quote)|(?P<bare>/[^:\s]+)):\s*$",
            line,
        )
        if path_match:
            current_path = path_match.group("quoted") or path_match.group("bare")
            continue
        method_match = re.match(r"^\s{4}(?P<method>get|post|put|delete|patch|options|head):\s*$", line, re.IGNORECASE)
        if not method_match or not current_path:
            continue
        block = _indented_block(lines, index + 1, 4)
        routes.append(
            ApiRouteFact(
                method=method_match.group("method").upper(),
                path=current_path,
                handler=_first_yaml_value(block, "operationId"),
                framework="openapi",
                kind="openapi-spec-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=index + 1, line_end=index + 1),
                parameters=_openapi_yaml_parameters(block, file_fact.path, index + 1),
                request_body="requestBody" if re.search(r"^\s*requestBody:\s*$", block, re.MULTILINE) else None,
                response_type=_openapi_yaml_response_summary(block),
            )
        )
    return routes


def _looks_like_openapi_spec(source: str) -> bool:
    return bool(re.search(r"^\s*['\"]?(?:openapi|swagger)['\"]?\s*[:\"]", source[:5000], re.MULTILINE))


def _openapi_json_parameters(items: object, file_path: str, line: int) -> list[RequestParamFact]:
    if not isinstance(items, list):
        return []
    params: list[RequestParamFact] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = _string_or_none(item.get("name"))
        source = _string_or_none(item.get("in")) or "unknown"
        if not name:
            continue
        schema = item.get("schema") if isinstance(item.get("schema"), dict) else {}
        params.append(
            RequestParamFact(
                name=name,
                source=source,
                type=_openapi_schema_name(schema),
                required=item.get("required") if isinstance(item.get("required"), bool) else None,
                evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
            )
        )
    return params


def _openapi_yaml_parameters(block: str, file_path: str, line: int) -> list[RequestParamFact]:
    params: list[RequestParamFact] = []
    pattern = re.compile(
        r"^\s*-\s*name:\s*(?P<name>[A-Za-z0-9_.-]+)[\s\S]{0,500}?^\s*in:\s*(?P<source>[A-Za-z0-9_.-]+)",
        re.MULTILINE,
    )
    for match in pattern.finditer(block):
        params.append(
            RequestParamFact(
                name=match.group("name"),
                source=match.group("source"),
                type=None,
                required=None,
                evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
            )
        )
    return params


def _openapi_json_request_body(operation: dict[object, object]) -> str | None:
    request_body = operation.get("requestBody")
    if not isinstance(request_body, dict):
        for param in operation.get("parameters", []):
            if isinstance(param, dict) and param.get("in") == "body":
                return _string_or_none(param.get("name")) or "body"
        return None
    content = request_body.get("content")
    if isinstance(content, dict):
        for media_type, media_def in content.items():
            if not isinstance(media_def, dict):
                continue
            schema = media_def.get("schema") if isinstance(media_def.get("schema"), dict) else {}
            schema_name = _openapi_schema_name(schema)
            return f"{media_type}:{schema_name}" if schema_name else str(media_type)
    return "requestBody"


def _openapi_json_response_summary(operation: dict[object, object]) -> str | None:
    responses = operation.get("responses")
    if not isinstance(responses, dict):
        return None
    codes = [str(code) for code in responses.keys()]
    schema_names: list[str] = []
    for response in responses.values():
        if not isinstance(response, dict):
            continue
        content = response.get("content")
        if isinstance(content, dict):
            for media_def in content.values():
                if isinstance(media_def, dict):
                    schema = media_def.get("schema") if isinstance(media_def.get("schema"), dict) else {}
                    schema_name = _openapi_schema_name(schema)
                    if schema_name:
                        schema_names.append(schema_name)
    parts = [f"responses:{','.join(codes[:10])}"]
    if schema_names:
        parts.append(f"schemas:{','.join(_dedupe(schema_names)[:5])}")
    return "; ".join(parts)


def _openapi_yaml_response_summary(block: str) -> str | None:
    codes = re.findall(r"^\s*['\"]?(?P<code>\d{3}|[1-5]XX|default)['\"]?:\s*$", block, re.MULTILINE)
    if not codes:
        return None
    return f"responses:{','.join(_dedupe(codes)[:10])}"


def _openapi_schema_name(schema: object) -> str | None:
    if not isinstance(schema, dict):
        return None
    ref = schema.get("$ref")
    if isinstance(ref, str):
        return ref.rsplit("/", 1)[-1]
    schema_type = schema.get("type")
    return str(schema_type) if schema_type else None


def _indented_block(lines: list[str], start_index: int, parent_indent: int) -> str:
    block: list[str] = []
    for line in lines[start_index:]:
        if line.strip() and len(line) - len(line.lstrip(" ")) <= parent_indent:
            break
        block.append(line)
    return "\n".join(block)


def _first_yaml_value(block: str, key: str) -> str | None:
    match = re.search(rf"^\s*{re.escape(key)}:\s*(.+)$", block, re.MULTILINE)
    if not match:
        return None
    value = match.group(1).strip().strip("'\"")
    return value or None


def _string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _build_backend_surfaces(
    routes: list[ApiRouteFact],
    symbols: list[SymbolFact],
    frameworks: list[FrameworkFact],
) -> list[BackendSurfaceFact]:
    backend_frameworks = {item.name for item in frameworks if item.category == "backend"}
    backend_frameworks.update(route.framework for route in routes)
    surfaces: list[BackendSurfaceFact] = []
    for framework in sorted(backend_frameworks):
        framework_routes = [route for route in routes if route.framework == framework]
        services = [symbol for symbol in symbols if symbol.name.endswith("Service")]
        models = [
            symbol
            for symbol in symbols
            if symbol.name.endswith(("Model", "Entity", "DTO", "Dto", "Schema"))
        ]
        surfaces.append(
            BackendSurfaceFact(
                framework=framework,
                route_count=len(framework_routes),
                handler_count=len({route.handler for route in framework_routes if route.handler}),
                service_count=len(services),
                model_count=len(models),
                evidence=[route.evidence for route in framework_routes[:10]],
            )
        )
    return surfaces


def _next_api_path(path: str) -> str | None:
    normalized = path.replace("\\", "/")
    if normalized.startswith("pages/api/"):
        stem = normalized.removeprefix("pages/api/").rsplit(".", 1)[0]
        return "/api/" + _clean_route_path(stem)
    marker = "/pages/api/"
    if marker in normalized:
        stem = normalized.split(marker, 1)[1].rsplit(".", 1)[0]
        return "/api/" + _clean_route_path(stem)

    if normalized.startswith("app/api/") and normalized.endswith(("/route.ts", "/route.js")):
        stem = normalized.removeprefix("app/api/").removesuffix("/route.ts").removesuffix("/route.js")
        return "/api/" + _clean_route_path(stem)
    marker = "/app/api/"
    if marker in normalized and normalized.endswith(("/route.ts", "/route.js")):
        stem = normalized.split(marker, 1)[1].removesuffix("/route.ts").removesuffix("/route.js")
        return "/api/" + _clean_route_path(stem)
    return None


def _clean_route_path(value: str) -> str:
    route = value.replace("/index", "").replace("[", ":").replace("]", "")
    return route.strip("/") or ""


def _function_after(source: str, offset: int) -> str | None:
    match = PY_FUNCTION_AFTER_DECORATOR_RE.search(source[offset : offset + PY_FUNCTION_SEARCH_WINDOW])
    return match.group("name") if match else None


def _quoted_value(value: str) -> str | None:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] in {"'", '"', "`"} and stripped[-1] == stripped[0]:
        return stripped[1:-1]
    return None


def _graphql_endpoint_from_config(root: Path, file_fact: FileFact) -> str | None:
    source_path = root / file_fact.path
    candidates = [
        source_path.parent / "config.json",
        source_path.parent.parent / "config" / "config.json",
        source_path.parent / "config" / "config.json",
    ]
    candidates.extend(path for path in root.rglob("config.json") if "node_modules" not in path.parts)
    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and isinstance(data.get("graphqlEndpoint"), str):
            return data["graphqlEndpoint"]
    return None


def _path_from_args(args: str, *, default: str = "/") -> str:
    match = re.search(r"""["'](?P<path>[^"']*)["']""", args)
    if not match:
        return default
    value = match.group("path")
    if not value:
        return default
    return value if value.startswith("/") else f"/{value}"


def _typescript_method_after(source: str, offset: int) -> str | None:
    start = _skip_typescript_decorators(source, offset)
    match = TS_METHOD_RE.search(source[start : start + 600])
    return match.group("name") if match else None


def _skip_typescript_decorators(source: str, offset: int) -> int:
    index = offset
    while index < len(source):
        while index < len(source) and source[index].isspace():
            index += 1
        if source.startswith("//", index):
            newline = source.find("\n", index)
            index = len(source) if newline < 0 else newline + 1
            continue
        if source.startswith("/*", index):
            end = source.find("*/", index + 2)
            index = len(source) if end < 0 else end + 2
            continue
        if index >= len(source) or source[index] != "@":
            return index
        depth = 0
        while index < len(source):
            char = source[index]
            if char == "(":
                depth += 1
            elif char == ")":
                depth = max(0, depth - 1)
            elif char == "\n" and depth == 0:
                index += 1
                break
            index += 1
    return index


def _go_framework_fallback(frameworks: list[FrameworkFact]) -> str | None:
    candidates = {
        framework.name
        for framework in frameworks
        if framework.category == "backend" and framework.name in {"chi", "echo", "fiber", "gin"}
    }
    return next(iter(candidates)) if len(candidates) == 1 else None


def _go_framework(source: str, fallback: str | None = None) -> str:
    lower = source.lower()
    if "labstack/echo" in lower:
        return "echo"
    if "gofiber/fiber" in lower:
        return "fiber"
    if "go-chi/chi" in lower:
        return "chi"
    if "gin-gonic/gin" in lower:
        return "gin"
    return fallback or "go"


def _symfony_first_route_path(attrs: str) -> str:
    for match in SYMFONY_ROUTE_ATTR_RE.finditer(attrs):
        return _path_from_args(match.group("args"), default="")
    return ""


def _symfony_doc_handler_after(source: str, offset: int) -> str | None:
    window = source[offset : offset + 900]
    class_match = PHP_CLASS_RE.search(window)
    function_match = PHP_FUNCTION_RE.search(window)
    if function_match and (class_match is None or function_match.start() < class_match.start()):
        return function_match.group("name")
    if class_match:
        class_name = class_match.group("name")
        brace_offset = source.find("{", offset + class_match.end())
        class_body_end = _find_matching_brace(source, brace_offset) if brace_offset >= 0 else None
        class_body = source[brace_offset:class_body_end] if class_body_end else source[brace_offset : brace_offset + 1800]
        if re.search(r"\bfunction\s+__invoke\s*\(", class_body):
            return "__invoke"
        return class_name
    return None


@lru_cache(maxsize=64)
def _symfony_controller_import_prefix(root: Path) -> str:
    for relative in ("config/routes.yaml", "config/routes.yml"):
        route_config = root / relative
        if not route_config.exists():
            continue
        source = route_config.read_text(encoding="utf-8", errors="ignore")
        for _name, _start, block in _yaml_top_level_blocks(source.splitlines()):
            resource, _ = _yaml_block_scalar(block, "resource", 1)
            prefix, _ = _yaml_block_scalar(block, "prefix", 1)
            if prefix and _symfony_route_resource_targets_controllers(resource, block):
                return prefix
    return ""


def _symfony_route_resource_targets_controllers(resource: str | None, block: list[str]) -> bool:
    if resource and ("routing.controllers" in resource or "src/Controller" in resource or "src\\Controller" in resource):
        return True
    text = "\n".join(block)
    return "routing.controllers" in text or "src/Controller" in text or "src\\Controller" in text


def _yaml_top_level_blocks(lines: list[str]) -> list[tuple[str, int, list[str]]]:
    blocks: list[tuple[str, int, list[str]]] = []
    current_name: str | None = None
    current_start = 1
    current_lines: list[str] = []
    for index, line in enumerate(lines, start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            if current_name is not None:
                current_lines.append(line)
            continue
        match = re.match(r"^(?P<name>[A-Za-z0-9_.-]+):\s*$", line)
        if match:
            if current_name is not None:
                blocks.append((current_name, current_start, current_lines))
            current_name = match.group("name")
            current_start = index
            current_lines = []
            continue
        if current_name is not None:
            current_lines.append(line)
    if current_name is not None:
        blocks.append((current_name, current_start, current_lines))
    return blocks


def _yaml_block_scalar(block: list[str], key: str, block_start_line: int) -> tuple[str | None, int]:
    pattern = re.compile(rf"^\s+{re.escape(key)}:\s*(?P<value>.+?)\s*$")
    for index, line in enumerate(block, start=block_start_line + 1):
        match = pattern.match(line)
        if not match:
            continue
        value = match.group("value").strip()
        value = value.split(" #", 1)[0].strip()
        value = value.strip("'\"")
        return (value or None), index
    return None, block_start_line


def _symfony_methods(args: str) -> list[str]:
    methods_source = re.search(r"methods\s*:\s*\[(?P<methods>[^\]]+)\]", args)
    if not methods_source:
        methods_source = re.search(r"methods\s*=\s*\{(?P<methods>[^}]+)\}", args)
    if not methods_source:
        return ["ANY"]
    found = re.findall(
        r"['\"](GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)['\"]",
        methods_source.group("methods"),
        re.IGNORECASE,
    )
    return [item.upper() for item in found] or ["ANY"]


def _symfony_yaml_methods(block: list[str]) -> list[str]:
    text = "\n".join(block)
    inline = re.search(r"^\s+methods:\s*\[(?P<methods>[^\]]+)\]", text, re.MULTILINE)
    if inline:
        found = re.findall(
            r"['\"]?(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)['\"]?",
            inline.group("methods"),
            re.IGNORECASE,
        )
        return [item.upper() for item in found] or ["ANY"]
    scalar = re.search(r"^\s+methods:\s*(?P<method>GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\s*$", text, re.MULTILINE | re.IGNORECASE)
    if scalar:
        return [scalar.group("method").upper()]
    return ["ANY"]


def _java_method_after(source: str, offset: int, file_path: str, line: int) -> dict[str, object]:
    window = source[offset : offset + 1600]
    match = JAVA_METHOD_DECL_RE.search(window)
    if not match:
        return {"name": None, "parameters": [], "request_body": None, "response_type": None}
    return _java_method_info_from_match(source, match, offset, file_path, line)


def _java_method_info_from_match(
    source: str,
    match: re.Match[str],
    base_offset: int,
    file_path: str,
    line: int,
) -> dict[str, object]:
    paren_start = base_offset + match.end() - 1
    paren_end = _find_matching_paren(source, paren_start)
    params_source = source[paren_start + 1 : paren_end] if paren_end is not None else ""
    parameters = _java_request_params(params_source, file_path, line)
    request_body = next((param.type or param.name for param in parameters if param.source == "body"), None)
    return_type = " ".join(match.group("return").split())
    return_type = re.sub(
        r"^(?:public|protected|private|static|final|synchronized)\s+",
        "",
        return_type,
    )
    return {
        "name": match.group("name"),
        "parameters": parameters,
        "request_body": request_body,
        "response_type": return_type or None,
        "file": file_path,
        "line": line,
    }


def _java_request_params(params_source: str, file_path: str, line: int) -> list[RequestParamFact]:
    params: list[RequestParamFact] = []
    for raw_param in _split_java_params(params_source):
        source = _request_param_source(raw_param)
        if source is None:
            continue
        clean = re.sub(r"@\w+(?:\s*\([^)]*\))?", " ", raw_param)
        clean = re.sub(r"\b(final|volatile)\b", " ", clean)
        tokens = [token for token in re.split(r"\s+", clean.strip()) if token]
        if len(tokens) < 2:
            continue
        name = tokens[-1].replace("...", "").strip()
        type_name = " ".join(tokens[:-1]).strip() or None
        explicit_name = _annotation_value(raw_param)
        params.append(
            RequestParamFact(
                name=explicit_name or name,
                source=source,
                type=type_name,
                required=_required_flag(raw_param),
                evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
            )
        )
    return params


def _split_java_params(params_source: str) -> list[str]:
    result: list[str] = []
    start = 0
    paren_depth = 0
    angle_depth = 0
    brace_depth = 0
    for index, char in enumerate(params_source):
        if char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth = max(0, paren_depth - 1)
        elif char == "<":
            angle_depth += 1
        elif char == ">":
            angle_depth = max(0, angle_depth - 1)
        elif char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth = max(0, brace_depth - 1)
        elif char == "," and not paren_depth and not angle_depth and not brace_depth:
            result.append(params_source[start:index].strip())
            start = index + 1
    tail = params_source[start:].strip()
    if tail:
        result.append(tail)
    return result


def _request_param_source(raw_param: str) -> str | None:
    if "@PathVariable" in raw_param:
        return "path"
    if "@RequestParam" in raw_param:
        return "query"
    if "@RequestBody" in raw_param:
        return "body"
    return None


def _annotation_value(raw_param: str) -> str | None:
    match = re.search(r"@\w+\s*\(\s*(?:value\s*=\s*|name\s*=\s*)?['\"]([^'\"]+)['\"]", raw_param)
    return match.group(1) if match else None


def _required_flag(raw_param: str) -> bool | None:
    if "required" not in raw_param:
        return None
    return not bool(re.search(r"required\s*=\s*false", raw_param))


def _looks_like_spring_controller(annotation_block: str, class_body: str) -> bool:
    return (
        "@RestController" in annotation_block
        or "@Controller" in annotation_block
        or bool(SPRING_ROUTE_RE.search(class_body))
    )


def _annotation_block_before(source: str, offset: int) -> str:
    prefix = source[max(0, offset - 800) : offset]
    lines = prefix.splitlines()
    collected: list[str] = []
    for line in reversed(lines):
        stripped = line.strip()
        if not stripped:
            if collected:
                break
            continue
        if stripped.startswith("@"):
            collected.append(stripped)
            continue
        if collected and (stripped.endswith(")") or stripped.endswith("}")):
            collected.append(stripped)
            continue
        break
    return "\n".join(reversed(collected))


def _java_mask_comments_preserving_offsets(source: str) -> str:
    def replace_comment(match: re.Match[str]) -> str:
        return "".join("\n" if char == "\n" else " " for char in match.group(0))

    return re.sub(r"/\*[\s\S]*?\*/|//[^\n]*", replace_comment, source)


def _csharp_attribute_block_before(source: str, offset: int) -> str:
    prefix = source[max(0, offset - 2000) : offset]
    trailing_blocks: list[list[str]] = []
    current: list[str] = []
    depth = 0
    for line in prefix.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if not current:
            if stripped.startswith("["):
                current = [stripped]
                depth = stripped.count("[") - stripped.count("]")
                if depth <= 0:
                    trailing_blocks.append(current)
                    current = []
                    depth = 0
            else:
                trailing_blocks = []
            continue
        current.append(stripped)
        depth += stripped.count("[") - stripped.count("]")
        if depth <= 0:
            trailing_blocks.append(current)
            current = []
            depth = 0
    if current:
        return ""
    return "\n".join("\n".join(block) for block in trailing_blocks)


def _spring_path_from_annotations(annotation_block: str) -> str:
    for match in SPRING_ROUTE_RE.finditer(annotation_block):
        if match.group("annotation") == "RequestMapping":
            return _spring_path_from_args(match.group("args") or "")
    return ""


def _spring_path_from_args(args: str) -> str:
    if not args.strip():
        return "/"
    explicit = re.search(
        r"""\b(?:value|path)\s*=\s*(?:\{\s*)?["'](?P<path>[^"']*)["']""",
        args,
    )
    if explicit:
        return _ensure_slash(explicit.group("path")) if explicit.group("path") else "/"
    positional = re.match(r"""\s*(?:\{\s*)?["'](?P<path>[^"']*)["']""", args)
    if positional:
        return _ensure_slash(positional.group("path")) if positional.group("path") else "/"
    return "/"


def _spring_methods(annotation: str, args: str) -> list[str]:
    mapping = {
        "GetMapping": ["GET"],
        "PostMapping": ["POST"],
        "PutMapping": ["PUT"],
        "DeleteMapping": ["DELETE"],
        "PatchMapping": ["PATCH"],
    }
    if annotation in mapping:
        return mapping[annotation]
    method_args = re.findall(
        r"\bmethod\s*=\s*(?P<value>\{[^)]*?\}|[^,)]*)",
        args,
        flags=re.DOTALL,
    )
    methods = [
        match.group("method")
        for method_arg in method_args
        for match in SPRING_METHOD_RE.finditer(method_arg)
    ]
    return methods or ["ANY"]


def _join_paths(prefix: str, path: str) -> str:
    if not prefix or prefix == "/":
        return path if path.startswith("/") else f"/{path}"
    if not path or path == "/":
        return prefix
    return f"{prefix.rstrip('/')}/{path.lstrip('/')}"


def _ensure_slash(path: str) -> str:
    return path if path.startswith("/") else f"/{path}"


def _aspnet_route_path(attrs: str, class_name: str) -> str:
    for match in ASPNET_ROUTE_ATTR_RE.finditer(attrs):
        if match.group("name").lower() == "route":
            return _ensure_slash(_aspnet_replace_tokens(match.group("path") or "", class_name))
    return ""


def _aspnet_replace_tokens(path: str, class_name: str, action: str | None = None) -> str:
    controller = class_name.removesuffix("Controller")
    controller_route = controller[:1].lower() + controller[1:]
    result = path.replace("[controller]", controller_route)
    if action is not None:
        result = result.replace("[action]", action)
    return result


def _flask_methods(args: str) -> list[str]:
    found = re.findall(r"['\"](GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)['\"]", args, flags=re.IGNORECASE)
    return [item.upper() for item in found] or ["GET"]


def _wordpress_methods(args: str) -> list[str]:
    constant_map = {
        "READABLE": "GET",
        "CREATABLE": "POST",
        "EDITABLE": "PUT",
        "DELETABLE": "DELETE",
    }
    methods: list[str] = []
    for match in WORDPRESS_METHOD_RE.finditer(args):
        if match.group("method"):
            methods.append(match.group("method").upper())
            continue
        constant = (match.group("constant") or "").upper()
        methods.append(constant_map.get(constant, "ANY"))
    if not methods:
        return ["ANY"]
    return _dedupe(methods)


def _drupal_route(file_fact: FileFact, path: str, handler: str | None, line: int) -> ApiRouteFact:
    return ApiRouteFact(
        method="ANY",
        path=path,
        handler=handler,
        framework="drupal",
        kind="drupal-routing-yaml",
        evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
    )


def _namespace(tag: str) -> str:
    match = re.match(r"\{.*\}", tag)
    return match.group(0) if match else ""


def _find_text(element: ET.Element, namespace: str, name: str) -> str | None:
    value = element.findtext(f"{namespace}{name}")
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _find_matching_brace(source: str, open_index: int) -> int | None:
    depth = 0
    for index in range(open_index, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    return None


def _find_matching_paren(source: str, open_index: int) -> int | None:
    depth = 0
    for index in range(open_index, len(source)):
        char = source[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
    return None


def _find_matching_wordpress_call_paren(source: str, open_index: int) -> int | None:
    return _find_matching_php_delimiter(source, open_index, "(", ")")


def _find_matching_php_delimiter(source: str, open_index: int, open_char: str, close_char: str) -> int | None:
    depth = 0
    quote: str | None = None
    escape = False
    for index in range(open_index, len(source)):
        char = source[index]
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if quote:
            if char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            continue
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return index
    return None


def _find_matching_square(source: str, open_index: int) -> int | None:
    if open_index < 0:
        return None
    depth = 0
    for index in range(open_index, len(source)):
        char = source[index]
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return index
    return None


def _read(root: Path, file_fact: FileFact) -> str:
    return (root / file_fact.path).read_text(encoding="utf-8", errors="ignore")


def _line_for_offset(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


def _line_for_text(source: str, text: str) -> int:
    index = source.find(text)
    return _line_for_offset(source, index) if index >= 0 else 1


def _first_match(source: str, pattern: str) -> str | None:
    match = re.search(pattern, source)
    return match.group(1) if match else None


def _split_params(source: str) -> list[str]:
    result: list[str] = []
    start = 0
    depth = 0
    angle_depth = 0
    for index, char in enumerate(source):
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth = max(0, depth - 1)
        elif char == "<":
            angle_depth += 1
        elif char == ">":
            angle_depth = max(0, angle_depth - 1)
        elif char == "," and depth == 0 and angle_depth == 0:
            result.append(source[start:index])
            start = index + 1
    tail = source[start:]
    if tail:
        result.append(tail)
    return result


def _dedupe(values: object) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(str(value))
    return result

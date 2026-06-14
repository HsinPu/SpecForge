from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

from specforge.extractors.dart import dart_api_route_map
from specforge.models import (
    ApiCallFact,
    ComponentFact,
    Evidence,
    FileFact,
    FrameworkFact,
    FrontendRouteFact,
    FrontendSurfaceFact,
    StateUsageFact,
    SymbolFact,
)


FETCH_RE = re.compile(r"(?<!\.)\bfetch\(\s*['\"`](?P<endpoint>[^'\"`]+)['\"`](?P<args>[^)]*)\)", re.DOTALL)
AJAX_RE = re.compile(
    r"\bajax\s*\(\s*(?P<quote>['\"`])(?P<endpoint>(?:/|https?://)[^'\"`]+)(?P=quote)(?P<args>[^)]*)",
    re.IGNORECASE | re.DOTALL,
)
AJAX_CALL_RE = re.compile(r"\bajax\s*\(", re.IGNORECASE)
AXIOS_RE = re.compile(
    r"\baxios\.(?P<method>get|post|put|delete|patch)\(\s*(?P<quote>['\"`])(?P<endpoint>.*?)(?P=quote)",
    re.IGNORECASE | re.DOTALL,
)
AXIOS_DIRECT_RE = re.compile(
    r"\baxios\.(?P<method>get|post|put|delete|patch)\(\s*"
    r"(?P<endpoint>this\.(?:url|apiVersion|baseUrl\(\)))\s*(?:,|\))",
    re.IGNORECASE,
)
CLIENT_CALL_RE = re.compile(
    r"\b(?P<client>api|client|http|request|requests|service)\.(?P<method>get|post|put|delete|patch|del)"
    r"\(\s*(?P<quote>['\"`])(?P<endpoint>[^'\"`]+)(?P=quote)",
    re.IGNORECASE,
)
API_PATH_CLIENT_CALL_RE = re.compile(
    r"\b(?P<client>api|client|http|request|requests|service)\.(?P<method>get|post|put|delete|patch|del)"
    r"\s*\(\s*(?:[A-Za-z_$][\w$]*\.)?apiPath\s*\(\s*[^,]+,\s*"
    r"(?P<quote>['\"`])(?P<endpoint>.*?)(?P=quote)",
    re.IGNORECASE | re.DOTALL,
)
NAMED_CLIENT_CALL_RE = re.compile(
    r"\b(?P<client>[A-Za-z_$][\w$]*(?:Api|API|Client|Http|Request|Service))"
    r"\.(?P<method>get|post|put|delete|patch)"
    r"\(\s*['\"`](?P<endpoint>/[^'\"`]+)['\"`]",
    re.IGNORECASE,
)
DART_CLIENT_CALL_RE = re.compile(
    r"\b(?P<client>_?[A-Za-z_$][\w$]*)\.(?P<method>get|post|put|delete|patch)"
    r"\s*(?:<[^>]+>)?\(\s*['\"](?P<endpoint>/[^'\"]+)['\"]",
    re.IGNORECASE,
)
DART_CLIENT_VARIABLE_CALL_RE = re.compile(
    r"\b(?P<client>_?[A-Za-z_$][\w$]*)\.(?P<method>get|post|put|delete|patch)"
    r"\s*(?:<[^>]+>)?\(\s*(?P<endpoint>[A-Za-z_]\w*)\b",
    re.IGNORECASE,
)
DART_API_ROUTE_CLIENT_CALL_RE = re.compile(
    r"\b(?P<client>_?[A-Za-z_$][\w$]*)\.(?P<method>get|post|put|delete|patch)"
    r"\s*(?:<[^>]+>)?\(\s*ApiRoute\.(?P<route>[A-Za-z_]\w*)\.(?P<accessor>v1|v2|target|targetRaw)\b",
    re.IGNORECASE | re.DOTALL,
)
OBJECT_CLIENT_CALL_RE = re.compile(
    r"\b(?P<client>[A-Za-z_$][\w$]*(?:api|Api|API|client|Client|http|Http|request|Request|service|Service)|axios)"
    r"\s*\(\s*\{(?P<body>[\s\S]{0,1800}?)\}\s*\)",
    re.IGNORECASE,
)
OBJECT_METHOD_CLIENT_CALL_RE = re.compile(
    r"\b(?P<client>[A-Za-z_$][\w$]*(?:api|Api|API|client|Client|http|Http|request|Request|service|Service)|axios)"
    r"\.(?P<method>get|post|put|delete|patch|request|postForm)\s*\(",
    re.IGNORECASE,
)
OBJECT_METHOD_RE = re.compile(r"\bmethod\s*:\s*['\"`](?P<method>get|post|put|delete|patch|options|head)['\"`]", re.IGNORECASE)
OBJECT_URL_RE = re.compile(r"\b(?:url|path|endpoint)\s*:\s*(?P<quote>['\"`])(?P<endpoint>/.*?)(?P=quote)", re.DOTALL)
OBJECT_ENDPOINT_VALUE_RE = re.compile(
    r"\b(?:url|path|endpoint)\s*:\s*"
    r"(?P<value>`(?:\\.|[^`])*`|'(?:\\.|[^'])*'|\"(?:\\.|[^\"])*\"|[A-Za-z_$][\w$]*)",
    re.DOTALL,
)
WORDPRESS_API_FETCH_RE = re.compile(r"\b(?P<client>(?:window\.wp\.)?apiFetch)\s*\(\s*\{(?P<body>[\s\S]{0,1600}?)\}\s*\)", re.IGNORECASE)
WORDPRESS_API_FETCH_PATH_RE = re.compile(
    r"\bpath\s*:\s*(?:(?P<quote>['\"`])(?P<endpoint>[^'\"`]+)(?P=quote)|(?P<variable>[A-Za-z_$][\w$]*))",
    re.DOTALL,
)
WORDPRESS_API_FETCH_METHOD_RE = re.compile(r"\bmethod\s*:\s*['\"`](?P<method>[A-Z]+)['\"`]", re.IGNORECASE)
TAURI_INVOKE_RE = re.compile(
    r"\b(?P<client>(?:window\.__TAURI__(?:_INTERNALS__)?(?:\.core)?\.)?(?:core\.)?invoke)"
    r"\s*(?:<[^>()]{1,180}>)?\s*\(\s*(?P<quote>['\"`])(?P<command>[^'\"`]+)(?P=quote)",
    re.DOTALL,
)
TAURI_INVOKE_IMPORT_RE = re.compile(
    r"\bimport\s*\{[^}]*\binvoke\b[^}]*\}\s*from\s*['\"](?:@tauri-apps/api(?:/core|/tauri)?|\.\/core)['\"]",
    re.DOTALL,
)
RTK_QUERY_OBJECT_RE = re.compile(
    r"\bquery\s*:\s*(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>\s*\(\s*\{(?P<body>[\s\S]{0,1800}?)\}\s*\)",
    re.IGNORECASE,
)
LEGACY_API_METHOD_CALL_RE = re.compile(
    r"\b(?P<method>GET|POST|PUT|DELETE|PATCH)\(\s*(?P<quote>['\"`])(?P<endpoint>/.*?)(?P=quote)",
    re.IGNORECASE | re.DOTALL,
)
ANGULAR_HTTP_RE = re.compile(
    r"\b(?:this\.)?http\s*\.\s*(?P<method>get|post|put|delete|patch)"
    r"\s*(?:<[^>]+>)?\s*\(\s*(?P<endpoint>(?:`[^`]*`|['\"][^'\"]*['\"])"
    r"(?:\s*\+\s*(?:`[^`]*`|['\"][^'\"]*['\"]|[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*))*)",
    re.IGNORECASE | re.DOTALL,
)
CSHARP_HTTPCLIENT_LITERAL_RE = re.compile(
    r"\b(?P<client>_?[A-Za-z_]\w*|HttpClient)\."
    r"(?P<method>GetFromJsonAsync|GetAsync|PostAsync|PostAsJsonAsync|PutAsync|PutAsJsonAsync|DeleteAsync|DeleteFromJsonAsync)"
    r"\s*(?:<[^>()]{1,200}>)?\s*\(\s*(?P<prefix>\$@?|@\$?)?\"(?P<endpoint>[^\"]+)\"",
    re.IGNORECASE | re.DOTALL,
)
CSHARP_CUSTOM_HTTP_CALL_RE = re.compile(
    r"\b(?P<client>_?[A-Za-z_]\w*)\."
    r"(?P<method>HttpGet|HttpPost|HttpPut|HttpDelete|HttpPatch)"
    r"\s*(?:<[^>()]{1,200}>)?\s*\(\s*(?P<prefix>\$@?|@\$?)?\"(?P<endpoint>[^\"]+)\"(?P<args>[^)]*)\)",
    re.IGNORECASE | re.DOTALL,
)
ANGULAR_LAZY_IMPORT_RE = re.compile(
    r"\bloadChildren\s*:\s*\(\)\s*=>\s*import\(\s*['\"](?P<target>[^'\"]+)['\"]\s*\)",
    re.DOTALL,
)
NUXT_FETCH_RE = re.compile(
    r"\b(?P<client>\$fetch|useFetch)\s*(?:<[^>]+>)?\s*\(\s*['\"`](?P<endpoint>/[^'\"`]+)['\"`](?P<args>[^)]*)\)",
    re.IGNORECASE | re.DOTALL,
)
NUXT_DYNAMIC_FETCH_RE = re.compile(
    r"\b(?P<client>\$fetch|useFetch)\s*(?:<[^>]+>)?\s*\(\s*(?P<endpoint>[A-Za-z_$][\w$]*)\s*(?P<args>,[^)]*)?\)",
    re.IGNORECASE | re.DOTALL,
)
COMPOSABLE_API_RE = re.compile(
    r"\b(?P<client>use[A-Za-z0-9_]*(?:API|Api))\s*(?:<[^>]+>)?\s*\(\s*(?P<endpoint>['\"`][^'\"`]+['\"`]|[A-Za-z_$][\w$]*)\s*(?P<args>,[^)]*)?",
    re.IGNORECASE | re.DOTALL,
)
API_SERVICE_METHOD_RE = re.compile(
    r"\b(?P<client>[A-Za-z_$][\w$]*(?:ApiService|APIService)|ApiService)"
    r"\.(?P<method>get|query|post|put|update|delete)\s*\(",
    re.IGNORECASE,
)
API_PATH_WRAPPER_CALL_RE = re.compile(
    r"(?<!\.)\b(?P<client>(?:fetch|get|load|query|search|suggest|post|create|update|delete|remove)"
    r"[A-Za-z0-9_$]*)\s*\(",
    re.IGNORECASE,
)
STRAPI_URL_CALL_RE = re.compile(
    r"\bgetStrapiURL\(\s*(?P<quote>['\"`])(?P<endpoint>.*?)(?P=quote)",
    re.IGNORECASE | re.DOTALL,
)
GENERATED_API_IMPORT_RE = re.compile(
    r"import\s+\{(?P<names>[^}]+)\}\s+from\s+['\"][^'\"]*/api/generated/(?:fetch|client)/[^'\"]+['\"]",
    re.DOTALL,
)
OPENAPI_TS_REQUEST_RE = re.compile(
    r"\b__request\s*\(\s*OpenAPI\s*,\s*\{(?P<body>[\s\S]{0,2200}?)\}\s*\)",
    re.DOTALL,
)
OPENAPI_TS_METHOD_RE = re.compile(r"\bmethod\s*:\s*['\"`](?P<method>[A-Z]+)['\"`]", re.IGNORECASE)
OPENAPI_TS_URL_RE = re.compile(r"\burl\s*:\s*['\"`](?P<endpoint>/[^'\"`]+)['\"`]", re.DOTALL)
TRPC_CLIENT_CALL_RE = re.compile(
    r"\b(?:trpc|api)\.(?P<path>[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\."
    r"(?P<hook>useQuery|useInfiniteQuery|useSuspenseQuery|useMutation|useSubscription|query|mutation|subscribe|prefetch)\s*\(",
)
GRAPHQL_OPERATION_RE = re.compile(
    r"(?<![./])\bgql\s*`(?P<body>[\s\S]*?)`|(?<![./])\bgraphql\s*`(?P<body_alt>[\s\S]*?)`",
    re.IGNORECASE,
)
GRAPHQL_OPERATION_HEADER_RE = re.compile(
    r"^\s*(?P<kind>query|mutation|subscription)\b\s*(?P<name>[A-Za-z_]\w*)?",
    re.IGNORECASE | re.MULTILINE,
)
EVENTSOURCE_RE = re.compile(
    r"\bnew\s+EventSource\(\s*(?P<quote>['\"`])(?P<endpoint>.*?)(?P=quote)",
    re.IGNORECASE | re.DOTALL,
)
WEBSOCKET_CLIENT_RE = re.compile(
    r"\bnew\s+WebSocket\(\s*(?P<quote>['\"`])(?P<endpoint>.*?)(?P=quote)",
    re.IGNORECASE | re.DOTALL,
)
WEBSOCKET_SEND_RE = re.compile(r"\b[A-Za-z_$][\w$]*\.send\(", re.IGNORECASE)
SOCKET_EMIT_RE = re.compile(r"\b(?:socket|io)\.emit\(\s*['\"](?P<event>[^'\"]+)['\"]", re.IGNORECASE)
ELECTRON_IPC_CALL_RE = re.compile(
    r"\b(?P<client>ipcRenderer|window\.[A-Za-z_$][\w$]*\??\.ipcRenderer)\??\."
    r"(?P<method>sendMessage|send|invoke|on|once)\(\s*['\"`](?P<channel>[^'\"`]+)['\"`]",
    re.IGNORECASE,
)
HOOK_RE = re.compile(r"\b(use[A-Z]\w*)\s*\(")
ROUTER_PATH_RE = re.compile(r"\bpath\s*[:=]\s*['\"](?P<route>[^'\"\r\n]*)['\"]")
REDWOOD_ROUTE_TAG_RE = re.compile(r"<Route\b(?P<body>[^>]*)>", re.DOTALL)
REDWOOD_ROUTE_PATH_RE = re.compile(r"\bpath\s*=\s*['\"](?P<route>[^'\"\r\n]+)['\"]")
PROPS_INTERFACE_RE = re.compile(r"(?:interface|type)\s+(?P<name>[A-Za-z_$][\w$]*Props)\s*(?:=)?\s*{(?P<body>[^}]+)}", re.DOTALL)
PROP_NAME_RE = re.compile(r"(?P<name>[A-Za-z_$][\w$]*)\??\s*:")
STATE_PATTERNS = [
    ("react", "hook", re.compile(r"\b(useState|useReducer|useContext)\s*\(")),
    ("qwik", "signal", re.compile(r"\b(useSignal|useStore|useTask\$|useVisibleTask\$|useComputed\$|useResource\$)\s*\(")),
    ("qwik-city", "route-data", re.compile(r"\b(routeLoader\$|routeAction\$|globalAction\$|server\$)\s*\(")),
    ("solid", "signal", re.compile(r"\b(createSignal|createStore|createMemo|createResource|createEffect)\s*\(")),
    ("solid-router", "route-data", re.compile(r"\b(createAsync|createAsyncStore|query|action|useSubmission|useSubmissions)\s*\(")),
    ("tanstack-query", "query", re.compile(r"\b(useQuery|useQueries|useMutation|fetchQuery|prefetchQuery)\s*\(")),
    ("tanstack-start", "server-function", re.compile(r"\b(createServerFn)\s*\(")),
    ("react-redux", "store", re.compile(r"\b(useSelector|useDispatch)\s*\(")),
    ("redux", "store", re.compile(r"\b(createSlice|configureStore|createStore)\s*\(")),
    ("zustand", "store", re.compile(r"\bcreate\s*\(")),
    ("pinia", "store", re.compile(r"\b(defineStore|createPinia)\s*\(")),
    ("vue", "state", re.compile(r"\b(ref|reactive|computed)\s*\(")),
    ("svelte", "rune", re.compile(r"(\$(?:state|derived|effect|props))\s*\(")),
    ("angular-rxjs", "subject", re.compile(r"\bnew\s+(BehaviorSubject|ReplaySubject|Subject)\s*(?:<[^>]+>)?\s*\(")),
    ("angular-rxjs", "subject-next", re.compile(r"\b([A-Za-z_$][\w$]*\$)\.next\s*\(")),
    ("ember", "tracked", re.compile(r"@\s*tracked\s+(?:declare\s+)?([A-Za-z_$][\w$]*)")),
    ("ember", "service", re.compile(r"@\s*service(?:\([^)]*\))?\s+(?:declare\s+)?([A-Za-z_$][\w$]*)")),
]
FRONTEND_EXTRACTABLE_LANGUAGES = {
    "typescript",
    "javascript",
    "astro",
    "razor",
    "dart",
    "kotlin",
    "swift",
    "xaml",
    "python",
}
STREAMLIT_SESSION_STATE_RE = re.compile(
    r"\bst\.session_state\s*"
    r"(?:\[\s*(?P<quote>['\"])(?P<bracket>[^'\"]+)(?P=quote)\s*\]"
    r"|\.(?P<attr>[A-Za-z_]\w*))?"
)
STREAMLIT_SESSION_STATE_CONTAINS_RE = re.compile(
    r"(?P<quote>['\"])(?P<key>[^'\"]+)(?P=quote)\s+(?:not\s+)?in\s+st\.session_state"
)
GRADIO_COMPONENT_RE = re.compile(
    r"\b(?:gr|gradio)\."
    r"(?P<kind>Blocks|Interface|ChatInterface|TabbedInterface|Number|Dropdown|"
    r"Button|Textbox|TextArea|Markdown|Examples|Image|Audio|Video|File|Dataframe|"
    r"Checkbox|CheckboxGroup|Radio|Slider|HTML|JSON|Plot|Gallery|Chatbot)\s*"
    r"\((?P<body>(?:[^()'\"\[\]]+|'[^']*'|\"[^\"]*\"|\[[\s\S]{0,500}?\]){0,1800})\)",
    re.IGNORECASE,
)
GRADIO_STRING_ARG_RE = re.compile(r"(?P<quote>['\"])(?P<value>.*?)(?P=quote)", re.DOTALL)
GRADIO_PROP_RE = re.compile(
    r"\b(?P<key>label|title|value|variant|inputs|outputs|fn|choices)\s*=\s*"
    r"(?P<value>\[[\s\S]{0,400}?\]|(?P<quote>['\"]).*?(?P=quote)|[^,\)\r\n]+)",
    re.IGNORECASE,
)
DASH_COMPONENT_RE = re.compile(
    r"\b(?P<namespace>html|dcc|dash_table|dbc|daq|dash_[A-Za-z_]\w*)\."
    r"(?P<kind>[A-Z][A-Za-z0-9_]*)\s*"
    r"\((?P<body>(?:[^()'\"\[\]]+|'[^']*'|\"[^\"]*\"|\[[\s\S]{0,700}?\]){0,2200})\)",
    re.IGNORECASE,
)
DASH_COMPONENT_START_RE = re.compile(
    r"\b(?P<namespace>html|dcc|dash_table|dbc|daq|dash_[A-Za-z_]\w*)\."
    r"(?P<kind>[A-Z][A-Za-z0-9_]*)\s*\(",
    re.IGNORECASE,
)
DASH_STRING_ARG_RE = re.compile(r"(?P<quote>['\"])(?P<value>.*?)(?P=quote)", re.DOTALL)
DASH_TOP_LEVEL_PROP_RE = re.compile(
    r"\b(?P<key>id|children|value|placeholder|options|topics|broker_url|broker_port|"
    r"broker_path|className|style)\s*=\s*"
    r"(?P<value>[\s\S]+?)\s*$",
    re.IGNORECASE,
)
PANEL_COMPONENT_START_RE = re.compile(
    r"\bpn\.(?:(?P<family>widgets|pane|template|indicators)\.)?"
    r"(?P<kind>[A-Z][A-Za-z0-9_]*|panel)\s*\(",
    re.IGNORECASE,
)
PANEL_STRING_ARG_RE = re.compile(r"(?P<quote>['\"])(?P<value>.*?)(?P=quote)", re.DOTALL)
PANEL_TOP_LEVEL_PROP_RE = re.compile(
    r"\b(?P<key>name|title|value|options|area|site|site_url|template|sizing_mode)\s*=\s*"
    r"(?P<value>[\s\S]+?)\s*$",
    re.IGNORECASE,
)
SHINY_COMPONENT_START_RE = re.compile(
    r"\b(?:ui|shiny\.ui)\."
    r"(?P<kind>page_[A-Za-z_]\w*|input_[A-Za-z_]\w*|output_[A-Za-z_]\w*|"
    r"h[1-6]|markdown|HTML|div|span|card|layout_[A-Za-z_]\w*|"
    r"navset_[A-Za-z_]\w*|nav_panel|sidebar|value_box|download_button)"
    r"\s*\(",
    re.IGNORECASE,
)
SHINY_STRING_ARG_RE = re.compile(r"(?P<quote>['\"])(?P<value>.*?)(?P=quote)", re.DOTALL)
SHINY_TOP_LEVEL_PROP_RE = re.compile(
    r"\b(?P<key>id|label|choices|selected|value|title|height|width|placeholder|class_|fillable|sidebar)\s*=\s*"
    r"(?P<value>[\s\S]+?)\s*$",
    re.IGNORECASE,
)
SHINY_INPUT_CALL_RE = re.compile(r"\binput\.(?P<name>[A-Za-z_]\w*)\s*\(")
SHINY_DECORATOR_RE = re.compile(r"@\s*(?P<namespace>render|reactive)\.(?P<kind>[A-Za-z_]\w*)")
ANGULAR_COMPONENT_RE = re.compile(
    r"@Component\s*\(\s*{(?P<meta>.*?)}\s*\)\s*export\s+class\s+(?P<name>[A-Za-z_]\w*)",
    re.DOTALL,
)
ANGULAR_SELECTOR_RE = re.compile(r"selector\s*:\s*['\"](?P<selector>[^'\"]+)['\"]")
ANGULAR_INPUT_RE = re.compile(r"@Input(?:\([^)]*\))?\s*(?:\r?\n\s*)?(?:set\s+)?(?P<name>[A-Za-z_]\w*)")
ANGULAR_SIGNAL_ASSIGN_RE = re.compile(r"\b(?P<name>[A-Za-z_$][\w$]*)\s*=\s*(?P<kind>signal|computed)\s*\(")
ANGULAR_RXJS_SUBJECT_ASSIGN_RE = re.compile(
    r"\b(?P<name>[A-Za-z_$][\w$]*)\s*=\s*new\s+(?P<kind>BehaviorSubject|ReplaySubject|Subject)\s*(?:<[^>]+>)?\s*\("
)
ANGULAR_RXJS_SUBJECT_NEXT_RE = re.compile(r"\b(?:this\.)?(?P<name>[A-Za-z_$][\w$]*)\.next\s*\(")
ANGULAR_RXJS_AS_OBSERVABLE_RE = re.compile(
    r"\b(?P<name>[A-Za-z_$][\w$]*)\s*=\s*(?:this\.)?(?P<subject>[A-Za-z_$][\w$]*)\.asObservable\s*\("
)
BLAZOR_PAGE_RE = re.compile(r"^\ufeff?\s*@page\s+['\"](?P<route>[^'\"]+)['\"]", re.MULTILINE)
EMBER_ROUTE_RE = re.compile(r"this\.route\(\s*['\"](?P<name>[^'\"]+)['\"](?P<args>[^)]*)\)", re.DOTALL)
EMBER_MOUNT_RE = re.compile(r"this\.mount\(\s*['\"](?P<name>[^'\"]+)['\"](?P<args>[^)]*)\)", re.DOTALL)
EMBER_PATH_RE = re.compile(r"path\s*:\s*['\"](?P<path>[^'\"]+)['\"]")
REACT_NAV_SCREEN_RE = re.compile(r"<(?:[A-Za-z_]\w*\.)?Screen\b[^>]*\bname\s*=\s*['\"](?P<name>[^'\"]+)['\"]")
REACT_ROUTE_PATH_ATTR_RE = re.compile(r"\bpath\s*=\s*\{?\s*['\"](?P<route>[^'\"\r\n]+)['\"]")
DART_WIDGET_RE = re.compile(
    r"class\s+(?P<name>[A-Za-z_]\w*)\s+extends\s+(?P<base>StatelessWidget|StatefulWidget|ConsumerWidget|ConsumerStatefulWidget|HookWidget|HookConsumerWidget)\b"
)
DART_ROUTE_CALL_RE = re.compile(r"\b(?P<callee>GoRoute|NavigationItem)\s*\(")
DART_GO_ROUTE_PATH_RE = re.compile(r"\bpath\s*:\s*['\"](?P<route>[^'\"]+)['\"]")
DART_ROUTERINO_ROOT_RE = re.compile(r"\bRouterinoHome\s*\(", re.MULTILINE)
DART_ROUTERINO_PUSH_RE = re.compile(
    r"\b(?:context|Routerino\.context)\."
    r"(?P<method>pushRootImmediately|pushAndRemoveUntilImmediately|pushAndRemoveUntil|pushImmediately|pushBottomSheet|push)"
    r"\s*\(",
    re.MULTILINE,
)
DART_PAGE_FACTORY_RE = re.compile(
    r"(?:=>|builder\s*:\s*\(\s*\)\s*=>|\(\s*\)\s*=>)\s*(?:const\s+|new\s+)?(?P<page>[A-Z][A-Za-z_]\w*Page)\s*\(",
    re.MULTILINE,
)
DART_FLUTTER_HOOK_RE = re.compile(
    r"\b(useState|useEffect|useMemoized|useFuture|useStream|useTextEditingController|useScrollController|useAnimationController|useFocusNode|useTabController)\s*\("
)
DART_RIVERPOD_REF_RE = re.compile(r"\bref\.(?P<usage>watch|read|refresh|listen)\s*(?:<[^>]+>)?\(\s*(?P<name>[A-Za-z_]\w*)")
DART_PROVIDER_DECL_RE = re.compile(
    r"\b(?:final|var)\s+(?P<name>[A-Za-z_]\w*)\s*=\s*"
    r"(?P<kind>(?:[A-Za-z_]\w*\.)?(?:Provider|FutureProvider|StreamProvider|StateProvider|StateNotifierProvider|NotifierProvider|AsyncNotifierProvider|ChangeNotifierProvider))"
    r"\s*(?:<[^;=]+>)?\s*\(",
)
DART_RIVERPOD_ANNOTATION_RE = re.compile(
    r"@\s*riverpod\s*(?:\r?\n\s*)+(?:[A-Za-z_<>,?\s]+\s+)?(?P<name>[A-Za-z_]\w*)\s*\(",
    re.MULTILINE,
)
DART_PROVIDER_SCOPE_RE = re.compile(r"\bProviderScope\s*\(")
KOTLIN_COMPOSABLE_RE = re.compile(
    r"@Composable\s*(?:\r?\n\s*)+(?:private\s+|internal\s+|public\s+)?fun\s+(?P<name>[A-Za-z_]\w*)\s*\((?P<args>[^)]*)\)",
    re.MULTILINE,
)
KOTLIN_NAV3_ENTRY_RE = re.compile(r"\bentry\s*<\s*(?P<key>[A-Za-z_]\w*)\s*>\s*(?:\(|\{)")
KOTLIN_COMPOSE_NAV_CALL_RE = re.compile(
    r"\b(?P<callee>composable|navigation)\s*(?:<\s*(?P<key>[A-Za-z_]\w*)\s*>)?\s*(?P<open>\(|\{)",
)
KOTLIN_NAV_ROUTE_ARG_RE = re.compile(r"\broute\s*=\s*['\"](?P<route>[^'\"\r\n]+)['\"]")
KOTLIN_NAV_FIRST_ARG_RE = re.compile(r"^\s*['\"](?P<route>[^'\"\r\n]+)['\"]")
KOTLIN_VIEWMODEL_RE = re.compile(r"\bclass\s+(?P<name>[A-Za-z_]\w*ViewModel)\b[\s\S]{0,400}?:\s*ViewModel\s*\(")
KOTLIN_STATE_FLOW_RE = re.compile(
    r"\b(?:private\s+)?(?:val|var)\s+(?P<name>[A-Za-z_]\w*)\s*:\s*(?P<kind>MutableStateFlow|StateFlow)\s*<",
)
KOTLIN_MUTABLE_STATE_FLOW_CALL_RE = re.compile(r"\b(?:val|var)\s+(?P<name>[A-Za-z_]\w*)\s*=\s*MutableStateFlow\s*\(")
KOTLIN_SAVED_STATE_FLOW_RE = re.compile(r"\b(?:val|var)\s+(?P<name>[A-Za-z_]\w*)\s*=\s*savedStateHandle\.getStateFlow\b")
KOTLIN_COLLECT_AS_STATE_RE = re.compile(
    r"\b(?:val|var)\s+(?P<name>[A-Za-z_]\w*)\s+(?:by|=)\s+[^=\n]{0,160}?\.collectAsStateWithLifecycle\s*\(",
    re.MULTILINE,
)
KOTLIN_MUTABLE_STATE_RE = re.compile(
    r"\b(?:val|var)\s+(?P<name>[A-Za-z_]\w*)\s+by\s+(?:remember(?:Saveable)?\s*\{[^}\n]*)?mutable(?:Int|Float|Long|Double)?StateOf\s*\(",
    re.MULTILINE,
)
KOTLIN_REMEMBER_STATE_RE = re.compile(r"\b(?:val|var)\s+(?P<name>[A-Za-z_]\w*)\s*=\s*remember\s*\{", re.MULTILINE)
SWIFTUI_VIEW_RE = re.compile(r"\bstruct\s+(?P<name>[A-Za-z_]\w*)\s*:\s*(?:[A-Za-z_]\w*\s*,\s*)*View\b")
SWIFTUI_STATE_RE = re.compile(
    r"@(?P<kind>State|StateObject|ObservedObject|Environment|EnvironmentObject|Binding|AppStorage|SceneStorage)\b(?:\([^)]*\))?\s+(?:private\s+)?(?:var|let)\s+(?P<name>[A-Za-z_]\w*)"
)
SWIFT_TCA_STORE_OF_RE = re.compile(
    r"\b(?:let|var)\s+(?P<name>[A-Za-z_]\w*)\s*:\s*StoreOf<(?P<feature>[^>\n]+)>",
    re.MULTILINE,
)
SWIFT_TCA_BINDABLE_STORE_RE = re.compile(
    r"@Bindable\s+(?:(?:public|internal|private|fileprivate)\s+)?(?:var|let)\s+"
    r"(?P<name>[A-Za-z_]\w*)(?:\s*:\s*StoreOf<(?P<feature>[^>\n]+)>)?",
    re.MULTILINE,
)
SWIFT_TCA_STORE_INIT_RE = re.compile(
    r"\bStore\s*\(\s*initialState\s*:\s*(?P<feature>[A-Za-z_]\w*)\s*\.\s*State\b",
    re.MULTILINE,
)
SWIFT_TCA_REDUCER_RE = re.compile(
    r"@Reducer(?:\([^)]*\))?\s*(?:\r?\n\s*)+(?:public\s+|internal\s+|private\s+|fileprivate\s+)?"
    r"struct\s+(?P<name>[A-Za-z_]\w*)",
    re.MULTILINE,
)
SWIFT_TCA_OBSERVABLE_STATE_RE = re.compile(
    r"@ObservableState\s*(?:\r?\n\s*)+(?:public\s+|internal\s+|private\s+|fileprivate\s+)?"
    r"struct\s+(?P<name>[A-Za-z_]\w*)",
    re.MULTILINE,
)
XAML_CLASS_RE = re.compile(r"\bx:Class\s*=\s*['\"](?P<class>[^'\"]+)['\"]")
XAML_ROOT_RE = re.compile(r"<(?P<tag>(?:[A-Za-z_]\w*:)?[A-Za-z_]\w*)\b")
XAML_NAME_RE = re.compile(r"\b(?:x:Name|Name)\s*=\s*['\"](?P<name>[^'\"]+)['\"]")
XAML_EVENT_RE = re.compile(r"\b(?P<event>Clicked|Tapped|Command|Loaded|Navigated|SelectionChanged|TextChanged)\s*=\s*['\"](?P<handler>[^'\"]+)['\"]")
QWIK_COMPONENT_RE = re.compile(r"\bexport\s+const\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*component\$", re.MULTILINE)
QWIK_DEFAULT_COMPONENT_RE = re.compile(r"\bexport\s+default\s+component\$", re.MULTILINE)
TANSTACK_FILE_ROUTE_RE = re.compile(
    r"\bcreate(?:Lazy)?FileRoute\s*\(\s*['\"`](?P<route>[^'\"`]+)['\"`]\s*\)",
    re.DOTALL,
)
TANSTACK_ROOT_ROUTE_RE = re.compile(r"\bcreateRootRoute(?:WithContext)?\s*(?:<[^>]+>)?\s*\(")


def extract_frontend_facts(
    root: Path,
    files: list[FileFact],
    symbols: list[SymbolFact],
    frameworks: list[FrameworkFact],
) -> tuple[
    list[FrontendRouteFact],
    list[ComponentFact],
    list[ApiCallFact],
    list[StateUsageFact],
    list[FrontendSurfaceFact],
]:
    routes: list[FrontendRouteFact] = []
    components: list[ComponentFact] = []
    api_calls: list[ApiCallFact] = []
    state_usages: list[StateUsageFact] = []
    frontend_frameworks = {item.name for item in frameworks if item.category in {"frontend", "mobile", "desktop"}}
    framework_names = {item.name for item in frameworks}

    for file_fact in files:
        if file_fact.role in {"test", "sample"}:
            continue
        if file_fact.role == "generated":
            if file_fact.language in {"typescript", "javascript"}:
                source = _read(root, file_fact)
                api_calls.extend(_extract_openapi_ts_request_calls(file_fact, source))
            continue
        normalized = file_fact.path.replace("\\", "/")
        if file_fact.language == "elixir" and "phoenix" in framework_names and normalized.lower().endswith("router.ex"):
            source = _read(root, file_fact)
            routes.extend(_extract_phoenix_live_frontend_routes(file_fact, source))
            continue
        if not _is_frontend_candidate(normalized, frontend_frameworks, framework_names):
            continue
        if (
            file_fact.language in FRONTEND_EXTRACTABLE_LANGUAGES
            or normalized.endswith((".vue", ".svelte", ".astro", ".cshtml", ".razor", ".xaml", ".axaml"))
            or ("ember" in frontend_frameworks and normalized.endswith((".hbs", ".gjs", ".gts")))
        ):
            source = _read(root, file_fact)
            routes.extend(_extract_frontend_routes(file_fact, source, frontend_frameworks))
            components.extend(_extract_components(file_fact, source, symbols, frameworks))
            api_calls.extend(_extract_api_calls(root, file_fact, source))
            state_usages.extend(_extract_state_usages(file_fact, source, frontend_frameworks))
        elif file_fact.language == "csharp" and "blazor" in frontend_frameworks:
            source = _read(root, file_fact)
            api_calls.extend(_extract_api_calls(root, file_fact, source))

    routes = _apply_angular_lazy_route_prefixes(root, files, routes)
    routes = _apply_ember_engine_mount_prefixes(root, files, routes)
    surfaces = build_frontend_surfaces(
        routes,
        components,
        api_calls,
        frameworks,
        state_usages=state_usages,
    )
    return routes, components, api_calls, state_usages, surfaces


def _extract_frontend_routes(
    file_fact: FileFact,
    source: str,
    frontend_frameworks: set[str],
) -> list[FrontendRouteFact]:
    routes: list[FrontendRouteFact] = []
    normalized = file_fact.path.replace("\\", "/")
    sveltekit_route = _sveltekit_route_for_path(normalized)
    if sveltekit_route:
        routes.append(_route(file_fact, sveltekit_route, "sveltekit", "sveltekit-route", 1))
    astro_route = _astro_route_for_path(normalized) if "astro" in frontend_frameworks else None
    if astro_route:
        routes.append(_route(file_fact, astro_route, "astro", "astro-page-route", 1))
    fresh_route = _fresh_route_for_path(normalized, source) if "fresh" in frontend_frameworks else None
    if fresh_route:
        routes.append(_route(file_fact, fresh_route, "fresh", "fresh-file-route", 1))
    qwik_route = _qwik_route_for_path(normalized) if {"qwik", "qwik-city"} & frontend_frameworks else None
    if qwik_route:
        routes.append(_route(file_fact, qwik_route, "qwik-city", "qwik-city-file-route", 1))
    solid_route = _solid_start_route_for_path(normalized) if (
        {"solid-start", "solid-router", "solid"} & frontend_frameworks
        and _looks_like_solid_route_source(normalized, source)
    ) else None
    if solid_route:
        routes.append(_route(file_fact, solid_route, "solid-start", "solid-start-file-route", 1))
    is_tanstack_source = _looks_like_tanstack_source(source)
    if {"tanstack-router", "tanstack-start"} & frontend_frameworks or is_tanstack_source:
        routes.extend(_extract_tanstack_routes(file_fact, source))
    is_redwood_source = _looks_like_redwood_route_source(source)
    if "redwood" in frontend_frameworks or is_redwood_source:
        routes.extend(_extract_redwood_routes(file_fact, source))
    expo_route = _expo_route_for_path(normalized) if "expo" in frontend_frameworks else None
    if expo_route:
        routes.append(_route(file_fact, expo_route, "expo", "expo-router-route", 1))
    next_route = _next_route_for_path(normalized) if "next" in frontend_frameworks else None
    if next_route:
        route, kind = next_route
        routes.append(_route(file_fact, route, "next", kind, 1))
    react_router_file_route = _react_router_file_route_for_path(normalized) if {"react-router", "remix"} & frontend_frameworks else None
    if react_router_file_route:
        framework = "remix" if _should_label_file_route_as_remix(source, frontend_frameworks) else "react-router"
        kind = "remix-file-route" if framework == "remix" else "react-router-file-route"
        routes.append(_route(file_fact, react_router_file_route, framework, kind, 1))
    nuxt_route = _nuxt_route_for_path(normalized) if "nuxt" in frontend_frameworks else None
    if nuxt_route:
        routes.append(_route(file_fact, nuxt_route, "nuxt", "nuxt-page-route", 1))
    elif _vue_file_route_for_path(normalized):
        routes.append(_route(file_fact, _vue_file_route_for_path(normalized) or "/", "vue", "vue-file-route", 1))
    if _is_blazor_route_markup(normalized, source, frontend_frameworks):
        for match in BLAZOR_PAGE_RE.finditer(source):
            routes.append(
                _route(
                    file_fact,
                    _normalize_frontend_route(match.group("route")),
                    "blazor",
                    "blazor-page-route",
                    _line_for_offset(source, match.start()),
                )
            )
    if normalized == "app/router.js" or normalized.endswith("/app/router.js") or normalized == "addon/routes.js" or normalized.endswith("/addon/routes.js"):
        routes.extend(_extract_ember_routes(file_fact, source))
    if "react-navigation" in frontend_frameworks and "Screen" in source:
        for match in REACT_NAV_SCREEN_RE.finditer(source):
            routes.append(
                _route(
                    file_fact,
                    _normalize_frontend_route(match.group("name")),
                    "react-navigation",
                    "react-navigation-screen",
                    _line_for_offset(source, match.start()),
                )
            )
    if normalized.endswith(".dart") and "GoRoute" in source:
        routes.extend(_extract_flutter_go_routes(file_fact, source))
    if normalized.endswith(".dart") and "Routerino" in source:
        routes.extend(_extract_flutter_routerino_routes(file_fact, source))
    if normalized.endswith(".kt") and (
        {"android", "jetpack-compose"} & frontend_frameworks
        or "NavKey" in source
        or "androidx.navigation" in source
    ):
        routes.extend(_extract_compose_navigation_routes(file_fact, source))
    if _should_extract_angular_routes(source, frontend_frameworks):
        routes.extend(_extract_angular_routes(file_fact, source))
    elif not is_tanstack_source and not is_redwood_source and _should_extract_vue_router_routes(source, frontend_frameworks):
        for match in ROUTER_PATH_RE.finditer(source):
            if _offset_is_js_inert(source, match.start()):
                continue
            route_value = match.group("route")
            if not _looks_like_route_value(route_value):
                continue
            routes.append(
                _route(
                    file_fact,
                    _normalize_frontend_route(route_value),
                    "vue",
                    "vue-router-route",
                    _line_for_offset(source, match.start()),
                )
            )
    elif not is_tanstack_source and not is_redwood_source and _should_extract_react_router_routes(source, frontend_frameworks) and "/content/" not in f"/{normalized}":
        routes.extend(_extract_react_router_routes(file_fact, source))
    return routes


def _extract_redwood_routes(file_fact: FileFact, source: str) -> list[FrontendRouteFact]:
    routes: list[FrontendRouteFact] = []
    for match in REDWOOD_ROUTE_TAG_RE.finditer(source):
        if _offset_is_js_inert(source, match.start()):
            continue
        body = match.group("body")
        path_match = REDWOOD_ROUTE_PATH_RE.search(body)
        if path_match:
            route_value = path_match.group("route")
            if not _is_static_redwood_route(route_value):
                continue
            route_path = _normalize_frontend_route(route_value)
            kind = "redwood-route"
        elif re.search(r"\bnotfound\b", body):
            route_path = "*"
            kind = "redwood-notfound-route"
        else:
            continue
        routes.append(_route(file_fact, route_path, "redwood", kind, _line_for_offset(source, match.start())))
    return routes


def _looks_like_redwood_route_source(source: str) -> bool:
    return "@redwoodjs/router" in source


def _is_static_redwood_route(route: str) -> bool:
    stripped = route.strip()
    return bool(stripped) and "\n" not in stripped and "\r" not in stripped and "${" not in stripped


def _extract_tanstack_routes(file_fact: FileFact, source: str) -> list[FrontendRouteFact]:
    routes: list[FrontendRouteFact] = []
    for match in TANSTACK_FILE_ROUTE_RE.finditer(source):
        if _offset_is_js_inert(source, match.start()):
            continue
        if not _is_tanstack_route_module(file_fact.path, source, match.start()):
            continue
        route_value = match.group("route")
        if not _is_static_tanstack_route(route_value):
            continue
        routes.append(
            _route(
                file_fact,
                _normalize_tanstack_route(route_value),
                "tanstack-router",
                "tanstack-file-route",
                _line_for_offset(source, match.start()),
            )
        )
    root_match = next((match for match in TANSTACK_ROOT_ROUTE_RE.finditer(source) if not _offset_is_js_inert(source, match.start())), None)
    if root_match and _is_tanstack_route_module(file_fact.path, source, root_match.start()):
        line = _line_for_offset(source, root_match.start()) if root_match else 1
        routes.append(_route(file_fact, "/", "tanstack-router", "tanstack-root-route", line))
    return routes


def _looks_like_tanstack_route_source(source: str) -> bool:
    return (
        "@tanstack/react-router" in source
        or "@tanstack/solid-router" in source
        or "@tanstack/vue-router" in source
        or "@tanstack/router-core" in source
        or TANSTACK_FILE_ROUTE_RE.search(source) is not None
    )


def _looks_like_tanstack_source(source: str) -> bool:
    return (
        _looks_like_tanstack_route_source(source)
        or "@tanstack/router-" in source
        or "@tanstack/start" in source
    )


def _is_static_tanstack_route(route: str) -> bool:
    stripped = route.strip()
    return bool(stripped) and "${" not in stripped and "\n" not in stripped and "\r" not in stripped


def _is_tanstack_route_module(path: str, source: str, offset: int) -> bool:
    normalized = path.replace("\\", "/").lower()
    if "/src/routes/" in f"/{normalized}" or "/app/routes/" in f"/{normalized}":
        return True
    prefix = source[max(0, offset - 120) : offset]
    return re.search(r"(?:^|[;\n]\s*)(?:export\s+)?const\s+Route\s*=\s*$", prefix) is not None


def _offset_is_js_comment(source: str, offset: int) -> bool:
    line_start = source.rfind("\n", 0, offset) + 1
    if source[line_start:offset].lstrip().startswith(("//", "*", "/*")):
        return True
    block_start = source.rfind("/*", 0, offset)
    block_end = source.rfind("*/", 0, offset)
    return block_start > block_end


def _offset_is_js_inert(source: str, offset: int) -> bool:
    quote: str | None = None
    escaped = False
    line_comment = False
    block_comment = False
    index = 0
    while index < offset:
        char = source[index]
        next_char = source[index + 1] if index + 1 < offset else ""
        if line_comment:
            if char == "\n":
                line_comment = False
            index += 1
            continue
        if block_comment:
            if char == "*" and next_char == "/":
                block_comment = False
                index += 2
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
            block_comment = True
            index += 2
            continue
        if char in {"'", '"', "`"}:
            quote = char
        index += 1
    return quote is not None or line_comment or block_comment


def _normalize_tanstack_route(route: str) -> str:
    cleaned = route.strip()
    if not cleaned:
        return "/"
    if cleaned == "$":
        return "/{*}"
    if not cleaned.startswith("/"):
        cleaned = f"/{cleaned}"
    parts: list[str] = []
    for raw_part in cleaned.split("/"):
        if raw_part == "":
            parts.append(raw_part)
        elif raw_part == "$":
            parts.append("{*}")
        else:
            parts.append(re.sub(r"\$([A-Za-z_][\w-]*)", r"{\1}", raw_part))
    normalized = "/".join(parts)
    return normalized if normalized.startswith("/") else f"/{normalized}"


def _extract_flutter_go_routes(file_fact: FileFact, source: str) -> list[FrontendRouteFact]:
    spans: list[dict[str, object]] = []
    for match in DART_ROUTE_CALL_RE.finditer(source):
        open_index = source.find("(", match.start())
        close_index = _find_matching_delimiter(source, open_index, "(", ")")
        if close_index is None:
            continue
        body = source[open_index + 1 : close_index]
        path_match = DART_GO_ROUTE_PATH_RE.search(body)
        if not path_match:
            continue
        callee = match.group("callee")
        route_value = path_match.group("route")
        if not _looks_like_route_value(route_value):
            continue
        spans.append(
            {
                "start": match.start(),
                "end": close_index,
                "route": route_value,
                "kind": "flutter-go-route" if callee == "GoRoute" else "flutter-navigation-item-route",
                "line": _line_for_offset(source, match.start()),
            }
        )

    parents: dict[int, int | None] = {}
    for index, span in enumerate(spans):
        parent_index: int | None = None
        parent_size: int | None = None
        span_start = int(span["start"])
        span_end = int(span["end"])
        for candidate_index, candidate in enumerate(spans):
            if candidate_index == index:
                continue
            candidate_start = int(candidate["start"])
            candidate_end = int(candidate["end"])
            if candidate_start < span_start and span_end <= candidate_end:
                candidate_size = candidate_end - candidate_start
                if parent_size is None or candidate_size < parent_size:
                    parent_index = candidate_index
                    parent_size = candidate_size
        parents[index] = parent_index

    cache: dict[int, str] = {}

    def full_route(index: int) -> str:
        if index in cache:
            return cache[index]
        route_value = str(spans[index]["route"])
        parent_index = parents.get(index)
        if parent_index is None:
            route = _normalize_frontend_route(route_value)
        else:
            route = _join_flutter_route(full_route(parent_index), route_value)
        cache[index] = route
        return route

    routes: list[FrontendRouteFact] = []
    seen: set[tuple[str, int]] = set()
    for index, span in enumerate(spans):
        route = full_route(index)
        key = (route, int(span["line"]))
        if key in seen:
            continue
        seen.add(key)
        routes.append(_route(file_fact, route, "flutter", str(span["kind"]), int(span["line"])))
    return routes


def _extract_flutter_routerino_routes(file_fact: FileFact, source: str) -> list[FrontendRouteFact]:
    routes: list[FrontendRouteFact] = []
    seen: set[tuple[str, str]] = set()

    for match in DART_ROUTERINO_ROOT_RE.finditer(source):
        open_index = source.find("(", match.start())
        close_index = _find_matching_delimiter(source, open_index, "(", ")")
        if close_index is None:
            continue
        block = source[open_index + 1 : close_index]
        page = _dart_page_factory_name(block)
        if page:
            key = ("/", "flutter-routerino-root")
            if key not in seen:
                seen.add(key)
                routes.append(_route(file_fact, "/", "flutter", "flutter-routerino-root", _line_for_offset(source, match.start())))

    for match in DART_ROUTERINO_PUSH_RE.finditer(source):
        open_index = source.find("(", match.start())
        close_index = _find_matching_delimiter(source, open_index, "(", ")")
        if close_index is None:
            continue
        block = source[open_index + 1 : close_index]
        page = _dart_page_factory_name(block)
        if not page:
            continue
        route = f"/{page}"
        key = (route, "flutter-routerino-screen")
        if key in seen:
            continue
        seen.add(key)
        routes.append(_route(file_fact, route, "flutter", "flutter-routerino-screen", _line_for_offset(source, match.start())))
    return routes


def _extract_compose_navigation_routes(file_fact: FileFact, source: str) -> list[FrontendRouteFact]:
    routes: list[FrontendRouteFact] = []
    seen: set[tuple[str, str]] = set()

    for match in KOTLIN_NAV3_ENTRY_RE.finditer(source):
        if _offset_is_js_inert(source, match.start()):
            continue
        route = _normalize_frontend_route(match.group("key"))
        key = (route, "compose-navigation3-entry")
        if key in seen:
            continue
        seen.add(key)
        routes.append(
            _route(
                file_fact,
                route,
                "jetpack-compose",
                "compose-navigation3-entry",
                _line_for_offset(source, match.start()),
            )
        )

    for match in KOTLIN_COMPOSE_NAV_CALL_RE.finditer(source):
        if _offset_is_js_inert(source, match.start()):
            continue
        body = ""
        if match.group("open") == "(":
            open_index = source.find("(", match.start())
            close_index = _find_matching_delimiter(source, open_index, "(", ")")
            if close_index is None:
                continue
            body = source[open_index + 1 : close_index]
        route_value = _compose_navigation_route_value(match.group("key"), body)
        if not route_value:
            continue
        kind = "compose-navigation-graph" if match.group("callee") == "navigation" else "compose-navigation-route"
        route = _normalize_frontend_route(route_value)
        key = (route, kind)
        if key in seen:
            continue
        seen.add(key)
        routes.append(_route(file_fact, route, "jetpack-compose", kind, _line_for_offset(source, match.start())))
    return routes


def _compose_navigation_route_value(type_key: str | None, body: str) -> str | None:
    if type_key:
        return type_key
    route_match = KOTLIN_NAV_ROUTE_ARG_RE.search(body)
    if route_match:
        return route_match.group("route")
    first_arg = KOTLIN_NAV_FIRST_ARG_RE.search(body)
    if first_arg:
        return first_arg.group("route")
    return None


def _dart_page_factory_name(source: str) -> str | None:
    match = DART_PAGE_FACTORY_RE.search(source)
    return match.group("page") if match else None


def _join_flutter_route(parent: str, child: str) -> str:
    stripped = child.strip()
    if not stripped:
        return parent or "/"
    if stripped.startswith(("/", "*")):
        return _normalize_frontend_route(stripped)
    normalized_parent = _normalize_frontend_route(parent)
    if normalized_parent in {"", "/"}:
        return _normalize_frontend_route(stripped)
    return f"{normalized_parent.rstrip('/')}/{stripped.lstrip('/')}"


def _extract_components(
    file_fact: FileFact,
    source: str,
    symbols: list[SymbolFact],
    frameworks: list[FrameworkFact],
) -> list[ComponentFact]:
    normalized = file_fact.path.replace("\\", "/")
    framework = _frontend_framework_for_path(normalized, frameworks)
    props_by_name = _props_by_interface(source)
    hooks = sorted(set(HOOK_RE.findall(source)))
    components: list[ComponentFact] = []

    if normalized.endswith(".vue"):
        components.append(
            ComponentFact(
                name=Path(normalized).stem,
                path=file_fact.path,
                framework="vue",
                props=_vue_props(source),
                hooks=[],
                evidence=Evidence(file=file_fact.path, kind="frontend-component", line_start=1, line_end=1),
            )
        )
        return components
    if normalized.endswith((".cshtml", ".razor")):
        framework = _razor_markup_framework(normalized, source, {item.name for item in frameworks})
        if framework:
            components.append(
                ComponentFact(
                    name=_blazor_component_name(normalized),
                    path=file_fact.path,
                    framework=framework,
                    props=[],
                    hooks=[],
                    evidence=Evidence(file=file_fact.path, kind="frontend-component", line_start=1, line_end=1),
                )
            )
        return components
    if normalized.endswith(".svelte"):
        component_name = _svelte_component_name(normalized)
        components.append(
            ComponentFact(
                name=component_name,
                path=file_fact.path,
                framework="sveltekit" if _sveltekit_route_for_path(normalized) else "svelte",
                props=[],
                hooks=[],
                evidence=Evidence(file=file_fact.path, kind="frontend-component", line_start=1, line_end=1),
            )
        )
        return components
    if normalized.endswith(".astro"):
        components.append(
            ComponentFact(
                name=_astro_component_name(normalized),
                path=file_fact.path,
                framework="astro",
                props=_astro_props(source),
                hooks=[],
                evidence=Evidence(file=file_fact.path, kind="frontend-component", line_start=1, line_end=1),
            )
        )
        return components
    if normalized.endswith(".swift"):
        swift_components = _extract_swiftui_components(file_fact, source)
        if swift_components:
            return swift_components
    if normalized.endswith((".xaml", ".axaml")):
        xaml_component = _extract_xaml_component(file_fact, source, frameworks)
        return [xaml_component] if xaml_component else []

    if normalized.endswith(".ts") and "@Component" in source:
        return _extract_angular_components(file_fact, source)
    if _is_ember_component_path(normalized):
        ember_components = _extract_ember_components(file_fact, source)
        if ember_components:
            return ember_components
    if normalized.endswith(".dart"):
        flutter_components = _extract_flutter_components(file_fact, source)
        if flutter_components:
            return flutter_components
    if normalized.endswith(".kt") and "@Composable" in source:
        compose_components = _extract_compose_components(file_fact, source)
        if compose_components:
            return compose_components
    if normalized.endswith(".py") and _looks_like_gradio_source(source):
        gradio_components = _extract_gradio_components(file_fact, source)
        if gradio_components:
            return gradio_components
    if normalized.endswith(".py") and _looks_like_dash_source(source):
        dash_components = _extract_dash_components(file_fact, source)
        if dash_components:
            return dash_components
    if normalized.endswith(".py") and _looks_like_panel_app_source(source):
        panel_components = _extract_panel_components(file_fact, source)
        if panel_components:
            return panel_components
    if normalized.endswith(".py") and _looks_like_shiny_source(source):
        shiny_components = _extract_shiny_components(file_fact, source)
        if shiny_components:
            return shiny_components
    if "component$(" in source:
        qwik_components = _extract_qwik_components(file_fact, source)
        if qwik_components:
            return qwik_components

    if not normalized.endswith((".tsx", ".jsx", ".js", ".mjs")):
        return []
    if normalized.endswith((".js", ".mjs")) and not _looks_like_react_component_source(source):
        return []

    for symbol in symbols:
        if symbol.path != file_fact.path or symbol.kind not in {"function", "class"}:
            continue
        if not symbol.name[:1].isupper() or symbol.name.endswith("Props"):
            continue
        components.append(
            ComponentFact(
                name=symbol.name,
                path=file_fact.path,
                framework=framework,
                props=props_by_name.get(f"{symbol.name}Props", []),
                hooks=hooks,
                evidence=symbol.evidence,
            )
        )
    return components


def _extract_api_calls(root: Path, file_fact: FileFact, source: str) -> list[ApiCallFact]:
    if file_fact.path.replace("\\", "/").lower().endswith(".d.ts"):
        return []
    calls: list[ApiCallFact] = []
    endpoint_context = _api_client_endpoint_context(source, root, file_fact.path)
    for match in FETCH_RE.finditer(source):
        call_text, call_end = _js_call_text(source, match.start())
        method = _fetch_method_from_call(match.group("args"), call_text)
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=_normalize_dynamic_endpoint(match.group("endpoint"), endpoint_context),
                method=method,
                client="fetch",
                trigger="runtime",
                context="source",
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, call_end),
                ),
            )
        )
    for match in AJAX_RE.finditer(source):
        if _ajax_literal_endpoint_is_concat_fragment(match.group("args")):
            continue
        call_text, call_end = _js_call_text(source, match.start())
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=_normalize_dynamic_endpoint(match.group("endpoint"), endpoint_context),
                method=_fetch_method_from_call(match.group("args"), call_text),
                client="ajax",
                trigger="runtime",
                context="source",
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, call_end),
                ),
            )
        )
    calls.extend(_extract_ajax_expression_calls(file_fact, source, endpoint_context))
    for match in AXIOS_RE.finditer(source):
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=_normalize_dynamic_endpoint(match.group("endpoint"), endpoint_context),
                method=match.group("method").upper(),
                client="axios",
                trigger="runtime",
                context="source",
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.end()),
                ),
            )
        )
    for match in AXIOS_DIRECT_RE.finditer(source):
        endpoint = _normalize_dynamic_endpoint(match.group("endpoint"), endpoint_context)
        if not endpoint.startswith("/"):
            continue
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=endpoint,
                method=match.group("method").upper(),
                client="axios",
                trigger="runtime",
                context="api-client-direct",
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.end()),
                ),
            )
        )
    for match in CLIENT_CALL_RE.finditer(source):
        if _looks_like_backend_route_registration_context(source, match.start("method")):
            continue
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=_normalize_client_endpoint(match.group("endpoint"), endpoint_context),
                method=_http_method_from_client_method(match.group("method")),
                client=match.group("client"),
                trigger="runtime",
                context="source",
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.end()),
                ),
            )
        )
    for match in API_PATH_CLIENT_CALL_RE.finditer(source):
        if _looks_like_backend_route_registration_context(source, match.start("method")):
            continue
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=_plausible_api_path_endpoint(match.group("endpoint"), endpoint_context),
                method=_http_method_from_client_method(match.group("method")),
                client=match.group("client"),
                trigger="runtime",
                context="apiPath-helper",
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.end()),
                ),
            )
        )
    for match in NAMED_CLIENT_CALL_RE.finditer(source):
        if _looks_like_backend_route_registration_context(source, match.start("method")):
            continue
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=_normalize_dynamic_endpoint(match.group("endpoint"), endpoint_context),
                method=match.group("method").upper(),
                client=match.group("client"),
                trigger="runtime",
                context="source",
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.end()),
                ),
            )
        )
    for match in DART_CLIENT_CALL_RE.finditer(source):
        if not file_fact.path.lower().endswith(".dart") and _looks_like_angular_http_source(source, match.group("client")):
            continue
        if _looks_like_backend_route_registration_context(source, match.start("method")):
            continue
        if not _looks_like_api_client_receiver(match.group("client")):
            continue
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=_normalize_dynamic_endpoint(match.group("endpoint"), endpoint_context),
                method=match.group("method").upper(),
                client=match.group("client"),
                trigger="runtime",
                context="dart-client-call" if file_fact.path.lower().endswith(".dart") else "source",
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.end()),
                ),
            )
        )
    calls.extend(_extract_dart_api_route_client_calls(root, file_fact, source))
    for match in DART_CLIENT_VARIABLE_CALL_RE.finditer(source):
        if file_fact.language in {"csharp", "razor"} or file_fact.path.lower().endswith((".cs", ".razor", ".cshtml")):
            continue
        if _client_variable_endpoint_is_call_prefix(source, match):
            continue
        if not file_fact.path.lower().endswith(".dart") and _looks_like_service_facade_receiver(match.group("client")):
            continue
        if _looks_like_backend_route_registration_context(source, match.start("method")):
            continue
        if not _looks_like_api_client_receiver(match.group("client")):
            continue
        variable_name = match.group("endpoint")
        if variable_name == "ApiRoute":
            continue
        endpoint = endpoint_context.get(variable_name)
        normalized_endpoint = _normalize_dynamic_endpoint(endpoint, endpoint_context) if endpoint else f"dynamic:{variable_name}"
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=normalized_endpoint,
                method=match.group("method").upper(),
                client=match.group("client"),
                trigger="runtime",
                context="dart-client-variable" if file_fact.path.lower().endswith(".dart") else "source-variable",
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.end()),
                ),
            )
        )
    calls.extend(_extract_object_method_client_calls(file_fact, source, endpoint_context))
    for match in OBJECT_CLIENT_CALL_RE.finditer(source):
        body = match.group("body")
        method_match = OBJECT_METHOD_RE.search(body)
        url_match = OBJECT_URL_RE.search(body)
        if not url_match:
            continue
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=_normalize_dynamic_endpoint(url_match.group("endpoint"), endpoint_context),
                method=method_match.group("method").upper() if method_match else "GET",
                client=match.group("client"),
                trigger="runtime",
                context="object-client",
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.end()),
                ),
            )
        )
    for match in RTK_QUERY_OBJECT_RE.finditer(source):
        body = match.group("body")
        method_match = OBJECT_METHOD_RE.search(body)
        url_match = OBJECT_URL_RE.search(body)
        if not url_match:
            continue
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=_normalize_dynamic_endpoint(url_match.group("endpoint"), endpoint_context),
                method=method_match.group("method").upper() if method_match else "GET",
                client="rtk-query",
                trigger="runtime",
                context="rtk-query",
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.end()),
                ),
            )
        )
    calls.extend(_extract_wordpress_api_fetch_calls(file_fact, source, endpoint_context))
    for match in LEGACY_API_METHOD_CALL_RE.finditer(source):
        if _looks_like_backend_route_registration_context(source, match.start()):
            continue
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=_normalize_dynamic_endpoint(match.group("endpoint"), endpoint_context),
                method=match.group("method").upper(),
                client="legacy-api-method",
                trigger="runtime",
                context="source",
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.end()),
                ),
            )
        )
    for match in ANGULAR_HTTP_RE.finditer(source):
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=_endpoint_from_js_endpoint_expression(match.group("endpoint"), endpoint_context),
                method=match.group("method").upper(),
                client="angular-httpclient",
                trigger="runtime",
                context="source",
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.end()),
                ),
            )
        )
    calls.extend(_extract_csharp_http_api_calls(file_fact, source))
    for match in NUXT_FETCH_RE.finditer(source):
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=_normalize_dynamic_endpoint(match.group("endpoint"), endpoint_context),
                method=_fetch_method(match.group("args")),
                client=match.group("client"),
                trigger="runtime",
                context="source",
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.end()),
                ),
            )
        )
    for match in NUXT_DYNAMIC_FETCH_RE.finditer(source):
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=f"dynamic:{match.group('endpoint')}",
                method=_fetch_method(match.group("args") or ""),
                client=match.group("client"),
                trigger="runtime",
                context="dynamic-source",
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.end()),
                ),
            )
        )
    for match in COMPOSABLE_API_RE.finditer(source):
        if _looks_like_function_declaration_context(source, match.start()):
            continue
        endpoint = _composable_api_endpoint(match.group("client"), match.group("endpoint"))
        if not endpoint:
            continue
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=endpoint,
                method=_composable_api_method(match.group("client"), match.group("args") or ""),
                client=match.group("client"),
                trigger="runtime",
                context="composable-api",
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.end()),
                ),
            )
        )
    calls.extend(_extract_strapi_url_calls(file_fact, source, endpoint_context))
    calls.extend(_extract_openapi_ts_request_calls(file_fact, source))
    calls.extend(_extract_generated_api_client_calls(file_fact, source))
    calls.extend(_extract_api_path_wrapper_calls(file_fact, source, endpoint_context))
    calls.extend(_extract_api_service_wrapper_calls(file_fact, source, endpoint_context))
    calls.extend(_extract_trpc_client_calls(file_fact, source))
    calls.extend(_extract_electron_ipc_client_calls(file_fact, source))
    calls.extend(_extract_tauri_invoke_calls(root, file_fact, source))
    calls.extend(_extract_graphql_client_calls(file_fact, source))
    calls.extend(_extract_realtime_client_calls(file_fact, source))
    calls.extend(_extract_socketio_client_calls(file_fact, source))
    return _dedupe_api_calls([call for call in calls if _is_useful_api_endpoint(call.endpoint)])


def _extract_ajax_expression_calls(
    file_fact: FileFact,
    source: str,
    endpoint_context: dict[str, str] | None,
) -> list[ApiCallFact]:
    calls: list[ApiCallFact] = []
    for match in AJAX_CALL_RE.finditer(source):
        open_index = match.end() - 1
        close_index = _find_matching_delimiter(source, open_index, "(", ")")
        if close_index is None:
            continue
        args = _split_js_call_args(source[open_index + 1 : close_index])
        if not args:
            continue
        if not _ajax_expression_arg_is_path_like(args[0]):
            continue
        method = _fetch_method(args[1] if len(args) > 1 else "")
        for endpoint in _js_endpoint_expression_variants(args[0], endpoint_context):
            if not _is_useful_api_endpoint(endpoint):
                continue
            calls.append(
                ApiCallFact(
                    path=file_fact.path,
                    endpoint=endpoint,
                    method=method,
                    client="ajax",
                    trigger="runtime",
                    context="ajax-expression",
                    evidence=Evidence(
                        file=file_fact.path,
                        kind="frontend-api-call",
                        line_start=_line_for_offset(source, match.start()),
                        line_end=_line_for_offset(source, close_index),
                    ),
                )
            )
    return calls


def _extract_csharp_http_api_calls(file_fact: FileFact, source: str) -> list[ApiCallFact]:
    if file_fact.language not in {"csharp", "razor"} and not file_fact.path.lower().endswith((".cs", ".razor", ".cshtml")):
        return []
    calls: list[ApiCallFact] = []
    for match in CSHARP_CUSTOM_HTTP_CALL_RE.finditer(source):
        endpoint = _normalize_csharp_endpoint(
            match.group("endpoint"),
            assume_api_base=True,
            method=match.group("method"),
            args=match.group("args") or "",
        )
        if not endpoint:
            continue
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=endpoint,
                method=_csharp_http_method(match.group("method")),
                client=match.group("client"),
                trigger="runtime",
                context="csharp-http-service",
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.end()),
                ),
            )
        )
    for match in CSHARP_HTTPCLIENT_LITERAL_RE.finditer(source):
        endpoint = _normalize_csharp_endpoint(match.group("endpoint"), assume_api_base=False)
        if not endpoint:
            continue
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=endpoint,
                method=_csharp_http_method(match.group("method")),
                client=match.group("client"),
                trigger="runtime",
                context="csharp-httpclient",
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.end()),
                ),
            )
        )
    return calls


def _extract_object_method_client_calls(
    file_fact: FileFact,
    source: str,
    endpoint_context: dict[str, str],
) -> list[ApiCallFact]:
    calls: list[ApiCallFact] = []
    for match in OBJECT_METHOD_CLIENT_CALL_RE.finditer(source):
        if _looks_like_backend_route_registration_context(source, match.start("method")):
            continue
        open_index = match.end() - 1
        close_index = _find_matching_delimiter(source, open_index, "(", ")")
        if close_index is None:
            continue
        args = _split_js_call_args(source[open_index + 1 : close_index])
        endpoint: str | None = None
        method_name = match.group("method")
        method = _object_method_client_http_method(method_name, "")

        if method_name.lower() == "postform" and args:
            endpoint = _object_method_first_arg_endpoint(args[0], endpoint_context)
        elif args and args[0].lstrip().startswith("{"):
            body = args[0].strip()[1:-1]
            endpoint = _object_endpoint_from_body(body, endpoint_context)
            method = _object_method_client_http_method(method_name, body)

        if not endpoint:
            continue
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=endpoint,
                method=method,
                client=match.group("client"),
                trigger="runtime",
                context="object-method-client",
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, close_index),
                ),
            )
        )
    return calls


def _object_method_first_arg_endpoint(expression: str, context: dict[str, str]) -> str | None:
    value = expression.strip()
    literal = _js_string_literal_value(value)
    if literal is not None:
        return _normalize_client_endpoint(literal, context)
    if re.fullmatch(r"[A-Za-z_$][\w$]*", value):
        endpoint = context.get(value)
        return _normalize_dynamic_endpoint(endpoint, context) if endpoint else f"dynamic:{value}"
    return _endpoint_from_js_endpoint_expression(value, context)


def _object_method_client_http_method(method_name: str, body: str) -> str:
    lowered = method_name.lower()
    if lowered == "postform":
        return "POST"
    if lowered == "request":
        method_match = OBJECT_METHOD_RE.search(body)
        return method_match.group("method").upper() if method_match else "GET"
    return _http_method_from_client_method(method_name)


def _object_endpoint_from_body(body: str, context: dict[str, str]) -> str | None:
    match = OBJECT_ENDPOINT_VALUE_RE.search(body)
    if not match:
        return None
    value = match.group("value").strip()
    literal = _js_string_literal_value(value)
    if literal is not None:
        return _normalize_dynamic_endpoint(literal, context)
    if re.fullmatch(r"[A-Za-z_$][\w$]*", value):
        endpoint = context.get(value)
        return _normalize_dynamic_endpoint(endpoint, context) if endpoint else f"dynamic:{value}"
    return None


def _csharp_http_method(method: str) -> str:
    lowered = method.lower()
    if "post" in lowered:
        return "POST"
    if "put" in lowered:
        return "PUT"
    if "delete" in lowered:
        return "DELETE"
    if "patch" in lowered:
        return "PATCH"
    return "GET"


def _normalize_csharp_endpoint(endpoint: str, assume_api_base: bool, method: str = "", args: str = "") -> str | None:
    normalized = endpoint.strip()
    if not normalized:
        return None
    if _looks_like_csharp_wrapper_endpoint(normalized):
        return None
    if normalized.startswith(("http://", "https://")):
        parsed = urlparse(normalized)
        normalized = parsed.path or "/"
    if "?" in normalized:
        normalized = normalized.split("?", 1)[0]
    normalized = normalized.lstrip("~/")
    normalized = re.sub(r"\{[^}]*?([A-Za-z_]\w*)\s*\}", r"{\1}", normalized)
    normalized = re.sub(r"\{([A-Za-z_]\w*)\}", r"{\1}", normalized)
    if method.lower() == "httpdelete" and "{" not in normalized:
        arg_name = _first_csharp_call_argument(args)
        if arg_name:
            normalized = f"{normalized.rstrip('/')}/{{{arg_name}}}"
    static_part = re.sub(r"\{[^}]+\}", "", normalized).strip("/")
    if not static_part:
        dynamic_name = _first_match(normalized, r"\{([^}]+)\}")
        return f"dynamic:{dynamic_name or 'csharp-endpoint'}"
    if not normalized.startswith("/"):
        prefix = "/api/" if assume_api_base else "/"
        normalized = f"{prefix}{normalized}"
    return re.sub(r"/{2,}", "/", normalized)


def _looks_like_csharp_wrapper_endpoint(endpoint: str) -> bool:
    cleaned = re.sub(r"\{[^}]+\}", "", endpoint).strip("/ ")
    return not cleaned or cleaned in {"_apiUrl", "apiUrl", "baseUrl", "_baseUrl"}


def _first_csharp_call_argument(args: str) -> str | None:
    match = re.search(r",\s*(?P<name>[A-Za-z_]\w*)\b", args)
    return match.group("name") if match else None


def _extract_wordpress_api_fetch_calls(
    file_fact: FileFact,
    source: str,
    endpoint_context: dict[str, str],
) -> list[ApiCallFact]:
    calls: list[ApiCallFact] = []
    if "apiFetch" not in source:
        return calls
    for match in WORDPRESS_API_FETCH_RE.finditer(source):
        body = match.group("body")
        path_match = WORDPRESS_API_FETCH_PATH_RE.search(body)
        if not path_match:
            continue
        endpoint = path_match.group("endpoint")
        if endpoint:
            endpoint = _wordpress_api_fetch_endpoint(_normalize_dynamic_endpoint(endpoint, endpoint_context))
            context = "wordpress-api-fetch"
        else:
            endpoint = f"dynamic:{path_match.group('variable')}"
            context = "wordpress-api-fetch-variable"
        method_match = WORDPRESS_API_FETCH_METHOD_RE.search(body)
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=endpoint,
                method=method_match.group("method").upper() if method_match else "GET",
                client=match.group("client"),
                trigger="runtime",
                context=context,
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.end()),
                ),
            )
        )
    return calls


def _wordpress_api_fetch_endpoint(endpoint: str) -> str:
    if endpoint.startswith(("dynamic:", "http://", "https://")):
        return endpoint
    if not endpoint.startswith("/"):
        endpoint = f"/{endpoint}"
    if endpoint == "/wp-json" or endpoint.startswith("/wp-json/"):
        return endpoint
    return f"/wp-json{endpoint}"


def _extract_dart_api_route_client_calls(root: Path, file_fact: FileFact, source: str) -> list[ApiCallFact]:
    if "ApiRoute." not in source:
        return []
    route_map = dart_api_route_map(root)
    if not route_map:
        return []
    calls: list[ApiCallFact] = []
    for match in DART_API_ROUTE_CLIENT_CALL_RE.finditer(source):
        if _looks_like_backend_route_registration_context(source, match.start("method")):
            continue
        if not _looks_like_api_client_receiver(match.group("client")):
            continue
        endpoints = _dart_api_route_endpoint_variants(route_map, match.group("route"), match.group("accessor"))
        for endpoint in endpoints:
            calls.append(
                ApiCallFact(
                    path=file_fact.path,
                    endpoint=endpoint,
                    method=match.group("method").upper(),
                    client=match.group("client"),
                    trigger="runtime",
                    context=f"dart-api-route:{match.group('accessor')}",
                    evidence=Evidence(
                        file=file_fact.path,
                        kind="frontend-api-call",
                        line_start=_line_for_offset(source, match.start()),
                        line_end=_line_for_offset(source, match.end()),
                    ),
                )
            )
    return calls


def _dart_api_route_endpoint_variants(route_map: dict[tuple[str, str], str], route_name: str, accessor: str) -> list[str]:
    normalized_accessor = accessor.lower()
    if normalized_accessor in {"v1", "v2"}:
        endpoint = route_map.get((route_name, normalized_accessor))
        return [endpoint] if endpoint else []
    return [
        endpoint
        for endpoint in (route_map.get((route_name, "v1")), route_map.get((route_name, "v2")))
        if endpoint
    ]


def _extract_state_usages(file_fact: FileFact, source: str, frontend_frameworks: set[str]) -> list[StateUsageFact]:
    usages: list[StateUsageFact] = []
    is_angular_state_source = "angular" in frontend_frameworks or "@angular/" in source
    if file_fact.language == "dart" or file_fact.path.lower().endswith(".dart"):
        usages.extend(_extract_dart_state_usages(file_fact, source))
    if file_fact.language == "kotlin" or file_fact.path.lower().endswith(".kt"):
        usages.extend(_extract_kotlin_state_usages(file_fact, source))
    if file_fact.language == "swift" or file_fact.path.lower().endswith(".swift"):
        usages.extend(_extract_swift_state_usages(file_fact, source))
    if (file_fact.language == "python" or file_fact.path.lower().endswith(".py")) and (
        "streamlit" in frontend_frameworks or _looks_like_streamlit_source(source)
    ):
        usages.extend(_extract_streamlit_state_usages(file_fact, source))
    if (file_fact.language == "python" or file_fact.path.lower().endswith(".py")) and (
        "shiny" in frontend_frameworks or _looks_like_shiny_source(source)
    ):
        usages.extend(_extract_shiny_state_usages(file_fact, source))
    if is_angular_state_source:
        usages.extend(_extract_angular_state_usages(file_fact, source))
    for library, usage, pattern in STATE_PATTERNS:
        if library == "react" and not _looks_like_react_state_source(file_fact, source, frontend_frameworks):
            continue
        if library in {"qwik", "qwik-city"} and "qwik" not in frontend_frameworks and "@builder.io/qwik" not in source and "component$(" not in source:
            continue
        if library in {"solid", "solid-router"} and "solid" not in frontend_frameworks and "solid-js" not in source and "@solidjs/router" not in source:
            continue
        if library == "tanstack-start" and "tanstack-start" not in frontend_frameworks and "@tanstack/" not in source:
            continue
        if library == "zustand" and "zustand" not in source:
            continue
        if library == "vue" and "vue" not in frontend_frameworks and "from 'vue'" not in source and 'from "vue"' not in source:
            continue
        if library == "angular-rxjs" and is_angular_state_source:
            continue
        if library == "angular-rxjs" and "angular" not in frontend_frameworks and "@angular/" not in source:
            continue
        if library == "ember" and "ember" not in frontend_frameworks and "@ember/" not in source and "@glimmer/" not in source:
            continue
        for match in pattern.finditer(source):
            line = _line_for_offset(source, match.start())
            name = match.group(1) if match.groups() else match.group(0).strip("(")
            usages.append(
                StateUsageFact(
                    source=file_fact.path,
                    library=library,
                    usage=usage,
                    name=name,
                    evidence=Evidence(file=file_fact.path, kind="state-usage", line_start=line, line_end=line),
                )
            )
    return _dedupe_state_usages(usages)


def _extract_streamlit_state_usages(file_fact: FileFact, source: str) -> list[StateUsageFact]:
    usages: list[StateUsageFact] = []
    seen_names: set[str] = set()
    generic_start: int | None = None

    def append_usage(name: str, offset: int) -> None:
        if name in seen_names:
            return
        seen_names.add(name)
        usages.append(_state_usage(file_fact, source, offset, "streamlit", "session-state", name))

    for match in STREAMLIT_SESSION_STATE_CONTAINS_RE.finditer(source):
        append_usage(match.group("key"), match.start("key"))

    for match in STREAMLIT_SESSION_STATE_RE.finditer(source):
        name = match.group("bracket") or match.group("attr") or "session_state"
        if name == "session_state":
            generic_start = match.start() if generic_start is None else generic_start
            continue
        append_usage(name, match.start())
    if not usages and generic_start is not None:
        append_usage("session_state", generic_start)
    return usages


def _looks_like_streamlit_source(source: str) -> bool:
    return bool(
        re.search(r"^\s*(?:import\s+streamlit\b|from\s+streamlit\s+import\b)", source, re.MULTILINE)
        or re.search(r"\bstreamlit\.", source)
        or re.search(
            r"\bst\."
            r"(?:set_page_config|title|header|write|markdown|sidebar|session_state|"
            r"text_input|button|chat_input)\b",
            source,
        )
    )


def _extract_gradio_components(file_fact: FileFact, source: str) -> list[ComponentFact]:
    components: list[ComponentFact] = []
    for match in GRADIO_COMPONENT_RE.finditer(source):
        kind = _normalize_gradio_component_kind(match.group("kind"))
        body = match.group("body")
        props = _gradio_component_props(body)
        label = _gradio_component_label(kind, body, props)
        name = f"{kind}:{label}" if label else kind
        line = _line_for_offset(source, match.start())
        components.append(
            ComponentFact(
                name=name,
                path=file_fact.path,
                framework="gradio",
                props=props,
                hooks=[],
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-component",
                    line_start=line,
                    line_end=line,
                ),
            )
        )
    return _dedupe_components(components)


def _normalize_gradio_component_kind(kind: str) -> str:
    normalized = kind[:1].upper() + kind[1:]
    return {"Textarea": "TextArea", "Json": "JSON", "Html": "HTML"}.get(normalized, normalized)


def _gradio_component_label(kind: str, body: str, props: list[str]) -> str | None:
    if kind == "Examples":
        return None
    prop_values = {prop.split("=", 1)[0].lower(): prop.split("=", 1)[1] for prop in props if "=" in prop}
    for key in ("title", "label", "value"):
        value = prop_values.get(key)
        if value:
            return value.strip("`")
    first_arg = GRADIO_STRING_ARG_RE.search(body)
    if first_arg:
        return _clean_gradio_prop_value(first_arg.group("value"))
    return None


def _gradio_component_props(body: str) -> list[str]:
    props: list[str] = []
    for match in GRADIO_PROP_RE.finditer(body):
        key = match.group("key")
        value = _clean_gradio_prop_value(match.group("value"))
        if value:
            props.append(f"{key}={value}")
    return _dedupe(props)


def _clean_gradio_prop_value(value: str) -> str:
    cleaned = " ".join(value.strip().strip(",").strip().strip("'\"").split())
    if len(cleaned) > 80:
        return cleaned[:77].rstrip() + "..."
    return cleaned


def _looks_like_gradio_source(source: str) -> bool:
    return bool(
        re.search(r"\bgr\.(?:Interface|Blocks|ChatInterface|TabbedInterface|load)\b", source)
        or re.search(
            r"\bgradio\.(?:Interface|Blocks|ChatInterface|TabbedInterface|load)\b",
            source,
        )
    )


def _extract_dash_components(file_fact: FileFact, source: str) -> list[ComponentFact]:
    components: list[ComponentFact] = []
    for kind, body, offset in _iter_dash_component_calls(source):
        props = _dash_component_props(body)
        label = _dash_component_label(kind, body, props)
        if kind in {"Div", "Span"} and not label and not props:
            continue
        name = f"{kind}:{label}" if label else kind
        line = _line_for_offset(source, offset)
        components.append(
            ComponentFact(
                name=name,
                path=file_fact.path,
                framework="dash",
                props=props,
                hooks=[],
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-component",
                    line_start=line,
                    line_end=line,
                ),
            )
        )
    return _dedupe_components(components)


def _iter_dash_component_calls(source: str) -> list[tuple[str, str, int]]:
    calls: list[tuple[str, str, int]] = []
    for match in DASH_COMPONENT_START_RE.finditer(source):
        open_paren = match.end() - 1
        close_paren = _matching_paren_index(source, open_paren)
        if close_paren is None:
            continue
        calls.append((match.group("kind"), source[open_paren + 1 : close_paren], match.start()))
    return calls


def _matching_paren_index(source: str, open_paren: int) -> int | None:
    depth = 0
    quote: str | None = None
    escape = False
    for index in range(open_paren, len(source)):
        char = source[index]
        if quote:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
    return None


def _dash_component_label(kind: str, body: str, props: list[str]) -> str | None:
    prop_values = {prop.split("=", 1)[0].lower(): prop.split("=", 1)[1] for prop in props if "=" in prop}
    for key in ("id", "children", "value", "placeholder"):
        value = prop_values.get(key)
        if value:
            return value.strip("`")
    if kind in {"H1", "H2", "H3", "H4", "H5", "H6", "P", "Button"}:
        first_arg = next(iter(_split_top_level_args(body)), "")
        string_match = DASH_STRING_ARG_RE.fullmatch(first_arg.strip())
        if string_match:
            return _clean_dash_prop_value(string_match.group("value"))
    return None


def _dash_component_props(body: str) -> list[str]:
    props: list[str] = []
    for part in _split_top_level_args(body):
        match = DASH_TOP_LEVEL_PROP_RE.match(part.strip())
        if not match:
            continue
        key = match.group("key")
        value = _clean_dash_prop_value(match.group("value"))
        if value:
            props.append(f"{key}={value}")
    return _dedupe(props)


def _split_top_level_args(body: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    quote: str | None = None
    escape = False
    for index, char in enumerate(body):
        if quote:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
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
        elif char == "," and depth == 0:
            parts.append(body[start:index].strip())
            start = index + 1
    tail = body[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def _clean_dash_prop_value(value: str) -> str:
    cleaned = " ".join(value.strip().strip(",").strip().strip("'\"").split())
    if len(cleaned) > 80:
        return cleaned[:77].rstrip() + "..."
    return cleaned


def _looks_like_dash_source(source: str) -> bool:
    return bool(
        re.search(r"\b(?:dash\.)?Dash\s*\(", source)
        or re.search(r"\bapp\.layout\s*=", source)
        or re.search(r"@\s*app\.callback\s*\(", source)
    )


def _extract_panel_components(file_fact: FileFact, source: str) -> list[ComponentFact]:
    components: list[ComponentFact] = []
    for kind, body, offset in _iter_panel_component_calls(source):
        kind = "Panel" if kind.lower() == "panel" else kind
        props = _panel_component_props(body)
        label = _panel_component_label(kind, body, props)
        if kind in {"Column", "Row", "Tabs"} and not label and not props:
            continue
        name = f"{kind}:{label}" if label else kind
        line = _line_for_offset(source, offset)
        components.append(
            ComponentFact(
                name=name,
                path=file_fact.path,
                framework="panel",
                props=props,
                hooks=[],
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-component",
                    line_start=line,
                    line_end=line,
                ),
            )
        )
    return _dedupe_components(components)


def _iter_panel_component_calls(source: str) -> list[tuple[str, str, int]]:
    calls: list[tuple[str, str, int]] = []
    for match in PANEL_COMPONENT_START_RE.finditer(source):
        kind = match.group("kind")
        if kind.lower() == "extension":
            continue
        open_paren = match.end() - 1
        close_paren = _matching_paren_index(source, open_paren)
        if close_paren is None:
            continue
        calls.append((kind, source[open_paren + 1 : close_paren], match.start()))
    return calls


def _panel_component_label(kind: str, body: str, props: list[str]) -> str | None:
    prop_values = {prop.split("=", 1)[0].lower(): prop.split("=", 1)[1] for prop in props if "=" in prop}
    for key in ("title", "name", "value", "area"):
        value = prop_values.get(key)
        if value:
            return value.strip("`")
    if kind in {"Panel", "Markdown", "HTML", "Str", "Alert"}:
        first_arg = next(iter(_split_top_level_args(body)), "")
        string_match = PANEL_STRING_ARG_RE.fullmatch(first_arg.strip())
        if string_match:
            return _clean_panel_prop_value(string_match.group("value"))
    return None


def _panel_component_props(body: str) -> list[str]:
    props: list[str] = []
    for part in _split_top_level_args(body):
        match = PANEL_TOP_LEVEL_PROP_RE.match(part.strip())
        if not match:
            continue
        key = match.group("key")
        value = _clean_panel_prop_value(match.group("value"))
        if value:
            props.append(f"{key}={value}")
    return _dedupe(props)


def _clean_panel_prop_value(value: str) -> str:
    cleaned = " ".join(value.strip().strip(",").strip().strip("'\"").split())
    if len(cleaned) > 80:
        return cleaned[:77].rstrip() + "..."
    return cleaned


def _looks_like_panel_app_source(source: str) -> bool:
    return bool(
        re.search(r"\.servable\s*\(", source)
        or re.search(r"\bpn\.serve\s*\(|\bpanel\.serve\s*\(", source)
    ) and bool(
        re.search(r"^\s*(?:import\s+panel\b|from\s+panel\s+import\b)", source, re.MULTILINE)
        or re.search(r"\bpn\.", source)
    )


def _extract_shiny_components(file_fact: FileFact, source: str) -> list[ComponentFact]:
    components: list[ComponentFact] = []
    for kind, body, offset in _iter_shiny_component_calls(source):
        normalized_kind = _normalize_shiny_component_kind(kind)
        props = _shiny_component_props(kind, body)
        label = _shiny_component_label(kind, normalized_kind, body, props)
        if normalized_kind in {"Div", "Span"} and not label and not props:
            continue
        name = f"{normalized_kind}:{label}" if label else normalized_kind
        line = _line_for_offset(source, offset)
        components.append(
            ComponentFact(
                name=name,
                path=file_fact.path,
                framework="shiny",
                props=props,
                hooks=[],
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-component",
                    line_start=line,
                    line_end=line,
                ),
            )
        )
    return _dedupe_components(components)


def _iter_shiny_component_calls(source: str) -> list[tuple[str, str, int]]:
    calls: list[tuple[str, str, int]] = []
    for match in SHINY_COMPONENT_START_RE.finditer(source):
        open_paren = match.end() - 1
        close_paren = _matching_paren_index(source, open_paren)
        if close_paren is None:
            continue
        calls.append((match.group("kind"), source[open_paren + 1 : close_paren], match.start()))
    return calls


def _normalize_shiny_component_kind(kind: str) -> str:
    if kind.upper() == "HTML":
        return "HTML"
    if re.fullmatch(r"h[1-6]", kind, re.IGNORECASE):
        return kind.upper()
    return "".join(part[:1].upper() + part[1:].lower() for part in kind.split("_") if part)


def _shiny_component_label(kind: str, normalized_kind: str, body: str, props: list[str]) -> str | None:
    prop_values = {prop.split("=", 1)[0].lower(): prop.split("=", 1)[1] for prop in props if "=" in prop}
    if kind.lower().startswith(("input_", "output_")):
        for key in ("id", "output_id"):
            value = prop_values.get(key)
            if value:
                return value.strip("`")
        first_arg = next(iter(_split_top_level_args(body)), "")
        string_match = SHINY_STRING_ARG_RE.fullmatch(first_arg.strip())
        if string_match:
            return _clean_shiny_prop_value(string_match.group("value"))
    for key in ("title", "label", "value"):
        value = prop_values.get(key)
        if value:
            return value.strip("`")
    if normalized_kind in {"H1", "H2", "H3", "H4", "H5", "H6", "Markdown", "HTML", "NavPanel"}:
        first_arg = next(iter(_split_top_level_args(body)), "")
        string_match = SHINY_STRING_ARG_RE.fullmatch(first_arg.strip())
        if string_match:
            return _clean_shiny_prop_value(string_match.group("value"))
    return None


def _shiny_component_props(kind: str, body: str) -> list[str]:
    props: list[str] = []
    parts = _split_top_level_args(body)
    if kind.lower().startswith(("input_", "output_")):
        string_args = [
            _clean_shiny_prop_value(match.group("value"))
            for part in parts[:2]
            if (match := SHINY_STRING_ARG_RE.fullmatch(part.strip()))
        ]
        if string_args:
            props.append(f"id={string_args[0]}")
        if len(string_args) > 1:
            props.append(f"label={string_args[1]}")
    for part in parts:
        match = SHINY_TOP_LEVEL_PROP_RE.match(part.strip())
        if not match:
            continue
        key = match.group("key")
        value = _clean_shiny_prop_value(match.group("value"))
        if value:
            props.append(f"{key}={value}")
    return _dedupe(props)


def _clean_shiny_prop_value(value: str) -> str:
    cleaned = " ".join(value.strip().strip(",").strip().strip("'\"").split())
    if len(cleaned) > 80:
        return cleaned[:77].rstrip() + "..."
    return cleaned


def _looks_like_shiny_source(source: str) -> bool:
    has_import = bool(
        re.search(r"^\s*(?:from\s+shiny(?:\.[A-Za-z_]\w*)?\s+import\b|import\s+shiny\b)", source, re.MULTILINE)
        or re.search(r"\bshiny\.", source)
    )
    has_app_signal = bool(
        re.search(r"\b(?:shiny\.)?App\s*\(", source)
        or re.search(r"\b(?:ui|shiny\.ui)\.page_[A-Za-z_]\w*\s*\(", source)
        or re.search(r"@\s*(?:render|reactive)\.[A-Za-z_]\w*", source)
    )
    return has_import and has_app_signal


def _extract_shiny_state_usages(file_fact: FileFact, source: str) -> list[StateUsageFact]:
    usages: list[StateUsageFact] = []
    seen: set[tuple[str, str]] = set()

    def append_usage(usage: str, name: str, offset: int) -> None:
        key = (usage, name)
        if key in seen:
            return
        seen.add(key)
        usages.append(_state_usage(file_fact, source, offset, "shiny", usage, name))

    for match in SHINY_INPUT_CALL_RE.finditer(source):
        append_usage("input", match.group("name"), match.start())
    for match in SHINY_DECORATOR_RE.finditer(source):
        append_usage(match.group("namespace"), match.group("kind"), match.start())
    return usages


def _extract_angular_state_usages(file_fact: FileFact, source: str) -> list[StateUsageFact]:
    usages: list[StateUsageFact] = []
    for match in ANGULAR_SIGNAL_ASSIGN_RE.finditer(source):
        usages.append(
            _state_usage(
                file_fact,
                source,
                match.start(),
                "angular",
                match.group("kind"),
                match.group("name"),
            )
        )
    for match in ANGULAR_RXJS_SUBJECT_ASSIGN_RE.finditer(source):
        usages.append(
            _state_usage(
                file_fact,
                source,
                match.start(),
                "angular-rxjs",
                "subject",
                match.group("name"),
            )
        )
    for match in ANGULAR_RXJS_SUBJECT_NEXT_RE.finditer(source):
        usages.append(
            _state_usage(
                file_fact,
                source,
                match.start(),
                "angular-rxjs",
                "subject-next",
                match.group("name"),
            )
        )
    for match in ANGULAR_RXJS_AS_OBSERVABLE_RE.finditer(source):
        usages.append(
            _state_usage(
                file_fact,
                source,
                match.start(),
                "angular-rxjs",
                "observable",
                f"{match.group('name')}<-{match.group('subject')}",
            )
        )
    return usages


def _extract_swift_state_usages(file_fact: FileFact, source: str) -> list[StateUsageFact]:
    usages: list[StateUsageFact] = []
    for match in SWIFTUI_STATE_RE.finditer(source):
        usages.append(_state_usage(file_fact, source, match.start(), "swiftui", "property-wrapper", f"@{match.group('kind')} {match.group('name')}"))
    for match in SWIFT_TCA_STORE_OF_RE.finditer(source):
        usages.append(_state_usage(file_fact, source, match.start(), "tca", "store", f"{match.group('name')}:{_clean_swift_type(match.group('feature'))}"))
    for match in SWIFT_TCA_BINDABLE_STORE_RE.finditer(source):
        feature = _clean_swift_type(match.group("feature") or "")
        name = match.group("name")
        usages.append(_state_usage(file_fact, source, match.start(), "tca", "bindable-store", f"{name}:{feature}" if feature else name))
    for match in SWIFT_TCA_STORE_INIT_RE.finditer(source):
        usages.append(_state_usage(file_fact, source, match.start(), "tca", "store-init", _clean_swift_type(match.group("feature"))))
    for match in SWIFT_TCA_REDUCER_RE.finditer(source):
        usages.append(_state_usage(file_fact, source, match.start(), "tca", "reducer", match.group("name")))
    for match in SWIFT_TCA_OBSERVABLE_STATE_RE.finditer(source):
        usages.append(_state_usage(file_fact, source, match.start(), "tca", "observable-state", match.group("name")))
    return _dedupe_state_usages(usages)


def _clean_swift_type(value: str) -> str:
    return " ".join(value.strip().split())


def _extract_kotlin_state_usages(file_fact: FileFact, source: str) -> list[StateUsageFact]:
    usages: list[StateUsageFact] = []
    for match in KOTLIN_VIEWMODEL_RE.finditer(source):
        usages.append(_state_usage(file_fact, source, match.start(), "androidx-lifecycle", "viewmodel", match.group("name")))
    for match in KOTLIN_STATE_FLOW_RE.finditer(source):
        library = "kotlin-flow"
        usage = "mutable-state-flow" if match.group("kind") == "MutableStateFlow" else "state-flow"
        usages.append(_state_usage(file_fact, source, match.start(), library, usage, match.group("name")))
    for match in KOTLIN_MUTABLE_STATE_FLOW_CALL_RE.finditer(source):
        usages.append(_state_usage(file_fact, source, match.start(), "kotlin-flow", "mutable-state-flow", match.group("name")))
    for match in KOTLIN_SAVED_STATE_FLOW_RE.finditer(source):
        usages.append(_state_usage(file_fact, source, match.start(), "androidx-lifecycle", "saved-state-flow", match.group("name")))
    for match in KOTLIN_COLLECT_AS_STATE_RE.finditer(source):
        usages.append(_state_usage(file_fact, source, match.start(), "androidx-lifecycle-compose", "collect-as-state", match.group("name")))
    for match in KOTLIN_MUTABLE_STATE_RE.finditer(source):
        usages.append(_state_usage(file_fact, source, match.start(), "jetpack-compose", "mutable-state", match.group("name")))
    for match in KOTLIN_REMEMBER_STATE_RE.finditer(source):
        usages.append(_state_usage(file_fact, source, match.start(), "jetpack-compose", "remember-state", match.group("name")))
    return _dedupe_state_usages(usages)


def _state_usage(
    file_fact: FileFact,
    source: str,
    offset: int,
    library: str,
    usage: str,
    name: str,
) -> StateUsageFact:
    line = _line_for_offset(source, offset)
    return StateUsageFact(
        source=file_fact.path,
        library=library,
        usage=usage,
        name=name,
        evidence=Evidence(file=file_fact.path, kind="state-usage", line_start=line, line_end=line),
    )


def _extract_dart_state_usages(file_fact: FileFact, source: str) -> list[StateUsageFact]:
    usages: list[StateUsageFact] = []
    for match in DART_FLUTTER_HOOK_RE.finditer(source):
        line = _line_for_offset(source, match.start())
        usages.append(
            StateUsageFact(
                source=file_fact.path,
                library="flutter-hooks",
                usage="hook",
                name=match.group(1),
                evidence=Evidence(file=file_fact.path, kind="state-usage", line_start=line, line_end=line),
            )
        )
    for match in DART_RIVERPOD_REF_RE.finditer(source):
        line = _line_for_offset(source, match.start())
        usages.append(
            StateUsageFact(
                source=file_fact.path,
                library="riverpod",
                usage=match.group("usage"),
                name=match.group("name"),
                evidence=Evidence(file=file_fact.path, kind="state-usage", line_start=line, line_end=line),
            )
        )
    for match in DART_PROVIDER_DECL_RE.finditer(source):
        line = _line_for_offset(source, match.start())
        provider_kind = match.group("kind").split(".")[-1]
        usages.append(
            StateUsageFact(
                source=file_fact.path,
                library="riverpod",
                usage=f"provider:{provider_kind}",
                name=match.group("name"),
                evidence=Evidence(file=file_fact.path, kind="state-usage", line_start=line, line_end=line),
            )
        )
    for match in DART_RIVERPOD_ANNOTATION_RE.finditer(source):
        line = _line_for_offset(source, match.start())
        usages.append(
            StateUsageFact(
                source=file_fact.path,
                library="riverpod",
                usage="provider:@riverpod",
                name=match.group("name"),
                evidence=Evidence(file=file_fact.path, kind="state-usage", line_start=line, line_end=line),
            )
        )
    for match in DART_PROVIDER_SCOPE_RE.finditer(source):
        line = _line_for_offset(source, match.start())
        usages.append(
            StateUsageFact(
                source=file_fact.path,
                library="riverpod",
                usage="scope",
                name="ProviderScope",
                evidence=Evidence(file=file_fact.path, kind="state-usage", line_start=line, line_end=line),
            )
        )
    return usages


def _looks_like_react_state_source(file_fact: FileFact, source: str, frontend_frameworks: set[str]) -> bool:
    normalized = file_fact.path.lower().replace("\\", "/")
    if normalized.endswith(".dart"):
        return False
    if "@builder.io/qwik" in source and "from 'react'" not in source and 'from "react"' not in source:
        return False
    if "solid-js" in source and "from 'react'" not in source and 'from "react"' not in source:
        return False
    if normalized.endswith((".tsx", ".jsx")):
        return True
    return "react" in frontend_frameworks or "from 'react'" in source or 'from "react"' in source


def _api_endpoint_from_expression(expression: str) -> str | None:
    value = expression.strip()
    if not value:
        return None
    if value[0] in {"'", '"', "`"} and value[-1:] == value[0]:
        endpoint = value[1:-1]
        return endpoint if endpoint.startswith("/") else None
    if re.fullmatch(r"[A-Za-z_$][\w$]*", value):
        return f"dynamic:{value}"
    return None


def _composable_api_endpoint(client: str, expression: str) -> str | None:
    normalized_client = client.lower()
    if normalized_client in {"usequeryapi", "usesearchandpaginatequeryapi"}:
        return "/api/stats/:domain/query"
    return _api_endpoint_from_expression(expression)


def _composable_api_method(client: str, args: str) -> str:
    normalized_client = client.lower()
    if normalized_client in {"usequeryapi", "usesearchandpaginatequeryapi"}:
        return "POST"
    return _fetch_method(args)


def _plausible_api_path_endpoint(path_expression: str, context: dict[str, str] | None = None) -> str:
    path = _normalize_dynamic_endpoint(path_expression, context).strip()
    if not path.startswith("/"):
        path = f"/{path}"
    return _normalize_client_endpoint(f"/api/stats/:domain{path}", context)


def _client_variable_endpoint_is_call_prefix(source: str, match: re.Match[str]) -> bool:
    suffix = source[match.end("endpoint") : match.end("endpoint") + 8].lstrip()
    return suffix.startswith((".", "("))


def _endpoint_from_js_endpoint_expression(expression: str, context: dict[str, str] | None = None) -> str:
    value = expression.strip()
    if "+" not in value:
        literal = _js_string_literal_value(value)
        return _normalize_client_endpoint(literal if literal is not None else value, context)

    parts = _split_js_concat_parts(value)
    if not parts:
        return _normalize_client_endpoint(value, context)

    endpoint_parts: list[str] = []
    for part in parts:
        literal = _js_string_literal_value(part)
        if literal is not None:
            endpoint_parts.append(literal)
            continue
        endpoint_parts.append(f":{_js_expression_param_name(part) or 'param'}")
    return _normalize_client_endpoint("".join(endpoint_parts), context)


def _split_js_concat_parts(expression: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    quote: str | None = None
    escaped = False
    for char in expression:
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\":
            current.append(char)
            escaped = True
            continue
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in {"'", '"', "`"}:
            quote = char
            current.append(char)
            continue
        if char == "+":
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []
            continue
        current.append(char)
    part = "".join(current).strip()
    if part:
        parts.append(part)
    return parts


def _js_string_literal_value(expression: str) -> str | None:
    stripped = expression.strip()
    if len(stripped) < 2 or stripped[0] not in {"'", '"', "`"} or stripped[-1] != stripped[0]:
        return None
    return stripped[1:-1]


def _js_expression_param_name(expression: str) -> str | None:
    identifiers = [item for item in re.findall(r"[A-Za-z_$][\w$]*", expression) if item not in {"this", "true", "false", "null", "undefined"}]
    return identifiers[-1] if identifiers else None


def _extract_api_path_wrapper_calls(
    file_fact: FileFact,
    source: str,
    endpoint_context: dict[str, str] | None,
) -> list[ApiCallFact]:
    calls: list[ApiCallFact] = []
    for match in API_PATH_WRAPPER_CALL_RE.finditer(source):
        if _looks_like_function_declaration_context(source, match.start()):
            continue
        open_index = source.find("(", match.start())
        close_index = _find_matching_delimiter(source, open_index, "(", ")")
        if close_index is None:
            continue
        args = _split_js_call_args(source[open_index + 1 : close_index])
        if not args:
            continue
        endpoint = _api_path_call_endpoint(args[0], endpoint_context)
        if not endpoint:
            continue
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=endpoint,
                method=_api_path_wrapper_http_method(match.group("client")),
                client=match.group("client"),
                trigger="runtime",
                context="apiPath-wrapper",
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, close_index),
                ),
            )
        )
    return calls


def _api_path_call_endpoint(expression: str, context: dict[str, str] | None = None) -> str | None:
    match = re.search(r"\b(?:[A-Za-z_$][\w$]*\.)?apiPath\s*\(", expression)
    if not match:
        return None
    open_index = expression.find("(", match.start())
    close_index = _find_matching_delimiter(expression, open_index, "(", ")")
    if close_index is None:
        return None
    args = _split_js_call_args(expression[open_index + 1 : close_index])
    if len(args) < 2:
        return None
    path_expression = _js_string_literal_value(args[1]) or args[1]
    return _plausible_api_path_endpoint(path_expression, context)


def _api_path_wrapper_http_method(client: str) -> str:
    normalized = client.lower()
    if normalized.startswith(("post", "create", "submit", "save")):
        return "POST"
    if normalized.startswith(("put", "update")):
        return "PUT"
    if normalized.startswith(("delete", "remove")):
        return "DELETE"
    return "GET"


def _extract_api_service_wrapper_calls(
    file_fact: FileFact,
    source: str,
    endpoint_context: dict[str, str] | None,
) -> list[ApiCallFact]:
    calls: list[ApiCallFact] = []
    for match in API_SERVICE_METHOD_RE.finditer(source):
        open_index = source.find("(", match.start())
        close_index = _find_matching_delimiter(source, open_index, "(", ")")
        if close_index is None:
            continue
        args = _split_js_call_args(source[open_index + 1 : close_index])
        method = match.group("method").lower()
        http_method = _api_service_http_method(method)
        for endpoint in _api_service_endpoint_variants(method, args, endpoint_context):
            calls.append(
                ApiCallFact(
                    path=file_fact.path,
                    endpoint=endpoint,
                    method=http_method,
                    client=match.group("client"),
                    trigger="runtime",
                    context="api-service-wrapper",
                    evidence=Evidence(
                        file=file_fact.path,
                        kind="frontend-api-call",
                        line_start=_line_for_offset(source, match.start()),
                        line_end=_line_for_offset(source, close_index),
                    ),
                )
            )
    return calls


def _api_service_http_method(method: str) -> str:
    return {
        "get": "GET",
        "query": "GET",
        "post": "POST",
        "put": "PUT",
        "update": "PUT",
        "delete": "DELETE",
    }.get(method, method.upper())


def _api_service_endpoint_variants(
    method: str,
    args: list[str],
    endpoint_context: dict[str, str] | None,
) -> list[str]:
    if not args:
        return []
    endpoints = _js_endpoint_expression_variants(args[0], endpoint_context)
    if method in {"get", "update"} and len(args) > 1:
        segment = _js_path_segment_from_expression(args[1])
        if segment:
            endpoints = [_join_endpoint_segment(endpoint, segment) for endpoint in endpoints]
    return _dedupe(endpoint for endpoint in endpoints if _is_useful_api_endpoint(endpoint))


def _js_endpoint_expression_variants(expression: str, context: dict[str, str] | None = None) -> list[str]:
    value = expression.strip()
    if "+" not in value:
        return [_endpoint_from_js_endpoint_expression(value, context)]
    variants = [""]
    for part in _split_js_concat_parts(value):
        literal = _js_string_literal_value(part)
        if literal is not None:
            part_variants = [literal]
        else:
            part_variants = _js_ternary_literal_variants(part) or [f":{_js_expression_param_name(part) or 'param'}"]
        variants = [prefix + suffix for prefix in variants for suffix in part_variants]
    return _dedupe(_normalize_client_endpoint(endpoint, context) for endpoint in variants)


def _js_ternary_literal_variants(expression: str) -> list[str] | None:
    value = expression.strip()
    while value.startswith("(") and value.endswith(")"):
        close = _find_matching_delimiter(value, 0, "(", ")")
        if close != len(value) - 1:
            break
        value = value[1:-1].strip()
    match = re.search(
        r"\?\s*(?P<q1>['\"`])(?P<yes>.*?)(?P=q1)\s*:\s*(?P<q2>['\"`])(?P<no>.*?)(?P=q2)",
        value,
        re.DOTALL,
    )
    if not match:
        return None
    return [match.group("yes"), match.group("no")]


def _js_path_segment_from_expression(expression: str) -> str | None:
    value = expression.strip()
    literal = _js_string_literal_value(value)
    if literal is not None:
        segment = _normalize_dynamic_endpoint(literal).strip("/")
    elif re.fullmatch(r"[A-Za-z_$][\w$]*", value):
        segment = f":{value}"
    else:
        segment = f":{_js_expression_param_name(value) or 'param'}"
    return segment or None


def _join_endpoint_segment(endpoint: str, segment: str) -> str:
    if endpoint.startswith(("dynamic:", "http://", "https://")):
        return endpoint
    return re.sub(r"/{2,}", "/", f"{endpoint.rstrip('/')}/{segment.lstrip('/')}")


def _split_js_call_args(source: str) -> list[str]:
    args: list[str] = []
    current: list[str] = []
    depth = 0
    quote: str | None = None
    escaped = False
    for char in source:
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\":
            current.append(char)
            escaped = True
            continue
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in {"'", '"', "`"}:
            quote = char
            current.append(char)
            continue
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth = max(0, depth - 1)
        if char == "," and depth == 0:
            arg = "".join(current).strip()
            if arg:
                args.append(arg)
            current = []
            continue
        current.append(char)
    arg = "".join(current).strip()
    if arg:
        args.append(arg)
    return args


def _extract_strapi_url_calls(
    file_fact: FileFact,
    source: str,
    endpoint_context: dict[str, str] | None,
) -> list[ApiCallFact]:
    if "getStrapiURL" not in source:
        return []
    calls: list[ApiCallFact] = []
    for match in STRAPI_URL_CALL_RE.finditer(source):
        endpoint = _strapi_api_endpoint(match.group("endpoint"), endpoint_context)
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=endpoint,
                method="GET",
                client="strapi-client",
                trigger="runtime",
                context="getStrapiURL",
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.end()),
                ),
            )
        )
    return calls


def _strapi_api_endpoint(endpoint: str, context: dict[str, str] | None = None) -> str:
    normalized = _normalize_dynamic_endpoint(endpoint, context)
    if normalized.startswith(("dynamic:", "http://", "https://")):
        return normalized
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    if normalized == "/api" or normalized.startswith("/api/"):
        return normalized
    return f"/api{normalized}"


def _extract_openapi_ts_request_calls(file_fact: FileFact, source: str) -> list[ApiCallFact]:
    if "__request" not in source or "OpenAPI" not in source:
        return []
    calls: list[ApiCallFact] = []
    for match in OPENAPI_TS_REQUEST_RE.finditer(source):
        body = match.group("body")
        url_match = OPENAPI_TS_URL_RE.search(body)
        if not url_match:
            continue
        method_match = OPENAPI_TS_METHOD_RE.search(body)
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=url_match.group("endpoint"),
                method=method_match.group("method").upper() if method_match else "GET",
                client="openapi-ts-client",
                trigger="generated-client",
                context="openapi-ts-request",
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.end()),
                ),
            )
        )
    return calls


def _extract_generated_api_client_calls(file_fact: FileFact, source: str) -> list[ApiCallFact]:
    imported_names: list[str] = []
    for match in GENERATED_API_IMPORT_RE.finditer(source):
        imported_names.extend(_imported_generated_api_names(match.group("names")))
    if not imported_names:
        return []
    calls: list[ApiCallFact] = []
    for name in _dedupe(imported_names):
        call_match = re.search(rf"\b{re.escape(name)}\s*\(", source)
        if not call_match:
            continue
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=f"generated:{name}",
                method=_method_from_generated_api_name(name),
                client="generated-fetch-client",
                trigger="runtime",
                context="generated-api-client",
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, call_match.start()),
                    line_end=_line_for_offset(source, call_match.end()),
                ),
            )
        )
    return calls


def _extract_trpc_client_calls(file_fact: FileFact, source: str) -> list[ApiCallFact]:
    if "trpc" not in source.lower() and "api." not in source:
        return []
    calls: list[ApiCallFact] = []
    for match in TRPC_CLIENT_CALL_RE.finditer(source):
        hook = match.group("hook")
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=f"/trpc/{match.group('path')}",
                method=_method_from_trpc_hook(hook),
                client="trpc",
                trigger="runtime",
                context="trpc-client",
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.end()),
                ),
            )
        )
    return calls


def _extract_electron_ipc_client_calls(file_fact: FileFact, source: str) -> list[ApiCallFact]:
    if "ipcRenderer" not in source:
        return []
    calls: list[ApiCallFact] = []
    for match in ELECTRON_IPC_CALL_RE.finditer(source):
        if _offset_is_js_inert(source, match.start()):
            continue
        line = _line_for_offset(source, match.start())
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=f"ipc#{match.group('channel')}",
                method="IPC",
                client="electron-ipc",
                trigger="runtime",
                context=f"ipc-renderer:{match.group('method')}",
                evidence=Evidence(file=file_fact.path, kind="frontend-api-call", line_start=line, line_end=line),
            )
        )
    return calls


def _extract_tauri_invoke_calls(root: Path, file_fact: FileFact, source: str) -> list[ApiCallFact]:
    if "invoke" not in source or not _looks_like_tauri_invoke_source(root, file_fact.path, source):
        return []
    calls: list[ApiCallFact] = []
    for match in TAURI_INVOKE_RE.finditer(source):
        if _offset_is_js_inert(source, match.start()):
            continue
        command = match.group("command").strip()
        if _looks_like_template_placeholder(command):
            continue
        endpoint = _tauri_invoke_endpoint(command)
        line = _line_for_offset(source, match.start())
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=endpoint,
                method="TAURI",
                client="tauri-invoke",
                trigger="runtime",
                context=f"tauri-invoke:{match.group('client')}",
                evidence=Evidence(file=file_fact.path, kind="frontend-api-call", line_start=line, line_end=line),
            )
        )
    return calls


def _looks_like_tauri_invoke_source(root: Path, path: str, source: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return (
        "@tauri-apps/api" in source
        or "__TAURI" in source
        or TAURI_INVOKE_IMPORT_RE.search(source) is not None
        or (root / "src-tauri").exists()
        or normalized.startswith("src-tauri/")
        or "/src-tauri/" in f"/{normalized}"
        or ("plugin:" in source and re.search(r"\bimport\s*\{[^}]*\binvoke\b[^}]*\}\s*from\s*['\"]\.\/core['\"]", source) is not None)
    )


def _tauri_invoke_endpoint(command: str) -> str:
    if "${" in command or "\n" in command or "\r" in command:
        return "dynamic:tauri-invoke"
    return f"tauri#{command}"


def _looks_like_template_placeholder(value: str) -> bool:
    return "{{" in value or "}}" in value or "<%" in value or "%>" in value


def _extract_graphql_client_calls(file_fact: FileFact, source: str) -> list[ApiCallFact]:
    if "gql`" not in source and "graphql`" not in source and "gql `" not in source and "graphql `" not in source:
        return []
    calls: list[ApiCallFact] = []
    for match in GRAPHQL_OPERATION_RE.finditer(source):
        body = match.group("body") or match.group("body_alt") or ""
        header = GRAPHQL_OPERATION_HEADER_RE.search(body)
        if not header:
            continue
        operation_name = header.group("name")
        kind = header.group("kind").capitalize()
        operation_body = body[header.start() :]
        root_fields = _graphql_root_field_names(operation_body)
        if not root_fields:
            fallback = operation_name or _first_graphql_field_name(operation_body[header.end() - header.start() :])
            root_fields = [fallback] if fallback else []
        root_fields = [field for field in root_fields if _is_graphql_operation_root_field(field)]
        if not root_fields:
            continue
        for root_field in _dedupe(root_fields):
            endpoint = f"/graphql#{kind}.{root_field}" if root_field else f"/graphql#{operation_name}"
            calls.append(
                ApiCallFact(
                    path=file_fact.path,
                    endpoint=endpoint,
                    method=header.group("kind").upper(),
                    client="graphql",
                    trigger="runtime",
                    context=f"graphql-client:{operation_name}" if operation_name else "graphql-client",
                    evidence=Evidence(
                        file=file_fact.path,
                        kind="frontend-api-call",
                        line_start=_line_for_offset(source, match.start()),
                        line_end=_line_for_offset(source, match.end()),
                    ),
                )
            )
    return calls


def _extract_socketio_client_calls(file_fact: FileFact, source: str) -> list[ApiCallFact]:
    if ".emit(" not in source or "socket" not in source.lower():
        return []
    normalized_path = file_fact.path.replace("\\", "/").lower()
    if normalized_path.startswith(("server/", "backend/", "api/")) and "socket.io-client" not in source:
        return []
    calls: list[ApiCallFact] = []
    for match in SOCKET_EMIT_RE.finditer(source):
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=f"socket.io#{match.group('event')}",
                method="EVENT",
                client="socket.io",
                trigger="runtime",
                context="socketio-event",
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.end()),
                ),
            )
        )
    return calls


def _extract_realtime_client_calls(file_fact: FileFact, source: str) -> list[ApiCallFact]:
    calls: list[ApiCallFact] = []
    for match in EVENTSOURCE_RE.finditer(source):
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=_httpish_endpoint(match.group("endpoint")),
                method="STREAM",
                client="EventSource",
                trigger="runtime",
                context="sse-client",
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.end()),
                ),
            )
        )
    websocket_client_seen = False
    for match in WEBSOCKET_CLIENT_RE.finditer(source):
        websocket_client_seen = True
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=_websocket_endpoint(match.group("endpoint")),
                method="WS",
                client="WebSocket",
                trigger="runtime",
                context="websocket-client",
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.end()),
                ),
            )
        )
    if websocket_client_seen:
        for match in WEBSOCKET_SEND_RE.finditer(source):
            calls.append(
                ApiCallFact(
                    path=file_fact.path,
                    endpoint="websocket#message",
                    method="EVENT",
                    client="WebSocket",
                    trigger="runtime",
                    context="websocket-send",
                    evidence=Evidence(
                        file=file_fact.path,
                        kind="frontend-api-call",
                        line_start=_line_for_offset(source, match.start()),
                        line_end=_line_for_offset(source, match.end()),
                    ),
                )
            )
    return calls


def _first_graphql_field_name(source: str) -> str | None:
    match = re.search(r"\{\s*(?P<name>[A-Za-z_]\w*)\b", source)
    return match.group("name") if match else None


def _graphql_root_field_names(source: str) -> list[str]:
    start = source.find("{")
    if start < 0:
        return []
    fields: list[str] = []
    depth = 0
    index = start
    while index < len(source):
        char = source[index]
        if char == "#":
            newline = source.find("\n", index)
            index = len(source) if newline < 0 else newline + 1
            continue
        if char == "{":
            depth += 1
            index += 1
            continue
        if char == "}":
            depth = max(0, depth - 1)
            index += 1
            continue
        if depth == 1 and char == "(":
            index = _skip_graphql_parentheses(source, index)
            continue
        if depth == 1 and char == "@":
            index = _skip_graphql_directive(source, index)
            continue
        if depth == 1 and source.startswith("...", index):
            index = _skip_graphql_fragment_spread(source, index)
            continue
        if depth != 1 or not (char.isalpha() or char == "_"):
            index += 1
            continue

        name_start = index
        index += 1
        while index < len(source) and (source[index].isalnum() or source[index] == "_"):
            index += 1
        name = source[name_start:index]
        cursor = index
        while cursor < len(source) and source[cursor].isspace():
            cursor += 1
        if cursor < len(source) and source[cursor] == ":":
            cursor += 1
            while cursor < len(source) and source[cursor].isspace():
                cursor += 1
            alias_target = cursor
            while cursor < len(source) and (source[cursor].isalnum() or source[cursor] == "_"):
                cursor += 1
            if cursor > alias_target:
                name = source[alias_target:cursor]
            index = cursor
        if not _graphql_root_field_is_client_only(source, cursor):
            fields.append(name)
    return fields


def _is_graphql_operation_root_field(name: str) -> bool:
    return bool(name) and not name.startswith("__") and name not in {"include", "skip", "fragment"}


def _graphql_root_field_is_client_only(source: str, index: int) -> bool:
    while index < len(source):
        while index < len(source) and source[index].isspace() and source[index] not in "\r\n":
            index += 1
        if index >= len(source) or source[index] in "\r\n{}":
            return False
        if source[index] == "(":
            index = _skip_graphql_parentheses(source, index)
            continue
        if source[index] == "@":
            directive_start = index
            index = _skip_graphql_directive(source, index)
            if re.match(r"@\s*client\b", source[directive_start:index], re.IGNORECASE):
                return True
            continue
        return False
    return False


def _skip_graphql_parentheses(source: str, index: int) -> int:
    depth = 0
    while index < len(source):
        char = source[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    return index


def _skip_graphql_directive(source: str, index: int) -> int:
    index += 1
    while index < len(source) and (source[index].isalnum() or source[index] == "_"):
        index += 1
    while index < len(source) and source[index].isspace():
        index += 1
    if index < len(source) and source[index] == "(":
        return _skip_graphql_parentheses(source, index)
    return index


def _skip_graphql_fragment_spread(source: str, index: int) -> int:
    index += 3
    while index < len(source) and source[index].isspace():
        index += 1
    if source[index : index + 2].lower() == "on" and (index + 2 == len(source) or not source[index + 2].isalnum()):
        index += 2
    while index < len(source) and source[index].isspace():
        index += 1
    while index < len(source) and (source[index].isalnum() or source[index] == "_"):
        index += 1
    return index


def _httpish_endpoint(endpoint: str) -> str:
    value = endpoint.strip()
    if value.startswith(("http://", "https://")):
        parsed = urlparse(value)
        value = parsed.path or "/"
    elif "/api/" in value and not value.startswith("/"):
        value = value[value.find("/api/") :]
    return _normalize_dynamic_endpoint(value)


def _websocket_endpoint(endpoint: str) -> str:
    value = endpoint.strip()
    if value.startswith(("ws://", "wss://", "http://", "https://")):
        parsed = urlparse(value)
        return parsed.path or "websocket#connection"
    if value.startswith("/"):
        return value
    return "websocket#connection"


def _method_from_trpc_hook(hook: str) -> str | None:
    normalized = hook.lower()
    if "mutation" in normalized:
        return "MUTATION"
    if "subscription" in normalized or "subscribe" in normalized:
        return "SUBSCRIPTION"
    if "query" in normalized or normalized == "prefetch":
        return "QUERY"
    return None


def _imported_generated_api_names(source: str) -> list[str]:
    names = []
    for raw in source.split(","):
        name = raw.strip().split(" as ", 1)[0].strip()
        if re.fullmatch(r"[A-Za-z_$][\w$]*", name):
            names.append(name)
    return names


def _method_from_generated_api_name(name: str) -> str | None:
    normalized = name.removeprefix("get")
    for prefix, method in [
        ("Get", "GET"),
        ("Create", "POST"),
        ("Post", "POST"),
        ("Update", "PUT"),
        ("Put", "PUT"),
        ("Delete", "DELETE"),
        ("Patch", "PATCH"),
        ("Follow", "POST"),
        ("Unfollow", "DELETE"),
    ]:
        if normalized.startswith(prefix) or name.startswith(prefix.lower()):
            return method
    return None


def _api_client_endpoint_context(
    source: str,
    root: Path,
    current_path: str,
    seen: set[str] | None = None,
) -> dict[str, str]:
    seen = seen or set()
    parent_match = re.search(r"\bclass\s+[A-Za-z_$][\w$]*\s+extends\s+(?P<parent>[A-Za-z_$][\w$]*)", source)
    parent_name = parent_match.group("parent") if parent_match else None
    if parent_name and parent_name not in {"ApiClient", "CacheEnabledApiClient"}:
        imported_parent = _local_default_import_source(source, root, current_path, parent_name)
        if imported_parent:
            parent_path, parent_source = imported_parent
            if parent_path not in seen:
                return _api_client_endpoint_context(parent_source, root, parent_path, {*seen, current_path})
        return {}
    context = _direct_api_client_endpoint_context(source)
    context.update(_js_string_constants(source))
    return context


def _direct_api_client_endpoint_context(source: str) -> dict[str, str]:
    match = re.search(
        r"\bsuper\(\s*(?P<quote>['\"])(?P<resource>[^'\"]*)(?P=quote)"
        r"(?:\s*,\s*(?P<options>\{[\s\S]{0,500}?\}))?\s*\)",
        source,
    )
    if not match:
        return {}

    options = match.group("options") or ""
    api_version = _first_match(options, r"\bapiVersion\s*:\s*['\"]([^'\"]+)['\"]") or "v1"
    api_version_path = f"/api/{api_version.strip('/')}"
    if re.search(r"\benterprise\s*:\s*true\b", options):
        api_version_path = f"/enterprise{api_version_path}"

    base_url = api_version_path
    if re.search(r"\baccountScoped\s*:\s*true\b", options):
        base_url = f"{base_url}/accounts/:account_id"

    resource = match.group("resource").strip("/")
    url = f"{base_url}/{resource}" if resource else f"{base_url}/"
    return {
        "api_version": api_version_path,
        "base_url": base_url,
        "url": url,
    }


def _js_string_constants(source: str) -> dict[str, str]:
    constants: dict[str, str] = {}
    for match in re.finditer(
        r"\b(?:const|let|var|final)\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*(?P<quote>['\"])(?P<value>https?://[^'\"]+|/[^'\"]*)(?P=quote)",
        source,
    ):
        constants[match.group("name")] = match.group("value")
    for match in re.finditer(
        r"\b(?:const|let|var|final)\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*`(?P<value>https?://[^`]+|/[^`]*)`",
        source,
        re.DOTALL,
    ):
        constants[match.group("name")] = match.group("value")
    return constants


def _local_default_import_source(
    source: str,
    root: Path,
    current_path: str,
    imported_name: str,
) -> tuple[str, str] | None:
    pattern = (
        r"\bimport\s+"
        + re.escape(imported_name)
        + r"\s+from\s+(?P<quote>['\"])(?P<target>\.[^'\"]+)(?P=quote)"
    )
    match = re.search(pattern, source)
    if not match:
        return None
    current_file = root / current_path
    target = (current_file.parent / match.group("target")).resolve()
    candidates = [target]
    if not target.suffix:
        candidates.extend(target.with_suffix(suffix) for suffix in (".js", ".ts", ".jsx", ".tsx"))
        candidates.extend((target / f"index{suffix}") for suffix in (".js", ".ts", ".jsx", ".tsx"))
    for candidate in candidates:
        try:
            relative = candidate.relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
        if candidate.exists() and candidate.is_file():
            return relative, candidate.read_text(encoding="utf-8", errors="ignore")
    return None


def _first_match(source: str, pattern: str) -> str | None:
    match = re.search(pattern, source)
    return match.group(1) if match else None


def _normalize_dynamic_endpoint(endpoint: str, context: dict[str, str] | None = None) -> str:
    normalized = endpoint.strip()
    context = context or {}
    if context:
        base_url = context.get("base_url", "")
        if base_url:
            normalized = re.sub(
                r"\$\{\s*this\.url\.replace\(\s*this\.resource\s*,\s*['\"]{2}\s*\)\s*\}",
                f"{base_url.rstrip('/')}/",
                normalized,
            )
        replacements = {
            "${this.apiVersion}": context.get("api_version", ""),
            "${this.baseUrl()}": base_url,
            "${this.url}": context.get("url", ""),
            "this.apiVersion": context.get("api_version", ""),
            "this.baseUrl()": base_url,
            "this.url": context.get("url", ""),
        }
        for needle, value in replacements.items():
            if value:
                normalized = normalized.replace(needle, value)
    for name, value in context.items():
        if not re.fullmatch(r"[A-Za-z_$][\w$]*", name):
            continue
        normalized = re.sub(r"\$\{\s*" + re.escape(name) + r"\s*\}", value.rstrip("/"), normalized)
    normalized = normalized.replace("\r", "").replace("\n", "")
    normalized = re.sub(r"\s+", "", normalized)
    variable_with_optional_query = re.fullmatch(r"\$\{\s*([A-Za-z_$][\w$]*)\s*\}(?:\?.*)?", normalized)
    if variable_with_optional_query:
        return f"dynamic:{variable_with_optional_query.group(1)}"
    variable_only = re.fullmatch(r"\$\{\s*([A-Za-z_$][\w$]*)\s*\}", normalized)
    if variable_only:
        return f"dynamic:{variable_only.group(1)}"
    normalized = re.sub(r"^\$\{\s*[A-Z][A-Z0-9_]*\s*\}", "", normalized)
    normalized = re.sub(r"\$\{\s*this\.accountIdFromRoute\s*\}", ":account_id", normalized)
    normalized = re.sub(r"\$\{\s*route\.params\.([A-Za-z_$][\w$]*)\s*\}", r":\1", normalized)
    normalized = re.sub(r"\$\{\s*params\.([A-Za-z_$][\w$]*)\s*\}", r":\1", normalized)
    normalized = re.sub(r"\$\{\s*this\.([A-Za-z_$][\w$]*)\s*\}", r":\1", normalized)
    normalized = re.sub(r"\$\{\s*[A-Za-z_$][\w$]*\(\s*([A-Za-z_$][\w$]*)\s*\)\s*\}", r":\1", normalized)
    normalized = re.sub(r"\$\{\s*[A-Za-z_$][\w$]*\?\.\s*([A-Za-z_$][\w$]*)[^}]*\}", r":\1", normalized)
    normalized = re.sub(r"\$\{\s*[A-Za-z_$][\w$]*\.([A-Za-z_$][\w$]*)\s*\}", r":\1", normalized)
    normalized = re.sub(r"\$\{\s*([A-Za-z_$][\w$]*)\s*\}", r":\1", normalized)
    normalized = re.sub(r"\$\{[^}]+\}", ":param", normalized)
    normalized = re.sub(r"\$([A-Za-z_]\w*)", r":\1", normalized)
    if "?" in normalized:
        normalized = normalized.split("?", 1)[0]
    normalized = re.sub(r"(?<!/):[A-Za-z_$][\w$]*$", "", normalized)
    return normalized


def _normalize_client_endpoint(endpoint: str, context: dict[str, str] | None = None) -> str:
    normalized = _normalize_dynamic_endpoint(endpoint, context)
    if normalized.startswith(("dynamic:", "http://", "https://", "websocket#", "socket.io#")):
        return normalized
    if normalized and not normalized.startswith("/") and not normalized.startswith(":"):
        return f"/{normalized}"
    return normalized


def _http_method_from_client_method(method: str) -> str:
    return "DELETE" if method.lower() == "del" else method.upper()


def _is_useful_api_endpoint(endpoint: str) -> bool:
    if not endpoint:
        return False
    if endpoint == "/":
        return False
    if endpoint in {"/:path", "/:url", "/:endpoint", "/:resource"}:
        return False
    if endpoint.startswith(("/packs/", "/packs-dev/")):
        return False
    if endpoint.startswith("/"):
        return True
    if endpoint.startswith(("dynamic:", "tauri#", "websocket#", "socket.io#", "kafka#", "rabbitmq#", "bullmq#", "redis#")):
        return True
    if endpoint.startswith(":"):
        return False
    if re.fullmatch(r"[A-Z_][A-Z0-9_]*", endpoint):
        return False
    return True


def _looks_like_function_declaration_context(source: str, offset: int) -> bool:
    prefix = source[max(0, offset - 32) : offset]
    return bool(re.search(r"\bfunction\s+$", prefix))


def _looks_like_backend_route_registration_context(source: str, offset: int) -> bool:
    prefix = source[max(0, offset - 48) : offset].lower()
    match = re.search(r"\b(?P<receiver>app|router|server|api)\s*\.\s*$", prefix)
    if not match:
        return False
    if match.group("receiver") in {"app", "router", "server"}:
        return True
    header = source[:2000].lower()
    return "from 'express'" in header or 'from "express"' in header or "require('express')" in header or 'require("express")' in header


def build_frontend_surfaces(
    routes: list[FrontendRouteFact],
    components: list[ComponentFact],
    api_calls: list[ApiCallFact],
    frameworks: list[FrameworkFact],
    pages: list[object] | None = None,
    forms: list[object] | None = None,
    styles: list[object] | None = None,
    assets: list[object] | None = None,
    state_usages: list[StateUsageFact] | None = None,
) -> list[FrontendSurfaceFact]:
    pages = pages or []
    forms = forms or []
    styles = styles or []
    assets = assets or []
    state_usages = state_usages or []
    frontend_frameworks = {item.name for item in frameworks if item.category in {"frontend", "mobile"}}
    frontend_frameworks.update(route.framework for route in routes)
    frontend_frameworks.update(component.framework for component in components)
    if pages:
        frontend_frameworks.add("static-site")
    surfaces: list[FrontendSurfaceFact] = []
    for framework in sorted(frontend_frameworks):
        framework_routes = [route for route in routes if route.framework == framework]
        framework_components = [component for component in components if component.framework == framework]
        is_static = framework in {"static-site", "html", "thymeleaf", "freemarker", "handlebars", "mustache", "ejs", "pug", "jsp"}
        surfaces.append(
            FrontendSurfaceFact(
                framework=framework,
                route_count=len(framework_routes),
                component_count=len(framework_components),
                api_call_count=len(api_calls),
                page_count=len(pages) if is_static else 0,
                form_count=len(forms) if is_static else 0,
                style_count=len(styles) if is_static or framework in {"sass", "tailwind", "bootstrap"} else 0,
                asset_count=len(assets) if is_static else 0,
                state_count=len(state_usages) if framework not in {"static-site", "html"} else 0,
                evidence=[
                    *[route.evidence for route in framework_routes[:5]],
                    *[component.evidence for component in framework_components[:5]],
                    *[getattr(page, "evidence") for page in pages[:5] if is_static],
                ],
            )
        )
    return surfaces


def _is_frontend_candidate(path: str, frontend_frameworks: set[str], framework_names: set[str] | None = None) -> bool:
    framework_names = framework_names or set()
    if (
        _next_route_for_path(path)
        or _sveltekit_route_for_path(path)
        or _astro_route_for_path(path)
        or _nuxt_route_for_path(path)
        or _vue_file_route_for_path(path)
        or path.endswith((".vue", ".svelte", ".astro", ".cshtml", ".razor"))
        or path.endswith((".swift", ".xaml", ".axaml"))
    ):
        return True
    lower = path.lower()
    if "flutter" in frontend_frameworks and lower.endswith(".dart"):
        return True
    if {"android", "jetpack-compose"} & frontend_frameworks and lower.endswith(".kt"):
        return True
    if "angular" in frontend_frameworks and lower.endswith((".component.ts", ".routes.ts", ".routing.ts", ".module.ts")):
        return True
    if "ember" in frontend_frameworks and (
        lower == "app/router.js"
        or lower.endswith("/app/router.js")
        or lower == "addon/routes.js"
        or lower.endswith("/addon/routes.js")
        or lower.startswith("app/components/")
        or "/app/components/" in f"/{lower}"
        or "/addon/components/" in f"/{lower}"
        or lower.endswith((".gjs", ".gts", ".hbs"))
    ):
        return True
    if "blazor" in frontend_frameworks and lower.endswith((".cshtml", ".razor")):
        return True
    if "blazor" in frontend_frameworks and lower.endswith(".cs") and re.search(r"(?:^|/)blazor[^/]*/", lower):
        return True
    if {"swiftui", "ios"} & frontend_frameworks and lower.endswith(".swift"):
        return True
    if {"maui", "wpf", "avalonia"} & frontend_frameworks and lower.endswith((".xaml", ".axaml")):
        return True
    if "streamlit" in frontend_frameworks and lower.endswith(".py"):
        return True
    if "gradio" in frontend_frameworks and lower.endswith(".py"):
        return True
    if "dash" in frontend_frameworks and lower.endswith(".py"):
        return True
    if "panel" in frontend_frameworks and lower.endswith(".py"):
        return True
    if "shiny" in frontend_frameworks and lower.endswith(".py"):
        return True
    if {"expo", "react-native", "react-navigation"} & frontend_frameworks and lower.endswith((".tsx", ".jsx", ".ts", ".js")):
        return True
    if "rails" in framework_names and lower.endswith((".js", ".mjs", ".ts")) and (
        lower.startswith("app/javascript/")
        or lower.startswith("app/assets/javascripts/")
        or "/app/javascript/" in f"/{lower}"
        or "/app/assets/javascripts/" in f"/{lower}"
    ):
        return True
    if frontend_frameworks and path.endswith((".tsx", ".jsx")):
        return True
    if frontend_frameworks and path.endswith((".ts", ".js", ".mjs")):
        return True
    if frontend_frameworks and ("/components/" in f"/{path}" or path.lower().endswith(("app.tsx", "app.jsx"))):
        return True
    return False


def _props_by_interface(source: str) -> dict[str, list[str]]:
    props: dict[str, list[str]] = {}
    for match in PROPS_INTERFACE_RE.finditer(source):
        props[match.group("name")] = PROP_NAME_RE.findall(match.group("body"))
    return props


def _vue_props(source: str) -> list[str]:
    match = re.search(r"defineProps\s*<\s*{(?P<body>[^}]+)}\s*>", source, re.DOTALL)
    return PROP_NAME_RE.findall(match.group("body")) if match else []


def _fetch_method(args: str) -> str:
    return _fetch_method_from_call(args, args)


def _fetch_method_from_call(args: str, call_text: str) -> str:
    match = re.search(r"(?:^|[,{]\s*)(?:method|type)\s*:\s*['\"`](?P<method>[A-Z]+)['\"`]", args, re.IGNORECASE)
    if not match and call_text != args:
        match = re.search(
            r"(?:^|[,{]\s*)(?:method|type)\s*:\s*['\"`](?P<method>[A-Z]+)['\"`]",
            call_text,
            re.IGNORECASE,
        )
    return match.group("method").upper() if match else "GET"


def _ajax_literal_endpoint_is_concat_fragment(args: str) -> bool:
    return args.lstrip().startswith("+")


def _ajax_expression_arg_is_path_like(expression: str) -> bool:
    value = expression.strip()
    if not value or value.startswith("{") or re.search(r"\s\?\s", value):
        return False
    if re.match(r"^[A-Za-z_$][\w$]*(?:\.|$|\()", value):
        return False
    literal = _js_string_literal_value(value)
    if literal is not None:
        return literal.startswith(("/", "http://", "https://"))
    if "+" not in value:
        return False
    for part in _split_js_concat_parts(value):
        literal = _js_string_literal_value(part)
        if literal and literal.startswith(("/", "http://", "https://")):
            return True
    return False


def _js_call_text(source: str, start: int, max_chars: int = 2000) -> tuple[str, int]:
    open_paren = source.find("(", start, min(len(source), start + 80))
    if open_paren == -1:
        end = min(len(source), start + max_chars)
        return source[start:end], end

    depth = 0
    quote: str | None = None
    escaped = False
    end_limit = min(len(source), open_paren + max_chars)
    index = open_paren
    while index < end_limit:
        char = source[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in {"'", '"', "`"}:
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return source[start : index + 1], index + 1
        index += 1

    return source[start:end_limit], end_limit


def _frontend_framework_for_path(path: str, frameworks: list[FrameworkFact]) -> str:
    names = {item.name for item in frameworks if item.category in {"frontend", "mobile"}}
    if "next" in names and _next_route_for_path(path):
        return "next"
    if "nuxt" in names and (path.endswith(".vue") or _nuxt_route_for_path(path)):
        return "nuxt"
    if "angular" in names and path.lower().endswith((".component.ts", ".component.js")):
        return "angular"
    if "ember" in names and path.lower().startswith("app/"):
        return "ember"
    if path.lower().endswith((".cshtml", ".razor")):
        return "blazor" if _is_legacy_blazor_markup_path(path, names) else "razor"
    if "flutter" in names and path.lower().endswith(".dart"):
        return "flutter"
    if "swiftui" in names and path.lower().endswith(".swift"):
        return "swiftui"
    if "maui" in names and path.lower().endswith(".xaml"):
        return "maui"
    if "avalonia" in names and path.lower().endswith((".xaml", ".axaml")):
        return "avalonia"
    if "wpf" in names and path.lower().endswith(".xaml"):
        return "wpf"
    if "expo" in names and _expo_route_for_path(path):
        return "expo"
    if "react-native" in names and path.lower().endswith((".tsx", ".jsx", ".ts", ".js")):
        return "react-native"
    if "redwood" in names and ("/web/src/" in f"/{path.lower()}" or path.lower().endswith(("routes.tsx", "routes.jsx", "routes.ts", "routes.js"))):
        return "redwood"
    if "qwik" in names and path.lower().endswith((".tsx", ".jsx", ".ts", ".js")):
        return "qwik"
    if "solid" in names and path.lower().endswith((".tsx", ".jsx", ".ts", ".js")):
        return "solid"
    if "jetpack-compose" in names and path.lower().endswith(".kt"):
        return "jetpack-compose"
    if "android" in names and path.lower().endswith(".kt"):
        return "android"
    if "sveltekit" in names and path.endswith(".svelte"):
        return "sveltekit"
    if "svelte" in names and path.endswith(".svelte"):
        return "svelte"
    if "vue" in names and path.endswith(".vue"):
        return "vue"
    if "react" in names:
        return "react"
    if "vite" in names:
        return "vite"
    return "react"


def _is_blazor_route_markup(path: str, source: str, frontend_frameworks: set[str]) -> bool:
    normalized = path.replace("\\", "/").lower()
    if normalized.endswith(".razor"):
        return True
    if not normalized.endswith(".cshtml") or "blazor" not in frontend_frameworks:
        return False
    return _is_legacy_blazor_markup_path(normalized, frontend_frameworks) or _looks_like_legacy_blazor_source(source)


def _razor_markup_framework(path: str, source: str, framework_names: set[str]) -> str | None:
    normalized = path.replace("\\", "/").lower()
    if normalized.endswith(".razor"):
        return "blazor"
    if normalized.endswith(".cshtml"):
        if _is_legacy_blazor_markup_path(normalized, framework_names) or _looks_like_legacy_blazor_source(source):
            return "blazor"
        return "razor"
    return None


def _is_legacy_blazor_markup_path(path: str, framework_names: set[str]) -> bool:
    if "blazor" not in framework_names:
        return False
    normalized = path.replace("\\", "/").lower()
    return re.search(r"(?:^|/)blazor[^/]*/", normalized) is not None


def _looks_like_legacy_blazor_source(source: str) -> bool:
    return "Microsoft.AspNetCore.Blazor" in source or ("@functions" in source and "ComponentBase" in source)


def _page_route(route: str) -> str:
    grouped = _strip_next_route_groups(route)
    cleaned = "" if grouped == "index" else grouped.replace("/index", "")
    cleaned = cleaned.replace("[", ":").replace("]", "")
    return "/" + cleaned.strip("/") if cleaned.strip("/") else "/"


def _next_route_for_path(path: str) -> tuple[str, str] | None:
    for marker in ("/app/", "app/"):
        if _inside_non_route_source_tree(path, marker):
            continue
        route_part = _path_after_marker(path, marker)
        if route_part is None:
            continue
        if "/api/" in f"/{route_part}/":
            return None
        if re.fullmatch(r"page\.(?:tsx|ts|jsx|js)", route_part):
            return "/", "next-app-route"
        match = re.match(r"(?P<route>.*)/page\.(?:tsx|ts|jsx|js)$", route_part)
        if match:
            return _page_route(match.group("route")), "next-app-route"

    for marker in ("/pages/", "pages/"):
        if _inside_non_route_source_tree(path, marker):
            continue
        route_part = _path_after_marker(path, marker)
        if route_part is None:
            continue
        if route_part.startswith("api/") or "/api/" in f"/{route_part}":
            return None
        if not route_part.endswith((".tsx", ".ts", ".jsx", ".js")):
            continue
        if Path(route_part).stem.startswith("_"):
            return None
        return _page_route(route_part.rsplit(".", 1)[0]), "next-pages-route"
    return None


def _react_router_file_route_for_path(path: str) -> str | None:
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


def _should_label_file_route_as_remix(source: str, frontend_frameworks: set[str]) -> bool:
    if "remix" not in frontend_frameworks:
        return False
    if "react-router" not in frontend_frameworks:
        return True
    return _looks_like_remix_route_source(source)


def _looks_like_remix_route_source(source: str) -> bool:
    return (
        "@remix-run/node" in source
        or "@remix-run/react" in source
        or "@remix-run/serve" in source
        or "ActionFunctionArgs" in source
        or "LoaderFunctionArgs" in source
        or "MetaFunction" in source
        or "LinksFunction" in source
        or re.search(r"\b(?:json|redirect)\s*\(", source) is not None and "@remix-run/" in source
    )


def _extract_phoenix_live_frontend_routes(file_fact: FileFact, source: str) -> list[FrontendRouteFact]:
    routes: list[FrontendRouteFact] = []
    scope_stack: list[str | None] = []
    for line_number, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if stripped == "end":
            if scope_stack:
                scope_stack.pop()
            continue

        scope_match = re.match(r"^\s*scope\s*\(?\s*['\"](?P<path>/[^'\"]*)['\"]", line, re.IGNORECASE)
        if scope_match and re.search(r"\bdo\s*(?:#.*)?$", line):
            scope_stack.append(scope_match.group("path"))
            continue

        live_match = re.match(
            r"^\s*live\s*\(?\s*['\"](?P<path>/[^'\"]*)['\"]\s*,\s*(?P<liveview>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)"
            r"(?:\s*,\s*:(?P<action>[A-Za-z_]\w*))?",
            line,
            re.IGNORECASE,
        )
        if live_match:
            routes.append(
                _route(
                    file_fact,
                    _join_frontend_routes([_phoenix_current_scope(scope_stack), live_match.group("path")]),
                    "phoenix-liveview",
                    "phoenix-live-route",
                    line_number,
                )
            )
            continue

        dashboard_match = re.match(r"^\s*live_dashboard\s*\(?\s*['\"](?P<path>/[^'\"]*)['\"]", line, re.IGNORECASE)
        if dashboard_match:
            routes.append(
                _route(
                    file_fact,
                    _join_frontend_routes([_phoenix_current_scope(scope_stack), dashboard_match.group("path")]),
                    "phoenix-liveview",
                    "phoenix-live-dashboard-route",
                    line_number,
                )
            )
            continue

        if re.search(r"\bdo\s*(?:#.*)?$", line):
            scope_stack.append(None)
    return routes


def _phoenix_current_scope(scope_stack: list[str | None]) -> str:
    return _join_frontend_routes([scope for scope in scope_stack if scope])


def _expo_route_for_path(path: str) -> str | None:
    normalized = path.replace("\\", "/")
    if not normalized.endswith((".tsx", ".ts", ".jsx", ".js")):
        return None
    route_part = _path_after_marker(normalized, "/app/")
    if route_part is None and normalized.startswith("app/"):
        route_part = normalized.removeprefix("app/")
    if route_part is None:
        return None
    name = Path(route_part).name
    if name.startswith("_") or name.startswith("+") or name in {"index.d.ts"}:
        return None
    stem = route_part.rsplit(".", 1)[0]
    if stem.endswith("/_layout") or stem == "_layout":
        return None
    return _page_route(_clean_vue_route_part(stem))


def _sveltekit_route_for_path(path: str) -> str | None:
    normalized = path.replace("\\", "/")
    page_suffixes = (
        "/+page.svelte",
        "/+page.js",
        "/+page.ts",
        "/+page.server.js",
        "/+page.server.ts",
        "+page.svelte",
        "+page.js",
        "+page.ts",
        "+page.server.js",
        "+page.server.ts",
    )
    if not normalized.endswith(page_suffixes):
        return None
    marker = "/routes/"
    route_part = None
    if normalized.startswith("routes/"):
        route_part = normalized.removeprefix("routes/")
    elif marker in normalized:
        route_part = normalized.split(marker, 1)[1]
    if route_part is None:
        return None
    route = route_part
    for suffix in page_suffixes:
        route = route.removesuffix(suffix)
    return _page_route(route)


def _astro_route_for_path(path: str) -> str | None:
    normalized = path.replace("\\", "/")
    if not normalized.endswith(".astro"):
        return None
    route_part = _path_after_marker(normalized, "/pages/")
    if route_part is None and normalized.startswith("pages/"):
        route_part = normalized.removeprefix("pages/")
    if route_part is None or _astro_non_route_page(route_part):
        return None
    return _page_route(_clean_astro_route_part(route_part.rsplit(".", 1)[0]))


def _fresh_route_for_path(path: str, source: str) -> str | None:
    override = re.search(r"\brouteOverride\s*:\s*['\"](?P<route>[^'\"]+)['\"]", source)
    if override:
        return _normalize_fresh_route(override.group("route"))
    normalized = path.replace("\\", "/")
    if not normalized.endswith((".ts", ".tsx", ".js", ".jsx")):
        return None
    route_part = _path_after_marker(normalized, "/routes/")
    if route_part is None and normalized.startswith("routes/"):
        route_part = normalized.removeprefix("routes/")
    if route_part is None or _fresh_non_route_file(route_part):
        return None
    return _page_route(_clean_fresh_route_part(route_part.rsplit(".", 1)[0]))


def _qwik_route_for_path(path: str) -> str | None:
    normalized = path.replace("\\", "/")
    if not normalized.endswith((".tsx", ".ts", ".jsx", ".js", ".mdx", ".md")):
        return None
    route_part = _path_after_marker(normalized, "/src/routes/")
    if route_part is None and normalized.startswith("src/routes/"):
        route_part = normalized.removeprefix("src/routes/")
    if route_part is None or _qwik_non_route_file(route_part):
        return None
    return _page_route(_clean_qwik_route_part(route_part.rsplit(".", 1)[0]))


def _solid_start_route_for_path(path: str) -> str | None:
    normalized = path.replace("\\", "/")
    if not normalized.endswith((".tsx", ".ts", ".jsx", ".js", ".mdx", ".md")):
        return None
    route_part = _path_after_marker(normalized, "/src/routes/")
    if route_part is None and normalized.startswith("src/routes/"):
        route_part = normalized.removeprefix("src/routes/")
    if route_part is None or _solid_non_route_file(route_part):
        return None
    return _page_route(_clean_solid_route_part(route_part.rsplit(".", 1)[0]))


def _looks_like_solid_route_source(path: str, source: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return (
        "solid-js" in source
        or "@solidjs/router" in source
        or "@solidjs/start" in source
        or "FileRoutes" in source
        or re.search(r"\b(createSignal|createMemo|createResource|createEffect)\s*\(", source) is not None
        or (
            (normalized.startswith("src/routes/") or "/src/routes/" in f"/{normalized}")
            and "/server/src/routes/" not in f"/{normalized}"
        )
    )


def _solid_non_route_file(route_part: str) -> bool:
    stem = route_part.rsplit(".", 1)[0]
    name = Path(stem).name
    lower = name.lower()
    return lower in {"layout", "app", "root"} or any(part.startswith("_") for part in stem.split("/")) or stem.endswith(("_test", ".test", ".spec"))


def _clean_solid_route_part(route: str) -> str:
    parts: list[str] = []
    for raw_part in route.split("/"):
        part = raw_part
        part = re.sub(r"\([^)]*\)", "", part)
        if part in {"index", ""}:
            parts.append(part)
        elif part.startswith("[[") and part.endswith("]]"):
            parts.append(f"{{{part[2:-2]}?}}")
        elif part.startswith("[...") and part.endswith("]"):
            parts.append(f"{{{part[4:-1]}*}}")
        elif part.startswith("[") and part.endswith("]"):
            parts.append(f"{{{part[1:-1]}}}")
        else:
            part = re.sub(r"\[\[([^\]]+)\]\]", r"{\1?}", part)
            part = re.sub(r"\[\.\.\.([^\]]+)\]", r"{\1*}", part)
            part = re.sub(r"\[([^\]]+)\]", r"{\1}", part)
            if part:
                parts.append(part)
    return "/".join(parts)


def _qwik_non_route_file(route_part: str) -> bool:
    stem = route_part.rsplit(".", 1)[0]
    name = Path(stem).name
    lower = name.lower().rstrip("!")
    return (
        lower in {"layout", "service-worker", "entry", "root"}
        or any(part.startswith("_") for part in stem.split("/"))
        or stem.endswith(("_test", ".test", ".spec"))
    )


def _clean_qwik_route_part(route: str) -> str:
    parts: list[str] = []
    for raw_part in route.split("/"):
        part = raw_part.rstrip("!")
        if "@" in part:
            part = part.split("@", 1)[0] or "index"
        if part in {"index", ""}:
            parts.append(part)
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


def _fresh_non_route_file(route_part: str) -> bool:
    stem = route_part.rsplit(".", 1)[0]
    return any(part.startswith("_") for part in stem.split("/")) or stem.endswith(("_test", ".test"))


def _clean_fresh_route_part(route: str) -> str:
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


def _normalize_fresh_route(route: str) -> str:
    normalized = _normalize_frontend_route(route)
    normalized = re.sub(r":([A-Za-z_$][\w$]*)\*", r"{\1*}", normalized)
    normalized = re.sub(r":([A-Za-z_$][\w$]*)", r"{\1}", normalized)
    return normalized


def _astro_non_route_page(route_part: str) -> bool:
    return any(part.startswith("_") for part in route_part.split("/"))


def _clean_astro_route_part(route: str) -> str:
    parts: list[str] = []
    for part in route.split("/"):
        if part in {"index", ""}:
            parts.append(part)
        elif part.startswith("[...") and part.endswith("]"):
            parts.append(f":{part[4:-1]}*")
        elif part.startswith("[") and part.endswith("]"):
            parts.append(f":{part[1:-1]}")
        else:
            parts.append(part)
    return "/".join(parts)


def _nuxt_route_for_path(path: str) -> str | None:
    normalized = path.replace("\\", "/")
    if not normalized.endswith(".vue"):
        return None
    route_part = _path_after_marker(normalized, "/pages/")
    if route_part is None and normalized.startswith("pages/"):
        route_part = normalized.removeprefix("pages/")
    if route_part is None:
        return None
    return _page_route(_clean_vue_route_part(route_part.rsplit(".", 1)[0]))


def _vue_file_route_for_path(path: str) -> str | None:
    normalized = path.replace("\\", "/")
    if not normalized.endswith(".vue"):
        return None
    route_part = _path_after_marker(normalized, "/routes/")
    if route_part is None and normalized.startswith("routes/"):
        route_part = normalized.removeprefix("routes/")
    if route_part is None:
        return None
    return _page_route(_clean_vue_route_part(route_part.rsplit(".", 1)[0]))


def _clean_vue_route_part(route: str) -> str:
    parts = []
    for part in route.split("/"):
        if part in {"index", ""}:
            parts.append(part)
            continue
        if part.startswith("[...") and part.endswith("]"):
            parts.append(f":{part[4:-1]}*")
        elif part.startswith("[") and part.endswith("]"):
            parts.append(f":{part[1:-1]}")
        else:
            parts.append(part)
    return "/".join(parts)


def _path_after_marker(path: str, marker: str) -> str | None:
    if path.startswith(marker):
        return path.removeprefix(marker)
    if not marker.startswith("/"):
        return None
    index = path.find(marker)
    if index == -1:
        return None
    return path[index + len(marker):]


def _inside_non_route_source_tree(path: str, marker: str) -> bool:
    prefix = _path_before_marker(path, marker)
    if prefix is None:
        return False
    normalized = prefix.strip("/")
    return "/src/" in f"/{normalized}/" and normalized != "src" and not normalized.endswith("/src")


def _path_before_marker(path: str, marker: str) -> str | None:
    if path.startswith(marker):
        return ""
    if not marker.startswith("/"):
        return None
    index = path.find(marker)
    if index == -1:
        return None
    return path[:index]


def _strip_next_route_groups(route: str) -> str:
    parts = [part for part in route.split("/") if part and not (part.startswith("(") and part.endswith(")"))]
    return "/".join(parts)


def _svelte_component_name(path: str) -> str:
    stem = Path(path).stem
    if not stem.startswith("+"):
        return _pascal_case(stem) or "SvelteComponent"
    parent = Path(path).parent.name
    suffix = {
        "+page": "Page",
        "+layout": "Layout",
        "+error": "Error",
    }.get(stem, "Component")
    return f"{_pascal_case(parent) or 'Route'}{suffix}"


def _astro_component_name(path: str) -> str:
    normalized = path.replace("\\", "/")
    stem = Path(normalized).stem
    if stem == "index":
        parent = Path(normalized).parent.name
        stem = parent if parent else stem
    stem = stem.replace("[...", "").replace("[", "").replace("]", "").replace("-", "_")
    return _pascal_case(stem) or "AstroComponent"


def _astro_props(source: str) -> list[str]:
    props: list[str] = []
    for match in re.finditer(r"(?:const|let)\s*\{(?P<body>[^}]+)\}\s*=\s*Astro\.props", source, re.DOTALL):
        for raw in match.group("body").split(","):
            name = raw.strip().split("=", 1)[0].split(":", 1)[0].strip()
            if name and re.fullmatch(r"[A-Za-z_$][\w$]*", name):
                props.append(name)
    for match in re.finditer(r"\bAstro\.props\.([A-Za-z_$][\w$]*)", source):
        props.append(match.group(1))
    return _dedupe(props)


def _blazor_component_name(path: str) -> str:
    return _pascal_case(Path(path).stem) or "BlazorComponent"


def _extract_angular_components(file_fact: FileFact, source: str) -> list[ComponentFact]:
    components: list[ComponentFact] = []
    for match in ANGULAR_COMPONENT_RE.finditer(source):
        line = _line_for_offset(source, match.start())
        selector = ANGULAR_SELECTOR_RE.search(match.group("meta"))
        props = _dedupe(ANGULAR_INPUT_RE.findall(source[match.end() : match.end() + 1600]))
        if selector:
            props = _dedupe([f"selector:{selector.group('selector')}", *props])
        components.append(
            ComponentFact(
                name=match.group("name"),
                path=file_fact.path,
                framework="angular",
                props=props,
                hooks=[],
                evidence=Evidence(file=file_fact.path, kind="frontend-component", line_start=line, line_end=line),
            )
        )
    return components


def _extract_qwik_components(file_fact: FileFact, source: str) -> list[ComponentFact]:
    components: list[ComponentFact] = []
    hooks = sorted(set(HOOK_RE.findall(source)))
    for match in QWIK_COMPONENT_RE.finditer(source):
        components.append(
            ComponentFact(
                name=match.group("name"),
                path=file_fact.path,
                framework="qwik",
                props=[],
                hooks=hooks,
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-component",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.end()),
                ),
            )
        )
    match = QWIK_DEFAULT_COMPONENT_RE.search(source)
    if match:
        components.append(
            ComponentFact(
                name=_qwik_default_component_name(file_fact.path),
                path=file_fact.path,
                framework="qwik",
                props=[],
                hooks=hooks,
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-component",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.end()),
                ),
            )
        )
    return components


def _qwik_default_component_name(path: str) -> str:
    normalized = path.replace("\\", "/")
    stem = Path(normalized).stem.rstrip("!")
    if stem == "index":
        parent = Path(normalized).parent.name
        stem = parent if parent and parent not in {"routes", "src"} else "index"
    return "".join(part.capitalize() for part in re.split(r"[^A-Za-z0-9]+", stem) if part) or "QwikComponent"


def _extract_ember_components(file_fact: FileFact, source: str) -> list[ComponentFact]:
    class_match = re.search(r"class\s+(?P<name>[A-Za-z_]\w*Component)\b", source)
    name = class_match.group("name") if class_match else f"{_pascal_case(Path(file_fact.path).stem)}Component"
    line = _line_for_offset(source, class_match.start()) if class_match else 1
    return [
        ComponentFact(
            name=name,
            path=file_fact.path,
            framework="ember",
            props=[],
            hooks=[],
            evidence=Evidence(file=file_fact.path, kind="frontend-component", line_start=line, line_end=line),
        )
    ]


def _extract_flutter_components(file_fact: FileFact, source: str) -> list[ComponentFact]:
    components: list[ComponentFact] = []
    for match in DART_WIDGET_RE.finditer(source):
        name = match.group("name")
        if name.startswith("_"):
            continue
        line = _line_for_offset(source, match.start())
        components.append(
            ComponentFact(
                name=name,
                path=file_fact.path,
                framework="flutter",
                props=[],
                hooks=[match.group("base")],
                evidence=Evidence(file=file_fact.path, kind="frontend-component", line_start=line, line_end=line),
            )
        )
    return components


def _extract_swiftui_components(file_fact: FileFact, source: str) -> list[ComponentFact]:
    components: list[ComponentFact] = []
    for match in SWIFTUI_VIEW_RE.finditer(source):
        name = match.group("name")
        if name.startswith("_") or "Preview" in name:
            continue
        line = _line_for_offset(source, match.start())
        wrappers = _dedupe([f"@{kind}" for kind, _name in SWIFTUI_STATE_RE.findall(source)])
        components.append(
            ComponentFact(
                name=name,
                path=file_fact.path,
                framework="swiftui",
                props=[],
                hooks=wrappers or ["View"],
                evidence=Evidence(file=file_fact.path, kind="frontend-component", line_start=line, line_end=line),
            )
        )
    return components


def _extract_xaml_component(file_fact: FileFact, source: str, frameworks: list[FrameworkFact]) -> ComponentFact | None:
    root_match = XAML_ROOT_RE.search(source)
    if not root_match:
        return None
    class_match = XAML_CLASS_RE.search(source)
    name = class_match.group("class").split(".")[-1] if class_match else Path(file_fact.path).stem
    root_tag = root_match.group("tag").split(":")[-1]
    props = [f"root:{root_tag}"]
    props.extend(f"x-name:{name}" for name in XAML_NAME_RE.findall(source)[:20])
    props.extend(f"event:{event}->{handler}" for event, handler in XAML_EVENT_RE.findall(source)[:20])
    line = _line_for_offset(source, class_match.start() if class_match else root_match.start())
    return ComponentFact(
        name=name,
        path=file_fact.path,
        framework=_xaml_framework_for_source(file_fact.path, source, frameworks),
        props=_dedupe(props),
        hooks=[],
        evidence=Evidence(file=file_fact.path, kind="frontend-component", line_start=line, line_end=line),
    )


def _xaml_framework_for_source(path: str, source: str, frameworks: list[FrameworkFact]) -> str:
    lower_path = path.lower()
    lower_source = source.lower()
    framework_names = {item.name for item in frameworks}
    if lower_path.endswith(".axaml") or "avaloniaui" in lower_source or "github.com/avaloniaui" in lower_source:
        return "avalonia"
    if "dotnet/2021/maui" in lower_source or "contentpage" in lower_source or "mauiwinuiapplication" in lower_source or "maui" in lower_path:
        return "maui"
    if "winfx/2006/xaml/presentation" in lower_source or "wpf" in lower_path:
        return "wpf"
    if "maui" in framework_names and "wpf" not in framework_names and "avalonia" not in framework_names:
        return "maui"
    if "wpf" in framework_names and "maui" not in framework_names and "avalonia" not in framework_names:
        return "wpf"
    if "avalonia" in framework_names and "maui" not in framework_names and "wpf" not in framework_names:
        return "avalonia"
    return "xaml"


def _extract_compose_components(file_fact: FileFact, source: str) -> list[ComponentFact]:
    components: list[ComponentFact] = []
    for match in KOTLIN_COMPOSABLE_RE.finditer(source):
        name = match.group("name")
        if name.startswith("_") or _is_compose_preview_function(source, match.start(), name):
            continue
        line = _line_for_offset(source, match.start())
        components.append(
            ComponentFact(
                name=name,
                path=file_fact.path,
                framework="jetpack-compose",
                props=_kotlin_arg_names(match.group("args")),
                hooks=["@Composable"],
                evidence=Evidence(file=file_fact.path, kind="frontend-component", line_start=line, line_end=line),
            )
        )
    return components


def _is_compose_preview_function(source: str, offset: int, name: str) -> bool:
    if "Preview" in name:
        return True
    prefix_lines = source[:offset].splitlines()
    annotation_lines = []
    for line in reversed(prefix_lines[-8:]):
        stripped = line.strip()
        if not stripped:
            continue
        if not stripped.startswith("@"):
            break
        annotation_lines.append(stripped)
    return any("Preview" in line for line in annotation_lines)


def _kotlin_arg_names(args: str) -> list[str]:
    names: list[str] = []
    for part in args.split(","):
        match = re.match(r"\s*(?:@\w+\s+)*(?P<name>[A-Za-z_]\w*)\s*:", part.strip())
        if match:
            names.append(match.group("name"))
    return names


def _is_ember_component_path(path: str) -> bool:
    lower = path.lower()
    return (
        (lower.startswith("app/components/") or "/app/components/" in f"/{lower}" or "/addon/components/" in f"/{lower}")
        and lower.endswith((".js", ".ts", ".gjs", ".gts", ".hbs"))
    )


def _extract_ember_routes(file_fact: FileFact, source: str) -> list[FrontendRouteFact]:
    routes: list[FrontendRouteFact] = []
    stack: list[str] = []
    for line_number, line in enumerate(source.splitlines(), start=1):
        for match in EMBER_MOUNT_RE.finditer(line):
            route_path = _ember_route_path(match.group("name"), match.group("args"))
            full_route = _join_frontend_routes([*stack, route_path])
            routes.append(_route(file_fact, full_route, "ember", "ember-mount-route", line_number))
        for match in EMBER_ROUTE_RE.finditer(line):
            route_path = _ember_route_path(match.group("name"), match.group("args"))
            full_route = _join_frontend_routes([*stack, route_path])
            routes.append(_route(file_fact, full_route, "ember", "ember-route", line_number))
            if "function" in match.group("args") or line[match.end() :].lstrip().startswith(", function"):
                stack.append(route_path)
        closing_count = line.count("});")
        for _ in range(closing_count):
            if stack:
                stack.pop()
    return routes


def _apply_ember_engine_mount_prefixes(
    root: Path,
    files: list[FileFact],
    routes: list[FrontendRouteFact],
) -> list[FrontendRouteFact]:
    prefixes = _ember_engine_mount_prefixes(root, files)
    if not prefixes:
        return routes

    result: list[FrontendRouteFact] = []
    for route in routes:
        prefix = prefixes.get(route.path.replace("\\", "/"))
        if route.framework != "ember" or prefix is None:
            result.append(route)
            continue
        result.append(
            FrontendRouteFact(
                route=_join_frontend_routes([prefix, route.route]),
                path=route.path,
                framework=route.framework,
                kind="ember-engine-route",
                evidence=Evidence(
                    file=route.evidence.file,
                    kind=route.evidence.kind,
                    line_start=route.evidence.line_start,
                    line_end=route.evidence.line_end,
                    note=f"engine mount:{prefix}",
                ),
            )
        )
    return result


def _ember_engine_mount_prefixes(root: Path, files: list[FileFact]) -> dict[str, str]:
    prefixes: dict[str, str] = {}
    for file_fact in files:
        normalized = file_fact.path.replace("\\", "/")
        lower = normalized.lower()
        if not (lower == "app/router.js" or lower.endswith("/app/router.js")):
            continue
        source = _read(root, file_fact)
        for match in EMBER_MOUNT_RE.finditer(source):
            engine_name = match.group("name")
            prefix = _ember_route_path(engine_name, match.group("args"))
            router_path = _ember_engine_routes_file(normalized, engine_name)
            if router_path:
                prefixes[router_path] = prefix
    return prefixes


def _ember_engine_routes_file(app_router_path: str, engine_name: str) -> str | None:
    marker = "/app/router.js"
    if app_router_path == "app/router.js":
        base = ""
    elif app_router_path.endswith(marker):
        base = app_router_path[: -len(marker)]
    else:
        return None
    return f"{base}/lib/{engine_name}/addon/routes.js".lstrip("/")


def _ember_route_path(name: str, args: str) -> str:
    path_match = EMBER_PATH_RE.search(args)
    value = path_match.group("path") if path_match else name
    return _normalize_frontend_route(value)


def _join_frontend_routes(parts: list[str]) -> str:
    joined = "/".join(part.strip("/") for part in parts if part and part != "/")
    return f"/{joined}" if joined else "/"


def _pascal_case(value: str) -> str:
    words = re.split(r"[^A-Za-z0-9]+", value)
    return "".join(word[:1].upper() + word[1:] for word in words if word)


def _looks_like_react_component_source(source: str) -> bool:
    return (
        "React.createElement" in source
        or "extends React.Component" in source
        or bool(re.search(r"\breturn\s*\(?\s*<", source))
        or bool(re.search(r"=>\s*\(?\s*<", source))
    )


def _should_extract_react_router_routes(source: str, frontend_frameworks: set[str]) -> bool:
    return bool(
        {"react-router", "react"} & frontend_frameworks
        and (
            re.search(r"<Route(?:\s|/|>)", source) is not None
            or "createBrowserRouter" in source
            or "createHashRouter" in source
            or "createRoutesFromElements" in source
        )
    )


def _extract_react_router_routes(file_fact: FileFact, source: str) -> list[FrontendRouteFact]:
    routes, jsx_path_spans = _extract_react_router_jsx_routes(file_fact, source)
    seen = {(route.route, route.evidence.line_start) for route in routes}
    for match in ROUTER_PATH_RE.finditer(source):
        if any(start <= match.start() < end for start, end in jsx_path_spans):
            continue
        if _offset_is_js_inert(source, match.start()):
            continue
        route_value = match.group("route")
        if not _looks_like_route_value(route_value):
            continue
        line = _line_for_offset(source, match.start())
        route_path = _normalize_frontend_route(route_value)
        key = (route_path, line)
        if key in seen:
            continue
        seen.add(key)
        routes.append(_route(file_fact, route_path, "react", "react-router-route", line))
    return routes


def _extract_react_router_jsx_routes(file_fact: FileFact, source: str) -> tuple[list[FrontendRouteFact], list[tuple[int, int]]]:
    routes: list[FrontendRouteFact] = []
    path_spans: list[tuple[int, int]] = []
    stack: list[str | None] = []
    seen: set[tuple[str, int]] = set()
    index = 0
    while index < len(source):
        close_match = re.search(r"</(?:Route|ModalRoute)\s*>", source[index:])
        open_match = re.search(r"<(?:Route|ModalRoute)\b", source[index:])
        close_index = index + close_match.start() if close_match else -1
        open_index = index + open_match.start() if open_match else -1
        candidates = [item for item in (close_index, open_index) if item >= 0]
        if not candidates:
            break
        tag_start = min(candidates)
        if close_index == tag_start:
            tag_end = close_index + len(close_match.group(0)) - 1 if close_match else source.find(">", tag_start)
            if tag_end < 0:
                break
            if stack and not _offset_is_js_inert(source, tag_start):
                stack.pop()
            index = tag_end + 1
            continue
        tag_end = _jsx_tag_end(source, tag_start)
        if tag_end is None:
            break
        tag_name_end = open_index + len(open_match.group(0)) if open_match else tag_start + len("<Route")
        body = source[tag_name_end:tag_end]
        route_match = REACT_ROUTE_PATH_ATTR_RE.search(body)
        route_path: str | None = None
        if route_match and not _offset_is_js_inert(source, tag_start):
            route_value = route_match.group("route")
            if _looks_like_route_value(route_value):
                route_path = _react_router_joined_route(stack, route_value)
                line = _line_for_offset(source, tag_start)
                key = (route_path, line)
                if key not in seen:
                    seen.add(key)
                    routes.append(_route(file_fact, route_path, "react", "react-router-route", line))
                attr_start = tag_name_end + route_match.start()
                path_spans.append((attr_start, tag_name_end + route_match.end()))
        if not body.rstrip().endswith("/"):
            stack.append(route_path)
        index = tag_end + 1
    return routes, path_spans


def _react_router_joined_route(stack: list[str | None], route_value: str) -> str:
    stripped = route_value.strip()
    parent = next((item for item in reversed(stack) if item), None)
    if not stack or stripped.startswith(("/", "*")):
        return _normalize_frontend_route(stripped)
    if parent is None:
        return _normalize_frontend_route(stripped)
    return _join_frontend_routes([parent, stripped])


def _jsx_tag_end(source: str, tag_start: int) -> int | None:
    quote: str | None = None
    escaped = False
    brace_depth = 0
    index = tag_start + 1
    while index < len(source):
        char = source[index]
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
            index += 1
            continue
        if char == "{":
            brace_depth += 1
        elif char == "}" and brace_depth:
            brace_depth -= 1
        elif char == ">" and brace_depth == 0:
            return index
        index += 1
    return None


def _should_extract_angular_routes(source: str, frontend_frameworks: set[str]) -> bool:
    return bool(
        "angular" in frontend_frameworks
        and (
            "@angular/router" in source
            or "RouterModule.forRoot" in source
            or "RouterModule.forChild" in source
            or re.search(r"\bRoutes\b", source)
            or re.search(r"\broutes\s*=", source, re.IGNORECASE)
        )
    )


def _extract_angular_routes(file_fact: FileFact, source: str) -> list[FrontendRouteFact]:
    routes: list[FrontendRouteFact] = []
    for route_value, offset, _span in _angular_route_entries(source):
        if not _looks_like_route_value(route_value):
            continue
        routes.append(
            _route(
                file_fact,
                route_value,
                "angular",
                "angular-route",
                _line_for_offset(source, offset),
            )
        )
    return routes


def _apply_angular_lazy_route_prefixes(
    root: Path,
    files: list[FileFact],
    routes: list[FrontendRouteFact],
) -> list[FrontendRouteFact]:
    prefixes = _angular_lazy_route_prefixes(root, files)
    if not prefixes:
        return routes

    result: list[FrontendRouteFact] = []
    for route in routes:
        normalized_path = route.path.replace("\\", "/")
        prefix_info = prefixes.get(normalized_path)
        if route.framework != "angular" or prefix_info is None:
            result.append(route)
            continue
        prefix, prefix_evidence = prefix_info
        note = f"lazy prefix:{prefix} via {prefix_evidence.file}:{prefix_evidence.line_start}"
        result.append(
            FrontendRouteFact(
                route=_join_frontend_routes([prefix, route.route]),
                path=route.path,
                framework=route.framework,
                kind="angular-lazy-route",
                evidence=Evidence(
                    file=route.evidence.file,
                    kind=route.evidence.kind,
                    line_start=route.evidence.line_start,
                    line_end=route.evidence.line_end,
                    note=note,
                ),
            )
        )
    return result


def _angular_lazy_route_prefixes(root: Path, files: list[FileFact]) -> dict[str, tuple[str, Evidence]]:
    prefixes: dict[str, tuple[str, Evidence]] = {}
    for file_fact in files:
        normalized = file_fact.path.replace("\\", "/")
        if file_fact.role in {"test", "sample", "generated"} or not normalized.endswith((".ts", ".js", ".mjs")):
            continue
        source = _read(root, file_fact)
        if "loadChildren" not in source:
            continue
        entries = _angular_route_entries(source)
        for match in ANGULAR_LAZY_IMPORT_RE.finditer(source):
            entry = _smallest_angular_entry_containing(entries, match.start())
            if entry is None:
                continue
            prefix, offset, _span = entry
            target_path = _resolve_local_module_path(root, file_fact.path, match.group("target"))
            if not target_path:
                continue
            prefixes.setdefault(
                target_path,
                (
                    prefix,
                    Evidence(
                        file=file_fact.path,
                        kind="frontend-route",
                        line_start=_line_for_offset(source, offset),
                        line_end=_line_for_offset(source, offset),
                    ),
                ),
            )
    return prefixes


def _angular_route_entries(source: str) -> list[tuple[str, int, tuple[int, int]]]:
    spans = _brace_spans(source)
    if not spans:
        return []

    path_by_span: dict[tuple[int, int], str] = {}
    offset_by_span: dict[tuple[int, int], int] = {}
    for match in ROUTER_PATH_RE.finditer(source):
        route_value = match.group("route")
        if route_value != "" and not _looks_like_route_value(route_value):
            continue
        span = _smallest_span_containing(spans, match.start(), match.end())
        if span is None or span in path_by_span:
            continue
        path_by_span[span] = route_value
        offset_by_span[span] = match.start()

    entries: list[tuple[str, int, tuple[int, int]]] = []
    for span, route_value in path_by_span.items():
        ancestors = [
            ancestor
            for ancestor in path_by_span
            if ancestor != span and ancestor[0] < span[0] and ancestor[1] >= span[1]
        ]
        parts = [path_by_span[item] for item in sorted(ancestors, key=lambda item: item[0])]
        parts.append(route_value)
        entries.append((_join_frontend_routes(parts), offset_by_span[span], span))
    return entries


def _smallest_angular_entry_containing(
    entries: list[tuple[str, int, tuple[int, int]]],
    offset: int,
) -> tuple[str, int, tuple[int, int]] | None:
    matches = [entry for entry in entries if entry[2][0] <= offset <= entry[2][1]]
    if not matches:
        return None
    return min(matches, key=lambda entry: entry[2][1] - entry[2][0])


def _brace_spans(source: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    stack: list[int] = []
    quote: str | None = None
    escaped = False
    for offset, char in enumerate(source):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if quote:
            if char == quote:
                quote = None
            continue
        if char in {"'", '"', "`"}:
            quote = char
            continue
        if char == "{":
            stack.append(offset)
        elif char == "}" and stack:
            start = stack.pop()
            spans.append((start, offset))
    return spans


def _smallest_span_containing(
    spans: list[tuple[int, int]],
    start: int,
    end: int,
) -> tuple[int, int] | None:
    matches = [span for span in spans if span[0] <= start and end <= span[1]]
    if not matches:
        return None
    return min(matches, key=lambda span: span[1] - span[0])


def _resolve_local_module_path(root: Path, current_path: str, target: str) -> str | None:
    if not target.startswith("."):
        return None
    current_file = root / current_path
    target_path = (current_file.parent / target).resolve()
    candidates = [target_path]
    suffixes = (".ts", ".js", ".mjs", ".tsx", ".jsx")
    if target_path.suffix not in suffixes:
        candidates.extend(Path(f"{target_path}{suffix}") for suffix in suffixes)
    if not target_path.suffix:
        candidates.extend((target_path / f"index{suffix}") for suffix in suffixes)
    root_resolved = root.resolve()
    for candidate in candidates:
        if not candidate.exists() or not candidate.is_file():
            continue
        try:
            return candidate.relative_to(root_resolved).as_posix()
        except ValueError:
            continue
    return None


def _should_extract_vue_router_routes(source: str, frontend_frameworks: set[str]) -> bool:
    return bool(
        {"vue-router", "vue"} & frontend_frameworks
        and (
            "vue-router" in source
            or "createRouter" in source
            or "createWebHistory" in source
            or "createMemoryHistory" in source
        )
    )


def _looks_like_route_value(route: str) -> bool:
    if not route or route.startswith((".", "http:", "https:", "file:")):
        return False
    if any(char in route for char in ("\n", "\r", "`", "$", "{", "}")):
        return False
    return route in {"", "**"} or route.startswith(("/", ":", "*")) or "/" in route or route.isidentifier()


def _normalize_frontend_route(route: str) -> str:
    stripped = route.strip()
    if not stripped or stripped == "**" or stripped.startswith(("/", ":", "*")):
        return stripped or "/"
    return "/" + stripped


def _route(file_fact: FileFact, route: str, framework: str, kind: str, line: int) -> FrontendRouteFact:
    return FrontendRouteFact(
        route=route,
        path=file_fact.path,
        framework=framework,
        kind=kind,
        evidence=Evidence(file=file_fact.path, kind="frontend-route", line_start=line, line_end=line),
    )


def _read(root: Path, file_fact: FileFact) -> str:
    return (root / file_fact.path).read_text(encoding="utf-8", errors="ignore")


def _find_matching_delimiter(source: str, open_index: int, open_char: str, close_char: str) -> int | None:
    if open_index < 0 or open_index >= len(source):
        return None
    depth = 0
    quote: str | None = None
    escaped = False
    for index in range(open_index, len(source)):
        char = source[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if quote:
            if char == quote:
                quote = None
            continue
        if char in {"'", '"', "`"}:
            quote = char
            continue
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return index
    return None


def _line_for_offset(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


def _dedupe(values: object) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(str(value))
    return result


def _dedupe_components(components: list[ComponentFact]) -> list[ComponentFact]:
    seen: set[tuple[str, str, str, int | None]] = set()
    result: list[ComponentFact] = []
    for component in components:
        key = (
            component.path,
            component.framework,
            component.name,
            component.evidence.line_start,
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(component)
    return result


def _dedupe_api_calls(calls: list[ApiCallFact]) -> list[ApiCallFact]:
    seen: dict[tuple[str, str, str, int], int] = {}
    result: list[ApiCallFact] = []
    for call in calls:
        key = (call.path, call.method or "", call.endpoint, call.evidence.line_start)
        existing_index = seen.get(key)
        if existing_index is None:
            seen[key] = len(result)
            result.append(call)
            continue
        existing = result[existing_index]
        if _api_call_specificity(call) > _api_call_specificity(existing):
            result[existing_index] = call
    return result


def _api_call_specificity(call: ApiCallFact) -> int:
    if call.client == "legacy-api-method":
        return 0
    if call.client in {"api", "client", "http", "request", "service"}:
        return 1
    if call.context in {"dart-client-call", "api-client-direct", "object-client", "rtk-query", "composable-api"}:
        return 3
    if call.client in {"angular-httpclient", "axios", "fetch", "$fetch", "useFetch"}:
        return 3
    return 2


def _looks_like_api_client_receiver(client: str) -> bool:
    normalized = client.strip("_").lower()
    if normalized in {"api", "client", "http", "request", "service", "axios", "dio"}:
        return True
    return any(token in normalized for token in ("api", "client", "http", "request", "service", "dio"))


def _looks_like_angular_http_source(source: str, client: str) -> bool:
    return client.lower() == "http" and ("@angular/common/http" in source or "HttpClient" in source)


def _looks_like_service_facade_receiver(client: str) -> bool:
    normalized = client.strip("_").lower()
    if not normalized.endswith("service"):
        return False
    return not any(token in normalized for token in ("api", "http", "request", "client"))


def _dedupe_state_usages(usages: list[StateUsageFact]) -> list[StateUsageFact]:
    seen: set[tuple[str, str, str, str, int]] = set()
    result: list[StateUsageFact] = []
    for usage in usages:
        key = (usage.source, usage.library, usage.usage, usage.name, usage.evidence.line_start)
        if key in seen:
            continue
        seen.add(key)
        result.append(usage)
    return result

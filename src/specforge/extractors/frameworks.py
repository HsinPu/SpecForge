from __future__ import annotations

from functools import lru_cache
import re
from pathlib import Path

from specforge.models import DependencyFact, Evidence, FileFact, FrameworkFact, ImportFact


FRONTEND_FRAMEWORKS = {
    "bootstrap",
    "blazor",
    "css-modules",
    "ejs",
    "ember",
    "expo",
    "freemarker",
    "fresh",
    "handlebars",
    "html",
    "ionic",
    "capacitor",
    "ios",
    "jsp",
    "mustache",
    "nativescript",
    "next",
    "nuxt",
    "angular",
    "astro",
    "pug",
    "phoenix-liveview",
    "quasar",
    "qwik",
    "qwik-city",
    "pinia",
    "react",
    "react-native",
    "react-navigation",
    "react-router",
    "remix",
    "redux",
    "redwood",
    "sass",
    "selmer",
    "static-site",
    "starlight",
    "solid",
    "solid-router",
    "solid-start",
    "svelte",
    "sveltekit",
    "swiftui",
    "tca",
    "tailwind",
    "tanstack-query",
    "tanstack-router",
    "tanstack-start",
    "trpc",
    "thymeleaf",
    "vite",
    "vue",
    "vue-router",
    "wpf",
    "avalonia",
    "sse",
    "websocket",
    "zustand",
    "flutter",
    "flutter-hooks",
    "go-router",
    "gradio",
    "maui",
    "dio",
    "freezed",
    "riverpod",
    "routerino",
    "streamlit",
}
BACKEND_FRAMEWORKS = {
    "actix-web",
    "adonisjs",
    "airflow",
    "aspnetcore",
    "axum",
    "chi",
    "django",
    "django-ninja",
    "drf",
    "ef-core",
    "echo",
    "elysia",
    "express",
    "fastify",
    "fastapi",
    "feathers",
    "fiber",
    "flask",
    "fresh",
    "gin",
    "gorm",
    "grape",
    "java-web",
    "hapi",
    "hono",
    "koa",
    "ktor",
    "laravel",
    "loopback",
    "clojure-ring",
    "compojure",
    "celery",
    "dagster",
    "dbt",
    "delta-lake",
    "drupal",
    "phoenix",
    "rails",
    "reitit",
    "rocket",
    "sails",
    "sinatra",
    "symfony",
    "servlet",
    "warp",
    "mybatis",
    "spring",
    "spree",
    "strapi",
    "wordpress",
    "openapi",
    "grpc",
    "playframework",
    "qwik-city",
    "great-expectations",
    "jupyter-notebook",
    "kedro",
    "dvc",
    "hydra",
    "keras",
    "mlflow",
    "pytorch",
    "pytorch-lightning",
    "scikit-learn",
    "tensorflow",
    "transformers",
    "wandb",
    "xgboost",
    "socketio",
    "prefect",
    "pyspark",
    "aspnetcore-jwt",
    "authjs",
    "bcrypt",
    "csrf",
    "django-simplejwt",
    "fastapi-jwt",
    "helmet",
    "jwt",
    "nextauth",
    "passport",
    "spring-security",
    "bullmq",
    "kafka",
    "rabbitmq",
    "redis-pubsub",
    "redwood",
    "sse",
    "websocket",
}
RUNTIME_FRAMEWORKS = {
    "ansible",
    "cloudflare-workers",
    "bun",
    "deno",
    "opentofu",
    "packer",
    "pulumi",
    "terraform",
    "terragrunt",
    "stuartsierra-component",
}

REMIX_PACKAGES = {
    "@remix-run/architect",
    "@remix-run/cloudflare",
    "@remix-run/css-bundle",
    "@remix-run/deno",
    "@remix-run/dev",
    "@remix-run/express",
    "@remix-run/netlify",
    "@remix-run/node",
    "@remix-run/react",
    "@remix-run/serve",
    "@remix-run/vercel",
    "remix",
}


def _is_react_router_package(name: str) -> bool:
    return (
        name in {"react-router", "react-router-dom", "@remix-run/router"}
        or name.startswith("react-router-")
        or name.startswith("@react-router/")
    )


def detect_frameworks(
    root: Path,
    files: list[FileFact],
    dependencies: list[DependencyFact],
    imports: list[ImportFact],
) -> list[FrameworkFact]:
    _read_text.cache_clear()
    detected: dict[tuple[str, str], FrameworkFact] = {}
    roles_by_path = {file_fact.path: file_fact.role for file_fact in files}
    dependency_names = {dependency.name.lower() for dependency in dependencies}
    has_solid_dependency = any(name in {"solid-js", "@solidjs/start", "@solidjs/router"} for name in dependency_names)
    has_react_dependency = any(name == "react" or name.startswith("react@") for name in dependency_names)

    for dependency in dependencies:
        name = dependency.name.lower()
        candidates = [
            ("react", "frontend", name == "react" or name.startswith("react@")),
            ("remix", "frontend", _is_remix_package(name)),
            ("react-native", "mobile", name == "react-native" or name.startswith("react-native-") or name.startswith("@react-native/")),
            ("expo", "mobile", name == "expo" or name.startswith("expo-") or name.startswith("@expo/")),
            ("react-navigation", "mobile", name == "@react-navigation/native" or name.startswith("@react-navigation/")),
            ("angular", "frontend", name in {"@angular/core", "@angular/router"} or name.startswith("@angular/")),
            ("astro", "frontend", name == "astro" or name.startswith("@astrojs/")),
            ("starlight", "frontend", name == "@astrojs/starlight"),
            ("fresh", "frontend", name in {"fresh", "@fresh/core"} or name.startswith("@fresh/")),
            ("fresh", "backend", name in {"fresh", "@fresh/core"} or name.startswith("@fresh/")),
            ("qwik", "frontend", name == "@builder.io/qwik" or name.startswith("@builder.io/qwik/")),
            ("qwik-city", "frontend", name == "@builder.io/qwik-city" or name.startswith("@builder.io/qwik-city/")),
            ("qwik-city", "backend", name == "@builder.io/qwik-city" or name.startswith("@builder.io/qwik-city/")),
            ("elysia", "backend", name == "elysia" or name.startswith("elysia@") or name.startswith("@elysiajs/")),
            ("next", "frontend", name == "next" or name.startswith("next@")),
            ("nuxt", "frontend", name == "nuxt" or name.startswith("@nuxt/") or name.startswith("nuxt-")),
            ("phoenix-liveview", "frontend", name == "phoenix_live_view"),
            ("vapor", "backend", name == "vapor" or name.startswith("vapor-")),
            ("fluent", "data", name == "fluent" or name.startswith("fluent-") or name.startswith("fluent_")),
            ("solid", "frontend", name == "solid-js"),
            ("solid-router", "frontend", name == "@solidjs/router"),
            ("solid-start", "frontend", name == "@solidjs/start" or name.startswith("solid-start")),
            ("svelte", "frontend", name == "svelte"),
            ("sveltekit", "frontend", name == "@sveltejs/kit"),
            ("tca", "frontend", name in {"swift-composable-architecture", "composablearchitecture"}),
            ("vue", "frontend", name == "vue" or name.startswith("vue@")),
            ("vite", "frontend", name == "vite" or name.startswith("vite@")),
            ("quasar", "frontend", name in {"quasar", "nuxt-quasar-ui"} or name.startswith("@quasar/")),
            ("ionic", "frontend", name in {"@ionic/angular", "@ionic/react", "@ionic/vue", "ionic-angular"} or name.startswith("@ionic/")),
            ("capacitor", "mobile", name == "@capacitor/core" or name.startswith("@capacitor/")),
            ("flutter", "frontend", name == "flutter"),
            ("go-router", "frontend", name == "go_router"),
            ("routerino", "frontend", name == "routerino"),
            ("riverpod", "frontend", name in {"riverpod", "flutter_riverpod", "hooks_riverpod", "riverpod_annotation"}),
            ("flutter-hooks", "frontend", name in {"flutter_hooks", "hooks_riverpod"}),
            ("dio", "frontend", name == "dio"),
            ("freezed", "frontend", name in {"freezed", "freezed_annotation"}),
            ("android", "mobile", name.startswith("androidx.") or name.startswith("com.android.")),
            ("room", "data", name == "androidx.room" or name.startswith("androidx.room:") or name.endswith(".android.room")),
            ("nativescript", "mobile", name in {"nativescript", "tns-core-modules"} or name.startswith("@nativescript/") or name.startswith("nativescript-")),
            ("ember", "frontend", name == "ember-source" or name.startswith("@ember/")),
            ("blazor", "frontend", "microsoft.aspnetcore.blazor" in name or "microsoft.aspnetcore.components" in name),
            ("maui", "mobile", name.startswith("microsoft.maui") or name in {"microsoft.maui.controls", "microsoft.maui.essentials"}),
            ("wpf", "frontend", name.startswith("microsoft.windowsdesktop.app.wpf") or name == "presentationframework"),
            ("avalonia", "frontend", name == "avalonia" or name.startswith("avalonia.")),
            ("react-router", "frontend", _is_react_router_package(name)),
            ("redwood", "frontend", name.startswith("@redwoodjs/") and name not in {"@redwoodjs/api", "@redwoodjs/api-server", "@redwoodjs/graphql-server"}),
            ("redwood", "backend", name in {"@redwoodjs/api", "@redwoodjs/api-server", "@redwoodjs/graphql-server"} or name.startswith("@redwoodjs/")),
            ("tanstack-query", "frontend", name in {"@tanstack/react-query", "react-query"}),
            ("tanstack-router", "frontend", name in {"@tanstack/react-router", "@tanstack/solid-router", "@tanstack/vue-router", "@tanstack/router-core"}),
            ("tanstack-start", "frontend", name in {"@tanstack/start", "@tanstack/react-start", "@tanstack/solid-start", "@tanstack/vue-start"} or name.startswith("@tanstack/start-")),
            ("vue-router", "frontend", name == "vue-router"),
            ("redux", "frontend", name in {"redux", "react-redux", "@reduxjs/toolkit"} or "redux" in name),
            ("zustand", "frontend", name == "zustand"),
            ("pinia", "frontend", name == "pinia"),
            ("tailwind", "frontend", name == "tailwindcss" or "tailwind" in name),
            ("bootstrap", "frontend", name == "bootstrap" or name.startswith("bootstrap@")),
            ("sass", "frontend", name in {"sass", "node-sass"} or name.startswith("sass@")),
            ("handlebars", "frontend", name in {"handlebars", "hbs", "express-handlebars"}),
            ("graphql", "backend", name in {"graphql", "express-graphql", "apollo-server", "@apollo/server"}),
            ("trpc", "backend", name.startswith("@trpc/")),
            ("socketio", "backend", name in {"socket.io", "socket.io-client", "flask-socketio"}),
            ("authjs", "security", name in {"auth", "@auth/core", "@auth/prisma-adapter"} or name.startswith("@auth/")),
            ("nextauth", "security", name in {"next-auth", "@next-auth/prisma-adapter"} or name.startswith("next-auth")),
            ("passport", "security", name == "passport" or name.startswith("passport-") or name.startswith("@nestjs/passport")),
            ("jwt", "security", name in {"jsonwebtoken", "jwt-decode", "@nestjs/jwt", "pyjwt", "python-jose"} or "jwt" in name),
            ("bcrypt", "security", name in {"bcrypt", "bcryptjs", "passlib"} or "bcrypt" in name),
            ("helmet", "security", name == "helmet"),
            ("csrf", "security", name in {"csurf", "csrf", "csurf-csrf"}),
            ("django-simplejwt", "security", name in {"djangorestframework-simplejwt", "django-rest-framework-simplejwt"}),
            ("fastapi-jwt", "security", name == "fastapi-jwt-auth"),
            ("websocket", "backend", name in {"ws", "websocket", "websocket-stream"}),
            ("sse", "backend", name in {"sse", "express-sse", "express-sse-ts", "particle-api-js"} or "server-sent" in name),
            ("sse", "frontend", name in {"eventsource", "event-source-polyfill"}),
            ("kafka", "backend", name in {"kafkajs", "kafka-node", "node-rdkafka"} or "kafka" in name),
            ("rabbitmq", "backend", name in {"amqplib", "amqp-connection-manager"} or "rabbitmq" in name),
            ("bullmq", "backend", name in {"bull", "bullmq"}),
            ("mongoose", "data", name == "mongoose" or name.startswith("mongoose-")),
            ("sequelize", "data", name == "sequelize" or name.startswith("sequelize-")),
            ("airflow", "workflow", name in {"apache-airflow", "airflow"} or name.startswith("apache-airflow-")),
            ("dbt", "data", name in {"dbt-core", "dbt"} or name.startswith("dbt-")),
            ("prefect", "workflow", name == "prefect" or name.startswith("prefect-")),
            ("dagster", "workflow", name == "dagster" or name.startswith("dagster-")),
            ("kedro", "data", name == "kedro" or name.startswith("kedro-")),
            ("great-expectations", "data-quality", name in {"great-expectations", "great_expectations"}),
            ("pyspark", "data", name == "pyspark"),
            ("delta-lake", "data", name in {"delta-spark", "deltalake"} or "delta-lake" in name),
            ("jupyter-notebook", "notebook", name in {"jupyter", "notebook", "jupyterlab", "ipykernel"}),
            ("dvc", "mlops", name.startswith("dvc")),
            ("hydra", "config", name in {"hydra", "hydra-core", "omegaconf"} or name.startswith("hydra-")),
            ("mlflow", "mlops", name == "mlflow" or name.startswith("mlflow")),
            ("pytorch", "ml", name in {"torch", "pytorch", "torchvision", "torchaudio"} or name.startswith(("torch==", "torch>=", "torch<=", "torchvision", "torchaudio"))),
            ("pytorch-lightning", "ml", name in {"lightning", "pytorch-lightning"} or name.startswith(("lightning==", "pytorch-lightning"))),
            ("tensorflow", "ml", name.startswith("tensorflow")),
            ("keras", "ml", name == "keras" or name.startswith("keras")),
            ("scikit-learn", "ml", name in {"scikit-learn", "sklearn"} or name.startswith("scikit-learn")),
            ("transformers", "ml", name in {"transformers", "sentence-transformers"} or name.startswith("transformers")),
            ("wandb", "mlops", name == "wandb" or name.startswith("wandb")),
            ("xgboost", "ml", name == "xgboost" or name.startswith("xgboost")),
            ("streamlit", "frontend", name == "streamlit" or name.startswith("streamlit")),
            ("gradio", "frontend", name == "gradio" or name.startswith("gradio")),
            ("grpc", "backend", name in {"grpcio", "grpcio-tools", "@grpc/grpc-js", "grpc"} or "google.golang.org/grpc" in name),
            ("electron", "desktop", name == "electron" or name.startswith("@electron/")),
            ("tauri", "desktop", name == "tauri" or name.startswith("@tauri-apps/")),
            ("mustache", "frontend", name == "mustache"),
            ("ejs", "frontend", name == "ejs"),
            ("pug", "frontend", name == "pug"),
            ("thymeleaf", "frontend", "thymeleaf" in name),
            ("freemarker", "frontend", "freemarker" in name),
            ("express", "backend", name == "express" or name.startswith("express@")),
            ("fastify", "backend", name == "fastify" or name.startswith("@fastify/") or name.startswith("fastify-")),
            ("hono", "backend", name == "hono" or name.startswith("@hono/")),
            ("ktor", "backend", name == "io.ktor.plugin" or name.startswith("io.ktor:ktor-server") or name.startswith("io.ktor/ktor-server")),
            ("bun", "runtime", name in {"bun", "bun-types", "@types/bun"}),
            ("feathers", "backend", name.startswith("@feathersjs/") or name in {"feathers", "feathers-memory"} or name.startswith("feathers-")),
            ("feathers-mongoose", "data", name == "feathers-mongoose"),
            ("feathers-nedb", "data", name == "feathers-nedb"),
            ("strapi", "backend", name == "@strapi/strapi" or name == "strapi" or name.startswith("@strapi/plugin-") or name.startswith("strapi-plugin-")),
            ("prisma", "data", name in {"prisma", "@prisma/client"} or name.startswith("@prisma/")),
            ("adonisjs", "backend", name == "@adonisjs/core" or name == "adonis-preset-ts"),
            ("adonis-lucid", "data", name == "@adonisjs/lucid" or name.startswith("@adonisjs/lucid-")),
            ("sails", "backend", name == "sails" or name.startswith("sails-hook-")),
            ("waterline", "data", name in {"waterline", "sails-hook-orm"}),
            ("celery", "backend", name == "celery" or name.startswith("celery")),
            ("nestjs", "backend", name.startswith("@nestjs/")),
            ("fastapi", "backend", name == "fastapi" or name.startswith("fastapi")),
            ("flask", "backend", name == "flask" or name.startswith("flask")),
            ("hapi", "backend", name in {"hapi", "@hapi/hapi"} or name.startswith("hapi-") or name.startswith("@hapi/")),
            ("koa", "backend", name == "koa" or name in {"koa-router", "@koa/router"} or name.startswith("koa-")),
            ("loopback", "backend", name in {"@loopback/rest", "@loopback/core", "@loopback/boot", "@loopback/authentication", "@loopback/authorization"} or name.startswith("@loopback/rest-")),
            ("loopback-repository", "data", name in {"@loopback/repository", "@loopback/repository-json-schema"}),
            ("grape", "backend", name == "grape" or name.startswith("grape-")),
            ("gin", "backend", "gin-gonic/gin" in name),
            ("gorm", "backend", name.startswith("gorm.io/gorm")),
            ("echo", "backend", "labstack/echo" in name),
            ("fiber", "backend", "gofiber/fiber" in name),
            ("chi", "backend", "go-chi/chi" in name),
            ("axum", "backend", name == "axum"),
            ("actix-web", "backend", name in {"actix-web", "actix_web"} or name.startswith("actix-")),
            ("rocket", "backend", name == "rocket" or name.startswith("rocket_")),
            ("warp", "backend", name == "warp"),
            ("django", "backend", name in {"django", "django-filter"} or name.startswith("django")),
            ("django-ninja", "backend", name in {"django-ninja", "ninja"} or name.startswith("django-ninja")),
            ("drf", "backend", name.startswith("djangorestframework")),
            ("laravel", "backend", name == "laravel/framework"),
            ("illuminate", "backend", name.startswith("illuminate/")),
            ("slim", "backend", name == "slim/slim" or name.startswith("slim/")),
            ("sinatra", "backend", name == "sinatra" or name.startswith("sinatra-")),
            ("active-record", "data", name in {"activerecord", "sinatra-activerecord"} or name.startswith("activerecord-")),
            ("rails", "backend", name in {"rails", "railties", "actionpack"} or name.startswith(("spree", "solid_"))),
            ("spree", "backend", name == "spree" or name.startswith("spree_")),
            ("phoenix", "backend", name == "phoenix" or name.startswith("phoenix_")),
            ("symfony", "backend", name in {"symfony/framework-bundle", "symfony/routing"}),
            ("yii2", "backend", name == "yiisoft/yii2" or name.startswith("yiisoft/yii2-")),
            ("aspnetcore", "backend", "microsoft.aspnetcore" in name or name == "microsoft.net.sdk.web"),
            ("ef-core", "data", name.startswith("microsoft.entityframeworkcore") or name.endswith(".entityframeworkcore")),
            ("spring", "backend", "spring-boot" in name or "springframework" in name),
            ("spring-security", "security", "spring-security" in name),
            ("jpa", "data", "spring-boot-starter-data-jpa" in name or "jakarta.persistence" in name or "javax.persistence" in name),
            ("hibernate", "data", "hibernate" in name),
            ("playframework", "backend", name in {"playframework/play-scala", "playframework/play-java"} or name.startswith("org.playframework/") or name.startswith("com.typesafe.play/") or name.startswith("play:")),
            ("play-ebean", "data", name == "playframework/play-ebean" or "play-ebean" in name),
            ("play-slick", "data", "play-slick" in name or name.endswith("/slick")),
            ("anorm", "data", name.endswith("/anorm") or name == "play:jdbc"),
            ("servlet", "backend", "servlet-api" in name or "jakarta.servlet" in name or "javax.servlet" in name),
            ("java-web", "backend", "servlet-api" in name or "jakarta.servlet" in name or "javax.servlet" in name),
            ("jsp", "frontend", "jsp-api" in name or "jakarta.servlet.jsp" in name or "javax.servlet.jsp" in name),
            ("mybatis", "backend", "mybatis" in name),
            ("openapi", "backend", name in {"swagger-core", "swagger-parser", "openapi-generator"} or "openapi" in name or "swagger" in name),
            ("wordpress", "backend", name.startswith("wordpress/") or name == "johnpbloch/wordpress"),
            ("drupal", "backend", name.startswith("drupal/")),
            ("clojure-ring", "backend", name.startswith("ring/")),
            ("compojure", "backend", name == "compojure/compojure"),
            ("reitit", "backend", "reitit" in name),
            ("selmer", "frontend", name == "selmer/selmer"),
            ("next.jdbc", "data", name == "com.github.seancorfield/next.jdbc" or name == "seancorfield/next.jdbc"),
            ("stuartsierra-component", "runtime", name == "com.stuartsierra/component"),
            ("luminus", "backend", "luminus" in name),
            ("pulumi", "runtime", name == "pulumi" or name.startswith("@pulumi/") or name.startswith("pulumi-")),
            ("cloudflare-workers", "runtime", name in {"wrangler", "@cloudflare/workers-types"} or name.startswith("@cloudflare/")),
            ("bun", "runtime", name in {"bun", "bun-types", "@types/bun"}),
            ("deno", "runtime", name == "deno"),
            ("terraform", "runtime", name in {"terraform", "python-terraform"} or name.startswith("terraform")),
            ("ansible", "runtime", name in {"ansible", "ansible-core", "molecule"} or name.startswith("ansible")),
        ]
        for framework, category, matched in candidates:
            if matched:
                _add(
                    detected,
                    framework,
                    category,
                    "dependency",
                    1.0,
                    dependency.evidence,
                )

    for file_fact in files:
        if file_fact.role in {"documentation", "generated", "sample", "test"}:
            continue
        path = file_fact.path.replace("\\", "/")
        name = Path(path).name
        lower = path.lower()
        config_matches = [
            ("next", "frontend", name.startswith("next.config")),
            ("astro", "frontend", name.startswith("astro.config")),
            ("nuxt", "frontend", name.startswith("nuxt.config")),
            ("sveltekit", "frontend", name.startswith("svelte.config")),
            ("svelte", "frontend", name.startswith("svelte.config")),
            ("vite", "frontend", name.startswith("vite.config")),
            ("redwood", "frontend", name == "redwood.toml"),
            ("redwood", "backend", name == "redwood.toml"),
            ("tailwind", "frontend", name.startswith("tailwind.config")),
            ("sass", "frontend", lower.endswith((".scss", ".sass"))),
            ("css-modules", "frontend", ".module." in name and lower.endswith((".css", ".scss", ".sass"))),
            ("spring", "backend", _looks_like_spring_config_path(lower) and not _looks_like_ktor_config(root / file_fact.path)),
            ("openapi", "backend", _looks_like_openapi_spec_path(lower, root / file_fact.path)),
            ("prisma", "data", lower.endswith("schema.prisma")),
            ("graphql", "backend", lower.endswith((".graphql", ".graphqls", ".gql"))),
            ("grpc", "backend", lower.endswith(".proto") and "service " in _read_text(root / file_fact.path)),
            ("helm", "runtime", name == "Chart.yaml"),
            ("kubernetes", "runtime", lower.endswith((".yaml", ".yml")) and _looks_like_kubernetes_manifest(root / file_fact.path)),
            ("terraform", "runtime", lower.endswith((".tf", ".tfvars", ".tfvars.json", ".tofu")) or name == ".terraform.lock.hcl"),
            ("cloudflare-workers", "runtime", lower.endswith(("wrangler.toml", "wrangler.json", "wrangler.jsonc"))),
            ("bun", "runtime", name.lower() in {"bun.lock", "bun.lockb", "bunfig.toml"}),
            ("deno", "runtime", lower.endswith(("deno.json", "deno.jsonc", "deno.lock"))),
            ("opentofu", "runtime", lower.endswith(".tofu") or lower.endswith((".tf", ".tfvars", ".tfvars.json")) and _looks_like_opentofu_source(root / file_fact.path)),
            ("terragrunt", "runtime", name == "terragrunt.hcl"),
            ("packer", "runtime", lower.endswith(".pkr.hcl") or _looks_like_packer_source(root / file_fact.path)),
            ("pulumi", "runtime", name in {"Pulumi.yaml", "Pulumi.yml"} or re.fullmatch(r"Pulumi\.[^.]+\.(?:ya?ml)", name) is not None),
            ("ansible", "runtime", _looks_like_ansible_path(lower, root / file_fact.path)),
            ("airflow", "workflow", name in {"airflow_settings.yaml", "airflow_settings.yml"} or lower.startswith("dags/") and lower.endswith(".py") and _looks_like_airflow_source(root / file_fact.path)),
            ("dbt", "data", _looks_like_dbt_config_path(lower)),
            ("prefect", "workflow", name == "prefect.yaml"),
            ("dagster", "workflow", name in {"dagster.yaml", "workspace.yaml", "workspace.yml"}),
            ("kedro", "data", name in {"catalog.yml", "catalog.yaml", "parameters.yml", "parameters.yaml"} and ("/conf/" in f"/{lower}" or lower.startswith("conf/"))),
            ("great-expectations", "data-quality", name in {"great_expectations.yml", "great_expectations.yaml"} or lower.startswith(("great_expectations/", "gx/"))),
            ("jupyter-notebook", "notebook", lower.endswith(".ipynb")),
            ("dvc", "mlops", name in {"dvc.yaml", "dvc.lock"} or lower.endswith(".dvc")),
            ("mlflow", "mlops", name == "MLproject"),
            ("hydra", "config", lower.endswith((".yml", ".yaml")) and _looks_like_hydra_config(root / file_fact.path)),
            ("streamlit", "frontend", lower == ".streamlit/config.toml"),
            ("java-web", "backend", lower.endswith("web-inf/web.xml")),
            ("servlet", "backend", lower.endswith("web-inf/web.xml")),
            ("ktor", "backend", name in {"application.conf", "application.yaml", "application.yml"} and _looks_like_ktor_config(root / file_fact.path)),
            ("rails", "backend", lower == "config/routes.rb" or lower.endswith("/config/routes.rb")),
            ("sinatra", "backend", lower == "config.ru" and _looks_like_sinatra_rack_source(root / file_fact.path)),
            ("laravel", "backend", lower in {"routes/api.php", "routes/web.php"}),
            ("phoenix", "backend", lower.endswith("router.ex")),
            (
                "aspnetcore",
                "backend",
                (lower.endswith(".csproj") and _looks_like_aspnet_project_file(root / file_fact.path))
                or (name in {"Program.cs", "Startup.cs"} and _looks_like_aspnet_source(root / file_fact.path)),
            ),
            ("maui", "mobile", lower.endswith(".csproj") and _looks_like_maui_project_file(root / file_fact.path)),
            ("wpf", "frontend", lower.endswith(".csproj") and _looks_like_wpf_project_file(root / file_fact.path)),
            ("avalonia", "frontend", lower.endswith((".csproj", ".xaml", ".axaml")) and _looks_like_avalonia_source(root / file_fact.path)),
            ("django", "backend", _looks_like_django_project_file(root / file_fact.path, lower, name)),
            ("symfony", "backend", lower in {"config/routes.yaml", "config/routes.yml"} or lower.startswith("src/controller/")),
            (
                "nestjs",
                "backend",
                lower.endswith((".controller.ts", ".module.ts")) and _looks_like_nestjs_source(root / file_fact.path),
            ),
            ("fastify", "backend", lower.endswith((".ts", ".js", ".mjs", ".cjs")) and _looks_like_fastify_source(root / file_fact.path)),
            ("hono", "backend", lower.endswith((".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")) and _looks_like_hono_source(root / file_fact.path)),
            ("qwik", "frontend", lower.endswith((".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")) and _looks_like_qwik_source(root / file_fact.path)),
            ("qwik-city", "frontend", lower.endswith((".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")) and _looks_like_qwik_city_source(root / file_fact.path)),
            ("qwik-city", "backend", lower.endswith((".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")) and _looks_like_qwik_city_source(root / file_fact.path)),
            ("elysia", "backend", lower.endswith((".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")) and _looks_like_elysia_source(root / file_fact.path)),
            ("feathers", "backend", lower.endswith((".ts", ".js")) and _looks_like_feathers_source(root / file_fact.path)),
            ("loopback", "backend", lower.endswith((".ts", ".js")) and _looks_like_loopback_source(root / file_fact.path)),
            ("strapi", "backend", _looks_like_strapi_source(root / file_fact.path)),
            ("tauri", "desktop", lower.endswith("tauri.conf.json") or lower.startswith("src-tauri/")),
            ("drupal", "backend", lower.endswith(".routing.yml") or lower.endswith(".routing.yaml")),
            ("clojure-ring", "backend", name == "project.clj"),
            ("playframework", "backend", name == "build.sbt" and _looks_like_play_build(root / file_fact.path)),
            ("playframework", "backend", lower.endswith("/conf/routes") or lower == "conf/routes"),
        ]
        path_matches = [
            ("astro", "frontend", lower.endswith(".astro")),
            ("fresh", "frontend", lower.endswith((".ts", ".tsx", ".js", ".jsx")) and _looks_like_fresh_source(root / file_fact.path)),
            ("fresh", "backend", lower.endswith((".ts", ".tsx", ".js", ".jsx")) and _looks_like_fresh_source(root / file_fact.path)),
            ("svelte", "frontend", lower.endswith(".svelte")),
            ("sveltekit", "frontend", lower.endswith(".svelte") and "/routes/" in f"/{lower}"),
            ("vue", "frontend", lower.endswith(".vue")),
            ("solid", "frontend", lower.endswith((".tsx", ".jsx", ".ts", ".js")) and _looks_like_solid_source(root / file_fact.path)),
            ("solid-router", "frontend", lower.endswith((".tsx", ".jsx", ".ts", ".js")) and _looks_like_solid_router_source(root / file_fact.path)),
            ("solid-start", "frontend", lower.endswith((".tsx", ".jsx", ".ts", ".js")) and _looks_like_solid_start_source(root / file_fact.path)),
            (
                "react",
                "frontend",
                (lower.endswith(".tsx") or lower.endswith(".jsx"))
                and not (has_solid_dependency and not has_react_dependency)
                and not _looks_like_solid_source(root / file_fact.path)
                and not _looks_like_qwik_source(root / file_fact.path),
            ),
            ("react-native", "mobile", lower.endswith((".tsx", ".jsx", ".ts", ".js")) and _looks_like_react_native_source(root / file_fact.path)),
            ("redwood", "frontend", lower.endswith((".tsx", ".jsx", ".ts", ".js")) and _looks_like_redwood_web_source(root / file_fact.path)),
            ("redwood", "backend", lower.endswith((".ts", ".js")) and _looks_like_redwood_api_source(root / file_fact.path)),
            ("expo", "mobile", lower.endswith((".tsx", ".jsx", ".ts", ".js")) and _looks_like_expo_source(root / file_fact.path)),
            ("swiftui", "frontend", lower.endswith(".swift") and _looks_like_swiftui_source(root / file_fact.path)),
            ("vapor", "backend", lower.endswith(".swift") and _looks_like_vapor_source(root / file_fact.path)),
            ("fluent", "data", lower.endswith(".swift") and _looks_like_fluent_source(root / file_fact.path)),
            ("ios", "mobile", lower.endswith(".swift") or ".xcodeproj/" in lower or _looks_like_ios_plist_path(lower)),
            ("tca", "frontend", lower.endswith(".swift") and _looks_like_tca_source(root / file_fact.path)),
            ("tanstack-query", "frontend", lower.endswith((".ts", ".tsx", ".js", ".jsx")) and _looks_like_tanstack_query_source(root / file_fact.path)),
            ("tanstack-router", "frontend", lower.endswith((".ts", ".tsx", ".js", ".jsx")) and _looks_like_tanstack_router_source(root / file_fact.path)),
            ("tanstack-start", "frontend", lower.endswith((".ts", ".tsx", ".js", ".jsx")) and _looks_like_tanstack_start_source(root / file_fact.path)),
            ("trpc", "frontend", lower.endswith((".ts", ".tsx", ".js", ".jsx")) and _looks_like_trpc_source(root / file_fact.path)),
            (
                "angular",
                "frontend",
                lower.endswith((".component.ts", ".component.html"))
                or lower.endswith((".module.ts", ".routing.ts", ".routes.ts"))
                and "@angular/" in _read_text(root / file_fact.path),
            ),
            ("ember", "frontend", lower in {"ember-cli-build.js", "app/router.js"} or lower.startswith("app/") and lower.endswith((".hbs", ".js")) and _looks_like_ember_source(root / file_fact.path)),
            ("blazor", "frontend", lower.endswith((".razor", ".cshtml")) and ("@page" in _read_text(root / file_fact.path) or "/pages/" in f"/{lower}")),
            ("static-site", "frontend", lower.endswith((".html", ".htm")) or lower.startswith(("public/", "static/"))),
            ("html", "frontend", lower.endswith((".html", ".htm"))),
            ("freemarker", "frontend", lower.endswith(".ftl")),
            ("handlebars", "frontend", lower.endswith((".hbs", ".handlebars"))),
            ("mustache", "frontend", lower.endswith(".mustache")),
            ("ejs", "frontend", lower.endswith(".ejs")),
            ("pug", "frontend", lower.endswith(".pug")),
            ("spring", "backend", lower.endswith((".java", ".kt")) and _looks_like_spring_source(root / file_fact.path)),
            ("jpa", "data", lower.endswith((".java", ".kt", ".properties", ".yml", ".yaml")) and _looks_like_jpa_source(root / file_fact.path)),
            ("hibernate", "data", lower.endswith((".java", ".kt", ".properties", ".yml", ".yaml")) and _looks_like_hibernate_source(root / file_fact.path)),
            ("java-web", "backend", "/src/main/webapp/" in f"/{lower}"),
            ("jsp", "frontend", lower.endswith(".jsp")),
            ("gin", "backend", lower.endswith(".go") and "gin-gonic/gin" in _read_text(root / file_fact.path).lower()),
            ("gorm", "backend", lower.endswith(".go") and ("gorm.io/gorm" in _read_text(root / file_fact.path).lower() or "gorm:\"" in _read_text(root / file_fact.path).lower())),
            ("rails", "backend", (lower.startswith("app/controllers/") or "/app/controllers/" in lower) and lower.endswith("_controller.rb")),
            ("sinatra", "backend", lower.endswith((".rb", ".ru")) and _looks_like_sinatra_ruby_source(root / file_fact.path)),
            ("grape", "backend", lower.endswith((".rb", ".ru")) and _looks_like_grape_ruby_source(root / file_fact.path)),
            ("laravel", "backend", lower.startswith("app/http/controllers/") and lower.endswith(".php")),
            ("phoenix", "backend", lower.endswith(".ex") and "_web/" in lower),
            ("flutter", "frontend", lower.startswith("lib/") and lower.endswith(".dart")),
            ("go-router", "frontend", lower.endswith(".dart") and "goroute(" in _read_text(root / file_fact.path).lower()),
            ("routerino", "frontend", lower.endswith(".dart") and _looks_like_routerino_source(root / file_fact.path)),
            ("riverpod", "frontend", lower.endswith(".dart") and _looks_like_riverpod_source(root / file_fact.path)),
            ("flutter-hooks", "frontend", lower.endswith(".dart") and _looks_like_flutter_hooks_source(root / file_fact.path)),
            ("dio", "frontend", lower.endswith(".dart") and _looks_like_dio_source(root / file_fact.path)),
            ("freezed", "frontend", lower.endswith(".dart") and _looks_like_freezed_source(root / file_fact.path)),
            ("android", "mobile", lower.endswith("androidmanifest.xml")),
            ("room", "data", lower.endswith((".kt", ".java", ".kts", ".gradle", ".gradle.kts", ".toml")) and _looks_like_room_source(root / file_fact.path)),
            ("maui", "mobile", lower.endswith(".xaml") and _looks_like_maui_xaml(root / file_fact.path)),
            ("wpf", "frontend", lower.endswith(".xaml") and _looks_like_wpf_xaml(root / file_fact.path)),
            ("avalonia", "frontend", lower.endswith((".xaml", ".axaml")) and _looks_like_avalonia_source(root / file_fact.path)),
            ("electron", "desktop", lower.endswith((".ts", ".js", ".mjs")) and _looks_like_electron_source(root / file_fact.path)),
            ("tauri", "desktop", lower.startswith("src-tauri/") or lower.endswith("tauri.conf.json")),
            ("wordpress", "backend", lower.endswith((".php", ".module", ".inc")) and _looks_like_wordpress_source(root / file_fact.path)),
            ("drupal", "backend", lower.endswith((".php", ".module", ".install", ".theme")) and _looks_like_drupal_source(root / file_fact.path)),
            ("yii2", "backend", lower.endswith(".php") and _looks_like_yii_source(root / file_fact.path)),
            ("slim", "backend", lower.endswith(".php") and _looks_like_slim_php_source(root / file_fact.path)),
            ("mybatis", "backend", lower.endswith("mapper.xml") or "@mapper" in _read_text(root / file_fact.path).lower()),
            ("celery", "backend", lower.endswith(".py") and _looks_like_celery_source(root / file_fact.path)),
            ("airflow", "workflow", lower.endswith(".py") and _looks_like_airflow_source(root / file_fact.path)),
            ("prefect", "workflow", lower.endswith(".py") and _looks_like_prefect_source(root / file_fact.path)),
            ("dagster", "workflow", lower.endswith(".py") and _looks_like_dagster_source(root / file_fact.path)),
            ("kedro", "data", lower.endswith(".py") and _looks_like_kedro_source(root / file_fact.path)),
            ("pyspark", "data", lower.endswith((".py", ".ipynb")) and _looks_like_spark_source(root / file_fact.path)),
            ("delta-lake", "data", lower.endswith((".py", ".ipynb")) and _looks_like_delta_source(root / file_fact.path)),
            ("great-expectations", "data-quality", lower.endswith((".py", ".ipynb")) and _looks_like_great_expectations_source(root / file_fact.path)),
            ("pytorch", "ml", lower.endswith((".py", ".ipynb")) and _looks_like_pytorch_source(root / file_fact.path)),
            ("pytorch-lightning", "ml", lower.endswith((".py", ".ipynb")) and _looks_like_lightning_source(root / file_fact.path)),
            ("tensorflow", "ml", lower.endswith((".py", ".ipynb")) and _looks_like_tensorflow_source(root / file_fact.path)),
            ("keras", "ml", lower.endswith((".py", ".ipynb")) and _looks_like_keras_source(root / file_fact.path)),
            ("scikit-learn", "ml", lower.endswith((".py", ".ipynb")) and _looks_like_sklearn_source(root / file_fact.path)),
            ("transformers", "ml", lower.endswith((".py", ".ipynb")) and _looks_like_transformers_source(root / file_fact.path)),
            ("mlflow", "mlops", lower.endswith((".py", ".ipynb")) and _looks_like_mlflow_source(root / file_fact.path)),
            ("wandb", "mlops", lower.endswith((".py", ".ipynb")) and _looks_like_wandb_source(root / file_fact.path)),
            ("hydra", "config", lower.endswith((".py", ".ipynb")) and _looks_like_hydra_source(root / file_fact.path)),
            ("streamlit", "frontend", lower.endswith(".py") and _looks_like_streamlit_source(root / file_fact.path)),
            ("gradio", "frontend", lower.endswith((".py", ".ipynb")) and _looks_like_gradio_source(root / file_fact.path)),
            ("socketio", "backend", lower.endswith((".ts", ".tsx", ".js", ".jsx", ".py")) and _looks_like_socketio_source(root / file_fact.path)),
            ("authjs", "security", lower.endswith((".ts", ".tsx", ".js", ".jsx")) and _looks_like_authjs_source(root / file_fact.path)),
            ("nextauth", "security", lower.endswith((".ts", ".tsx", ".js", ".jsx")) and _looks_like_nextauth_source(root / file_fact.path)),
            ("passport", "security", lower.endswith((".ts", ".tsx", ".js", ".jsx")) and _looks_like_passport_source(root / file_fact.path)),
            ("jwt", "security", lower.endswith((".ts", ".tsx", ".js", ".jsx", ".py", ".java", ".kt", ".cs", ".php")) and _looks_like_jwt_source(root / file_fact.path)),
            ("bcrypt", "security", lower.endswith((".ts", ".tsx", ".js", ".jsx", ".py", ".java", ".kt", ".cs", ".php")) and _looks_like_bcrypt_source(root / file_fact.path)),
            ("spring-security", "security", lower.endswith((".java", ".kt")) and _looks_like_spring_security_source(root / file_fact.path)),
            ("django-simplejwt", "security", lower.endswith(".py") and _looks_like_django_simplejwt_source(root / file_fact.path)),
            ("fastapi-jwt", "security", lower.endswith(".py") and _looks_like_fastapi_security_source(root / file_fact.path)),
            ("aspnetcore-jwt", "security", lower.endswith((".cs", ".csproj")) and _looks_like_aspnet_jwt_source(root / file_fact.path)),
            ("websocket", "backend", lower.endswith((".ts", ".tsx", ".js", ".jsx", ".py")) and _looks_like_websocket_source(root / file_fact.path)),
            ("sse", "backend", lower.endswith((".ts", ".tsx", ".js", ".jsx", ".py")) and _looks_like_sse_source(root / file_fact.path)),
            ("sse", "frontend", lower.endswith((".html", ".htm", ".ts", ".tsx", ".js", ".jsx", ".vue", ".svelte")) and _looks_like_eventsource_source(root / file_fact.path)),
            ("kafka", "backend", lower.endswith((".ts", ".tsx", ".js", ".jsx", ".py", ".java", ".kt", ".go")) and _looks_like_kafka_source(root / file_fact.path)),
            ("rabbitmq", "backend", lower.endswith((".ts", ".tsx", ".js", ".jsx", ".py", ".java", ".kt", ".go")) and _looks_like_rabbitmq_source(root / file_fact.path)),
            ("bullmq", "backend", lower.endswith((".ts", ".tsx", ".js", ".jsx")) and _looks_like_bullmq_source(root / file_fact.path)),
            ("redis-pubsub", "backend", lower.endswith((".ts", ".tsx", ".js", ".jsx", ".py")) and _looks_like_redis_pubsub_source(root / file_fact.path)),
            ("pulumi", "runtime", lower.endswith((".py", ".ts", ".js", ".go", ".cs", ".java")) and _looks_like_pulumi_source(root / file_fact.path)),
        ]
        for framework, category, matched in [*config_matches, *path_matches]:
            if matched:
                _add(detected, framework, category, "path", 0.75, file_fact.evidence)
        if lower.endswith((".html", ".htm")):
            source = _read_text(root / file_fact.path)
            if _looks_like_thymeleaf(source):
                _add(detected, "thymeleaf", "frontend", "template", 0.9, file_fact.evidence)
            if "bootstrap" in source.lower():
                _add(detected, "bootstrap", "frontend", "template", 0.75, file_fact.evidence)
            if "tailwind" in source.lower():
                _add(detected, "tailwind", "frontend", "template", 0.75, file_fact.evidence)
        if name in {"build.gradle", "build.gradle.kts"}:
            source = _read_text(root / file_fact.path)
            if "com.android.application" in source or "com.android.library" in source:
                _add(detected, "android", "mobile", "gradle", 0.9, file_fact.evidence)
            if "org.jetbrains.kotlin.android" in source or "kotlin(\"android\")" in source:
                _add(detected, "android", "mobile", "gradle", 0.85, file_fact.evidence)
            if "androidx.compose" in source or "composeOptions" in source:
                _add(detected, "jetpack-compose", "mobile", "gradle", 0.8, file_fact.evidence)
            if "androidx.room" in source or "room-runtime" in source or "room-ktx" in source:
                _add(detected, "room", "data", "gradle", 0.85, file_fact.evidence)

    pom_path = root / "pom.xml"
    if pom_path.exists() and "<packaging>war</packaging>" in _read_text(pom_path):
        _add(
            detected,
            "java-web",
            "backend",
            "packaging",
            0.85,
            Evidence(file="pom.xml", kind="framework", note="Maven packaging is war"),
        )

    for import_fact in imports:
        if roles_by_path.get(import_fact.path) in {"documentation", "generated", "sample", "test"}:
            continue
        module = (import_fact.module or "").lower()
        if module.startswith("react"):
            _add(detected, "react", "frontend", "import", 0.85, import_fact.evidence)
        if module == "react-native" or module.startswith("react-native-") or module.startswith("@react-native/"):
            _add(detected, "react-native", "mobile", "import", 0.85, import_fact.evidence)
        if module == "expo" or module.startswith("expo-") or module.startswith("@expo/"):
            _add(detected, "expo", "mobile", "import", 0.85, import_fact.evidence)
        if module == "@react-navigation/native" or module.startswith("@react-navigation/"):
            _add(detected, "react-navigation", "mobile", "import", 0.85, import_fact.evidence)
        if module.startswith("@ionic/") or module == "ionic-angular":
            _add(detected, "ionic", "frontend", "import", 0.85, import_fact.evidence)
        if module.startswith("@nativescript/") or module.startswith("nativescript-") or module == "tns-core-modules":
            _add(detected, "nativescript", "mobile", "import", 0.85, import_fact.evidence)
        if module.startswith("@angular/"):
            _add(detected, "angular", "frontend", "import", 0.85, import_fact.evidence)
        if module == "next" or module.startswith("next/"):
            _add(detected, "next", "frontend", "import", 0.85, import_fact.evidence)
        if module == "@astrojs/starlight" or module.startswith("@astrojs/starlight/"):
            _add(detected, "starlight", "frontend", "import", 0.9, import_fact.evidence)
        if module == "astro" or module.startswith("astro/"):
            _add(detected, "astro", "frontend", "import", 0.85, import_fact.evidence)
        if module == "nuxt" or module.startswith("#app") or module.startswith("#imports") or module.startswith("@nuxt/"):
            _add(detected, "nuxt", "frontend", "import", 0.85, import_fact.evidence)
        if module == "quasar" or module.startswith("@quasar/"):
            _add(detected, "quasar", "frontend", "import", 0.85, import_fact.evidence)
        if module in {"svelte", "svelte/store"} or module.startswith("svelte/"):
            _add(detected, "svelte", "frontend", "import", 0.85, import_fact.evidence)
        if module == "@sveltejs/kit" or module.startswith("$app/"):
            _add(detected, "sveltekit", "frontend", "import", 0.85, import_fact.evidence)
        if module == "composablearchitecture":
            _add(detected, "tca", "frontend", "import", 0.9, import_fact.evidence)
        if module == "solid-js" or module.startswith("solid-js/"):
            _add(detected, "solid", "frontend", "import", 0.9, import_fact.evidence)
        if module == "@solidjs/router":
            _add(detected, "solid-router", "frontend", "import", 0.9, import_fact.evidence)
        if module == "@solidjs/start" or module.startswith("@solidjs/start/") or module.startswith("solid-start"):
            _add(detected, "solid-start", "frontend", "import", 0.9, import_fact.evidence)
        if module.startswith("vue"):
            _add(detected, "vue", "frontend", "import", 0.85, import_fact.evidence)
        if module.startswith("@ember/") or module.startswith("@glimmer/"):
            _add(detected, "ember", "frontend", "import", 0.85, import_fact.evidence)
        if module.startswith("microsoft.aspnetcore.blazor") or module.startswith("microsoft.aspnetcore.components"):
            _add(detected, "blazor", "frontend", "import", 0.85, import_fact.evidence)
        if module.startswith("react-router") or module == "@remix-run/router":
            _add(detected, "react-router", "frontend", "import", 0.85, import_fact.evidence)
        if module.startswith("@redwoodjs/"):
            _add(detected, "redwood", "frontend", "import", 0.9, import_fact.evidence)
            _add(detected, "redwood", "backend", "import", 0.85, import_fact.evidence)
        if _is_remix_package(module):
            _add(detected, "remix", "frontend", "import", 0.9, import_fact.evidence)
        if module in {"@tanstack/react-query", "react-query"}:
            _add(detected, "tanstack-query", "frontend", "import", 0.9, import_fact.evidence)
        if module in {"@tanstack/react-router", "@tanstack/solid-router", "@tanstack/vue-router", "@tanstack/router-core"}:
            _add(detected, "tanstack-router", "frontend", "import", 0.9, import_fact.evidence)
        if module in {"@tanstack/start", "@tanstack/react-start", "@tanstack/solid-start", "@tanstack/vue-start"} or module.startswith("@tanstack/start-"):
            _add(detected, "tanstack-start", "frontend", "import", 0.9, import_fact.evidence)
        if module.startswith("@trpc/"):
            _add(detected, "trpc", "frontend", "import", 0.9, import_fact.evidence)
        if module == "vue-router":
            _add(detected, "vue-router", "frontend", "import", 0.85, import_fact.evidence)
        if module in {"redux", "react-redux", "@reduxjs/toolkit"} or module.startswith("@reduxjs"):
            _add(detected, "redux", "frontend", "import", 0.85, import_fact.evidence)
        if module == "zustand":
            _add(detected, "zustand", "frontend", "import", 0.85, import_fact.evidence)
        if module == "pinia":
            _add(detected, "pinia", "frontend", "import", 0.85, import_fact.evidence)
        if module == "express":
            _add(detected, "express", "backend", "import", 0.85, import_fact.evidence)
        if module == "@adonisjs/core" or module.startswith("@ioc:Adonis/Core"):
            _add(detected, "adonisjs", "backend", "import", 0.85, import_fact.evidence)
        if module == "@adonisjs/lucid" or module.startswith("@ioc:Adonis/Lucid"):
            _add(detected, "adonis-lucid", "data", "import", 0.85, import_fact.evidence)
        if module == "sails" or module.startswith("sails/") or module.startswith("sails-hook-"):
            _add(detected, "sails", "backend", "import", 0.85, import_fact.evidence)
        if module == "waterline" or module == "sails-hook-orm":
            _add(detected, "waterline", "data", "import", 0.85, import_fact.evidence)
        if module in {"hapi", "@hapi/hapi"} or module.startswith("hapi-") or module.startswith("@hapi/"):
            _add(detected, "hapi", "backend", "import", 0.85, import_fact.evidence)
        if module == "koa" or module in {"koa-router", "@koa/router"} or module.startswith("koa-"):
            _add(detected, "koa", "backend", "import", 0.85, import_fact.evidence)
        if module in {"@loopback/rest", "@loopback/core", "@loopback/boot"} or module.startswith("@loopback/authentication") or module.startswith("@loopback/authorization"):
            _add(detected, "loopback", "backend", "import", 0.85, import_fact.evidence)
        if module == "@loopback/repository" or module.startswith("@loopback/repository"):
            _add(detected, "loopback-repository", "data", "import", 0.85, import_fact.evidence)
        if module == "fastify" or module.startswith("@fastify/") or module == "fastify-plugin":
            _add(detected, "fastify", "backend", "import", 0.85, import_fact.evidence)
        if module == "hono" or module.startswith("hono/") or module.startswith("@hono/"):
            _add(detected, "hono", "backend", "import", 0.9, import_fact.evidence)
        if module == "@builder.io/qwik" or module.startswith("@builder.io/qwik/"):
            _add(detected, "qwik", "frontend", "import", 0.9, import_fact.evidence)
        if module == "@builder.io/qwik-city" or module.startswith("@builder.io/qwik-city/"):
            _add(detected, "qwik-city", "frontend", "import", 0.9, import_fact.evidence)
            _add(detected, "qwik-city", "backend", "import", 0.85, import_fact.evidence)
        if module == "elysia" or module.startswith("elysia/") or module.startswith("@elysiajs/"):
            _add(detected, "elysia", "backend", "import", 0.9, import_fact.evidence)
        if module == "fresh" or module.startswith("fresh/") or module.startswith("@fresh/"):
            _add(detected, "fresh", "frontend", "import", 0.9, import_fact.evidence)
            _add(detected, "fresh", "backend", "import", 0.9, import_fact.evidence)
        if module.startswith("@feathersjs/") or module.startswith("feathers-") or module == "feathers":
            _add(detected, "feathers", "backend", "import", 0.85, import_fact.evidence)
        if module == "feathers-mongoose":
            _add(detected, "feathers-mongoose", "data", "import", 0.85, import_fact.evidence)
        if module == "feathers-nedb":
            _add(detected, "feathers-nedb", "data", "import", 0.85, import_fact.evidence)
        if module == "@strapi/strapi" or module.startswith("@strapi/") or module.startswith("strapi-plugin"):
            _add(detected, "strapi", "backend", "import", 0.85, import_fact.evidence)
        if module == "mongoose" or module.startswith("mongoose-"):
            _add(detected, "mongoose", "data", "import", 0.85, import_fact.evidence)
        if module == "sequelize" or module.startswith("sequelize-"):
            _add(detected, "sequelize", "data", "import", 0.85, import_fact.evidence)
        if module == "@prisma/client" or module.startswith("@prisma/"):
            _add(detected, "prisma", "data", "import", 0.85, import_fact.evidence)
        if module == "electron" or module.startswith("electron/"):
            _add(detected, "electron", "desktop", "import", 0.85, import_fact.evidence)
        if module.startswith("@tauri-apps/"):
            _add(detected, "tauri", "desktop", "import", 0.85, import_fact.evidence)
        if module in {"graphql", "express-graphql"} or module.startswith("@apollo/"):
            _add(detected, "graphql", "backend", "import", 0.85, import_fact.evidence)
        if module in {"socket.io", "socket.io-client", "flask_socketio"}:
            _add(detected, "socketio", "backend", "import", 0.9, import_fact.evidence)
        if module in {"grpc", "grpcio"} or module.startswith("@grpc/") or "google.golang.org/grpc" in module:
            _add(detected, "grpc", "backend", "import", 0.9, import_fact.evidence)
        if module.startswith("@nestjs/"):
            _add(detected, "nestjs", "backend", "import", 0.85, import_fact.evidence)
        if module == "fastapi":
            _add(detected, "fastapi", "backend", "import", 0.85, import_fact.evidence)
        if module == "flask":
            _add(detected, "flask", "backend", "import", 0.85, import_fact.evidence)
        if module == "celery" or module.startswith("celery."):
            _add(detected, "celery", "backend", "import", 0.9, import_fact.evidence)
        if "gin-gonic/gin" in module:
            _add(detected, "gin", "backend", "import", 0.85, import_fact.evidence)
        if "labstack/echo" in module:
            _add(detected, "echo", "backend", "import", 0.85, import_fact.evidence)
        if "gofiber/fiber" in module:
            _add(detected, "fiber", "backend", "import", 0.85, import_fact.evidence)
        if "go-chi/chi" in module:
            _add(detected, "chi", "backend", "import", 0.85, import_fact.evidence)
        if module == "axum" or module.startswith("axum::"):
            _add(detected, "axum", "backend", "import", 0.85, import_fact.evidence)
        if module == "actix_web" or module.startswith("actix_web::"):
            _add(detected, "actix-web", "backend", "import", 0.85, import_fact.evidence)
        if module == "rocket" or module.startswith("rocket::"):
            _add(detected, "rocket", "backend", "import", 0.85, import_fact.evidence)
        if module == "warp" or module.startswith("warp::"):
            _add(detected, "warp", "backend", "import", 0.85, import_fact.evidence)
        if module.startswith("laravel\\"):
            _add(detected, "laravel", "backend", "import", 0.85, import_fact.evidence)
        if module.startswith("illuminate\\"):
            _add(detected, "illuminate", "backend", "import", 0.85, import_fact.evidence)
        if module.startswith("phoenix."):
            _add(detected, "phoenix", "backend", "import", 0.85, import_fact.evidence)
        if module.startswith("microsoft.aspnetcore"):
            _add(detected, "aspnetcore", "backend", "import", 0.85, import_fact.evidence)
        if module.startswith("microsoft.entityframeworkcore"):
            _add(detected, "ef-core", "data", "import", 0.85, import_fact.evidence)
        if module in {"django", "django.urls", "rest_framework"} or module.startswith("django."):
            _add(detected, "django", "backend", "import", 0.85, import_fact.evidence)
        if module == "rest_framework" or module.startswith("rest_framework."):
            _add(detected, "drf", "backend", "import", 0.85, import_fact.evidence)
        if module == "ninja" or module.startswith("ninja."):
            _add(detected, "django-ninja", "backend", "import", 0.85, import_fact.evidence)
        if (
            module.startswith("symfony\\component\\routing") or module.startswith("symfony\\bundle\\frameworkbundle")
        ) and _looks_like_symfony_project_path(import_fact.path):
            _add(detected, "symfony", "backend", "import", 0.85, import_fact.evidence)
        if module.startswith("drupal\\") or module.startswith("drupal."):
            _add(detected, "drupal", "backend", "import", 0.85, import_fact.evidence)
        if module.startswith("compojure."):
            _add(detected, "compojure", "backend", "import", 0.85, import_fact.evidence)
        if module.startswith("ring."):
            _add(detected, "clojure-ring", "backend", "import", 0.85, import_fact.evidence)
        if module.startswith("reitit."):
            _add(detected, "reitit", "backend", "import", 0.85, import_fact.evidence)
        if module.startswith("selmer."):
            _add(detected, "selmer", "frontend", "import", 0.85, import_fact.evidence)
        if module.startswith("next.jdbc"):
            _add(detected, "next.jdbc", "data", "import", 0.85, import_fact.evidence)
        if module.startswith("com.stuartsierra.component"):
            _add(detected, "stuartsierra-component", "runtime", "import", 0.85, import_fact.evidence)
        if module.startswith("org.springframework"):
            _add(detected, "spring", "backend", "import", 0.85, import_fact.evidence)
        if module.startswith(("jakarta.persistence", "javax.persistence", "org.springframework.data.jpa")):
            _add(detected, "jpa", "data", "import", 0.85, import_fact.evidence)
        if module.startswith("org.hibernate"):
            _add(detected, "hibernate", "data", "import", 0.85, import_fact.evidence)
        if module.startswith(("play.api", "play.mvc", "play.libs", "play.routing")):
            _add(detected, "playframework", "backend", "import", 0.85, import_fact.evidence)
        if module.startswith(("io.ktor.server", "io.ktor.application", "io.ktor.routing")):
            _add(detected, "ktor", "backend", "import", 0.85, import_fact.evidence)
        if module.startswith("anorm"):
            _add(detected, "anorm", "data", "import", 0.85, import_fact.evidence)
        if module.startswith("slick."):
            _add(detected, "play-slick", "data", "import", 0.85, import_fact.evidence)
        if module.startswith("androidx."):
            _add(detected, "android", "mobile", "import", 0.8, import_fact.evidence)
        if module.startswith("androidx.room"):
            _add(detected, "room", "data", "import", 0.85, import_fact.evidence)
        if module.startswith("androidx.compose"):
            _add(detected, "jetpack-compose", "mobile", "import", 0.85, import_fact.evidence)
        if module.startswith("airflow"):
            _add(detected, "airflow", "workflow", "import", 0.9, import_fact.evidence)
        if module.startswith("prefect"):
            _add(detected, "prefect", "workflow", "import", 0.9, import_fact.evidence)
        if module.startswith("dagster"):
            _add(detected, "dagster", "workflow", "import", 0.9, import_fact.evidence)
        if module.startswith("kedro"):
            _add(detected, "kedro", "data", "import", 0.85, import_fact.evidence)
        if module.startswith("great_expectations"):
            _add(detected, "great-expectations", "data-quality", "import", 0.9, import_fact.evidence)
        if module.startswith("pyspark"):
            _add(detected, "pyspark", "data", "import", 0.9, import_fact.evidence)
        if module.startswith("delta") or module.startswith("deltalake"):
            _add(detected, "delta-lake", "data", "import", 0.85, import_fact.evidence)
        if module.startswith(("notebook", "jupyter", "IPython".lower())):
            _add(detected, "jupyter-notebook", "notebook", "import", 0.75, import_fact.evidence)
        if module == "pulumi" or module.startswith("pulumi_") or module.startswith("@pulumi/"):
            _add(detected, "pulumi", "runtime", "import", 0.9, import_fact.evidence)
        if module in {"bun", "bun-types", "@types/bun"}:
            _add(detected, "bun", "runtime", "import", 0.85, import_fact.evidence)
        if module in {"torch", "torchvision", "torchaudio"} or module.startswith(("torch.", "torchvision.", "torchaudio.")):
            _add(detected, "pytorch", "ml", "import", 0.9, import_fact.evidence)
        if module in {"lightning", "pytorch_lightning"} or module.startswith(("lightning.", "pytorch_lightning.")):
            _add(detected, "pytorch-lightning", "ml", "import", 0.9, import_fact.evidence)
        if module == "tensorflow" or module.startswith("tensorflow."):
            _add(detected, "tensorflow", "ml", "import", 0.9, import_fact.evidence)
        if module == "keras" or module.startswith("keras."):
            _add(detected, "keras", "ml", "import", 0.85, import_fact.evidence)
        if module == "sklearn" or module.startswith("sklearn."):
            _add(detected, "scikit-learn", "ml", "import", 0.9, import_fact.evidence)
        if module in {"transformers", "sentence_transformers"} or module.startswith(("transformers.", "sentence_transformers.")):
            _add(detected, "transformers", "ml", "import", 0.9, import_fact.evidence)
        if module == "mlflow" or module.startswith("mlflow."):
            _add(detected, "mlflow", "mlops", "import", 0.9, import_fact.evidence)
        if module == "wandb" or module.startswith("wandb."):
            _add(detected, "wandb", "mlops", "import", 0.9, import_fact.evidence)
        if module == "hydra" or module.startswith("hydra.") or module == "omegaconf" or module.startswith("omegaconf."):
            _add(detected, "hydra", "config", "import", 0.85, import_fact.evidence)
        if module == "streamlit" or module.startswith("streamlit."):
            _add(detected, "streamlit", "frontend", "import", 0.9, import_fact.evidence)
        if module == "gradio" or module.startswith("gradio."):
            _add(detected, "gradio", "frontend", "import", 0.9, import_fact.evidence)

    return sorted(detected.values(), key=lambda item: (item.category, item.name, item.source))


def _looks_like_next_route_path(path: str) -> bool:
    if not path.endswith((".tsx", ".ts", ".jsx", ".js")):
        return False
    name = Path(path).name
    if _has_next_app_dir(path):
        return name in {
            "error.js",
            "error.jsx",
            "error.ts",
            "error.tsx",
            "layout.js",
            "layout.jsx",
            "layout.ts",
            "layout.tsx",
            "loading.js",
            "loading.jsx",
            "loading.ts",
            "loading.tsx",
            "page.js",
            "page.jsx",
            "page.ts",
            "page.tsx",
            "route.js",
            "route.ts",
        }
    if _has_next_pages_dir(path):
        return not name.startswith("_")
    return False


def _has_next_app_dir(path: str) -> bool:
    parts = path.split("/")
    if "app" not in parts:
        return False
    index = parts.index("app")
    prefix = parts[:index]
    if prefix in ([], ["src"]):
        return True
    if len(prefix) >= 2 and prefix[-2] in {"apps", "packages"}:
        return True
    if len(prefix) >= 3 and prefix[-3] in {"apps", "packages"} and prefix[-1] == "src":
        return True
    return False


def _has_next_pages_dir(path: str) -> bool:
    parts = path.split("/")
    if "pages" not in parts:
        return False
    index = parts.index("pages")
    prefix = parts[:index]
    if prefix in ([], ["src"]):
        return True
    if len(prefix) >= 2 and prefix[-2] in {"apps", "packages"}:
        return True
    if len(prefix) >= 3 and prefix[-3] in {"apps", "packages"} and prefix[-1] == "src":
        return True
    return False


def _looks_like_thymeleaf(source: str) -> bool:
    return "xmlns:th=" in source or bool(re.search(r"\bth:[A-Za-z0-9_-]+\s*=", source))


def _looks_like_spring_config_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    name = Path(normalized).name
    if name not in {"application.properties", "application.yml", "application.yaml"}:
        return False
    return (
        "/" not in normalized
        or normalized.startswith("config/")
        or normalized.startswith("src/main/resources/")
        or "/src/main/resources/" in f"/{normalized}"
    )


def _looks_like_ktor_config(path: Path) -> bool:
    source = _read_text(path)
    lowered = source.lower()
    return "ktor" in lowered and ("application" in lowered or "deployment" in lowered or "modules" in lowered)


def _looks_like_dbt_config_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    name = Path(normalized).name
    if name in {"dbt_project.yml", "dbt_project.yaml"}:
        return True
    if name not in {"packages.yml", "packages.yaml", "profiles.yml", "profiles.yaml"}:
        return False
    return (
        "/" not in normalized
        or normalized.startswith("dbt/")
        or "/dbt/" in f"/{normalized}"
    )


def _looks_like_ember_source(path: Path) -> bool:
    source = _read_text(path)
    lower = source.lower()
    return (
        "@ember/" in lower
        or "@glimmer/" in lower
        or "emberrouter" in lower
        or "router.map" in lower
    )


def _looks_like_spring_source(path: Path) -> bool:
    source = _read_text(path)
    return (
        "org.springframework" in source
        or "@SpringBootApplication" in source
        or "@RestController" in source
        or "@Controller" in source
        or "@RequestMapping" in source
    )


def _looks_like_jpa_source(path: Path) -> bool:
    source = _read_text(path)
    return (
        "jakarta.persistence" in source
        or "javax.persistence" in source
        or "org.springframework.data.jpa" in source
        or "JpaRepository" in source
        or "spring.jpa." in source
    )


def _looks_like_room_source(path: Path) -> bool:
    source = _read_text(path)
    return (
        "androidx.room" in source
        or 'id("androidx.room")' in source
        or 'id = "androidx.room"' in source
        or "room-runtime" in source
        or "room-ktx" in source
        or "room-compiler" in source
    )


def _looks_like_hibernate_source(path: Path) -> bool:
    source = _read_text(path)
    return (
        "org.hibernate" in source
        or "spring.jpa.hibernate" in source
        or "hibernate." in source
    )


def _looks_like_aspnet_project_file(path: Path) -> bool:
    source = _read_text(path).lower()
    return (
        "microsoft.net.sdk.web" in source
        or "microsoft.aspnetcore" in source
        or "aspnetcore" in source
    )


def _looks_like_aspnet_source(path: Path) -> bool:
    source = _read_text(path)
    return (
        "Microsoft.AspNetCore" in source
        or "WebApplication.CreateBuilder" in source
        or "IApplicationBuilder" in source
        or "IWebHostEnvironment" in source
        or re.search(r"\bapp\.Map(?:Get|Post|Put|Delete|Patch|Controllers|RazorPages)\s*\(", source) is not None
        or re.search(r"\bapp\.Use(?:Routing|Endpoints|Authentication|Authorization)\s*\(", source) is not None
    )


def _looks_like_ios_plist_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    if not normalized.endswith(".plist"):
        return False
    if normalized.endswith(("entitlements.mac.plist", "entitlements.mas.plist", "entitlements.mac.inherit.plist")):
        return False
    return (
        normalized.startswith("ios/")
        or "/ios/" in f"/{normalized}"
        or normalized.startswith("platforms/ios/")
        or "/platforms/ios/" in f"/{normalized}"
        or normalized.startswith("runner/")
        or ".xcodeproj/" in normalized
        or ".xcworkspace/" in normalized
    )


def _looks_like_maui_project_file(path: Path) -> bool:
    source = _read_text(path).lower()
    return (
        "<usemaui>true</usemaui>" in source
        or "microsoft.maui" in source
        or "net8.0-android" in source
        or "net9.0-android" in source
        or "net10.0-android" in source
        or "maccatalyst" in source
    )


def _looks_like_wpf_project_file(path: Path) -> bool:
    source = _read_text(path).lower()
    return (
        "<usewpf>true</usewpf>" in source
        or "microsoft.net.sdk.windowsdesktop" in source and "wpf" in source
        or "presentationframework" in source
    )


def _looks_like_maui_xaml(path: Path) -> bool:
    source = _read_text(path)
    return "schemas.microsoft.com/dotnet/2021/maui" in source or "<ContentPage" in source or "<Shell" in source or "MauiWinUIApplication" in source


def _looks_like_wpf_xaml(path: Path) -> bool:
    source = _read_text(path)
    return (
        "schemas.microsoft.com/winfx/2006/xaml/presentation" in source
        and not _looks_like_maui_xaml(path)
        and not _looks_like_avalonia_source(path)
    )


def _looks_like_avalonia_source(path: Path) -> bool:
    source = _read_text(path).lower()
    return (
        "avalonia" in source
        or "github.com/avaloniaui" in source
        or path.suffix.lower() == ".axaml"
    )


def _looks_like_swiftui_source(path: Path) -> bool:
    source = _read_text(path)
    return "import SwiftUI" in source or re.search(r"\bstruct\s+\w+\s*:\s*View\b", source) is not None


def _looks_like_vapor_source(path: Path) -> bool:
    source = _read_text(path)
    return "import Vapor" in source or "Application(" in source and "Request" in source


def _looks_like_fluent_source(path: Path) -> bool:
    source = _read_text(path)
    return "import Fluent" in source or "FluentKit" in source or re.search(r"\bclass\s+\w+\s*:\s*Model\b", source) is not None


def _looks_like_react_native_source(path: Path) -> bool:
    source = _read_text(path)
    return (
        "from 'react-native'" in source
        or 'from "react-native"' in source
        or "require('react-native')" in source
        or 'require("react-native")' in source
        or "react-native/" in source
        or "from 'expo" in source
        or 'from "expo' in source
        or "expo-router" in source
        or re.search(r"\b(AppRegistry|StyleSheet|View|Text)\b", source) is not None and "from 'react-native'" in source
    )


def _looks_like_redwood_web_source(path: Path) -> bool:
    source = _read_text(path)
    normalized = path.as_posix().lower()
    return (
        "@redwoodjs/router" in source
        or "@redwoodjs/web" in source
        or "/web/src/" in f"/{normalized}" and ("gql`" in source or "from '@redwoodjs/" in source or 'from "@redwoodjs/' in source)
    )


def _looks_like_redwood_api_source(path: Path) -> bool:
    source = _read_text(path)
    normalized = path.as_posix().lower()
    return (
        "@redwoodjs/graphql-server" in source
        or "@redwoodjs/api" in source
        or "/api/src/graphql/" in f"/{normalized}"
        or "/api/src/services/" in f"/{normalized}"
    )


def _looks_like_expo_source(path: Path) -> bool:
    source = _read_text(path)
    return "expo-router" in source or "from 'expo" in source or 'from "expo' in source or "registerRootComponent" in source


def _looks_like_django_project_file(path: Path, lower: str, name: str) -> bool:
    if name == "manage.py":
        source = _read_text(path)
        return "DJANGO_SETTINGS_MODULE" in source or "django.core.management" in source
    if not (name == "settings.py" or lower.endswith("urls.py")):
        return False
    source = _read_text(path)
    if name == "settings.py":
        return any(
            marker in source
            for marker in (
                "INSTALLED_APPS",
                "MIDDLEWARE",
                "ROOT_URLCONF",
                "DJANGO_SETTINGS_MODULE",
                "django.contrib",
            )
        )
    return "urlpatterns" in source and ("django.urls" in source or "django.conf.urls" in source or "path(" in source)


def _looks_like_electron_source(path: Path) -> bool:
    source = _read_text(path)
    return "from 'electron'" in source or 'from "electron"' in source or "require('electron')" in source or 'require("electron")' in source


def _looks_like_wordpress_source(path: Path) -> bool:
    source = _read_text(path)
    lower = source.lower()
    return (
        "plugin name:" in lower
        or "add_action(" in lower
        or "add_filter(" in lower
        or "register_rest_route(" in lower
        or "wp_enqueue_script(" in lower
        or "wp_insert_post(" in lower
    )


def _looks_like_yii_source(path: Path) -> bool:
    source = _read_text(path)
    lower = source.lower()
    return (
        "yii\\rest\\urlrule" in lower
        or "urlrule::class" in lower and "yii\\rest\\urlrule" in lower
        or "yii\\web\\application" in lower
        or "yii\\base\\module" in lower
        or "extends \\yii\\rest\\" in lower
        or "extends yii\\rest\\" in lower
    )


def _looks_like_slim_php_source(path: Path) -> bool:
    source = _read_text(path)
    lower = source.lower()
    return (
        "slim\\app" in lower
        or "slim\\factory\\appfactory" in lower
        or "slim\\http\\request" in lower
        or "slim\\psr7" in lower
        or re.search(r"\$(?:app|this)->(?:group|get|post|put|patch|delete|options|any|map)\s*\(", source) is not None
        and "slim" in lower
    )


def _looks_like_sinatra_rack_source(path: Path) -> bool:
    source = _read_text(path)
    return "sinatra" in source.lower() and re.search(r"\brun\s+(?:Sinatra::Application|[A-Za-z_]\w*)", source) is not None


def _looks_like_sinatra_ruby_source(path: Path) -> bool:
    normalized = str(path).replace("\\", "/").lower()
    if normalized.endswith("/config/routes.rb") or "/config/routes/" in normalized:
        return False
    source = _read_text(path)
    lower = source.lower()
    if "grape::api" in lower:
        return False
    return (
        "require 'sinatra" in lower
        or 'require "sinatra' in lower
        or "sinatra::base" in lower
        or "sinatra::application" in lower
        or re.search(r"(?m)^\s*(?:get|post|put|patch|delete|options|head)\s+['\"]/", source) is not None
    )


def _looks_like_grape_ruby_source(path: Path) -> bool:
    source = _read_text(path)
    lower = source.lower()
    return (
        "grape::api" in lower
        or "require 'grape" in lower
        or 'require "grape' in lower
        or re.search(r"(?m)^\s*mount\s+::?[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*", source) is not None
    )


def _looks_like_drupal_source(path: Path) -> bool:
    source = _read_text(path)
    lower = source.lower()
    normalized = path.as_posix().lower()
    return (
        "\\drupal\\" in source
        or "drupal::" in lower
        or path.name.endswith((".module", ".install", ".theme"))
        or normalized.endswith((".routing.yml", ".routing.yaml", ".services.yml", ".services.yaml"))
    )


def _looks_like_openapi_spec_path(path: str, source_path: Path) -> bool:
    name = Path(path).name.lower()
    if not name.endswith((".json", ".yaml", ".yml")):
        return False
    if any(marker in name for marker in ("openapi", "swagger")):
        return True
    source = _read_text(source_path)[:5000]
    return bool(re.search(r"^\s*['\"]?(openapi|swagger)['\"]?\s*[:\"]", source, re.MULTILINE))


def _looks_like_kubernetes_manifest(path: Path) -> bool:
    source = _read_text(path)[:6000]
    return bool(
        re.search(r"^\s*apiVersion\s*:", source, re.MULTILINE)
        and re.search(r"^\s*kind\s*:\s*[A-Za-z]", source, re.MULTILINE)
    )


def _looks_like_tanstack_query_source(path: Path) -> bool:
    source = _read_text(path)
    return "@tanstack/react-query" in source or "react-query" in source or re.search(r"\buse(Query|Mutation|Queries)\s*\(", source) is not None


def _looks_like_tanstack_router_source(path: Path) -> bool:
    source = _read_text(path)
    return (
        "@tanstack/react-router" in source
        or "@tanstack/solid-router" in source
        or "@tanstack/vue-router" in source
        or "@tanstack/router-core" in source
        or re.search(r"\bcreate(?:Lazy)?FileRoute\s*\(\s*['\"`]/", source) is not None
    )


def _looks_like_tanstack_start_source(path: Path) -> bool:
    source = _read_text(path)
    return (
        "@tanstack/start" in source
        or "@tanstack/react-start" in source
        or "@tanstack/solid-start" in source
        or "@tanstack/vue-start" in source
        or "@tanstack/start-" in source
        or re.search(r"\bcreateServerFn\s*\(", source) is not None
    )


def _looks_like_trpc_source(path: Path) -> bool:
    source = _read_text(path)
    return (
        "@trpc/" in source
        or "createTRPCRouter" in source
        or "initTRPC" in source
        or re.search(r"\b(publicProcedure|protectedProcedure|t\.procedure)\b", source) is not None
    )


def _looks_like_nestjs_source(path: Path) -> bool:
    source = _read_text(path)
    return "@nestjs/" in source or "@Controller" in source or "@Module" in source or "NestFactory" in source


def _looks_like_fastify_source(path: Path) -> bool:
    source = _read_text(path)
    return (
        "from 'fastify'" in source
        or 'from "fastify"' in source
        or "require('fastify')" in source
        or 'require("fastify")' in source
        or "@fastify/" in source
        or "fastify-plugin" in source
        or re.search(r"\bfastify\.(?:route|get|post|put|delete|patch|options|head|all|register)\s*\(", source, re.IGNORECASE) is not None
    )


def _looks_like_hono_source(path: Path) -> bool:
    source = _read_text(path)
    return (
        "from 'hono'" in source
        or 'from "hono"' in source
        or "new Hono" in source
        or "new OpenAPIHono" in source
        or "OpenAPIHono" in source
        or "AppOpenAPI" in source
        or "createRoute(" in source
        or "@hono/" in source
        or ("Hono" in source and re.search(r"\b[A-Za-z_$][\w$]*\.(?:get|post|put|delete|patch|all|route)\s*\(", source) is not None)
    )


def _looks_like_elysia_source(path: Path) -> bool:
    source = _read_text(path)
    return (
        "from 'elysia'" in source
        or 'from "elysia"' in source
        or "new Elysia" in source
        or ("Elysia" in source and re.search(r"\.[A-Za-z_$]?(?:get|post|put|delete|patch|all)\s*\(\s*['\"`]/", source) is not None)
    )


def _looks_like_fresh_source(path: Path) -> bool:
    source = _read_text(path)
    return (
        "from 'fresh'" in source
        or 'from "fresh"' in source
        or 'from "$fresh/' in source
        or 'from "$fresh' in source
        or "define.handlers" in source
        or ".fsRoutes()" in source
    )


def _looks_like_qwik_source(path: Path) -> bool:
    source = _read_text(path)
    return (
        "@builder.io/qwik" in source
        or "component$(" in source
        or "useSignal(" in source
        or "useTask$(" in source
        or "useVisibleTask$(" in source
    )


def _looks_like_qwik_city_source(path: Path) -> bool:
    source = _read_text(path)
    normalized = path.as_posix().lower()
    return (
        "@builder.io/qwik-city" in source
        or "qwikCity(" in source
        or (
            "/src/routes/" in f"/{normalized}"
            and (
                "component$(" in source
                or re.search(r"\b(?:routeLoader|routeAction|globalAction|server)\$\s*\(", source) is not None
                or re.search(r"\bexport\s+const\s+on(?:Request|Get|Post|Put|Delete|Patch|Head|Options)\b", source) is not None
            )
        )
    )


def _looks_like_solid_source(path: Path) -> bool:
    source = _read_text(path)
    if "solid-js" in source:
        return True
    if _looks_like_react_source_text(source):
        return False
    return re.search(r"\b(createSignal|createMemo|createResource|createEffect)\s*\(", source) is not None


def _looks_like_react_source_text(source: str) -> bool:
    return (
        re.search(r"\bfrom\s+['\"]react['\"]", source) is not None
        or re.search(r"\bfrom\s+['\"]react/", source) is not None
        or re.search(r"\brequire\(\s*['\"]react['\"]\s*\)", source) is not None
        or "React." in source
    )


def _looks_like_solid_router_source(path: Path) -> bool:
    source = _read_text(path)
    return (
        "@solidjs/router" in source
    )


def _looks_like_solid_start_source(path: Path) -> bool:
    source = _read_text(path)
    normalized = path.as_posix().lower()
    return (
        "@solidjs/start" in source
        or "FileRoutes" in source and ("solid-js" in source or "@solidjs/router" in source)
        or "/src/routes/" in f"/{normalized}" and ("solid-js" in source or "@solidjs/router" in source)
    )


def _looks_like_feathers_source(path: Path) -> bool:
    source = _read_text(path)
    normalized = path.as_posix().lower()
    return (
        "@feathersjs/" in source
        or "feathers-mongoose" in source
        or "feathers-nedb" in source
        or "/services/" in f"/{normalized}" and "app.use(" in source and "service.hooks" in source
    )


def _looks_like_loopback_source(path: Path) -> bool:
    source = _read_text(path)
    return (
        "@loopback/rest" in source
        or "@loopback/core" in source
        or "@loopback/repository" in source
        or (
            re.search(r"@\s*(?:get|post|put|patch|del|delete|head|options)\s*\(", source) is not None
            and "getModelSchemaRef" in source
        )
    )


def _looks_like_socketio_source(path: Path) -> bool:
    source = _read_text(path)
    return (
        "socket.io" in source
        or "SocketIO" in source
        or "flask_socketio" in source
        or re.search(r"\bsocketio\s*\(", source) is not None
        or re.search(r"\bio\.on\(\s*['\"](?:connect|connection)", source) is not None
    )


def _looks_like_authjs_source(path: Path) -> bool:
    source = _read_text(path)
    return "from 'auth'" in source or 'from "auth"' in source or "@auth/" in source


def _looks_like_nextauth_source(path: Path) -> bool:
    source = _read_text(path)
    return "next-auth" in source or "NextAuth(" in source or "getServerSession" in source or "authOptions" in source


def _looks_like_passport_source(path: Path) -> bool:
    source = _read_text(path)
    return "passport" in source or "@nestjs/passport" in source or "AuthGuard(" in source


def _looks_like_jwt_source(path: Path) -> bool:
    source = _read_text(path)
    lower = source.lower()
    suffix = path.suffix.lower()
    return (
        "jsonwebtoken" in lower
        or "jwtservice" in source
        or "jwtbearer" in lower
        or "jwt_" in lower
        or (suffix == ".py" and "simplejwt" in lower)
        or "jwt.encode" in lower
        or "jwt.decode" in lower
        or "jwt.sign" in lower
        or "jwt.verify" in lower
        or "io.jsonwebtoken" in lower
        or "jwts." in lower
        or "jwtauthentication" in source.lower()
        or "bearer token" in lower
        or re.search(r"^(?:import|from)\s+jwt\b", source, re.MULTILINE) is not None
    )


def _looks_like_bcrypt_source(path: Path) -> bool:
    source = _read_text(path)
    lower = source.lower()
    return "bcrypt" in lower or "passwordencoder" in lower or "password_hash" in lower or "passlib" in lower


def _looks_like_spring_security_source(path: Path) -> bool:
    source = _read_text(path)
    return (
        "springframework.security" in source
        or "@EnableWebSecurity" in source
        or "SecurityFilterChain" in source
        or "OncePerRequestFilter" in source
        or "UserDetailsService" in source
    )


def _looks_like_django_simplejwt_source(path: Path) -> bool:
    source = _read_text(path)
    return "rest_framework_simplejwt" in source or "SIMPLE_JWT" in source or "JWTAuthentication" in source


def _looks_like_fastapi_security_source(path: Path) -> bool:
    source = _read_text(path)
    return (
        "OAuth2PasswordBearer" in source
        or "OAuth2PasswordRequestForm" in source
        or "HTTPBearer" in source
        or "fastapi_jwt_auth" in source
    )


def _looks_like_aspnet_jwt_source(path: Path) -> bool:
    source = _read_text(path)
    return (
        "JwtBearer" in source
        or "AddAuthentication" in source and "Bearer" in source
        or "Microsoft.AspNetCore.Authentication.JwtBearer" in source
    )


def _looks_like_websocket_source(path: Path) -> bool:
    source = _read_text(path)
    if "socket.io" in source or "socket.io-client" in source:
        return False
    return (
        "WebSocketServer" in source
        or "WebSocket.Server" in source
        or "require('ws')" in source
        or 'require("ws")' in source
        or "from 'ws'" in source
        or 'from "ws"' in source
        or re.search(r"\bnew\s+WebSocket\s*\(", source) is not None
        or re.search(r"\bwss?\.on\(\s*['\"](?:connection|message)", source) is not None
    )


def _looks_like_sse_source(path: Path) -> bool:
    source = _read_text(path)
    return (
        "text/event-stream" in source
        or "EventSource(" in source
        or "new EventSource" in source
        or "getEventStream(" in source
        or "publishEvent(" in source
    )


def _looks_like_eventsource_source(path: Path) -> bool:
    source = _read_text(path)
    return "EventSource(" in source or "new EventSource" in source


def _looks_like_kafka_source(path: Path) -> bool:
    source = _read_text(path)
    lower = source.lower()
    return (
        "kafkajs" in lower
        or "kafka-node" in lower
        or "node-rdkafka" in lower
        or "new kafka" in lower
        or "kafka.producer" in lower
        or "kafka.consumer" in lower
        or "kafkaclient" in source
    )


def _looks_like_rabbitmq_source(path: Path) -> bool:
    source = _read_text(path)
    lower = source.lower()
    return (
        "amqplib" in lower
        or "rabbitmq" in lower
        or "amqp://" in lower
        or "sendtoqueue" in lower
        or ".consume(" in lower and "assertqueue" in lower
    )


def _looks_like_bullmq_source(path: Path) -> bool:
    source = _read_text(path)
    return "bullmq" in source or "from 'bull'" in source or 'from "bull"' in source or "require('bull')" in source or 'require("bull")' in source


def _looks_like_redis_pubsub_source(path: Path) -> bool:
    source = _read_text(path)
    lower = source.lower()
    return (
        ("redis" in lower or "ioredis" in lower)
        and (
            re.search(r"\.publish\s*\(", source) is not None
            or re.search(r"\.subscribe\s*\(", source) is not None
            or re.search(r"\.pSubscribe\s*\(", source) is not None
        )
    )


def _looks_like_celery_source(path: Path) -> bool:
    source = _read_text(path)
    return (
        "from celery import" in source
        or "import celery" in source
        or "@shared_task" in source
        or re.search(r"@\w+\.task\s*\(", source) is not None
        or "Celery(" in source
    )


def _looks_like_airflow_source(path: Path) -> bool:
    source = _read_text(path)
    return (
        "from airflow" in source
        or "import airflow" in source
        or "DAG(" in source
        or "@dag" in source
        or "airflow.decorators" in source
    )


def _looks_like_prefect_source(path: Path) -> bool:
    source = _read_text(path)
    return (
        "from prefect" in source
        or "import prefect" in source
        or "@flow" in source
        or "@task" in source and "prefect" in source.lower()
    )


def _looks_like_dagster_source(path: Path) -> bool:
    source = _read_text(path)
    return (
        "from dagster" in source
        or "import dagster" in source
        or "@asset" in source
        or "@op" in source
        or "@job" in source
        or "Definitions(" in source
    )


def _looks_like_kedro_source(path: Path) -> bool:
    source = _read_text(path)
    return (
        "from kedro" in source
        or "import kedro" in source
        or "Pipeline(" in source and "node(" in source
        or "KedroSession" in source
    )


def _looks_like_spark_source(path: Path) -> bool:
    source = _read_text(path)
    return (
        "pyspark" in source
        or "SparkSession" in source
        or ".readStream" in source
        or ".writeStream" in source
    )


def _looks_like_delta_source(path: Path) -> bool:
    source = _read_text(path).lower()
    return "delta.tables" in source or "delta-spark" in source or "deltalake" in source or ".format(\"delta\")" in source or ".format('delta')" in source


def _looks_like_great_expectations_source(path: Path) -> bool:
    source = _read_text(path)
    lower = source.lower()
    return "great_expectations" in source or "great expectations" in lower or "context.sources" in source or "ExpectationSuite" in source


def _looks_like_pulumi_source(path: Path) -> bool:
    source = _read_text(path)
    lower = source.lower()
    return (
        "import pulumi" in lower
        or "from pulumi" in lower
        or "@pulumi/" in source
        or "new pulumi." in lower
        or re.search(r"\bpulumi\.(?:export|Config|Output|ResourceOptions)\b", source) is not None
    )


def _looks_like_opentofu_source(path: Path) -> bool:
    source = _read_text(path).lower()
    return "opentofu" in source or "tofu " in source or "tofu_" in source


def _looks_like_packer_source(path: Path) -> bool:
    lower_path = path.as_posix().lower()
    name = path.name.lower()
    if not (
        name == "packerfile"
        or lower_path.endswith((".pkr.hcl", ".pkr.json"))
        or ("/packer/" in f"/{lower_path}" and lower_path.endswith((".hcl", ".json")))
    ):
        return False
    source = _read_text(path)
    return bool(
        re.search(r"^\s*(?:packer|source|build)\s*{", source, re.MULTILINE)
        or re.search(r"^\s*source\s+\"[^\"]+\"\s+\"[^\"]+\"\s*{", source, re.MULTILINE)
        or re.search(r'"builders"\s*:', source)
        or re.search(r'"provisioners"\s*:', source)
    )


def _looks_like_ansible_path(path: str, source_path: Path) -> bool:
    if not path.endswith((".yml", ".yaml")):
        return False
    parts = path.split("/")
    if any(part in {"tasks", "handlers", "defaults", "vars", "meta", "playbooks", "group_vars", "host_vars"} for part in parts):
        return True
    if "/molecule/" in f"/{path}" or Path(path).name in {"galaxy.yml", "galaxy.yaml", "requirements.yml", "requirements.yaml"}:
        return True
    source = _read_text(source_path)
    return _looks_like_ansible_source(source)


def _looks_like_ansible_source(source: str) -> bool:
    return bool(
        re.search(r"^\s*-\s+hosts\s*:", source, re.MULTILINE)
        or re.search(r"^\s*hosts\s*:", source, re.MULTILINE) and re.search(r"^\s*(?:tasks|roles)\s*:", source, re.MULTILINE)
        or "ansible.builtin." in source
        or re.search(r"^\s*-\s+name\s*:", source, re.MULTILINE) and re.search(r"^\s*(?:apt|yum|dnf|copy|template|service|package|lineinfile|include_tasks|import_tasks|debug)\s*:", source, re.MULTILINE)
    )


def _looks_like_pytorch_source(path: Path) -> bool:
    source = _read_text(path)
    return (
        re.search(r"^(?:import|from)\s+torch\b", source, re.MULTILINE) is not None
        or "torch.nn" in source
        or "nn.Module" in source
        or "DataLoader(" in source and "torch" in source
    )


def _looks_like_lightning_source(path: Path) -> bool:
    source = _read_text(path)
    return (
        "pytorch_lightning" in source
        or "lightning.pytorch" in source
        or "LightningModule" in source
        or "Trainer(" in source and "lightning" in source.lower()
    )


def _looks_like_tensorflow_source(path: Path) -> bool:
    source = _read_text(path)
    return (
        re.search(r"^(?:import|from)\s+tensorflow\b", source, re.MULTILINE) is not None
        or "tf.keras" in source
        or "tensorflow.keras" in source
    )


def _looks_like_keras_source(path: Path) -> bool:
    source = _read_text(path)
    return re.search(r"^(?:import|from)\s+keras\b", source, re.MULTILINE) is not None or "keras.models" in source


def _looks_like_sklearn_source(path: Path) -> bool:
    source = _read_text(path)
    return re.search(r"^(?:import|from)\s+sklearn\b", source, re.MULTILINE) is not None or "scikit-learn" in source.lower()


def _looks_like_transformers_source(path: Path) -> bool:
    source = _read_text(path)
    return (
        re.search(r"^(?:import|from)\s+transformers\b", source, re.MULTILINE) is not None
        or "AutoModel" in source
        or "AutoTokenizer" in source
        or "pipeline(" in source and "transformers" in source
    )


def _looks_like_mlflow_source(path: Path) -> bool:
    source = _read_text(path)
    return re.search(r"^(?:import|from)\s+mlflow\b", source, re.MULTILINE) is not None or "mlflow." in source


def _looks_like_wandb_source(path: Path) -> bool:
    source = _read_text(path)
    return re.search(r"^(?:import|from)\s+wandb\b", source, re.MULTILINE) is not None or "wandb." in source


def _looks_like_hydra_source(path: Path) -> bool:
    source = _read_text(path)
    return "@hydra.main" in source or "hydra.compose" in source or "OmegaConf" in source


def _looks_like_hydra_config(path: Path) -> bool:
    source = _read_text(path)
    normalized = path.as_posix().lower()
    if "/.circleci/" in f"/{normalized}" or "/.github/workflows/" in f"/{normalized}":
        return False
    in_hydra_config_dir = "/conf/" in f"/{normalized}" or "/configs/" in f"/{normalized}"
    has_defaults = re.search(r"^\s*defaults\s*:", source, re.MULTILINE) is not None
    has_explicit_hydra = (
        re.search(r"^\s*_target_\s*:", source, re.MULTILINE) is not None
        or re.search(r"^\s*hydra\s*:", source, re.MULTILINE) is not None
    )
    return has_explicit_hydra or (in_hydra_config_dir and has_defaults)


def _looks_like_streamlit_source(path: Path) -> bool:
    source = _read_text(path)
    return "import streamlit" in source or "streamlit." in source or re.search(r"\bst\.(?:title|write|sidebar|cache|button|dataframe|plotly_chart)\b", source) is not None


def _looks_like_gradio_source(path: Path) -> bool:
    source = _read_text(path)
    return "import gradio" in source or "gradio." in source or re.search(r"\bgr\.(?:Interface|Blocks|ChatInterface|TabbedInterface)\b", source) is not None


def _looks_like_riverpod_source(path: Path) -> bool:
    source = _read_text(path)
    return (
        "package:flutter_riverpod/" in source
        or "package:hooks_riverpod/" in source
        or "package:riverpod_annotation/" in source
        or "ProviderScope(" in source
        or re.search(r"\bref\.(?:watch|read|refresh|listen)\s*\(", source) is not None
        or re.search(r"\b(?:FutureProvider|StreamProvider|StateProvider|Provider)\s*(?:<[^>]+>)?\s*\(", source) is not None
    )


def _looks_like_flutter_hooks_source(path: Path) -> bool:
    source = _read_text(path)
    return "package:flutter_hooks/" in source or re.search(r"\buse(?:State|Effect|Memoized|Future|Stream)\s*\(", source) is not None


def _looks_like_routerino_source(path: Path) -> bool:
    source = _read_text(path)
    return "package:routerino/" in source or "RouterinoHome(" in source or "Routerino.context" in source


def _looks_like_dio_source(path: Path) -> bool:
    source = _read_text(path)
    return "package:dio/" in source or "Dio(" in source or re.search(r"\b_?[A-Za-z_]\w*\.get\s*\(\s*['\"]/", source) is not None


def _looks_like_freezed_source(path: Path) -> bool:
    source = _read_text(path)
    return "package:freezed_annotation/" in source or "@freezed" in source or "with _$" in source


def _looks_like_tca_source(path: Path) -> bool:
    source = _read_text(path)
    return (
        "import ComposableArchitecture" in source
        or "@Reducer" in source
        or "@ObservableState" in source
        or "StoreOf<" in source
        or "TestStore(" in source
    )


def _looks_like_strapi_source(path: Path) -> bool:
    normalized = path.as_posix().lower()
    source = _read_text(path)
    if normalized.endswith("schema.json") and (
        "/content-types/" in f"/{normalized}" or "/components/" in f"/{normalized}"
    ):
        return '"attributes"' in source and ('"collectionType"' in source or '"singleType"' in source or '"info"' in source)
    if not normalized.endswith((".ts", ".js", ".mjs", ".cjs")):
        return False
    if "@strapi/strapi" in source or "createCoreRouter" in source or "createCoreController" in source or "createCoreService" in source:
        return True
    if "api::" in source and ("/src/api/" in f"/{normalized}" or normalized.startswith("api/src/api/")):
        return True
    return False


def _is_remix_package(name: str) -> bool:
    return name in REMIX_PACKAGES


def _looks_like_symfony_project_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return normalized.startswith("src/controller/") or normalized.startswith("config/")


def _looks_like_play_build(path: Path) -> bool:
    source = _read_text(path)
    return "PlayScala" in source or "PlayJava" in source or "playframework" in source.lower() or "play-" in source.lower()


@lru_cache(maxsize=32768)
def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _add(
    detected: dict[tuple[str, str], FrameworkFact],
    name: str,
    category: str,
    source: str,
    confidence: float,
    evidence: Evidence,
) -> None:
    key = (category, name)
    current = detected.get(key)
    if current is None or confidence > current.confidence:
        detected[key] = FrameworkFact(
            name=name,
            category=category,
            source=source,
            confidence=confidence,
            evidence=evidence,
        )

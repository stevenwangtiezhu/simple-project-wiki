# Wiki Structure

Use this file to choose a `.spwiki/<language>/content` structure after scanning the project. The default language is `zh`; `en` is also supported by the scripts. Custom project topics belong in `.spwiki/topic-overrides.json`, not in the skill source.

## Universal Shape

Every project wiki should start with:

```text
.spwiki/
└── zh/
    └── content/
        ├── 项目概述.md
        ├── 快速开始.md
        ├── 故障排除指南.md
        ├── 架构设计/
        │   └── 架构设计.md
        ├── 核心模块/
        │   └── 核心模块.md
        ├── 开发指南/
        │   └── 开发指南.md
        ├── 构建与部署/
        │   └── 构建与部署.md
        └── 安全与权限/
            └── 安全与权限.md
```

For English wikis the same logical shape is localized, for example:

```text
.spwiki/
└── en/
    └── content/
        ├── Project Overview.md
        ├── Quick Start.md
        ├── Troubleshooting Guide.md
        ├── Architecture/
        │   └── Architecture.md
        └── Core Modules/
            └── Core Modules.md
```

Use same-name index pages for every topic directory. For example, `核心模块/核心模块.md` summarizes the child pages under `核心模块/`.

## Depth Profiles

- `light`: root pages plus 4-6 topic directories. Best for small libraries or fast onboarding.
- `balanced`: root pages plus 7-10 topic directories and a few key module pages.
- `deep`: RepoWiki-like depth with topic directories, same-name index pages, and subdirectories for major modules. This is the default for large projects and monorepos.
- `deep` also creates index/matrix pages such as API route, auth, configuration, data model, risk, subproject dependency, and third-party service indexes when useful.

## Java / Spring Backend

Prefer these topics:

```text
API接口文档/
安全与权限/
数据库设计/
架构设计/
核心模块/
部署与运维/
开发指南/
扩展开发/
性能优化/
配置管理/
```

Common child pages:
- `架构设计/分层架构设计/Controller层设计.md`
- `架构设计/分层架构设计/Service层设计.md`
- `架构设计/分层架构设计/DAO层设计.md`
- `数据库设计/MyBatis映射配置.md`
- `数据库设计/数据库表结构设计.md`
- `安全与权限/认证与授权.md`
- `安全与权限/安全防护/API接口安全防护.md`
- `部署与运维/环境准备与配置.md`

## Frontend Web App

Prefer these topics:

```text
API接口层/
UI组件库/
状态管理系统/
页面视图组件/
架构设计/
配置管理/
构建与部署/
安全考虑/
性能优化/
扩展开发/
工具函数库/
```

Common child pages:
- `页面视图组件/认证页面系统.md`
- `页面视图组件/主页布局设计.md`
- `状态管理系统/全局状态管理.md`
- `API接口层/API基础配置.md`
- `UI组件库/布局组件.md`
- `构建与部署/开发环境配置.md`

## Electron / Desktop App

Add these when Electron or desktop packaging is present:

```text
桌面应用集成/
桌面应用集成/Electron主进程配置.md
桌面应用集成/IPC进程间通信.md
桌面应用集成/窗口管理系统.md
桌面应用集成/自动更新机制.md
```

## Mobile / uni-app

Add these when `pages.json`, `manifest.json`, `uni-app`, native plugins, or mobile platform folders are present:

```text
移动端应用架构/
页面路由系统/
原生能力集成/
状态管理系统/
平台适配/
构建与发布/
```

## Library / SDK

Use a smaller structure:

```text
项目概述.md
快速开始.md
API参考/
核心模块/
数据模型设计/
扩展开发/
测试与调试.md
```

Focus on public API, examples, extension points, compatibility, and tests.

## Project Overrides

When a project needs domain-specific topics, create `.spwiki/topic-overrides.json`:

```json
{
  "append_topics": [
    {
      "key": "domain-workflows",
      "title": "Domain Workflows",
      "children": ["Order Flow", "Settlement Flow"]
    }
  ]
}
```

Use overrides to add business-specific pages without making the shared skill project-specific.

## Monorepo

For monorepos:
- Root wiki: describe repository layout, shared dependencies, cross-project data flow, build order, shared infrastructure, and integration risks.
- Subproject wiki: describe the subproject as if it were maintained independently.
- Cross-project protocols or schemas should be documented in the root wiki and repeated only briefly in subproject pages.

Example:

```text
repo/.spwiki/zh/content/项目概述.md
repo/backend/.spwiki/zh/content/项目概述.md
repo/admin/.spwiki/zh/content/项目概述.md
repo/web/.spwiki/zh/content/项目概述.md
repo/mobile/.spwiki/zh/content/项目概述.md
```

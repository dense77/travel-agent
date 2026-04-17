"""作用：
- 标记 `travel_agent` 为顶层 Python 包。

约定：
- 项目的 Web 启动入口在 `travel_agent.app.main`。
- 这个文件不放运行期副作用，避免导入包时偷偷创建全局资源。
"""

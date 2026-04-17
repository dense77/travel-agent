# 旅游规划 Agent 最小可运行闭环

本仓库当前交付的是一个“最小可运行闭环”后端，不是完整产品。

它已经能跑通下面这条链路：

`POST /sessions` 创建会话 -> `POST /sessions/{session_id}/run` 触发工作流 -> `Planner` 生成计划 -> `Executor` 调用 `Mock Skill` -> `GET /sessions/{session_id}` 查询结果

当前实现与代码严格一致：
- 有 FastAPI 接口
- 有 LangGraph 工作流
- 有按城市条件分支的 LangGraph 演示
- 有 Planner / Executor 分层
- 有内存态会话存储
- 有一个 `mock_travel` 技能
- 没有前端页面
- 没有真实模型调用
- 没有 RAG / Milvus / Redis / 数据库 / 外部旅游 API

## 1. README：怎么启动、怎么跑、怎么验证

### 运行环境

- Python 3.9
- 当前依赖文件名是 [`requirments.txt`](/Users/dense77/Desktop/Agent/旅游规划agent/requirments.txt)

说明：
- 文件名是 `requirments.txt`，不是常见的 `requirements.txt`
- 这是当前仓库真实状态，README 不做重命名假设

### 安装依赖

```bash
python3 -m pip install -r requirments.txt
```

### 启动服务

优先使用下面这条命令：

```bash
python3 -m uvicorn travel_agent.app.main:app --reload
```

说明：
- 某些环境里 `uvicorn` 脚本不在 `PATH`，直接写 `uvicorn ...` 可能报 `command not found`
- `python3 -m uvicorn ...` 更稳，和当前交付验证一致

启动成功后访问：

- Swagger 文档: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 最短验证方式

仓库内已经提供了 3 个最小测试脚本，目录在 [`test_requests`](/Users/dense77/Desktop/Agent/旅游规划agent/test_requests)：

- [`create_session.py`](/Users/dense77/Desktop/Agent/旅游规划agent/test_requests/create_session.py)
- [`run_session.py`](/Users/dense77/Desktop/Agent/旅游规划agent/test_requests/run_session.py)
- [`get_session.py`](/Users/dense77/Desktop/Agent/旅游规划agent/test_requests/get_session.py)

按顺序执行：

```bash
python3 test_requests/create_session.py
```

示例输出：

```json
{"session_id":"sess_xxxxxxxx","status":"created"}
```

把上一步返回的 `session_id` 带入下面两条命令：

```bash
python3 test_requests/run_session.py <session_id>
```

```bash
python3 test_requests/get_session.py <session_id>
```

### 条件分支演示

如果你是想学习 LangGraph 的条件分支，可以直接运行这个脚本：

```bash
python3 demo_langgraph_city_branch.py
```

它会连续演示 4 个输入：

- 上海 -> `shanghai_branch`
- 北京 -> `beijing_branch`
- 杭州 -> `hangzhou_branch`
- 苏州 -> `other_city_branch`

运行时你会在控制台看到类似下面的节点输出：

```text
[LangGraph Demo] planner -> 已生成基础旅行计划
[LangGraph Demo] city_selector -> 识别到城市：上海
[LangGraph Demo] route_by_city -> selected_city=上海，命中分支：shanghai_branch
[LangGraph Demo] shanghai_branch -> 进入上海分支，准备生成上海城市玩法建议。
[LangGraph Demo] executor -> 开始执行计划，当前分支：shanghai_branch
[LangGraph Demo] result -> 汇总完成，最终分支：shanghai_branch
```

对应的条件分支定义在：

- [`travel_agent/app/graph/workflow.py`](/Users/dense77/Desktop/Agent/旅游规划agent/travel_agent/app/graph/workflow.py)
- [`travel_agent/app/graph/nodes.py`](/Users/dense77/Desktop/Agent/旅游规划agent/travel_agent/app/graph/nodes.py)

重点是这段 `LangGraph` 写法：

```python
graph.add_conditional_edges(
    "city_selector",
    route_by_city,
    {
        "shanghai_branch": "shanghai_branch",
        "beijing_branch": "beijing_branch",
        "hangzhou_branch": "hangzhou_branch",
        "other_city_branch": "other_city_branch",
    },
)
```

### 也可以直接在 Swagger 里手动验证

顺序如下：

1. 调用 `POST /sessions`
2. 复制返回的 `session_id`
3. 调用 `POST /sessions/{session_id}/run`
4. 再调用 `GET /sessions/{session_id}`

推荐输入：

```json
{
  "query": "五一从上海去杭州玩三天，预算3000，想看西湖和灵隐寺",
  "constraints": {
    "budget": 3000,
    "start_city": "上海",
    "travel_days": 3
  }
}
```

预期结果：
- `create` 返回 `status: created`
- `run` 返回 `status: finished`
- `get` 返回 `current_plan`、`observations`、`final_result`
- `final_result.answer` 中可看到 `Hangzhou`、`West Lake`、`Lingyin Temple`

## 2. 设计说明：为什么这么设计，核心结构是什么

### 为什么当前这样设计

当前交付目标不是做完整旅行产品，而是先把“最小闭环”做成真的能运行、能演示、能交接的工程骨架。

因此这版刻意只保留最少必需结构：

- API 层负责接请求和回结果
- Graph 层负责工作流编排
- Planner 负责产出一步计划
- Executor 负责执行计划
- Skill 层负责封装一个可调用能力
- Memory 层负责保存会话状态

这样做的原因：
- 能真实体现文档里的“双层 Agent + 工作流编排”方向
- 能把复杂能力留到后续迭代，不把骨架做散
- 能在没有真实外部依赖的情况下先证明主链路是通的

### 当前核心结构

代码入口：
- 应用入口在 [`travel_agent/app/main.py`](/Users/dense77/Desktop/Agent/旅游规划agent/travel_agent/app/main.py)
- API 路由在 [`travel_agent/app/api/routes/sessions.py`](/Users/dense77/Desktop/Agent/旅游规划agent/travel_agent/app/api/routes/sessions.py)
- 工作流在 [`travel_agent/app/graph/workflow.py`](/Users/dense77/Desktop/Agent/旅游规划agent/travel_agent/app/graph/workflow.py)

最小结构如下：

```text
travel_agent/
  app/
    api/routes/sessions.py
    graph/workflow.py
    graph/nodes.py
    graph/state.py
    agents/planner/agent.py
    agents/executor/agent.py
    agents/contracts.py
    memory/memory_store.py
    skills/base.py
    skills/registry.py
    skills/mock_travel.py
    main.py
```

### 当前工作流

实际流程如下：

1. `POST /sessions`
2. `InMemoryMemoryStore.create_session`
3. `POST /sessions/{id}/run`
4. `TravelGraphWorkflow.invoke`
5. `planner` 节点调用 [`PlannerAgent`](/Users/dense77/Desktop/Agent/旅游规划agent/travel_agent/app/agents/planner/agent.py)
6. `executor` 节点调用 [`ExecutorAgent`](/Users/dense77/Desktop/Agent/旅游规划agent/travel_agent/app/agents/executor/agent.py)
7. `ExecutorAgent` 通过 [`SkillRegistry`](/Users/dense77/Desktop/Agent/旅游规划agent/travel_agent/app/skills/registry.py) 调用 [`MockTravelSkill`](/Users/dense77/Desktop/Agent/旅游规划agent/travel_agent/app/skills/mock_travel.py)
8. `result` 节点组装 `final_result`
9. `GET /sessions/{id}` 查询最终状态

### 每层当前职责

`api`
- 提供 3 个接口：创建、运行、查询

`graph`
- 用 LangGraph 串起 `planner -> executor -> result`

`planner`
- 固定产出 1 个步骤
- 该步骤指定调用 `mock_travel`

`executor`
- 读取计划步骤
- 执行工具调用
- 把工具结果转成结构化 observation

`memory`
- 仅做进程内会话保存
- 服务重启后数据会丢失

`skills`
- 当前只有 1 个 Mock Skill
- 返回确定性的演示数据

## 3. 测试说明：验证了什么，还有什么没验证

### 已验证内容

已经实际验证过以下内容：

1. 服务可以成功启动
2. `/docs` 可以打开
3. `POST /sessions` 可以创建会话
4. `POST /sessions/{session_id}/run` 可以跑完整个最小闭环
5. `GET /sessions/{session_id}` 可以查到执行后的最终状态
6. `Planner -> Executor -> Mock Skill -> Result` 这一条主链路是通的
7. Python 3.9 兼容性问题已经修正过一次，当前代码可以在 3.9 环境运行

### 当前验证方式

当前验证方式只有两种：

- Swagger 手动调用
- [`test_requests`](/Users/dense77/Desktop/Agent/旅游规划agent/test_requests) 目录下的 3 个脚本

这说明当前是“人工验收 + 脚本验收”，不是自动化测试体系。

### 还没有验证的内容

以下内容当前没有验证，也没有实现：

- pytest 单元测试
- 集成测试框架
- 端到端自动回归
- 并发场景
- 异常恢复
- 超时控制
- RePlan
- RAG 检索
- 外部 API 调用
- 数据持久化
- 权限控制
- 性能压测

### 一个需要注意的验证细节

`run_session.py` 和 `get_session.py` 必须按顺序验证。

如果并发执行：
- `run_session.py` 可能已经完成
- 但 `get_session.py` 也可能刚好查到运行前状态

这不是接口错误，而是当前实现没有异步任务队列，查询结果取决于请求到达时点。

## 4. 风险与限制：哪些问题是已知的，为什么当前仍可接受

### 已知限制

1. 结果是 Mock，不是真实旅游规划
原因：
- 当前 `MockTravelSkill` 只根据关键词返回固定结构化结果

2. 没有真实模型调用
原因：
- 当前没有接 LLM，也没有 Prompt 设计

3. 没有 RAG / Milvus
原因：
- 当前闭环只验证工作流，不验证知识检索链路

4. 没有 Redis / 数据库
原因：
- 当前使用 [`InMemoryMemoryStore`](/Users/dense77/Desktop/Agent/旅游规划agent/travel_agent/app/memory/memory_store.py)
- 服务一重启，会话状态就丢失

5. 没有 RePlan
原因：
- 当前工作流只跑单次 `planner -> executor -> result`

6. 没有真实外部服务
原因：
- 没有接高德地图、酒店、12306、图片检索

7. 没有自动化评估体系
原因：
- 当前没有实现 `evaluation` 模块

8. 没有前端页面
原因：
- 当前只有 FastAPI 后端和 Swagger 文档页

### 为什么当前仍可接受

这些限制在“最小闭环交付”阶段仍可接受，原因只有一个：当前目标是验证工程主链路，而不是验证业务完整度。

现在已经能确认：
- 路由是通的
- 状态图是通的
- Agent 分工是通的
- Skill 调用机制是通的
- 结果组装和状态查询是通的

对下一阶段来说，这些是最关键的骨架验证结果。

### 需要交接时特别说明的事实

交接时不要把当前版本描述成：
- 完整旅游助手
- 多轮智能规划系统
- 可用的生产系统

更准确的说法应该是：

“这是一个已跑通最小闭环的后端骨架，证明了双层 Agent 工作流、Skill 调用和会话状态流转可以成立，但真实业务能力还没有接入。”

## 5. 演示顺序：如果只有几分钟，应该按什么顺序展示

如果只有 3 到 5 分钟，建议按下面顺序演示。

### 第 1 步：先说清楚这次演示的边界

一句话说明：

“这次演示的是后端最小可运行闭环，不是完整产品页面。重点是证明 API、工作流、Planner/Executor 和 Skill 调用已经打通。”

### 第 2 步：展示 `/docs`

打开：

- [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

只强调 3 个接口：
- `POST /sessions`
- `POST /sessions/{session_id}/run`
- `GET /sessions/{session_id}`

### 第 3 步：演示创建会话

调用 `POST /sessions`。

讲解重点：
- 用户请求先进入会话
- 系统返回一个 `session_id`

### 第 4 步：演示运行闭环

调用 `POST /sessions/{session_id}/run`。

讲解重点：
- LangGraph 工作流启动
- Planner 先生成一步计划
- Executor 调用 `mock_travel`
- 返回结构化结果

### 第 5 步：演示查询最终状态

调用 `GET /sessions/{session_id}`。

讲解重点：
- 可以看到 `current_plan`
- 可以看到 `observations`
- 可以看到 `final_result`

### 第 6 步：最后再打开代码入口

如果对方还要看代码，只打开 4 个文件即可：

- [`travel_agent/app/main.py`](/Users/dense77/Desktop/Agent/旅游规划agent/travel_agent/app/main.py)
- [`travel_agent/app/api/routes/sessions.py`](/Users/dense77/Desktop/Agent/旅游规划agent/travel_agent/app/api/routes/sessions.py)
- [`travel_agent/app/graph/workflow.py`](/Users/dense77/Desktop/Agent/旅游规划agent/travel_agent/app/graph/workflow.py)
- [`travel_agent/app/skills/mock_travel.py`](/Users/dense77/Desktop/Agent/旅游规划agent/travel_agent/app/skills/mock_travel.py)

这样别人能在最短时间里看懂：
- 从哪里启动
- 从哪里进接口
- 工作流怎么串
- 技能结果从哪里来

## 当前交付结论

当前仓库适合作为“最小闭环交付版本”继续向下迭代。

它已经具备：
- 可启动
- 可调用
- 可演示
- 可交接

它还不具备：
- 真实业务能力
- 自动化测试体系
- 可长期运行的状态存储
- 生产级稳定性

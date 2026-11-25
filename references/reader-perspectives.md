# 按读者要完成的任务组织源码导读

选页前，试着补完这句话：“读完这一页，读者能独立＿＿。”用一个可检查的动作填空，如预测结果、选择接口、定位故障。优先依据用户给出的目标。只给出角色时，结合提问和对项目的熟悉程度判断；沿用 skill 的默认读者时，可从第一种结构起步。以下结构可以裁剪，标题用项目中的具体问题来写。

例如，“第一次读 Pi，正在给编辑器接入会话恢复”同时提供了经验和任务。用一小段介绍会话与分支，正文直接进入接入者需要的输入、返回值和边界条件。如果随后改问“修复恢复逻辑要保住哪些行为”，可以复用同一份源码证据，改从维护者的回归用例切入。

## 初次接触项目：预测一次操作的结果

从读者做过的动作开篇，给出输入，跟到第一个可见结果。途中遇到职责交接时，再引入负责的组件。随后改变一个条件，让读者预测会看到什么。适合的页面顺序是“发起一次操作 → 数据经过谁 → 结果为何改变”。架构图帮助定位角色，流程页只展开决定结果的交接。[架构地图](https://claudecn.com/docs/source-analysis/architecture/) · [运行时流程](https://claudecn.com/docs/source-analysis/runtime/)

## SDK 接入者或扩展作者：选对接口并接通一次调用

以要增加的具体行为开篇，找到最小公开入口。先交代调用者提供什么、宿主何时调用、结果怎样返回，再走一遍成功路径。把注册时机、生命周期或权限条件放在会改变结果的那一步。结尾给一个可观察的成功结果，让接入者能区分“已经注册”和“实际执行过”。[工具平面](https://claudecn.com/docs/source-analysis/tools/) · [插件系统](https://claudecn.com/docs/source-analysis/plugins/) · [MCP 与 Bridge](https://claudecn.com/docs/source-analysis/mcp-bridge/)

## 维护者：判断改动影响，并选出回归用例

先举一个用户依赖的现有行为。沿调用点找到状态的拥有者、写入位置和消费结果的一方。改变分支、顺序或配置，说明影响会传到哪里。用一对有区分力的输入收尾，写出各自的预期结果；已有测试就链接断言，新增用例的想法标为建议。读者据此能指出应改哪一层，以及哪条约束要保住。[记忆系统](https://claudecn.com/docs/source-analysis/memory/) · [权限治理](https://claudecn.com/docs/source-analysis/governance/)

## 排障者：用一个观察点区分两种原因

从具体症状开始，按失败可能发生的位置分支。为每个候选原因找一个能支持或排除它的观察点，如返回值、事件顺序、持久化字段。按“看到什么 → 能判定什么 → 下一处查哪里”排列步骤；涉及成本或次数时先说清统计口径。源码没有提供可用日志时，给出可检查的调用点，注明仍需采集的现场信息。[Hooks 韧性](https://claudecn.com/docs/source-analysis/hooks-resilience/) · [成本追踪](https://claudecn.com/docs/source-analysis/cost-usage/)

## 团队实践者：决定哪些做法适合迁移

从团队眼前的工程决定切入，交代原项目为哪项约束付出了什么成本。判断团队是否有相同约束，再选一条可以先试的最短路径。按依赖关系安排阶段，每阶段写出可检查的产物，例如能力目录、权限边界或一次独立验证的结果。最后给出决定是否扩大使用的依据。[工程落地清单](https://claudecn.com/docs/source-analysis/engineering-playbook/) · [Coordinator 编排](https://claudecn.com/docs/source-analysis/coordinator/)

## 源码研究者或技术评估者：判断一项能力有多少证据

把待判断的主张写具体，先限定提交、入口和配置。沿声明、注册、可达调用、结果或测试逐项追查，指出哪一步证据充分、哪里还需要验证。结尾用与证据相称的动词写结论，例如“定义了类型”“在此配置下注册”“测试断言了该结果”。若判断公开可用性还依赖服务端开关，单列这个未知条件。[研究方法](https://claudecn.com/docs/source-analysis/research-method/) · [扩展与信号](https://claudecn.com/docs/source-analysis/signals/)

以上六种结构是对 Claude 中文社区源码分析专栏的编辑归纳。需要对照同一机制面向不同读者的成文效果时，可读[按读者展开的示例](page-patterns.md)。

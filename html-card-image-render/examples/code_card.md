# 智能编排策略卡片

## 背景
- 目标：把多节点任务调度可视化并用于评审汇报
- 关注：吞吐、延迟、稳定性三者平衡

## 核心规则
- 优先分配低延迟队列给实时任务
- 批处理任务在资源空闲窗口并行执行
- 当错误率升高时，自动降级并切换保守策略

## 伪代码
```python
def schedule(job, state):
    if job.realtime:
        return "fast-lane"
    if state.error_rate > 0.02:
        return "safe-mode"
    return "batch-lane"
```

## 结论
- 使用统一策略后，线上波动明显下降
- 建议每周复盘一次阈值配置

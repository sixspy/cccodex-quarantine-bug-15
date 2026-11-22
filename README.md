# cc-quarantine-lab

CC_Codex 二期（26.11）**数据工程**产品线：**抓取隔离舱检疫台**（Pyramid + Waitress + 原生 JS SPA 右侧抽屉 + SQLite）。

## 一句话骨架

**抓取批次 → 坏件入隔离舱 → 复核放行 / 回炉重抓 → 隔离对账**

与血缘影响、压实合并、回灌切片、契约换版、水印盖印、清单闭合、留存裁撤**正交**；不做 CDC 游标 / Feed 归并 / Slicegate 类指纹。

## 领域

- **所属领域**：数据工程
- **子方向偏采集**：源站抓取结果检疫、坏件隔离、回炉重抓、隔离对账

## 页面（≥8）

1. 抓取批次 2. 隔离舱 3. 复核放行 4. 回炉队列 5. 隔离对账  
6. 源站名册 7. 入舱规则 8. 审计轨迹 9. 台参数

## 本地

http://127.0.0.1:7500/login · **admin / 123456** · 端口 **7500**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest
python run.py
```

## 预留切口（未做）

入舱半失败闭、复核与回炉二选一命运、并发争抢写锁、对账快照与现行舱双写等，出题可切。

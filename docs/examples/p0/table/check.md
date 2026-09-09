# 核对报告

## 执行与调用依据
- 实际应用：SkillNav 流程及 local-sales；已从任务根目录运行其 scripts/audit.py，退出码 0。
- 宿主启用状态：依据用户提供的测试宿主确认；local-sales 的 agents/openai.yaml 允许隐式调用。
- Python 实际版本：3.11.9；脚本仅依赖标准库。
- cloud-sales 仅作为候选读取，未执行：当前宿主无 cloud_sales_upload，且输入不含 customer_id、net_amount。

## 独立文件核对
- 核对器重新读取 sales.csv 与 totals.csv，使用 Fraction 有理数逐商品重算，未调用技能的 Decimal 汇总代码。
- 输入 3 条，输出 2 个商品；列名 product,total、商品去首尾空格、排序、唯一性及两位小数均通过断言。
- 各商品金额与源数据逐项一致，总金额 19.80；原输入及所用技能源文件的执行前后 SHA-256 一致。

| 商品 | 核对金额 |
| --- | ---: |
| 台灯 | 7.50 |
| 笔记本 | 12.30 |

## 文件证据
- sales.csv SHA-256：`500d45547952a545d0807712a83af152b98f93748900d04525fee5bbad296183`
- totals.csv SHA-256：`469d41051004b8f500d256359ce047773361f8f69e6adc3073160746558bd02a`
- audit.py SHA-256：`bf4189d853e4db7a08b4dd717b4e6f22f61a00e0c869546cff4308f4e7f3f9dd`

## 证据范围
- 上述结果来自实际脚本执行、产物读取和独立算法断言；本报告由核对程序写入。
- 模型判断：local-sales 适用于本次格式和本地执行边界；该判断不是工具回执，也不表示用户已验收。
- 本次未联网、安装、对外操作或读写长期记忆；仅新增 totals.csv 和 check.md。

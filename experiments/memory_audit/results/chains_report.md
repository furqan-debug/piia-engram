# Engram 集成链审计报告

日期: 2026-05-27 00:55:22

结果: 10/10 PASS, 0 FAIL, 0 SKIP

| Case | 结果 | 备注 |
|------|------|------|
| C1 身份→上下文 | PASS | tmp=E:\Temp\engram_chain_f9e_3tna; role_in_context=True |
| C2 写入→搜索→计数 | PASS | tmp=E:\Temp\engram_chain_p2f3yrn3; access_count 0->1 |
| C3 Staging→晋升 | PASS | tmp=E:\Temp\engram_chain_n7qc2pkb; tier=verified; promoted=1 |
| C4 Session保存→恢复 | PASS | tmp=E:\Temp\engram_chain_aoepshdk; session_id=2026-05-27T00-55-20 |
| C5 wrap_up全链 | PASS | tmp=E:\Temp\engram_chain_7mr8k7qv; insights={'saved_lessons': 1, 'saved_decisions': 1, 'duplicates': 0, 'skipped': 1, 'results': [{'type': 'lesson', 'status': 'saved', 'id': '9df518998085', 'summary': 'chain C5：注意部署前必须检查环境变量', 'domain': ''} |
| C6 Playbook执行链 | PASS | tmp=E:\Temp\engram_chain_o99l4wqf; completed=2/3 |
| C7 冲突检测 | PASS | tmp=E:\Temp\engram_chain_cysyfq90; conflicts=1 |
| C8 Dedup→合并 | PASS | tmp=E:\Temp\engram_chain_3tn7ql96; suggestions=1 total=None |
| C9 Health联动 | PASS | tmp=E:\Temp\engram_chain_1yfn7cy9; health 82->57; stale_hit=True |
| C10 Identity Card聚合 | PASS | tmp=E:\Temp\engram_chain_ej1g_0dt; card_len=351 |

## 说明

每条链均使用独立临时 Engram(root=tmp) 实例，不影响真实数据。

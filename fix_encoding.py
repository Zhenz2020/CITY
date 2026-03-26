#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复 planning_agent.py 中的中文乱码问题
"""

# 读取文件
with open('city/agents/planning_agent.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 检查文件中包含的乱码字符
# 常见乱码字符集
garbled_chars = set()
for char in content:
    if '\u4e00' <= char <= '\u9fff':  # 中文字符范围
        # 检查是否是常见乱码字符（生僻字或特定编码错误产生的字符）
        if char in '璺綉瑙勫垝鏅鸿兘浣浜彛椹姩鍩競婕斿寲簬瀵瘧鎵睍櫤綋鑳噴掔閬厤闀挎潯傚竵敞亾閬缁滄墿煄鍒鍛鍗忓宸ヤ綔銆鍒涘缓鏂扮疆璁＄畻鎴戜滑鏄剧ず鍒欏紡鍒欐柟寮忕殑鎰熺煡鍐虫柇鍩庡競鐘舵€佸綋鍉嶄笌鍏堣繘鍒跺畾绗鍧愭爣鍐呴儴鍒涘缓鐢熸垚鍒犻櫎鏇存柊鍒ゆ柇澶勭悊杈撳叆杈撳嚭鏍囧噯鍖栧厤鐢靛瓙鍟嗗姟鍒嗘瀽':
            garbled_chars.add(char)

# 写入结果
with open('garbled_chars.txt', 'w', encoding='utf-8') as f:
    f.write(f"发现的乱码字符: {sorted(garbled_chars)}\n")
    f.write(f"共 {len(garbled_chars)} 个不同字符\n")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分析文件中剩余的所有乱码字符"""

with open('city/agents/planning_agent.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 收集所有中文字符
garbled_chars = set()
for char in content:
    if '\u4e00' <= char <= '\u9fff':  # CJK 统一表意文字
        garbled_chars.add(char)

# 写入结果文件
with open('remaining_chars.txt', 'w', encoding='utf-8') as f:
    f.write("文件中所有中文字符（按Unicode排序）：\n")
    for char in sorted(garbled_chars):
        f.write(f"{char} (U+{ord(char):04X})\n")
    f.write(f"\n共 {len(garbled_chars)} 个不同字符\n")

print(f"发现 {len(garbled_chars)} 个不同中文字符")

# 分析编码问题
with open('encoding_result.txt', 'w', encoding='utf-8') as f:
    chars = '路网规划智能体'
    for c in chars:
        encoded = c.encode("utf-8").hex()
        f.write(f'{c}: U+{ord(c):04X} = {encoded}\n')

    f.write("---\n")
    chars2 = '璺綉瑙勫垝鏅鸿兘浣'
    for c in chars2:
        encoded = c.encode("utf-8").hex()
        f.write(f'{c}: U+{ord(c):04X} = {encoded}\n')
